"""
Phase 3 regression: BOS → Grade-A Order Block linkage (2026-06-11).

Pins the pipeline seam that drives the Phase-0 "stealth/overwatch Grade-A
starvation" finding: `detect_structural_breaks` emits breaks; `detect_obs_from_bos`
mints structure-confirmed (Grade A) OBs ONLY from emitted breaks. If break emission
is wrongly suppressed (garbled CHoCH conditions, ranging deadlock, volume gates),
the Grade-A OB pool starves for that mode.

Verifies:
- A clean simple-mode bullish BOS produces ≥1 bullish Grade-A OB whose candle is
  strictly BEFORE the BOS timestamp (temporal-prior = "BOS ordering" standing fix)
- Exact bearish mirror
- stealth_balanced (4swing + volume 1.3x) CAN produce BOS-linked Grade-A OBs when
  volume genuinely confirms — encodes Phase-0 §0.4 as a regression
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.strategy.smc.bos_choch import detect_structural_breaks
from backend.strategy.smc.order_blocks import detect_obs_from_bos

from backend.tests.unit.test_bos_choch_structure import (
    _df_from_closes,
    _macro_4swing_closes,
    _ramp,
)


def _simple_bullish_df() -> pd.DataFrame:
    """Uptrend seed; red descent into a higher low; rise capped below the swing
    high; breakout at idx34. The descent candles (red) sit within the OB lookback
    window of the BOS candle."""
    closes = [95.0]
    closes += _ramp(95, 105, 8)        # peak 1 @ idx8
    closes += _ramp(105, 95, 8)        # trough 1 @ idx16
    closes += _ramp(95, 105, 8)        # peak 2 @ idx24 (equal highs)
    closes += _ramp(105, 98, 6)        # red descent → trough 2 @ idx30 (higher low)
    closes += _ramp(98, 103, 3)        # green rise idx31-33, below swing high
    closes += [110.0, 112.0, 114.0, 116.0]  # breakout idx34-37 (all green)
    closes += [116.0] * 3              # tail
    return _df_from_closes(closes)


class TestBosObLinkageBullish:
    def test_bullish_bos_produces_grade_a_ob_before_break(self):
        df = _simple_bullish_df()
        breaks = detect_structural_breaks(df, {"swing_lookback": 3})
        bos = [b for b in breaks if b.break_type == "BOS" and b.direction == "bullish"]
        assert len(bos) >= 1, "fixture must produce at least one bullish BOS"

        obs = detect_obs_from_bos(df, breaks, {"swing_lookback": 3})
        assert len(obs) >= 1, (
            "bullish BOS with a red candle in lookback range must mint an OB — "
            "the BOS→OB linkage is broken"
        )
        assert all(ob.direction == "bullish" for ob in obs)
        assert any(ob.grade == "A" for ob in obs), (
            "structure-confirmed OB with strong displacement must be Grade A"
        )
        # Temporal-prior guard (BOS ordering standing fix): the OB candle must
        # precede the break that confirmed it.
        first_bos_ts = min(b.timestamp for b in bos)
        first_ob = min(obs, key=lambda o: o.timestamp)
        assert first_ob.timestamp < first_bos_ts, (
            "OB candle must be strictly BEFORE its confirming BOS"
        )

    def test_bearish_mirror_produces_grade_a_ob(self):
        closes = [200.0 - c for c in _simple_bullish_df()["close"].tolist()]
        df = _df_from_closes(closes)
        breaks = detect_structural_breaks(df, {"swing_lookback": 3})
        bos = [b for b in breaks if b.break_type == "BOS" and b.direction == "bearish"]
        assert len(bos) >= 1, "mirrored fixture must produce at least one bearish BOS"

        obs = detect_obs_from_bos(df, breaks, {"swing_lookback": 3})
        assert len(obs) >= 1
        assert all(ob.direction == "bearish" for ob in obs)
        assert any(ob.grade == "A" for ob in obs)
        first_bos_ts = min(b.timestamp for b in bos)
        first_ob = min(obs, key=lambda o: o.timestamp)
        assert first_ob.timestamp < first_bos_ts


class TestStealthGradeALinkage:
    """Phase-0 §0.4 regression: stealth (4swing + volume) must remain CAPABLE of
    minting BOS-linked Grade-A OBs when volume genuinely confirms the break."""

    def test_stealth_volume_confirmed_bos_mints_grade_a_ob(self):
        closes = _macro_4swing_closes(with_red_dip=True)
        vols = [1000.0] * len(closes)
        for i in (27, 28, 29, 30):
            vols[i] = 5000.0           # breakout volume ~4x avg ≥ stealth's 1.3x
        df = _df_from_closes(closes, vols)

        breaks = detect_structural_breaks(
            df, {"swing_lookback": 3}, mode_profile="stealth_balanced"
        )
        bos = [b for b in breaks if b.break_type == "BOS" and b.direction == "bullish"]
        assert len(bos) >= 1, (
            "stealth 4swing BOS with confirming volume must be emitted — if this "
            "fails, the Grade-A starvation root cause has regressed"
        )

        obs = detect_obs_from_bos(df, breaks, {"swing_lookback": 3})
        grade_a = [ob for ob in obs if ob.grade == "A" and ob.direction == "bullish"]
        assert len(grade_a) >= 1, (
            "stealth must be able to produce BOS-linked Grade-A OBs (Phase-0 §0.4)"
        )
        first_bos_ts = min(b.timestamp for b in bos)
        assert all(ob.timestamp < first_bos_ts for ob in grade_a), (
            "every Grade-A OB candle must precede the confirming BOS (temporal-prior)"
        )

    def test_stealth_low_volume_bos_suppressed_no_ob(self):
        """Negative pair: without confirming volume, stealth emits no BOS and
        therefore mints no structure-confirmed OB (current design — flagged in the
        Phase 3 decisions log as starvation co-cause, propose-don't-apply)."""
        closes = _macro_4swing_closes(with_red_dip=True)
        df = _df_from_closes(closes)   # constant volume → ratio 1.0 < 1.3
        breaks = detect_structural_breaks(
            df, {"swing_lookback": 3}, mode_profile="stealth_balanced"
        )
        assert [b for b in breaks if b.break_type == "BOS"] == []
        obs = detect_obs_from_bos(df, breaks, {"swing_lookback": 3})
        assert obs == []
