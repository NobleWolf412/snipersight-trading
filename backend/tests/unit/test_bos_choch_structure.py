"""
Regression tests for Phase 3 (2026-06-11): bos_choch.py structural fixes.

3A — _detect_bos_choch_pattern CHoCH conditions were garbled: both CHoCH branches
     tested inverted structure relationships (e.g. bullish CHoCH required the newest
     high ABOVE the older high — contradicting "prior bearish") and returned the
     OLDER swing's level/timestamp (index -3). Fixed: CHoCH requires genuine
     opposite-direction prior structure and breaks the MOST RECENT swing (index -1).

3B — _determine_initial_trend compared values[-1] vs values[-2]: the LAST two swings
     of the entire dataframe seeded the INITIAL trend (look-ahead + contradicted its
     own docstring). Fixed to first two swings. Also: an initial "ranging" trend
     deadlocked the scan loop (trend only mutated inside up/downtrend branches) →
     ZERO breaks emitted silently. Fixed: ranging resolves on the first decisive
     break (loudly logged, establishing break NOT emitted).

3C — BOS volume rejection used `continue`, skipping the swing-ref update, so the
     state machine pretended the break never happened and the same stale level
     re-fired on later candles. Fixed to the CHoCH-style skip_signal pattern with
     unconditional ref advance. NOTE: latent under current mode wiring (no live mode
     combines simple validation with a BOS volume gate) — tests use a monkeypatched
     profile to make the path observable.
"""

from __future__ import annotations

import logging

import pandas as pd
import pytest

from backend.strategy.smc.bos_choch import (
    MODE_BOS_VALIDATION,
    MODE_VOLUME_REQUIREMENTS,
    _detect_bos_choch_pattern,
    _determine_initial_trend,
    detect_structural_breaks,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts(n: int) -> list:
    return list(pd.date_range("2026-01-01", periods=n, freq="1h"))


TS4 = _ts(4)


def _df_from_closes(closes, vols=None) -> pd.DataFrame:
    """Build OHLCV df with midpoint opens (avoids high/low ties at peaks/troughs).

    high = max(o, c) + 0.2 ; low = min(o, c) - 0.2 ; o = (prev_close + close) / 2.
    Equal peak CLOSES therefore give exactly equal swing-high values.
    """
    idx = pd.date_range("2026-01-01", periods=len(closes), freq="1h")
    opens, highs, lows = [], [], []
    prev = closes[0]
    for c in closes:
        o = (prev + c) / 2.0
        opens.append(o)
        highs.append(max(o, c) + 0.2)
        lows.append(min(o, c) - 0.2)
        prev = c
    v = vols if vols is not None else [1000.0] * len(closes)
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": v},
        index=idx,
    )


def _ramp(a: float, b: float, n: int) -> list:
    """n closes stepping linearly from a (exclusive) to b (inclusive)."""
    step = (b - a) / n
    return [a + step * (k + 1) for k in range(n)]


# ===========================================================================
# 3A — _detect_bos_choch_pattern
# ===========================================================================

class TestBosPinnedThroughRename:
    """BOS semantics must be IDENTICAL pre/post the chronological rename (pure rename)."""

    def test_bullish_bos_ascending_structure(self):
        # [L1,H1,L2,H2] = [94, 101, 96, 103]: ascending 94 < 96 < 101 < 103
        bt, d, lvl, ts = _detect_bos_choch_pattern(
            [-1, 1, -1, 1], [94.0, 101.0, 96.0, 103.0], TS4, 104.0, 104.5, 103.5
        )
        assert (bt, d) == ("BOS", "bullish")
        assert lvl == 103.0  # most recent higher high
        assert ts == TS4[-1]

    def test_bearish_bos_descending_structure(self):
        # [H1,L1,H2,L2] = [106, 99, 104, 97]: descending 106 > 104 > 99 > 97
        bt, d, lvl, ts = _detect_bos_choch_pattern(
            [1, -1, 1, -1], [106.0, 99.0, 104.0, 97.0], TS4, 96.0, 96.5, 95.5
        )
        assert (bt, d) == ("BOS", "bearish")
        assert lvl == 97.0  # most recent lower low
        assert ts == TS4[-1]

    def test_bullish_bos_not_fired_without_close_break(self):
        bt, *_ = _detect_bos_choch_pattern(
            [-1, 1, -1, 1], [94.0, 101.0, 96.0, 103.0], TS4, 102.0, 102.5, 101.5
        )
        assert bt is None

    def test_bearish_bos_not_fired_without_close_break(self):
        bt, *_ = _detect_bos_choch_pattern(
            [1, -1, 1, -1], [106.0, 99.0, 104.0, 97.0], TS4, 98.0, 98.5, 97.5
        )
        assert bt is None


