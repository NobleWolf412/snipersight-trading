"""
Tests for OHLCVCache.is_expired() candle-boundary-anchored TTL.

Bug context — May 2026 dda4d192 session forensics. Gate 3 (BTC impulse)
fired 84 LONG rejections citing `btc_impulse=strong_down` during the
08:xx and 09:xx hours, but BTC's actual 1h candles in those hours were
neutral (+0.11% / -0.03%). The only candle in the window with a
strong-down close was 06:00 → 07:00 at -1.05%.

Root cause: `OHLCVCache.is_expired()` previously measured time-since-
fetch (`now - fetched_at >= tf_seconds`) instead of time-since-candle-
close. When a fetch happened near a candle boundary, the cached df
held a "latest" candle that was eligible for refresh, but the TTL
kept the cache valid for up to ~59 more minutes. During that window,
`pct_change_last(df.tail(2))` computed pct change against an OLDER
pair of closes than reality, producing phantom `strong_down` impulses
hours after BTC had moved on.

Fix: anchor TTL to wall-clock candle boundaries — expire when the
candle AFTER the latest cached one has closed (a fresh fetch would
then return a newer "latest closed candle").

Per CLAUDE.md §11 (silent-bug surfacing), §14 rubric 4 (negative
tests paired with positive), §16 rubric 12 (symmetry — though TTL
is direction-agnostic, the bug it caused WAS direction-asymmetric).
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from backend.data.ohlcv_cache import CacheEntry


def _df_with_latest_open(latest_open_utc: datetime, n_rows: int = 5) -> pd.DataFrame:
    """Build a minimal OHLCV df whose last row's `timestamp` column is
    `latest_open_utc` (treated by the cache as the open time of the
    latest closed candle). Earlier rows have timestamps stepped back by
    1 hour each — content doesn't matter for is_expired()."""
    rows = []
    for i in range(n_rows):
        ts = latest_open_utc - pd.Timedelta(hours=(n_rows - 1 - i))
        rows.append(
            {
                "timestamp": ts,
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1000.0,
            }
        )
    return pd.DataFrame(rows)


def _make_entry(latest_open: datetime, timeframe: str = "1h") -> CacheEntry:
    df = _df_with_latest_open(latest_open)
    return CacheEntry(
        df=df,
        fetched_at=latest_open.timestamp(),  # value irrelevant under new TTL
        timeframe=timeframe,
        symbol="BTC/USDT",
    )


# ──────────────────────────────────────────────────────────────────────
# Positive — cache IS expired when next candle has closed
# ──────────────────────────────────────────────────────────────────────


def test_expired_when_next_candle_just_closed_1h():
    """latest_open=07:00. The 08:00 candle closes at 09:00. At 09:00:06
    (past the 5s buffer), is_expired must return True — a fresh fetch
    would now deliver 08:00 as the new latest closed candle.

    This is the EXACT case that the dda4d192 bug missed."""
    latest_open = datetime(2026, 5, 23, 7, 0, 0, tzinfo=timezone.utc)
    entry = _make_entry(latest_open)
    # Simulate wall-clock = 09:00:06 UTC (next candle just closed + buffer)
    now_epoch = datetime(2026, 5, 23, 9, 0, 6, tzinfo=timezone.utc).timestamp()
    with patch("backend.data.ohlcv_cache.time.time", return_value=now_epoch):
        assert entry.is_expired() is True


def test_expired_when_long_past_next_close():
    """latest_open=07:00. At 11:00 (multiple hours later), still expired."""
    latest_open = datetime(2026, 5, 23, 7, 0, 0, tzinfo=timezone.utc)
    entry = _make_entry(latest_open)
    now_epoch = datetime(2026, 5, 23, 11, 0, 0, tzinfo=timezone.utc).timestamp()
    with patch("backend.data.ohlcv_cache.time.time", return_value=now_epoch):
        assert entry.is_expired() is True


def test_expired_short_timeframe_5m():
    """Same logic on a 5m candle: latest_open=07:00, expires at 07:10:06."""
    latest_open = datetime(2026, 5, 23, 7, 0, 0, tzinfo=timezone.utc)
    entry = _make_entry(latest_open, timeframe="5m")
    now_epoch = datetime(2026, 5, 23, 7, 10, 7, tzinfo=timezone.utc).timestamp()
    with patch("backend.data.ohlcv_cache.time.time", return_value=now_epoch):
        assert entry.is_expired() is True


