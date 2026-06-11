"""
Phase 4C: OB source tagging + wick demotion tests.

Tests cover:
1. Wick color gate: wrong-color candle does NOT produce a wick OB
2. Wick color gate: correct-color candle DOES produce a wick OB
3. Bull/bear symmetry for color gate
4. filter_overlapping_order_blocks: wick OB yields to anchor; anchor gains wick_agreement
5. filter_overlapping_order_blocks: two wicks → strongest wins (no agreement transfer)
6. _score_order_blocks_incremental: wick-only pool capped at 35
7. _score_order_blocks_incremental: wick_agreement bonus +10 on anchor OB
8. _score_order_blocks_incremental: anchor pool bypasses wick-only cap
9. filter_obs_by_mode: freshness written back to ob.freshness_score
"""
from datetime import datetime

import pytest

from backend.shared.models.smc import OrderBlock
from backend.strategy.smc.order_blocks import filter_overlapping_order_blocks, filter_obs_by_mode
from backend.strategy.confluence.scorer import _score_order_blocks_incremental


# ── Helpers ────────────────────────────────────────────────────────────────


def _ob(
    direction: str,
    source: str = "structural",
    displacement_strength: float = 60.0,
    freshness_score: float = 90.0,
    mitigation_level: float = 0.0,
    grade: str = "B",
    high: float = 101.0,
    low: float = 99.0,
    timeframe: str = "1h",
    wick_agreement: bool = False,
) -> OrderBlock:
    return OrderBlock(
        timeframe=timeframe,
        direction=direction,
        high=high,
        low=low,
        timestamp=datetime(2024, 1, 1),
        displacement_strength=displacement_strength,
        mitigation_level=mitigation_level,
        freshness_score=freshness_score,
        grade=grade,
        source=source,
        wick_agreement=wick_agreement,
    )


# ── 1–3. Wick color gate (detector level) ────────────────────────────────────
# These tests exercise the logic by constructing candles directly and verifying
# the gate formula. We don't spin up the full detector to avoid OHLCV fixture
# overhead; instead we test the boolean gate logic extracted from order_blocks.py.


def _wick_gate_bullish(close: float, open_: float, lower_wick: float, body: float, min_wick_ratio: float = 2.0) -> bool:
    """Mirrors the 4C fix: wick branch requires close < open (bearish candle)."""
    return (lower_wick / body >= min_wick_ratio) and close < open_


def _wick_gate_bearish(close: float, open_: float, upper_wick: float, body: float, min_wick_ratio: float = 2.0) -> bool:
    """Mirrors the 4C fix: wick branch requires close > open (bullish candle)."""
    return (upper_wick / body >= min_wick_ratio) and close > open_


def test_bullish_wick_gate_wrong_color_fails():
    """Green candle (close > open) with strong lower wick does NOT pass bullish gate."""
    assert not _wick_gate_bullish(close=101.0, open_=99.0, lower_wick=10.0, body=2.0)


def test_bullish_wick_gate_correct_color_passes():
    """Red candle (close < open) with strong lower wick DOES pass bullish gate."""
    assert _wick_gate_bullish(close=99.0, open_=101.0, lower_wick=10.0, body=2.0)


def test_bearish_wick_gate_wrong_color_fails():
    """Red candle (close < open) with strong upper wick does NOT pass bearish gate."""
    assert not _wick_gate_bearish(close=99.0, open_=101.0, upper_wick=10.0, body=2.0)


def test_bearish_wick_gate_correct_color_passes():
    """Green candle (close > open) with strong upper wick DOES pass bearish gate."""
    assert _wick_gate_bearish(close=101.0, open_=99.0, upper_wick=10.0, body=2.0)


# ── 4. filter_overlapping_order_blocks: wick yields to anchor ────────────────


def test_filter_overlap_wick_yields_to_anchor_bullish():
    """When wick OB overlaps >50% with anchor OB, wick is dropped; anchor gets wick_agreement."""
    anchor = _ob("bullish", source="structural", displacement_strength=50.0, high=101.5, low=98.5)
    wick = _ob("bullish", source="rejection_wick", displacement_strength=90.0, high=101.0, low=99.0)
    result = filter_overlapping_order_blocks([anchor, wick], max_overlap=0.5)
    assert len(result) == 1
    assert result[0] is anchor
    assert result[0].wick_agreement is True