class TestChochFixed:
    """3A core: CHoCH requires opposite-direction prior structure, breaks index -1."""

    def test_bullish_choch_on_prior_bearish_structure(self):
        # [L1,H1,L2,H2] = [96, 104, 94, 102]: lower high (102<104), lower low (94<96)
        # close 103 breaks above the MOST RECENT lower high (102).
        bt, d, lvl, ts = _detect_bos_choch_pattern(
            [-1, 1, -1, 1], [96.0, 104.0, 94.0, 102.0], TS4, 103.0, 103.5, 102.5
        )
        assert (bt, d) == ("CHoCH", "bullish")
        assert lvl == 102.0, "must break the MOST RECENT lower high (was: older high)"
        assert ts == TS4[-1], "timestamp must be the most recent swing (was: index -3)"

    def test_bearish_choch_on_prior_bullish_structure(self):
        # [H1,L1,H2,L2] = [104, 96, 106, 98]: higher high (106>104), higher low (98>96)
        # close 95 breaks below the MOST RECENT higher low (98).
        bt, d, lvl, ts = _detect_bos_choch_pattern(
            [1, -1, 1, -1], [104.0, 96.0, 106.0, 98.0], TS4, 95.0, 95.5, 94.5
        )
        assert (bt, d) == ("CHoCH", "bearish")
        assert lvl == 98.0
        assert ts == TS4[-1]

    def test_bullish_choch_requires_close_above_recent_lower_high(self):
        # Same prior-bearish structure, close BELOW the recent LH → no fire.
        bt, *_ = _detect_bos_choch_pattern(
            [-1, 1, -1, 1], [96.0, 104.0, 94.0, 102.0], TS4, 101.0, 101.5, 100.5
        )
        assert bt is None

    def test_bearish_choch_requires_close_below_recent_higher_low(self):
        bt, *_ = _detect_bos_choch_pattern(
            [1, -1, 1, -1], [104.0, 96.0, 106.0, 98.0], TS4, 99.0, 99.5, 98.5
        )
        assert bt is None


class TestGarbledConditionsDead:
    """Geometry the OLD garbled conditions accepted must now return None."""

    def test_old_bullish_garble_rejected(self):
        # Old condition: close > h1 and h2 > h1 > l1 > l2.
        # [L1,H1,L2,H2] = [96, 100, 90, 105], close 101 (> old level 100, < h2 105).
        # Old code fired CHoCH bullish @100. Neither BOS (96<90 fails ascending)
        # nor CHoCH (h2 105 > h1 100 fails lower-high) is valid now.
        bt, d, lvl, ts = _detect_bos_choch_pattern(
            [-1, 1, -1, 1], [96.0, 100.0, 90.0, 105.0], TS4, 101.0, 101.5, 100.5
        )
        assert bt is None, f"old garbled bullish CHoCH geometry must not fire (got {bt} @{lvl})"

    def test_old_bearish_garble_rejected(self):
        # Old condition: close < l1 and l2 < l1 < h2 < h1.
        # [H1,L1,H2,L2] = [110, 100, 104, 95], close 99 (< old level 100, > l2 95).
        # Old code fired CHoCH bearish @100. Now: BOS needs close < l2 (99>95 no);
        # CHoCH needs h2 > h1 (104<110 no) → None.
        bt, d, lvl, ts = _detect_bos_choch_pattern(
            [1, -1, 1, -1], [110.0, 100.0, 104.0, 95.0], TS4, 99.0, 99.5, 98.5
        )
        assert bt is None, f"old garbled bearish CHoCH geometry must not fire (got {bt} @{lvl})"


class TestPatternNegatives:
    def test_fewer_than_four_swings_returns_none(self):
        bt, d, lvl, ts = _detect_bos_choch_pattern(
            [-1, 1, -1], [96.0, 104.0, 94.0], _ts(3), 110.0, 110.5, 109.5
        )
        assert (bt, d, lvl, ts) == (None, None, 0.0, None)

    def test_non_alternating_shape_returns_none(self):
        bt, *_ = _detect_bos_choch_pattern(
            [1, 1, -1, 1], [104.0, 105.0, 94.0, 102.0], TS4, 110.0, 110.5, 109.5
        )
        assert bt is None

    def test_close_inside_range_returns_none_both_shapes(self):
        bt1, *_ = _detect_bos_choch_pattern(
            [-1, 1, -1, 1], [94.0, 101.0, 96.0, 103.0], TS4, 100.0, 100.5, 99.5
        )
        bt2, *_ = _detect_bos_choch_pattern(
            [1, -1, 1, -1], [106.0, 99.0, 104.0, 97.0], TS4, 100.0, 100.5, 99.5
        )
        assert bt1 is None and bt2 is None


