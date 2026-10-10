"""Durable recovery under scripted transport, storage faults and duplicate owners."""
import asyncio
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace as S
from unittest.mock import Mock

import ccxt
import pytest

from backend.bot.executor.execution_journal import ExecutionJournal, JournalError, credential_binding
from backend.bot.executor.live_executor import LiveExecutor
from backend.tests.unit.runtime_fixtures import prepare_adapter, initialize_fixture, fixture_ws
from backend.bot.executor.live_preflight import read_only_preflight
from backend.bot.executor.paper_executor import OrderStatus
from backend.bot.live_trading_service import LiveTradingService
from backend.tests.unit.test_live_lifecycle import snapshot, service, cleanup


def adapter():
    return prepare_adapter(S(supports_trading=lambda: True, testnet=True, exchange=S(apiKey="fixture"),
             fetch_balance=Mock(return_value={"free": {"USDT": 1000}}),
             set_position_mode_one_way=Mock(return_value=True),
             set_margin_mode=Mock(), set_leverage=Mock(),
             create_order=Mock(side_effect=ccxt.RequestTimeout("lost acknowledgment")),
             fetch_order=Mock(), fetch_order_by_client_id=Mock(side_effect=ccxt.OrderNotFound("not yet visible")),
             fetch_positions=Mock(return_value=[]), fetch_account_snapshot=Mock(return_value=snapshot()),
             cancel_order=Mock(return_value={"id": "remote", "status": "canceled", "filled": 0})))


def create(path, ad=None):
    ex = LiveExecutor(ad or adapter(), journal=ExecutionJournal(path, "fixture", runtime=True, environment="testnet"),
                      max_position_size_usd=2000, max_total_exposure_usd=2000)
    return initialize_fixture(ex)


@pytest.fixture
def ex(tmp_path):
    obj = create(tmp_path / "execution.sqlite3")
    yield obj
    obj.close()


def place(ex, side="BUY"):
    return ex.place_order("A", side, "LIMIT", 10, price=100)


def test_owner_blocks_same_process_and_readonly_inspection_does_not_acquire(tmp_path):
    path = tmp_path / "execution.sqlite3"
    first = ExecutionJournal(path, "fixture")
    try:
        with pytest.raises(JournalError, match="owned"):
            ExecutionJournal(path, "fixture")
        before = path.read_bytes()
        assert ExecutionJournal.inspect(path)["recovery_required"]
        assert path.read_bytes() == before
    finally:
        first.close()
    second = ExecutionJournal(path, "fixture")
    assert not second.was_clean
    second.close()


@pytest.mark.parametrize("damage", ["database_missing", "marker_missing", "corrupt", "schema", "record", "marker_schema"])
def test_damaged_expected_storage_never_becomes_fresh(tmp_path, damage):
    path = tmp_path / "execution.sqlite3"
    ex = create(path)
    place(ex)
    ex.close()
    if damage == "database_missing":
        path.unlink()
    elif damage == "marker_missing":
        path.with_suffix(".initialized").unlink()
    elif damage == "corrupt":
        path.write_bytes(b"not sqlite")
    elif damage == "marker_schema":
        marker = path.with_suffix(".initialized")
        data = json.loads(marker.read_text())
        data["version"] = 999
        marker.write_text(json.dumps(data))
    else:
        with sqlite3.connect(path) as con:
            con.execute("UPDATE metadata SET version=999" if damage == "schema" else "UPDATE requests SET state='{}'")
    assert ExecutionJournal.inspect(path)["recovery_required"]
    with pytest.raises(JournalError):
        ExecutionJournal(path, "fixture")


def test_credential_rotation_and_environment_change_do_not_select_empty_store(tmp_path):
    path = tmp_path / "execution.sqlite3"
    binding = credential_binding(True, "first-key")
    ExecutionJournal(path, binding).close()
    for other in (credential_binding(False, "first-key"), credential_binding(True, "rotated-key")):
        with pytest.raises(JournalError, match="binding"):
            ExecutionJournal(path, other)
    assert b"first-key" not in path.read_bytes()
    assert "first-key" not in path.with_suffix(".initialized").read_text()


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_restore_preserves_original_identity_and_never_guesses_position_ownership(tmp_path, side):
    path = tmp_path / "execution.sqlite3"
    first = create(path)
    order = place(first, side)
    first.close()
    restored = create(path)
    try:
        assert restored.recovery_snapshot()["recovery_only"]
        restored.refresh_order(order.order_id)
        restored._adapter.fetch_order_by_client_id.assert_called_once_with(order.order_id, "A")
        assert not restored.recovery_snapshot()["entry_admission_enabled"]
        with pytest.raises(JournalError, match="Restart recovery"):
            place(restored, side)
        assert len(restored._orders) == 1
        restored._adapter.create_order.assert_not_called()
        restored._adapter.set_position_mode_one_way.assert_not_called()
    finally:
        restored.close()


