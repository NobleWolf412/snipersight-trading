"""
Tests for IngestionPipeline.normalize_and_validate in-progress-candle strip.

Bug context — Adversarial review of cache-TTL fix (a61589c) Counter-argument
1: exchanges (Phemex, ccxt-backed) return the still-forming candle as the
last row of fetch_ohlcv. Caching that row + reading
`pct_change_last(df.tail(2))` downstream (orchestrator.py:3865) computes pct
change against a partial-candle close, producing phantom "strong" moves on
intrabar noise. The cache-TTL fix on its own can't eliminate this because
the cache locks in whatever the adapter delivered.

Fix: strip the last row of normalize_and_validate output if its timestamp
is in the current (still-open) candle's window. The cache then only holds
fully-closed candles, and `pct_change_last` always reads closed-to-closed.

Per CLAUDE.md §11 (silent-bug surfacing — partial-candle reads are silent).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from backend.data.ingestion_pipeline import IngestionPipeline


@pytest.fixture
def pipeline():
    """Pipeline with a stub adapter — normalize_and_validate doesn't call it."""
    return IngestionPipeline(adapter=MagicMock(), use_cache=False)


def _build_df(timestamps: list[datetime]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "timestamp": ts,
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1000.0,
            }
            for ts in timestamps
        ]
    )


# ──────────────────────────────────────────────────────────────────────
# Positive — in-progress candle IS stripped
# ──────────────────────────────────────────────────────────────────────


def test_strips_in_progress_1h_candle(pipeline):
    """Wall-clock is 09:30 UTC. The 09:00 candle is still in progress
    (opens at 09:00, closes at 10:00). normalize_and_validate must drop
    that last row so the cache only holds the 08:00 closed candle."""
    timestamps = [
        datetime(2026, 5, 23, 6, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 23, 7, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 23, 8, 0, tzinfo=timezone.utc),  # last closed
        datetime(2026, 5, 23, 9, 0, tzinfo=timezone.utc),  # in-progress
    ]
    df_in = _build_df(timestamps)
    wall_clock = datetime(2026, 5, 23, 9, 30, tzinfo=timezone.utc).timestamp()
    with patch("backend.data.ingestion_pipeline.time.time", return_value=wall_clock):
        df_out = pipeline.normalize_and_validate(df_in, "BTC/USDT", "1h")
    assert len(df_out) == 3, "in-progress 09:00 candle must be stripped"
    last_ts = pd.Timestamp(df_out["timestamp"].iloc[-1])
    assert last_ts.hour == 8, f"latest closed should be 08:00, got {last_ts}"


def test_strips_in_progress_5m_candle(pipeline):
    """5m mirror of the 1h positive test — confirms the formula scales."""
    timestamps = [
        datetime(2026, 5, 23, 9, 50, tzinfo=timezone.utc),
        datetime(2026, 5, 23, 9, 55, tzinfo=timezone.utc),  # last closed (09:55→10:00)
        datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),  # in-progress (opens 10:00)
    ]
    df_in = _build_df(timestamps)
    wall_clock = datetime(2026, 5, 23, 10, 2, tzinfo=timezone.utc).timestamp()
    with patch("backend.data.ingestion_pipeline.time.time", return_value=wall_clock):
        df_out = pipeline.normalize_and_validate(df_in, "BTC/USDT", "5m")
    assert len(df_out) == 2
    last_ts = pd.Timestamp(df_out["timestamp"].iloc[-1])
    assert last_ts.minute == 55, f"latest closed should be 09:55, got {last_ts}"


# ──────────────────────────────────────────────────────────────────────
# Negative — fully-closed candles are kept
# ──────────────────────────────────────────────────────────────────────


def test_keeps_all_closed_candles(pipeline):
    """Wall-clock 09:30. Latest row is 08:00 (already closed). All rows
    kept — no strip."""
    timestamps = [
        datetime(2026, 5, 23, 6, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 23, 7, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 23, 8, 0, tzinfo=timezone.utc),  # closed before wall_clock window
    ]
    df_in = _build_df(timestamps)
    wall_clock = datetime(2026, 5, 23, 9, 30, tzinfo=timezone.utc).timestamp()
    with patch("backend.data.ingestion_pipeline.time.time", return_value=wall_clock):
        df_out = pipeline.normalize_and_validate(df_in, "BTC/USDT", "1h")
    assert len(df_out) == 3
    last_ts = pd.Timestamp(df_out["timestamp"].iloc[-1])
    assert last_ts.hour == 8


def test_boundary_exact_open_strips(pipeline):
    """Wall-clock 09:00:01 — 09:00 candle JUST opened. Last row's open
    timestamp == current_open_epoch → strip."""
    timestamps = [
        datetime(2026, 5, 23, 7, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 23, 8, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 23, 9, 0, tzinfo=timezone.utc),  # just-opened candle
    ]
    df_in = _build_df(timestamps)
    wall_clock = datetime(2026, 5, 23, 9, 0, 1, tzinfo=timezone.utc).timestamp()
    with patch("backend.data.ingestion_pipeline.time.time", return_value=wall_clock):
        df_out = pipeline.normalize_and_validate(df_in, "BTC/USDT", "1h")
    assert len(df_out) == 2


def test_boundary_one_second_before_open_keeps(pipeline):
    """Wall-clock 08:59:59 — still inside the 08:00 candle window. Last
    row is the 08:00 candle (in progress). Should strip."""
    timestamps = [
        datetime(2026, 5, 23, 7, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 23, 8, 0, tzinfo=timezone.utc),  # in progress at 08:59:59
    ]
    df_in = _build_df(timestamps)
    wall_clock = datetime(2026, 5, 23, 8, 59, 59, tzinfo=timezone.utc).timestamp()
    with patch("backend.data.ingestion_pipeline.time.time", return_value=wall_clock):
        df_out = pipeline.normalize_and_validate(df_in, "BTC/USDT", "1h")
    assert len(df_out) == 1
    last_ts = pd.Timestamp(df_out["timestamp"].iloc[-1])
    assert last_ts.hour == 7


# ──────────────────────────────────────────────────────────────────────
# Defensive — unknown timeframe is a no-op
# ──────────────────────────────────────────────────────────────────────


def test_unknown_timeframe_skips_strip(pipeline):
    """If the timeframe isn't in the seconds table (e.g., a typo or new
    TF the bot doesn't recognize), the strip silently no-ops rather than
    breaking ingestion."""
    timestamps = [
        datetime(2026, 5, 23, 6, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 23, 7, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 23, 9, 0, tzinfo=timezone.utc),
    ]
    df_in = _build_df(timestamps)
    df_out = pipeline.normalize_and_validate(df_in, "BTC/USDT", "weird_tf")
    # No strip should occur — all 3 rows kept (no tf_seconds known)
    assert len(df_out) == 3
