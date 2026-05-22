"""
Pipeline structural smoke test for SniperSight (CLAUDE.md §20 Backend Integrity).

Scope (Tier 2.5a — structural only):
Verifies that the orchestrator pipeline can be LOADED and CONFIGURED. Catches the
silent-break vectors that have historically slipped past unit tests:

- Renamed / removed SniperContext fields
- A fifth scanner mode silently shipping (regresses CLAUDE.md §10 standing fix #6)
- min_confluence_score drift from the §4 table without a documented reason
- RELATIVITY_MAP keys or values silently changing (regresses §7)
- run_pre_scoring_gates signature drift (regresses §6 pre-scoring gates contract)
- Telemetry EventType removals that would silently break /autopsy

Behavioral smoke (orchestrator.scan against an OHLCV fixture, comparing to a frozen
golden output) is Tier 2.5b — deferred on the fixture-format decision documented in
the Tier 2.5 plan.

Modes:
  python -m backend.diagnostics.pipeline_smoke capture        # mint new golden
  python -m backend.diagnostics.pipeline_smoke {verify,diff}  # compare vs golden (default)

Wired into §16 Rubric 14: "For pipeline changes, pipeline_smoke.py passes against
pipeline_smoke_golden.json." Non-zero exit on drift.
"""
from __future__ import annotations

import inspect
import json
import sys
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

DIAG_DIR = Path(__file__).parent
GOLDEN_PATH = DIAG_DIR / "pipeline_smoke_golden.json"
REPO_ROOT = DIAG_DIR.parent.parent


# ---------------------------------------------------------------------------
# Individual checks. Each returns a stable JSON-serializable dict.
# All imports wrapped — a failing import becomes a payload entry, not a crash.
# ---------------------------------------------------------------------------


def _safe_import(label: str, importer: Callable[[], Any]) -> str:
    try:
        importer()
        return "ok"
    except Exception as exc:
        return f"err: {exc!r}"


def check_imports() -> Dict[str, Any]:
    """Six load surfaces operators historically broke during refactors."""
    return {
        "orchestrator": _safe_import(
            "orchestrator",
            lambda: __import__("backend.engine.orchestrator", fromlist=["Orchestrator"]),
        ),
        "sniper_context": _safe_import(
            "sniper_context",
            lambda: __import__("backend.engine.context", fromlist=["SniperContext"]),
        ),
        "scorer": _safe_import(
            "scorer",
            lambda: __import__(
                "backend.strategy.confluence.scorer",
                fromlist=["run_pre_scoring_gates", "GateResult"],
            ),
        ),
        "scanner_modes": _safe_import(
            "scanner_modes",
            lambda: __import__(
                "backend.shared.config.scanner_modes",
                fromlist=["list_modes", "get_mode", "RELATIVITY_MAP"],
            ),
        ),
        "regime_detector": _safe_import(
            "regime_detector",
            lambda: __import__(
                "backend.analysis.regime_detector",
                fromlist=["RegimeDetector", "get_regime_detector"],
            ),
        ),
        "telemetry_events": _safe_import(
            "telemetry_events",
            lambda: __import__(
                "backend.bot.telemetry.events", fromlist=["EventType", "TelemetryEvent"]
            ),
        ),
    }


def check_sniper_context_fields() -> Dict[str, Any]:
    """Snapshot the SniperContext dataclass field set."""
    try:
        from backend.engine.context import SniperContext  # type: ignore
    except Exception as exc:
        return {"error": f"import failed: {exc!r}"}
    if not is_dataclass(SniperContext):
        return {"error": "SniperContext is not a dataclass"}
    names = sorted([f.name for f in fields(SniperContext)])
    return {"field_count": len(names), "field_names": names}


def check_mode_inventory() -> Dict[str, Any]:
    """CLAUDE.md §10 standing fix #6: only four modes exist."""
    try:
        from backend.shared.config.scanner_modes import MODES  # type: ignore
    except Exception as exc:
        return {"error": f"import failed: {exc!r}"}
    names = sorted(MODES.keys())
    return {"mode_count": len(names), "mode_names": names}


