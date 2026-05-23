"""
FIX-04 — evaluate_htf_momentum_gate default fade_threshold_rsi symmetry.

Per CLAUDE.md §10 standing fix: RSI fade thresholds standardized to 70/30. The
previous default in scorer.py:1243 was 75.0 → produced asymmetric (25/75) for
LONG/SHORT climax detection on unknown mode_name/profile pairs. All four real
modes (overwatch, stealth, surgical, strike) explicitly override to 70.0, but
fall-through to default was a silent §10 violation (§11 silent-bug class).

Fix:
  - Default fade_threshold_rsi changed 75.0 → 70.0
  - Added explicit `else:` branch with logger.warning on unknown mode/profile
    so a missing branch fails loudly per §11 rather than silently producing
    asymmetric thresholds.

Coverage:
  - Default value enforced for unknown mode (positive — §10 compliance)
  - All four real modes still resolve to 70.0 (regression — no behavior change)
  - Loud-warning fires when neither mode_name nor profile match
  - Symmetry: LONG climax @ RSI 26 mirrors SHORT climax @ RSI 74 (both trigger)
  - Boundary: RSI 30 does NOT trigger LONG climax (strict-less);
              RSI 70 does NOT trigger SHORT climax (strict-greater)
  - Negative: RSI 50 triggers neither direction (no climax)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import pytest

from backend.shared.models.indicators import IndicatorSet, IndicatorSnapshot
from backend.strategy.confluence.scorer import evaluate_htf_momentum_gate


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class _ModeConfig:
    """Minimal ScanConfig-shaped object for the function under test."""

    name: str = ""
    profile: str = ""


def _make_indicators(rsi: float, adx: float = 35.0, tf: str = "4h") -> IndicatorSet:
    """Indicator set with one timeframe; adx >= 30 ⇒ momentum_state='strong'."""
    snap = IndicatorSnapshot(
        rsi=rsi,
        stoch_rsi=50.0,
        bb_upper=102.0,
        bb_middle=100.0,
        bb_lower=98.0,
        atr=2.0,
        volume_spike=False,
        mfi=50.0,
        obv=0.0,
        adx=adx,
    )
    return IndicatorSet(by_timeframe={tf: snap})


def _swing_structure(tf: str, trend: str) -> dict:
    return {tf: {"trend": trend}}


# ──────────────────────────────────────────────────────────────────────────────
# §10 compliance — default threshold is 70.0, not 75.0
# ──────────────────────────────────────────────────────────────────────────────


def test_default_threshold_is_70_for_unknown_mode_long_climax_at_rsi_29():
    """Unknown mode_name+profile must use default 70.0 → LONG climax triggers
    at RSI < 30. With default 75.0 (pre-fix), threshold = 25 → RSI 29 would
    NOT trigger climax → §10 violation."""
    cfg = _ModeConfig(name="unknown_mode", profile="unknown_profile")
    ind = _make_indicators(rsi=29.0)
    swing = _swing_structure("4h", "bearish")  # opposed to LONG

    result = evaluate_htf_momentum_gate(
        indicators=ind,
        direction="LONG",
        mode_config=cfg,
        swing_structure=swing,
    )

    assert result["allowed"] is True, "RSI 29 < 30 must qualify as climax under §10"
    assert "CLIMAX" in result.get("reason", ""), f"Expected CLIMAX, got: {result}"


def test_default_threshold_is_70_for_unknown_mode_short_climax_at_rsi_71():
    """Symmetric mirror: RSI 71 must trigger SHORT climax under §10 default."""
    cfg = _ModeConfig(name="unknown_mode", profile="unknown_profile")
    ind = _make_indicators(rsi=71.0)
    swing = _swing_structure("4h", "bullish")  # opposed to SHORT

    result = evaluate_htf_momentum_gate(
        indicators=ind,
        direction="SHORT",
        mode_config=cfg,
        swing_structure=swing,
    )

    assert result["allowed"] is True, "RSI 71 > 70 must qualify as climax under §10"
    assert "CLIMAX" in result.get("reason", ""), f"Expected CLIMAX, got: {result}"


# ──────────────────────────────────────────────────────────────────────────────
# Loud-failure — unknown mode emits warning (§11)
# ──────────────────────────────────────────────────────────────────────────────


def test_unknown_mode_emits_warning(caplog):
    """Unknown mode_name/profile must log a WARNING per §11 loud-failure."""
    cfg = _ModeConfig(name="ghost", profile="recon")  # both removed in §10
    ind = _make_indicators(rsi=50.0)
    swing = _swing_structure("4h", "neutral")

    # loguru → std logging via InterceptHandler is repo-wide; tap propagated logs
    with caplog.at_level(logging.WARNING):
        evaluate_htf_momentum_gate(
            indicators=ind,
            direction="LONG",
            mode_config=cfg,
            swing_structure=swing,
        )

    # The warning surfaces somewhere — exact handler binding can vary in CI,
    # so we check the loguru-captured records on the root logger or in caplog.
    # If both are empty, the warning was suppressed (bug).
    saw_warning = any(
        "unknown mode_name" in r.message and "ghost" in r.message
        for r in caplog.records
    )
    if not saw_warning:
        # Fallback: re-import loguru and use add() capture (loguru doesn't
        # propagate to std logging by default in all configurations).
        from loguru import logger as _logger
        captured = []
        sink_id = _logger.add(lambda m: captured.append(str(m)), level="WARNING")
        try:
            evaluate_htf_momentum_gate(
                indicators=ind,
                direction="LONG",
                mode_config=cfg,
                swing_structure=swing,
            )
        finally:
            _logger.remove(sink_id)
        saw_warning = any("unknown mode_name" in c and "ghost" in c for c in captured)

    assert saw_warning, "Loud warning must fire on unknown mode_name+profile"


# ──────────────────────────────────────────────────────────────────────────────
# Regression — four real modes still resolve to threshold 70.0
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "mode_name,profile,expected_tf",
    [
        ("overwatch", "macro_surveillance", "1d"),
        ("stealth", "stealth_balanced", "4h"),
        ("surgical", "precision", "1h"),
        ("strike", "intraday_aggressive", "1h"),
    ],
)
def test_four_real_modes_use_threshold_70_long(mode_name, profile, expected_tf):
    """Regression: each of the four real modes must continue to use threshold
    70.0 (LONG climax at RSI 29)."""
    cfg = _ModeConfig(name=mode_name, profile=profile)
    ind = _make_indicators(rsi=29.0, tf=expected_tf)
    swing = _swing_structure(expected_tf, "bearish")

    result = evaluate_htf_momentum_gate(
        indicators=ind,
        direction="LONG",
        mode_config=cfg,
        swing_structure=swing,
    )

    assert result["allowed"] is True, (
        f"{mode_name}/{profile}: RSI 29 < 30 must qualify as climax under §10"
    )


@pytest.mark.parametrize(
    "mode_name,profile,expected_tf",
    [
        ("overwatch", "macro_surveillance", "1d"),
        ("stealth", "stealth_balanced", "4h"),
        ("surgical", "precision", "1h"),
        ("strike", "intraday_aggressive", "1h"),
    ],
)
def test_four_real_modes_use_threshold_70_short(mode_name, profile, expected_tf):
    """Symmetric mirror: each of the four real modes must allow SHORT climax at
    RSI 71."""
    cfg = _ModeConfig(name=mode_name, profile=profile)
    ind = _make_indicators(rsi=71.0, tf=expected_tf)
    swing = _swing_structure(expected_tf, "bullish")

    result = evaluate_htf_momentum_gate(
        indicators=ind,
        direction="SHORT",
        mode_config=cfg,
        swing_structure=swing,
    )

    assert result["allowed"] is True, (
        f"{mode_name}/{profile}: RSI 71 > 70 must qualify as climax under §10"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Bull/bear symmetry — mirrored outcomes
# ──────────────────────────────────────────────────────────────────────────────


def test_long_at_rsi_26_mirrors_short_at_rsi_74():
    """Strict §10 symmetry: LONG climax at RSI 26 and SHORT climax at RSI 74
    must both return allowed=True with the same score_adjustment magnitude."""
    cfg = _ModeConfig(name="stealth", profile="stealth_balanced")

    long_ind = _make_indicators(rsi=26.0)
    long_swing = _swing_structure("4h", "bearish")
    long_result = evaluate_htf_momentum_gate(
        indicators=long_ind,
        direction="LONG",
        mode_config=cfg,
        swing_structure=long_swing,
    )

    short_ind = _make_indicators(rsi=74.0)
    short_swing = _swing_structure("4h", "bullish")
    short_result = evaluate_htf_momentum_gate(
        indicators=short_ind,
        direction="SHORT",
        mode_config=cfg,
        swing_structure=short_swing,
    )

    assert long_result["allowed"] == short_result["allowed"] == True
    assert long_result["score_adjustment"] == short_result["score_adjustment"], (
        f"Asymmetric climax bonus: LONG={long_result['score_adjustment']} "
        f"vs SHORT={short_result['score_adjustment']}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Boundary — strict-less / strict-greater, not <= / >=
# ──────────────────────────────────────────────────────────────────────────────


def test_long_climax_does_not_fire_at_exact_rsi_30():
    """RSI 30 is NOT < 30 → LONG climax must NOT fire (strict-less boundary)."""
    cfg = _ModeConfig(name="stealth", profile="stealth_balanced")
    ind = _make_indicators(rsi=30.0)
    swing = _swing_structure("4h", "bearish")

    result = evaluate_htf_momentum_gate(
        indicators=ind,
        direction="LONG",
        mode_config=cfg,
        swing_structure=swing,
    )

    # RSI 30 in strong-trend opposed setup → should NOT be climax; either
    # blocked or routed elsewhere — but reason must NOT contain CLIMAX.
    assert "CLIMAX" not in result.get("reason", ""), (
        f"RSI 30 must NOT trigger LONG climax (strict-less), got: {result}"
    )


def test_short_climax_does_not_fire_at_exact_rsi_70():
    """RSI 70 is NOT > 70 → SHORT climax must NOT fire (strict-greater)."""
    cfg = _ModeConfig(name="stealth", profile="stealth_balanced")
    ind = _make_indicators(rsi=70.0)
    swing = _swing_structure("4h", "bullish")

    result = evaluate_htf_momentum_gate(
        indicators=ind,
        direction="SHORT",
        mode_config=cfg,
        swing_structure=swing,
    )

    assert "CLIMAX" not in result.get("reason", ""), (
        f"RSI 70 must NOT trigger SHORT climax (strict-greater), got: {result}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Negative — RSI 50 triggers neither direction
# ──────────────────────────────────────────────────────────────────────────────


def test_rsi_50_no_climax_long():
    """RSI 50 is mid-range → never qualifies as LONG climax."""
    cfg = _ModeConfig(name="stealth", profile="stealth_balanced")
    ind = _make_indicators(rsi=50.0)
    swing = _swing_structure("4h", "bearish")

    result = evaluate_htf_momentum_gate(
        indicators=ind,
        direction="LONG",
        mode_config=cfg,
        swing_structure=swing,
    )

    assert "CLIMAX" not in result.get("reason", "")


def test_rsi_50_no_climax_short():
    """Symmetric mirror: RSI 50 → never SHORT climax."""
    cfg = _ModeConfig(name="stealth", profile="stealth_balanced")
    ind = _make_indicators(rsi=50.0)
    swing = _swing_structure("4h", "bullish")

    result = evaluate_htf_momentum_gate(
        indicators=ind,
        direction="SHORT",
        mode_config=cfg,
        swing_structure=swing,
    )

    assert "CLIMAX" not in result.get("reason", "")
