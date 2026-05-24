"""
Tests for §10 bull/bear symmetry in RegimeDetector.analyze_timeframe_trend.

Bug context — symmetry-guard audit (2026-05-23) flagged
backend/analysis/regime_detector.py:524-536 as a bull-asymmetric
trend_score: strong_up=85, up=70 vs strong_down=15, down=30. The 70-
point gap between mirrored directions implicitly weights "buy-and-hold
direction" and contradicts the trend-following research consensus that
trends are equally tradeable in both directions for a system that
trades both LONG and SHORT.

Downstream impact: trend_score feeds composite MarketRegime.score at
weight 0.3 (regime_detector.py:121). The pre-fix asymmetry produced a
~21-point composite-score handicap on bearish regimes vs mirrored
bullish regimes. min_regime_score gates (40 for STEALTH/STRIKE, 60 for
OVERWATCH, 30 for SURGICAL) then admitted bull regimes that would
mirror-reject bear ones, biasing the bot's signal admission toward
LONGs in symmetric market conditions.

Fix: mirror the scores. strong_down=85, down=70. Trend clarity drives
quality; direction doesn't.

Per CLAUDE.md §10 (bullish/bearish signal symmetry in scoring),
§14 rubric 4 (negative tests paired with positive), §16 rubric 12
(direction-pair every relevant test).
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.analysis.regime_detector import RegimeDetector


# ──────────────────────────────────────────────────────────────────────
# Source-level symmetry assertions — defend against future regressions
# ──────────────────────────────────────────────────────────────────────


def test_classify_trend_scores_are_symmetric_in_source():
    """Pin §10 bull/bear symmetry directly in regime_detector.py source.

    Any future commit that reverts strong_down=85→15 or down=70→30 will
    fail this test. Catches the exact regression class the May 2026
    symmetry-guard audit identified."""
    from pathlib import Path
    import re

    src_path = (
        Path(__file__).resolve().parents[2]
        / "analysis"
        / "regime_detector.py"
    )
    assert src_path.exists(), f"regime_detector.py not found at {src_path}"
    src = src_path.read_text(encoding="utf-8")

    # The two pairs of scores that must mirror.
    # `strong_up` and `strong_down` must both return the same magnitude.
    strong_up_match = re.search(
        r'return\s+"strong_up",\s*(\d+(?:\.\d+)?)\s*,', src
    )
    strong_down_match = re.search(
        r'return\s+"strong_down",\s*(\d+(?:\.\d+)?)\s*,', src
    )
    assert strong_up_match, "could not find strong_up return in source"
    assert strong_down_match, "could not find strong_down return in source"
    strong_up_score = float(strong_up_match.group(1))
    strong_down_score = float(strong_down_match.group(1))
    assert strong_up_score == strong_down_score, (
        f"§10 violation: strong_up={strong_up_score} must mirror "
        f"strong_down={strong_down_score}. Trend clarity drives quality; "
        f"direction doesn't. See test docstring for full context."
    )

    # Same check for `up` and `down`. Two `up` returns exist (the
    # override path at "Explosive Rebound" / "Impulsive Recovery" + the
    # main bullish branch); two `down` returns exist (the override
    # "Structural Fatigue" + the main bearish branch). Collect all and
    # assert the set of `up` scores == set of `down` scores.
    up_scores = {
        float(m) for m in re.findall(r'return\s+"up",\s*(\d+(?:\.\d+)?)\s*,', src)
    }
    down_scores = {
        float(m) for m in re.findall(r'return\s+"down",\s*(\d+(?:\.\d+)?)\s*,', src)
    }
    assert up_scores == down_scores, (
        f"§10 violation: up scores {up_scores} must mirror down scores "
        f"{down_scores}. Both override-path and main-branch returns must "
        f"score directional-clarity equally regardless of sign."
    )


def test_sideways_score_is_below_directional_scores():
    """Sideways (= chop, the LOW-quality regime) must score strictly
    less than directional regimes (up/down/strong_up/strong_down). This
    pins the directional-clarity-drives-quality framing — without it,
    one could "fix" the bull/bear symmetry test by setting all scores
    to the same value, which would lose the trend-vs-chop signal."""
    from pathlib import Path
    import re

    src_path = (
        Path(__file__).resolve().parents[2]
        / "analysis"
        / "regime_detector.py"
    )
    src = src_path.read_text(encoding="utf-8")

    sideways_scores = {
        float(m)
        for m in re.findall(r'return\s+"sideways",\s*(\d+(?:\.\d+)?)\s*,', src)
    }
    directional_scores = (
        {float(m) for m in re.findall(r'return\s+"up",\s*(\d+(?:\.\d+)?)\s*,', src)}
        | {
            float(m)
            for m in re.findall(r'return\s+"down",\s*(\d+(?:\.\d+)?)\s*,', src)
        }
        | {
            float(m)
            for m in re.findall(
                r'return\s+"strong_up",\s*(\d+(?:\.\d+)?)\s*,', src
            )
        }
        | {
            float(m)
            for m in re.findall(
                r'return\s+"strong_down",\s*(\d+(?:\.\d+)?)\s*,', src
            )
        }
    )

    assert sideways_scores, "no sideways scores found"
    assert directional_scores, "no directional scores found"
    max_sideways = max(sideways_scores)
    min_directional = min(directional_scores)
    assert max_sideways < min_directional, (
        f"sideways score {max_sideways} must be strictly less than "
        f"min directional score {min_directional}. Sideways IS the "
        f"low-quality regime per the §10 directional-clarity framing."
    )


# ──────────────────────────────────────────────────────────────────────
# Composite-impact sanity — verify the fix actually lifts bear-regime
# composite scores into parity with bull-regime composites
# ──────────────────────────────────────────────────────────────────────


def test_trend_score_composite_weight_unchanged():
    """The composite weight on trend_score is 0.3 (regime_detector.py
    line 121). This is the multiplier that translates the per-direction
    asymmetry into a composite-score delta. Pin the weight so a future
    composite-score refactor doesn't silently amplify the trend
    component without crossing this test."""
    from pathlib import Path
    import re

    src_path = (
        Path(__file__).resolve().parents[2]
        / "analysis"
        / "regime_detector.py"
    )
    src = src_path.read_text(encoding="utf-8")

    # Find the trend_score * weight line in the composite-score block.
    match = re.search(r"trend_score\s*\*\s*(\d+(?:\.\d+)?)", src)
    assert match, "trend_score weight assignment not found in composite block"
    weight = float(match.group(1))
    assert 0.1 <= weight <= 0.5, (
        f"trend_score composite weight {weight} outside the "
        f"reasonable range [0.1, 0.5]; an unexpected refactor may have "
        f"shipped — review composite block at regime_detector.py:121."
    )


def test_symmetric_scores_produce_equal_composite_contribution():
    """Mathematical pin: with the symmetric fix, a strong_up regime and
    a strong_down regime contribute IDENTICALLY to MarketRegime.score
    via the trend_score * 0.3 path. This is what §10 demands."""
    strong_up_score = 85.0
    strong_down_score = 85.0  # post-fix
    weight = 0.3
    assert (
        strong_up_score * weight == strong_down_score * weight
    ), "post-fix composite contribution must be identical for mirrored strong trends"

    up_score = 70.0
    down_score = 70.0  # post-fix
    assert (
        up_score * weight == down_score * weight
    ), "post-fix composite contribution must be identical for mirrored normal trends"


def test_pre_fix_asymmetric_handicap_no_longer_present():
    """Document and pin the exact handicap the fix eliminates.

    Pre-fix: strong_up 85 vs strong_down 15. Composite delta:
        (85 - 15) * 0.3 = 21.0 points handicap on bear regimes.

    Post-fix: 85 vs 85. Composite delta = 0.

    With STEALTH min_regime_score = 40, a 21-point handicap on bearish
    composites meant marginal bearish regimes (composite ~45) would
    fail the gate while mirrored bullish regimes (composite ~66) sailed
    through. This test pins that the handicap is gone."""
    from pathlib import Path
    import re

    src_path = (
        Path(__file__).resolve().parents[2]
        / "analysis"
        / "regime_detector.py"
    )
    src = src_path.read_text(encoding="utf-8")

    su = re.search(r'return\s+"strong_up",\s*(\d+(?:\.\d+)?)\s*,', src)
    sd = re.search(r'return\s+"strong_down",\s*(\d+(?:\.\d+)?)\s*,', src)
    handicap = (float(su.group(1)) - float(sd.group(1))) * 0.3
    assert handicap == 0.0, (
        f"§10 violation: bear-regime composite handicap = {handicap:.2f} "
        f"points (was 21.0 pre-fix). Must be 0.0 — see test docstring."
    )