@pytest.mark.parametrize("side,qty", [("BUY", 10), ("SELL", -10)])
@pytest.mark.parametrize("terminal", [True, False])
def test_restored_fills_do_not_double_account_snapshot_or_cash(tmp_path, side, qty, terminal):
    path = tmp_path / "execution.sqlite3"
    first = create(path)
    order = place(first, side)
    fixture_ws(first, "remote", order.order_id, "filled" if terminal else "partiallyfilled", 10 if terminal else 4, 100)
    first.close()
    restored = create(path)
    try:
        restored._adapter.fetch_positions.return_value = [{"symbol": "A", "contracts": 10,
                                                          "side": "long" if qty > 0 else "short", "entryPrice": 100}]
        restored.reconcile_account(force=True)
        before = restored.get_balance()
        for status, fill in (("filled", 10), ("partiallyfilled", 4), ("filled", 10)):
            fixture_ws(restored, "remote", order.order_id, status, fill, 100)
        assert restored.get_position("A") == qty
        assert restored._cached_balance == before and restored.get_trade_history() == []
        assert not restored.accounting_status()['entry_eligible']
        assert restored.get_order(order.order_id).filled_quantity == 10
        assert restored._journal.records()[0][1]["filled_quantity"] == 10
    finally:
        restored.close()


@pytest.mark.parametrize("error", [sqlite3.OperationalError("database or disk is full"), PermissionError("read-only disk")])
def test_pre_submit_storage_failure_makes_zero_exchange_calls(ex, error):
    ex._journal.submit_intent = Mock(side_effect=error)
    place(ex)
    ex._adapter.create_order.assert_not_called()
    assert ex.recovery_snapshot()["storage_error"]
    assert not ex.recovery_snapshot()["entry_admission_enabled"]


def test_post_submit_save_failure_keeps_original_durable_unknown_intent(ex):
    ex._adapter.create_order.side_effect = None
    ex._adapter.create_order.return_value = {"id": "remote", "status": "filled", "filled": 10, "average": 100}
    ex._journal.record_execution = Mock(side_effect=OSError("disk full after send"))
    with pytest.raises(JournalError, match='disk full after send'):
        place(ex)
    rows = ex._journal.records()
    assert rows[0][1]["status"] == "PENDING" and rows[0][1]["filled_quantity"] == 0
    assert ex.recovery_snapshot()["storage_error"]
    with pytest.raises(JournalError):
        place(ex)
    ex._adapter.create_order.assert_called_once()


def test_cancel_intent_is_committed_before_transport_and_failure_blocks_send(ex):
    order = place(ex)
    fixture_ws(ex, "remote", order.order_id, "open", 0, 0)
    def cancel(*args):
        assert ex._journal.records()[0][1]["cancel_requested"]
        raise ccxt.RequestTimeout("lost cancel")
    ex._adapter.cancel_order.side_effect = cancel
    assert not ex.cancel_order(order.order_id)
    ex._journal.observe = Mock(side_effect=PermissionError("storage unavailable"))
    with pytest.raises(JournalError):
        ex.cancel_order(order.order_id)
    assert ex._adapter.cancel_order.call_count == 1


def test_submission_intent_captures_complete_wire_and_owner_before_send(ex):
    def send(**wire):
        intent, state = ex._journal.records()[0]
        assert intent["wire"] == wire and intent["owner"] == "live"
        assert intent["generation"] and state["status"] == "PENDING"
        raise ccxt.RequestTimeout("lost")
    ex._adapter.create_order.side_effect = send
    ex.place_order("A", "SELL", "LIMIT", 10, price=100, reduce_only=True, sl_price=101, tp_price=95)
    intent = ex._journal.records()[0][0]
    assert intent["purpose"] == "exit" and intent["reduce_only"]


@pytest.mark.parametrize("kind", ["stop", "tp", "trail"])
def test_protection_has_durable_reduce_only_intent(ex, kind):
    if kind == "stop":
        order = ex.place_stop_order("A", "SELL", 10, 99)
    elif kind == "tp":
        order = ex.place_take_profit_order("A", "SELL", 10, 105)
    else:
        order = ex.place_trailing_stop_order("A", "SELL", 10, 105, 1.5)
    intent, _ = ex._journal.records()[0]
    assert intent["purpose"] == "protection" and intent["reduce_only"]
    assert intent["wire"]["params"]["reduceOnly"] is True
    assert intent["order_id"] == order.order_id