@pytest.mark.parametrize('types,levels,close,kind,direction', [
    ([1,-1,1,-1], [101.,94.,103.,96.], 104., 'BOS', 'bullish'),
    ([1,-1,1,-1], [104.,96.,102.,94.], 103., 'CHoCH', 'bullish'),
    ([-1,1,-1,1], [99.,106.,97.,104.], 96., 'BOS', 'bearish'),
    ([-1,1,-1,1], [96.,104.,98.,106.], 97., 'CHoCH', 'bearish'),
])
def test_structural_four_swing_checks_both_boundaries(types, levels, close, kind, direction):
    found = _detect_bos_choch_pattern(types, levels, TS4, close, close+.5, close-.5)
    assert found == (kind, direction, levels[-2], TS4[-2])
    # Touches and wick-only breaks do not confirm a close beyond the boundary.
    level = levels[-2]
    assert _detect_bos_choch_pattern(types, levels, TS4, level, level+1., level-1.)[0] is None
    mirrored = _detect_bos_choch_pattern([-t for t in types], [200.-x for x in levels],
                                        TS4, 200.-close, 200.-close+.5, 200.-close-.5)
    assert mirrored == (kind, 'bearish' if direction == 'bullish' else 'bullish', 200.-level, TS4[-2])


def test_structural_four_swing_mixed_newest_geometry_is_not_older_trend():
    # A higher high and lower low are mixed evidence; do not search an older
    # ascending window just to manufacture a bullish continuation.
    for close in (104., 91.):
        assert _detect_bos_choch_pattern([1,-1,1,-1], [101.,94.,103.,92.],
                                       TS4, close, close+.5, close-.5)[0] is None


class TestPatternSymmetry:
    """Mirror prices around 200: bullish inputs must map to bearish outputs exactly."""

    CASES = [
        # (types, levels, close) — bullish-side inputs
        ([-1, 1, -1, 1], [94.0, 101.0, 96.0, 103.0], 104.0),   # bullish BOS
        ([-1, 1, -1, 1], [96.0, 104.0, 94.0, 102.0], 103.0),   # bullish CHoCH
        ([-1, 1, -1, 1], [94.0, 101.0, 96.0, 103.0], 100.0),   # no fire
    ]

    @pytest.mark.parametrize("types,levels,close", CASES)
    def test_mirror_symmetry(self, types, levels, close):
        bt_bull, d_bull, lvl_bull, ts_bull = _detect_bos_choch_pattern(
            types, levels, TS4, close, close + 0.5, close - 0.5
        )
        m_types = [-t for t in types]
        m_levels = [200.0 - x for x in levels]
        m_close = 200.0 - close
        bt_bear, d_bear, lvl_bear, ts_bear = _detect_bos_choch_pattern(
            m_types, m_levels, TS4, m_close, m_close + 0.5, m_close - 0.5
        )
        assert bt_bear == bt_bull, "break type must mirror"
        if bt_bull is not None:
            assert {d_bull, d_bear} == {"bullish", "bearish"}, "direction must flip"
            assert lvl_bear == pytest.approx(200.0 - lvl_bull), "level must mirror"
            assert ts_bear == ts_bull, "timestamp index must match"


# ===========================================================================
# 3B — _determine_initial_trend + ranging deadlock
# ===========================================================================

class TestInitialTrendFirstSwings:
    def test_uses_first_swings_not_last_uptrend(self):
        # First two highs ASCEND, last two DESCEND. Old code: downtrend. New: uptrend.
        highs = pd.Series([100.0, 105.0, 110.0, 108.0, 104.0])
        lows = pd.Series([90.0, 95.0])
        assert _determine_initial_trend(highs, lows) == "uptrend"

    def test_uses_first_swings_not_last_downtrend(self):
        # First two highs DESCEND, last two ASCEND. Old code: uptrend. New: downtrend.
        highs = pd.Series([110.0, 105.0, 100.0, 102.0, 106.0])
        lows = pd.Series([95.0, 90.0])
        assert _determine_initial_trend(highs, lows) == "downtrend"

    def test_equal_first_highs_falls_through_to_lows(self):
        highs = pd.Series([105.0, 105.0, 120.0])
        lows = pd.Series([90.0, 95.0])  # ascending firsts → uptrend
        assert _determine_initial_trend(highs, lows) == "uptrend"

    def test_all_equal_firsts_is_ranging(self):
        highs = pd.Series([105.0, 105.0])
        lows = pd.Series([95.0, 95.0])
        assert _determine_initial_trend(highs, lows) == "ranging"

    def test_too_few_swings_is_ranging(self):
        assert _determine_initial_trend(pd.Series([105.0]), pd.Series([95.0])) == "ranging"


