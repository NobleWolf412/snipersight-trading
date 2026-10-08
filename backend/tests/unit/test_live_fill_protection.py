"""Offline lifecycle regressions using real service/executor/position methods.

No adapter or exchange client is constructed. Run with the guarded audit runner
to block credentials, external networking, child processes and production writes.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from threading import RLock
from types import SimpleNamespace as S
from unittest.mock import AsyncMock, Mock

import pytest

import backend.bot.live_trading_service as service_module
from backend.tests.unit.execution_fixtures import attach_journal, seed_order
from backend.bot.live_trading_service import LiveTradingService
from backend.bot.executor.live_executor import LiveExecutor
from backend.bot.executor.paper_executor import Order, OrderSide, OrderStatus, OrderType
from backend.bot.executor.position_manager import PositionManager, PositionStatus


SYMBOL = "FIXTURE/USDT"


@pytest.fixture(params=["LONG", "SHORT"])
def state(request, monkeypatch, tmp_path):
    direction = request.param
    clock = S(now=100.0)
    monkeypatch.setattr(service_module, "time", S(monotonic=lambda: clock.now))
    svc = LiveTradingService()
    svc.config = S(max_positions=3, balance_reconcile_interval=60, kill_switch_enabled=False)
    svc.stats.signals_taken = 0
    svc._last_reconcile_at = clock.now
    svc._startup_reconciled = svc._exchange_state_known = True
    svc.activities = []
    svc._log_activity = lambda event, data: svc.activities.append((event, data))
    svc.position_manager = PositionManager(price_fetcher=lambda symbol: 100.0)
    svc.position_manager.monitor_all_positions = AsyncMock()
    svc._refresh_price_cache = AsyncMock()
    svc._sync_closed_positions = AsyncMock()
    svc._price_cache = {SYMBOL: 100.0}
    svc.adapter = None

    # Bypass LiveExecutor's constructor (which changes exchange account mode).
    ex = object.__new__(LiveExecutor)
    ex.dry_run = False
    ex._state_lock = RLock()
    ex._reduce_only_order_ids = set()
    ex._unacknowledged_orders = {}
    ex._cancel_requested_orders = set()
    ex._last_order_recovery_at = 0.0
    ex._order_id_prefix = "fixture"
    ex.balance_known = True
    ex.last_balance_observed_at = clock.now
    ex._orders = {}
    ex._exchange_order_map = {"entry": "exchange-entry"}
    ex._reverse_order_map = {"exchange-entry": "entry"}
    ex._fills = []
    ex._positions = {}
    ex._position_avg_price = {}
    ex._cached_balance = 1000.0
    ex.fee_rate = 0.001
    ex.metrics = {"fills_recorded_via_ws": 0, "fills_recorded_via_rest": 0}
    ex._adapter = S(
        fetch_order=Mock(return_value={"status": "open", "filled": 0, "remaining": 10, "amount": 10}),
        cancel_order=Mock(return_value={"status": "canceled", "filled": 0}),
    )
    ex.check_fill_via_positions = Mock(return_value=None)
    svc.executor = ex
    plan = S(symbol=SYMBOL, direction=direction, trade_type="intraday", targets=[],
             stop_loss=S(level=99.0 if direction == "LONG" else 101.0))
    order = Order("entry", SYMBOL, OrderSide.BUY if direction == "LONG" else OrderSide.SELL,
                  OrderType.LIMIT, 10.0, price=100.0, status=OrderStatus.OPEN)
    ex._orders[order.order_id] = order
    attach_journal(ex, tmp_path / "execution.sqlite3")
    seed_order(ex, order)
    request.addfinalizer(ex._journal.close)
    svc._pending_plans[order.order_id] = plan
    svc._pending_placed_at[order.order_id] = datetime.now(timezone.utc)
    svc._pending_placed_price[order.order_id] = 100.0
    calls = []
    responses = []

    def place_stop(**kwargs):
        calls.append(kwargs)
        response = responses.pop(0) if responses else OrderStatus.OPEN
        if isinstance(response, Exception):
            raise response
        stop = Order(f"stop-{len(calls)}", kwargs["symbol"], OrderSide(kwargs["side"]),
                     OrderType.STOP_LOSS, kwargs["quantity"], status=response,
                     price=kwargs["stop_price"], stop_price=kwargs["stop_price"])
        ex._orders[stop.order_id] = stop
        if response == OrderStatus.OPEN:
            ex._exchange_order_map[stop.order_id] = "remote-" + stop.order_id
        seed_order(ex, stop)
        return stop

    ex.place_stop_order = Mock(side_effect=place_stop)
    ex.place_take_profit_order = Mock(return_value=S(status=OrderStatus.OPEN, order_id="tp"))
    ex.place_trailing_stop_order = Mock(return_value=S(status=OrderStatus.OPEN, order_id="trail"))
    return S(svc=svc, ex=ex, plan=plan, order=order, clock=clock,
             calls=calls, responses=responses, direction=direction)


def ws(state, status="filled", quantity=10.0):
    state.ex.apply_ws_fill("exchange-entry", "entry", status, quantity, 100.0)


def monitor_tick(state, monkeypatch):
    async def stop(seconds):
        state.svc._running = False
    monkeypatch.setattr(service_module, "asyncio", S(sleep=stop, to_thread=asyncio.to_thread))
    state.svc._running = True
    asyncio.run(state.svc._monitor_loop())


def assert_adopted(state, quantity=10.0):
    positions = state.svc.position_manager.get_open_positions()
    assert len(positions) == 1
    pos = positions[0]
    assert pos.entry_order_id == "entry" and pos.direction == state.direction
    assert pos.quantity == quantity and pos.remaining_quantity == quantity
    assert state.ex.get_position(SYMBOL) == (quantity if state.direction == "LONG" else -quantity)
    assert not state.svc._pending_plans
    assert not state.svc._pending_placed_at and not state.svc._pending_placed_price
    assert state.svc.stats.signals_taken == 1
    return pos


def test_ws_full_fill_is_adopted_next_tick_without_rest_or_price(state, monkeypatch):
    ws(state)
    state.svc._price_cache = {}
    assert state.order not in state.ex.get_open_orders()
    monitor_tick(state, monkeypatch)
    pos = assert_adopted(state)
    state.ex._adapter.fetch_order.assert_not_called()
    state.svc.position_manager.monitor_all_positions.assert_awaited_once()
    assert state.svc._exchange_stop_orders[pos.position_id] == "stop-1"
    assert state.calls[0]["side"] == ("SELL" if state.direction == "LONG" else "BUY")


def test_rest_ws_expiry_replays_do_not_duplicate_or_reopen_closed_position(state):
    state.ex._adapter.fetch_order.return_value = {"status": "closed", "filled": 10, "average": 100}
    asyncio.run(state.svc._monitor_pending_entries())
    pos = assert_adopted(state)
    ws(state)
    asyncio.run(state.svc._open_filled_entry("entry", state.plan, 100, 10))
    pos.status = PositionStatus.CLOSED
    state.svc._pending_plans["entry"] = state.plan
    state.svc._pending_placed_at["entry"] = datetime.now(timezone.utc) - timedelta(minutes=121)
    asyncio.run(state.svc._monitor_pending_entries())
    assert len(state.svc.position_manager.positions) == 1
    assert not state.svc.position_manager.get_open_positions()
    assert state.svc.stats.signals_taken == 1
    assert len(state.ex._fills) == 1 and len(state.calls) == 1
    assert not state.svc._pending_plans
    state.ex._adapter.cancel_order.assert_not_called()


@pytest.mark.parametrize("prior_partial", [False, True])
def test_ws_partial_then_cancel_adopts_terminal_cumulative_quantity(state, prior_partial):
    if prior_partial:
        ws(state, "partiallyfilled", 2)
    ws(state, "canceled", 4)
    ws(state, "canceled", 4)
    asyncio.run(state.svc._monitor_pending_entries())
    assert_adopted(state, 4)
    assert sum(fill.quantity for fill in state.ex._fills) == 4
    assert state.calls[0]["quantity"] == 4


@pytest.mark.parametrize("path", ["poll", "expiry"])
def test_rest_cancellation_discovers_partial_quantity_without_prior_update(state, path):
    response = {"status": "canceled", "filled": 4, "average": 100}
    if path == "poll":
        state.ex._adapter.fetch_order.return_value = response
    else:
        state.ex._adapter.cancel_order.return_value = response
        state.svc._pending_placed_at["entry"] -= timedelta(minutes=121)
    asyncio.run(state.svc._monitor_pending_entries())
    assert_adopted(state, 4)


def test_nonterminal_partial_remains_pending_until_cancel(state):
    ws(state, "partiallyfilled", 4)
    state.ex._adapter.fetch_order.return_value = {"status": "open", "filled": 4, "remaining": 6}
    state.ex._adapter.cancel_order.return_value = {"status": "canceled", "filled": 4}
    state.svc._pending_placed_at["entry"] -= timedelta(minutes=3)
    asyncio.run(state.svc._monitor_pending_entries())
    assert not state.svc.position_manager.positions
    assert "entry" in state.svc._pending_plans
    state.ex.check_fill_via_positions.assert_not_called()
    state.svc._pending_placed_at["entry"] -= timedelta(minutes=121)
    asyncio.run(state.svc._monitor_pending_entries())
    assert_adopted(state, 4)


@pytest.mark.parametrize("status", ["canceled", "rejected"])
def test_unfilled_terminal_order_clears_all_pending_metadata(state, status):
    ws(state, status, 0)
    asyncio.run(state.svc._monitor_pending_entries())
    assert not state.svc._pending_plans and not state.svc._pending_placed_price
    assert not state.svc.position_manager.positions and not state.calls
    assert not state.ex._fills


def test_cancel_response_without_quantity_does_not_invent_full_fill(state):
    state.ex._adapter.fetch_order.return_value = {"status": "canceled"}
    asyncio.run(state.svc._monitor_pending_entries())
    assert not state.svc.position_manager.positions and not state.ex._fills
    assert "entry" in state.svc._pending_plans
    assert state.order.status == OrderStatus.PENDING
    state.ex._adapter.fetch_order.return_value = {"status": "canceled", "filled": 0}
    asyncio.run(state.svc._monitor_pending_entries())
    assert not state.svc._pending_plans


@pytest.mark.parametrize("response", [{}, {"status": "open"}, RuntimeError("cancel timeout")])
def test_unknown_cancellation_keeps_pending_entry(state, response):
    state.svc._pending_placed_at["entry"] -= timedelta(minutes=121)
    if isinstance(response, Exception):
        state.ex._adapter.cancel_order.side_effect = response
    else:
        state.ex._adapter.cancel_order.return_value = response
    asyncio.run(state.svc._monitor_pending_entries())
    assert "entry" in state.svc._pending_plans and state.order.status == OrderStatus.PENDING


@pytest.mark.parametrize("price,quantity", [(0, 10), (100, 0), (float("nan"), 10), (100, float("inf"))])
def test_invalid_terminal_fill_retains_expired_plan(state, price, quantity):
    state.order.status = OrderStatus.FILLED
    state.order.price = state.order.average_fill_price = price
    state.order.filled_quantity = quantity
    state.svc._pending_placed_at["entry"] -= timedelta(minutes=121)
    asyncio.run(state.svc._monitor_pending_entries())
    assert "entry" in state.svc._pending_plans
    assert not state.svc.position_manager.positions
    assert any(event == "entry_adoption_deferred" for event, _ in state.svc.activities)


def test_adoption_error_preserves_plan_and_other_monitoring_then_recovers(state, monkeypatch):
    ws(state)
    original = state.svc.position_manager.open_position
    state.svc.position_manager.open_position = Mock(side_effect=RuntimeError("fixture failure"))
    monitor_tick(state, monkeypatch)
    assert "entry" in state.svc._pending_plans
    state.svc.position_manager.monitor_all_positions.assert_awaited_once()
    state.svc.position_manager.open_position = original
    monitor_tick(state, monkeypatch)
    assert_adopted(state)


def test_position_published_before_adoption_error_is_reused(state):
    ws(state)
    pm = state.svc.position_manager
    original = pm.open_position

    def publish_then_fail(**kwargs):
        original(**kwargs)
        raise RuntimeError("failure after position published")
    pm.open_position = publish_then_fail
    asyncio.run(state.svc._monitor_pending_entries())
    assert len(pm.positions) == 1 and "entry" in state.svc._pending_plans
    asyncio.run(state.svc._monitor_pending_entries())
    asyncio.run(state.svc._sync_exchange_stops())
    assert len(pm.positions) == 1 and not state.svc._pending_plans
    assert len(state.calls) == 1


@pytest.mark.parametrize("failure", [OrderStatus.REJECTED, RuntimeError("stop timeout")])
def test_failed_stop_retries_after_delay_and_does_not_repeat_other_exits(state, failure):
    state.plan.targets = [S(level=105 if state.direction == "LONG" else 95, percentage=50)]
    state.responses.append(failure)
    ws(state)
    asyncio.run(state.svc._monitor_pending_entries())
    pos = assert_adopted(state)
    assert pos.position_id not in state.svc._exchange_stop_orders
    for now in [100, 101, 104.9]:
        state.clock.now = now
        asyncio.run(state.svc._sync_exchange_stops())
    assert len(state.calls) == 1
    state.clock.now = 105
    asyncio.run(state.svc._sync_exchange_stops())
    assert state.svc._exchange_stop_orders[pos.position_id] == "stop-2"
    state.clock.now = 120
    asyncio.run(state.svc._sync_exchange_stops())
    assert len(state.calls) == 2
    state.ex.place_take_profit_order.assert_called_once()
    state.ex.place_trailing_stop_order.assert_called_once()
    assert any(event == "exchange_stop_failed" for event, _ in state.svc.activities)


def test_replacement_rejection_keeps_old_stop_then_places_before_cancelling(state):
    ws(state)
    asyncio.run(state.svc._monitor_pending_entries())
    pos = assert_adopted(state)
    pos.stop_loss = 100.0
    state.responses.append(OrderStatus.REJECTED)
    asyncio.run(state.svc._sync_exchange_stops())
    assert state.svc._exchange_stop_orders[pos.position_id] == "stop-1"
    assert state.ex._orders["stop-1"].status == OrderStatus.OPEN
    original = state.ex.cancel_order

    def cancel(oid):
        assert state.svc._exchange_stop_orders[pos.position_id] == "stop-3"
        assert state.ex._orders["stop-3"].status == OrderStatus.OPEN
        return original(oid)
    state.ex.cancel_order = Mock(side_effect=cancel)
    state.clock.now += 5
    asyncio.run(state.svc._sync_exchange_stops())
    state.ex.cancel_order.assert_called_once_with("stop-1")
    assert state.ex._orders["stop-1"].status == OrderStatus.CANCELLED


def test_retry_uses_remaining_quantity_and_closed_position_is_not_reprotected(state):
    state.responses.append(OrderStatus.REJECTED)
    ws(state)
    asyncio.run(state.svc._monitor_pending_entries())
    pos = assert_adopted(state)
    pos.remaining_quantity = 4
    state.clock.now += 5
    asyncio.run(state.svc._sync_exchange_stops())
    assert state.calls[-1]["quantity"] == 4
    pos.status = PositionStatus.CLOSED
    state.svc._exchange_stop_retry_at[pos.position_id] = 200
    state.clock.now = 300
    asyncio.run(state.svc._sync_exchange_stops())
    assert len(state.calls) == 2 and not state.svc._exchange_stop_retry_at


def test_missing_stop_id_with_cached_level_is_retried(state):
    ws(state)
    asyncio.run(state.svc._monitor_pending_entries())
    pos = assert_adopted(state)
    state.svc._exchange_stop_orders.pop(pos.position_id)
    asyncio.run(state.svc._sync_exchange_stops())
    assert len(state.calls) == 2
    assert state.svc._exchange_stop_orders[pos.position_id] == "stop-2"


def test_invalid_stop_on_one_position_does_not_block_next_position(state):
    ws(state)
    asyncio.run(state.svc._monitor_pending_entries())
    first = assert_adopted(state)
    first.stop_loss = None
    second_plan = S(**dict(vars(state.plan), symbol="SECOND/USDT"))
    pid = state.svc.position_manager.open_position(second_plan, 100, 2, "entry-2")
    asyncio.run(state.svc._sync_exchange_stops())
    assert pid in state.svc._exchange_stop_orders
    assert state.calls[-1]["quantity"] == 2
    assert first.position_id in state.svc._exchange_stop_retry_at


def test_zero_remaining_quantity_never_falls_back_to_original_size(state):
    state.responses.append(OrderStatus.REJECTED)
    ws(state)
    asyncio.run(state.svc._monitor_pending_entries())
    pos = assert_adopted(state)
    pos.remaining_quantity = 0
    state.clock.now += 5
    asyncio.run(state.svc._sync_exchange_stops())
    assert len(state.calls) == 1


def test_cancelled_protection_is_not_adopted_as_an_entry(state):
    state.svc._clear_pending_entry("entry")
    state.order.order_type = OrderType.STOP_LOSS
    ws(state, "canceled", 4)
    asyncio.run(state.svc._monitor_pending_entries())
    assert state.order.filled_quantity == 4
    assert not state.svc.position_manager.positions and not state.ex._fills
