"""Offline migration, atomic publication, identity ownership and replay."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D
import json
import sqlite3
from unittest.mock import patch
import pytest
from backend.bot.executor.execution_journal import ExecutionJournal, JournalError, upgrade_accounting_schema
from backend.tests.unit.test_accounting_models import context, order, fact


def seed(path, filled=0):
    journal = ExecutionJournal(path, "fixture")
    now = datetime.now(timezone.utc).isoformat()
    intent = dict(order_id="order", symbol="BTC/USDT:USDT", side="BUY", order_type="LIMIT", quantity=10,
        price=100, stop_price=None, purpose="entry", reduce_only=False, owner="fixture", generation="fixture",
        wire=dict(symbol="BTC/USDT:USDT", side="buy", amount=10, params={"clientOrderId": "order"}))
    state = dict(status="FILLED" if filled else "OPEN", filled_quantity=filled,
        average_fill_price=100 if filled else 0, exchange_id="remote", unknown_reason=None,
        cancel_requested=False, rejection_reason=None, created_at=now, updated_at=now)
    journal.submit_intent(intent, state)
    journal.close()
    return intent, state


@pytest.fixture
def store(tmp_path):
    path = tmp_path / "execution.sqlite3"
    seed(path)
    upgrade_accounting_schema(path, "fixture", environment="testnet")
    journal = ExecutionJournal(path, "fixture")
    yield journal
    journal.close()


def rows(path, table):
    with sqlite3.connect(path) as con:
        return con.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()


def test_default_v1_is_unchanged_and_migration_requires_exclusive_owner(tmp_path):
    path = tmp_path / "execution.sqlite3"
    seed(path)
    journal = ExecutionJournal(path, "fixture")
    try:
        assert journal.schema_version == 1
        with pytest.raises(JournalError, match="upgrade"):
            journal.record_accounting(order())
        with pytest.raises(JournalError, match="owned"):
            upgrade_accounting_schema(path, "fixture", environment="testnet")
        assert {r[0] for r in journal._connection.execute("SELECT name FROM sqlite_master WHERE type='table'")} == {"metadata", "requests", "events"}
    finally:
        journal.close()


def test_upgrade_preserves_legacy_marker_records_clean_flag_and_verified_backup(tmp_path):
    path = tmp_path / "execution.sqlite3"
    seed(path, filled=10)
    marker = path.with_suffix(".initialized").read_bytes()
    old_requests, old_events, meta = rows(path, "requests"), rows(path, "events"), rows(path, "metadata")
    result = upgrade_accounting_schema(path, "fixture", environment="testnet")
    assert path.with_suffix(".initialized").read_bytes() == marker
    assert rows(path, "requests") == old_requests
    assert rows(path, "events")[:len(old_events)] == old_events
    assert rows(path, "metadata")[0][-1] == meta[0][-1]
    assert rows(result["backup"], "requests") == old_requests
    assert rows(result["backup"], "events") == old_events
    before = rows(path, "events")
    assert upgrade_accounting_schema(path, "fixture", environment="testnet")["already_upgraded"]
    assert rows(path, "events") == before
    j = ExecutionJournal(path, "fixture")
    try:
        state = j.financial_state("order")
        assert state.legacy_quantity == 10 and state.filled_quantity == 0 and state.cost is None
        assert not state.financially_complete
        assert j._connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
    finally:
        j.close()


def test_order_and_execution_overlap_survives_reopen_without_cash_replay(store):
    path = store.path
    first = store.record_accounting(order("4", "400", status="OPEN"))["state"]
    assert first.filled_quantity == 4
    store.record_accounting(order())
    store.record_accounting(fact("a", "4", "400"))
    result = store.record_accounting(fact("b", "6", "660"))["state"]
    assert result.filled_quantity == 10 and result.cost == 1060 and result.financially_complete
    assert result.fees[0].amount == D("0.4")
    for _ in range(3):
        assert store.record_accounting(fact("b", "6", "660"))["disposition"] == "duplicate"
        assert store.financial_state("order") == result
    legacy = store.records()
    assert legacy[0][1]["filled_quantity"] == 0
    store.close()
    reopened = ExecutionJournal(path, "fixture")
    try:
        assert reopened.financial_state("order") == result
        assert reopened.records() == legacy
    finally:
        reopened.close()


def test_conflicting_duplicate_is_durable_and_invalidates_completeness(store):
    store.record_accounting(order())
    store.record_accounting(fact())
    assert store.financial_state("order").financially_complete
    result = store.record_accounting(fact(cost="1100"))
    assert result["disposition"] == "conflict"
    assert not result["state"].financially_complete and result["state"].filled_quantity == 10
    assert result["state"].cost is None


@pytest.mark.parametrize("evidence", [order(client_order_id="foreign", exchange_order_id="foreign"),
    fact(eid=None), order(context=context(binding="foreign")), order(side="SELL")])
def test_quarantine_is_retained_without_mutating_original_projection(store, evidence):
    before = store.financial_state("order")
    result = store.record_accounting(evidence)
    assert result["disposition"] == "quarantined"
    assert store.financial_state("order") == before
    event = json.loads(store._connection.execute("SELECT payload FROM events ORDER BY sequence DESC LIMIT 1").fetchone()[0])
    assert event["disposition"] == "quarantined" and event["reasons"]


def test_unowned_fact_can_be_linked_later_once(store):
    loose = fact(client_order_id=None, exchange_order_id=None)
    result = store.record_accounting(loose)
    assert result["disposition"] == "quarantined" and result["state"] is None
    result = store.record_accounting(fact())["state"]
    assert result.filled_quantity == 10 and result.cost == 1060
    assert store._connection.execute("SELECT COUNT(*) FROM execution_facts").fetchone()[0] == 1


class FaultConnection:
    def __init__(self, connection, trigger):
        self.connection, self.trigger = connection, trigger
    def __getattr__(self, name):
        return getattr(self.connection, name)
    def execute(self, sql, *args):
        if self.trigger != "commit" and self.trigger in sql:
            raise sqlite3.OperationalError("fixture write failure: " + self.trigger)
        return self.connection.execute(sql, *args)
    def commit(self):
        if self.trigger == "commit":
            raise sqlite3.OperationalError("fixture commit failure")
        self.connection.commit()


@pytest.mark.parametrize("trigger", ["INSERT INTO events", "INSERT INTO financial_orders", "INSERT INTO execution_facts", "commit"])
def test_financial_transaction_failure_preserves_previous_state_and_latches(store, trigger):
    state = store.financial_state("order")
    events = store._connection.execute("SELECT * FROM events").fetchall()
    original = store._connection
    store._connection = FaultConnection(original, trigger)
    with pytest.raises(JournalError, match="fixture"):
        store.record_accounting(fact())
    assert store.financial_state("order") == state and store.failed
    assert store._connection.execute("SELECT * FROM events").fetchall() == events
    assert store._connection.execute("SELECT COUNT(*) FROM execution_facts").fetchone()[0] == 0
    with pytest.raises(JournalError):
        store.record_accounting(order())


@pytest.mark.parametrize("trigger", ["CREATE TABLE execution_facts", "INSERT INTO events", "INSERT INTO financial_orders", "UPDATE metadata SET version", "commit"])
def test_failed_migration_rolls_back_schema_and_rows(tmp_path, trigger):
    path = tmp_path / "execution.sqlite3"
    seed(path)
    old = {t: rows(path, t) for t in ("metadata", "requests", "events")}
    connect = sqlite3.connect
    def faulty(*args, **kwargs):
        connection = connect(*args, **kwargs)
        return FaultConnection(connection, trigger) if "mode=rw" in str(args[0]) else connection
    with patch("backend.bot.executor.execution_journal.sqlite3.connect", side_effect=faulty):
        with pytest.raises(JournalError, match="fixture"):
            upgrade_accounting_schema(path, "fixture", environment="testnet")
    assert {t: rows(path, t) for t in old} == old
    with sqlite3.connect(path) as con:
        assert {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")} == set(old)


def test_backup_failure_does_not_change_original_store(tmp_path):
    path = tmp_path / "execution.sqlite3"
    seed(path)
    original = path.read_bytes()
    with patch("backend.bot.executor.execution_journal.os.fsync", side_effect=OSError("backup flush failure")):
        with pytest.raises(JournalError, match="backup flush"):
            upgrade_accounting_schema(path, "fixture", environment="testnet")
    assert path.read_bytes() == original


def test_corrupt_financial_payload_is_rejected_by_readonly_inspection_and_open(store):
    path = store.path
    store.close()
    with sqlite3.connect(path) as con:
        con.execute("UPDATE financial_orders SET payload='{}'")
    assert ExecutionJournal.inspect(path)["error"]
    with pytest.raises(JournalError):
        ExecutionJournal(path, "fixture")


def test_unowned_conflicting_fact_stays_unowned_without_breaking_store(store):
    store.record_accounting(fact(side="SELL", client_order_id=None, exchange_order_id=None))
    result = store.record_accounting(fact())
    assert result["disposition"] == "conflict" and result["state"] is None
    assert store.financial_state("order").filled_quantity == 0 and not store.failed
    assert store._connection.execute("SELECT order_id FROM execution_facts").fetchone()[0] is None


def test_unknown_fields_are_enriched_without_replaying_terminal_quantity(store):
    store.record_accounting(order(cost=None))
    store.record_accounting(fact(cost=None, fees=None))
    assert store.financial_state("order").filled_quantity == 10
    assert store.financial_state("order").cost is None
    store.record_accounting(fact())
    state = store.record_accounting(order())["state"]
    assert state.financially_complete and state.filled_quantity == 10 and state.fees[0].amount == D("0.2")


def test_funding_does_not_fill_a_strategy_order(store):
    result = store.record_accounting(fact(kind="FUNDING"))
    assert result["disposition"] == "quarantined"
    assert store.financial_state("order").filled_quantity == 0


def test_store_binding_and_environment_cannot_be_changed_by_migration(store):
    path = store.path
    store.close()
    with pytest.raises(JournalError, match="binding"):
        upgrade_accounting_schema(path, "other", environment="testnet")
    with pytest.raises(JournalError, match="environment"):
        upgrade_accounting_schema(path, "fixture", environment="production")


def test_later_legacy_exchange_identity_can_link_financial_evidence(tmp_path):
    path = tmp_path / "execution.sqlite3"
    seed(path)
    with sqlite3.connect(path) as conn:
        old = json.loads(conn.execute("SELECT state FROM requests").fetchone()[0])
        old["exchange_id"] = None
        conn.execute("UPDATE requests SET state=?", (json.dumps(old),))
    upgrade_accounting_schema(path, "fixture", environment="testnet")
    journal = ExecutionJournal(path, "fixture")
    try:
        legacy = journal.records()[0][1]
        legacy["exchange_id"] = "remote"
        journal.observe("order", legacy)
        result = journal.record_accounting(order(client_order_id=None))
        assert result["state"].filled_quantity == 10 and result["state"].exchange_order_id == "remote"
    finally:
        journal.close()


def test_foreign_key_failure_and_event_mismatch_cannot_authorize_projection(store):
    with pytest.raises(sqlite3.IntegrityError):
        store._connection.execute("UPDATE financial_orders SET event_sequence=999999")
    store._connection.rollback()
    path = store.path
    store.close()
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE financial_orders SET event_sequence=1")
    assert "event mismatch" in ExecutionJournal.inspect(path)["error"]


def test_commit_succeeds_but_return_is_lost_requires_reopen_not_resubmission(store):
    class LostReturn(FaultConnection):
        def commit(self):
            self.connection.commit()
            raise sqlite3.OperationalError("fixture lost commit acknowledgment")
    path = store.path
    store._connection = LostReturn(store._connection, "after_commit")
    with pytest.raises(JournalError, match="lost commit"):
        store.record_accounting(fact())
    assert store.failed
    assert store.financial_state("order").filled_quantity == 10
    with pytest.raises(JournalError):
        store.record_accounting(fact())
    store.close()
    reopened = ExecutionJournal(path, "fixture")
    try:
        assert reopened.record_accounting(fact())["disposition"] == "duplicate"
        assert reopened.financial_state("order").fees[0].amount == D("0.2")
    finally:
        reopened.close()


def test_actual_zero_rebate_and_separate_currencies_are_not_modeled_fees(store):
    from backend.bot.executor.accounting_models import Fee
    store.record_accounting(order())
    fees = (Fee("USDT", D("-0.02"), "raw"), Fee("PT", D(0), "raw"))
    state = store.record_accounting(fact(fees=fees))["state"]
    assert state.financially_complete
    assert {fee.currency: fee.amount for fee in state.fees} == {"USDT": D("-0.02"), "PT": D(0)}
