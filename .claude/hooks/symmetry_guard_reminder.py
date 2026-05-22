#!/usr/bin/env python3
"""PostToolUse hook: remind about symmetry-guard when CLAUDE.md §10 standing-fix files are edited.

Reads Claude Code hook JSON from stdin, inspects ``tool_input.file_path`` against
the standing-fix surface regex list, and prints a one-line stderr reminder on match.

Non-blocking by design: always exits 0, never raises. A hook that breaks the
tool call is worse than a missed reminder. Malformed input -> silent exit 0.

Wired via .claude/settings.json PostToolUse matcher ``Edit|Write|MultiEdit``.
"""
from __future__ import annotations

import json
import re
import sys

# Patterns mirror CLAUDE.md §10 Standing Fixes + symmetry-guard.md "Standing-Fix Surface" table.
# Suffix-anchored ($) so absolute paths and repo-relative paths both match.
WATCHED = [
    re.compile(r"backend[/\\]strategy[/\\]confluence[/\\]scorer\.py$"),
    re.compile(r"backend[/\\]engine[/\\]orchestrator\.py$"),
    re.compile(r"backend[/\\]analysis[/\\]regime_.*\.py$"),
    re.compile(r"backend[/\\]shared[/\\]config[/\\]scanner_modes\.py$"),
    re.compile(r"backend[/\\]strategy[/\\]smc[/\\].*\.py$"),
    re.compile(r"backend[/\\]services[/\\]smc_service\.py$"),
]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # malformed input must never block a tool call

    tool_input = payload.get("tool_input") or {}
    fp = tool_input.get("file_path") or ""
    if not fp:
        return 0

    fp_norm = fp.replace("\\", "/")

    for pat in WATCHED:
        if pat.search(fp_norm):
            sys.stderr.write(
                f"[symmetry-guard reminder] you just edited {fp} "
                "(CLAUDE.md §10 standing-fix surface). "
                "Invoke the symmetry-guard agent and paste its report verbatim "
                "alongside the §16 audit before declaring this change complete (§18).\n"
            )
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