def test_terminal_recovery_requires_flat_checkpoint_before_clean_restart(tmp_path):
    path = tmp_path / "execution.sqlite3"
    first = create(path)
    order = place(first)
    fixture_ws(first, "remote", order.order_id, "canceled", 0, 0)
    first.checkpoint_flat(first.verify_flat_account())
    first.close()
    second = create(path)
    assert not second.recovery_snapshot()["recovery_only"]
    second.close()


def test_restart_recovery_preserves_protection_and_observes_foreign_exposure(tmp_path, monkeypatch):
    from backend.bot import live_trading_service
    from backend.bot.trade_journal import TradeJournalService
    # Shutdown report recovery opens the trade journal; keep it in the fixture store.
    journal = TradeJournalService(tmp_path / "trades.jsonl")
    monkeypatch.setattr(live_trading_service, "get_trade_journal", lambda: journal)
    path = tmp_path / "execution.sqlite3"
    first = create(path)
    order = first.place_stop_order("A", "SELL", 10, 99)
    first.close()
    restored = create(path)
    svc = service(restored)
    restored._adapter.fetch_order_by_client_id.side_effect = None
    restored._adapter.fetch_order_by_client_id.return_value = {
        "id": "remote", "clientOrderId": order.order_id, "status": "open", "filled": 0}
    restored._adapter.fetch_order.return_value = {"id": "remote", "status": "open", "filled": 0}
    restored._adapter.fetch_positions.return_value = [{"symbol": "A", "contracts": 10, "side": "long", "entryPrice": 100}]
    svc.adapter.fetch_account_snapshot.return_value = snapshot(positions=[{"symbol": "A", "contracts": 10}], orders=[{"id": "remote", "symbol": "A"}])
    async def run():
        try:
            status = await svc.stop()
            assert status["lifecycle"]["phase"] == "recovering"
            assert status["lifecycle"]["unmanaged_symbols"] == ["A"]
            assert restored.get_order(order.order_id).status == OrderStatus.OPEN
            restored._adapter.cancel_order.assert_not_called()
            restored._adapter.create_order.assert_not_called()
        finally:
            await cleanup(svc)
    try:
        asyncio.run(run())
    finally:
        restored.close()


def test_readonly_preflight_never_initializes_mutation_owner_or_position_mode(tmp_path, monkeypatch):
    import time
    ad = adapter()
    ad.exchange.fetch_time = lambda: time.time() * 1000
    result = read_only_preflight(ad)
    assert result["ok"]
    ad.set_position_mode_one_way.assert_not_called()
    ad.create_order.assert_not_called()
    assert not list(tmp_path.iterdir())


def test_closed_executor_cannot_mutate_through_a_stale_reference(ex):
    ex.close()
    with pytest.raises(JournalError):
        ex.place_stop_order("A", "SELL", 10, 99)
    ex._adapter.create_order.assert_not_called()


def test_paper_testnet_cannot_drop_unresolved_executor_on_reset(ex):
    from backend.bot.paper_trading_service import PaperTradingService, PaperBotStatus
    svc = object.__new__(PaperTradingService)
    svc.status = PaperBotStatus.STOPPED
    svc.executor = ex
    svc.position_manager = None
    place(ex)
    with pytest.raises(ValueError, match="recovery"):
        svc.reset()
    assert svc.executor is ex


def test_paper_status_and_repeated_stop_keep_recovery_visible(ex):
    from backend.bot.paper_trading_service import PaperTradingService, PaperBotStatus
    svc = PaperTradingService()
    svc.status = PaperBotStatus.STOPPED
    svc.executor = ex
    order = place(ex)
    result = asyncio.run(svc.stop())
    assert result["recovery_required"]
    assert result["execution_recovery"]["requests"][0]["order_id"] == order.order_id


