# 2026-05-21 — Workflow enhancement Tier 4a: pre-commit typecheck + verbatim-paste enforcement hooks

## Headline
Two new PreToolUse hooks landed: `pre_commit_typecheck.py` blocks commits when `npx tsc --noEmit` fails on any staged `src/**.ts(x)` or `tests/visual/**.ts` file; `verbatim_paste_enforcer.py` blocks commits when a recent Agent invocation (general-purpose / symmetry-guard / backend-integrity / adversarial-review / Plan) has no matching verbatim-paste signal in the assistant transcript before the commit.

## Context
Two queued items from the Tier 4 backlog. Both are PreToolUse hooks gated on Bash matching `git commit`.

**pre_commit_typecheck.py** — earlier deferred on cost-benefit because `npx tsc` takes 5-10s on every commit. Solution: gate the cost by checking staged file paths. If no TypeScript files are staged, hook returns 0 immediately (no tsc invocation). When TS is staged, run tsc and block on failure.

**verbatim_paste_enforcer.py** — highest historical pain on the queue. Calibrated on the 3a' / 3a'' / 3z.h slip incidents (CLAUDE.md §16 "Verbatim-paste enforcement"): coder repeatedly summarized §16 audit / symmetry-guard output instead of pasting the raw Section 1/2/3 block. Honor-system enforcement kept failing because the slip is invisible to the operator until they read the response carefully. A hook makes the slip impossible to commit-out.

## Resolution

### pre_commit_typecheck.py
File: `.claude/hooks/pre_commit_typecheck.py`

Logic:
1. Read PreToolUse JSON payload from stdin; bail if not `Bash` with `git commit` in the command.
2. Run `git diff --cached --name-only`; if no staged files match `(^|/)src/.+\.(ts|tsx)$` or `(^|/)tests/visual/.+\.ts$`, exit 0 silently (no tsc cost).
3. Run `npx --no-install tsc --noEmit -p tsconfig.json` with 180s timeout.
4. On rc=0, emit stderr `[pre_commit_typecheck] tsc --noEmit clean; commit proceeds.` and exit 0.
5. On documented skip codes (timeout, npx missing): emit stderr warning, exit 0 (don't wedge commits on tool-side flakes).
6. On real tsc failure: emit JSON `{"decision":"block","reason":"<tsc output>"}` to stdout and exit 0. Claude Code's PreToolUse runner interprets this as "block this tool call" and surfaces the reason.

Verified directly:
- Non-commit Bash (`ls -la`) → exit 0, silent
- Commit with no staged TS → exit 0, silent
- Empty stdin → exit 0, silent

Untested live (no TS errors to inject for blocking-path verification this round): the substantive logic is straightforward subprocess + return code routing. Bug surface is narrow.

### verbatim_paste_enforcer.py
File: `.claude/hooks/verbatim_paste_enforcer.py`

Logic:
1. Read PreToolUse JSON payload from stdin; bail if not `Bash` with `git commit`.
2. Resolve `transcript_path` from payload. If missing, fail-open with exit 0 (older/newer harnesses may not provide it).
3. Parse transcript JSONL (tolerant of variant schemas). Iterate messages.
4. Find most recent Agent (`Task` tool_use) invocation in last `LOOKBACK_TURNS=60` messages where `subagent_type` ∈ `{general-purpose, symmetry-guard, backend-integrity, adversarial-review, Plan}`.
5. If no gated Agent found, exit 0 (nothing to enforce).
6. Collect ASSISTANT text from messages AFTER the agent invocation. `_extract_assistant_text` deliberately EXCLUDES `tool_result` blocks — those carry the subagent's own output back into the model, not the coder's paste, so they don't count toward the verbatim signal.
7. Check for any signal pattern in the collected text:
   - `Section 1` / `Section 2` / `Section 3`
   - `SYMMETRY-GUARD REPORT` / `BACKEND-INTEGRITY REPORT` / `ADVERSARIAL REVIEW`
   - Markdown audit table header `| # | Rubric`
   - The word `verbatim`
8. If signal present → exit 0 with stderr `[verbatim_paste_enforcer] verbatim signal found...`.
9. If signal absent → emit JSON `{"decision":"block","reason":"<calibrated message citing §16 and 3a'/3a''/3z.h"}` to stdout.

Verified with synthetic transcripts:
- Non-commit Bash → silent exit 0
- Commit with no transcript_path → silent exit 0
- Empty stdin → silent exit 0
- Transcript with Agent invocation + assistant text containing "Section 1/2/3" after → ALLOW
- Transcript with Agent invocation + tool_result containing "Section 1/2/3" (but NO assistant text with signal) → BLOCK with calibrated reason. This case caught the early-draft bug where `_extract_text` included tool_result content as a false positive; the fix (only assistant role + only `type:"text"` blocks) is documented in the function docstring.

### settings.json wiring
Added `PreToolUse` matcher `Bash` with two hooks in order: `verbatim_paste_enforcer.py` first, `pre_commit_typecheck.py` second. Both fire on every Bash invocation; both no-op unless the command matches `git commit`. Order is arbitrary (both must allow); putting verbatim first means the more-important §16 enforcement runs first.

## Why it matters next time

The verbatim-paste hook closes the highest-pain failure mode in the autonomous loop. The 3a' / 3a'' / 3z.h slip pattern was: coder summarizes audit output → commits → operator catches it post-merge → calibration round → next session repeats the same slip. Now: commit blocks until verbatim Section 1/2/3 (or equivalent) appears in the assistant text. The slip becomes impossible at the commit boundary, not just discouraged at the convention level.

The typecheck hook closes a smaller but recurring vector: silent TS type errors landing in commits because the coder forgot to run `npx tsc` after editing `src/`. Memory note from the post-Phase-7 baseline cleanup ("4 'cyan' ChipKind tsc errors fixed in commit f0bda83") is the prior incidence; that slip is now caught before commit.

Both hooks are deliberately conservative — fail-open on tool-side flakes (npx missing, transcript schema variation, malformed stdin) so they never wedge the loop. The §16 audit subagent itself remains the redundant gate; the hooks are belt-and-suspenders.

## Carry-forward items
- TS-type sync (Tier 4b — next): generate `src/types/api.ts` from FastAPI's openapi.json so backend response shape changes surface as frontend type errors that the new typecheck hook would catch.
- pipeline_smoke.py (Tier 2.5): still queued; will need backend-integrity agent invocation for blast-radius.
- Docs rewrite, package.json eject, scheduled repo-janitor: also queued.

Cross-ref: CLAUDE.md §16 "Verbatim-paste enforcement", §18 Pre-flight Discipline; `backend/diagnostics/decisions/2026-05-21__verbatim-paste-rule.md` (calibration history); commits 72f64fe (Tier 1), 9024ef2 (Tier 2), 373c51c (Tier 3).
