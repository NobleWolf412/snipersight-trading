"""Candle-derived structure ages accept aware and legacy naive UTC timestamps."""
from datetime import datetime, timedelta, timezone

import pytest

from backend.shared.models import smc
from backend.analysis import htf_levels


NOW = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)


@pytest.fixture
def utc_clock(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            # Deliberately different local time: naive machine time isn't UTC.
            return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)-timedelta(hours=5)
    monkeypatch.setattr(smc, 'datetime', Clock)
    monkeypatch.setattr(htf_levels, 'datetime', Clock)


def stamp(days, form):
    value = NOW-timedelta(days=days)
    if form == 'naive':
        return value.replace(tzinfo=None)
    return value.astimezone(timezone(timedelta(hours=-5))) if form == 'offset' else value


@pytest.mark.parametrize('form', ['naive', 'utc', 'offset'])
@pytest.mark.parametrize('pool_type', ['equal_highs', 'equal_lows'])
@pytest.mark.parametrize('days,fresh', [(0, True), (7, True), (8, False)])
def test_structure_timestamp_utc_pool_freshness(utc_clock, form, pool_type, days, fresh):
    pool = smc.LiquidityPool(100., pool_type, 3, '4h', last_touch=stamp(days, form))
    assert pool.is_fresh is fresh
    pool.swept = True
    assert pool.is_fresh is False


@pytest.mark.parametrize('first_form', ['naive', 'utc', 'offset'])
@pytest.mark.parametrize('last_form', ['naive', 'utc', 'offset'])
def test_structure_timestamp_utc_level_score(utc_clock, first_form, last_form):
    detector = htf_levels.HTFLevelDetector()
    score = detector._score_level(100., 3, stamp(30, first_form),
                                  stamp(7, last_form), [1e6], '4h')
    assert score == 85.
