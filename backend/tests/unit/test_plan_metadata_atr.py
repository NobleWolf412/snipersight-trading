"""
Regression for hot-path audit bug #13 (3_CORRECTNESS): the orchestrator's post-plan
revalidation drift gate computes `atr_val = float(plan.metadata.get("atr") or 0.0)` and
`drift_atr = drift_abs / atr_val if atr_val > 0 else 0.0`, then rejects on
`drift_atr > max_drift_atr` (3.0). But the planner never wrote `plan.metadata["atr"]`,
so atr_val was always 0.0 → drift_atr forced 0.0 → the `> 3.0` ATR-drift check was
permanently dead. Only the looser 15% pct check survived.

Fix: the planner now stores the ATR it built the plan with in `plan.metadata["atr"]`,
re-arming the existing drift_atr gate.

See backend/diagnostics/decisions/2026-05-29__hotpath-robustness-audit.md (bug #13).
Per CLAUDE.md §11, §14 rubric 4 (negative+positive pair).
"""

from __future__ import annotations

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


def _build_plan(monkeypatch, atr: float, current_price: float = 100.0):
    cp = current_price
    monkeypatch.setattr(
        ps, "_calculate_entry_zone",
        lambda *a, **k: (EntryZone(near_entry=cp, far_entry=cp * 0.995, rationale="t"), True),
    )
    monkeypatch.setattr(
        ps, "_calculate_stop_loss",
        lambda *a, **k: (StopLoss(level=cp * 0.99, distance_atr=1.0, rationale="t"), True),
    )
    return generate_trade_plan(
        symbol="TEST/USDT", direction="LONG", setup_type="intraday",
        current_price=cp, indicators=_indicators(atr), smc_snapshot=SMCSnapshot([], [], [], []),
        confluence_breakdown=_confluence(), config=ScanConfig(),
        multi_tf_data=None, missing_critical_timeframes=[],
    )


def test_plan_metadata_carries_atr(monkeypatch):
    """The plan now records the ATR it was built with — was absent (→0.0) before,
    which dead-armed the orchestrator drift_atr gate."""
    plan = _build_plan(monkeypatch, atr=2.5)
    assert plan is not None
    assert plan.metadata.get("atr") == 2.5


def test_atr_rearms_drift_gate(monkeypatch):
    """Mirror the orchestrator gate arithmetic: with metadata['atr'] populated, a
    >3-ATR move yields drift_atr > max_drift_atr (3.0) and would reject. Pre-fix
    atr_val was 0.0 → drift_atr forced 0.0 → never > 3.0 (the dead gate)."""
    plan = _build_plan(monkeypatch, atr=2.0, current_price=100.0)
    atr_val = float(plan.metadata.get("atr") or 0.0)
    assert atr_val == 2.0  # not 0.0 (the bug)

    avg_entry = (plan.entry_zone.near_entry + plan.entry_zone.far_entry) / 2.0
    live_price = avg_entry + 7.0  # 7 units ≈ 3.5 ATR
    drift_atr = abs(live_price - avg_entry) / max(atr_val, 1e-12) if atr_val > 0 else 0.0
    assert drift_atr > 3.0  # gate is live again (pre-fix this was forced to 0.0)