def _ranging_breakout_closes() -> list:
    """Equal swing highs (105, 105), single swing low (95) → initial trend ranging.
    Flat shelf, then upside breakout."""
    closes = [95.0]
    closes += _ramp(95, 105, 8)        # peak 1 @ idx8 (close 105)
    closes += _ramp(105, 95, 8)        # trough @ idx16
    closes += _ramp(95, 105, 8)        # peak 2 @ idx24 (close 105, equal)
    closes += [103.0] * 7              # flat shelf idx25-31 (tie-killed lows)
    closes += [110.0, 113.0, 116.0, 119.0, 122.0, 125.0]  # breakout idx32-37
    return closes


class TestRangingDeadlockFixed:
    def test_ranging_start_emits_breaks_after_resolve(self, caplog):
        df = _df_from_closes(_ranging_breakout_closes())
        with caplog.at_level(logging.INFO, logger="backend.strategy.smc.bos_choch"):
            breaks = detect_structural_breaks(df, {"swing_lookback": 3})
        assert len(breaks) >= 1, (
            "ranging initial trend must no longer deadlock the scan to zero breaks"
        )
        assert all(b.direction == "bullish" and b.break_type == "BOS" for b in breaks)
        assert "RANGING resolved to uptrend" in caplog.text, "resolution must be loud"

    def test_establishing_break_not_emitted(self):
        df = _df_from_closes(_ranging_breakout_closes())
        breaks = detect_structural_breaks(df, {"swing_lookback": 3})
        # idx32 is the resolving candle — it must NOT be emitted as a signal.
        resolve_ts = df.index[32]
        assert all(b.timestamp > resolve_ts.to_pydatetime() for b in breaks), (
            "the trend-establishing break must not be emitted (no prior trend to "
            "classify it as BOS vs CHoCH)"
        )

    def test_ranging_with_no_breakout_stays_silent(self, caplog):
        closes = [95.0]
        closes += _ramp(95, 105, 8)
        closes += _ramp(105, 95, 8)
        closes += _ramp(95, 105, 8)
        closes += [103.0] * 14         # flat forever — no decisive break
        df = _df_from_closes(closes)
        with caplog.at_level(logging.INFO, logger="backend.strategy.smc.bos_choch"):
            breaks = detect_structural_breaks(df, {"swing_lookback": 3})
        assert breaks == []
        assert "RANGING resolved" not in caplog.text

    def test_ranging_downtrend_mirror(self, caplog):
        closes = [200.0 - c for c in _ranging_breakout_closes()]
        df = _df_from_closes(closes)
        with caplog.at_level(logging.INFO, logger="backend.strategy.smc.bos_choch"):
            breaks = detect_structural_breaks(df, {"swing_lookback": 3})
        assert len(breaks) >= 1
        assert all(b.direction == "bearish" and b.break_type == "BOS" for b in breaks)
        assert "RANGING resolved to downtrend" in caplog.text


def _ranging_4swing_closes() -> list:
    """Equal first two swing highs (105,105) AND equal first two swing lows (95,95)
    → ranging. Then an ascending 4-swing develops (L95, H101, L97, H106) and price
    breaks above 106 → 4swing BOS resolves the trend, next candle emits."""
    closes = [100.0]
    closes += _ramp(100, 105, 5)       # peak a @ idx5 (105)
    closes += _ramp(105, 102, 3)       # idx6-8
    closes += [102.0] * 4              # flat idx9-12 (tie-killed lows: no swing low)
    closes += _ramp(102, 105, 3)       # peak b @ idx15 (105, equal)
    closes += _ramp(105, 95, 6)        # trough c @ idx21 (95)
    closes += _ramp(95, 104, 5)        # peak d @ idx26 (104)
    closes += _ramp(104, 95, 5)        # trough e @ idx31 (95, equal)
    closes += _ramp(95, 101, 4)        # peak f @ idx35 (101)
    closes += _ramp(101, 97, 3)        # trough g @ idx38 (97)
    closes += _ramp(97, 106, 5)        # peak h @ idx43 (106)
    closes += [103.0] * 5              # flat idx44-48 (below 106; > lookback wide so h confirms)
    closes += [109.0, 111.5, 114.0, 116.5]  # breakout idx49-52
    return closes


class TestRanging4SwingResolve:
    @pytest.fixture
    def fourswing_profile(self, monkeypatch):
        # 4swing validation, no volume requirements — isolates the ranging branch.
        monkeypatch.setitem(MODE_BOS_VALIDATION, "test_4swing", "4swing")
        return "test_4swing"

    def test_4swing_geometry_establishes_prior_trend_and_emits_once(self, fourswing_profile):
        df = _df_from_closes(_ranging_4swing_closes())
        breaks = detect_structural_breaks(
            df, {"swing_lookback": 3}, mode_profile=fourswing_profile
        )
        # Unlike the simple detector, four alternating pivots already establish
        # a prior trend. Consume the first close break, not a later duplicate.
        assert len(breaks) == 1
        assert all(b.direction == "bullish" and b.break_type == "BOS" for b in breaks)
        assert breaks[0].timestamp == df.index[49].to_pydatetime()


