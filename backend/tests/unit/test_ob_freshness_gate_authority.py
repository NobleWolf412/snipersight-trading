"""
Regression for T2 / Phase 1A: filter_obs_by_mode (Gate 2) is the SINGLE OB freshness
authority (operator decision #3, 2026-06-09).

Two dead scale-mismatch freshness filters were retired:
  - order_blocks.detect_order_blocks end-of-function filter (freshness_score 0-100 vs
    ob_min_freshness 0-1=0.05 → always true, expired nothing)
  - smc_service detect() aggregation filter (same mismatch + misleading "stale OBs" log)
Gate 2 (filter_obs_by_mode, thresholds 38/19/12 on the 0-100 scale ≈ 2.5 half-lives) is
now the only place OB staleness expiry happens, and it must FAIL LOUD on a None/unknown
mode_profile rather than silently returning the list unfiltered.

Per CLAUDE.md §14 rubric 4 (positive+negative), §16 rubric 12 (bull/bear symmetry).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backend.shared.models.smc import OrderBlock
from backend.strategy.smc.order_blocks import filter_obs_by_mode

# stealth_balanced Gate-2 criteria: 15m allowed, min_freshness=19.0, max_mitigation=0.4.
# 15m half-life = 24h → freshness = 2**(-age_h/24)*100.
#   24h (1.0 HL) → 50.0  (KEPT, > 19)
#   60h (2.5 HL) → 17.7  (EXPIRED, < 19)
_STEALTH = "stealth_balanced"


def _ob(direction: str, timestamp: datetime) -> OrderBlock:
    """A 15m OB, unmitigated, so only freshness governs its survival under Gate 2."""
    return OrderBlock(
        timeframe="15m",
        direction=direction,
        high=101.0,
        low=100.0,
        timestamp=timestamp,
        displacement_strength=50.0,
        mitigation_level=0.0,
        freshness_score=100.0,  # recalculated by filter_obs_by_mode via current_time
    )


# ── (a) None / unknown mode_profile must FAIL LOUD, never silently unfiltered ──────


def test_none_mode_profile_raises_not_silent_passthrough():
    now = datetime.utcnow()
    obs = [_ob("bullish", now - timedelta(hours=1))]
    with pytest.raises(ValueError, match="mode_profile is required"):
        filter_obs_by_mode(obs, mode_profile=None, current_time=now)


def test_unknown_mode_profile_raises():
    now = datetime.utcnow()
    obs = [_ob("bullish", now - timedelta(hours=1))]
    with pytest.raises(ValueError, match="unknown mode_profile"):
        filter_obs_by_mode(obs, mode_profile="ghost", current_time=now)


def test_empty_input_is_exempt_from_fail_loud():
    """An empty pool is a legitimate no-op, not a wiring bug — must NOT raise."""
    assert filter_obs_by_mode([], mode_profile=None) == []


def test_all_four_profiles_accepted():
    now = datetime.utcnow()
    obs = [_ob("bullish", now - timedelta(hours=1))]
    for profile in ("macro_surveillance", "stealth_balanced", "intraday_aggressive", "precision"):
        # must not raise; fresh 15m OB survives in modes whose TF set includes 15m
        filter_obs_by_mode(obs, mode_profile=profile, current_time=now)


# ── (b) per-TF expiry at the ~2.5 half-life boundary ───────────────────────────────


def test_stale_ob_expired_fresh_ob_kept_at_boundary():
    now = datetime.utcnow()
    fresh = _ob("bullish", now - timedelta(hours=24))   # 1.0 HL → 50.0, kept
    stale = _ob("bullish", now - timedelta(hours=60))   # 2.5 HL → 17.7, expired
    out = filter_obs_by_mode([fresh, stale], mode_profile=_STEALTH, current_time=now)
    kept_ts = {ob.timestamp for ob in out}
    assert fresh.timestamp in kept_ts
    assert stale.timestamp not in kept_ts


# ── (c) bull/bear OBs age identically (Gate 2 is direction-agnostic) ────────────────


@pytest.mark.parametrize("direction", ["bullish", "bearish"])
def test_freshness_expiry_is_direction_symmetric(direction):
    now = datetime.utcnow()
    fresh = _ob(direction, now - timedelta(hours=24))   # kept
    stale = _ob(direction, now - timedelta(hours=60))   # expired
    out = filter_obs_by_mode([fresh, stale], mode_profile=_STEALTH, current_time=now)
    kept_ts = {ob.timestamp for ob in out}
    assert fresh.timestamp in kept_ts, f"{direction}: fresh OB wrongly expired"
    assert stale.timestamp not in kept_ts, f"{direction}: stale OB wrongly kept"
