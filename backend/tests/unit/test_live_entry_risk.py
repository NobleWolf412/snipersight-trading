"""Offline final-entry risk checks with real CCXT precision and executor preflight.

The exchange market is an in-memory fixture; all transport is forbidden. No
adapter is constructed and LiveExecutor's account-changing constructor is bypassed.
"""

import asyncio
from decimal import Decimal
from threading import RLock
import time
from types import SimpleNamespace as S
from unittest.mock import Mock

import ccxt
import pytest

from backend.bot.live_trading_service import LiveTradingService
from backend.bot.executor.live_executor import LiveExecutor
from backend.bot.executor.paper_executor import OrderStatus
from backend.shared.config.live_trading_config import LiveTradingConfig


SYMBOL = "FIXTURE/USDT:USDT"


@pytest.fixture(params=["LONG", "SHORT"])
def state(request):
    exchange = ccxt.phemex()
    exchange.fetch = Mock(side_effect=AssertionError("Network forbidden"))
    exchange.request = Mock(side_effect=AssertionError("Exchange requests forbidden"))
    market = dict(id="FIXTUREUSDT", symbol=SYMBOL, base="FIXTURE", quote="USDT", settle="USDT",
                  type="swap", spot=False, swap=True, future=False, option=False,
                  linear=True, inverse=False, contract=True, contractSize=1.0,
                  precision={"price": 0.01, "amount": 0.001})
    exchange.markets = {SYMBOL: market}
    ex = object.__new__(LiveExecutor)
    ex.dry_run = True
    ex._state_lock = RLock()
    ex._reduce_only_order_ids = set()
    ex._unacknowledged_orders = {}
    ex._cancel_requested_orders = set()
    ex._order_id_prefix = "fixture"
    ex.balance_known = True
    ex.last_balance_observed_at = time.monotonic()
    ex._orders = {}
    ex._positions = {}
    ex._position_avg_price = {}
    ex._order_counter = 0
    ex._cached_balance = 1000.0
    ex._initial_balance = 1000.0
    ex.fee_rate = 0.001
    ex._fills = []
    ex.max_position_size_usd = 5000.0
    ex.max_total_exposure_usd = 10000.0
    ex.min_balance_usd = 50.0
    ex.target_leverage = 1
    ex.place_order = Mock(wraps=ex.place_order)
    svc = LiveTradingService()
    svc.executor = ex
    svc.position_manager = S(positions={}, get_open_positions=lambda: [])
    svc.config = LiveTradingConfig(dry_run=True, sensitivity_preset="custom", min_confluence=65,
                                  max_position_size_usd=5000, max_total_exposure_usd=10000)
    svc.adapter = S(exchange=exchange, get_market_info=Mock(return_value={"tick_size": 0.01, "lot_size": 0.001}))
    svc._startup_reconciled = svc._exchange_state_known = True
    svc._price_cache = {SYMBOL: 100.0}
    svc._price_cache_observed_at = {SYMBOL: time.monotonic()}
    svc.events = []
    svc.signals = []
    svc._log_activity = lambda event, data: svc.events.append((event, data))
    svc._log_signal = lambda plan, status, message, **data: svc.signals.append((status, message, data))
    return S(svc=svc, ex=ex, exchange=exchange, market=market, direction=request.param)


def plan(state, entry=100.0, stop=None, score=75, trade_type="intraday"):
    if stop is None:
        stop = 99.0 if state.direction == "LONG" else 101.0
    return S(symbol=SYMBOL, direction=state.direction, confidence_score=score,
             entry_zone=S(near_entry=entry, far_entry=entry), stop_loss=S(level=stop), trade_type=trade_type)


def run(state, entry_plan):
    asyncio.run(state.svc._process_signal(entry_plan))
    state.exchange.fetch.assert_not_called()
    state.exchange.request.assert_not_called()
    return list(state.ex._orders.values())


