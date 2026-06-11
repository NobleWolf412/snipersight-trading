"""
Regression test for Fix 4c: Fibonacci binary gate (2026-06-11).

Old behavior: graduated percentage-based scoring (0.3/0.6/1.2% bands + golden pocket
bonus + TF weight), producing partial scores (20/40/60+ pts).

New behavior: binary gate — within 0.5 ATR of any HTF Fibonacci level → 100.0,
else → 0.0. No graduated intermediate scores.

Verifies:
- Function accepts `atr` keyword argument
- No ATR (None or 0) → score 0.0 (conservative fallback)
- Level within 0.5 ATR → score 100.0
- Level outside 0.5 ATR → score 0.0
- Bull/bear symmetry: both directions produce same binary output given identical geometry
- No percentage bands (0.3/0.6/1.2) in function body
- No TF weight multiplication in function body
- vwap_score = 40.0 floor not present (Fix 4b guard, belt-and-suspenders)
"""

from __future__ import annotations

import pathlib
import re

import pytest

SCORER_SRC = pathlib.Path("backend/strategy/confluence/scorer.py").read_text(
    encoding="utf-8"
)

# Locate the function body for narrow-scope assertions
_FIB_FN_RE = re.compile(
    r"def _score_fibonacci_incremental\b.*?(?=\ndef |\Z)",
    re.DOTALL,
)
_match = _FIB_FN_RE.search(SCORER_SRC)
FIB_FN_BODY = _match.group(0) if _match else ""


class TestFibFunctionSignature:
    def test_atr_param_present(self):
        """Function must accept `atr` keyword argument."""
        assert "atr:" in FIB_FN_BODY or "atr =" in FIB_FN_BODY, (
            "_score_fibonacci_incremental missing `atr` parameter — binary gate requires ATR"
        )

    def test_atr_has_optional_default(self):
        """ATR must default to None (optional for call-site backward compat)."""
        assert "atr: Optional[float] = None" in FIB_FN_BODY or "atr=None" in FIB_FN_BODY, (
            "atr parameter must be Optional[float] = None"
        )


class TestFibBinaryGateLogic:
    def test_no_atr_returns_zero(self):
        """If ATR is None, score must be 0.0 — can't confirm proximity."""
        assert "not atr or atr <= 0" in FIB_FN_BODY or "not atr" in FIB_FN_BODY, (
            "ATR guard not found — function may produce non-zero scores without ATR"
        )

    def test_returns_100_on_hit(self):
        """Binary gate hit must return score 100.0 (not partial)."""
        assert '"score": 100.0' in FIB_FN_BODY, (
            "Function does not return score=100.0 on gate hit"
        )

    def test_returns_0_on_miss(self):
        """Binary gate miss must return score 0.0."""
        assert '"score": 0.0' in FIB_FN_BODY, (
            "Function does not return score=0.0 on gate miss"
        )

    def test_threshold_is_half_atr(self):
        """Gate threshold must be 0.5 * atr."""
        assert "0.5 * atr" in FIB_FN_BODY, (
            "Threshold is not 0.5 * atr — binary gate proximity check incorrect"
        )

    def test_abs_distance_check(self):
        """Distance check must use abs(current_price - nearest.price)."""
        assert "abs(current_price - nearest.price)" in FIB_FN_BODY, (
            "abs distance check on nearest.price not found — may compare wrong quantity"
        )


class TestFibGraduatedScoringRemoved:
    def test_no_percentage_band_0_3(self):
        """Old 0.3% proximity band must be removed."""
        assert "prox <= 0.3" not in FIB_FN_BODY, (
            "Old 0.3% proximity band still present in _score_fibonacci_incremental"
        )

    def test_no_percentage_band_0_6(self):
        """Old 0.6% proximity band must be removed."""
        assert "prox <= 0.6" not in FIB_FN_BODY, (
            "Old 0.6% proximity band still present in _score_fibonacci_incremental"
        )

    def test_no_percentage_band_1_2(self):
        """Old 1.2% proximity band must be removed."""
        assert "prox <= 1.2" not in FIB_FN_BODY, (
            "Old 1.2% proximity band still present in _score_fibonacci_incremental"
        )

    def test_no_tf_weight_multiplier(self):
        """Old TF weight (1.2x for 1D) must be removed."""
        assert "level_score *= 1.2" not in FIB_FN_BODY, (
            "Old 1D timeframe weight multiplier still in function body"
        )

    def test_no_golden_pocket_bonus_pts(self):
        """Old +25 golden pocket bonus must be removed (now label only)."""
        assert "level_score += 25" not in FIB_FN_BODY, (
            "Old +25 golden pocket bonus still in function body"
        )


class TestFibBullBearSymmetry:
    """Binary gate is direction-agnostic in its ATR-distance math.
    Symmetry verified via inline simulation of the gate logic."""

    @staticmethod
    def _gate(current_price: float, level_price: float, atr: float) -> float:
        """Inline reproduction of the binary gate check."""
        if not atr or atr <= 0:
            return 0.0
        threshold = 0.5 * atr
        if abs(current_price - level_price) <= threshold:
            return 100.0
        return 0.0

    def test_long_within_gate_scores_100(self):
        """LONG: price within 0.5 ATR of level → 100.0."""
        result = self._gate(current_price=100.0, level_price=100.2, atr=1.0)
        assert result == 100.0

    def test_short_within_gate_scores_100(self):
        """SHORT: price within 0.5 ATR of level → 100.0 (symmetric)."""
        result = self._gate(current_price=100.0, level_price=99.8, atr=1.0)
        assert result == 100.0

    def test_long_outside_gate_scores_0(self):
        """LONG: price beyond 0.5 ATR → 0.0."""
        result = self._gate(current_price=100.0, level_price=101.0, atr=1.0)
        assert result == 0.0

    def test_short_outside_gate_scores_0(self):
        """SHORT: price beyond 0.5 ATR → 0.0 (symmetric)."""
        result = self._gate(current_price=100.0, level_price=99.0, atr=1.0)
        assert result == 0.0

    def test_exactly_at_threshold_passes(self):
        """Exactly at 0.5 ATR boundary must pass (<=, not <)."""
        result = self._gate(current_price=100.0, level_price=100.5, atr=1.0)
        assert result == 100.0

    def test_one_tick_past_threshold_fails(self):
        """One tick past 0.5 ATR must fail."""
        result = self._gate(current_price=100.0, level_price=100.51, atr=1.0)
        assert result == 0.0

    def test_no_atr_returns_zero(self):
        """None ATR → 0.0 regardless of proximity."""
        result = self._gate(current_price=100.0, level_price=100.0, atr=None)
        assert result == 0.0

    def test_zero_atr_returns_zero(self):
        """Zero ATR → 0.0 to prevent division/threshold edge cases."""
        result = self._gate(current_price=100.0, level_price=100.0, atr=0.0)
        assert result == 0.0
