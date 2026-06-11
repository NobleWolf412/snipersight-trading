"""
Phase 4D: OB freshness/mitigation recomputation regression.

The wall-clock fix in smc_service.py uses:
    replace(ob, freshness_score=calculate_freshness(ob, datetime.now()))
This file proves:
1. dataclasses.replace() preserves source + wick_agreement (4C fields survive chain)
2. calculate_freshness() returns a measurably decayed value for old OBs (not frozen at 100)
3. Negative: freshness is NOT 100 for a 24h-old OB (decay fires)
4. Bull/bear symmetry: decay applies to both OB directions
"""
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from backend.shared.models.smc import OrderBlock
from backend.strategy.smc.order_blocks import calculate_freshness


def _ob(direction: str, timeframe: str = "1h", freshness_score: float = 100.0) -> OrderBlock:
    return OrderBlock(
        timeframe=timeframe,
        direction=direction,
        high=101.0,
        low=99.0,
        timestamp=datetime(2024, 1, 1, 0, 0, 0),
        displacement_strength=60.0,
        mitigation_level=0.0,
        freshness_score=freshness_score,
        source="structural",
        wick_agreement=True,
    )


# ── 1. replace() chain preserves 4C fields ─────────────────────────────────


def test_replace_preserves_source_bullish():
    """replace(ob, freshness_score=X) must not drop ob.source."""
    ob = _ob("bullish")
    updated = replace(ob, freshness_score=50.0)
    assert updated.source == "structural"


def test_replace_preserves_wick_agreement_bullish():
    """replace() must not drop ob.wick_agreement."""
    ob = _ob("bullish")
    updated = replace(ob, freshness_score=50.0)
    assert updated.wick_agreement is True


def test_replace_preserves_source_bearish():
    ob = _ob("bearish")
    updated = replace(ob, freshness_score=50.0)
    assert updated.source == "structural"


def test_replace_preserves_wick_agreement_bearish():
    ob = _ob("bearish")
    updated = replace(ob, freshness_score=50.0)
    assert updated.wick_agreement is True


def test_replace_chain_mitigation_then_freshness_preserves_source():
    """Two-step replace chain (mitigation then freshness) preserves source."""
    ob = _ob("bullish")
    after_mitigation = replace(ob, mitigation_level=0.2)
    after_freshness = replace(after_mitigation, freshness_score=75.0)
    assert after_freshness.source == "structural"
    assert after_freshness.wick_agreement is True
    assert after_freshness.mitigation_level == pytest.approx(0.2)


def test_replace_chain_lifecycle_then_freshness_preserves_source():
    """Two-step replace chain (breaker lifecycle then freshness) preserves source."""
    ob = _ob("bullish")
    after_lifecycle = replace(ob, breaker=True, invalidated=False)
    after_freshness = replace(after_lifecycle, freshness_score=60.0)
    assert after_freshness.source == "structural"
    assert after_freshness.wick_agreement is True
    assert after_freshness.breaker is True


# ── 2. calculate_freshness decays for aged OBs ─────────────────────────────


def test_freshness_decays_for_24h_old_ob_bullish():
    """1h OB (half-life=48h): 24h old → freshness = 2^(-24/48)*100 ≈ 70.7, not 100."""
    ob = _ob("bullish", timeframe="1h", freshness_score=100.0)
    current_time = ob.timestamp + timedelta(hours=24)
    result = calculate_freshness(ob, current_time)
    assert result < 95.0, f"Expected freshness ≈ 70.7, got {result}"
    assert result > 0.0


def test_freshness_decays_for_24h_old_ob_bearish():
    ob = _ob("bearish", timeframe="1h", freshness_score=100.0)
    current_time = ob.timestamp + timedelta(hours=24)
    result = calculate_freshness(ob, current_time)
    assert result < 95.0
    assert result > 0.0


def test_freshness_not_frozen_at_100_after_replace_bullish():
    """The wall-clock fix: replace(ob, freshness_score=calculate_freshness(ob, now)).
    Proves the fix produces non-100 freshness for a 24h-old OB."""
    ob = _ob("bullish", timeframe="1h", freshness_score=100.0)
    current_time = ob.timestamp + timedelta(hours=24)
    new_freshness = calculate_freshness(ob, current_time)
    updated = replace(ob, freshness_score=new_freshness)
    assert updated.freshness_score < 95.0, (
        f"freshness must be updated from 100.0; got {updated.freshness_score}"
    )


def test_freshness_not_frozen_at_100_after_replace_bearish():
    ob = _ob("bearish", timeframe="1h", freshness_score=100.0)
    current_time = ob.timestamp + timedelta(hours=24)
    new_freshness = calculate_freshness(ob, current_time)
    updated = replace(ob, freshness_score=new_freshness)
    assert updated.freshness_score < 95.0


def test_freshness_approaches_100_for_brand_new_ob():
    """Freshness starts near 100 for a just-formed OB (wall-clock seconds old)."""
    ob = _ob("bullish", timeframe="1h", freshness_score=100.0)
    current_time = ob.timestamp + timedelta(seconds=10)
    result = calculate_freshness(ob, current_time)
    # 10s old with 48h half-life: 2^(-10/172800)*100 ≈ 99.996
    assert result > 99.0


def test_brand_new_ob_is_not_decayed_below_threshold():
    """Negative: a 10s-old OB must NOT have freshness < 95.0 (no spurious decay)."""
    ob = _ob("bullish", timeframe="1h", freshness_score=100.0)
    current_time = ob.timestamp + timedelta(seconds=10)
    result = calculate_freshness(ob, current_time)
    assert result >= 95.0, f"Brand-new OB should not decay below 95.0; got {result}"