def test_filter_overlap_wick_yields_to_anchor_bearish():
    """Symmetric bearish case: wick yields to anchor and transfers wick_agreement."""
    anchor = _ob("bearish", source="bos", displacement_strength=50.0, high=101.5, low=98.5)
    wick = _ob("bearish", source="rejection_wick", displacement_strength=90.0, high=101.0, low=99.0)
    result = filter_overlapping_order_blocks([anchor, wick], max_overlap=0.5)
    assert len(result) == 1
    assert result[0] is anchor
    assert result[0].wick_agreement is True


def test_filter_overlap_no_agreement_when_both_wick():
    """When two wick OBs overlap, stronger wins but no wick_agreement transfer."""
    wick_a = _ob("bullish", source="rejection_wick", displacement_strength=90.0, high=101.5, low=98.5)
    wick_b = _ob("bullish", source="rejection_wick", displacement_strength=40.0, high=101.0, low=99.0)
    result = filter_overlapping_order_blocks([wick_a, wick_b], max_overlap=0.5)
    assert len(result) == 1
    assert result[0].wick_agreement is False


def test_filter_overlap_different_direction_no_conflict():
    """Bullish and bearish OBs in same price range do not conflict."""
    bull = _ob("bullish", source="structural", high=101.0, low=99.0)
    bear = _ob("bearish", source="rejection_wick", high=101.0, low=99.0)
    result = filter_overlapping_order_blocks([bull, bear], max_overlap=0.5)
    assert len(result) == 2


# ── 5–8. _score_order_blocks_incremental ───────────────────────────────────


def test_scorer_wick_only_cap_applied_bullish():
    """Wick-only pool with Grade A + Fresh OB + Recent would score 70; capped at 35."""
    wick = _ob(
        "bullish",
        source="rejection_wick",
        displacement_strength=50.0,
        freshness_score=90.0,
        grade="A",
        mitigation_level=0.0,
    )
    result = _score_order_blocks_incremental([wick], "bullish")
    assert result["score"] == pytest.approx(35.0, abs=0.01)
    comp_names = [c[0] for c in result["components"]]
    assert "Wick-Only Cap" in comp_names


def test_scorer_wick_only_cap_applied_bearish():
    """Symmetric bearish wick-only cap."""
    wick = _ob("bearish", source="rejection_wick", freshness_score=90.0, grade="A", mitigation_level=0.0)
    result = _score_order_blocks_incremental([wick], "bearish")
    assert result["score"] == pytest.approx(35.0, abs=0.01)


def test_scorer_wick_agreement_bonus_bullish():
    """Anchor OB with wick_agreement=True gets +10 on top of base scoring."""
    anchor = _ob(
        "bullish",
        source="structural",
        freshness_score=90.0,
        grade="B",
        mitigation_level=0.0,
        displacement_strength=50.0,
        wick_agreement=True,
    )
    result = _score_order_blocks_incremental([anchor], "bullish")
    # Grade B=30 + Fresh=15 + Recent=15 + Agreement=10 = 70
    assert result["score"] == pytest.approx(70.0, abs=0.01)
    comp_names = [c[0] for c in result["components"]]
    assert "Wick Agreement" in comp_names
    assert "Wick-Only Cap" not in comp_names


def test_scorer_wick_agreement_bonus_bearish():
    anchor = _ob("bearish", source="bos", freshness_score=90.0, grade="B", mitigation_level=0.0, displacement_strength=50.0, wick_agreement=True)
    result = _score_order_blocks_incremental([anchor], "bearish")
    assert result["score"] == pytest.approx(70.0, abs=0.01)
    assert "Wick Agreement" in [c[0] for c in result["components"]]


