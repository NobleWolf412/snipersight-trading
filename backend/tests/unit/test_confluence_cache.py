"""
Tests for backend.strategy.confluence.cache.

Covers:
  - Basic record/get round-trip.
  - Symmetry: bullish and bearish breakdowns are stored and retrievable.
  - Visibility counters increment correctly.
  - Ring buffer eviction at capacity.
  - Empty / malformed inputs are handled without raising.
  - Distribution aggregation over a heterogeneous sample.
"""

from __future__ import annotations

import pytest

from backend.shared.models.scoring import ConfluenceBreakdown, ConfluenceFactor
from backend.strategy.confluence import cache


def _make_breakdown(symbol: str, direction: str, score: float = 72.0) -> ConfluenceBreakdown:
    factors = [
        ConfluenceFactor(name="structure", score=80.0, weight=0.4, rationale="BOS confirmed"),
        ConfluenceFactor(name="momentum",  score=70.0, weight=0.3, rationale="MACD aligned"),
        ConfluenceFactor(name="volume",    score=65.0, weight=0.3, rationale="Volume above avg"),
    ]
    return ConfluenceBreakdown(
        total_score=score,
        factors=factors,
        synergy_bonus=2.0,
        conflict_penalty=1.0,
        regime="trend",
        htf_aligned=True,
        btc_impulse_gate=True,
        symbol=symbol,
        direction=direction,
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def test_record_and_get_roundtrip():
    br = _make_breakdown("BTC/USDT", "bullish")
    assert cache.record("BTC/USDT_42_15m_long", br) is True
    fetched = cache.get("BTC/USDT_42_15m_long")
    assert fetched is br


def test_symmetry_bullish_and_bearish_both_recorded():
    """Both directions must round-trip through the cache identically."""
    bull_br = _make_breakdown("ETH/USDT", "bullish", score=74.0)
    bear_br = _make_breakdown("ETH/USDT", "bearish", score=68.0)

    bull_id = "ETH/USDT_99_4h_long"
    bear_id = "ETH/USDT_99_4h_short"

    assert cache.record(bull_id, bull_br) is True
    assert cache.record(bear_id, bear_br) is True

    fetched_bull = cache.get(bull_id)
    fetched_bear = cache.get(bear_id)
    assert fetched_bull is bull_br
    assert fetched_bear is bear_br
    assert fetched_bull.direction == "bullish"
    assert fetched_bear.direction == "bearish"

    stats = cache.stats()
    assert stats["records_total"] == 2
    assert stats["lookups_total"] == 2
    assert stats["lookup_misses_total"] == 0


def test_get_returns_most_recent_when_id_collides():
    """If two breakdowns share an id, get() should return the newest."""
    first = _make_breakdown("SOL/USDT", "bullish", score=60.0)
    second = _make_breakdown("SOL/USDT", "bullish", score=78.0)
    sid = "SOL/USDT_5_1h_long"
    cache.record(sid, first)
    cache.record(sid, second)
    assert cache.get(sid) is second


def test_record_with_empty_id_returns_false_and_increments_error():
    br = _make_breakdown("BTC/USDT", "bullish")
    assert cache.record("", br) is False
    assert cache.record(None, br) is False  # type: ignore[arg-type]
    stats = cache.stats()
    assert stats["records_total"] == 0
    assert stats["record_errors_total"] == 2


def test_record_with_none_breakdown_returns_false():
    assert cache.record("X_1_5m_long", None) is False  # type: ignore[arg-type]
    assert cache.stats()["record_errors_total"] == 1


def test_get_unknown_id_returns_none_and_counts_miss():
    cache.record("X_1_5m_long", _make_breakdown("X/USDT", "bullish"))
    assert cache.get("does_not_exist") is None
    stats = cache.stats()
    assert stats["lookups_total"] == 1
    assert stats["lookup_misses_total"] == 1


def test_ring_buffer_eviction_at_capacity():
    """Buffer at capacity should drop oldest, not raise."""
    capacity = cache._BUFFER_SIZE  # type: ignore[attr-defined]
    for i in range(capacity + 5):
        cache.record(f"X/USDT_{i}_5m_long", _make_breakdown("X/USDT", "bullish"))
    # First 5 should have been evicted.
    assert cache.get("X/USDT_0_5m_long") is None
    assert cache.get("X/USDT_4_5m_long") is None
    assert cache.get(f"X/USDT_{capacity + 4}_5m_long") is not None
    assert cache.stats()["buffer_size"] == capacity


def test_distribution_aggregates_factor_contributions():
    for i in range(10):
        br = _make_breakdown("BTC/USDT", "bullish", score=70 + i)
        cache.record(f"BTC/USDT_{i}_15m_long", br)
    dist = cache.aggregate_distribution(n=10)
    assert dist["sample_count"] == 10
    # Average total_score = mean(70..79) = 74.5
    assert dist["avg_total_score"] == pytest.approx(74.5)
    assert dist["avg_synergy_bonus"] == pytest.approx(2.0)
    assert dist["avg_conflict_penalty"] == pytest.approx(1.0)
    factor_names = {f["name"] for f in dist["factors"]}
    assert factor_names == {"structure", "momentum", "volume"}
    # Highest weighted score factor should sort first.
    assert dist["factors"][0]["name"] == "structure"


def test_distribution_with_empty_buffer_returns_zeros():
    dist = cache.aggregate_distribution(n=10)
    assert dist["sample_count"] == 0
    assert dist["avg_total_score"] == 0.0
    assert dist["factors"] == []
