"""Offline constraints for the proposed FV1 accounting foundation.

Exit 0 means observations match the design evidence, not that accounting is safe.
Current journal/executor methods and disposable SQLite migration sketches only;
no production migration, credentials, exchange calls or historical writes.
"""
import hashlib
import json
import logging
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.diagnostics.live_accounting_diagnostic import guard_offline, source_hashes


def exercise(directory):
    from datetime import datetime, timezone
    import sqlite3
    from types import SimpleNamespace as S
    from unittest.mock import Mock, patch
    import ccxt
    import backend.bot.executor.execution_journal as journal_module
    from backend.bot.executor.execution_journal import ExecutionJournal, JournalError, validate_record
    from backend.bot.executor.live_executor import LiveExecutor

    results = []
    def record(case, expected, observed, implication):
        results.append(dict(case=case, expected=expected, observed=observed,
                            probe_matches_expected=expected == observed, implication=implication))

    now = datetime.now(timezone.utc).isoformat()
    intent = dict(order_id="fixture", symbol="BTC/USDT:USDT", owner="offline", generation="fixture",
                  side="BUY", order_type="LIMIT", purpose="entry", reduce_only=False,
                  quantity=10, price=100, stop_price=None,
                  wire={"symbol": "BTC/USDT:USDT", "side": "buy", "amount": 10,
                        "params": {"clientOrderId": "fixture"}})
    state = dict(status="FILLED", filled_quantity=10, average_fill_price=100,
                 cancel_requested=False, exchange_id="remote", unknown_reason=None,
                 rejection_reason=None, created_at=now, updated_at=now)
    validate_record(intent, state)
    for price in (None, 0):
        missing = dict(state, average_fill_price=price)
        try:
            validate_record(intent, missing)
            rejected = False
        except JournalError:
            rejected = True
        record(f"legacy_record_requires_price_{price}", True, rejected,
               "New financial evidence must represent confirmed quantity with unknown cost without weakening legacy recovery validation.")

    for side in ("BUY", "SELL"):
        adapter = S(supports_trading=lambda: True,
                    fetch_balance=lambda: {"free": {"USDT": 1000}},
                    set_margin_mode=Mock(), set_leverage=Mock(),
                    create_order=Mock(return_value={"id": "remote", "status": "open", "filled": 0}),
                    fetch_order=Mock(return_value={"id": "remote", "status": "closed", "filled": 10, "average": 100}))
        ex = LiveExecutor(adapter, journal=ExecutionJournal(directory / f"{side}.sqlite3", "offline-fv1"),
                          max_position_size_usd=2000, max_total_exposure_usd=2000)
        try:
            ex.set_entry_admission(True)
            order = ex.place_order("BTC/USDT:USDT", side, "LIMIT", 10, price=100)
            with patch.object(ex._journal, "observe", side_effect=OSError("fixture disk failure after fill")):
                ex.refresh_order(order.order_id)
            durable = ex._journal.records()[0][1]
            record(f"{side}_financial_publication_precedes_persistence",
                   {"memory_filled": 10, "durable_filled": 0, "local_fills": 1,
                    "balance": 999, "risk_blocked": True, "submissions": 1},
                   {"memory_filled": order.filled_quantity, "durable_filled": durable["filled_quantity"],
                    "local_fills": len(ex.get_trade_history()), "balance": ex.get_balance(),
                    "risk_blocked": bool(ex._journal_error) and not ex._entry_admission_enabled,
                    "submissions": adapter.create_order.call_count},
                   "Existing storage-failure containment freezes new risk; future financial state must commit before in-memory publication.")
        finally:
            ex.close()

    path = directory / "version-probe.sqlite3"
    store = ExecutionJournal(path, "offline-version")
    store.close()
    marker = path.with_suffix(".initialized")
    before_marker = marker.read_bytes()
    inspection = ExecutionJournal.inspect(path)
    record("valid_v1_readonly_inspection_reaches_database", None, inspection.get("error"),
           "Control: the fixture URI must pass the file guard before schema rejection probes are meaningful.")
    with patch.object(journal_module, "SCHEMA_VERSION", 2):
        inspection = ExecutionJournal.inspect(path)
        try:
            changed = ExecutionJournal(path, "offline-version")
        except JournalError:
            open_rejected = True
        else:
            changed.close()
            open_rejected = False
    record("removing_v1_schema_support_blocks_existing_store", {"inspect_blocked": True, "open_blocked": True},
           {"inspect_blocked": inspection["recovery_required"] and bool(inspection.get("error")),
            "open_blocked": open_rejected},
           "Default v1 support must remain while marker format and accounting capability evolve separately.")
    assert marker.read_bytes() == before_marker

    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE metadata SET version=2 WHERE singleton=1")
    inspection = ExecutionJournal.inspect(path)
    record("incomplete_v2_without_migration_evidence_is_rejected", True, bool(inspection.get("error")),
           "A version-only change must not pass current validation; actual old-reader compatibility is tested by accounting_storage_diagnostic.")

    # These are migration sketches, not a production migration implementation.
    # Python's context manager alone does not BEGIN before SQLite DDL.
    for explicit_begin in (False, True):
        candidate = directory / f"migration-sketch-{explicit_begin}.sqlite3"
        with sqlite3.connect(candidate) as connection:
            connection.execute("CREATE TABLE metadata(version INTEGER)")
            connection.execute("INSERT INTO metadata VALUES(1)")
        with sqlite3.connect(candidate) as connection:
            try:
                with connection:
                    if explicit_begin:
                        connection.execute("BEGIN IMMEDIATE")
                    connection.execute("CREATE TABLE financial_observations(id TEXT PRIMARY KEY)")
                    connection.execute("UPDATE metadata SET version=2")
                    raise RuntimeError("fixture interruption before commit")
            except RuntimeError:
                pass
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            observed = {"version": connection.execute("SELECT version FROM metadata").fetchone()[0],
                        "new_table_remains": "financial_observations" in tables}
        record(f"migration_ddl_rollback_explicit_begin_{explicit_begin}",
               {"version": 1, "new_table_remains": not explicit_begin}, observed,
               "Migration DDL and version publication need one explicit transaction, with verified backup before BEGIN.")

    market = {"id": "BTCUSDT", "symbol": "BTC/USDT:USDT", "type": "swap", "swap": True,
              "spot": False, "linear": True, "inverse": False, "contract": True,
              "settle": "USDT", "settleId": "USDT", "base": "BTC", "quote": "USDT",
              "baseId": "BTC", "quoteId": "USDT", "contractSize": 1,
              "precision": {"price": 0.1, "amount": 0.001}, "info": {}}
    client = ccxt.phemex()
    client.set_markets([market])
    position = {"symbol": "BTCUSDT", "side": "Buy", "sizeRq": "10", "valueRv": "1000",
                "avgEntryPriceRp": "100", "markPriceRp": "106", "positionMarginRv": "250",
                "assignedPosBalanceRv": "250", "leverageRr": "4", "maintMarginReqRr": "0.01"}
    parsed = client.parse_position(position, market)
    record("unified_upnl_can_be_calculated_without_raw_evidence", 60, parsed["unrealizedPnl"],
           "Account observation parser must require raw mark-PnL provenance instead of mistaking parser arithmetic for exchange evidence.")
    body = {"code": 0, "data": {"account": {"currency": "USDT", "accountBalanceRv": "1000",
                                               "totalUsedBalanceRv": "250", "bonusBalanceRv": "50"}}}
    balance = client.parse_swap_balance(body)
    record("unified_balance_does_not_resolve_bonus_policy", {"total": 1000, "free": 750},
           {"total": balance["total"]["USDT"], "free": balance["free"]["USDT"]},
           "Nonzero bonus requires an unsupported/incomplete account observation until its economic treatment is established.")
    return results


def main():
    directory = Path(tempfile.mkdtemp(prefix="snipersight-fv1-readiness-")).resolve()
    before = source_hashes()
    guard_offline(directory)
    try:
        results = exercise(directory)
        after = source_hashes()
        assert before == after
        mismatches = sum(not row["probe_matches_expected"] for row in results)
        report = {"scope": "FV1 design constraints; matching probes do not mean financial correctness",
                  "cases": len(results), "unexpected_results": mismatches,
                  "source_hashes": after, "sources_unchanged": True,
                  "diagnostic_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  "artifact_directory": str(directory), "results": results}
        status = int(mismatches > 0)
    except Exception:
        import traceback
        report = {"harness_error": traceback.format_exc(), "artifact_directory": str(directory)}
        status = 2
    finally:
        logging.shutdown()
    report["exit_code"] = status
    (directory / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