# ===========================================================================
# 3C — BOS volume-reject skip_signal (latent path, monkeypatched profile)
# ===========================================================================

VOLGATED = "test_volgated_simple"


@pytest.fixture
def volgated_profile(monkeypatch):
    # Simple validation (absent from MODE_BOS_VALIDATION) + BOS volume gate @1.5x.
    monkeypatch.setitem(
        MODE_VOLUME_REQUIREMENTS,
        VOLGATED,
        {"require_volume": True, "min_volume_ratio": 1.5, "apply_to": ["BOS"]},
    )
    return VOLGATED


def _volgate_bullish_df() -> pd.DataFrame:
    """Uptrend seed (equal highs 105/105, ascending lows 95→98). Candle 34 breaks
    out on LOW volume (gated); candle 35 closes above the OLD swing level but below
    candle 34's high, on HIGH volume; candle 36 breaks candle 34's high on HIGH
    volume. Old code: stale re-fire at 35 and/or stale level at 36. New code:
    exactly one BOS, level == candle 34's high."""
    closes = [95.0]
    closes += _ramp(95, 105, 8)        # peak 1 @ idx8
    closes += _ramp(105, 95, 8)        # trough 1 @ idx16 (95)
    closes += _ramp(95, 105, 8)        # peak 2 @ idx24 (equal)
    closes += _ramp(105, 98, 6)        # trough 2 @ idx30 (98 — higher low)
    closes += _ramp(98, 103, 3)        # idx31-33 rise, below old swing high
    closes += [110.0]                  # idx34: gated breakout (low volume)
    closes += [107.0]                  # idx35: above OLD level, below idx34 high
    closes += [115.0]                  # idx36: above idx34 high
    closes += [115.5, 116.0, 116.5, 117.0]  # gentle rise (no swing at 36, sub-min_break steps)
    vols = [1000.0] * len(closes)
    vols[35] = 5000.0
    vols[36] = 5000.0
    return _df_from_closes(closes, vols)


class TestBosVolumeRejectAdvancesRef:
    def test_stale_level_does_not_refire_bullish(self, volgated_profile):
        df = _volgate_bullish_df()
        breaks = detect_structural_breaks(
            df, {"swing_lookback": 3}, mode_profile=volgated_profile
        )
        bos = [b for b in breaks if b.break_type == "BOS"]
        old_swing_high = df["high"].iloc[24]   # the pre-breakout swing level
        gated_candle_high = df["high"].iloc[34]
        assert all(b.level != pytest.approx(old_swing_high) for b in bos), (
            "BOS emitted at the STALE pre-gate swing level — volume-rejected break "
            "did not advance the swing ref (old `continue` behavior)"
        )
        assert len(bos) == 1, f"expected exactly one BOS after ref advance, got {len(bos)}"
        assert bos[0].level == pytest.approx(gated_candle_high), (
            "the emitted BOS must break the gated candle's high (the advanced ref)"
        )
        assert bos[0].direction == "bullish"
        assert bos[0].timestamp == df.index[36].to_pydatetime()

    def test_stale_level_does_not_refire_bearish_mirror(self, volgated_profile):
        closes_bull = _volgate_bullish_df()["close"].tolist()
        closes = [200.0 - c for c in closes_bull]
        vols = [1000.0] * len(closes)
        vols[35] = 5000.0
        vols[36] = 5000.0
        df = _df_from_closes(closes, vols)
        breaks = detect_structural_breaks(
            df, {"swing_lookback": 3}, mode_profile=volgated_profile
        )
        bos = [b for b in breaks if b.break_type == "BOS"]
        old_swing_low = df["low"].iloc[24]
        gated_candle_low = df["low"].iloc[34]
        assert all(b.level != pytest.approx(old_swing_low) for b in bos)
        assert len(bos) == 1
        assert bos[0].level == pytest.approx(gated_candle_low)
        assert bos[0].direction == "bearish"
        assert bos[0].timestamp == df.index[36].to_pydatetime()


def _macro_4swing_closes(with_red_dip: bool = False) -> list:
    """Ascending 4-swing (L95 @5, H105 @11, L97 @16, H106 @22) then breakout.
    with_red_dip inserts a red candle + doji in the flat shelf (for OB linkage)."""
    closes = [99.0]
    closes += _ramp(99, 95, 5)         # trough l1 @ idx5 (95)
    closes += _ramp(95, 105, 6)        # peak h1 @ idx11 (105)
    closes += _ramp(105, 97, 5)        # trough l2 @ idx16 (97)
    closes += _ramp(97, 106, 6)        # peak h2 @ idx22 (106)
    if with_red_dip:
        closes += [103.0, 102.5, 102.5, 103.0]  # idx23-26: flat, red @24, doji @25
    else:
        closes += [103.0] * 4          # flat idx23-26
    closes += [109.0, 112.0, 115.0, 118.0]      # breakout idx27-30
    closes += [118.0] * 5              # tail padding (length safety)
    return closes


