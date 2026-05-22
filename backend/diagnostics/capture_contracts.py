"""
Contract capture + diff for SniperSight backend integrity (CLAUDE.md §20).

Captures frozen snapshots of:
  - API route inventory (path, method, response model name)
  - Telemetry event types + factory function payload keys
  - SniperContext field set
  - SQLite + JSONL schemas

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


_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\((.*?)\)",
    re.IGNORECASE | re.DOTALL,
)


def _parse_create_tables(source: str) -> List[Dict[str, Any]]:
    """Parse all CREATE TABLE statements from a Python source string."""
    out: List[Dict[str, Any]] = []
    for match in _CREATE_TABLE_RE.finditer(source):
        table = match.group(1)
        body = match.group(2)
        # Extract column names — first token of each comma-separated entry
        cols: List[str] = []
        for part in body.split(","):
            part = part.strip()
            if not part:
                continue
            # Skip standalone constraints (PRIMARY KEY, FOREIGN KEY, etc when not inline)
            if part.upper().startswith(("PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "CHECK", "CONSTRAINT")):
                continue
            tok = part.split()[0].strip('`"[]')
            if tok and tok.isidentifier():
                cols.append(tok)
        out.append({"table": table, "columns": sorted(cols)})
    out.sort(key=lambda x: x["table"])
    return out


def capture_db_contracts() -> Dict[str, Any]:
    """Scan storage / persistence modules for CREATE TABLE schemas + JSONL key samples."""
    db_tables: List[Dict[str, Any]] = []

    # Telemetry storage
    telemetry_storage = REPO_ROOT / "backend" / "bot" / "telemetry" / "storage.py"
    if telemetry_storage.exists():
        src = telemetry_storage.read_text(encoding="utf-8", errors="ignore")
        for t in _parse_create_tables(src):
            t["source"] = "backend/bot/telemetry/storage.py"
            db_tables.append(t)

    # Other persistence (best-effort: scan backend/bot for CREATE TABLE).
    # Skips logged to stderr per §11 loud-failure preference.
    skipped: List[str] = []
    for py in (REPO_ROOT / "backend").rglob("*.py"):
        if "venv" in py.parts or "__pycache__" in py.parts:
            continue
        if py == telemetry_storage:
            continue
        try:
            src = py.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            rel = str(py.relative_to(REPO_ROOT)).replace("\\", "/")
            print(f"[capture_contracts] skipped {rel}: {exc!r}", file=sys.stderr)
            skipped.append(rel)
            continue
        if "CREATE TABLE" not in src:
            continue
        for t in _parse_create_tables(src):
            t["source"] = str(py.relative_to(REPO_ROOT)).replace("\\", "/")
            db_tables.append(t)

    db_tables.sort(key=lambda x: (x["source"], x["table"]))

    # JSONL contracts — sniff canonical key set from first line of each .jsonl.
    # Exclude:
    #   - venv / __pycache__: artifact dirs
    #   - logs/ at repo root: runtime-emitted per-session signals.jsonl files
    #     (gitignored under the existing `logs` + `*.log` patterns in
    #     .gitignore; each paper-trader session creates a new path which
    #     would drift the baseline without representing an actual schema
    #     change). Canonical JSONLs live under backend/cache/.
    #   The logs/ check is anchored to the FIRST path component relative to
    #   REPO_ROOT to avoid false positives on incidental "logs" segments in
    #   absolute paths (e.g. usernames containing "logs").
    jsonl_files: List[Dict[str, Any]] = []
    for jsonl_glob in ("**/signals.jsonl", "**/trade_journal.jsonl"):
        for path in REPO_ROOT.rglob(jsonl_glob):
            if "venv" in path.parts or "__pycache__" in path.parts:
                continue
            try:
                rel_parts = path.relative_to(REPO_ROOT).parts
            except ValueError:
                rel_parts = path.parts
            if rel_parts and rel_parts[0] == "logs":
                continue
            try:
                with path.open("r", encoding="utf-8", errors="ignore") as fh:
                    first = fh.readline().strip()
                if not first:
                    continue
                obj = json.loads(first)
                if isinstance(obj, dict):
                    jsonl_files.append(
                        {
                            "path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
                            "keys": sorted(list(obj.keys())),
                        }
                    )
            except Exception as exc:
                rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
                print(f"[capture_contracts] skipped {rel}: {exc!r}", file=sys.stderr)
                skipped.append(rel)
                continue

    jsonl_files.sort(key=lambda x: x["path"])
    return {
        "sqlite_tables": db_tables,
        "jsonl_files": jsonl_files,
        "table_count": len(db_tables),
        "jsonl_count": len(jsonl_files),
        "skipped_paths": sorted(skipped),
    }


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


def cmd_capture() -> int:
    """Capture current state as the new baseline."""
    print("[capture_contracts] Capturing baselines -> %s" % CONTRACTS_DIR)
    results: List[str] = []
    for filename, label, fn in CAPTURES:
        try:
            data = fn()
        except Exception as exc:
            data = {"error": f"capture failed: {exc!r}"}
        target = CONTRACTS_DIR / filename
        _write(data, target)
        marker = "OK"
        if "error" in data:
            marker = f"ERR ({data['error']})"
        results.append(f"  - {label}: {marker} -> {target.relative_to(REPO_ROOT)}")
    print("\n".join(results))
    print("[capture_contracts] done.")
    return 0


def _diff_dicts(label: str, baseline: Any, current: Any, path: str = "") -> List[str]:
    """Recursively diff two JSON-like structures. Returns list of human lines."""
    lines: List[str] = []
    if type(baseline) is not type(current):
        lines.append(f"  {label}{path}: type changed ({type(baseline).__name__} → {type(current).__name__})")
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
        # For lists of dicts with a stable identifying field, do a set-style diff
        if baseline and isinstance(baseline[0], dict):
            idx_field = None
            for f in ("path", "table", "name", "id"):
                if f in baseline[0]:
                    idx_field = f
                    break
            if idx_field:
                b_idx = {item.get(idx_field): item for item in baseline if isinstance(item, dict)}
                c_idx = {item.get(idx_field): item for item in current if isinstance(item, dict)}
                for k in sorted(b_idx.keys() - c_idx.keys(), key=lambda x: str(x)):
                    lines.append(f"  {label}{path}: removed item ({idx_field}={k!r})")
                for k in sorted(c_idx.keys() - b_idx.keys(), key=lambda x: str(x)):
                    lines.append(f"  {label}{path}: added item ({idx_field}={k!r})")
                for k in sorted(b_idx.keys() & c_idx.keys(), key=lambda x: str(x)):
                    lines.extend(_diff_dicts(label, b_idx[k], c_idx[k], path + f"[{idx_field}={k!r}]"))
                return lines
        if baseline != current:
            lines.append(f"  {label}{path}: list changed (len {len(baseline)} → {len(current)})")
    else:
        if baseline != current:
            lines.append(f"  {label}{path}: {baseline!r} → {current!r}")
    return lines


def cmd_diff() -> int:
    """Compare current code against baseline; non-zero exit on drift."""
    print("[capture_contracts] Diffing current vs baseline...")
    total_drift = 0
    summary_lines: List[str] = []
    detail_lines: List[str] = []

    for filename, label, fn in CAPTURES:
        target = CONTRACTS_DIR / filename
        if not target.exists():
            summary_lines.append(f"  - {label}: NO BASELINE ({target.relative_to(REPO_ROOT)} missing)")
            total_drift += 1
            continue
        try:
            current = fn()
        except Exception as exc:
            current = {"error": f"capture failed: {exc!r}"}
        with target.open("r", encoding="utf-8") as fh:
            baseline = json.load(fh)
        diffs = _diff_dicts(label, baseline, current)
        if diffs:
            summary_lines.append(f"  - {label}: DRIFT ({len(diffs)} changes)")
            detail_lines.extend(diffs)
            total_drift += len(diffs)
        else:
            summary_lines.append(f"  - {label}: clean")

    # §12 paste-friendly: summary first, detail second, raw last
    print("\n=== SUMMARY ===")
    print("\n".join(summary_lines))
    if detail_lines:
        print("\n=== DETAIL ===")
        print("\n".join(detail_lines))
    print(f"\n=== RESULT: {'DRIFT' if total_drift else 'CLEAN'} ({total_drift} changes) ===")
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
