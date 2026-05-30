"""
Regression for hot-path audit bug #9 (3_CORRECTNESS): in calculate_confluence_score,
the sweep-discount block reassigned the regime-derived `htf_trend` PARAMETER to the
swing-structure trend (looping 1D/4H swing_structure). That clobbered value persisted
and was the value read at the HTF Alignment sub-score (`_score_htf_alignment_incremental`,
~scorer.py:2803). So whenever sweep_score>30 and swing_structure existed, HTF Alignment
was scored against the swing-structure trend instead of the regime trend the caller
passed — silently sourcing a 35%-of-HTF-Composite sub-score from the wrong input.

Fix: the discount now uses a LOCAL `swing_htf_trend` (it legitimately keys off swing
structure) and leaves the `htf_trend` parameter intact for the downstream alignment call.

See backend/diagnostics/decisions/2026-05-29__hotpath-robustness-audit.md (bug #9).
Per CLAUDE.md §11, §14 rubric 4 (negative+positive), §16 rubric 12 (LONG/SHORT symmetry).
"""

from __future__ import annotations

from unittest.mock import patch

from backend.strategy.confluence import scorer as scorer_mod
from backend.strategy.confluence.scorer import calculate_confluence_score
from backend.shared.models.smc import SMCSnapshot
from backend.shared.models.indicators import IndicatorSet, IndicatorSnapshot
from backend.shared.config.defaults import ScanConfig


def _indicators() -> IndicatorSet:
    snap = IndicatorSnapshot(
        rsi=50.0, stoch_rsi=50.0, bb_upper=102.0, bb_middle=100.0, bb_lower=98.0,
        atr=2.0, volume_spike=False, mfi=50.0, obv=0.0,
    )
    return IndicatorSet(by_timeframe={"4H": snap})


def _capture_htf_trend(direction: str, htf_trend_param: str, swing_trend: str) -> dict:
    """Run calculate_confluence_score through the sweep-discount path and capture the
    htf_trend value that reaches _score_htf_alignment_incremental."""
    smc = SMCSnapshot(
        order_blocks=[], fvgs=[], structural_breaks=[], liquidity_sweeps=[],
        swing_structure={"4h": {"trend": swing_trend}},
    )
    captured: dict = {}

    def _fake_align(htf_trend, direction, htf_indicators=None, indicator_set=None):
        captured["htf_trend"] = htf_trend
        return {"score": 100.0, "rationale": "test"}

    with patch.object(
        scorer_mod, "_score_liquidity_sweeps_incremental",
        return_value={"score": 50.0, "rationale": "sweep"},  # > 30 → triggers the block
    ), patch.object(scorer_mod, "_score_htf_alignment_incremental", side_effect=_fake_align):
        calculate_confluence_score(
            smc_snapshot=smc, indicators=_indicators(), config=ScanConfig(),
            direction=direction, htf_trend=htf_trend_param,
        )
    return captured


def test_param_not_clobbered_long_discount():
    """LONG + bearish swing → discount triggers, but HTF Alignment must score against
    the regime parameter ('bullish'), not the swing trend ('bearish')."""
    captured = _capture_htf_trend("LONG", htf_trend_param="bullish", swing_trend="bearish")
    assert captured.get("htf_trend") == "bullish"  # was "bearish" (swing) before the fix


def test_param_not_clobbered_short_discount():
    """SHORT mirror (§16 rubric 12): SHORT + bullish swing → discount triggers; HTF
    Alignment must use the regime parameter ('bearish')."""
    captured = _capture_htf_trend("SHORT", htf_trend_param="bearish", swing_trend="bullish")
    assert captured.get("htf_trend") == "bearish"  # was "bullish" (swing) before the fix


def test_param_not_clobbered_when_no_discount():
    """Even when the discount does NOT apply (neutral swing), the block still ran and
    pre-fix clobbered the parameter to 'neutral'. The parameter must survive."""
    captured = _capture_htf_trend("LONG", htf_trend_param="bullish", swing_trend="neutral")
    assert captured.get("htf_trend") == "bullish"  # was "neutral" (clobbered) before the fix
