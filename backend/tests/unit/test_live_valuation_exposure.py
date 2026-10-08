"""Offline regressions for unavailable valuation and pending entry reservations."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier, RLock
import time
from types import SimpleNamespace as S
from unittest.mock import AsyncMock, Mock

import pytest

from backend.bot.executor.live_executor import LiveExecutor
from backend.bot.executor.paper_executor import Order, OrderSide, OrderStatus, OrderType
from backend.bot.live_trading_service import LiveTradingService
import backend.bot.live_trading_service as service_module
from backend.tests.unit.test_live_entry_risk import state, plan, run, SYMBOL
from backend.tests.unit.execution_fixtures import attach_journal, seed_order


@pytest.fixture(params=["LONG", "SHORT"])
def executor(request, tmp_path):
    ex = object.__new__(LiveExecutor)
    ex._state_lock = RLock()
    ex._reduce_only_order_ids = set()
    ex._unacknowledged_orders = {}
    ex._cancel_requested_orders = set()
    ex._last_order_recovery_at = 0.0
    ex._order_id_prefix = "fixture"
    ex._orders = {}
    ex._order_counter = 0
    ex._positions = {}
    ex._position_avg_price = {}
    ex._fills = []
    ex._exchange_order_map = {}
    ex._reverse_order_map = {}
    ex._cached_balance = ex._initial_balance = 1000.0
    ex.balance_known = True
    ex.last_balance_observed_at = time.monotonic()
    ex.last_balance_error = ex.last_equity_error = None
    ex.max_position_size_usd = 10000
    ex.max_total_exposure_usd = 1500
    ex.min_balance_usd = 50
    ex.fee_rate = 0.001
    ex.target_leverage = 1
    ex.dry_run = True
    ex.side = "BUY" if request.param == "LONG" else "SELL"
    ex.sign = 1 if request.param == "LONG" else -1
    ex._adapter = S(cancel_order=Mock(), fetch_balance=Mock())
    ex.metrics = {"fills_recorded_via_ws": 0, "fills_recorded_via_rest": 0, "balance_fetch_failures": 0}
    attach_journal(ex, tmp_path / "execution.sqlite3")
    yield ex
    ex._journal.close()


def entry(ex, symbol="A", quantity=10):
    return ex.place_order(symbol, ex.side, "LIMIT", quantity, price=100)


@pytest.mark.parametrize("mark", [None, 0, -1, float("nan"), float("inf"), True])
def test_missing_or_invalid_mark_makes_equity_unavailable(executor, mark):
    ex = executor
    ex._positions = {"A": ex.sign}
    ex._position_avg_price = {"A": 100}
    assert ex.get_equity({} if mark is None else {"A": mark}) is None
    assert ex.get_pnl({}) is None
    assert "A" in ex.last_equity_error
    assert ex.get_equity({"A": 100}) == 1000
    assert ex.last_equity_error is None
    assert ex.get_equity({"A": 110}) == 1000 + 10 * ex.sign


def test_flat_symbol_needs_no_mark_but_unknown_balance_blocks_equity(executor):
    executor._positions["FLAT"] = 0
    assert executor.get_equity({}) == 1000
    executor.balance_known = False
    assert executor.get_equity({}) is None


@pytest.mark.parametrize("response", [{}, {"free": {}}, {"free": {"USDT": None}},
                                    {"free": {"USDT": float("nan")}}, {"free": {"USDT": True}}, RuntimeError("timeout")])
def test_balance_fetch_failure_preserves_cash_but_invalidates_valuation(executor, response):
    executor.dry_run = False
    before = executor.last_balance_observed_at
    if isinstance(response, Exception):
        executor._adapter.fetch_balance.side_effect = response
    else:
        executor._adapter.fetch_balance.return_value = response
    assert executor.reconcile_balance() == 1000
    assert not executor.balance_known and executor.last_balance_observed_at == before
    assert executor.get_equity({}) is None
    executor._adapter.fetch_balance.side_effect = None
    executor._adapter.fetch_balance.return_value = {"free": {"USDT": 0}}
    assert executor.reconcile_balance() == 0
    assert executor.balance_known and executor.get_equity({}) == 0


def test_candidate_counts_once_and_second_pending_entry_cannot_reuse_budget(executor):
    executor.max_total_exposure_usd = 1000
    first = entry(executor)
    second = entry(executor, "B", 1)
    assert first.status == OrderStatus.OPEN and second.status == OrderStatus.REJECTED
    assert executor._total_exposure_usd() == 1000
    assert "committed exposure" in second.rejection_reason
    assert executor.cancel_order(first.order_id)
    assert entry(executor, "B").status == OrderStatus.OPEN


def test_partial_fill_moves_reservation_and_cancel_releases_only_remainder(executor):
    first = entry(executor)
    executor.apply_ws_fill("", first.order_id, "partiallyfilled", 4, 100)
    assert executor._total_exposure_usd() == 1000
    assert entry(executor, "B", 5).status == OrderStatus.OPEN
    assert entry(executor, "C", 0.001).status == OrderStatus.REJECTED
    assert executor.cancel_order(first.order_id) is False  # terminal partial fill
    assert executor._total_exposure_usd() == 900  # 400 filled + 500 pending
    assert entry(executor, "C", 6).status == OrderStatus.OPEN


def test_full_fill_replaces_reservation_without_double_counting(executor):
    order = entry(executor)
    executor.apply_ws_fill("", order.order_id, "filled", 10, 100)
    executor.apply_ws_fill("", order.order_id, "filled", 10, 100)
    assert executor._total_exposure_usd() == 1000
    assert entry(executor, "B", 5).status == OrderStatus.OPEN
    assert entry(executor, "C", 1).status == OrderStatus.REJECTED


def test_rejected_entry_releases_its_reservation(executor):
    order = entry(executor)
    executor.apply_ws_fill("", order.order_id, "rejected", 0, 0)
    assert executor._total_exposure_usd() == 0
    assert entry(executor).status == OrderStatus.OPEN


@pytest.mark.parametrize("response", [{}, {"status": "open"}, RuntimeError("cancel timeout")])
def test_unconfirmed_cancel_does_not_release_reservation(executor, response):
    order = entry(executor)
    seed_order(executor, order)
    executor.dry_run = False
    executor._exchange_order_map[order.order_id] = "remote"
    if isinstance(response, Exception):
        executor._adapter.cancel_order.side_effect = response
    else:
        executor._adapter.cancel_order.return_value = response
    assert not executor.cancel_order(order.order_id)
    assert executor._total_exposure_usd() == 1000


def test_reduce_only_exit_bypasses_entry_limits_and_is_not_reserved(executor):
    executor._positions = {"A": 20 * executor.sign}
    executor._position_avg_price = {"A": 100}
    executor.balance_known = False
    executor._cached_balance = 0
    closing_side = "SELL" if executor.sign == 1 else "BUY"
    exit_order = executor.place_order("A", closing_side, "LIMIT", 20, price=100, reduce_only=True)
    assert exit_order.status == OrderStatus.OPEN
    assert executor._total_exposure_usd() == 2000


def test_native_exit_orders_do_not_consume_pending_entry_budget(executor):
    for typ in (OrderType.STOP_LOSS, OrderType.TAKE_PROFIT, OrderType.TRAILING_STOP):
        executor._orders[typ.value] = Order(typ.value, "A", OrderSide.BUY, typ, 50,
                                            price=100, status=OrderStatus.OPEN)
    assert executor._total_exposure_usd() == 0


@pytest.mark.parametrize("price", [None, float("nan")])
def test_unpriced_pending_order_blocks_more_risk(executor, price):
    order = entry(executor)
    order.price = price
    later = entry(executor, "B", 1)
    assert later.status == OrderStatus.REJECTED
    assert "pending entry price" in later.rejection_reason


def test_concurrent_admission_cannot_reuse_same_exposure_allowance(executor):
    executor.max_total_exposure_usd = 150
    gate = Barrier(8)

    def submit(index):
        gate.wait(timeout=3)
        closing_side = "SELL" if executor.side == "BUY" else "BUY"
        executor.place_stop_order(str(index), closing_side, 1, 99)
        result = entry(executor, str(index), 1)
        executor.place_take_profit_order(str(index), closing_side, 1, 110)
        executor.place_trailing_stop_order(str(index), closing_side, 1, 105, 1)
        return result
    with ThreadPoolExecutor(max_workers=8) as pool:
        orders = list(pool.map(submit, range(8)))
    assert sum(order.status == OrderStatus.OPEN for order in orders) == 1
    assert len({order.order_id for order in orders}) == 8
    assert len(executor._orders) == 32  # 8 entries plus 24 protective orders
    assert executor._total_exposure_usd() == 100


def test_orphan_position_is_refreshed_and_can_be_valued(state):
    state.ex._positions = {"ORPHAN": 1 if state.direction == "LONG" else -1}
    state.ex._position_avg_price = {"ORPHAN": 100}
    state.svc._fetch_price = AsyncMock(return_value=100)
    asyncio.run(state.svc._refresh_price_cache())
    state.svc._fetch_price.assert_awaited_once_with("ORPHAN")
    assert state.svc._valuation_equity() == 1000
    assert state.svc._price_cache_refreshed_at is not None


@pytest.mark.parametrize("failure", [RuntimeError("ticker timeout"), float("nan")])
def test_failed_refresh_invalidates_old_mark_and_recovers(state, failure):
    state.ex._positions = {"ORPHAN": 1 if state.direction == "LONG" else -1}
    state.ex._position_avg_price = {"ORPHAN": 100}
    state.svc._price_cache["ORPHAN"] = 100
    state.svc._price_cache_observed_at["ORPHAN"] = time.monotonic()
    state.svc._fetch_price = AsyncMock(side_effect=failure) if isinstance(failure, Exception) else AsyncMock(return_value=failure)
    asyncio.run(state.svc._refresh_price_cache())
    assert state.svc._price_cache["ORPHAN"] == 100  # retained only as last-known data
    assert "ORPHAN" not in state.svc._fresh_price_cache()
    assert state.svc._valuation_equity() is None
    assert state.svc._price_cache_refreshed_at is None
    state.svc._fetch_price = AsyncMock(return_value=100)
    asyncio.run(state.svc._refresh_price_cache())
    assert state.svc._valuation_equity() == 1000


def test_stale_or_unstamped_prices_do_not_authorize_entry(state):
    state.svc._price_cache_observed_at[SYMBOL] = time.monotonic() - 31
    state.svc._fetch_price = AsyncMock(side_effect=RuntimeError("timeout"))
    assert not run(state, plan(state))
    state.ex.place_order.assert_not_called()
    state.svc._fetch_price = AsyncMock(return_value=100)
    assert run(state, plan(state))[0].status == OrderStatus.OPEN


def test_unpriced_orphan_blocks_admission_despite_fresh_entry_price(state):
    state.ex._positions = {"ORPHAN": 1 if state.direction == "LONG" else -1}
    state.ex._position_avg_price = {"ORPHAN": 100}

    async def fetch(symbol):
        if symbol == "ORPHAN":
            raise RuntimeError("orphan quote missing")
        return 100
    state.svc._fetch_price = fetch
    assert not run(state, plan(state))
    state.ex.place_order.assert_not_called()
    assert state.svc.signals[-1][2]["reason_type"] == "risk_validation"


def test_old_or_failed_balance_cannot_authorize_new_entry(state):
    state.ex.last_balance_observed_at = time.monotonic() - 121
    assert not run(state, plan(state))
    state.ex.last_balance_observed_at = time.monotonic()
    state.ex.balance_known = False
    assert not run(state, plan(state))
    state.ex.balance_known = True
    assert run(state, plan(state))[0].status == OrderStatus.OPEN


def test_unavailable_equity_does_not_change_drawdown_or_repeat_trade_stats(state):
    state.ex.balance_known = False
    state.svc._peak_equity = 1000
    state.svc.stats.max_drawdown = 2
    state.svc._update_stats(S(pnl=-10, exit_reason="stop_loss"))
    assert state.svc._peak_equity == 1000 and state.svc.stats.max_drawdown == 2
    assert state.svc.stats.total_trades == 1 and state.svc.stats.total_pnl == -10


def test_entry_quote_expiring_during_metadata_work_is_not_submitted(state, monkeypatch):
    clock = S(now=time.monotonic())
    monkeypatch.setattr(service_module, "time", S(monotonic=lambda: clock.now))
    state.svc.adapter.get_market_info.side_effect = lambda symbol: setattr(clock, "now", clock.now + 31)
    assert not run(state, plan(state))
    state.ex.place_order.assert_not_called()
    assert state.svc.signals[-1][2]["reason_type"] == "price_fetch"
