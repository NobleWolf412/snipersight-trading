"""
Regression tests for the entry-time SMC liquidity-pool journal instrumentation
(observability-only, NO scoring/stop/execution behavior change).

Guards:
  decisions/2026-06-13__journal-entry-pool-instrumentation.md

Covers:
  - _nearest_same_side_pool direction-awareness + bull/bear MIRROR symmetry
    (§16 Rubric 12): LONG -> pools below entry (pwl/pdl); SHORT -> pools above (pwh/pdh),
    selected via the SAME basis risk_engine._buffer_stop_from_liquidity uses.
  - The swept flag is reported (not filtered) so spent liquidity is distinguishable.
  - Malformed / empty / None key_levels -> (None, None, None, None), never raises
    (§16 Rubric 4 negative test + loud-failure guard).
  - Synthetic CompletedTrade.to_dict() round-trip: the new keys land in the journal record.
"""

import pytest

from backend.bot.paper_trading_service import (
    _nearest_same_side_pool,
    _pool_price_swept,
    CompletedTrade,
)
from backend.analysis.key_levels import KeyLevels, KeyLevel
from datetime import datetime, timezone


ATR = 1.0


def _kl_dict(**levels):
    """Production-shaped key_levels dict (KeyLevels.to_dict()) with given pool prices.

    Pass ``("price", swept)`` tuples to set the swept flag, or a bare float for swept=False.
    """
    ts = datetime(2026, 6, 1, tzinfo=timezone.utc)
    kw = {}
    for k, v in levels.items():
        if isinstance(v, tuple):
            price, swept = v
        else:
            price, swept = v, False
        kw[k] = KeyLevel(price=price, level_type=k.upper(), timestamp=ts, timeframe="1d", swept=swept)
    return KeyLevels(symbol="X", **kw).to_dict()


# ── Bull/bear MIRROR symmetry on nearest-same-side selection ──────────────────

def test_long_picks_nearest_pool_below_entry():
    # LONG entry 110. pwl @ 100 (10 ATR below), pdl @ 105 (5 ATR below) -> pdl is nearer.
    kl = _kl_dict(pwl=100.0, pdl=105.0)
    label, price, dist, swept = _nearest_same_side_pool(kl, entry_ref=110.0, direction="LONG", atr=ATR)
    assert label == "PDL"
    assert price == 105.0
    assert dist == pytest.approx(5.0)
    assert swept is False


def test_short_picks_nearest_pool_above_entry_mirror():
    # SHORT mirror of the LONG case: entry 90. pwh @ 100 (10 ATR above), pdh @ 95 (5 ATR
    # above) -> pdh is nearer. Same distance magnitude as the LONG test (mirror).
    kl = _kl_dict(pwh=100.0, pdh=95.0)
    label, price, dist, swept = _nearest_same_side_pool(kl, entry_ref=90.0, direction="SHORT", atr=ATR)
    assert label == "PDH"
    assert price == 95.0
    assert dist == pytest.approx(5.0)
    assert swept is False


def test_long_ignores_pools_on_wrong_side():
    # LONG entry 110: a pwl ABOVE entry (115) is on the wrong (non-stop) side -> skipped.
    # Only pdl @ 108 (below) qualifies.
    kl = _kl_dict(pwl=115.0, pdl=108.0)
    label, price, dist, _ = _nearest_same_side_pool(kl, entry_ref=110.0, direction="LONG", atr=ATR)
    assert label == "PDL"
    assert price == 108.0
    assert dist == pytest.approx(2.0)


def test_short_ignores_pools_on_wrong_side_mirror():
    # SHORT entry 90: a pwh BELOW entry (85) is on the wrong side -> skipped.
    kl = _kl_dict(pwh=85.0, pdh=92.0)
    label, price, dist, _ = _nearest_same_side_pool(kl, entry_ref=90.0, direction="SHORT", atr=ATR)
    assert label == "PDH"
    assert price == 92.0
    assert dist == pytest.approx(2.0)


def test_no_qualifying_pool_returns_none_long():
    # LONG entry 110, but the only pools sit ABOVE entry -> no stop-side pool.
    kl = _kl_dict(pwl=120.0, pdl=130.0)
    assert _nearest_same_side_pool(kl, entry_ref=110.0, direction="LONG", atr=ATR) == (None, None, None, None)


def test_no_qualifying_pool_returns_none_short_mirror():
    kl = _kl_dict(pwh=80.0, pdh=70.0)
    assert _nearest_same_side_pool(kl, entry_ref=90.0, direction="SHORT", atr=ATR) == (None, None, None, None)


