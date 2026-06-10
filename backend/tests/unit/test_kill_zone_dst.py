"""
Regression for Phase 2: kill-zone / session times are DST-aware (America/New_York),
not a hardcoded UTC-5.

Before: get_current_session / get_current_kill_zone converted with a fixed
timedelta(hours=-5). For the live caller (scorer passes datetime.now(timezone.utc))
this was correct in winter but 1 hour off in summer (EDT). For naive timestamps the
whole conversion was SKIPPED, leaving raw UTC matched against Eastern-labeled windows
(~5h off). Both are fixed by converting through ZoneInfo("America/New_York").

The kill_zone factor is live in scoring (scorer.py:2567, weight up to 0.15), so the NY
kill zone must fire at the correct Eastern wall-clock year-round.

NY_OPEN window = 07:00-10:00 Eastern → 11:00-14:00 UTC in summer (EDT, UTC-4),
12:00-15:00 UTC in winter (EST, UTC-5).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.strategy.smc.sessions import (
    KillZone,
    TradingSession,
    _to_eastern,
    get_current_kill_zone,
    get_current_session,
)

UTC = timezone.utc


# ── _to_eastern: DST-aware, naive treated as UTC ──────────────────────────────────


def test_to_eastern_dst_aware_and_naive_is_utc():
    assert _to_eastern(datetime(2026, 7, 1, 12, 0, tzinfo=UTC)).hour == 8   # summer EDT
    assert _to_eastern(datetime(2026, 1, 15, 13, 0, tzinfo=UTC)).hour == 8  # winter EST
    assert _to_eastern(datetime(2026, 7, 1, 12, 0)).hour == 8               # naive → UTC → 08 EDT


# ── 08:00 Eastern lands in NEW_YORK_OPEN from different UTC inputs per season ──────
# (US DST 2026: spring-forward Mar 8, fall-back Nov 1)


@pytest.mark.parametrize(
    "label,ts",
    [
        ("summer EDT 8am ET",          datetime(2026, 7, 1, 12, 0, tzinfo=UTC)),
        ("winter EST 8am ET",          datetime(2026, 1, 15, 13, 0, tzinfo=UTC)),
        ("post-spring-forward 8am ET", datetime(2026, 3, 15, 12, 0, tzinfo=UTC)),
        ("post-fall-back 8am ET",      datetime(2026, 11, 15, 13, 0, tzinfo=UTC)),
    ],
)
def test_ny_open_killzone_dst_aware(label, ts):
    assert get_current_kill_zone(ts) == KillZone.NEW_YORK_OPEN, label


# ── the specific DST bug is gone (summer ±1h boundary) ────────────────────────────


def test_summer_dst_bug_ny_open_now_fires():
    """11:30 UTC summer = 07:30 EDT (inside NY_OPEN). Pre-fix hardcoded -5 gave 06:30 → None."""
    assert get_current_kill_zone(datetime(2026, 7, 1, 11, 30, tzinfo=UTC)) == KillZone.NEW_YORK_OPEN


def test_summer_false_positive_gone():
    """14:30 UTC summer = 10:30 EDT (outside NY_OPEN). Pre-fix gave 09:30 → NY_OPEN false positive."""
    assert get_current_kill_zone(datetime(2026, 7, 1, 14, 30, tzinfo=UTC)) is None


def test_naive_timestamp_now_converted_not_skipped():
    """naive 12:00 (UTC) summer → 08:00 EDT → NY_OPEN. Pre-fix skipped conversion for naive
    inputs and matched raw 12:00 against the Eastern tables (→ LONDON_CLOSE, ~5h wrong)."""
    assert get_current_kill_zone(datetime(2026, 7, 1, 12, 0)) == KillZone.NEW_YORK_OPEN


# ── session path is DST-aware too ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "label,ts",
    [
        ("summer 16:00 ET", datetime(2026, 7, 1, 20, 0, tzinfo=UTC)),   # 16:00 EDT
        ("winter 16:00 ET", datetime(2026, 1, 15, 21, 0, tzinfo=UTC)),  # 16:00 EST
    ],
)
def test_new_york_session_dst_aware(label, ts):
    # 16:00 ET matches only NEW_YORK among SESSION_TIMES (ASIAN/LONDON miss at 4pm).
    assert get_current_session(ts) == TradingSession.NEW_YORK, label