def test_actual_live_start_restores_before_strategy_or_mode_initialization(tmp_path, monkeypatch):
    import backend.bot.live_trading_service as module
    from backend.shared.config.live_trading_config import LiveTradingConfig
    path = tmp_path / "execution.sqlite3"
    first = create(path)
    order = place(first)
    first.close()
    ad = adapter()
    monkeypatch.setattr(module, "load_phemex_credentials", lambda: ("fixture-key", "fixture-secret"))
    monkeypatch.setattr(module, "PhemexAdapter", lambda **kwargs: ad)
    monkeypatch.setattr(module, "LiveExecutor", lambda **kwargs: LiveExecutor(
        **kwargs, journal=ExecutionJournal(path, "fixture", runtime=True, environment="testnet")))
    orchestrator = Mock(side_effect=AssertionError("Strategy must not start during recovery"))
    monkeypatch.setattr(module, "Orchestrator", orchestrator)
    svc = LiveTradingService()
    async def run():
        try:
            result = await svc.start(LiveTradingConfig())
            assert result["lifecycle"]["phase"] == "recovering"
            assert svc.executor.get_order(order.order_id)
            assert svc.position_manager is None and svc._scan_task is None
            assert not svc._running
            ad.set_position_mode_one_way.assert_not_called()
            ad.create_order.assert_not_called()
            orchestrator.assert_not_called()
        finally:
            await cleanup(svc)
    try:
        asyncio.run(run())
    finally:
        svc.executor.close()


def test_paper_start_stop_reset_are_excluded_during_async_transition():
    from backend.bot.paper_trading_service import PaperTradingService, PaperBotStatus
    svc = object.__new__(PaperTradingService)
    svc.status = PaperBotStatus.IDLE
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        async def starting(config):
            entered.set()
            await release.wait()
        svc._start_session = starting
        from backend.bot.paper_trading_service import PaperTradingConfig
        task = asyncio.create_task(svc.start(PaperTradingConfig(use_testnet=True)))
        await entered.wait()
        try:
            for command in (svc.start(S()), svc.stop()):
                with pytest.raises(ValueError, match="transition"):
                    await command
            with pytest.raises(ValueError, match="transition"):
                svc.reset()
        finally:
            release.set()
            await task
    asyncio.run(run())


def test_cancelled_protection_intent_is_observed_but_not_retried_after_restart(tmp_path):
    path = tmp_path / "execution.sqlite3"
    first = create(path)
    order = first.place_stop_order("A", "SELL", 10, 99)
    fixture_ws(first, "remote", order.order_id, "open", 0, 0)
    first._adapter.cancel_order.side_effect = ccxt.RequestTimeout("unknown cancellation")
    first.cancel_order(order.order_id)
    first.close()
    restored = create(path)
    try:
        restored._adapter.fetch_order.return_value = {"id": "remote", "status": "open", "filled": 0}
        restored.recover_uncertain_orders()
        restored._adapter.fetch_order.assert_called_once()
        restored._adapter.cancel_order.assert_not_called()
        assert order.order_id in restored._cancel_requested_orders
    finally:
        restored.close()


def test_sqlite_transaction_failure_latches_and_rolls_back_request(ex):
    original_event = ex._journal._event
    ex._journal._event = Mock(side_effect=sqlite3.OperationalError("database or disk is full"))
    place(ex)
    assert ex._journal.failed and ex._journal.records() == []
    ex._adapter.create_order.assert_not_called()
    ex._journal._event = original_event
    with pytest.raises(JournalError):
        ex._journal.mark_flat("fixture")


def test_uninitialized_inspection_does_not_create_marker_database_or_directory(tmp_path):
    target = tmp_path / "absent" / "execution.sqlite3"
    assert ExecutionJournal.inspect(target) == {"exists": False, "recovery_required": False, "requests": []}
    assert not target.parent.exists()


def test_late_execution_revision_prevents_stale_flat_checkpoint(ex):
    observed_at = ex.verify_flat_account()
    ex.reconcile_account(force=True)
    order = place(ex)
    fixture_ws(ex, "remote", order.order_id, "canceled", 0, 0)
    with pytest.raises(JournalError, match="Execution changed"):
        ex.checkpoint_flat(observed_at)
    assert not ex._journal._connection.execute("SELECT clean FROM metadata").fetchone()[0]


def test_api_preflight_uses_only_readonly_check():
    import ast
    tree = ast.parse((Path(__file__).resolve().parents[2] / "api_server.py").read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "live_trading_preflight")
    calls = [n.func.id for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    assert "LiveExecutor" not in calls
    assert any(isinstance(n, ast.Name) and n.id == "read_only_preflight" for n in ast.walk(node))


def test_journal_schema_is_exact_and_separate_from_trade_history(ex):
    tables = {row[0] for row in ex._journal._connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == {"metadata", "requests", "events", "financial_orders", "execution_facts"}
    assert ex._journal._connection.execute("PRAGMA synchronous").fetchone() == (2,)
    assert ex._journal._connection.execute("PRAGMA journal_mode").fetchone() == ("delete",)
