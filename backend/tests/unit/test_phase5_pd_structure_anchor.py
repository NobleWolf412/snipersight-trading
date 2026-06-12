"""
Phase 5A — structure-anchored Premium/Discount dealing range.

Covers (per design 2026-06-12__phase5-design-pd-structure-anchored-dealing-range.md):
1. anchor="window" byte-identical to legacy behavior (zero behavior change)
2. Structural range differs from window when structure is tighter than the window
3. _compute_structural_dealing_range exact (last swing pair + running extremes)
4. Bull/bear symmetry (price-mirrored df → mirrored range, pct_mirror == 100 - pct)
5. Expansion legs both directions (running-extreme extension keeps pct <= 100)
6. Sparse-structure fallback — LOUD (caplog WARNING), stamped window_fallback
7. Sanity invariants (geometry ordering; flat df → 50%, no ZeroDivision)
8. Negative (missing column raises; swing_lookback=0 → fallback; structure w/o lookback raises)
9. Gate non-regression (structural EQ == window EQ ⇒ identical equilibrium)
10. Contract (to_dict superset of the 7 legacy keys + 4 additive keys)
"""
import logging

import pandas as pd
import pytest

from backend.analysis.premium_discount import (
    PremiumDiscountZone,
    _compute_structural_dealing_range,
    detect_premium_discount,
)

# ── Fixtures: explicit OHLC with hand-verified fractals (swing_lookback=2) ──────
# Swing highs at idx {2:115, 6:118, 10:120}; swing lows at idx {4:90, 8:88}.
# Most recent pair: SH*=idx10(120), SL*=idx8(88) → structural range [88, 120].
# Window(all 13) extremes are ALSO [88, 120] → used for gate non-regression.
H13 = [100, 102, 115, 103, 101, 104, 118, 105, 102, 106, 120, 108, 107]
L13 = [99, 101, 98, 100, 90, 95, 97, 103, 88, 94, 99, 106, 105]

# Same structure prepended with an OLD wide window extreme (high=135 at idx1,
# not a fractal — insufficient left neighbors). Window high=135 but structural
# SH* stays 120 → structural range_high(120) != window range_high(135).
PRE_H = [120, 135, 121, 119, 118]
PRE_L = [110, 108, 109, 107, 106]
H18 = PRE_H + H13
L18 = PRE_L + L13


def _df(highs, lows, closes=None):
    n = len(highs)
    closes = closes if closes is not None else [(h + l) / 2 for h, l in zip(highs, lows)]
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    return pd.DataFrame(
        {"open": closes, "high": highs, "low": lows, "close": closes,
         "volume": [1000.0] * n},
        index=idx,
    )


def _mirror(highs, lows, pivot):
    """Reflect prices about `pivot`: high' = 2P - low, low' = 2P - high."""
    m_high = [2 * pivot - l for l in lows]
    m_low = [2 * pivot - h for h in highs]
    return m_high, m_low


# ── 1. anchor="window" byte-identical to legacy ────────────────────────────────


def test_window_anchor_byte_identical_to_legacy():
    df = _df(H13, L13)
    z = detect_premium_discount(df, lookback=50, current_price=110.0)  # default anchor
    # legacy: tail(min(50,13)) extremes
    assert z.range_high == pytest.approx(120.0)
    assert z.range_low == pytest.approx(88.0)
    assert z.equilibrium == pytest.approx(104.0)
    assert z.current_zone == "premium"  # 110 >= 104
    assert z.zone_percentage == pytest.approx((110 - 88) / 32 * 100)
    assert z.range_anchor == "window"


def test_window_anchor_default_unchanged_call_signature():
    """Existing production call shape (no kw-only args) still works."""
    df = _df(H13, L13)
    z = detect_premium_discount(df, lookback=50, current_price=100.0)
    assert z.current_zone == "discount"  # 100 < 104


# ── 2-3. Structural range + differs from window ────────────────────────────────


def test_structural_range_exact():
    df = _df(H13, L13)
    out = _compute_structural_dealing_range(df, swing_lookback=2)
    assert out is not None
    range_high, range_low, sh_ts, sl_ts = out
    assert range_high == pytest.approx(120.0)
    assert range_low == pytest.approx(88.0)
    assert sh_ts == df.index[10]
    assert sl_ts == df.index[8]