def check_mode_thresholds() -> Dict[str, Any]:
    """Per-mode threshold + TF table — CLAUDE.md §4. Silent threshold edits surface here."""
    try:
        from backend.shared.config.scanner_modes import MODES  # type: ignore
    except Exception as exc:
        return {"error": f"import failed: {exc!r}"}

    out: Dict[str, Any] = {}
    for name in sorted(MODES.keys()):
        m = MODES[name]
        out[name] = {
            "min_confluence_score": float(m.min_confluence_score),
            "profile": m.profile,
            "primary_planning_timeframe": m.primary_planning_timeframe,
            "critical_timeframes": list(m.critical_timeframes),
            "timeframes": list(m.timeframes),
            "expected_trade_type": m.expected_trade_type,
            "allowed_trade_types": list(m.allowed_trade_types),
            "cascade_trade_types": (
                list(m.cascade_trade_types) if m.cascade_trade_types is not None else None
            ),
        }
    return out


def check_relativity_map() -> Dict[str, Any]:
    """CLAUDE.md §7 — Scalp/Intraday/Swing TF hierarchy."""
    try:
        from backend.shared.config.scanner_modes import RELATIVITY_MAP  # type: ignore
    except Exception as exc:
        return {"error": f"import failed: {exc!r}"}
    out: Dict[str, Any] = {"keys": sorted(RELATIVITY_MAP.keys())}
    for k in sorted(RELATIVITY_MAP.keys()):
        # Defensive: only copy primitive values, sorted by key
        v = RELATIVITY_MAP[k]
        if isinstance(v, dict):
            out[k] = {sk: v[sk] for sk in sorted(v.keys())}
        else:
            out[k] = v
    return out


def check_pre_scoring_gates() -> Dict[str, Any]:
    """CLAUDE.md §6 — run_pre_scoring_gates signature + GateResult field set."""
    try:
        from backend.strategy.confluence.scorer import (  # type: ignore
            GateResult,
            run_pre_scoring_gates,
        )
    except Exception as exc:
        return {"error": f"import failed: {exc!r}"}

    out: Dict[str, Any] = {"run_pre_scoring_gates_exists": callable(run_pre_scoring_gates)}
    try:
        sig = inspect.signature(run_pre_scoring_gates)
        out["signature_params"] = sorted(sig.parameters.keys())
    except (TypeError, ValueError) as exc:
        out["signature_params"] = f"signature-introspection-failed: {exc!r}"

    if is_dataclass(GateResult):
        out["GateResult_fields"] = sorted([f.name for f in fields(GateResult)])
    else:
        # Best-effort fallback for non-dataclass GateResult shapes
        out["GateResult_fields"] = sorted(
            [a for a in dir(GateResult) if not a.startswith("_")]
        )
    return out


def check_regime_detector() -> Dict[str, Any]:
    """Regime detector surface — class + public method set (no instantiation)."""
    try:
        from backend.analysis.regime_detector import (  # type: ignore
            RegimeDetector,
            get_regime_detector,
        )
    except Exception as exc:
        return {"error": f"import failed: {exc!r}"}

    methods = sorted(
        [a for a in dir(RegimeDetector) if not a.startswith("_") and callable(getattr(RegimeDetector, a, None))]
    )
    return {
        "RegimeDetector_exists": True,
        "get_regime_detector_exists": callable(get_regime_detector),
        "RegimeDetector_methods": methods,
    }


def check_telemetry_events() -> Dict[str, Any]:
    """EventType enum values + the four /autopsy-required events present."""
    try:
        from backend.bot.telemetry.events import EventType  # type: ignore
    except Exception as exc:
        return {"error": f"import failed: {exc!r}"}

    values = sorted([e.value for e in EventType])
    required = {
        "scan_started": "scan_started" in values,
        "scan_completed": "scan_completed" in values,
        "signal_generated": "signal_generated" in values,
        "signal_rejected": "signal_rejected" in values,
    }
    return {"event_type_values": values, "required_events_present": required}


CHECKS: List[Tuple[str, Callable[[], Dict[str, Any]]]] = [
    ("imports", check_imports),
    ("sniper_context", check_sniper_context_fields),
    ("mode_inventory", check_mode_inventory),
    ("mode_thresholds", check_mode_thresholds),
    ("relativity_map", check_relativity_map),
    ("pre_scoring_gates", check_pre_scoring_gates),
    ("regime_detector", check_regime_detector),
    ("telemetry_events", check_telemetry_events),
]


# ---------------------------------------------------------------------------
# Diff helper — copied verbatim from capture_contracts.py per Plan agent's
# "don't refactor for two callers" decision. If a third caller appears, hoist
# to backend/diagnostics/_diff.py.
# ---------------------------------------------------------------------------