# ── swept flag is reported (not filtered) ─────────────────────────────────────

def test_swept_flag_is_surfaced():
    kl = _kl_dict(pdl=(105.0, True))
    label, price, dist, swept = _nearest_same_side_pool(kl, entry_ref=110.0, direction="LONG", atr=ATR)
    assert label == "PDL"
    assert swept is True  # swept pool is still selected (reported), not skipped


# ── Distance is in ATR units (scales with atr) ────────────────────────────────

def test_distance_scales_with_atr():
    kl = _kl_dict(pdl=105.0)
    _, _, dist_atr2, _ = _nearest_same_side_pool(kl, entry_ref=110.0, direction="LONG", atr=2.0)
    # 5 price units / atr 2.0 = 2.5 ATR
    assert dist_atr2 == pytest.approx(2.5)


# ── Negative / malformed guards: never raise, return all-None ─────────────────

@pytest.mark.parametrize("bad", [None, {}, [], "garbage", 123, {"pwl": None, "pdl": None}])
def test_malformed_key_levels_returns_none(bad):
    assert _nearest_same_side_pool(bad, entry_ref=110.0, direction="LONG", atr=ATR) == (None, None, None, None)


@pytest.mark.parametrize("bad_dir", ["bullish", "buy", "", None, "UP"])
def test_unexpected_direction_returns_none_no_silent_default(bad_dir):
    # An unexpected direction token must NOT silently route to the SHORT branch —
    # it returns all-None (loud-failure guard), preserving mirror symmetry.
    kl = _kl_dict(pwl=100.0, pwh=120.0)
    assert _nearest_same_side_pool(kl, entry_ref=110.0, direction=bad_dir, atr=ATR) == (None, None, None, None)


@pytest.mark.parametrize("ok_dir", ["LONG", "long", "Long", "SHORT", "short"])
def test_direction_is_case_insensitive(ok_dir):
    # Canonical directions resolve regardless of case (callers emit uppercase; the helper
    # normalizes). LONG-family picks the below-entry pool; SHORT-family the above-entry pool.
    kl = _kl_dict(pwl=100.0, pwh=120.0)
    label, _, _, _ = _nearest_same_side_pool(kl, entry_ref=110.0, direction=ok_dir, atr=ATR)
    assert label == ("PWL" if ok_dir.upper() == "LONG" else "PWH")


def test_zero_or_missing_atr_returns_none():
    kl = _kl_dict(pdl=105.0)
    assert _nearest_same_side_pool(kl, entry_ref=110.0, direction="LONG", atr=0.0) == (None, None, None, None)
    assert _nearest_same_side_pool(kl, entry_ref=110.0, direction="LONG", atr=None) == (None, None, None, None)


def test_pool_price_swept_robust_to_shapes():
    # dict shape, flat float, and KeyLevel-like object all resolve; malformed -> (None, None)
    assert _pool_price_swept({"price": 100.0, "swept": True}) == (100.0, True)
    assert _pool_price_swept(100.0) == (100.0, None)
    assert _pool_price_swept(None) == (None, None)
    assert _pool_price_swept({"price": None}) == (None, None)
    assert _pool_price_swept({"price": -5.0}) == (None, None)  # non-positive rejected


# ── Synthetic CompletedTrade.to_dict() round-trip: new keys land in the journal ──

def test_completed_trade_to_dict_carries_pool_keys():
    kl = _kl_dict(pdl=105.0, pwl=100.0)
    label, price, dist, swept = _nearest_same_side_pool(kl, entry_ref=110.0, direction="LONG", atr=ATR)
    trade = CompletedTrade(
        trade_id="X/USDT_1",
        symbol="X/USDT",
        direction="LONG",
        entry_price=110.0,
        exit_price=112.0,
        quantity=1.0,
        entry_time=datetime(2026, 6, 13, tzinfo=timezone.utc),
        exit_time=datetime(2026, 6, 13, 1, tzinfo=timezone.utc),
        pnl=2.0,
        pnl_pct=1.8,
        exit_reason="target",
        entry_key_levels=kl,
        nearest_same_side_pool_dist_atr=dist,
        nearest_same_side_pool_label=label,
        nearest_same_side_pool_price=price,
        nearest_same_side_pool_swept=swept,
    )
    d = trade.to_dict()
    assert d["entry_key_levels"] == kl
    assert d["nearest_same_side_pool_label"] == "PDL"
    assert d["nearest_same_side_pool_price"] == 105.0
    assert d["nearest_same_side_pool_dist_atr"] == pytest.approx(5.0)
    assert d["nearest_same_side_pool_swept"] is False


