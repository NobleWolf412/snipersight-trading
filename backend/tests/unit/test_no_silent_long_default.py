"""
Regression: the 8 `context.metadata.get("chosen_direction", "LONG")` silent-LONG
defaults in orchestrator.py (the §2-RISKY landmines from the 2026-06-02 Stage-1
direction-authority audit) must not return.

Two execution-critical sites (_generate_trade_plan, _cascade_plan_generation)
previously coerced a missing/unresolved direction into a phantom LONG trade. They
now mirror the Stage-6 direction_unresolved guard (orch ~2313): if chosen_direction
is not LONG/SHORT they log loudly and return None instead of fabricating a side.
The six logging/label sites use the honest `or "UNKNOWN"` sentinel (the pattern
already at orch ~2117), so a diagnostic in the bug case is no longer mislabeled LONG.

Per CLAUDE.md §11 (prefer loud failures), §16 rubric 12 (LONG/SHORT symmetry — the
fix REMOVES a bullish default), and the decisions entry
2026-06-02__direction-authority-map-and-stage1-rewrite-blastmap.md (Step 1).
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.engine.orchestrator import Orchestrator

_ORCH_SRC = Path(__file__).resolve().parents[2] / "engine" / "orchestrator.py"


def _bare_orchestrator():
    o = object.__new__(Orchestrator)
    o._CASCADE_SCALE_SETTINGS = {}
    o._CASCADE_TYPE_BONUS = {}
    o._build_cascade_config = lambda tt: SimpleNamespace(profile=tt)
    o._derive_btc_impulse = lambda *a, **k: None
    return o


def _drive_cascade(chosen_direction):
    """Run _cascade_plan_generation; record whether the plan/gate collaborators
    were reached (they must NOT be when direction is unresolved)."""
    o = _bare_orchestrator()
    plan_calls, gate_calls = [], []

    o._generate_trade_plan = lambda context, *a, **k: plan_calls.append(
        context.metadata.get("chosen_direction")
    )

    meta = {"symbol_regime": SimpleNamespace(trend="strong_up")}
    if chosen_direction is not _MISSING:
        meta["chosen_direction"] = chosen_direction

    ctx = SimpleNamespace(
        symbol="ETH/USDT", macro_context=None, smc_snapshot=object(), metadata=meta,
    )

    def _fake_gates(**kw):
        gate_calls.append(kw["direction"])
        return SimpleNamespace(passed=True, gate_name="", reason="")

    with patch("backend.engine.orchestrator.run_pre_scoring_gates", _fake_gates):
        result = o._cascade_plan_generation(ctx, 100.0, ("intraday", "scalp"))
    return result, plan_calls, gate_calls


_MISSING = object()


def test_cascade_aborts_when_direction_missing():
    """No chosen_direction key at all → abort, no phantom LONG, collaborators untouched."""
    result, plan_calls, gate_calls = _drive_cascade(_MISSING)
    assert result is None
    assert plan_calls == [], "must not build any plan when direction is unresolved"
    assert gate_calls == [], "must not run gates with a fabricated direction"


def test_cascade_aborts_when_direction_invalid():
    """A non-LONG/SHORT sentinel (e.g. 'UNKNOWN') is treated as unresolved, not LONG."""
    result, plan_calls, gate_calls = _drive_cascade("UNKNOWN")
    assert result is None
    assert plan_calls == []
    assert gate_calls == []


def test_cascade_proceeds_on_short_session():
    """Symmetry (§16 r12): a valid SHORT must NOT trip the guard — it runs as SHORT,
    proving the guard rejects only unresolved direction, not the bearish side."""
    result, plan_calls, gate_calls = _drive_cascade("SHORT")
    assert gate_calls == ["SHORT", "SHORT"]      # both scales gated as SHORT
    assert plan_calls == ["SHORT", "SHORT"]      # both scales planned as SHORT


def test_cascade_proceeds_on_long_session():
    """Bull mirror of the SHORT case — a *resolved* LONG is still honored."""
    _, plan_calls, gate_calls = _drive_cascade("LONG")
    assert gate_calls == ["LONG", "LONG"]
    assert plan_calls == ["LONG", "LONG"]


def test_no_silent_long_default_remains_in_source():
    """Structural guard: the silent-LONG default must not reappear anywhere in
    orchestrator.py. Re-introducing `.get("chosen_direction", "LONG")` reintroduces
    the phantom-LONG bug class. Honest `or "UNKNOWN"` sentinels are allowed."""
    src = _ORCH_SRC.read_text(encoding="utf-8")
    offenders = re.findall(r'chosen_direction["\']\s*,\s*["\']LONG["\']', src)
    assert not offenders, (
        f"{len(offenders)} silent-LONG default(s) reintroduced in orchestrator.py "
        "— use `.get(\"chosen_direction\") or \"UNKNOWN\"` (logging) or a loud "
        "direction_unresolved guard (execution) instead"
    )
