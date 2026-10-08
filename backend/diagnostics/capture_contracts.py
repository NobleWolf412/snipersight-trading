"""
Contract capture + diff for SniperSight backend integrity (CLAUDE.md §20).

Captures frozen snapshots of:
  - API route inventory (path, method, response model name)
  - Telemetry event types + factory function parameter names (not runtime payload validation)
  - SniperContext field set
  - Production SQLite declarations and selected JSONL writer implementation fingerprints

Two modes:
  python -m backend.diagnostics.capture_contracts capture   # re-baseline
  python -m backend.diagnostics.capture_contracts diff      # compare current vs baseline

Diff mode exits non-zero on drift. Wired into §16 audit Rubrics 13 + 14.

Output: backend/diagnostics/contracts/*.json
Format: §12 paste-friendly (short summary, structured detail, raw data).
"""

from __future__ import annotations

import inspect
import json
import re
import sys
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CONTRACTS_DIR = Path(__file__).parent / "contracts"
REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Capture: API contracts
# ---------------------------------------------------------------------------


def capture_api_contracts() -> Dict[str, Any]:
    """Introspect FastAPI app for route inventory.

    Returns a stable shape: {"routes": [{"path", "methods", "name", "response_model"}, ...]}
    Routes are sorted by path for stable diffs.
    """
    try:
        from backend.api_server import app  # type: ignore
    except Exception as exc:
        return {"error": f"failed to import backend.api_server: {exc!r}", "routes": []}

    routes: List[Dict[str, Any]] = []
    for r in app.routes:
        path = getattr(r, "path", None)
        if not path or not isinstance(path, str):
            continue
        # Skip mounts / static files / openapi.json etc — only API endpoints
        if not path.startswith("/api"):
            continue
        methods = sorted(list(getattr(r, "methods", []) or []))
        name = getattr(r, "name", None)
        response_model = getattr(r, "response_model", None)
        rm_name = (
            getattr(response_model, "__name__", str(response_model))
            if response_model is not None
            else None
        )
        routes.append(
            {
                "path": path,
                "methods": methods,
                "name": name,
                "response_model": rm_name,
            }
        )

    routes.sort(key=lambda x: (x["path"], ",".join(x["methods"])))
    return {"routes": routes, "count": len(routes)}


# ---------------------------------------------------------------------------
# Capture: Telemetry contracts
# ---------------------------------------------------------------------------


def capture_telemetry_contracts() -> Dict[str, Any]:
    """Introspect telemetry event types + factory function payload keys."""
    try:
        from backend.bot.telemetry import events as ev_mod  # type: ignore
        from backend.bot.telemetry.events import EventType  # type: ignore
    except Exception as exc:
        return {"error": f"failed to import telemetry events: {exc!r}"}

    event_types = sorted([e.value for e in EventType])

    factories: Dict[str, List[str]] = {}
    for name, obj in inspect.getmembers(ev_mod, inspect.isfunction):
        if not name.startswith("create_"):
            continue
        try:
            sig = inspect.signature(obj)
            factories[name] = sorted(list(sig.parameters.keys()))
        except (TypeError, ValueError):
            factories[name] = []

    return {
        "event_types": event_types,
        "event_type_count": len(event_types),
        "factories": dict(sorted(factories.items())),
    }


# ---------------------------------------------------------------------------
# Capture: Pipeline contracts (SniperContext)
# ---------------------------------------------------------------------------


def capture_pipeline_contracts() -> Dict[str, Any]:
    """Introspect SniperContext field set + type names."""
    try:
        from backend.engine.context import SniperContext  # type: ignore
    except Exception as exc:
        return {"error": f"failed to import SniperContext: {exc!r}"}

    if not is_dataclass(SniperContext):
        return {"error": "SniperContext is not a dataclass"}

    flds = []
    for f in fields(SniperContext):
        # Render type name compactly; full repr may include generics
        type_str = str(f.type) if isinstance(f.type, str) else repr(f.type)
        flds.append(
            {
                "name": f.name,
                "type": type_str,
                "has_default": f.default is not f.default_factory,
            }
        )
    flds.sort(key=lambda x: x["name"])
    return {"sniper_context_fields": flds, "field_count": len(flds)}


# ---------------------------------------------------------------------------
# Capture: DB + JSONL schemas
# ---------------------------------------------------------------------------


def _parse_create_tables(source: str) -> List[Dict[str, Any]]:
    """Inspect literal declarations with SQLite; reject unresolved DDL."""
    from backend.diagnostics.storage_contracts import sqlite_tables
    tables, unresolved = sqlite_tables(source)
    if unresolved:
        raise ValueError('; '.join(unresolved))
    return tables


def capture_db_contracts() -> Dict[str, Any]:
    """Production SQLite declarations and JSONL writer evidence, independent of history.

    Writer fingerprints are implementation-change detectors, not inferred schemas.
    No historical database or JSONL file is opened by this capture.
    """
    from backend.diagnostics.storage_contracts import capture_storage
    return capture_storage(REPO_ROOT)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


CAPTURES: List[Tuple[str, str, Any]] = [
    ("api_contracts.json", "api_contracts", capture_api_contracts),
    ("telemetry_contracts.json", "telemetry_contracts", capture_telemetry_contracts),
    ("pipeline_contracts.json", "pipeline_contracts", capture_pipeline_contracts),
    ("db_contracts.json", "db_contracts", capture_db_contracts),
]