def assert_budget(state, entry_plan, order):
    request = state.ex.place_order.call_args.kwargs
    entry, native_stop, planned_stop = map(lambda n: Decimal(str(n)),
                                          [request["price"], request["sl_price"], entry_plan.stop_loss.level])
    distance = max(abs(entry - native_stop), abs(entry - planned_stop))
    risk = Decimal(str(order.quantity)) * distance
    budget = Decimal(str(state.ex.get_equity(state.svc._price_cache))) * Decimal(str(state.svc.config.risk_per_trade)) / 100
    assert 0 < risk <= budget
    assert Decimal(str(order.quantity)) == Decimal(state.exchange.amount_to_precision(SYMBOL, order.quantity))
    assert Decimal(str(order.price)) == Decimal(state.exchange.price_to_precision(SYMBOL, order.price))
    assert Decimal(str(request["sl_price"])) == Decimal(state.exchange.price_to_precision(SYMBOL, request["sl_price"]))
    risk_event = next(data for event, data in state.svc.events if event == "entry_risk_sized")
    assert risk_event["planned_stop_risk"] == float(risk)
    assert risk_event["risk_budget"] == float(budget)
    return risk


@pytest.mark.parametrize("case", ["control", "snap", "near", "pullback"])
def test_original_eight_cases_respect_final_entry_budget(state, case):
    sign = 1 if state.direction == "LONG" else -1
    entry = 100 + {"control": 0, "snap": 1, "near": 0.1, "pullback": -1}[case] * sign
    stop = 100 - (2 if case == "pullback" else 1) * sign
    p = plan(state, entry, stop)
    orders = run(state, p)
    assert len(orders) == 1 and orders[0].status == OrderStatus.OPEN
    risk = assert_budget(state, p, orders[0])
    assert Decimal("9.99") <= risk <= Decimal("10")
    if case == "snap":
        assert orders[0].quantity == 12.5  # previous method produced 25 and $20 risk


@pytest.mark.parametrize("trade_type", ["scalp", "intraday", "swing"])
@pytest.mark.parametrize("score", [69, 75])
def test_snap_thresholds_preserved_while_budget_is_invariant(state, trade_type, score):
    sign = 1 if state.direction == "LONG" else -1
    p = plan(state, 100 + 5 * sign, 100 - 2 * sign, score, trade_type)
    order = run(state, p)[0]
    assert order.status == OrderStatus.OPEN
    assert_budget(state, p, order)


def test_precision_is_applied_before_sizing_and_accounts_for_software_stop(state):
    sign = 1 if state.direction == "LONG" else -1
    state.market["precision"] = {"price": 0.1, "amount": 0.01}
    p = plan(state, 100 + 0.06 * sign, 100 - 1.04 * sign)
    order = run(state, p)[0]
    assert order.price == (100.1 if sign == 1 else 99.9)
    assert p.stop_loss.level == 100 - 1.04 * sign  # scanner plan remains unchanged
    assert_budget(state, p, order)


def test_coarse_lot_floors_without_exceeding_budget(state):
    state.market["precision"]["amount"] = 3.0
    p = plan(state)
    order = run(state, p)[0]
    assert order.quantity == 9
    assert_budget(state, p, order)


def test_zero_lot_result_is_rejected(state):
    state.market["precision"]["amount"] = 20.0
    assert not run(state, plan(state))
    state.ex.place_order.assert_not_called()
    assert state.svc.signals[-1][2]["reason_type"] == "position_size"


@pytest.mark.parametrize("stop_case", ["equal", "wrong_side", "snap_cross", "precision_collapse"])
def test_invalid_final_stop_geometry_never_reaches_executor(state, stop_case):
    sign = 1 if state.direction == "LONG" else -1
    entry = 100 if stop_case != "snap_cross" else 100 - sign
    stop = 100 if stop_case == "equal" else 100 + sign
    if stop_case in ("snap_cross", "precision_collapse"):
        stop = 100 - 0.1 * sign
    if stop_case == "precision_collapse":
        state.market["precision"]["price"] = 1.0
    assert not run(state, plan(state, entry, stop))
    state.ex.place_order.assert_not_called()
    assert state.svc.signals[-1][2]["reason_type"] == "risk_validation"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1, True])
