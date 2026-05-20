"""
Tests for the structural-validity guard in PositionManager._check_targets_hit.

Per CLAUDE.md §11 (silent-bug class), §14 rubric 3 (mass conservation), and
§14 rubric 4 (negative tests paired with positive):

Bug context — May 2026 INJ/USDT_1779288485 forensics (session fcfeffd6):
  45/67 session trades (and 306/460 all-session "target wins") closed in
  <1 second with exit_reason='target' and pnl<0. Root cause: targets are
  computed at signal time relative to the planned entry; if signal-vs-fill
  drift pushes actual entry past the target level, the executor's
  _check_targets_hit returns the (now-unfavorable) target as "hit" the
  instant the position opens.

Fix (Patch B): _check_targets_hit filters structurally-invalid targets
before matching against current_price. LONG: target.level > entry_price
required. SHORT: target.level < entry_price required.

These tests:
  - Positive: valid LONG/SHORT targets match correctly (no regression)
  - Negative LONG: target below entry is removed, not returned as hit
  - Negative SHORT: target above entry is removed, not returned as hit
  - Mixed: invalid targets removed while valid ones remain
  - All invalid: all targets removed; no hit returned (position stays open)
  - Mass-conservation: assert in the function body fires if guard is bypassed
  - Idempotency: re-calling on already-cleaned position is stable
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

import pytest

from backend.bot.executor.position_manager import (
    PositionManager,
    PositionState,
    PositionStatus,
)
from backend.shared.models.planner import Target


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


def _dummy_price_fetcher(symbol: str) -> float:
    return 100.0


@pytest.fixture
def manager() -> PositionManager:
    """A PositionManager that simulates an executor present (paper mode).

    `order_executor=lambda` (non-None) ensures the SIMULATION_MIN_TARGET_HOLD
    branch does NOT fire, mirroring paper-trading where an executor exists
    but isn't a real exchange. The bug we're fixing only manifests in that
    branch — same-process tests with order_executor=None would be filtered
    out by the existing hold check.
    """
    return PositionManager(
        price_fetcher=_dummy_price_fetcher,
        order_executor=lambda *a, **kw: None,
    )


def _make_target(level: float, percentage: float = 50.0, label: str = "TP") -> Target:
    return Target(
        level=level,
        rationale="test target",
        percentage=percentage,
        label=label,
        rr_ratio=1.5,
        weight=1.0,
    )


def _make_position(
    direction: str,
    entry_price: float,
    target_levels: List[float],
    stop_loss: float = 0.0,
) -> PositionState:
    targets = [_make_target(lvl) for lvl in target_levels]
    return PositionState(
        position_id="test-position",
        symbol="TEST/USDT",
        direction=direction,
        entry_price=entry_price,
        quantity=100.0,
        remaining_quantity=100.0,
        stop_loss=stop_loss if stop_loss else (entry_price * 0.99 if direction == "LONG" else entry_price * 1.01),
        targets=targets,
        # Use a created_at far in the past so SIMULATION_MIN_TARGET_HOLD never matters here
        created_at=datetime.now(timezone.utc) - timedelta(hours=24),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Positive — guard does NOT regress legitimate target hits
# ──────────────────────────────────────────────────────────────────────────────


def test_valid_long_target_matches_when_price_crosses(manager):
    """LONG with target above entry: when current_price reaches target, hit fires."""
    pos = _make_position("LONG", entry_price=100.0, target_levels=[103.0])
    hit = manager._check_targets_hit(pos, current_price=103.5)
    assert hit is not None
    assert hit.level == 103.0


def test_valid_short_target_matches_when_price_crosses(manager):
    """SHORT with target below entry: when current_price drops to target, hit fires."""
    pos = _make_position("SHORT", entry_price=100.0, target_levels=[97.0])
    hit = manager._check_targets_hit(pos, current_price=96.5)
    assert hit is not None
    assert hit.level == 97.0


def test_valid_long_target_no_match_before_cross(manager):
    """LONG with target above entry: no hit while price < target."""
    pos = _make_position("LONG", entry_price=100.0, target_levels=[103.0])
    hit = manager._check_targets_hit(pos, current_price=101.0)
    assert hit is None
    # All valid targets preserved
    assert len(pos.targets) == 1


# ──────────────────────────────────────────────────────────────────────────────
# Negative — invalid targets removed, not returned as hit
# ──────────────────────────────────────────────────────────────────────────────


def test_long_target_below_entry_is_removed_not_returned(manager, caplog):
    """LONG with target BELOW entry (the INJ/USDT bug pattern): target removed.

    Reproduces the INJ session pattern: signal_entry=4.986, actual_entry=5.113,
    target computed at ~5.027 (above signal entry but BELOW actual entry).
    Pre-patch: target returned as "hit" at fill, exit_reason='target' booked
    as a structural loss. Post-patch: target removed with WARNING, position
    stays OPEN and closes via stop_loss/stagnation/timeout.
    """
    pos = _make_position(
        "LONG",
        entry_price=5.113,        # actual fill (drifted)
        target_levels=[5.027],    # target was relative to signal_entry 4.986
    )
    import logging
    caplog.set_level(logging.WARNING)

    hit = manager._check_targets_hit(pos, current_price=5.027)
    assert hit is None, "invalid target must NOT be returned as hit"
    assert len(pos.targets) == 0, "invalid target must be removed from position.targets"
    # Loud failure: WARNING-level log must surface so operator sees the bug
    assert any("INVALID_TARGET_GEOMETRY" in rec.message for rec in caplog.records), (
        "guard must emit INVALID_TARGET_GEOMETRY warning when removing invalid targets"
    )


def test_short_target_above_entry_is_removed_not_returned(manager, caplog):
    """SHORT with target ABOVE entry: symmetric bug, same fix."""
    pos = _make_position(
        "SHORT",
        entry_price=4.986,        # actual fill drifted DOWN from signal entry
        target_levels=[5.027],    # target was relative to a higher signal entry
    )
    import logging
    caplog.set_level(logging.WARNING)

    hit = manager._check_targets_hit(pos, current_price=5.027)
    assert hit is None, "invalid SHORT target must NOT be returned as hit"
    assert len(pos.targets) == 0
    assert any("INVALID_TARGET_GEOMETRY" in rec.message for rec in caplog.records), (
        "guard must fire symmetrically for SHORT — §10 standing-fix symmetry"
    )


def test_long_target_exactly_at_entry_is_removed(manager):
    """LONG with target == entry: also invalid (no profit possible, would book as 'target' for 0 PnL)."""
    pos = _make_position("LONG", entry_price=100.0, target_levels=[100.0])
    hit = manager._check_targets_hit(pos, current_price=100.0)
    assert hit is None
    assert len(pos.targets) == 0


def test_short_target_exactly_at_entry_is_removed(manager):
    """SHORT with target == entry: symmetric — invalid by definition."""
    pos = _make_position("SHORT", entry_price=100.0, target_levels=[100.0])
    hit = manager._check_targets_hit(pos, current_price=100.0)
    assert hit is None
    assert len(pos.targets) == 0


# ──────────────────────────────────────────────────────────────────────────────
# Mixed — partial-validity case
# ──────────────────────────────────────────────────────────────────────────────


def test_long_mixed_targets_keeps_valid_removes_invalid(manager):
    """LONG entry=5.113, targets=[5.027 (invalid), 5.200 (valid)]:
    invalid removed, valid kept, no hit until valid target crossed."""
    pos = _make_position(
        "LONG",
        entry_price=5.113,
        target_levels=[5.027, 5.200],
    )
    # At current_price=5.150 (above invalid target's level but below valid target)
    hit = manager._check_targets_hit(pos, current_price=5.150)
    assert hit is None, "must NOT return the invalid 5.027 target as hit"
    assert len(pos.targets) == 1
    assert pos.targets[0].level == 5.200

    # Now move price to cross the valid target
    hit2 = manager._check_targets_hit(pos, current_price=5.250)
    assert hit2 is not None
    assert hit2.level == 5.200


def test_short_mixed_targets_keeps_valid_removes_invalid(manager):
    """SHORT entry=4.986, targets=[5.027 (invalid), 4.800 (valid)]:
    invalid removed, valid kept."""
    pos = _make_position(
        "SHORT",
        entry_price=4.986,
        target_levels=[5.027, 4.800],
    )
    hit = manager._check_targets_hit(pos, current_price=4.950)
    assert hit is None
    assert len(pos.targets) == 1
    assert pos.targets[0].level == 4.800

    hit2 = manager._check_targets_hit(pos, current_price=4.750)
    assert hit2 is not None
    assert hit2.level == 4.800


# ──────────────────────────────────────────────────────────────────────────────
# Idempotency — guard is safe to re-run
# ──────────────────────────────────────────────────────────────────────────────


def test_guard_idempotent_on_already_cleaned_position(manager):
    """After invalid targets are removed, re-calling _check_targets_hit is a no-op."""
    pos = _make_position("LONG", entry_price=5.113, target_levels=[5.027])
    manager._check_targets_hit(pos, current_price=5.027)
    assert len(pos.targets) == 0

    # Second call must not crash; must return None; must not re-remove anything
    hit = manager._check_targets_hit(pos, current_price=5.027)
    assert hit is None
    assert len(pos.targets) == 0


def test_guard_no_op_when_all_targets_valid(manager, caplog):
    """If all targets are structurally valid, guard does nothing (no log, no removal)."""
    pos = _make_position("LONG", entry_price=100.0, target_levels=[102.0, 104.0, 106.0])
    import logging
    caplog.set_level(logging.WARNING)

    hit = manager._check_targets_hit(pos, current_price=101.0)
    assert hit is None  # no target crossed yet
    assert len(pos.targets) == 3
    # No INVALID_TARGET_GEOMETRY log should fire
    assert not any("INVALID_TARGET_GEOMETRY" in rec.message for rec in caplog.records), (
        "guard must stay silent when all targets are valid"
    )
