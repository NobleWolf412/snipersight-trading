# 2026-05-21 — Workflow enhancement Tier 2: adversarial-review + backend-integrity agents, /triage + /contract-check skills, symmetry-guard PostToolUse hook

## Headline
Tier 2 of the workflow enhancement landed: two new subagents (adversarial-review, backend-integrity), two new skills (/triage, /contract-check), one PostToolUse hook (symmetry-guard reminder) wired via new repo-tracked .claude/settings.json. All six artifacts live in .claude/ — no backend code touched.

## Context
Tier 1 (commit 72f64fe) added CLAUDE.md §17-§20 + Rubrics 13/14 + capture_contracts.py + initial baselines + decisions log scaffold. Operator approved Tier 2 with "go" after the Tier 1 audit pass.

Plan agent invocation per §18 produced a tight implementation plan (file order, per-file outlines, hook testing plan, rubric applicability prep). Plan pasted verbatim in the originating conversation; execution followed.

Pain points addressed:
1. **Adversarial-review gap (§16 explicit)** — same-model audit subagent cannot catch different-prior issues. New agent has 8 enumerated stance heuristics (market-maker, HFT, regime-flip, liquidity-regime, cycle-flip, adversarial-feed, stop-hunter, same-day calibration) and refuses to verdict ACCEPT without genuinely trying alternatives.
2. **Blast-radius mapping (§20 Rubric 13) was manual** — new backend-integrity agent makes it routine. UPSTREAM/DOWNSTREAM/CONTRACT SURFACE/POTENTIAL BREAKS format mirrors the Surface Map in §20.
3. **Task routing was ad-hoc per turn** — /triage skill formalizes §17 declaration as a front-of-house gate that asks for redirect before code starts.
4. **§16 Rubric 14 ergonomics** — /contract-check skill wraps `python -m backend.diagnostics.capture_contracts` with refusal gates on `capture` (no same-day decisions entry → refuse).
5. **§18 symmetry-guard auto-invoke was honor-system** — PostToolUse hook fires a stderr reminder when Edit/Write/MultiEdit touches the §10 standing-fix surface (scorer.py, orchestrator.py, regime_*.py, scanner_modes.py, smc_*.py, smc_service.py). Non-blocking — reminder is for the coder, hook never breaks tool calls.

## Resolution

**Files created (Tier 2 commit scope):**
- `.claude/agents/adversarial-review.md` — Different-Prior Heuristics + CHALLENGE/ALTERNATIVES/MARKET-DOMAIN RISKS/VERDICT format
- `.claude/agents/backend-integrity.md` — Surface Map grep patterns + UPSTREAM/DOWNSTREAM/CONTRACT SURFACE/POTENTIAL BREAKS format
- `.claude/skills/contract-check/SKILL.md` — 3 modes (diff/capture/status); capture refuses without same-day decisions entry
- `.claude/skills/triage/SKILL.md` — §17 task-type classifier with explicit operator question gate
- `.claude/hooks/symmetry_guard_reminder.py` — Python script, cross-platform (Windows-safe path handling), non-blocking
- `.claude/settings.json` — PostToolUse hook wired with `Edit|Write|MultiEdit` matcher

**Hook activation tests (per Plan agent's Layer A + B requirements):**
- Layer A1: forward-slash watched path (`backend/strategy/confluence/scorer.py`) → fires reminder, EXIT=0 ✅
- Layer A2: forward-slash non-watched path (`backend/api_server.py`) → silent, EXIT=0 ✅
- Layer A3: JSON-escaped backslash path (`backend\engine\orchestrator.py`) → fires reminder, EXIT=0 ✅
- Layer A4: absolute Windows path with `smc/` subdir → fires reminder, EXIT=0 ✅
- Layer B1: empty stdin → silent, EXIT=0 ✅
- Layer B2: malformed JSON → silent, EXIT=0 ✅
- Layer B3: empty JSON object `{}` → silent, EXIT=0 ✅
- Layer C (live in-harness firing) deferred to next session — non-blocking by design, false-negative cost is one missed reminder per next-edit, not a regression.

**Contract diff:** `python -m backend.diagnostics.capture_contracts diff` returned `CLEAN (0 changes)` post-Tier-2. No backend code touched, so no drift expected.

**Calibration note for the §16 audit subagent on this round:** Tier 2 is entirely tooling/process layer. Rubrics 1-5, 7, 12 are N/A. Rubrics 6, 8, 9, 10, 11, 13, 14 apply.

## Why it matters next time

Tier 1 set up the policies (§17-§20 + Rubrics 13/14 + capture_contracts driver). Tier 2 makes the policies operationally cheap to follow:

- `/triage` reduces the chance of wrong skill/agent selection on the first turn
- `/contract-check diff` replaces typing `python -m backend.diagnostics.capture_contracts diff` (the friction had value as a gate; the skill keeps the gate while removing typing cost)
- `backend-integrity` agent makes Rubric 13 blast-radius mapping a one-call delegation instead of manual grepping
- `adversarial-review` agent fills the §16 "what the audit cannot catch" gap with an explicit different-prior protocol
- `symmetry_guard_reminder.py` hook removes "did I remember to invoke symmetry-guard?" from the coder's working memory on every §10-surface edit

Deferred (Tier 2.5 / Tier 3):
- `pipeline_smoke.py` + `golden_scan.json` — needs frozen OHLCV fixture decision (which symbol, which timeframe, frozen-on-what-date)
- Memory archive of completed Phase 0-7 entries — Tier 3
- snapshot framework `summary.json` parallel-worker bug fix — Tier 3
- Frontend↔backend TS-type sync — Tier 4

Cross-ref: CLAUDE.md §16/§17/§18/§19/§20; commit 72f64fe (Tier 1); `backend/diagnostics/decisions/2026-05-21__workflow-enhancement-tier1.md`.
