"""
Regression test for Fix 4e: weekly_stoch_rsi data source 1W → 1D (2026-06-11).

Includes functional tests that call the real evaluate_weekly_stoch_rsi_bonus() using
minimal IndicatorSet / IndicatorSnapshot objects.

Old behavior: evaluate_weekly_stoch_rsi_bonus() called _get_tf_indicators(indicators, "1W").
Weekly (1W) candles are often unavailable or several days stale, causing the bonus function
to silently return default=aligned=True and bonus=0.0 even when the daily StochRSI has
a clear cross signal.

New behavior: function uses "1D" timeframe, which is always populated and more responsive.
The weight key `weekly_stoch_rsi` and factor name "Weekly StochRSI Bonus" are unchanged
to avoid unnecessary cascade renames.

Verifies:
- Function body uses "1D", not "1W"
- "1W" not present in the function body (except in historical comment)
- Docstring updated to document the Fix 4e change
- Bull/bear symmetry: both directions produce correct output with same 1D input
"""

from __future__ import annotations

import pathlib
import re

import pytest

from backend.shared.models.indicators import IndicatorSet, IndicatorSnapshot
from backend.strategy.confluence.scorer import evaluate_weekly_stoch_rsi_bonus


def _make_snapshot(stoch_rsi_k: float = 50.0, stoch_rsi_k_prev: float = 50.0) -> IndicatorSnapshot:
    """Minimal IndicatorSnapshot with all required fields."""
    return IndicatorSnapshot(
        rsi=50.0,
        stoch_rsi=50.0,
        bb_upper=110.0,
        bb_middle=100.0,
        bb_lower=90.0,
        atr=1.0,
        volume_spike=False,
        stoch_rsi_k=stoch_rsi_k,
        stoch_rsi_k_prev=stoch_rsi_k_prev,
    )


def _make_indicator_set(**timeframes) -> IndicatorSet:
    """Create IndicatorSet from keyword args of {tf: stoch_rsi_k}."""
    return IndicatorSet(by_timeframe={
        tf: _make_snapshot(k_val) if isinstance(k_val, float) else _make_snapshot()
        for tf, k_val in timeframes.items()
    })

SCORER_SRC = pathlib.Path("backend/strategy/confluence/scorer.py").read_text(
    encoding="utf-8"
)

# Locate the evaluate_weekly_stoch_rsi_bonus function body
_FN_RE = re.compile(
    r"def evaluate_weekly_stoch_rsi_bonus\b.*?(?=\ndef |\Z)",
    re.DOTALL,
)
_match = _FN_RE.search(SCORER_SRC)
FN_BODY = _match.group(0) if _match else ""


class TestWeeklyStochRsiDataSource:
    def test_function_uses_1d_not_1w(self):
        """_get_tf_indicators must be called with '1D', not '1W'."""
        assert '_get_tf_indicators(indicators, "1D")' in FN_BODY, (
            "evaluate_weekly_stoch_rsi_bonus still uses '1W' as data source — "
            "Fix 4e requires '1D'"
        )

    def test_no_live_1w_call_in_function(self):
        """The live _get_tf_indicators call must not use '1W' anymore."""
        # The function body may contain '1W' in comments/docstring; we only care
        # that the actual call uses '1D'. Check by scanning for the call pattern.
        call_pattern = re.compile(r'_get_tf_indicators\(indicators,\s*"1W"\)')
        assert not call_pattern.search(FN_BODY), (
            "_get_tf_indicators(..., '1W') still present in function body — "
            "Fix 4e requires '1D'"
        )

    def test_fix4e_comment_present(self):
        """Fix 4e rationale comment must be in the function to document the change."""
        assert "Fix 4e" in FN_BODY, (
            "Fix 4e comment not found in evaluate_weekly_stoch_rsi_bonus — "
            "change must document why 1W was replaced"
        )

    def test_missing_stoch_rsi_k_logs_debug(self):
        """When stoch_rsi_k is None (1D data unavailable), a debug log must be emitted
        before the early return — per §12 loud-failures-over-silent-skips."""
        assert "logger.debug" in FN_BODY and "1D stoch_rsi_k missing" in FN_BODY, (
            "No debug log before early return on missing 1D stoch_rsi_k — "
            "data-absent path is invisible in logs (§12 OBS-02)"
        )

    def test_docstring_updated(self):
        """Docstring must reference '1D' (not exclusively '1W') after Fix 4e."""
        assert "1D" in FN_BODY, (
            "Docstring not updated — still documents '1W' data source"
        )


