"""Price-feed loss must not manufacture a close or cancel native protection.

Run through the guarded audit runner: real manager/service methods, scripted
transports, temporary execution journals, no startup or exchange connection.
"""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as S
from unittest.mock import AsyncMock, Mock

import pytest

import backend.bot.executor.position_manager as manager_module
from backend.bot.executor.position_manager import PositionManager, PositionState, PositionStatus
from backend.bot.executor.execution_journal import ExecutionJournal
from backend.bot.executor.live_executor import LiveExecutor
from backend.tests.unit.runtime_fixtures import prepare_adapter, initialize_fixture
from backend.bot.executor.paper_executor import PaperExecutor, OrderStatus
from backend.bot.live_trading_service import LiveTradingService
from backend.bot.paper_trading_service import PaperTradingService

SYMBOL = "FIXTURE/USDT"
NOW = datetime(2026, 10, 7, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW if tz else NOW.replace(tzinfo=None)
    monkeypatch.setattr(manager_module, "datetime", FrozenDateTime)


@pytest.fixture(params=["LONG", "SHORT"])
def direction(request):
    return request.param


@pytest.fixture(params=[PositionStatus.OPEN, PositionStatus.PARTIAL])
def position(request, direction):
    partial = request.param == PositionStatus.PARTIAL
    return PositionState(
        "fixture-position", SYMBOL, direction, 100, 10, 4 if partial else 10,
        99 if direction == "LONG" else 101, [], status=request.param,
        realized_pnl=6 if partial else 0, unrealized_pnl=2,
        created_at=NOW - timedelta(days=100), updated_at=NOW - timedelta(hours=1),
    )


@pytest.mark.parametrize("bad", [0.0, -1.0, None, False, True, "100", float("nan"),
                                  float("inf"), -float("inf"), RuntimeError("offline feed")])
def test_repeated_feed_failure_preserves_entire_position(position, bad, caplog):
    fetcher = Mock(side_effect=bad) if isinstance(bad, Exception) else Mock(return_value=bad)
    execute = AsyncMock(return_value=True)
    pm = PositionManager(fetcher, execute)
    pm.positions[position.position_id] = position
    before = deepcopy(position.__dict__)

    async def run():
        for _ in range(2):
            await pm.monitor_all_positions()
            assert position.__dict__ == before
            assert pm.get_open_positions() == [position]
    asyncio.run(run())
    execute.assert_not_awaited()
    assert fetcher.call_count == 2  # No second blind fetch/settlement on timeout.
    errors = [r.message for r in caplog.records if "ORPHAN_PRICE_FEED_UNAVAILABLE" in r.message]
    assert len(errors) == 2
    assert all(position.position_id in msg and SYMBOL in msg for msg in errors)


@pytest.mark.parametrize("age_factor", [0.99, 1.0, 1.01])
@pytest.mark.parametrize("has_last_observation", [False, True])
def test_timeout_boundary_only_changes_diagnostic(position, age_factor, has_last_observation, caplog):
    pm = PositionManager(lambda _: 0.0, AsyncMock())
    pm.positions[position.position_id] = position
    limit = pm._get_adaptive_stagnation_hours(position) * 2
    last_seen = NOW - timedelta(hours=limit * age_factor)
    position.created_at = NOW - timedelta(days=100) if has_last_observation else last_seen
    position._last_monitored_at = last_seen if has_last_observation else None
    before = deepcopy(position.__dict__)
    asyncio.run(pm.monitor_all_positions())
    assert position.__dict__ == before
    assert ("ORPHAN_PRICE_FEED_UNAVAILABLE" in caplog.text) == (age_factor > 1)


@pytest.mark.parametrize("confirmed", [False, True])
def test_feed_recovery_resumes_existing_confirmed_exit_rules(position, confirmed):
    fetcher = Mock(return_value=0.0)
    execute = AsyncMock(return_value=confirmed)
    pm = PositionManager(fetcher, execute)
    pm.positions[position.position_id] = position
    before = deepcopy(position.__dict__)

    async def run():
        await pm.monitor_all_positions()
        assert position.__dict__ == before
        execute.assert_not_awaited()
        fetcher.return_value = 98 if position.direction == "LONG" else 102
        await pm.monitor_all_positions()
    asyncio.run(run())
    execute.assert_awaited_once_with(symbol=SYMBOL,
                                    side="SELL" if position.direction == "LONG" else "BUY",
                                    quantity=before["remaining_quantity"], price=fetcher.return_value)
    assert position._last_monitored_at == NOW
    if confirmed:
        assert position.status == PositionStatus.STOPPED_OUT
        assert position.remaining_quantity == 0
        assert position.exit_reason == "stop_loss"
    else:
        assert position.status == before["status"]
        assert position.remaining_quantity == before["remaining_quantity"]
        assert position.realized_pnl == before["realized_pnl"]
        assert position.exit_price is None


@pytest.mark.parametrize("service_kind", ["live", "paper_testnet", "paper"])
def test_service_completion_cannot_archive_or_unprotect_feed_orphan(position, service_kind, tmp_path, monkeypatch):
    """Actual cache callbacks and synchronizers; no simulated terminal status."""
    svc = LiveTradingService() if service_kind == "live" else PaperTradingService()
    journal_sink = Mock()
    monkeypatch.setattr("backend.bot.live_trading_service.get_trade_journal", lambda: journal_sink)
    monkeypatch.setattr("backend.bot.paper_trading_service.get_trade_journal", lambda: journal_sink)
    svc.telemetry_storage = Mock()
    adapter = S(supports_trading=lambda: True,
                fetch_balance=lambda: {"free": {"USDT": 1000}},
                create_order=Mock(return_value={"id": "stop-remote", "status": "open", "filled": 0}),
                cancel_order=Mock(return_value={"id": "stop-remote", "status": "canceled", "filled": 0}))
    prepare_adapter(adapter, SYMBOL, "offline-orphan")
    ex = (PaperExecutor(initial_balance=1000) if service_kind == "paper" else
          LiveExecutor(adapter, journal=ExecutionJournal(tmp_path / "execution.sqlite3", "offline-orphan", runtime=True, environment="testnet")))
    if service_kind != "paper":
        initialize_fixture(ex)
    svc.executor = ex
    svc.position_manager = PositionManager(svc._get_price, svc._execute_exit_order)
    svc.position_manager.positions[position.position_id] = position
    svc._price_cache.clear()
    before = deepcopy(position.__dict__)
    try:
        stop = None
        if service_kind != "paper":
            stop = ex.place_stop_order(SYMBOL, "SELL" if position.direction == "LONG" else "BUY",
                                       position.remaining_quantity, position.stop_loss)
            assert stop.status == OrderStatus.OPEN
            if service_kind == "live":
                svc._exchange_stop_orders[position.position_id] = stop.order_id
                svc._exchange_stop_levels[position.position_id] = position.stop_loss
        adapter.create_order.reset_mock()

        async def run():
            for _ in range(2):
                await svc.position_manager.monitor_all_positions()
                await svc._sync_closed_positions()
        asyncio.run(run())
        assert position.__dict__ == before
        assert svc.position_manager.get_open_positions() == [position]
        assert svc.completed_trades == []
        assert svc._completed_trade_ids == set()
        assert svc.stats.total_trades == 0
        svc.telemetry_storage.store_event.assert_not_called()
        journal_sink.upsert.assert_not_called()
        adapter.create_order.assert_not_called()
        adapter.cancel_order.assert_not_called()
        if stop:
            assert stop.status == OrderStatus.OPEN
        if service_kind == "live":
            assert svc._exchange_stop_orders[position.position_id] == stop.order_id
        if service_kind == "paper":
            assert ex.get_trade_history() == []
    finally:
        if service_kind != "paper":
            ex.close()
