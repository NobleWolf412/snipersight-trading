"""Offline regression coverage for exchange-state validity and restart cleanup.

Extract actual methods/models without importing application bootstrap, credentials,
or exchange clients. Adapter responses and async scheduling are in-memory fixtures;
these tests do not validate exchange protocol behavior or real concurrency.
"""

import ast
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from decimal import Decimal, ROUND_DOWN
import logging
import math
from pathlib import Path
from threading import Lock, RLock
import time
from types import MethodType, SimpleNamespace as S
from typing import Any, Dict, List, Optional

import pytest

from backend.shared.config.scanner_modes import get_mode
from backend.shared.config.sensitivity import resolve_sensitivity, passes_confluence_gate
from backend.shared.config.strategy_policy import resolve_bot_sensitivity, plan_strategy_gate
from backend.shared.config.score_policy import STRONG_SCORE, evidence_allows_entry


ROOT = Path(__file__).resolve().parents[3]
SYMBOL = "FIXTURE/USDT"


def finish(coroutine):
    """Fixtures resolve awaits immediately; unexpected IO/suspension is an error."""
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    coroutine.close()
    raise AssertionError("Unexpected coroutine suspension")


async def noop(*args, **kwargs):
    pass


async def inline_thread(callback, *args):
    return callback(*args)


class InlineLoop:
    async def run_in_executor(self, executor, callback):
        return callback()