def _diff_dicts(label: str, baseline: Any, current: Any, path: str = "") -> List[str]:
    lines: List[str] = []
    if type(baseline) is not type(current):
        lines.append(
            f"  {label}{path}: type changed ({type(baseline).__name__} -> {type(current).__name__})"
        )
        return lines
    if isinstance(baseline, dict):
        b_keys, c_keys = set(baseline.keys()), set(current.keys())
        for k in sorted(b_keys - c_keys):
            lines.append(f"  {label}{path}: removed key '{k}'")
        for k in sorted(c_keys - b_keys):
            lines.append(f"  {label}{path}: added key '{k}'")
        for k in sorted(b_keys & c_keys):
            lines.extend(_diff_dicts(label, baseline[k], current[k], path + f".{k}"))
    elif isinstance(baseline, list):
        if baseline != current:
            lines.append(
                f"  {label}{path}: list changed (len {len(baseline)} -> {len(current)})"
            )
    else:
        if baseline != current:
            lines.append(f"  {label}{path}: {baseline!r} -> {current!r}")
    return lines


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def _build_payload() -> Dict[str, Any]:
    payload: Dict[str, Any] = {"checks": {}}
    for label, fn in CHECKS:
        try:
            payload["checks"][label] = fn()
        except Exception as exc:
            # Hard backstop: an individual check raising should never crash the smoke.
            payload["checks"][label] = {"error": f"check raised: {exc!r}"}
    return payload


def cmd_capture() -> int:
    """Mint a new golden baseline. Operator must document the why in commit body."""
    print(f"[pipeline_smoke] Capturing structural baseline -> {GOLDEN_PATH.relative_to(REPO_ROOT)}")
    payload = _build_payload()
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with GOLDEN_PATH.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    # Summary
    print("\n=== SUMMARY ===")
    for label, _ in CHECKS:
        result = payload["checks"].get(label, {})
        if isinstance(result, dict) and "error" in result:
            print(f"  - {label}: ERR ({result['error']})")
        else:
            print(f"  - {label}: captured")
    print("\n[pipeline_smoke] done.")
    return 0


def cmd_verify() -> int:
    """Compare current pipeline structure vs the frozen golden. Non-zero on drift."""
    print(f"[pipeline_smoke] Verifying current structure vs {GOLDEN_PATH.relative_to(REPO_ROOT)}")
    if not GOLDEN_PATH.exists():
        print(
            f"\n=== RESULT: NO BASELINE ({GOLDEN_PATH.relative_to(REPO_ROOT)} missing — run capture first) ==="
        )
        return 1

    try:
        with GOLDEN_PATH.open("r", encoding="utf-8") as fh:
            baseline = json.load(fh)
    except Exception as exc:
        print(f"[pipeline_smoke] failed to read baseline: {exc!r}", file=sys.stderr)
        return 1

    current = _build_payload()

    summary_lines: List[str] = []
    detail_lines: List[str] = []
    total_drift = 0

    base_checks = (baseline or {}).get("checks", {}) or {}
    curr_checks = (current or {}).get("checks", {}) or {}

    all_labels = sorted(set(base_checks.keys()) | set(curr_checks.keys()))
    for label in all_labels:
        if label not in base_checks:
            summary_lines.append(f"  - {label}: ADDED (no baseline)")
            total_drift += 1
            continue
        if label not in curr_checks:
            summary_lines.append(f"  - {label}: REMOVED (present in baseline)")
            total_drift += 1
            continue
        diffs = _diff_dicts(label, base_checks[label], curr_checks[label])
        if diffs:
            summary_lines.append(f"  - {label}: DRIFT ({len(diffs)} changes)")
            detail_lines.extend(diffs)
            total_drift += len(diffs)
        else:
            summary_lines.append(f"  - {label}: clean")

    # §12 paste-friendly: summary, detail, raw
    print("\n=== SUMMARY ===")
    print("\n".join(summary_lines))
    if detail_lines:
        print("\n=== DETAIL ===")
        print("\n".join(detail_lines))
    print(f"\n=== RESULT: {'DRIFT' if total_drift else 'CLEAN'} ({total_drift} changes) ===")
    return 0 if total_drift == 0 else 1


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "verify"
    if cmd == "capture":
        return cmd_capture()
    if cmd in ("verify", "diff"):
        return cmd_verify()
    print(
        "Usage: python -m backend.diagnostics.pipeline_smoke {capture|verify|diff}",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