def test_structural_differs_from_window():
    df = _df(H18, L18)
    z_struct = detect_premium_discount(df, anchor="structure", swing_lookback=2, current_price=110.0)
    z_window = detect_premium_discount(df, lookback=len(df), current_price=110.0)
    assert z_struct.range_anchor == "structure"
    assert z_struct.range_high == pytest.approx(120.0)  # excludes old 135 spike
    assert z_window.range_high == pytest.approx(135.0)  # window includes it
    assert z_struct.range_high < z_window.range_high


def test_structural_records_provenance():
    df = _df(H13, L13)
    z = detect_premium_discount(df, anchor="structure", swing_lookback=2)
    assert z.range_anchor == "structure"
    assert z.swing_lookback_used == 2
    assert z.anchor_swing_high_ts == str(df.index[10])
    assert z.anchor_swing_low_ts == str(df.index[8])


# ── 4. Bull/bear symmetry (price-mirrored df) ──────────────────────────────────


def test_structural_bull_bear_symmetry():
    pivot = 100.0
    df = _df(H13, L13)
    m_high, m_low = _mirror(H13, L13, pivot)
    mdf = _df(m_high, m_low)

    # current prices chosen NOT at equilibrium (tie-break is asymmetric by 1 pt)
    orig = detect_premium_discount(df, anchor="structure", swing_lookback=2, current_price=110.0)
    mirr = detect_premium_discount(mdf, anchor="structure", swing_lookback=2, current_price=2 * pivot - 110.0)

    assert mirr.range_high == pytest.approx(2 * pivot - orig.range_low)   # 112
    assert mirr.range_low == pytest.approx(2 * pivot - orig.range_high)   # 80
    assert mirr.equilibrium == pytest.approx(2 * pivot - orig.equilibrium)  # 96
    # zone_percentage mirrors: pct' == 100 - pct
    assert mirr.zone_percentage == pytest.approx(100 - orig.zone_percentage)
    # classification swaps
    assert orig.current_zone == "premium"
    assert mirr.current_zone == "discount"


def test_extreme_levels_symmetry():
    """75%/25% levels mirror to 25%/75% under reflection."""
    pivot = 100.0
    orig = detect_premium_discount(_df(H13, L13), anchor="structure", swing_lookback=2)
    m_high, m_low = _mirror(H13, L13, pivot)
    mirr = detect_premium_discount(_df(m_high, m_low), anchor="structure", swing_lookback=2)
    assert mirr.extreme_premium == pytest.approx(2 * pivot - orig.extreme_discount)
    assert mirr.extreme_discount == pytest.approx(2 * pivot - orig.extreme_premium)


# ── 5. Expansion legs both directions ──────────────────────────────────────────


def test_expansion_leg_up_extends_range_high():
    """Price breaks above last swing high → running-extreme extends range_high; pct<=100."""
    highs = list(H13)
    highs[12] = 125.0  # last candle breaks above SH*=120 (not a fractal: no right side)
    df = _df(highs, L13)
    z = detect_premium_discount(df, anchor="structure", swing_lookback=2, current_price=124.0)
    assert z.range_high == pytest.approx(125.0)  # extended to running high
    assert z.current_zone == "premium"
    assert z.zone_percentage <= 100.0


def test_expansion_leg_down_extends_range_low():
    """Mirror: breakdown below last swing low extends range_low; pct>=0."""
    lows = list(L13)
    lows[12] = 80.0  # breaks below SL*=88
    df = _df(H13, lows)
    z = detect_premium_discount(df, anchor="structure", swing_lookback=2, current_price=81.0)
    assert z.range_low == pytest.approx(80.0)
    assert z.current_zone == "discount"
    assert z.zone_percentage >= 0.0


# ── 6. Sparse-structure fallback — LOUD ────────────────────────────────────────


def test_fallback_when_structure_too_sparse(caplog):
    df = _df(H13, L13)  # len 13 < 2*10+1=21
    with caplog.at_level(logging.WARNING, logger="backend.analysis.premium_discount"):
        z = detect_premium_discount(df, anchor="structure", swing_lookback=10, current_price=110.0)
    assert z.range_anchor == "window_fallback"
    assert z.range_high == pytest.approx(120.0)  # window extremes used
    assert "fell back to window range" in caplog.text  # loudness is tested
    assert z.swing_lookback_used == 10


