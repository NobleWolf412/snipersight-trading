#!/usr/bin/env python3
"""PreToolUse hook: run `npx tsc --noEmit` before any git commit that touches src/ or tests/visual/.

Skips if no TypeScript files are staged (commits that only touch backend/, docs, or
configuration files don't trigger the cost). On tsc failure, blocks the commit with
the error output so the coder can fix before retrying.

Wired via .claude/settings.json PreToolUse matcher `Bash`. Hook decides itself whether
to fire based on the actual command + staged file list.

Non-blocking on hook-internal errors (network hiccup, npx missing, etc.) — exits 0
with stderr warning. Better to miss a typecheck than to wedge commits.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys


COMMIT_RE = re.compile(r"^\s*git\s+commit\b", re.IGNORECASE)
TS_PATTERNS = [
    re.compile(r"(^|/)src/.+\.(ts|tsx)$"),
    re.compile(r"(^|/)tests/visual/.+\.ts$"),
]


def _is_git_commit(payload: dict) -> bool:
    tool_name = payload.get("tool_name") or ""
    if tool_name != "Bash":
        return False
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    return bool(COMMIT_RE.search(cmd))


def _has_staged_ts_files() -> bool:
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        # Git unavailable or timed out — let the commit proceed; tsc skip is the safe default.
        return False
    if out.returncode != 0:
        return False
    for line in (out.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        for pat in TS_PATTERNS:
            if pat.search(line):
                return True
    return False


def _run_tsc() -> tuple[int, str]:
    """Return (returncode, combined-output)."""
    try:
        out = subprocess.run(
            ["npx", "--no-install", "tsc", "--noEmit", "-p", "tsconfig.json"],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        return 124, "[pre_commit_typecheck] tsc timed out (180s); skipping enforcement"
    except FileNotFoundError:
        return 0, "[pre_commit_typecheck] npx not on PATH; skipping enforcement"
    except Exception as exc:
        return 0, f"[pre_commit_typecheck] tsc launch failed: {exc!r}; skipping enforcement"
    return out.returncode, (out.stdout or "") + (out.stderr or "")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # malformed input must never block

    if not _is_git_commit(payload):
        return 0  # not a commit; allow

    if not _has_staged_ts_files():
        return 0  # no TS staged; skip tsc cost

    rc, output = _run_tsc()
    if rc == 0:
        # Pass — short stderr note for transparency; no block.
        sys.stderr.write("[pre_commit_typecheck] tsc --noEmit clean; commit proceeds.\n")
        return 0

    # Skip-enforcement codes from _run_tsc (timeout, npx missing) return rc != 0 with
    # a documented marker in `output`. Don't block on those; just warn.
    if "skipping enforcement" in (output or ""):
        sys.stderr.write(output + "\n")
        return 0

    # tsc failed substantively — block the commit with the error output as the reason.
    reason = (
        "[pre_commit_typecheck] tsc --noEmit failed; commit blocked. Fix the type "
        "errors below and re-stage:\n\n"
    ) + (output or "<no output>")
    response = {"decision": "block", "reason": reason}
    sys.stdout.write(json.dumps(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
