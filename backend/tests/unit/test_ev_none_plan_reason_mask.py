"""
Regression for the reason-masking bug found during the 2026-06-01 autopsy series.

orchestrator._generate_trade_plan computed an EV estimate (plan.risk_reward, then
plan.metadata["ev"]) WITHOUT guarding plan-is-None. When the planner legitimately
returns None (a decline — reachability, entry-depth gate, etc.), `plan.risk_reward`
threw AttributeError; the except handler's own `plan.metadata["ev"] = None` RE-THREW
'NoneType' object has no attribute 'metadata', which escaped to the outer catch and
OVERWROTE context.metadata["plan_failure_reason"] with the generic NoneType error —
masking ~half the planner rejections (2218 in one session log) and making the real
decline reasons (incl. the TP1 reachability declines) undiagnosable.

Fix: wrap the EV block in `if plan is not None:` so a None plan skips EV cleanly and
the real decline reason propagates.

Per CLAUDE.md §11 (silent-failure / reason preservation), §14 rubric 4 (negative+positive).
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from backend.engine import orchestrator as orch_mod
from backend.engine.orchestrator import Orchestrator
from backend.engine.context import SniperContext
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode
from backend.shared.models.smc import SMCSnapshot
from backend.shared.models.indicators import IndicatorSet, IndicatorSnapshot
from backend.shared.models.scoring import ConfluenceBreakdown, ConfluenceFactor

_MASK = "'NoneType' object has no attribute 'metadata'"


def _ctx() -> SniperContext:
    snap = IndicatorSnapshot(
        rsi=50.0, stoch_rsi=50.0, bb_upper=110.0, bb_middle=100.0, bb_lower=90.0,
        atr=2.0, volume_spike=False,
    )
    c = SniperContext(symbol="ETH/USDT", profile="stealth", run_id="t",
                      timestamp=datetime.now(timezone.utc))
    c.smc_snapshot = SMCSnapshot([], [], [], [])
    c.multi_tf_indicators = IndicatorSet(by_timeframe={"4H": snap})
    c.confluence_breakdown = ConfluenceBreakdown(
        total_score=75.0,
        factors=[ConfluenceFactor(name="x", score=75, weight=1.0, rationale="x")],
        synergy_bonus=0.0, conflict_penalty=0.0, regime="trend",
        htf_aligned=True, btc_impulse_gate=True,
    )
    c.metadata = {"chosen_direction": "LONG"}
    c.multi_tf_data = None
    return c


def _orch() -> Orchestrator:
    o = object.__new__(Orchestrator)
    o.config = ScanConfig()
    o.scanner_mode = get_mode("stealth")
    o.current_regime = None        # read at orchestrator.py:3164 (global_regime enrichment)
    o.macro_context = None
    o.exchange_adapter = None
    return o


def test_none_plan_does_not_mask_decline_reason():
    """Planner returns None (a decline) → _generate_trade_plan returns None WITHOUT
    overwriting plan_failure_reason with the NoneType-metadata mask."""
    o, c = _orch(), _ctx()
    with patch.object(orch_mod, "generate_trade_plan", return_value=None):
        result = o._generate_trade_plan(c, 100.0)
    assert result is None
    assert _MASK not in str(c.metadata.get("plan_failure_reason") or ""), (
        f"decline reason was masked: {c.metadata.get('plan_failure_reason')!r}"
    )


def test_valid_plan_still_gets_ev():
    """Positive pair: a valid plan still gets its EV computed (the guard must not
    break the happy path)."""
    o, c = _orch(), _ctx()
    plan = MagicMock()
    plan.risk_reward = 2.0
    plan.metadata = {}
    plan.targets = []
    plan.setup_type = "Test"
    plan.direction = "LONG"
    with patch.object(orch_mod, "generate_trade_plan", return_value=plan):
        result = o._generate_trade_plan(c, 100.0)
    assert result is plan
    assert "ev" in plan.metadata  # EV path ran for the valid plan