def test_fallback_when_no_swing_lows(caplog):
    """Monotonic-up df has no fractal lows → fallback, loudly."""
    highs = [100 + i for i in range(15)]
    lows = [99 + i for i in range(15)]
    df = _df(highs, lows)
    with caplog.at_level(logging.WARNING, logger="backend.analysis.premium_discount"):
        z = detect_premium_discount(df, anchor="structure", swing_lookback=2)
    assert z.range_anchor == "window_fallback"
    assert "fell back to window range" in caplog.text


# ── 7. Sanity invariants ───────────────────────────────────────────────────────


def test_geometry_ordering_holds():
    z = detect_premium_discount(_df(H13, L13), anchor="structure", swing_lookback=2)
    assert z.range_low <= z.extreme_discount <= z.equilibrium <= z.extreme_premium <= z.range_high


def test_flat_df_no_zero_division():
    flat = _df([100.0] * 13, [100.0] * 13)
    z = detect_premium_discount(flat, lookback=13, current_price=100.0)
    assert z.range_high == pytest.approx(z.range_low)
    assert z.zone_percentage == pytest.approx(50.0)  # range_size==0 guard


# ── 8. Negative tests ──────────────────────────────────────────────────────────


def test_structure_requires_swing_lookback():
    df = _df(H13, L13)
    with pytest.raises(ValueError, match="swing_lookback"):
        detect_premium_discount(df, anchor="structure")


def test_swing_lookback_zero_falls_back(caplog):
    df = _df(H13, L13)
    with caplog.at_level(logging.WARNING, logger="backend.analysis.premium_discount"):
        z = detect_premium_discount(df, anchor="structure", swing_lookback=0)
    assert z.range_anchor == "window_fallback"


def test_missing_high_column_raises():
    df = _df(H13, L13).drop(columns=["high"])
    with pytest.raises(KeyError):
        detect_premium_discount(df, lookback=13)


# ── 9. Gate non-regression (structural EQ == window EQ ⇒ identical) ─────────────


def test_gate_nonregression_when_ranges_coincide():
    """H13/L13: structural [88,120] == window [88,120] → equilibria must match,
    so the gate's in_optimal_zone predicate is byte-identical pre/post."""
    df = _df(H13, L13)
    entry = 95.0
    z_win = detect_premium_discount(df, lookback=len(df), current_price=entry)
    z_str = detect_premium_discount(df, anchor="structure", swing_lookback=2, current_price=entry)
    assert z_str.equilibrium == pytest.approx(z_win.equilibrium)
    # gate predicate (scorer.py:1138-1140) identical for both
    for is_long in (True, False):
        win_in = (is_long and entry <= z_win.equilibrium) or (not is_long and entry >= z_win.equilibrium)
        str_in = (is_long and entry <= z_str.equilibrium) or (not is_long and entry >= z_str.equilibrium)
        assert win_in == str_in


# ── 10. Contract ───────────────────────────────────────────────────────────────


def test_to_dict_superset_of_legacy_keys():
    z = detect_premium_discount(_df(H13, L13), anchor="structure", swing_lookback=2, current_price=110.0)
    d = z.to_dict()
    legacy = {"range_high", "range_low", "equilibrium", "extreme_premium",
              "extreme_discount", "current_zone", "zone_percentage"}
    additive = {"range_anchor", "anchor_swing_high_ts", "anchor_swing_low_ts", "swing_lookback_used"}
    assert legacy.issubset(d.keys())
    assert additive.issubset(d.keys())
    assert d["range_anchor"] == "structure"


def test_dataclass_defaults_window_compatible():
    """Constructing with only the legacy fields still works (additive defaults)."""
    z = PremiumDiscountZone(
        range_high=120.0, range_low=88.0, equilibrium=104.0,
        premium_start=104.0, discount_end=104.0,
        extreme_premium=112.0, extreme_discount=96.0,
    )
    assert z.range_anchor == "window"
    assert z.anchor_swing_high_ts is None
    assert z.swing_lookback_used is None
