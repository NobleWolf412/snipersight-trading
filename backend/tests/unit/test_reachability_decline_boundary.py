"""
Regression for the 2026-06-02 reachability-clamp over-decline re-tune (Stage 1, Lever B).

The TP1 reachability clamp declines a plan when `ceiling / stop_atr < target_min_rr_after_clip`.
At the old default min_rr_after_clip=1.2 (ceiling 1.3) the decline boundary was 1.3/1.2 = 1.083 ATR
— so ANY stop wider than ~1.08 ATR was declined, killing the structural-stop cohort (median ~1.5 ATR).
Stage 1 lowers the default to 1.0, moving the boundary to 1.3/1.0 = 1.3 ATR WITHOUT raising the
reachability ceiling (so TP1 stays clamped to a genuinely-reachable 1.3 ATR — anti-stagnation preserved).

These tests pin the boundary move: a 1.2-ATR stop is DECLINED at min_rr_after_clip=1.2 but
CLAMP-ACCEPTED at 1.0. §15 baseline: decisions/2026-06-02__fix-design__reachability-clamp-overdecline.md.
Per CLAUDE.md §14 rubric 4 (negative+positive), §16 rubric 12 (LONG/SHORT symmetry).
"""

from __future__ import annotations

import pytest

from backend.strategy.planner.risk_engine import _calculate_targets, ReachabilityDecline
from backend.shared.models.planner import EntryZone, StopLoss
from backend.shared.models.smc import SMCSnapshot
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.planner_config import PlannerConfig


def _call(min_rr_after_clip: float, is_bullish: bool = True):
    """Drive _calculate_targets with a ~1.2-ATR stop (atr=1.0) and TP1 ladder 1.5R so the
    raw TP1 (1.8 ATR) exceeds the 1.3-ATR ceiling → clamp path → clamped_rr = 1.3/1.2 = 1.083."""
    if is_bullish:
        ez = EntryZone(near_entry=100.0, far_entry=99.9, rationale="t")
        sl = StopLoss(level=98.8, distance_atr=1.2, rationale="t")  # risk_distance 1.2, atr 1.0
    else:
        ez = EntryZone(near_entry=100.0, far_entry=100.1, rationale="t")
        sl = StopLoss(level=101.2, distance_atr=1.2, rationale="t")
    pcfg = PlannerConfig()  # ceiling 1.3
    pcfg.target_min_rr_after_clip = min_rr_after_clip
    pcfg.target_rr_ladder = [1.5, 2.5, 4.0]
    return _calculate_targets(
        is_bullish=is_bullish, entry_zone=ez, stop_loss=sl,
        smc_snapshot=SMCSnapshot([], [], [], []), atr=1.0, config=ScanConfig(),
        planner_cfg=pcfg, setup_archetype="TREND_OB_PULLBACK", regime_label="normal",
    )


def test_new_default_is_one():
    """The shipped default is now 1.0 (Stage 1)."""
    assert PlannerConfig().target_min_rr_after_clip == 1.0


def test_stop_1_2atr_declined_at_old_min_rr_long():
    """Negative (old behavior): a 1.2-ATR stop is DECLINED at min_rr_after_clip=1.2
    (boundary 1.083 ATR) — the over-decline this re-tune fixes."""
    with pytest.raises(ReachabilityDecline):
        _call(1.2, is_bullish=True)


def test_stop_1_2atr_accepted_at_new_min_rr_long():
    """Positive (new behavior): the same 1.2-ATR stop is clamp-accepted at 1.0
    (boundary 1.3 ATR) — must NOT raise ReachabilityDecline."""
    try:
        _call(1.0, is_bullish=True)
    except ReachabilityDecline:
        pytest.fail("1.2-ATR stop should be clamp-accepted at min_rr_after_clip=1.0")


def test_stop_1_2atr_declined_at_old_min_rr_short():
    """SHORT mirror (§16 rubric 12)."""
    with pytest.raises(ReachabilityDecline):
        _call(1.2, is_bullish=False)


def test_stop_1_2atr_accepted_at_new_min_rr_short():
    try:
        _call(1.0, is_bullish=False)
    except ReachabilityDecline:
        pytest.fail("1.2-ATR stop (SHORT) should be clamp-accepted at min_rr_after_clip=1.0")
