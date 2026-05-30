"""
Regression for hot-path audit bug #10 (3_CORRECTNESS): _filter_targets_by_opposing_structure
kept opposing order blocks with `freshness_score > 0.5`, but freshness_score is on a
0-100 scale (order_blocks.calculate_freshness returns freshness * 100; siblings at
scorer.py:155/995 use 50.0). So `> 0.5` admitted essentially EVERY opposing OB (anything
>0.5% fresh), over-blocking valid take-profit targets, truncating the ladder toward the
nearest target, and biasing realized R:R down.

Fix: threshold corrected to `> 50.0` — only STRONG opposing structures block a TP, matching
the comment intent ("strong opposing structures") and the sibling 0-100 checks.

See backend/diagnostics/decisions/2026-05-29__hotpath-robustness-audit.md (bug #10).
Per CLAUDE.md §14 rubric 4 (negative+positive), §16 rubric 12 (LONG/SHORT symmetry).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from backend.shared.models.smc import SMCSnapshot, OrderBlock
from backend.shared.models.planner import Target
from backend.strategy.planner.risk_engine import _filter_targets_by_opposing_structure

_ATR = 2.0  # proximity_threshold = 0.5*ATR = 1.0


def _ob(direction: str, low: float, high: float, freshness: float) -> OrderBlock:
    return OrderBlock(
        timeframe="4H", direction=direction, high=high, low=low,
        timestamp=datetime.utcnow() - timedelta(days=1),
        displacement_strength=50.0, mitigation_level=0.1, freshness_score=freshness,
    )


def _t(level: float) -> Target:
    return Target(level=level, rationale="t", percentage=50.0, label="TP", rr_ratio=1.5, weight=1.0)


def _snap(obs) -> SMCSnapshot:
    return SMCSnapshot(order_blocks=obs, fvgs=[], structural_breaks=[], liquidity_sweeps=[])


# ── LONG (opposing = bearish OB) ───────────────────────────────────────────────


def test_mid_fresh_opposing_ob_does_not_block_long():
    """A 30%-fresh bearish OB over a TP must NOT block it (below the 50 threshold).
    Pre-fix (>0.5) it qualified and stripped the target."""
    snap = _snap([_ob("bearish", 104.0, 106.0, 30.0)])
    out = _filter_targets_by_opposing_structure([_t(105.0), _t(110.0)], snap, is_bullish=True, atr=_ATR)
    assert sorted(t.level for t in out) == [105.0, 110.0]  # 105 retained


def test_strong_opposing_ob_still_blocks_long():
    """An 80%-fresh bearish OB over a TP still blocks it (no regression — strong
    opposing structure should filter)."""
    snap = _snap([_ob("bearish", 104.0, 106.0, 80.0)])
    out = _filter_targets_by_opposing_structure([_t(105.0), _t(110.0)], snap, is_bullish=True, atr=_ATR)
    assert [t.level for t in out] == [110.0]  # 105 blocked, 110 kept


# ── SHORT mirror (opposing = bullish OB) ───────────────────────────────────────


def test_mid_fresh_opposing_ob_does_not_block_short():
    snap = _snap([_ob("bullish", 94.0, 96.0, 30.0)])
    out = _filter_targets_by_opposing_structure([_t(95.0), _t(90.0)], snap, is_bullish=False, atr=_ATR)
    assert sorted(t.level for t in out) == [90.0, 95.0]  # 95 retained


def test_strong_opposing_ob_still_blocks_short():
    snap = _snap([_ob("bullish", 94.0, 96.0, 80.0)])
    out = _filter_targets_by_opposing_structure([_t(95.0), _t(90.0)], snap, is_bullish=False, atr=_ATR)
    assert [t.level for t in out] == [90.0]  # 95 blocked, 90 kept
