"""
Regression for hot-path audit bug #3 (1_BROKEN): the cascade re-derived a
per-scale direction (_derive_cascade_direction) AFTER confluence scoring and
wrote it into context.metadata["chosen_direction"]. _generate_trade_plan then
built geometry for the flipped direction but passed the unchanged session-
direction confluence_breakdown — so a flipped SHORT plan carried the LONG score,
LONG factor breakdown, and LONG-regime HTF adjustment, mis-ranking the candidate
and persisting a wrong-direction score.

Fix (operator-approved Option C): the cascade varies the trade-type SCALE only
(swing/intraday/scalp) and inherits the session direction. The per-scale
direction flip was removed entirely (the feature was unobservable in telemetry
and only ever produced sub-swing plans, the net-losing cohort).

See backend/diagnostics/decisions/2026-05-30__fix-design__cascade-direction-score-mismatch.md
and 2026-05-29__hotpath-robustness-audit.md (bug #3).

Per CLAUDE.md §11, §16 rubric 12 (LONG/SHORT symmetry), §10 (bull/bear symmetry).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from backend.engine.orchestrator import Orchestrator


def test_derive_cascade_direction_removed():
    """Structural guard: the per-scale direction-flip method must stay removed.
    Re-adding it reintroduces the wrong-direction-score bug (#3)."""
    assert not hasattr(Orchestrator, "_derive_cascade_direction"), (
        "Orchestrator._derive_cascade_direction was removed (audit #3); "
        "re-adding it reintroduces the cascade wrong-direction-score bug"
    )


def _bare_orchestrator():
    o = object.__new__(Orchestrator)
    o._CASCADE_SCALE_SETTINGS = {}
    o._CASCADE_TYPE_BONUS = {}
    o._build_cascade_config = lambda tt: SimpleNamespace(profile=tt)
    o._derive_btc_impulse = lambda *a, **k: None
    return o


def _run_cascade(session_direction: str, cascade_types):
    """Drive _cascade_plan_generation with stubbed collaborators; record the
    direction seen at each gate call and each plan-generation call."""
    o = _bare_orchestrator()
    seen_plan_dirs = []
    seen_gate_dirs = []

    def _fake_plan(context, current_price, tick_size=0.0, lot_size=0.0, config_override=None):
        seen_plan_dirs.append(context.metadata["chosen_direction"])
        return None  # no candidate — we only assert the direction at call time

    o._generate_trade_plan = _fake_plan

    ctx = SimpleNamespace(
        symbol="ETH/USDT",
        macro_context=None,
        smc_snapshot=object(),  # truthy → gate path runs
        # strong_up regime previously could trigger the scalp counter-HTF flip block
        metadata={"chosen_direction": session_direction,
                  "symbol_regime": SimpleNamespace(trend="strong_up")},
    )

    def _fake_gates(**kw):
        seen_gate_dirs.append(kw["direction"])
        return SimpleNamespace(passed=True, gate_name="", reason="")

    with patch("backend.engine.orchestrator.run_pre_scoring_gates", _fake_gates):
        result = o._cascade_plan_generation(ctx, 100.0, cascade_types)

    return ctx, result, seen_plan_dirs, seen_gate_dirs


def test_cascade_never_flips_direction_long():
    ctx, result, plan_dirs, gate_dirs = _run_cascade("LONG", ("swing", "intraday", "scalp"))

    assert result is None  # plan stub returns None → no candidates
    assert ctx.metadata["chosen_direction"] == "LONG"          # never flipped
    assert plan_dirs == ["LONG", "LONG", "LONG"]               # every scale used session dir
    assert gate_dirs == ["LONG", "LONG", "LONG"]               # gates ran with session dir
    assert ctx.metadata["cascade_attempts"]                    # trade-type scaling preserved


def test_cascade_never_flips_direction_short():
    """SHORT-session mirror (§16 rubric 12): even a strong_up regime — which
    previously could flip a scalp scale to LONG — must not flip a SHORT session."""
    ctx, result, plan_dirs, gate_dirs = _run_cascade("SHORT", ("intraday", "scalp"))

    assert ctx.metadata["chosen_direction"] == "SHORT"
    assert plan_dirs == ["SHORT", "SHORT"]
    assert gate_dirs == ["SHORT", "SHORT"]