def test_completed_trade_defaults_null_when_pool_absent():
    # A trade built without pool context (e.g. older/recovered position) emits null keys,
    # never crashes, and is JSON-serializable.
    import json
    trade = CompletedTrade(
        trade_id="Y/USDT_1", symbol="Y/USDT", direction="SHORT",
        entry_price=90.0, exit_price=88.0, quantity=1.0,
        entry_time=datetime(2026, 6, 13, tzinfo=timezone.utc), exit_time=None,
        pnl=0.0, pnl_pct=0.0, exit_reason="session_stopped",
    )
    d = trade.to_dict()
    assert d["entry_key_levels"] is None
    assert d["nearest_same_side_pool_dist_atr"] is None
    assert d["nearest_same_side_pool_label"] is None
    assert d["nearest_same_side_pool_price"] is None
    assert d["nearest_same_side_pool_swept"] is None
    json.dumps(d, default=str)  # must not raise


# ── Planner-path: generate_trade_plan must populate plan.metadata["entry_key_levels"] ──
# (Regression for the §16-caught BLOCKER: the stash was first written at a line where
# `plan` did not yet exist, raising UnboundLocalError that the buffer try/except
# swallowed — leaving the feature inert AND killing the liquidity buffer. These tests
# prove the write executes AFTER plan construction and survives to the bot layer.)

from backend.strategy.planner import planner_service as ps
from backend.strategy.planner.planner_service import generate_trade_plan
from backend.shared.models.smc import SMCSnapshot
from backend.shared.models.scoring import ConfluenceBreakdown, ConfluenceFactor
from backend.shared.config.defaults import ScanConfig
from backend.shared.models.indicators import IndicatorSet, IndicatorSnapshot
from backend.shared.models.planner import EntryZone, StopLoss


def _indicators(atr: float, tf: str = "4H") -> IndicatorSet:
    snap = IndicatorSnapshot(
        rsi=50.0, stoch_rsi=50.0, bb_upper=110.0, bb_middle=100.0, bb_lower=90.0,
        atr=atr, volume_spike=False,
    )
    return IndicatorSet(by_timeframe={tf: snap})


def _confluence() -> ConfluenceBreakdown:
    return ConfluenceBreakdown(
        total_score=75.0,
        factors=[ConfluenceFactor(name="Structure", score=80, weight=1.0, rationale="x")],
        synergy_bonus=0.0, conflict_penalty=0.0, regime="trend",
        htf_aligned=True, btc_impulse_gate=True,
    )


def _build_plan_with_key_levels(monkeypatch, key_levels, cp: float = 100.0):
    monkeypatch.setattr(
        ps, "_calculate_entry_zone",
        lambda *a, **k: (EntryZone(near_entry=cp, far_entry=cp * 0.995, rationale="t"), True),
    )
    monkeypatch.setattr(
        ps, "_calculate_stop_loss",
        lambda *a, **k: (StopLoss(level=cp * 0.99, distance_atr=1.0, rationale="t"), True),
    )
    snap = SMCSnapshot([], [], [], [])
    snap.key_levels = key_levels  # production: SMCSnapshot.key_levels = KeyLevels.to_dict()
    return generate_trade_plan(
        symbol="TEST/USDT", direction="LONG", setup_type="intraday",
        current_price=cp, indicators=_indicators(2.0), smc_snapshot=snap,
        confluence_breakdown=_confluence(), config=ScanConfig(),
        multi_tf_data=None, missing_critical_timeframes=[],
    )


def test_planner_populates_entry_key_levels_in_metadata(monkeypatch):
    kl = _kl_dict(pwl=98.0, pdl=99.0)
    plan = _build_plan_with_key_levels(monkeypatch, kl)
    assert plan is not None
    # The write must have EXECUTED (it lives in the metadata literal, after plan build).
    assert plan.metadata.get("entry_key_levels") == kl


def test_planner_entry_key_levels_null_when_no_key_levels(monkeypatch):
    plan = _build_plan_with_key_levels(monkeypatch, None)
    assert plan is not None
    # key_levels None -> stored None (not crash, not missing key).
    assert "entry_key_levels" in plan.metadata
    assert plan.metadata["entry_key_levels"] is None
