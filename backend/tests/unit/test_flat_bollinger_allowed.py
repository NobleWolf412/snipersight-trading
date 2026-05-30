"""
Regression for hot-path audit bug #12 (3_CORRECTNESS): IndicatorSnapshot.__post_init__
required STRICT `bb_upper > bb_middle > bb_lower`. On a flat-price (zero-variance) window
the Bollinger Bands are all equal (BBU==BBM==BBL), so the strict check raised ValueError,
which indicator_service caught and dropped the WHOLE timeframe. With the TF gone, the
HTF structural-proximity gate ran on a partial IndicatorSet and treated the absent TF as
a perfect pass — inflating confluence on a trade possibly entering opposing HTF structure.

Fix: the validation now allows EQUAL bands (`>=`), which is the mathematically correct
output for zero-variance data. Genuinely inverted ordering (upper < lower) still raises.
Downstream %B already guards a zero band-range (indicator_service.py:204 → 0.5), so equal
bands introduce no division-by-zero.

See backend/diagnostics/decisions/2026-05-29__hotpath-robustness-audit.md (bug #12).
Per CLAUDE.md §11, §14 rubric 4 (negative+positive pair).
"""

from __future__ import annotations

import pytest

from backend.shared.models.indicators import IndicatorSnapshot


def _snap(bb_upper: float, bb_middle: float, bb_lower: float) -> IndicatorSnapshot:
    return IndicatorSnapshot(
        rsi=50.0, stoch_rsi=50.0,
        bb_upper=bb_upper, bb_middle=bb_middle, bb_lower=bb_lower,
        atr=1.0, volume_spike=False, mfi=50.0, obv=0.0,
    )


def test_flat_bands_no_longer_dropped():
    """Zero-variance window → BBU==BBM==BBL must construct (was a ValueError that
    dropped the whole TF and inflated the HTF gate). bb_width == 0."""
    snap = _snap(100.0, 100.0, 100.0)
    assert snap.bb_width == 0.0


def test_normal_bands_still_valid():
    """Positive (no-regression): a normal volatile window still constructs."""
    snap = _snap(102.0, 100.0, 98.0)
    assert snap.bb_width == 4.0


def test_inverted_bands_still_raise():
    """Negative: a genuinely inverted ordering (upper < lower) is still invalid."""
    with pytest.raises(ValueError):
        _snap(98.0, 100.0, 102.0)


def test_misordered_middle_still_raises():
    """Negative: middle above upper is invalid ordering even though upper > lower."""
    with pytest.raises(ValueError):
        _snap(100.0, 101.0, 99.0)
