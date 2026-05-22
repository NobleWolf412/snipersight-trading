#!/usr/bin/env python3
"""PreToolUse hook: block git commit if a recent Agent (subagent) invocation has no
matching verbatim-paste signal in the conversation transcript.

Calibrated on the §16 "Verbatim-paste enforcement" subsection of CLAUDE.md
(3a'/3a''/3z.h slip incidents): coder repeatedly summarized audit/symmetry-guard/
adversarial-review output instead of pasting the raw Section 1/2/3 block. This
hook makes the slip impossible to commit-out.

Activation: PreToolUse on Bash matching `git commit`. Reads transcript_path from the
hook payload and inspects the last N user/assistant turns. If a recent Agent tool use
exists, the assistant text after it must contain at least one known verbatim signal
(Section 1, SYMMETRY-GUARD REPORT, BACKEND-INTEGRITY REPORT, ADVERSARIAL REVIEW,
or a markdown status-table header). Otherwise the commit is blocked.

Non-blocking on hook-internal errors — better to allow a commit than to wedge the
loop. The §16 audit subagent itself is the redundant gate.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

# Window size: how far back to look for an Agent invocation. The transcript can be
# long; we only care about Agent invocations relatively close to this commit.
LOOKBACK_TURNS = 60

# Verbatim-paste signals. ANY of these in the post-Agent assistant text satisfies the gate.
VERBATIM_SIGNALS = [
    re.compile(r"\bSection\s*1\b", re.IGNORECASE),
    re.compile(r"\bSection\s*2\b", re.IGNORECASE),
    re.compile(r"\bSection\s*3\b", re.IGNORECASE),
    re.compile(r"SYMMETRY-GUARD\s+REPORT", re.IGNORECASE),
    re.compile(r"BACKEND-INTEGRITY\s+REPORT", re.IGNORECASE),
    re.compile(r"ADVERSARIAL\s+REVIEW", re.IGNORECASE),
    # Status table marker: `| # | Rubric |` or similar audit table headers
    re.compile(r"\|\s*#\s*\|\s*Rubric", re.IGNORECASE),
    # Explicit verbatim phrase from CLAUDE.md §16
    re.compile(r"verbatim", re.IGNORECASE),
]

# Agent subagent_type values whose output MUST be pasted. Extending this list is the
# right move when a new audit-style agent ships.
GATED_AGENT_TYPES = {
    "general-purpose",  # the §16 audit subagent runs here
    "symmetry-guard",
    "backend-integrity",
    "adversarial-review",
    "Plan",  # §18 Pre-flight requires Plan agent output pasted verbatim
}

COMMIT_RE = re.compile(r"^\s*git\s+commit\b", re.IGNORECASE)


def _is_git_commit(payload: dict) -> bool:
    tool_name = payload.get("tool_name") or ""
    if tool_name != "Bash":
        return False
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    return bool(COMMIT_RE.search(cmd))


def _iter_transcript_messages(path: str):
    """Yield message dicts from a Claude Code JSONL transcript, oldest first.

    Tolerant of variant schemas: returns whatever dicts are in the file.
    """
    p = Path(path)
    if not p.exists():
        return
    try:
        with p.open("r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    continue
    except Exception:
        return


def _extract_assistant_text(message: Any) -> str:
    """Pull plain text out of an ASSISTANT transcript message.

    Critically excludes ``tool_result`` blocks — those carry the subagent's own output
    back to the model, NOT the coder's paste. The §16 verbatim-paste rule requires the
    coder to put the agent output into their assistant text, so that is the only place
    we count signals.

    Non-assistant messages (user, tool_result wrappers) return empty.
    """
    if not isinstance(message, dict):
        return ""
    # Newer harnesses wrap: {message: {role, content}}; older may be flat.
    inner = message.get("message", message) if isinstance(message.get("message"), dict) else message
    if not isinstance(inner, dict):
        return ""
    role = inner.get("role")
    if role != "assistant":
        return ""
    content = inner.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                # ONLY plain text blocks count — tool_use / tool_result excluded.
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return ""


def _find_recent_agent_invocation(messages: list[dict]) -> int | None:
    """Return the index of the most recent Agent (Task) tool_use in the last LOOKBACK window.

    Returns None if none found.
    """
    window = messages[-LOOKBACK_TURNS:] if len(messages) > LOOKBACK_TURNS else messages
    offset = len(messages) - len(window)
    for rel_idx, msg in reversed(list(enumerate(window))):
        # Search message content for tool_use blocks of name "Task" / "Agent"
        m = msg.get("message", msg) if isinstance(msg, dict) else {}
        content = m.get("content") if isinstance(m, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use":
                continue
            name = block.get("name") or ""
            if name not in ("Task", "Agent"):
                continue
            sub_input = block.get("input") or {}
            sub_type = sub_input.get("subagent_type") or ""
            if sub_type in GATED_AGENT_TYPES:
                return offset + rel_idx
    return None


def _verbatim_signal_present(text: str) -> bool:
    if not text:
        return False
    for sig in VERBATIM_SIGNALS:
        if sig.search(text):
            return True
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # malformed input must never block

    if not _is_git_commit(payload):
        return 0

    transcript_path = payload.get("transcript_path") or ""
    if not transcript_path:
        # Newer/older harnesses may not include transcript_path. Best-effort fail-open.
        return 0

    try:
        messages = list(_iter_transcript_messages(transcript_path))
    except Exception:
        return 0

    if not messages:
        return 0

    agent_idx = _find_recent_agent_invocation(messages)
    if agent_idx is None:
        return 0  # no gated Agent invocation recently — nothing to enforce

    # Check assistant text AFTER the agent invocation for a verbatim signal.
    # _extract_assistant_text returns "" for user / tool_result messages, so we only
    # see what the coder actually put in their own response — not what the subagent
    # returned via tool_result.
    post_agent = messages[agent_idx + 1 :]
    accumulated = "\n".join(_extract_assistant_text(m) for m in post_agent)

    if _verbatim_signal_present(accumulated):
        sys.stderr.write(
            "[verbatim_paste_enforcer] verbatim signal found after recent gated Agent invocation; "
            "commit proceeds.\n"
        )
        return 0

    reason = (
        "[verbatim_paste_enforcer] A recent Agent invocation (audit / symmetry-guard / "
        "backend-integrity / adversarial-review / Plan) was followed by NO verbatim-paste "
        "signal in the assistant transcript before this commit. Per CLAUDE.md §16 "
        '"Verbatim-paste enforcement" + §18 Pre-flight Discipline, the agent\'s full output '
        "block must appear verbatim in the response message body (look for headers like "
        "'Section 1' / 'SYMMETRY-GUARD REPORT' / 'ADVERSARIAL REVIEW' / a status table with "
        "`| # | Rubric |`). Coder-authored summary tables do NOT satisfy the rule, even on a "
        "clean ✅ pass (calibrated on 3a'/3a''/3z.h). Paste the verbatim block, then retry "
        "the commit."
    )
    response = {"decision": "block", "reason": reason}
    sys.stdout.write(json.dumps(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