def _write(payload: Dict[str, Any], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")


def _capture_problem(data: Any) -> Optional[str]:
    """A matching failure record is never a successful contract capture."""
    if not isinstance(data, dict):
        return "capture must return an object"
    if "error" in data:
        return f"capture error: {data['error']!r}"
    if data.get("unresolved"):
        return str(data["unresolved"])
    return None


def cmd_capture() -> int:
    """Capture all inventories successfully before replacing any baseline."""
    print("[capture_contracts] Capturing baselines -> %s" % CONTRACTS_DIR)
    snapshots = []
    errors = []
    for filename, label, fn in CAPTURES:
        try:
            data = fn()
        except Exception as exc:
            data = {"error": f"capture failed: {exc!r}"}
        problem = _capture_problem(data)
        if problem:
            errors.append(f"  - {label}: INCOMPLETE ({problem})")
        snapshots.append((filename, label, data))
    if errors:
        print("\n".join(errors))
        print("[capture_contracts] No baselines changed; incomplete capture.")
        return 1
    for filename, label, data in snapshots:
        target = CONTRACTS_DIR / filename
        _write(data, target)
        print(f"  - {label}: OK -> {target}")
    print("[capture_contracts] done.")
    return 0


def _diff_dicts(label: str, baseline: Any, current: Any, path: str = "") -> List[str]:
    """Recursively diff inventories; index lists only by unique complete identities."""
    lines: List[str] = []
    if type(baseline) is not type(current):
        return [f"  {label}{path}: type changed ({type(baseline).__name__} → {type(current).__name__})"]
    if isinstance(baseline, dict):
        b_keys, c_keys = set(baseline), set(current)
        for k in sorted(b_keys - c_keys):
            lines.append(f"  {label}{path}: removed key '{k}'")
        for k in sorted(c_keys - b_keys):
            lines.append(f"  {label}{path}: added key '{k}'")
        for k in sorted(b_keys & c_keys):
            lines.extend(_diff_dicts(label, baseline[k], current[k], path + f".{k}"))
    elif isinstance(baseline, list):
        items = baseline + current
        if items and all(isinstance(item, dict) for item in items):
            candidates = (("source", "table"), ("source", "symbol"), ("path", "methods"),
                          ("path",), ("table",), ("name",), ("id",))
            for fields in candidates:
                if not all(all(field in item for field in fields) for item in items):
                    continue
                def identity(item):
                    return tuple(json.dumps(item[field], sort_keys=True) for field in fields)
                b_idx = {identity(item): item for item in baseline}
                c_idx = {identity(item): item for item in current}
                if len(b_idx) != len(baseline) or len(c_idx) != len(current):
                    continue
                key_label = ",".join(fields)
                for key in sorted(b_idx.keys() - c_idx.keys()):
                    lines.append(f"  {label}{path}: removed item ({key_label}={key!r})")
                for key in sorted(c_idx.keys() - b_idx.keys()):
                    lines.append(f"  {label}{path}: added item ({key_label}={key!r})")
                for key in sorted(b_idx.keys() & c_idx.keys()):
                    lines.extend(_diff_dicts(label, b_idx[key], c_idx[key], path + f"[{key_label}={key!r}]"))
                return lines
        if baseline != current:
            lines.append(f"  {label}{path}: list changed (len {len(baseline)} → {len(current)})")
    elif baseline != current:
        lines.append(f"  {label}{path}: {baseline!r} → {current!r}")
    return lines


def cmd_diff() -> int:
    """Compare current code against baseline; incomplete evidence always fails."""
    print("[capture_contracts] Diffing current vs baseline...")
    total_drift = 0
    summary_lines: List[str] = []
    detail_lines: List[str] = []
    for filename, label, fn in CAPTURES:
        target = CONTRACTS_DIR / filename
        try:
            current = fn()
        except Exception as exc:
            current = {"error": f"capture failed: {exc!r}"}
        problem = _capture_problem(current)
        if problem:
            summary_lines.append(f"  - {label}: INCOMPLETE ({problem})")
            total_drift += 1
            continue
        try:
            with target.open("r", encoding="utf-8") as fh:
                baseline = json.load(fh)
        except (OSError, UnicodeError, ValueError) as exc:
            summary_lines.append(f"  - {label}: BASELINE UNAVAILABLE ({exc})")
            total_drift += 1
            continue
        problem = _capture_problem(baseline)
        if problem:
            summary_lines.append(f"  - {label}: INVALID BASELINE ({problem})")
            total_drift += 1
            continue
        diffs = _diff_dicts(label, baseline, current)
        if diffs:
            summary_lines.append(f"  - {label}: DRIFT ({len(diffs)} changes)")
            detail_lines.extend(diffs)
            total_drift += len(diffs)
        else:
            summary_lines.append(f"  - {label}: clean")
    print("\n=== SUMMARY ===")
    print("\n".join(summary_lines))
    if detail_lines:
        print("\n=== DETAIL ===")
        print("\n".join(detail_lines))
    print(f"\n=== RESULT: {'DRIFT/INCOMPLETE' if total_drift else 'CLEAN'} ({total_drift} changes) ===")
    return 0 if total_drift == 0 else 1


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "diff"
    if cmd == "capture":
        return cmd_capture()
    if cmd == "diff":
        return cmd_diff()
    print(
        "Usage: python -m backend.diagnostics.capture_contracts {capture|diff}",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