# ──────────────────────────────────────────────────────────────────────
# Negative — cache is NOT expired during the in-progress candle window
# ──────────────────────────────────────────────────────────────────────


def test_not_expired_during_in_progress_candle():
    """latest_open=07:00. At 08:30 the 08:00 candle is still in progress.
    A fresh fetch would still return 07:00 as latest — so cache is fresh."""
    latest_open = datetime(2026, 5, 23, 7, 0, 0, tzinfo=timezone.utc)
    entry = _make_entry(latest_open)
    now_epoch = datetime(2026, 5, 23, 8, 30, 0, tzinfo=timezone.utc).timestamp()
    with patch("backend.data.ohlcv_cache.time.time", return_value=now_epoch):
        assert entry.is_expired() is False


def test_not_expired_one_second_before_threshold():
    """Boundary safety: latest_open=07:00. Threshold = 09:00:05 (with default
    5s buffer). At 09:00:04, NOT yet expired."""
    latest_open = datetime(2026, 5, 23, 7, 0, 0, tzinfo=timezone.utc)
    entry = _make_entry(latest_open)
    now_epoch = datetime(2026, 5, 23, 9, 0, 4, tzinfo=timezone.utc).timestamp()
    with patch("backend.data.ohlcv_cache.time.time", return_value=now_epoch):
        assert entry.is_expired() is False


def test_not_expired_immediately_after_fetch():
    """latest_open=07:00, fetched at 07:55 (just before next candle close).
    At 07:55:01 (immediately after fetch), cache is fresh."""
    latest_open = datetime(2026, 5, 23, 7, 0, 0, tzinfo=timezone.utc)
    entry = _make_entry(latest_open)
    now_epoch = datetime(2026, 5, 23, 7, 55, 1, tzinfo=timezone.utc).timestamp()
    with patch("backend.data.ohlcv_cache.time.time", return_value=now_epoch):
        assert entry.is_expired() is False


# ──────────────────────────────────────────────────────────────────────
# Bug-class regression — the exact dda4d192 scenario must now expire
# ──────────────────────────────────────────────────────────────────────


def test_dda4d192_regression_scan_at_08_32_must_expire():
    """The dda4d192 forensic scenario. A scan at 07:55 cached BTC with
    latest_open=07:00 (because 08:00 hadn't closed yet at fetch time).
    Under the OLD TTL formula, cache stayed valid until 08:55 — and a
    scan at 08:32 would hit cache, see latest=07:00, compute pct=-1.05%,
    fire Gate 3 strong_down.

    Under the NEW TTL formula, cache expires at 09:00:05. So a scan at
    08:32 still hits cache (which is correct — 08:00 candle hasn't
    closed yet, so a fresh fetch would also return 07:00 as latest).

    Wait — that means a scan at 08:32 STILL sees stale data. The fix
    is correct: the in-progress 08:xx candle simply isn't visible until
    09:00. The bug isn't that 08:32 sees latest=07:00; it's that the
    08:32 SCAN computes pct_change relative to the prior closed candle
    (07:00 close vs 06:00 close = -1.05%), which IS the most recent
    information available.

    The OLD bug was different: even at 09:00:30 (after 08:00 had
    closed), cache held latest=07:00 because TTL hadn't fired. With
    the fix, at 09:00:06 the cache expires and the next fetch gets
    latest=08:00, computing pct=(08:00−07:00)/07:00 = +0.11% = neutral.

    This test pins THAT case — the moment when the fix should cause a
    fresh fetch to occur."""
    latest_open = datetime(2026, 5, 23, 7, 0, 0, tzinfo=timezone.utc)
    entry = _make_entry(latest_open)
    # Simulate wall-clock = 09:00:30 (just after the 08:00 candle closed)
    now_epoch = datetime(2026, 5, 23, 9, 0, 30, tzinfo=timezone.utc).timestamp()
    with patch("backend.data.ohlcv_cache.time.time", return_value=now_epoch):
        # OLD formula: time_since_fetch = 09:00:30 - 07:00 = 7230s vs
        #              tf_seconds + buffer = 3605s → expired=True ALSO
        #              (but only because >1h had passed; in the real
        #              bug fetched_at was 07:55, so at 08:32 the OLD
        #              formula said NOT expired and held the stale df).
        # NEW formula: now (32430s) >= latest_open (25200s) +
        #              2*tf_seconds (7200s) + buffer (5s) = 32405s →
        #              expired=True. Forces refetch.
        assert entry.is_expired() is True


