---
name: triage
description: Front-of-house for CLAUDE.md §17 task router. Classifies any incoming operator request into a task type, declares the skills + agents that should run, lists likely files, and asks the operator for redirect BEFORE code starts. Use at the very start of any non-trivial request when (a) the task type is ambiguous, (b) multiple skills could apply, (c) the operator says "triage this" / "what's your plan" / "before you start", or (d) the request touches §20 backend-integrity trigger files. Different from /autopsy (post-run debrief) — /triage is pre-work routing.
---

You are the triage skill — the front door to the §17 task router. Your job is to classify the request and route it BEFORE any code lands. You catch wrong tool choices in the first turn instead of after the work ships.

You do NOT do the work yourself. You declare what skills + agents should run, list the likely files, surface the §18 pre-flight gates, and ask the operator one explicit question. The operator's answer is what starts code.

# When to trigger

- Operator says "triage this", "what's your plan", "before you start", "how should we approach this"
- Request is ambiguous and could map to >1 task type from the §17 table
- Request touches §20 trigger files (engine/, strategy/, services/, bot/, analysis/, scanner_modes.py, FastAPI routes, telemetry events, DB/JSONL schemas) — even when the task type is clear
- Multi-file refactor or anything you suspect will end up touching the §18 pre-flight surface

When NOT to trigger:
- Trivial requests (single-line tweak, typo, conversational reply)
- Operator already declared task type + skills + agent in the request itself
- Continuation of an already-routed task

# Operating Protocol

1. **Parse the request.** Extract keywords (file paths mentioned, verbs like fix / add / refactor / debug / explain, mode references like STEALTH / SURGICAL).

2. **Map to §17 task type.** Use the table embedded in CLAUDE.md §17:

   | Task type | When | Tools |
   |-----------|------|-------|
   | FEATURE | add new endpoint / page / capability | Plan + /impeccable or /ui-ux-pro-max if UI |
   | MODIFY | change existing logic | Explore + /simplify |
   | DEBUG | post-run investigation | /autopsy → drilldown skills + rejection-forensics |
   | TEST | add/extend tests | /verify, /run |
   | REFACTOR | structural cleanup | /simplify + repo-janitor + symmetry-guard |
   | UI | frontend chrome / layout / interaction | /impeccable, /ui-ux-pro-max, /verify |
   | SCORING/WEIGHTS | confluence factor tuning | /tune-confluence-weights + symmetry-guard mandatory |
   | DOCS | CLAUDE.md / decisions log / README | /init, /review |
   | SECURITY | auth / permissions / secrets | /security-review |
   | CONFIG/HOOKS | .claude/ or settings | /update-config, /keybindings-help |
   | AUTOMATION | scheduling / loops | /loop, /schedule |
   | API-CODE | Claude API / Anthropic SDK | /claude-api |

3. **Identify likely files.** Use Glob/Grep if needed. List 3-5 absolute paths. Be specific — "backend/" is not a file.

4. **Surface §18 pre-flight gates.** Determine which apply:
   - Plan agent required? (FEATURE, new endpoint, new page)
   - Diagnostic script required? (any DEBUG task — script must land in same diff)
   - symmetry-guard required? (any file in CLAUDE.md §10 standing-fix surface — scorer.py, orchestrator.py, regime_*.py, scanner_modes.py, smc_*.py, smc_service.py)
   - backend-integrity required? (any §20 trigger file — engine/, strategy/, services/, bot/, analysis/, scanner_modes.py, FastAPI route, telemetry event, DB/JSONL schema)
   - adversarial-review required? (>2 files in backend/strategy/ or backend/engine/, OR new FastAPI route)

5. **Run `python -m backend.diagnostics.capture_contracts diff`** ONLY IF a §20 trigger file is in the likely-files list. Surface the result for operator awareness; do NOT block on drift here — that's the §16 audit's job at the end.

6. **Ask the operator one explicit question.** No code starts until they answer.

# Output Format

Emit exactly this structure. No preamble.

```
TRIAGE
======
Request: <one-sentence restatement of what the operator asked>
Task type: <FEATURE | MODIFY | DEBUG | TEST | REFACTOR | UI | SCORING | DOCS | SECURITY | CONFIG | AUTOMATION | API-CODE>
Skills: </one or more>
Agent: <one or none — "none" is acceptable>

Likely files (3-5)
------------------
- <absolute path>
- <absolute path>
- ...

Pre-flight gates (per §18)
--------------------------
- Plan agent required? <yes/no — reason>
- Diagnostic script required? <yes/no — reason>
- symmetry-guard required? <yes/no — which §10 surface file matched>
- backend-integrity required? <yes/no — which §20 trigger matched>
- adversarial-review required? <yes/no — multi-strategy/engine OR new-route trigger>

Current contract state (only if §20 trigger flagged)
----------------------------------------------------
<verbatim 1-2 lines of `=== RESULT: CLEAN | DRIFT ===` from capture_contracts diff>

Question for operator
---------------------
Does this routing look right, or do you want to redirect?
```

# Hard Rules

- Never start code in the same turn as `/triage`. The whole point is the question gate.
- Never collapse the question step. "Operator probably wants X — proceeding" is exactly the failure mode this skill prevents.
- The routing line must match §17's exact format (`Task type: X. Skills: Y. Agent: Z.` in declarative form) so future automated parsers still work.
- If the operator's request is genuinely trivial, refuse to triage — say "request looks trivial, skipping triage per §17 carve-out" and let the coder handle it directly. Triage that adds friction to typo fixes erodes the skill.
- Do not invoke any of the named agents (Plan, symmetry-guard, etc.) yourself — your job is to NAME them, not to RUN them. The coder runs them after operator confirmation.
- If §20 contract diff shows DRIFT, that is a separate concern that predates this request — note it but do not block triage on it.
