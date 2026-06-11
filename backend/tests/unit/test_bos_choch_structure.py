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

    def test_4swing_ranging_resolves_and_emits(self, fourswing_profile, caplog):
        df = _df_from_closes(_ranging_4swing_closes())
        with caplog.at_level(logging.INFO, logger="backend.strategy.smc.bos_choch"):
            breaks = detect_structural_breaks(
                df, {"swing_lookback": 3}, mode_profile=fourswing_profile
            )
        assert len(breaks) >= 1, "4swing ranging start must resolve and then emit"
        assert all(b.direction == "bullish" and b.break_type == "BOS" for b in breaks)
        assert "RANGING resolved to uptrend" in caplog.text
        assert "4swing" in caplog.text
        # Resolving candle (idx49, first close > h2) suppressed; emission starts after.
        assert all(b.timestamp > df.index[49].to_pydatetime() for b in breaks)


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
