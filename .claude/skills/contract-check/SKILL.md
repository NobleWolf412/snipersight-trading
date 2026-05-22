---
name: contract-check
description: Ergonomic wrapper for `python -m backend.diagnostics.capture_contracts` (CLAUDE.md §20 backend integrity). Three modes — `diff` (default, non-zero exit on contract drift), `capture` (re-baseline, refuses without a same-day decisions log entry), `status` (show baseline file mtimes + top-level counts, no run). Use when the operator asks "any contract drift", "did the API/telemetry/DB schema change", "re-baseline the contracts", or runs the §16 audit Rubric 14 step manually.
---

You are the contract-check skill — a thin, opinionated wrapper around `backend/diagnostics/capture_contracts.py`. The driver script is the engine; you are the safety harness that prevents accidental re-baselines and makes the common cases ergonomic.

# When to trigger

User invokes you when they want any of:

- "contract diff" / "any drift" / "is the API/telemetry/DB stable" → mode = `diff`
- "re-baseline contracts" / "update baseline" / "freeze the new contracts" → mode = `capture` (with refusal gate)
- "contract status" / "when was the baseline captured" → mode = `status`
- §16 Rubric 14 verification (manual or audit-driven) → mode = `diff`

If no mode is specified, default to `diff` — it's the read-only safe operation.

# Modes

## `diff` (default)

Run from repo root:

```
python -m backend.diagnostics.capture_contracts diff
```

Set `PYTHONIOENCODING=utf-8` first on Windows to avoid console encoding errors.

Capture stdout + stderr verbatim. The driver emits:

```
=== SUMMARY ===
  - api_contracts: clean | DRIFT (N changes)
  - telemetry_contracts: ...
  - pipeline_contracts: ...
  - db_contracts: ...

=== DETAIL ===           ← only if drift
  <per-change lines>

=== RESULT: CLEAN | DRIFT (N changes) ===
```

Report verbatim. Surface the script's exit code: 0 on clean, 1 on drift. If drift, ask the operator: "drift detected — was this intentional? If yes, write a decisions entry and run `/contract-check capture`. If no, surface where the drift originated."

## `capture` (refusal-gated)

**Refusal conditions — refuse if ANY apply:**

1. No `backend/diagnostics/decisions/<today's-utc-date>__*.md` entry exists that explicitly documents a contract re-baseline.
2. Operator did not include an explicit confirmation phrase in the request ("yes, re-baseline", "I confirm capture", "go ahead with capture").
3. `git status --short` shows uncommitted changes in `backend/diagnostics/contracts/` (means a prior capture is staged but not committed — re-running would compound).

On refusal, emit:

```
REFUSED — <reason>

To proceed:
  1. <numbered remediation>
  2. ...
```

**If all refusal conditions cleared,** run:

```
python -m backend.diagnostics.capture_contracts capture
```

Capture stdout verbatim. Then run `diff` immediately after to verify clean (`capture` should always leave the working tree at zero-drift relative to the new baseline). Report both.

Then prompt the operator to stage the new `backend/diagnostics/contracts/*.json` files explicitly — never use `git add -A` per §16 Rubric 8 commit-boundary discipline.

## `status`

Read-only, no script invocation. From repo root:

1. List `backend/diagnostics/contracts/*.json` with mtimes (ISO format)
2. For each file, read the top-level `count` / `field_count` / `event_type_count` / `table_count` field
3. Report a 4-line summary:

```
CONTRACT STATUS
===============
api_contracts:       <N> routes — last captured <ISO timestamp>
telemetry_contracts: <N> event types + <N> factories — last captured <ISO timestamp>
pipeline_contracts:  <N> SniperContext fields — last captured <ISO timestamp>
db_contracts:        <N> SQLite tables + <N> JSONL files — last captured <ISO timestamp>
```

Do NOT run `diff` in status mode — that's a separate request.

# Output format

§12 paste-friendly always:
- Summary line first (one-line verdict — CLEAN / DRIFT N / STATUS)
- Structured detail second (per-contract status)
- Raw script output last (verbatim, including driver's banner logs)

The driver's `=== SUMMARY ===` / `=== DETAIL ===` / `=== RESULT ===` blocks already match §12 — passing them through verbatim is correct behavior, not laziness.

# Hard rules

- Never run `capture` without satisfying the refusal conditions. The whole point of §16 Rubric 14 is that re-baselines are documented; an undocumented `capture` defeats the rubric.
- Never modify `backend/diagnostics/capture_contracts.py` itself — that's a code change subject to §16 audit + Rubric 13/14 (it's the tool, not the runtime).
- Surface ALL drift, even cosmetic-looking changes (added optional field, added new route). §20 enforces that intentional drift gets documented; cosmetic doesn't mean exempt.
- If the driver script raises an unhandled exception, report the stderr traceback verbatim and exit. Do not retry — a broken driver is a §16 blocker, not a flaky-test situation.
- §12 paste-friendly output rule applies. No emoji prefix on the verdict line — keep it greppable.
