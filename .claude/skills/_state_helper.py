"""
Cross-skill state helper for the SniperSight post-run debug skill set.

Purpose
-------
Skills (`/autopsy`, `/trade-autopsy`, `/scan-autopsy`, `/rejection-survey`,
`/confluence-trace`) operate on the same sessions and frequently re-investigate
findings already resolved by a sibling skill. This helper provides a tiny,
explicit JSON state layer at `.claude/.skill-state/session-<session_id>.json`
so a later skill can SEE prior verdicts and annotate its output accordingly.

Design principles (per CLAUDE.md §11 / §16)
-------------------------------------------
1. **Memory layer, not control layer.** Skills MUST still re-run their analysis
   fresh; the state file only ANNOTATES output. A skill that reads prior state
   and skips work is broken — it would mask regressions.
2. **Idempotent upserts.** Findings are keyed by `(session_id, thread_key)`;
   re-writing a finding overwrites the prior one. Re-running a skill twice on
   the same session produces the same final state.
3. **Loud failures.** Corrupt/missing files return empty state, never exceptions.
   Write failures log to stderr at WARNING but don't take the skill down.
4. **Schema-stable.** Top-level keys (`resolved_findings`, `observability_gaps`,
   `vocabulary_drift`) are append-only in semantics. New keys may be added in
   future without breaking existing readers.

State file shape
----------------
```
{
  "session_id": "3544b1b6",
  "window": {"start": "...", "end": "..."},        // optional
  "first_seen": "<utc>",
  "last_updated": "<utc>",
  "resolved_findings": [
    {
      "thread_key": "hi-conf-loss-<trade_id>",     // stable identifier
      "skill": "trade-autopsy",
      "verdict": "EXPECTED-LOSS-NO-BUG",
      "summary": "geometry worked; entry-timing failure",
      "ts": "<utc>"
    },
    ...
  ],
  "observability_gaps": [
    {
      "id": "ml-rejections-not-in-telemetry",      // canonical kebab-case id
      "first_seen": "<utc>",
      "status": "open" | "patched" | "wontfix",
      "summary": "ml_gate filters via _log_signal but no signal_rejected telemetry"
    },
    ...
  ],
  "vocabulary_drift": [
    {
      "reason": "<new reason text>",
      "gate_name": "<new gate>",
      "first_seen": "<utc>",
      "count": 5
    },
    ...
  ]
}
```

CLI invocations (called from skills via Bash)
---------------------------------------------
    python .claude/skills/_state_helper.py read <session_id>
    python .claude/skills/_state_helper.py write-finding <session_id> <thread_key> <skill> <verdict> [summary]
    python .claude/skills/_state_helper.py write-gap <session_id> <gap_id> <status> [summary]
    python .claude/skills/_state_helper.py write-drift <session_id> <reason> <gate_name>
    python .claude/skills/_state_helper.py list-findings <session_id>
    python .claude/skills/_state_helper.py list-gaps <session_id>

Read-only operations exit 0 with JSON or empty output. Write operations exit 0
on success, 1 on filesystem failure. All commands write to stdout (JSON or
human-readable lines per the command), never to stderr unless an error occurs.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


_STATE_DIR = Path(__file__).resolve().parent.parent / ".skill-state"


def _now() -> str:
    """UTC timestamp for state-file fields."""
    return datetime.now(timezone.utc).isoformat()


def _state_path(session_id: str) -> Path:
    """Resolve the JSON file path for a session_id."""
    return _STATE_DIR / f"session-{session_id}.json"


def read_session_state(session_id: str) -> Optional[Dict[str, Any]]:
    """Return parsed state dict, or None if missing/unreadable.

    Per design principle 3 (loud failures): missing file → None (no error);
    unreadable file → None with stderr warning (corruption is reported but
    doesn't crash the skill).
    """
    path = _state_path(session_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"warning: state file unreadable: {path} ({exc})", file=sys.stderr)
        return None


def _ensure_state(session_id: str) -> Dict[str, Any]:
    """Load existing state or initialise a new one."""
    state = read_session_state(session_id)
    if state is None:
        state = {
            "session_id": session_id,
            "first_seen": _now(),
            "last_updated": _now(),
            "resolved_findings": [],
            "observability_gaps": [],
            "vocabulary_drift": [],
        }
    return state


def _save_state(session_id: str, state: Dict[str, Any]) -> bool:
    """Persist state to disk. Returns True on success."""
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        state["last_updated"] = _now()
        path = _state_path(session_id)
        path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        return True
    except Exception as exc:
        print(f"warning: state file write failed: {exc}", file=sys.stderr)
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Public API — findings
# ──────────────────────────────────────────────────────────────────────────────


def write_finding(
    session_id: str,
    thread_key: str,
    skill: str,
    verdict: str,
    summary: str = "",
) -> bool:
    """Record a resolved finding. Idempotent upsert by (session_id, thread_key)."""
    state = _ensure_state(session_id)
    findings: List[Dict[str, Any]] = state.setdefault("resolved_findings", [])
    # Upsert: remove any existing entry with the same thread_key, then append.
    findings = [f for f in findings if f.get("thread_key") != thread_key]
    findings.append({
        "thread_key": thread_key,
        "skill": skill,
        "verdict": verdict,
        "summary": summary,
        "ts": _now(),
    })
    state["resolved_findings"] = findings
    # Mass-conservation: every thread_key appears exactly once after upsert.
    keys = [f["thread_key"] for f in findings]
    assert len(keys) == len(set(keys)), (
        f"state-helper invariant violated — duplicate thread_key in {session_id}"
    )
    return _save_state(session_id, state)


def list_findings(session_id: str) -> List[Dict[str, Any]]:
    """Return all resolved findings for a session (empty list if none)."""
    state = read_session_state(session_id)
    if not state:
        return []
    return state.get("resolved_findings", []) or []


def get_finding(session_id: str, thread_key: str) -> Optional[Dict[str, Any]]:
    """Return a specific finding by thread_key, or None."""
    for f in list_findings(session_id):
        if f.get("thread_key") == thread_key:
            return f
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Public API — observability gaps
# ──────────────────────────────────────────────────────────────────────────────


def write_gap(
    session_id: str,
    gap_id: str,
    status: str = "open",
    summary: str = "",
) -> bool:
    """Record an observability gap. Idempotent upsert by (session_id, gap_id)."""
    if status not in ("open", "patched", "wontfix"):
        print(f"warning: unrecognised gap status '{status}', expected open/patched/wontfix",
              file=sys.stderr)
    state = _ensure_state(session_id)
    gaps: List[Dict[str, Any]] = state.setdefault("observability_gaps", [])
    existing = next((g for g in gaps if g.get("id") == gap_id), None)
    if existing:
        # Preserve first_seen, update status + summary
        existing["status"] = status
        if summary:
            existing["summary"] = summary
    else:
        gaps.append({
            "id": gap_id,
            "first_seen": _now(),
            "status": status,
            "summary": summary,
        })
    state["observability_gaps"] = gaps
    return _save_state(session_id, state)


def list_gaps(session_id: str) -> List[Dict[str, Any]]:
    """Return all observability gaps recorded for a session."""
    state = read_session_state(session_id)
    if not state:
        return []
    return state.get("observability_gaps", []) or []


# ──────────────────────────────────────────────────────────────────────────────
# Public API — vocabulary drift
# ──────────────────────────────────────────────────────────────────────────────


def write_drift(
    session_id: str,
    reason: str,
    gate_name: Optional[str] = None,
) -> bool:
    """Record a vocabulary-drift entry. Increments count on existing matches."""
    state = _ensure_state(session_id)
    drift: List[Dict[str, Any]] = state.setdefault("vocabulary_drift", [])
    existing = next(
        (d for d in drift if d.get("reason") == reason and d.get("gate_name") == gate_name),
        None,
    )
    if existing:
        existing["count"] = (existing.get("count", 1) or 0) + 1
    else:
        drift.append({
            "reason": reason,
            "gate_name": gate_name,
            "first_seen": _now(),
            "count": 1,
        })
    state["vocabulary_drift"] = drift
    return _save_state(session_id, state)


def list_drift(session_id: str) -> List[Dict[str, Any]]:
    """Return all vocabulary-drift entries for a session."""
    state = read_session_state(session_id)
    if not state:
        return []
    return state.get("vocabulary_drift", []) or []


# ──────────────────────────────────────────────────────────────────────────────
# CLI dispatch
# ──────────────────────────────────────────────────────────────────────────────


_USAGE = """\
Usage:
  python _state_helper.py read <session_id>
  python _state_helper.py write-finding <session_id> <thread_key> <skill> <verdict> [summary]
  python _state_helper.py write-gap     <session_id> <gap_id> [status=open] [summary]
  python _state_helper.py write-drift   <session_id> <reason> [gate_name]
  python _state_helper.py list-findings <session_id>
  python _state_helper.py list-gaps     <session_id>
  python _state_helper.py list-drift    <session_id>
"""


def _main(argv: List[str]) -> int:
    if len(argv) < 2:
        print(_USAGE, file=sys.stderr)
        return 2
    cmd = argv[1]
    try:
        if cmd == "read":
            sid = argv[2]
            state = read_session_state(sid)
            print(json.dumps(state, indent=2) if state else "{}")
            return 0
        if cmd == "write-finding":
            sid, thread_key, skill, verdict = argv[2], argv[3], argv[4], argv[5]
            summary = argv[6] if len(argv) > 6 else ""
            ok = write_finding(sid, thread_key, skill, verdict, summary)
            return 0 if ok else 1
        if cmd == "write-gap":
            sid, gap_id = argv[2], argv[3]
            status = argv[4] if len(argv) > 4 else "open"
            summary = argv[5] if len(argv) > 5 else ""
            ok = write_gap(sid, gap_id, status, summary)
            return 0 if ok else 1
        if cmd == "write-drift":
            sid, reason = argv[2], argv[3]
            gate = argv[4] if len(argv) > 4 else None
            ok = write_drift(sid, reason, gate)
            return 0 if ok else 1
        if cmd == "list-findings":
            sid = argv[2]
            for f in list_findings(sid):
                print(f"{f.get('skill','?'):20s}  {f.get('thread_key','?'):40s}  {f.get('verdict','?')}")
            return 0
        if cmd == "list-gaps":
            sid = argv[2]
            for g in list_gaps(sid):
                print(f"{g.get('id','?'):40s}  {g.get('status','?'):10s}  {g.get('summary','')}")
            return 0
        if cmd == "list-drift":
            sid = argv[2]
            for d in list_drift(sid):
                print(f"{d.get('gate_name','?'):30s}  count={d.get('count','?'):>4}  reason={(d.get('reason','') or '')[:60]}")
            return 0
        print(_USAGE, file=sys.stderr)
        return 2
    except IndexError:
        print(_USAGE, file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