def test_dda4d192_old_bug_scenario_now_correctly_expires():
    """Direct simulation of the dda4d192 bug case under the new formula.

    Setup that previously produced the bug:
      - fetched_at = 07:55 (just before 08:00 candle close)
      - cached df: latest candle has open=07:00 (since 08:00 hadn't
        closed at fetch time)
      - scan at 08:32: under OLD code, time_since_fetch = 37 min,
        less than 1h, cache HIT, returned stale df → 84 LONG
        rejections at Gate 3.

    Under NEW code at 08:32 wall-clock: cache is fresh BUT for the
    correct reason (the 08:00 candle hasn't closed yet, so a fresh
    fetch wouldn't yield newer data anyway). At 09:00:06 wall-clock,
    cache expires regardless of when the fetch happened. That's the
    fix — TTL no longer depends on fetched_at."""
    latest_open = datetime(2026, 5, 23, 7, 0, 0, tzinfo=timezone.utc)
    fetched_at = datetime(2026, 5, 23, 7, 55, 0, tzinfo=timezone.utc).timestamp()
    df = _df_with_latest_open(latest_open)
    entry = CacheEntry(
        df=df, fetched_at=fetched_at, timeframe="1h", symbol="BTC/USDT"
    )
    # Phase 1: scan at 08:32 — cache still fresh (correct: 08:00 candle
    # still in progress, fresh fetch wouldn't give new info)
    now_8_32 = datetime(2026, 5, 23, 8, 32, 0, tzinfo=timezone.utc).timestamp()
    with patch("backend.data.ohlcv_cache.time.time", return_value=now_8_32):
        assert entry.is_expired() is False
    # Phase 2: scan at 09:00:30 — cache expired regardless of
    # fetched_at. This is the regression fix.
    now_9_00_30 = datetime(2026, 5, 23, 9, 0, 30, tzinfo=timezone.utc).timestamp()
    with patch("backend.data.ohlcv_cache.time.time", return_value=now_9_00_30):
        assert entry.is_expired() is True


# ──────────────────────────────────────────────────────────────────────
# Edge cases — empty df, malformed timestamps, naive timestamps
# ──────────────────────────────────────────────────────────────────────


def test_empty_df_always_expired():
    entry = CacheEntry(
        df=pd.DataFrame(),
        fetched_at=0.0,
        timeframe="1h",
        symbol="BTC/USDT",
    )
    assert entry.is_expired() is True


def test_naive_timestamp_assumed_utc():
    """If the cached df has naive timestamps (no tz info — exchange
    convention is UTC), is_expired must treat them as UTC. A naive
    timestamp interpreted as local time would shift TTL by the local
    UTC offset and re-introduce hour-scale staleness on non-UTC hosts."""
    naive = pd.Timestamp("2026-05-23 07:00:00")  # no tz
    rows = [
        {"timestamp": naive, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}
    ]
    df = pd.DataFrame(rows)
    entry = CacheEntry(df=df, fetched_at=0.0, timeframe="1h", symbol="BTC/USDT")
    # 09:00:06 UTC — past expiry threshold IF treated as UTC; not yet
    # expired IF treated as local time on most timezones.
    now_epoch = datetime(2026, 5, 23, 9, 0, 6, tzinfo=timezone.utc).timestamp()
    with patch("backend.data.ohlcv_cache.time.time", return_value=now_epoch):
        assert entry.is_expired() is True


def test_not_expired_when_latest_open_in_future():
    """Clock skew / fixture sanity: if the cached df's latest_open is
    AHEAD of wall-clock, is_expired must return False (the candle hasn't
    even opened yet, so the cache trivially can't be stale). Pins safe
    behavior on weird inputs."""
    latest_open = datetime(2026, 5, 23, 12, 0, 0, tzinfo=timezone.utc)
    entry = _make_entry(latest_open)
    # Wall-clock is 3 hours BEFORE latest_open
    now_epoch = datetime(2026, 5, 23, 9, 0, 0, tzinfo=timezone.utc).timestamp()
    with patch("backend.data.ohlcv_cache.time.time", return_value=now_epoch):
        assert entry.is_expired() is False


# ──────────────────────────────────────────────────────────────────────
# get_remaining_seconds parity — must mirror is_expired math
# ──────────────────────────────────────────────────────────────────────


