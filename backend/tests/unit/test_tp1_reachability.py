"""
Behavioral tests for the TP1 reachability clamp/decline fix (2026-05-31).
decisions/2026-05-30__fix-design__tp1-reachability.md

Exercises the REAL pipeline (generate_trade_plan -> _calculate_targets) rather than
replicating the decision math, and pins the §16-audit catch: the reachability_clamped
flag must survive the _adjust_targets_for_wick_barriers rebuild, else the admission
gate silently re-rejects clamped targets at the full min_rr_ratio.

Behavior under test (ceiling 1.3 ATR, after-clip floor 1.2, ladder TP1 1.5R):
  - tight stop  -> TP1 reachable, NOT clamped, full R:R (negative case, §16 R4)
  - moderate stop -> TP1 clamped to the ceiling at a lower R:R, plan still admitted
  - extreme stop -> TP1 unreachable even at the floor -> clean skip (plan is None)
Paired LONG/SHORT (§10 / §16 R12).
"""
from __future__ import annotations

import pandas as pd
import pytest

from backend.strategy.planner import planner_service as ps
from backend.strategy.planner.planner_service import generate_trade_plan
from backend.strategy.planner.risk_engine import _adjust_targets_for_wick_barriers
from backend.shared.models.planner import EntryZone, StopLoss, Target
from backend.shared.models.smc import SMCSnapshot
from backend.shared.models.scoring import ConfluenceBreakdown, ConfluenceFactor
from backend.shared.models.indicators import IndicatorSet, IndicatorSnapshot
from backend.shared.config.defaults import ScanConfig
from backend.bot.telemetry.logger import get_telemetry_logger


@pytest.fixture(autouse=True)
def reset_telemetry():
    logger = get_telemetry_logger()
    logger._cache.clear()
    yield
    logger._cache.clear()


def _indicators(atr: float, tf: str = "4H") -> IndicatorSet:
    snap = IndicatorSnapshot(
        rsi=50.0, stoch_rsi=50.0, bb_upper=110.0, bb_middle=100.0, bb_lower=90.0,
        atr=atr, volume_spike=False,
    )
    return IndicatorSet(by_timeframe={tf: snap})


def _confluence() -> ConfluenceBreakdown:
    return ConfluenceBreakdown(
        total_score=75.0,
        factors=[
            ConfluenceFactor(name="Structure", score=80, weight=0.4, rationale="OB"),
            ConfluenceFactor(name="Momentum", score=70, weight=0.3, rationale="impulse"),
            ConfluenceFactor(name="Liquidity", score=60, weight=0.3, rationale="sweep"),
        ],
        synergy_bonus=5.0, conflict_penalty=0.0, regime="trend",
        htf_aligned=True, btc_impulse_gate=True,
    )


def _run(monkeypatch, direction: str, stop_atr: float, atr: float = 1.0, price: float = 100.0,
         leverage: int = 1):
    """Drive generate_trade_plan with a monkeypatched entry zone + stop at `stop_atr`
    ATR from near_entry. Returns the plan (or None on a clean-skip decline).
    `leverage` > 1 exercises _adjust_targets_for_leverage (a Target rebuilder upstream
    of the admission gate)."""
    is_long = direction == "LONG"

    def fake_entry_zone(*a, **k):
        # near = price; far is just inside the zone (0.1 ATR), correct side per direction.
        far = price - 0.1 * atr if is_long else price + 0.1 * atr
        return EntryZone(near_entry=price, far_entry=far, rationale="Test"), True

    def fake_stop_loss(*a, **k):
        level = price - stop_atr * atr if is_long else price + stop_atr * atr
        return StopLoss(level=level, distance_atr=stop_atr, rationale="Test"), True

    monkeypatch.setattr(ps, "_calculate_entry_zone", fake_entry_zone)
    monkeypatch.setattr(ps, "_calculate_stop_loss", fake_stop_loss)

    return generate_trade_plan(
        symbol="TEST/USDT",
        direction=direction,
        setup_type="intraday",
        current_price=price,
        indicators=_indicators(atr),
        smc_snapshot=SMCSnapshot(order_blocks=[], fvgs=[], structural_breaks=[], liquidity_sweeps=[]),
        confluence_breakdown=_confluence(),
        config=ScanConfig(leverage=leverage),
        multi_tf_data=None,
        missing_critical_timeframes=[],
    )


# ── tight stop: reachable, NOT clamped (negative case) ────────────────────────
@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_tight_stop_not_clamped(monkeypatch, direction):
    plan = _run(monkeypatch, direction, stop_atr=0.3)
    assert plan is not None, f"{direction} tight-stop plan should build"
    assert plan.metadata.get("tp1_clamped") is False, (
        f"{direction}: tight stop (0.3 ATR -> TP1 ~0.45 ATR) must NOT be clamped"
    )


# ── moderate stop: clamped, still admitted ────────────────────────────────────
@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_moderate_stop_clamped_and_admitted(monkeypatch, direction):
    plan = _run(monkeypatch, direction, stop_atr=1.0)
    assert plan is not None, f"{direction}: moderate-stop clamped plan must be ADMITTED (after-clip floor)"
    assert plan.metadata.get("tp1_clamped") is True, (
        f"{direction}: moderate stop (1.0 ATR -> TP1 1.5 ATR > 1.3 ceiling) must clamp"
    )
    # Clamped R:R must sit in [after-clip floor, full ladder) — reachable but admissible.
    assert plan.risk_reward_ratio < 1.5 + 1e-6, f"{direction}: clamped R:R should be below full ladder"
    assert plan.risk_reward_ratio >= 1.2 - 1e-6, f"{direction}: clamped R:R must clear the after-clip floor"