def test_invalid_equity_cannot_bypass_risk_guard(state, bad):
    state.ex.get_equity = Mock(return_value=bad)
    assert not run(state, plan(state))
    state.ex.place_order.assert_not_called()


@pytest.mark.parametrize("field", ["market", "entry", "stop", "risk"])
def test_nonfinite_sizing_input_is_rejected(state, field):
    p = plan(state)
    if field == "market":
        state.svc._price_cache[SYMBOL] = float("nan")
    elif field == "entry":
        p.entry_zone.near_entry = float("nan")
    elif field == "stop":
        p.stop_loss.level = float("nan")
    else:
        state.svc.config.risk_per_trade = float("nan")
    assert not run(state, p)
    state.ex.place_order.assert_not_called()


@pytest.mark.parametrize("failure", ["metadata", "price", "amount_up"])
def test_unavailable_or_upward_precision_result_fails_closed(state, failure):
    if failure == "metadata":
        state.svc.adapter.get_market_info.side_effect = RuntimeError("metadata unavailable")
    elif failure == "price":
        state.exchange.price_to_precision = Mock(side_effect=ValueError("invalid precision"))
    else:
        state.exchange.amount_to_precision = Mock(return_value="10.001")
    assert not run(state, plan(state))
    state.ex.place_order.assert_not_called()


@pytest.mark.parametrize("changes", [{"contractSize": 0.01}, {"linear": False}, {"settle": "BTC"}])
def test_unsupported_contract_units_are_rejected(state, changes):
    state.market.update(changes)
    assert not run(state, plan(state))
    state.ex.place_order.assert_not_called()


def test_final_notional_above_cap_is_rejected_after_snap(state):
    state.svc.config.max_position_size_usd = state.ex.max_position_size_usd = 1100
    sign = 1 if state.direction == "LONG" else -1
    assert not run(state, plan(state, 100 + sign))
    state.ex.place_order.assert_not_called()
    assert state.svc.signals[-1][2]["reason_type"] == "position_size"


def test_final_notional_below_cap_is_not_rejected_using_market_based_size(state):
    state.svc.config.max_position_size_usd = state.ex.max_position_size_usd = 950
    sign = 1 if state.direction == "LONG" else -1
    p = plan(state, 100 + 0.1 * sign)
    order = run(state, p)[0]
    assert order.status == OrderStatus.OPEN
    assert_budget(state, p, order)


@pytest.mark.parametrize("cap", [1100, 1099.99])
def test_real_executor_aggregate_exposure_boundary_is_preserved(state, cap):
    state.ex._positions["OTHER"] = 1
    state.ex._position_avg_price["OTHER"] = 100
    state.svc._price_cache["OTHER"] = 100
    state.svc._price_cache_observed_at["OTHER"] = time.monotonic()
    state.ex.max_total_exposure_usd = cap
    order = run(state, plan(state))[0]
    assert order.status == (OrderStatus.OPEN if cap == 1100 else OrderStatus.REJECTED)
    assert bool(state.svc._pending_plans) == (cap == 1100)


def test_minimum_balance_preflight_still_blocks_submission(state):
    state.ex.min_balance_usd = 1001
    order = run(state, plan(state))[0]
    assert order.status == OrderStatus.REJECTED
    assert not state.svc._pending_plans


def test_budget_is_price_distance_only_and_improved_fill_does_not_increase_it(state):
    state.svc.config.leverage = state.ex.target_leverage = 5
    state.ex.fee_rate = 0.002
    p = plan(state)
    order = run(state, p)[0]
    assert order.quantity == 10  # leverage affects margin; fee budget policy unchanged
    fill_price = 99.9 if state.direction == "LONG" else 100.1
    fill = state.ex._record_fill(order, order.quantity, fill_price)
    stop_risk = order.quantity * abs(fill_price - p.stop_loss.level)
    assert stop_risk < 10
    assert fill.fee == pytest.approx(order.quantity * fill_price * state.ex.fee_rate)


def test_missing_market_cache_blocks_without_an_exchange_order(state):
    state.exchange.markets = None
    assert not run(state, plan(state))
    state.ex.place_order.assert_not_called()