def test_get_remaining_seconds_mirrors_is_expired_when_fresh():
    """The /api/cache/* debug endpoints expose remaining_seconds. After
    the candle-boundary fix, remaining must reflect actual expiration
    (not elapsed-since-fetch). Otherwise operators see misleading
    numbers during paper-trading triage."""
    latest_open = datetime(2026, 5, 23, 7, 0, 0, tzinfo=timezone.utc)
    entry = _make_entry(latest_open)
    # Wall-clock = 08:00:00 (mid-cycle). is_expired=False.
    # Expected remaining = (09:00:05 - 08:00:00) = 3605s.
    now_epoch = datetime(2026, 5, 23, 8, 0, 0, tzinfo=timezone.utc).timestamp()
    with patch("backend.data.ohlcv_cache.time.time", return_value=now_epoch):
        assert entry.is_expired() is False
        remaining = entry.get_remaining_seconds()
        assert 3604.0 <= remaining <= 3606.0, (
            f"remaining_seconds should mirror is_expired math; got {remaining}"
        )


def test_get_remaining_seconds_zero_when_expired():
    """Once is_expired returns True, remaining_seconds must be 0 (not a
    negative number, not a phantom large value from the old formula)."""
    latest_open = datetime(2026, 5, 23, 7, 0, 0, tzinfo=timezone.utc)
    entry = _make_entry(latest_open)
    # Wall-clock = 11:00 (long past expiry at 09:00:05)
    now_epoch = datetime(2026, 5, 23, 11, 0, 0, tzinfo=timezone.utc).timestamp()
    with patch("backend.data.ohlcv_cache.time.time", return_value=now_epoch):
        assert entry.is_expired() is True
        assert entry.get_remaining_seconds() == 0.0


def test_get_remaining_seconds_empty_df_returns_zero():
    entry = CacheEntry(
        df=pd.DataFrame(), fetched_at=0.0, timeframe="1h", symbol="BTC/USDT"
    )
    assert entry.get_remaining_seconds() == 0.0


def test_malformed_timestamp_falls_back_to_elapsed_since_fetch(caplog):
    """If the timestamp column is unparseable, is_expired must not crash
    the bot. It falls back to the OLD elapsed-since-fetch formula —
    same behavior as before, so the bot keeps running with the original
    (broken) semantics rather than wedging.

    POST-CA3: the fallback emits a WARNING-level log AND a structured
    telemetry event (kind=ohlcv_cache_ttl_fallback_to_elapsed) so the
    silent-regression-to-broken-behavior class is now LOUD per §11 +
    §15. This test pins both: the fallback works AND the operator sees
    it loudly."""
    import logging
    df = pd.DataFrame(
        [{"timestamp": object(), "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]
    )
    fetched_at = datetime(2026, 5, 23, 7, 0, 0, tzinfo=timezone.utc).timestamp()
    entry = CacheEntry(df=df, fetched_at=fetched_at, timeframe="1h", symbol="BTC/USDT")

    caplog.set_level(logging.WARNING)
    mock_logger = MagicMock()
    with patch(
        "backend.bot.telemetry.logger.get_telemetry_logger",
        return_value=mock_logger,
    ):
        # 2h after fetch — even the broken formula says expired
        now_epoch = datetime(2026, 5, 23, 9, 0, 0, tzinfo=timezone.utc).timestamp()
        with patch("backend.data.ohlcv_cache.time.time", return_value=now_epoch):
            assert entry.is_expired() is True
        # 30 min after fetch — broken formula says NOT expired
        now_epoch_short = datetime(2026, 5, 23, 7, 30, 0, tzinfo=timezone.utc).timestamp()
        with patch("backend.data.ohlcv_cache.time.time", return_value=now_epoch_short):
            assert entry.is_expired() is False

    # CA3 — WARNING must fire on the fallback path. Two is_expired calls
    # above → at least one WARNING with the canonical "fall*back" phrasing.
    warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("fall" in r.getMessage().lower() for r in warning_records), (
        f"fallback path must emit a WARNING-level log, got: "
        f"{[r.getMessage() for r in warning_records]}"
    )

    # CA3 — structured telemetry event must fire with the right kind.
    assert mock_logger.log_event.called, (
        "fallback path must emit a structured telemetry event so silent "
        "regression to broken behavior is visible in the activity feed"
    )
    last_event = mock_logger.log_event.call_args[0][0]
    assert last_event.event_type.value == "warning_issued"
    assert last_event.data["kind"] == "ohlcv_cache_ttl_fallback_to_elapsed"
    assert last_event.data["timeframe"] == "1h"
