"""
Regression for hot-path audit bug #1 (1_BROKEN): PositionManager._execute_exit
and _execute_partial_exit DISCARDED the order_executor return value and returned
True unconditionally (except on a raised exception).

The live/paper order_executor wrappers (_execute_exit_order) do NOT raise on a
failed close — they return False (rejected reduce-only with the position still
open on the exchange, None order, None fill). Discarding that False made
_monitor_position settle the PositionState as closed while the live position
stayed OPEN and naked (the exchange-native stop is cancelled BEFORE the market
exit fires). See:
  backend/diagnostics/decisions/2026-05-29__fix-design__execute-exit-discarded-return.md
  backend/diagnostics/decisions/2026-05-29__hotpath-robustness-audit.md

These tests pin BOTH layers:
  - Direct contract: _execute_exit / _execute_partial_exit return the executor's
    bool (False stays False, True stays True), for LONG and SHORT.
  - End-to-end settle: a stop-hit with a failing executor must NOT settle the
    position (stays OPEN, remaining_quantity unchanged, still in
    get_open_positions); a succeeding executor settles it exactly as before.

Per CLAUDE.md §11 (loud-failure surfacing), §14 rubric 4 (negative+positive
pair), §16 rubric 12 (bull/bear symmetry).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from unittest.mock import patch, MagicMock

from backend.bot.executor.position_manager import (
    PositionManager,
    PositionState,
    PositionStatus,
)


def _price_fetcher_factory(price: float):
    def _fetch(symbol: str) -> float:
        return price
    return _fetch


def _executor_returning(value):
    """Async order_executor stub that returns a fixed value (mirrors the real
    _execute_exit_order bool contract)."""
    async def _stub(*args, **kwargs):
        return value
    return _stub


def _make_position(direction: str, entry_price: float) -> PositionState:
    return PositionState(
        position_id="test-position",
        symbol="TEST/USDT",
        direction=direction,
        entry_price=entry_price,
        quantity=100.0,
        remaining_quantity=100.0,
        stop_loss=entry_price * 0.99 if direction == "LONG" else entry_price * 1.01,
        targets=[],
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Direct contract — _execute_exit propagates the executor bool
# ──────────────────────────────────────────────────────────────────────────────


def test_execute_exit_returns_false_when_executor_fails_long():
    pos = _make_position("LONG", 100.0)
    mgr = PositionManager(
        price_fetcher=_price_fetcher_factory(98.0),
        order_executor=_executor_returning(False),
    )
    result = asyncio.run(mgr._execute_exit(pos, 98.0, "STOP_LOSS"))
    assert result is False  # was unconditionally True before the fix


def test_execute_exit_returns_false_when_executor_fails_short():
    pos = _make_position("SHORT", 100.0)
    mgr = PositionManager(
        price_fetcher=_price_fetcher_factory(102.0),
        order_executor=_executor_returning(False),
    )
    result = asyncio.run(mgr._execute_exit(pos, 102.0, "STOP_LOSS"))
    assert result is False


def test_execute_exit_returns_true_when_executor_succeeds_long():
    pos = _make_position("LONG", 100.0)
    mgr = PositionManager(
        price_fetcher=_price_fetcher_factory(98.0),
        order_executor=_executor_returning(True),
    )
    assert asyncio.run(mgr._execute_exit(pos, 98.0, "STOP_LOSS")) is True


def test_execute_exit_returns_true_when_executor_succeeds_short():
    pos = _make_position("SHORT", 100.0)
    mgr = PositionManager(
        price_fetcher=_price_fetcher_factory(102.0),
        order_executor=_executor_returning(True),
    )
    assert asyncio.run(mgr._execute_exit(pos, 102.0, "STOP_LOSS")) is True


# ──────────────────────────────────────────────────────────────────────────────
# Direct contract — _execute_partial_exit propagates the executor bool
# ──────────────────────────────────────────────────────────────────────────────


def test_execute_partial_exit_returns_false_when_executor_fails_long():
    pos = _make_position("LONG", 100.0)
    mgr = PositionManager(
        price_fetcher=_price_fetcher_factory(105.0),
        order_executor=_executor_returning(False),
    )
    assert asyncio.run(mgr._execute_partial_exit(pos, 105.0, 50.0)) is False


def test_execute_partial_exit_returns_false_when_executor_fails_short():
    pos = _make_position("SHORT", 100.0)
    mgr = PositionManager(
        price_fetcher=_price_fetcher_factory(95.0),
        order_executor=_executor_returning(False),
    )
    assert asyncio.run(mgr._execute_partial_exit(pos, 95.0, 50.0)) is False


def test_execute_partial_exit_returns_true_when_executor_succeeds():
    pos = _make_position("LONG", 100.0)
    mgr = PositionManager(
        price_fetcher=_price_fetcher_factory(105.0),
        order_executor=_executor_returning(True),
    )
    assert asyncio.run(mgr._execute_partial_exit(pos, 105.0, 50.0)) is True


# ──────────────────────────────────────────────────────────────────────────────
# End-to-end — a failing stop exit must NOT settle the position (the bug)
# ──────────────────────────────────────────────────────────────────────────────


def _run_monitor(mgr: PositionManager, pos: PositionState):
    mgr.positions[pos.position_id] = pos
    with patch(
        "backend.bot.telemetry.logger.get_telemetry_logger",
        return_value=MagicMock(),
    ):
        asyncio.run(mgr._monitor_position(pos))


def test_failed_stop_exit_leaves_position_open_long():
    """LONG stop hit (price <= stop) with a failing executor: position must
    stay OPEN, remaining_quantity unchanged, still in get_open_positions —
    NOT settled to STOPPED_OUT. This is the stranded-position bug."""
    pos = _make_position("LONG", 100.0)  # stop_loss 99.0
    mgr = PositionManager(
        price_fetcher=_price_fetcher_factory(98.0),  # below stop → stop hit
        order_executor=_executor_returning(False),
    )
    _run_monitor(mgr, pos)
    assert pos.status == PositionStatus.OPEN
    assert pos.remaining_quantity == 100.0
    assert pos.position_id in {p.position_id for p in mgr.get_open_positions()}


def test_failed_stop_exit_leaves_position_open_short():
    """SHORT mirror: price >= stop with a failing executor must not settle."""
    pos = _make_position("SHORT", 100.0)  # stop_loss 101.0
    mgr = PositionManager(
        price_fetcher=_price_fetcher_factory(102.0),  # above stop → stop hit
        order_executor=_executor_returning(False),
    )
    _run_monitor(mgr, pos)
    assert pos.status == PositionStatus.OPEN
    assert pos.remaining_quantity == 100.0
    assert pos.position_id in {p.position_id for p in mgr.get_open_positions()}


def test_successful_stop_exit_settles_position_long():
    """Positive (no-regression) pair: a succeeding executor settles the stop
    exactly as before the fix — STOPPED_OUT, qty 0, removed from open."""
    pos = _make_position("LONG", 100.0)
    mgr = PositionManager(
        price_fetcher=_price_fetcher_factory(98.0),
        order_executor=_executor_returning(True),
    )
    _run_monitor(mgr, pos)
    assert pos.status == PositionStatus.STOPPED_OUT
    assert pos.remaining_quantity == 0.0
    assert pos.position_id not in {p.position_id for p in mgr.get_open_positions()}


def test_successful_stop_exit_settles_position_short():
    """SHORT mirror of the positive pair."""
    pos = _make_position("SHORT", 100.0)
    mgr = PositionManager(
        price_fetcher=_price_fetcher_factory(102.0),
        order_executor=_executor_returning(True),
    )
    _run_monitor(mgr, pos)
    assert pos.status == PositionStatus.STOPPED_OUT
    assert pos.remaining_quantity == 0.0
    assert pos.position_id not in {p.position_id for p in mgr.get_open_positions()}