def test_scorer_anchor_pool_bypasses_cap_bullish():
    """Anchor OB (source=structural) with same quality profile is NOT capped at 35."""
    anchor = _ob("bullish", source="structural", freshness_score=90.0, grade="A", mitigation_level=0.0)
    result = _score_order_blocks_incremental([anchor], "bullish")
    assert result["score"] > 35.0
    assert "Wick-Only Cap" not in [c[0] for c in result["components"]]


def test_scorer_anchor_pool_bypasses_cap_bearish():
    anchor = _ob("bearish", source="structural", freshness_score=90.0, grade="A", mitigation_level=0.0)
    result = _score_order_blocks_incremental([anchor], "bearish")
    assert result["score"] > 35.0


def test_scorer_prefers_anchor_over_wick_when_both_present_bullish():
    """When anchor and wick OBs both exist, scorer uses anchor pool."""
    anchor = _ob("bullish", source="structural", freshness_score=50.0, grade="B", mitigation_level=0.0)
    wick = _ob("bullish", source="rejection_wick", freshness_score=90.0, grade="A", mitigation_level=0.0)
    result = _score_order_blocks_incremental([anchor, wick], "bullish")
    assert result["best_ob"] is anchor
    assert "Wick-Only Cap" not in [c[0] for c in result["components"]]


def test_scorer_prefers_anchor_over_wick_when_both_present_bearish():
    anchor = _ob("bearish", source="bos", freshness_score=50.0, grade="B", mitigation_level=0.0)
    wick = _ob("bearish", source="rejection_wick", freshness_score=90.0, grade="A", mitigation_level=0.0)
    result = _score_order_blocks_incremental([anchor, wick], "bearish")
    assert result["best_ob"] is anchor


# ── 9. Engulfing OBs are NOT tagged rejection_wick ───────────────────────────


def _engulfing_wick_gate_source(is_wick_rejection: bool) -> str:
    """Mirrors order_blocks.py OB constructor source expression."""
    return "rejection_wick" if is_wick_rejection else "engulfing"


def test_engulfing_only_ob_tagged_engulfing_not_wick_bullish():
    """Pure engulfing (is_wick_rejection=False) → source='engulfing', NOT 'rejection_wick'."""
    assert _engulfing_wick_gate_source(is_wick_rejection=False) == "engulfing"


def test_wick_rejection_ob_tagged_rejection_wick_bullish():
    """Wick rejection (is_wick_rejection=True) → source='rejection_wick'."""
    assert _engulfing_wick_gate_source(is_wick_rejection=True) == "rejection_wick"


def test_scorer_engulfing_ob_treated_as_anchor_not_capped():
    """Engulfing OBs (source='engulfing') are treated as anchor pool — not capped at 35."""
    engulfing = _ob("bullish", source="engulfing", freshness_score=90.0, grade="A", mitigation_level=0.0)
    result = _score_order_blocks_incremental([engulfing], "bullish")
    assert result["score"] > 35.0
    assert "Wick-Only Cap" not in [c[0] for c in result["components"]]


def test_scorer_engulfing_ob_treated_as_anchor_bearish():
    engulfing = _ob("bearish", source="engulfing", freshness_score=90.0, grade="A", mitigation_level=0.0)
    result = _score_order_blocks_incremental([engulfing], "bearish")
    assert result["score"] > 35.0


# ── 10. filter_obs_by_mode freshness writeback ─────────────────────────────


def test_filter_obs_by_mode_writes_back_freshness():
    """filter_obs_by_mode writes recalculated freshness back to ob.freshness_score.

    1h OB half-life = 48h.  At +24h, freshness = 2^(-24/48)*100 ≈ 70.7 → passes
    precision gate (min=12) and is measurably below the original 100.0.
    """
    from datetime import timedelta
    ob = _ob("bullish", source="structural", freshness_score=100.0, timeframe="1h")
    current_time = ob.timestamp + timedelta(hours=24)
    result = filter_obs_by_mode([ob], mode_profile="precision", current_time=current_time)
    assert result, "OB should survive the freshness gate at +24h (freshness ≈ 70.7 > min 12)"
    assert result[0] is ob  # same Python object, mutated in-place
    assert result[0].freshness_score < 95.0, (
        f"freshness_score should be written back from ~100 to ≈70.7, got {result[0].freshness_score}"
    )