class TestCurrentWiring4SwingVolumeGate:
    """macro_surveillance (4swing, BOS volume 1.5x) — current live wiring."""

    def _df(self, breakout_vol: float) -> pd.DataFrame:
        closes = _macro_4swing_closes()
        vols = [1000.0] * len(closes)
        for i in (27, 28, 29, 30):
            vols[i] = breakout_vol
        return _df_from_closes(closes, vols)

    def test_low_volume_bos_suppressed_scan_completes(self):
        df = self._df(breakout_vol=1000.0)   # ratio 1.0 < 1.5 → all gated
        breaks = detect_structural_breaks(
            df, {"swing_lookback": 3}, mode_profile="macro_surveillance"
        )
        assert breaks == [], "low-volume 4swing BOS must be suppressed (signal gate)"

    def test_high_volume_bos_emitted(self):
        df = self._df(breakout_vol=5000.0)   # ratio ~4x ≥ 1.5 → passes
        breaks = detect_structural_breaks(
            df, {"swing_lookback": 3}, mode_profile="macro_surveillance"
        )
        bos = [b for b in breaks if b.break_type == "BOS" and b.direction == "bullish"]
        assert len(bos) >= 1, "high-volume 4swing BOS must be emitted"
        h2_level = df["high"].iloc[22]
        assert all(b.level == pytest.approx(h2_level) for b in bos), (
            "4swing BOS must break the most recent higher high (h2)"
        )


@pytest.mark.parametrize('direction', ['bullish', 'bearish'])
@pytest.mark.parametrize('seed', ['uptrend', 'downtrend', 'ranging'])
def test_structural_four_swing_geometry_owns_direction_and_consumes_pivot(monkeypatch, direction, seed):
    from backend.strategy.smc import bos_choch
    closes = _macro_4swing_closes()
    if direction == 'bearish':
        closes = [200.-x for x in closes]
    vols = [1000.] * len(closes)
    for i in (27,28,29,30):
        vols[i] = 5000.
    df = _df_from_closes(closes, vols)
    monkeypatch.setattr(bos_choch, '_determine_initial_trend', lambda *_: seed)
    events = detect_structural_breaks(df, {'swing_lookback': 3}, mode_profile='stealth_balanced')
    assert len(events) == 1
    assert (events[0].break_type, events[0].direction) == ('BOS', direction)
    assert events[0].timestamp == df.index[27].to_pydatetime()


@pytest.mark.parametrize('direction', ['bullish', 'bearish'])
def test_structural_four_swing_volume_failure_cannot_refire_same_pivot(direction):
    closes = _macro_4swing_closes()
    if direction == 'bearish':
        closes = [200.-x for x in closes]
    vols = [1000.] * len(closes)
    for i in (28,29,30):
        vols[i] = 5000.
    events = detect_structural_breaks(_df_from_closes(closes, vols),
                                     {'swing_lookback': 3}, mode_profile='stealth_balanced')
    assert events == []


def _four_swing_control(monkeypatch, highs, lows, closes, volumes, *, direction='bullish'):
    from backend.strategy.smc import bos_choch
    from backend.indicators import volatility
    df = _df_from_closes(closes, volumes)
    high_points = pd.Series({df.index[i]: price for i, price in highs})
    low_points = pd.Series({df.index[i]: price for i, price in lows})
    if direction == 'bearish':
        df = _df_from_closes([200.-x for x in closes], volumes)
        high_points, low_points = 200.-low_points, 200.-high_points
    monkeypatch.setattr(bos_choch, '_detect_swing_highs', lambda *_: high_points)
    monkeypatch.setattr(bos_choch, '_detect_swing_lows', lambda *_: low_points)
    monkeypatch.setattr(bos_choch, '_determine_initial_trend', lambda *_: 'ranging')
    monkeypatch.setattr(volatility, 'compute_atr', lambda *_args, **_kwargs: pd.Series(4., index=df.index))
    return detect_structural_breaks(df, {'swing_lookback': 3, 'min_break_distance_atr': 1.},
                                    mode_profile='stealth_balanced')