@pytest.fixture
def source():
    ns = dict(
        dataclass=dataclass, field=field, datetime=datetime, timedelta=timedelta,
        timezone=timezone, Enum=Enum, Optional=Optional, Dict=Dict, List=List,
        Any=Any, Target=object, TradePlan=object, math=math, time=time, Decimal=Decimal,
        PaperTradingStats=S, logger=logging.getLogger("test.live_reconciliation"),
        get_mode=get_mode, resolve_sensitivity=resolve_sensitivity, passes_confluence_gate=passes_confluence_gate,
        resolve_bot_sensitivity=resolve_bot_sensitivity, plan_strategy_gate=plan_strategy_gate,
        STRONG_SCORE=STRONG_SCORE, evidence_allows_entry=evidence_allows_entry,
        asyncio=S(get_running_loop=lambda: InlineLoop(), sleep=noop, to_thread=inline_thread, Lock=asyncio.Lock),
    )
    trees = {}

    def tree(path):
        if path not in trees:
            trees[path] = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        return trees[path]

    def execute(path, nodes):
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ROOT / path),
                     "exec", dont_inherit=True), ns)

    for path, names in [
        ("backend/bot/executor/paper_executor.py", ("OrderType", "OrderStatus")),
        ("backend/bot/executor/position_manager.py", ("PositionStatus", "PositionState")),
        ("backend/bot/live_trading_service.py", ("LiveBotStatus", "LifecycleConflict")),
    ]:
        execute(path, [n for n in tree(path).body if isinstance(n, ast.ClassDef) and n.name in names])

    methods = {}
    for path, clsname, names in [
        ("backend/bot/executor/live_executor.py", "LiveExecutor", ("reconcile_positions", "get_position", "get_open_position_symbols", "recover_uncertain_orders")),
        ("backend/bot/executor/position_manager.py", "PositionManager", ("get_open_positions", "close_position")),
        ("backend/bot/live_trading_service.py", "LiveTradingService", (
            "__init__", "reset", "_reset_session", "_set_exchange_state_known", "_entry_reconciliation_ready",
            "_startup_reconcile", "_observe_account", "_monitor_loop", "_process_signal", "_has_position",
            "_get_active_positions", "_detect_exchange_closed_positions", "_monitor_pending_entries",
            "_fresh_price_cache", "_valuation_equity", "_refresh_price_cache",
        )),
    ]:
        cls = next(n for n in tree(path).body if isinstance(n, ast.ClassDef) and n.name == clsname)
        for name in names:
            node = next(n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
            execute(path, [node])
            methods[(clsname, name)] = ns[name]
    paper = "backend/bot/paper_trading_service.py"
    for node in tree(paper).body:
        if (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                and node.target.id in ("_PENDING_TTL_MINUTES", "_MAX_LIMIT_DISTANCE_PCT")):
            ns[node.target.id] = ast.literal_eval(node.value)
    path = "backend/shared/utils/math_utils.py"
    execute(path, [n for n in tree(path).body if isinstance(n, ast.FunctionDef) and n.name == "round_to_lot"])
    return ns, methods


def bind(obj, source, cls):
    for (owner, name), fn in source[1].items():
        if owner == cls:
            setattr(obj, name, MethodType(fn, obj))
    return obj


def row(direction="LONG", **changes):
    return dict(dict(symbol=SYMBOL, contracts=10.0, side=direction.lower(), entryPrice=100.0), **changes)


def sequence(values):
    values = iter(values)

    def fetch():
        value = next(values)
        if isinstance(value, Exception):
            raise value
        return value
    return fetch


def make_executor(source, responses):
    ex = bind(S(dry_run=False, _positions={SYMBOL: 10.0},
                _position_avg_price={SYMBOL: 100.0}), source, "LiveExecutor")
    ex._adapter = S(fetch_positions=sequence(responses))
    ex._state_lock = RLock()
    ex._unacknowledged_orders = {}
    ex._cancel_requested_orders = set()
    ex._last_order_recovery_at = 0.0
    ex.balance_known = True
    ex.last_balance_observed_at = time.monotonic()
    ex.reconcile_balance = lambda: None
    ex.set_entry_admission = lambda enabled: None
    ex.get_balance = lambda: 1000.0
    ex.get_equity = lambda prices: 1000.0
    ex.get_open_orders = lambda: []
    ex.recovery_snapshot = lambda: {"revision": 0, "requests": []}
    ex.placed = []

    def place(**kwargs):
        ex.placed.append(kwargs)
        return S(status=S(value="OPEN"), order_id="new-entry")
    ex.place_order = place
    return ex


def make_service(source, responses, direction=None, orders=None, cancel_result=None):
    ns = source[0]
    svc = bind(S(), source, "LiveTradingService")
    svc.__init__()
    pm = bind(S(positions={}, _lock=Lock(), monitor_all_positions=noop), source, "PositionManager")
    if direction:
        pm.positions["pos"] = ns["PositionState"](
            position_id="pos", symbol=SYMBOL, direction=direction, entry_price=100.0,
            quantity=10.0, remaining_quantity=10.0,
            stop_loss=99.0 if direction == "LONG" else 101.0, targets=[],
        )
    svc.position_manager = pm
    svc.executor = make_executor(source, responses)
    if direction == "SHORT":
        svc.executor._positions[SYMBOL] = -10.0
    svc.config = S(dry_run=False, sniper_mode='stealth', balance_reconcile_interval=60,
                   kill_switch_enabled=False, max_positions=3, min_confluence=65.0,
                   sensitivity_preset="custom", risk_per_trade=1.0, max_position_size_usd=5000.0)
    svc.cancelled = []

    def cancel(oid, symbol):
        svc.cancelled.append((oid, symbol))
        if isinstance(cancel_result, Exception):
            raise cancel_result
        return {"status": "canceled"} if cancel_result is None else cancel_result
    svc.adapter = S(exchange=S(
        fetch_open_orders=lambda: [] if orders is None else orders,
        market=lambda symbol: dict(linear=True, contract=True, contractSize=1, settle="USDT", quote="USDT"),
        price_to_precision=lambda symbol, price: str(price),
        amount_to_precision=lambda symbol, amount: str(Decimal(amount).quantize(Decimal("0.001"), rounding=ROUND_DOWN))),

                    cancel_order=cancel, get_market_info=lambda symbol: {"lot_size": 0.001})
    svc.adapter.fetch_account_snapshot = lambda: {
        "complete": True, "scope": "phemex:swap:USDT",
        "orders": svc.adapter.exchange.fetch_open_orders(),
        "positions": [{"symbol": sym, "contracts": abs(qty)} for sym, qty in svc.executor._positions.items()],
    }
    svc.activities = []
    svc.signals = []
    svc._log_activity = lambda event, data: svc.activities.append((event, data))
    svc._log_signal = lambda *args, **kwargs: svc.signals.append((args, kwargs))
    svc._price_cache = {SYMBOL: 100.0}
    svc._price_cache_observed_at = {SYMBOL: time.monotonic()}
    svc._refresh_price_cache = noop
    svc._sync_exchange_stops = noop
    svc._sync_closed_positions = noop
    return svc


def tick(source, svc):
    async def stop_tick(seconds):
        svc._running = False
    source[0]["asyncio"].sleep = stop_tick
    svc._last_reconcile_at = -1e10
    svc._running = True
    finish(svc._monitor_loop())


@pytest.mark.parametrize("bad", [
    RuntimeError("timeout"), None, {}, [None], [row(contracts=None)],
    [row(contracts="bad")], [row(contracts=float("nan"))], [row(contracts=-1)],
    [row(contracts=True)], [row(side=None)], [row(entryPrice=float("inf"))],
    [row(entryPrice=0)], [row(symbol="")], [row(), row(side="short")],
    [row(contracts=20), row(symbol="OTHER/USDT", contracts="bad")],
])
def test_invalid_snapshot_is_unknown_and_publishes_no_partial_state(source, bad):
    ex = make_executor(source, [bad])
    before = (ex._positions.copy(), ex._position_avg_price.copy())
    assert ex.reconcile_positions() is None
    assert (ex._positions, ex._position_avg_price) == before


@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_complete_snapshot_updates_side_price_and_clears_absent_symbols(source, direction):
    ex = make_executor(source, [[row(direction, entryPrice=102.0)]])
    ex._positions["OLD/USDT"] = 2.0
    ex._position_avg_price["OLD/USDT"] = 40.0
    assert ex.reconcile_positions() == {SYMBOL}
    assert ex._positions == {SYMBOL: 10.0 if direction == "LONG" else -10.0, "OLD/USDT": 0.0}
    assert ex._position_avg_price == {SYMBOL: 102.0, "OLD/USDT": 0.0}


def test_valid_empty_and_zero_positions_are_distinct_from_failure(source):
    ex = make_executor(source, [[], [row(contracts=0, side=None, entryPrice=None)]])
    assert ex.reconcile_positions() == set()
    assert ex._positions[SYMBOL] == 0
    assert ex.reconcile_positions() == set()


@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_monitor_failure_preserves_position_protection_and_recovers(source, direction):
    svc = make_service(source, [RuntimeError("timeout"), [row(direction)]], direction)
    svc._startup_reconciled = svc._exchange_state_known = True
    svc._exchange_stop_orders = {"pos": "stop"}
    svc._exchange_stop_levels = {"pos": 99.0 if direction == "LONG" else 101.0}
    svc._exchange_tp_orders = {"pos": "tp"}
    svc._exchange_trailing_orders = {"pos": "trail"}
    tick(source, svc)
    pos = svc.position_manager.positions["pos"]
    assert pos.status == source[0]["PositionStatus"].OPEN
    assert pos.remaining_quantity == 10 and pos.realized_pnl == 0
    assert svc._exchange_stop_orders == {"pos": "stop"}
    assert svc._exchange_tp_orders == {"pos": "tp"}
    assert svc._exchange_trailing_orders == {"pos": "trail"}
    assert svc._has_position(SYMBOL) and not svc._entry_reconciliation_ready()
    finish(svc._process_signal(S(symbol=SYMBOL)))
    assert svc.signals[-1][1]["reason_type"] == "exchange_state_unknown"
    assert not svc.executor.placed
    tick(source, svc)
    assert svc._entry_reconciliation_ready() and svc._has_position(SYMBOL)
    assert not svc._orphaned_symbols


def test_monitor_valid_empty_snapshot_retains_existing_closure_path(source):
    svc = make_service(source, [[]], "LONG")
    svc._startup_reconciled = svc._exchange_state_known = True
    tick(source, svc)
    assert svc.position_manager.positions["pos"].status == source[0]["PositionStatus"].CLOSED
    assert svc.executor.get_position(SYMBOL) == 0
    assert svc._entry_reconciliation_ready()


def test_direct_unknown_snapshot_cannot_close_positions(source):
    svc = make_service(source, [], "LONG")
    finish(svc._detect_exchange_closed_positions(None))
    assert len(svc.position_manager.get_open_positions()) == 1
    assert not svc._entry_reconciliation_ready()


def test_monitor_blocks_newly_observed_unmanaged_position(source):
    svc = make_service(source, [[row()]])
    svc._startup_reconciled = svc._exchange_state_known = True
    tick(source, svc)
    assert svc._has_position(SYMBOL) and svc._entry_reconciliation_ready()


def test_startup_failure_does_not_cancel_and_monitor_retries(source):
    orders = [dict(id="stop", symbol=SYMBOL, type="stop")]
    svc = make_service(source, [RuntimeError("timeout"), [row()], [row()]], orders=orders)
    assert finish(svc._startup_reconcile()) is False
    assert not svc.cancelled and not svc._entry_reconciliation_ready()
    tick(source, svc)
    assert not svc._entry_reconciliation_ready() and svc._has_position(SYMBOL)
    assert not svc.cancelled


@pytest.mark.parametrize("order", [
    dict(type="stop"), dict(type="trailing_stop_market"), dict(type="take_profit_market"),
    dict(type="limit", reduceOnly=True), dict(type="limit", info={"closeOnTrigger": True}),
])
def test_startup_preserves_protection_even_without_open_position(source, order):
    svc = make_service(source, [[], []], orders=[dict(id="old-stop", symbol=SYMBOL, **order)])
    assert finish(svc._startup_reconcile()) is False
    assert not svc.cancelled and svc._has_position(SYMBOL)


@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_startup_foreign_order_blocks_admission_without_cancellation(source, direction):
    svc = make_service(source, [[], [row(direction)]],
                       orders=[dict(id="entry", symbol=SYMBOL, type="limit")],
                       cancel_result={"status": "closed"})
    assert finish(svc._startup_reconcile()) is False
    assert not svc.cancelled
    assert svc._has_position(SYMBOL)


def test_startup_preserves_foreign_plain_entry(source):
    svc = make_service(source, [[], []], orders=[dict(id="entry", symbol=SYMBOL, type="limit")])
    assert finish(svc._startup_reconcile()) is False
    assert not svc.cancelled
    assert not svc._entry_reconciliation_ready() and svc._has_position(SYMBOL)


def test_startup_accepts_complete_flat_account(source):
    svc = make_service(source, [[], []])
    assert finish(svc._startup_reconcile()) is True
    assert svc._entry_reconciliation_ready()


@pytest.mark.parametrize("orders", [None, {}, [None], [dict(id="a", symbol=SYMBOL, type="limit"), {}]])
def test_invalid_order_snapshot_prevents_all_cancellations(source, orders):
    svc = make_service(source, [[]])
    svc.adapter.exchange.fetch_open_orders = lambda: orders
    assert finish(svc._startup_reconcile()) is False
    assert not svc.cancelled and not svc._entry_reconciliation_ready()


@pytest.mark.parametrize("result", [{}, {"status": "open"}, RuntimeError("cancel timeout")])
def test_unconfirmed_cancellation_keeps_admission_blocked(source, result):
    svc = make_service(source, [[]], orders=[dict(id="entry", symbol=SYMBOL, type="limit")],
                       cancel_result=result)
    assert finish(svc._startup_reconcile()) is False
    assert not svc._entry_reconciliation_ready()


def test_final_snapshot_failure_keeps_admission_blocked(source):
    svc = make_service(source, [[], RuntimeError("post-cleanup timeout")])
    assert finish(svc._startup_reconcile()) is False
    assert not svc._entry_reconciliation_ready()


@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
@pytest.mark.parametrize("fail_during_price_fetch", [False, True])
def test_entry_gate_checks_again_after_await(source, direction, fail_during_price_fetch):
    svc = make_service(source, [])
    svc._startup_reconciled = svc._exchange_state_known = True
    svc._price_cache = {}
    svc._refresh_price_cache = MethodType(source[1][('LiveTradingService', '_refresh_price_cache')], svc)

    async def fetch(symbol):
        if fail_during_price_fetch:
            svc._set_exchange_state_known(False, "fixture timeout during price fetch")
        return 100.0
    svc._fetch_price = fetch
    plan = S(symbol=SYMBOL, confidence_score=75.0, direction=direction,
             stop_loss=S(level=99.0 if direction == "LONG" else 101.0),
             entry_zone=S(near_entry=100.0, far_entry=100.0), trade_type="intraday")
    finish(svc._process_signal(plan))
    assert len(svc.executor.placed) == (0 if fail_during_price_fetch else 1)
    assert svc.signals[-1][1]["reason_type"] == ("exchange_state_unknown" if fail_during_price_fetch else "pending_fill")


def test_initial_and_reset_state_block_entries(source):
    svc = make_service(source, [])
    assert not svc._entry_reconciliation_ready()
    svc._startup_reconciled = svc._exchange_state_known = True
    svc.executor = None  # Resetting an idle session has no account to re-observe.
    finish(svc.reset())
    assert not svc._entry_reconciliation_ready()


def test_dry_run_startup_does_not_fetch_exchange_state(source):
    svc = make_service(source, [])
    svc.config.dry_run = True
    assert finish(svc._startup_reconcile()) is True
    assert svc._entry_reconciliation_ready() and not svc.cancelled