class TestWeeklyStochRsiSymmetry:
    """
    Binary symmetry: same input → same outcome regardless of bull/bear direction
    for the key scoring branches. Verified inline to avoid needing a full IndicatorSet.
    """

    @staticmethod
    def _score(k_current: float, k_prev: float, is_bullish: bool,
               oversold: float = 20.0, overbought: float = 80.0,
               max_bonus: float = 15.0, max_penalty: float = 10.0) -> float:
        """Inline reproduction of the crossover/zone bonus logic."""
        # Crossover: K crossed above oversold threshold
        if k_prev is not None and k_prev <= oversold and k_current > oversold:
            return max_bonus if is_bullish else -max_penalty
        # Crossover: K crossed below overbought threshold
        if k_prev is not None and k_prev >= overbought and k_current < overbought:
            return max_bonus if not is_bullish else -max_penalty
        # Zone: in oversold
        if k_current <= oversold:
            return 10.0 if is_bullish else 5.0
        # Zone: in overbought
        if k_current >= overbought:
            return 10.0 if not is_bullish else 5.0
        # Neutral
        return 0.0

    def test_bullish_cross_above_oversold_gives_max_bonus(self):
        """K crossing above 20 from below: LONG gets max_bonus."""
        assert self._score(k_current=22.0, k_prev=18.0, is_bullish=True) == 15.0

    def test_bearish_cross_above_oversold_gives_max_penalty(self):
        """K crossing above 20 from below: SHORT gets max_penalty (symmetric)."""
        assert self._score(k_current=22.0, k_prev=18.0, is_bullish=False) == -10.0

    def test_bearish_cross_below_overbought_gives_max_bonus(self):
        """K crossing below 80 from above: SHORT gets max_bonus."""
        assert self._score(k_current=78.0, k_prev=82.0, is_bullish=False) == 15.0

    def test_bullish_cross_below_overbought_gives_penalty(self):
        """K crossing below 80 from above: LONG gets max_penalty (symmetric)."""
        assert self._score(k_current=78.0, k_prev=82.0, is_bullish=True) == -10.0

    def test_in_oversold_long_gets_10(self):
        """K in oversold zone: LONG gets +10 (anticipation)."""
        assert self._score(k_current=15.0, k_prev=15.0, is_bullish=True) == 10.0

    def test_in_oversold_short_gets_5(self):
        """K in oversold zone: SHORT gets +5 (momentum; symmetric pattern)."""
        assert self._score(k_current=15.0, k_prev=15.0, is_bullish=False) == 5.0

    def test_in_overbought_short_gets_10(self):
        """K in overbought zone: SHORT gets +10 (anticipation)."""
        assert self._score(k_current=85.0, k_prev=85.0, is_bullish=False) == 10.0

    def test_in_overbought_long_gets_5(self):
        """K in overbought zone: LONG gets +5 (momentum; symmetric pattern)."""
        assert self._score(k_current=85.0, k_prev=85.0, is_bullish=True) == 5.0

    def test_neutral_zone_no_bonus(self):
        """K in neutral (20-80): zero bonus for both directions."""
        assert self._score(k_current=50.0, k_prev=50.0, is_bullish=True) == 0.0
        assert self._score(k_current=50.0, k_prev=50.0, is_bullish=False) == 0.0


class TestWeeklyStochRsiFunctional:
    """
    Functional tests that call the REAL evaluate_weekly_stoch_rsi_bonus() using
    minimal IndicatorSet + IndicatorSnapshot objects.
    """

    def test_no_1d_data_returns_neutral(self):
        """STRIKE/SURGICAL: IndicatorSet without '1D' → bonus=0, aligned=True (neutral)."""
        ind = IndicatorSet(by_timeframe={"4h": _make_snapshot()})
        result = evaluate_weekly_stoch_rsi_bonus(ind, "bullish")
        assert result["bonus"] == 0.0, f"Expected neutral bonus=0.0, got {result['bonus']}"
        assert result["aligned"] is True, "Expected aligned=True on missing 1D data"

    def test_no_1d_data_short_returns_neutral(self):
        """Short direction with no 1D data also returns neutral (symmetric)."""
        ind = IndicatorSet(by_timeframe={"4h": _make_snapshot()})
        result = evaluate_weekly_stoch_rsi_bonus(ind, "bearish")
        assert result["bonus"] == 0.0
        assert result["aligned"] is True

    def test_1d_oversold_long_positive_bonus(self):
        """1D stoch_rsi_k in oversold (<20): LONG gets a positive bonus."""
        snap = _make_snapshot(stoch_rsi_k=15.0, stoch_rsi_k_prev=15.0)
        ind = IndicatorSet(by_timeframe={"1d": snap})
        result = evaluate_weekly_stoch_rsi_bonus(ind, "long")
        assert result["bonus"] > 0, f"Expected positive bonus for LONG in oversold, got {result['bonus']}"

    def test_1d_oversold_short_smaller_bonus(self):
        """1D stoch_rsi_k in oversold (<20): SHORT gets smaller bonus than LONG (symmetric logic)."""
        snap = _make_snapshot(stoch_rsi_k=15.0, stoch_rsi_k_prev=15.0)
        ind = IndicatorSet(by_timeframe={"1d": snap})
        long_result = evaluate_weekly_stoch_rsi_bonus(ind, "long")
        short_result = evaluate_weekly_stoch_rsi_bonus(ind, "short")
        assert long_result["bonus"] > short_result["bonus"], (
            f"LONG oversold bonus ({long_result['bonus']}) should exceed SHORT ({short_result['bonus']})"
        )

    def test_1d_overbought_short_positive_bonus(self):
        """1D stoch_rsi_k in overbought (>80): SHORT gets a positive bonus."""
        snap = _make_snapshot(stoch_rsi_k=85.0, stoch_rsi_k_prev=85.0)
        ind = IndicatorSet(by_timeframe={"1d": snap})
        result = evaluate_weekly_stoch_rsi_bonus(ind, "short")
        assert result["bonus"] > 0, f"Expected positive bonus for SHORT in overbought, got {result['bonus']}"

    def test_1d_overbought_long_smaller_bonus(self):
        """1D stoch_rsi_k in overbought (>80): LONG gets smaller bonus (symmetric)."""
        snap = _make_snapshot(stoch_rsi_k=85.0, stoch_rsi_k_prev=85.0)
        ind = IndicatorSet(by_timeframe={"1d": snap})
        short_result = evaluate_weekly_stoch_rsi_bonus(ind, "short")
        long_result = evaluate_weekly_stoch_rsi_bonus(ind, "long")
        assert short_result["bonus"] > long_result["bonus"], (
            f"SHORT overbought bonus ({short_result['bonus']}) should exceed LONG ({long_result['bonus']})"
        )