# ── §16 audit round-2 catch: flag survives the leverage-adjuster rebuild ──────
@pytest.mark.parametrize("is_bullish", [True, False])
def test_clamp_flag_survives_leverage_rebuild(is_bullish):
    """_adjust_targets_for_leverage rebuilds every Target and runs BEFORE the admission
    gate (planner_service:444 < :794). At leverage 5 (scale_factor 1.2 != 1.0) the rebuild
    fires; the reachability_clamped flag MUST survive it, else the gate re-gates a clamped
    target at the full min_rr_ratio and silently rejects it (round-2 bug). Tested directly
    for determinism — through the full pipeline, leverage also widens the stop, which is a
    separate (correct) decline path."""
    from backend.strategy.planner.risk_engine import _adjust_targets_for_leverage

    entry = 100.0
    level = entry + 1.3 if is_bullish else entry - 1.3
    clamped = Target(level=level, rationale="clamped", rr_ratio=1.3, percentage=100.0,
                     reachability_clamped=True)
    out, _meta = _adjust_targets_for_leverage([clamped], leverage=5, entry_price=entry,
                                              is_bullish=is_bullish)
    assert out and out[0].reachability_clamped is True, (
        "reachability_clamped MUST survive the leverage-adjuster rebuild — else the admission "
        "gate silently rejects the clamped target at the full min_rr_ratio under leverage"
    )


def test_non_clamped_target_stays_unclamped_through_leverage_rebuild():
    """Negative pair: an un-clamped target rebuilt by the leverage adjuster stays un-clamped."""
    from backend.strategy.planner.risk_engine import _adjust_targets_for_leverage

    normal = Target(level=101.3, rationale="normal", rr_ratio=1.3, percentage=100.0,
                    reachability_clamped=False)
    out, _meta = _adjust_targets_for_leverage([normal], leverage=5, entry_price=100.0,
                                              is_bullish=True)
    assert out and out[0].reachability_clamped is False, "un-clamped target must not gain the flag"


# ── extreme stop: declined (clean skip, plan is None) ─────────────────────────
@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_extreme_stop_declined(monkeypatch, direction):
    plan = _run(monkeypatch, direction, stop_atr=3.0)
    assert plan is None, (
        f"{direction}: extreme stop (3.0 ATR -> even a 1.2R target = 3.6 ATR > ceiling) "
        f"must DECLINE (clean skip, no plan)"
    )


# ── §16 audit catch: clamp flag survives the wick-barrier rebuild ─────────────
def test_clamp_flag_survives_wick_barrier_rebuild():
    """A reachability-clamped TP1 that gets pulled in by a wick barrier must KEEP its
    reachability_clamped flag through the Target rebuild — else the admission gate
    re-gates it at min_rr_ratio and silently rejects it (the 2026-05-31 audit bug)."""
    atr, entry, risk = 1.0, 100.0, 1.0
    # Clamped LONG TP1 at 1.3 ATR above entry.
    clamped_tp = Target(level=entry + 1.3 * atr, rationale="clamped", rr_ratio=1.3,
                         reachability_clamped=True)
    # One candle with a qualifying upper-wick supply zone between entry and target.
    # open/close form a small body at ~100.95; high 101.25 -> upper_wick 0.30 (>=0.3 ATR);
    # candidate = body_hi - 0.1 ATR = 100.85 -> realised 0.85R (>= 0.8R floor) -> REBUILD.
    df = pd.DataFrame(
        [{"open": 100.85, "high": 101.29, "low": 100.80, "close": 100.95, "volume": 100.0}] * 3
    )

    class _MTF:
        timeframes = {"5m": df}

    out = _adjust_targets_for_wick_barriers([clamped_tp], _MTF(), entry, True, atr, risk)
    assert len(out) == 1
    assert abs(out[0].level - 100.85) < 1e-6, "wick barrier should have rebuilt TP1 at the body edge"
    assert out[0].reachability_clamped is True, (
        "reachability_clamped MUST survive the wick-barrier rebuild — else the admission "
        "gate silently rejects the clamped target at the full min_rr_ratio"
    )


def test_non_clamped_target_stays_unclamped_through_wick_rebuild():
    """Negative pair: an un-clamped target rebuilt by the wick barrier stays un-clamped."""
    atr, entry, risk = 1.0, 100.0, 1.0
    normal_tp = Target(level=entry + 1.3 * atr, rationale="normal", rr_ratio=1.3,
                       reachability_clamped=False)
    df = pd.DataFrame(
        [{"open": 100.85, "high": 101.29, "low": 100.80, "close": 100.95, "volume": 100.0}] * 3
    )

    class _MTF:
        timeframes = {"5m": df}

    out = _adjust_targets_for_wick_barriers([normal_tp], _MTF(), entry, True, atr, risk)
    assert out[0].reachability_clamped is False, "un-clamped target must not gain the flag"