@pytest.mark.parametrize('direction', ['bullish', 'bearish'])
@pytest.mark.parametrize('base,break_volume,expected_count,expected_grade', [
    (1870., 2469., 0, None),    # Just below 1.3x average.
    (1870., 2470., 1, 'C'),     # 2470 / ((19*1870+2470)/20) == 1.3 exactly.
    (900., 1900., 1, 'B'),      # 1900 / ((19*900+1900)/20) == 2 exactly: promote C.
])
def test_structural_four_swing_choch_volume_boundaries_and_consumption(monkeypatch, direction, base, break_volume, expected_count, expected_grade):
    closes, vols = [100.] * 40, [base] * 40
    closes[29:33] = [103.] * 4
    vols[29] = break_volume
    vols[30:33] = [5000.] * 3  # No re-emission or later upgrade of that pivot.
    events = _four_swing_control(monkeypatch, [(23,104.),(25,102.)], [(24,96.),(26,94.)],
                                closes, vols, direction=direction)
    assert len(events) == expected_count
    if events:
        assert (events[0].break_type, events[0].direction, events[0].grade) == ('CHoCH', direction, expected_grade)


@pytest.mark.parametrize('direction', ['bullish', 'bearish'])
def test_structural_four_swing_distinct_pivots_at_same_price_are_distinct(monkeypatch, direction):
    closes, vols = [100.] * 40, [1000.] * 40
    closes[23], closes[31] = 104., 104.
    vols[23], vols[31] = 5000., 5000.
    events = _four_swing_control(monkeypatch,
        [(19,101.),(21,103.),(27,100.),(29,103.)],
        [(20,94.),(22,96.),(28,90.),(30,92.)], closes, vols, direction=direction)
    assert len(events) == 2
    assert all(e.direction == direction and e.break_type == 'BOS' for e in events)
    assert events[0].level == events[1].level
    assert events[0].timestamp != events[1].timestamp


@pytest.mark.parametrize('mixed', [True, False])
def test_structural_four_swing_never_falls_back_to_simple_break(monkeypatch, mixed):
    closes, vols = [100.] * 40, [1000.] * 40
    closes[29], vols[29] = 110., 5000.
    highs = [(23,101.),(25,103.)] if mixed else [(23,101.)]
    lows = [(24,94.),(26,92.)] if mixed else [(24,94.)]
    assert _four_swing_control(monkeypatch, highs, lows, closes, vols) == []


def _controlled_graded_break(monkeypatch, direction, kind, minimum, multiple, *, atr=4., volume=1000.):
    """Exercise each real emission branch with controlled swing and ATR inputs."""
    from backend.strategy.smc import bos_choch
    from backend.indicators import volatility
    df = _df_from_closes([95.] * 30)
    level = 100. if direction == 'bullish' else 90.
    distance = 4. * minimum * multiple
    close = level + distance if direction == 'bullish' else level - distance
    df.loc[df.index[-1], ['open', 'high', 'low', 'close', 'volume']] = [
        95., max(95., close)+.2, min(95., close)-.2, close, volume]
    monkeypatch.setattr(bos_choch, '_detect_swing_highs',
                        lambda *_: pd.Series([100.], index=[df.index[9]]))
    monkeypatch.setattr(bos_choch, '_detect_swing_lows',
                        lambda *_: pd.Series([90.], index=[df.index[10]]))
    trend = 'uptrend' if (direction == 'bullish') == (kind == 'BOS') else 'downtrend'
    monkeypatch.setattr(bos_choch, '_determine_initial_trend', lambda *_: trend)
    monkeypatch.setattr(volatility, 'compute_atr', lambda *_args, **_kwargs: pd.Series(atr, index=df.index))
    breaks = detect_structural_breaks(df, {'swing_lookback': 3, 'min_break_distance_atr': minimum})
    assert len(breaks) == 1
    event = breaks[0]
    assert (event.direction, event.break_type) == (direction, kind)
    return event


@pytest.mark.parametrize('direction', ['bullish', 'bearish'])
@pytest.mark.parametrize('kind', ['BOS', 'CHoCH'])
@pytest.mark.parametrize('minimum', [.5, 1., 1.5])
@pytest.mark.parametrize('multiple,expected', [(1.4, 'C'), (1.5, 'B'), (2.49, 'B'), (2.5, 'A')])
def test_structural_grading_uses_atr_units_and_ordered_boundaries(monkeypatch, direction, kind, minimum, multiple, expected):
    event = _controlled_graded_break(monkeypatch, direction, kind, minimum, multiple)
    assert event.grade == expected
    assert event.break_distance_atr == pytest.approx(minimum * multiple)


@pytest.mark.parametrize('direction', ['bullish', 'bearish'])
@pytest.mark.parametrize('kind', ['BOS', 'CHoCH'])
@pytest.mark.parametrize('multiple,expected', [(1.4, 'B'), (1.5, 'A'), (2.5, 'A')])
def test_structural_grading_preserves_volume_promotion(monkeypatch, direction, kind, multiple, expected):
    event = _controlled_graded_break(monkeypatch, direction, kind, 1., multiple, volume=5000.)
    assert event.grade == expected


