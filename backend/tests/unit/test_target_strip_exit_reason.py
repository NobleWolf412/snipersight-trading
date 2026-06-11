"""
Regression for Fix 5 (plan 2026-06-11): when a position's targets are fully
stripped by the structural-validity guard and the position eventually exits
via the stagnation path, exit_reason must be "target_strip", NOT "stagnation".

Root cause: _check_targets_hit removes targets whose level is on the wrong
side of the actual fill price (documented in test_executor_target_strip_telemetry.py
and the May-2026 INJ/fcfeffd6 forensics). The position then lives on with an
empty targets list. The stagnation timer fires later and was setting
exit_reason="stagnation", poisoning journal autopsies — they classified these
trades as "slow-bleed stagnation" rather than "entry-geometry failure".

Fixed in: position_manager.py _monitor_position stagnation exit block.
The fix checks: targets_stripped_count > 0 AND no remaining targets AND no
targets_hit. If all three hold, exit_reason is "target_strip".

Per CLAUDE.md §14 rubric 4 (negative pair), §16 rubric 12 (bull/bear symmetry).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from backend.bot.executor.position_manager import (
    PositionManager,
    PositionState,
    PositionStatus,
)
from backend.shared.models.planner import Target


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _price_fetcher_factory(price: float):
    def _fetch(symbol: str) -> float:
        return price
    return _fetch


def _make_position(
    direction: str,
    entry_price: float,
    stop_loss: float,
    *,
    targets_stripped_count: int = 0,
    targets_hit_count: int = 0,
    hours_old: float = 48.0,
    stagnation_strikes: int = 1,
) -> PositionState:
    """Build a PositionState pre-configured to fire stagnation on next monitor cycle.

    - No remaining targets (position left open after strip or all targets hit).
    - Old enough for the adaptive stagnation timer (48h >> scalp 2h / intraday 8h).
    - _stagnation_strikes=1 so the threshold (2) fires on the first call.
    - PnL slightly negative (below stagnation floor) but above the deep-loss
      deferral floor (stop is far away at 5% distance).
    """
    pos = PositionState(
        position_id="test-target-strip-reason",
        symbol="TEST/USDT",
        direction=direction,
        entry_price=entry_price,
        quantity=100.0,
        remaining_quantity=100.0,
        stop_loss=stop_loss,
        targets=[],
        created_at=datetime.now(timezone.utc) - timedelta(hours=hours_old),
        trade_type="scalp",
    )
    pos.targets_stripped_count = targets_stripped_count
    pos._stagnation_strikes = stagnation_strikes
    # Simulate any targets that were legitimately hit.
    for _ in range(targets_hit_count):
        t = Target(
            level=entry_price * 1.02 if direction == "LONG" else entry_price * 0.98,
            rationale="simulated hit",
            percentage=50.0,
            label="TP1",
            rr_ratio=2.0,
            weight=1.0,
        )
        pos.targets_hit.append(t)
    return pos


def _run_monitor(mgr: PositionManager, pos: PositionState):
    mgr.positions[pos.position_id] = pos
    with patch(
        "backend.bot.telemetry.logger.get_telemetry_logger",
        return_value=MagicMock(),
    ):
        asyncio.run(mgr._monitor_position(pos))


# ──────────────────────────────────────────────────────────────────────────────
# Positive: all targets stripped, none hit → exit_reason = "target_strip"
# ──────────────────────────────────────────────────────────────────────────────


def test_all_targets_stripped_long_gives_target_strip_exit_reason():
    """LONG position: all targets invalid (stripped), none ever hit.
    Stagnation fires → exit_reason must be 'target_strip', not 'stagnation'."""
    pos = _make_position(
        direction="LONG",
        entry_price=100.0,
        stop_loss=95.0,  # 5% away — deep-loss floor not triggered at 99.5
        targets_stripped_count=2,
        targets_hit_count=0,
    )
    mgr = PositionManager(
        price_fetcher=_price_fetcher_factory(99.5),  # slight loss, no stop hit
        order_executor=None,
        max_hours_open=None,  # disable hard cap; we're testing the stagnation path
    )
    _run_monitor(mgr, pos)
    assert pos.status == PositionStatus.CLOSED
    assert pos.exit_reason == "target_strip", (
        f"Expected 'target_strip', got '{pos.exit_reason}' — "
        "stagnation exit when all targets were stripped must use 'target_strip'"
    )


def test_all_targets_stripped_short_gives_target_strip_exit_reason():
    """SHORT mirror: same condition, bearish path."""
    pos = _make_position(
        direction="SHORT",
        entry_price=100.0,
        stop_loss=105.0,  # 5% away
        targets_stripped_count=3,
        targets_hit_count=0,
    )
    mgr = PositionManager(
        price_fetcher=_price_fetcher_factory(100.5),  # slight loss for SHORT
        order_executor=None,
        max_hours_open=None,
    )
    _run_monitor(mgr, pos)
    assert pos.status == PositionStatus.CLOSED
    assert pos.exit_reason == "target_strip", (
        f"Expected 'target_strip', got '{pos.exit_reason}' — SHORT mirror failed"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Negative: plain stagnation (no strip) stays "stagnation"
# ──────────────────────────────────────────────────────────────────────────────


def test_plain_stagnation_no_strip_keeps_stagnation_exit_reason_long():
    """Negative pair: no targets were stripped (targets_stripped_count=0).
    Stagnation exit must still produce 'stagnation', not 'target_strip'."""
    pos = _make_position(
        direction="LONG",
        entry_price=100.0,
        stop_loss=95.0,
        targets_stripped_count=0,
        targets_hit_count=0,
    )
    mgr = PositionManager(
        price_fetcher=_price_fetcher_factory(99.5),
        order_executor=None,
        max_hours_open=None,
    )
    _run_monitor(mgr, pos)
    assert pos.status == PositionStatus.CLOSED
    assert pos.exit_reason == "stagnation", (
        f"Expected 'stagnation', got '{pos.exit_reason}' — "
        "clean stagnation must not be reclassified as 'target_strip'"
    )


def test_plain_stagnation_no_strip_keeps_stagnation_exit_reason_short():
    """SHORT mirror of the plain-stagnation negative pair."""
    pos = _make_position(
        direction="SHORT",
        entry_price=100.0,
        stop_loss=105.0,
        targets_stripped_count=0,
        targets_hit_count=0,
    )
    mgr = PositionManager(
        price_fetcher=_price_fetcher_factory(100.5),
        order_executor=None,
        max_hours_open=None,
    )
    _run_monitor(mgr, pos)
    assert pos.status == PositionStatus.CLOSED
    assert pos.exit_reason == "stagnation"


# ──────────────────────────────────────────────────────────────────────────────
# Negative: TP1 was legitimately hit, THEN trailing targets stripped
# → remainder closes as "stagnation" (TP1 was real, don't misclassify)
# ──────────────────────────────────────────────────────────────────────────────


def test_partial_exit_then_strip_still_stagnation():
    """TP1 was legitimately hit (targets_hit_count=1), then TP2/3 were stripped.
    When the PARTIAL remainder exits via stagnation, exit_reason stays
    'stagnation' — TP1 was a real win; the strip is secondary context.
    'target_strip' is reserved for positions where NO TP was ever reachable."""
    pos = _make_position(
        direction="LONG",
        entry_price=100.0,
        stop_loss=95.0,
        targets_stripped_count=2,
        targets_hit_count=1,  # TP1 was legitimately hit
    )
    pos.status = PositionStatus.PARTIAL
    pos.remaining_quantity = 50.0
    mgr = PositionManager(
        price_fetcher=_price_fetcher_factory(99.5),
        order_executor=None,
        max_hours_open=None,
    )
    _run_monitor(mgr, pos)
    assert pos.status == PositionStatus.CLOSED
    assert pos.exit_reason == "stagnation", (
        f"Expected 'stagnation', got '{pos.exit_reason}' — "
        "remainder after a real partial exit must not be misclassified as 'target_strip'"
    )
