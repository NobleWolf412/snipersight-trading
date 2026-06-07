"""
Regression for SMC routing audit defect F2 (2026-05-31, #2 RISKY):
the no-SMC-structure HTF-swing stop FALLBACK gated only on `htf_swing_allowed` (inherited
via copy.copy from STEALTH's override ("4h","1h")), never on the tier's `stop_timeframes`.
So an intraday cascade tier (stop_timeframes 1h/15m/5m) could pull a 4h swing for its stop —
a second wide-stop pathway. Fix: `_resolve_htf_swing_allowed` intersects the allowlist with
`_get_allowed_stop_tfs(config)`, applied identically in the long and short fallbacks.

Per CLAUDE.md §11 (loud/correct fallbacks), §16 rubric 12 (the guard is direction-agnostic —
one helper, both fallbacks), and decisions/2026-05-31__smc-tf-mode-routing-audit.md (F2).
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

from backend.strategy.planner.risk_engine import _resolve_htf_swing_allowed

_RISK_SRC = Path(__file__).resolve().parents[2] / "strategy" / "planner" / "risk_engine.py"


def _cfg(stop_tfs=(), structure_tfs=(), override=("4h", "1h"), profile="intraday"):
    return SimpleNamespace(
        profile=profile,
        stop_timeframes=stop_tfs,
        structure_timeframes=structure_tfs,
        overrides={"htf_swing_allowed": override},
    )


def _pc():
    # planner_cfg duck: only htf_swing_allowed is read by the helper
    return SimpleNamespace(htf_swing_allowed={"intraday": ("4h", "1h", "1d"),
                                              "stealth": ("4h", "1h", "15m", "5m")})


def _lower(tfs):
    return [t.lower() for t in tfs]


def test_intraday_tier_drops_4h_swing():
    """F2 core: intraday tier (stop_timeframes 1h/15m/5m) must NOT keep 4h even though the
    inherited htf_swing_allowed override lists it."""
    out = _resolve_htf_swing_allowed(_cfg(stop_tfs=("1h", "15m", "5m")), _pc(), "intraday")
    assert "4h" not in _lower(out), f"4h leaked onto an intraday tier: {out}"
    assert "1h" in _lower(out), "1h (in both override and stop_timeframes) should survive"


def test_stealth_tier_keeps_4h_swing():
    """Mirror: a tier whose stop_timeframes INCLUDE 4h keeps the 4h swing (no over-restriction)."""
    out = _resolve_htf_swing_allowed(_cfg(stop_tfs=("4h", "1h", "15m", "5m")), _pc(), "stealth")
    assert "4h" in _lower(out), f"4h wrongly dropped from a tier that allows it: {out}"


def test_unrestricted_when_no_stop_or_structure_tfs():
    """Backward-compat: no stop_timeframes AND no structure_timeframes => no constraint."""
    out = _resolve_htf_swing_allowed(_cfg(stop_tfs=(), structure_tfs=()), _pc(), "intraday")
    assert "4h" in _lower(out), "unconstrained config should retain the full override"


def test_falls_back_to_structure_timeframes():
    """When stop_timeframes is empty, the constraint uses structure_timeframes (the existing
    _get_allowed_stop_tfs fallback): a structure allowlist without 4h still drops 4h."""
    out = _resolve_htf_swing_allowed(_cfg(stop_tfs=(), structure_tfs=("1h", "15m")), _pc(), "intraday")
    assert "4h" not in _lower(out), f"4h leaked via structure_timeframes fallback: {out}"


def test_both_fallbacks_use_the_helper_symmetric():
    """Structural symmetry guard (§16 r12): the long AND short no-structure swing fallbacks must
    BOTH route through _resolve_htf_swing_allowed — exactly 2 call sites — so the F2 constraint
    can't be reintroduced asymmetrically on one side."""
    src = _RISK_SRC.read_text(encoding="utf-8")
    calls = len(re.findall(r"_resolve_htf_swing_allowed\(config, planner_cfg, mode_profile\)", src))
    assert calls == 2, f"expected the helper called in both long+short fallbacks, found {calls}"
