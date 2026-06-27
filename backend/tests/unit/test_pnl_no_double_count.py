"""P&L double-count regression (TRIAGE #1, 2026-06-27). The target-exit path in
PositionManager._monitor_position was the ONLY exit path that did not zero unrealized_pnl after
settling the closed slice into realized_pnl, so total_pnl (= realized + unrealized) read 2x the
true P&L on target exits — overstating the journal / edge measurement.

These drive the REAL _monitor_position target block (order_executor=None skips order placement, so
the in-process bookkeeping runs directly; price_fetcher feeds the trigger price). The cycle-top
update_unrealized_pnl sets unrealized on the full qty, exactly reproducing the bug scenario."""
import asyncio
from datetime import datetime, timedelta, timezone

from backend.bot.executor.position_manager import (
    PositionManager,
    PositionState,
    PositionStatus,
)
from backend.shared.models.planner import Target

ENTRY = 0.1492
EXIT = 0.1487
QTY = 60240.0
TRUE_FULL_PNL = (ENTRY - EXIT) * QTY  # SHORT profit on the full position = 30.12


def _target(level, pct):
    t = Target(level=level, rationale="test")
    t.percentage = pct
    return t


def _short_position(targets):
    p = PositionState(
        position_id="t1", symbol="ADA/USDT:USDT", direction="SHORT",
        entry_price=ENTRY, quantity=QTY, remaining_quantity=QTY,
        stop_loss=0.1500, targets=targets,
    )
    # age past the simulation min-target-hold so _check_targets_hit (order_executor=None branch)
    # actually evaluates the target instead of returning None for a too-fresh position
    p.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
    return p


def _pm(pos):
    pm = PositionManager(price_fetcher=lambda s: EXIT, order_executor=None)
    pm.positions[pos.position_id] = pos
    return pm


def test_target_full_exit_does_not_double_count():
    # single 100% target at the exit price -> full close on hit
    pos = _short_position([_target(EXIT, 100.0)])
    asyncio.run(_pm(pos)._monitor_position(pos))
    assert pos.status == PositionStatus.CLOSED
    # the fix: unrealized cleared once the whole position is realized
    assert abs(pos.unrealized_pnl) < 1e-9, f"unrealized must be 0 on full close, got {pos.unrealized_pnl}"
    # total_pnl must equal the TRUE profit, not 2x it (the bug gave 60.24)
    assert abs(pos.total_pnl - TRUE_FULL_PNL) < 1e-6, f"doubled: {pos.total_pnl} vs {TRUE_FULL_PNL}"
    assert abs(pos.realized_pnl - TRUE_FULL_PNL) < 1e-6


def test_target_full_exit_long_symmetry():
    # LONG mirror (entry below exit = profit) — the fix is direction-agnostic; same no-2x invariant.
    l_entry, l_exit = 0.1487, 0.1492
    true_pnl = (l_exit - l_entry) * QTY  # 30.12
    pos = PositionState(
        position_id="tL", symbol="ADA/USDT:USDT", direction="LONG",
        entry_price=l_entry, quantity=QTY, remaining_quantity=QTY,
        stop_loss=0.1480, targets=[_target(l_exit, 100.0)],
    )
    pos.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
    pm = PositionManager(price_fetcher=lambda s: l_exit, order_executor=None)
    pm.positions[pos.position_id] = pos
    asyncio.run(pm._monitor_position(pos))
    assert pos.status == PositionStatus.CLOSED
    assert abs(pos.unrealized_pnl) < 1e-9
    assert abs(pos.total_pnl - true_pnl) < 1e-6


def test_target_partial_exit_unrealized_on_remaining_only():
    # two targets: TP1 at EXIT (50%, hit), TP2 deeper (50%, NOT hit at EXIT) so the position stays
    # PARTIAL. total_pnl is the full mark-to-market (30.12), NOT realized(15.06) + STALE full-qty
    # unrealized(30.12)=45.18 (the pre-fix bug).
    pos = _short_position([_target(EXIT, 50.0), _target(0.1480, 50.0)])
    asyncio.run(_pm(pos)._monitor_position(pos))
    assert pos.status == PositionStatus.PARTIAL
    assert abs(pos.realized_pnl - TRUE_FULL_PNL / 2) < 1e-6          # half closed
    assert abs(pos.unrealized_pnl - TRUE_FULL_PNL / 2) < 1e-6        # half remaining, on REDUCED qty
    assert abs(pos.total_pnl - TRUE_FULL_PNL) < 1e-6                 # not 1.5x
    assert abs(pos.remaining_quantity - QTY / 2) < 1e-3
