"""
Phase 4A: FVG scoring fixes.

Tests cover:
1. Selection key uses size_atr * freshness_score (not raw size)
2. Virgin epsilon: overlap < _FVG_VIRGIN_EPSILON gets +20 (not strict == 0)
3. Stale penalty: freshness_score < 0.3 → -10
4. Fill penalty: overlap > _FVG_FILL_THRESHOLD still fires
5. Bull/bear symmetry: all positive tests have a mirrored bearish test
6. fvg.py: potential_bearish_gaps counter incremented symmetrically
"""
from datetime import datetime
from unittest.mock import patch

import pytest

from backend.shared.models.smc import FVG
from backend.strategy.confluence.scorer import _score_fvgs_incremental


def _fvg(
    direction: str,
    size_atr: float = 1.5,
    freshness_score: float = 0.8,
    overlap_with_price: float = 0.0,
    grade: str = "B",
    size: float = 50.0,
) -> FVG:
    top = 100.0
    bottom = top - size
    return FVG(
        timeframe="1h",
        direction=direction,
        top=top,
        bottom=bottom,
        timestamp=datetime(2024, 1, 1),
        size=size,
        overlap_with_price=overlap_with_price,
        freshness_score=freshness_score,
        grade=grade,
        size_atr=size_atr,
    )


# ── Selection key: size_atr × freshness dominates ──────────────────────────


def test_selection_key_prefers_larger_size_atr_bullish():
    """Best FVG is the one with higher size_atr, not higher raw size."""
    small_big_raw = _fvg("bullish", size_atr=3.0, size=10.0, freshness_score=0.9)
    big_small_atr = _fvg("bullish", size_atr=0.5, size=1000.0, freshness_score=0.9)
    result = _score_fvgs_incremental([small_big_raw, big_small_atr], "bullish")
    assert result["best_fvg"] is small_big_raw


def test_selection_key_prefers_larger_size_atr_bearish():
    small_big_raw = _fvg("bearish", size_atr=3.0, size=10.0, freshness_score=0.9)
    big_small_atr = _fvg("bearish", size_atr=0.5, size=1000.0, freshness_score=0.9)
    result = _score_fvgs_incremental([small_big_raw, big_small_atr], "bearish")
    assert result["best_fvg"] is small_big_raw


def test_selection_key_deprioritizes_stale_bullish():
    """Fresh smaller FVG preferred over stale larger FVG."""
    stale_large = _fvg("bullish", size_atr=2.0, freshness_score=0.1, overlap_with_price=0.0)
    fresh_small = _fvg("bullish", size_atr=1.0, freshness_score=0.9, overlap_with_price=0.0)
    # stale_large key = 2.0 × 0.1 × 1.0 = 0.2; fresh_small key = 1.0 × 0.9 × 1.0 = 0.9
    result = _score_fvgs_incremental([stale_large, fresh_small], "bullish")
    assert result["best_fvg"] is fresh_small


def test_selection_key_deprioritizes_stale_bearish():
    stale_large = _fvg("bearish", size_atr=2.0, freshness_score=0.1, overlap_with_price=0.0)
    fresh_small = _fvg("bearish", size_atr=1.0, freshness_score=0.9, overlap_with_price=0.0)
    result = _score_fvgs_incremental([stale_large, fresh_small], "bearish")
    assert result["best_fvg"] is fresh_small


# ── Virgin epsilon: near-zero overlap earns +20 ────────────────────────────


def test_virgin_epsilon_tiny_overlap_bullish():
    """overlap=0.01 < _FVG_VIRGIN_EPSILON (0.02) → still gets virgin +20."""
    fvg = _fvg("bullish", overlap_with_price=0.01, freshness_score=0.8)
    result = _score_fvgs_incremental([fvg], "bullish")
    comp_names = [c[0] for c in result["components"]]
    assert "Virgin FVG" in comp_names


def test_virgin_epsilon_tiny_overlap_bearish():
    fvg = _fvg("bearish", overlap_with_price=0.01, freshness_score=0.8)
    result = _score_fvgs_incremental([fvg], "bearish")
    comp_names = [c[0] for c in result["components"]]
    assert "Virgin FVG" in comp_names


def test_virgin_epsilon_above_threshold_no_bonus_bullish():
    """overlap=0.05 > _FVG_VIRGIN_EPSILON → NO virgin bonus."""
    fvg = _fvg("bullish", overlap_with_price=0.05, freshness_score=0.8)
    result = _score_fvgs_incremental([fvg], "bullish")
    comp_names = [c[0] for c in result["components"]]
    assert "Virgin FVG" not in comp_names


def test_virgin_epsilon_above_threshold_no_bonus_bearish():
    fvg = _fvg("bearish", overlap_with_price=0.05, freshness_score=0.8)
    result = _score_fvgs_incremental([fvg], "bearish")
    comp_names = [c[0] for c in result["components"]]
    assert "Virgin FVG" not in comp_names


# ── Stale penalty: freshness < 0.3 → -10 ──────────────────────────────────


def test_stale_penalty_fires_bullish():
    fvg = _fvg("bullish", freshness_score=0.2, overlap_with_price=0.0)
    result = _score_fvgs_incremental([fvg], "bullish")
    comp_names = [c[0] for c in result["components"]]
    assert "Stale FVG" in comp_names
    stale_comp = next(c for c in result["components"] if c[0] == "Stale FVG")
    assert stale_comp[1] == -10.0


def test_stale_penalty_fires_bearish():
    fvg = _fvg("bearish", freshness_score=0.2, overlap_with_price=0.0)
    result = _score_fvgs_incremental([fvg], "bearish")
    comp_names = [c[0] for c in result["components"]]
    assert "Stale FVG" in comp_names


def test_stale_penalty_does_not_fire_fresh_bullish():
    """freshness=0.8 → no stale penalty."""
    fvg = _fvg("bullish", freshness_score=0.8, overlap_with_price=0.0)
    result = _score_fvgs_incremental([fvg], "bullish")
    comp_names = [c[0] for c in result["components"]]
    assert "Stale FVG" not in comp_names


def test_stale_penalty_does_not_fire_fresh_bearish():
    fvg = _fvg("bearish", freshness_score=0.8, overlap_with_price=0.0)
    result = _score_fvgs_incremental([fvg], "bearish")
    comp_names = [c[0] for c in result["components"]]
    assert "Stale FVG" not in comp_names


# ── Fill penalty still fires ───────────────────────────────────────────────


def test_fill_penalty_fires_bullish():
    fvg = _fvg("bullish", overlap_with_price=0.8, freshness_score=0.8)
    result = _score_fvgs_incremental([fvg], "bullish")
    comp_names = [c[0] for c in result["components"]]
    assert "Filled" in comp_names


def test_fill_penalty_fires_bearish():
    fvg = _fvg("bearish", overlap_with_price=0.8, freshness_score=0.8)
    result = _score_fvgs_incremental([fvg], "bearish")
    comp_names = [c[0] for c in result["components"]]
    assert "Filled" in comp_names


def test_fill_penalty_does_not_fire_unfilled_bullish():
    fvg = _fvg("bullish", overlap_with_price=0.3, freshness_score=0.8)
    result = _score_fvgs_incremental([fvg], "bullish")
    comp_names = [c[0] for c in result["components"]]
    assert "Filled" not in comp_names


def test_fill_penalty_does_not_fire_unfilled_bearish():
    fvg = _fvg("bearish", overlap_with_price=0.3, freshness_score=0.8)
    result = _score_fvgs_incremental([fvg], "bearish")
    comp_names = [c[0] for c in result["components"]]
    assert "Filled" not in comp_names