@pytest.mark.parametrize('direction', ['bullish', 'bearish'])
@pytest.mark.parametrize('kind', ['BOS', 'CHoCH'])
@pytest.mark.parametrize('atr', [0., float('nan')])
def test_structural_grading_missing_atr_cannot_create_qualifying_grade(monkeypatch, direction, kind, atr):
    event = _controlled_graded_break(monkeypatch, direction, kind, 1., 1.5, atr=atr)
    assert event.grade == 'C'
    assert event.break_distance_atr == 0.


@pytest.mark.parametrize('tf', ['15m', '1h', '4h', '1d'])
def test_structural_grading_captured_btc_feed(monkeypatch, tf, capsys):
    """Later public-feed capture truncated to the rejection's completed bars.

    This checks detector grading on real prices, not a replay of the original scan.
    """
    import json
    from collections import Counter
    from pathlib import Path
    from backend.services.smc_service import SMCDetectionService
    from backend.shared.config.smc_config import get_tf_smc_config
    from backend.indicators.volatility import compute_atr
    payload = json.loads((Path(__file__).resolve().parents[3] / 'docs/audits/structural_gate_2026-10-10' / f'btc_{tf}.json').read_text())
    df = pd.DataFrame(payload['candles'])
    df.index = pd.to_datetime(df.pop('timestamp'), utc=True)
    duration = pd.Timedelta({'15m': '15min', '1h': '1h', '4h': '4h', '1d': '1D'}[tf])
    df = df[df.index + duration <= pd.Timestamp(payload['capture']['analysis_cutoff'])]
    config = SMCDetectionService(mode='stealth')._create_tf_smc_config(get_tf_smc_config(tf, 'stealth'))
    events = detect_structural_breaks(df, config, mode_profile='stealth_balanced')
    from backend.strategy.smc import bos_choch
    from backend.shared.config.smc_config import scale_lookback
    import bisect
    lookback = scale_lookback(config.structure_swing_lookback, bos_choch._infer_timeframe(df))
    highs, lows = bos_choch._detect_swing_highs(df, lookback), bos_choch._detect_swing_lows(df, lookback)
    kinds, levels, indices = bos_choch._build_swing_sequence(highs, lows)
    raw = Counter()
    for timestamp, row in df.iterrows():
        pos = bisect.bisect_right(indices, timestamp)
        kind, direction, _, _ = bos_choch._detect_bos_choch_pattern(kinds[:pos], levels[:pos], indices[:pos], row.close, row.high, row.low)
        if kind:
            raw[(kind, direction)] += 1
    with monkeypatch.context() as m:
        m.setitem(MODE_VOLUME_REQUIREMENTS, 'stealth_balanced', {'require_volume': False})
        ungated = detect_structural_breaks(df, config, mode_profile='stealth_balanced')
    simple = detect_structural_breaks(df, config, mode_profile='intraday_aggressive')
    with capsys.disabled():
        print('STRUCTURAL_DIAGNOSTIC ' + json.dumps(dict(tf=tf, swings=[len(highs),len(lows)],
            initial=bos_choch._determine_initial_trend(highs,lows), raw_patterns={str(k):v for k,v in raw.items()},
            without_volume=len(ungated), simple_control=len(simple))))
    atr = compute_atr(df, period=14)
    mean_volume = df.volume.rolling(20).mean()
    expected = []
    for event in events:
        ratio = abs(df.loc[event.timestamp, 'close'] - event.level) / atr.loc[event.timestamp]
        grade = ('A' if ratio >= 2.5 * config.structure_min_break_distance_atr else
                 'B' if ratio >= 1.5 * config.structure_min_break_distance_atr else 'C')
        if df.loc[event.timestamp, 'volume'] / mean_volume.loc[event.timestamp] >= 2.:
            grade = {'C': 'B', 'B': 'A', 'A': 'A'}[grade]
        expected.append((event, grade, ratio))
    latest = {}
    for direction in ('bullish', 'bearish'):
        aligned = [row for row in expected if row[0].direction == direction]
        if aligned:
            event, grade, ratio = max(aligned, key=lambda row: row[0].timestamp)
            latest[direction] = dict(timestamp=event.timestamp.isoformat(), kind=event.break_type,
                                     actual_grade=event.grade, expected_grade=grade, distance_atr=ratio)
    with capsys.disabled():
        print('STRUCTURAL_CAPTURE ' + json.dumps(dict(tf=tf, candles=len(df), events=len(events),
            grades=dict(Counter(e.grade for e in events)), latest=latest)))
    assert events, 'Captured real feed must exercise actual four-swing emissions'
    assert all(e.grade == grade for e, grade, _ in expected)
    assert all(e.break_distance_atr == pytest.approx(ratio) for e, _, ratio in expected)
