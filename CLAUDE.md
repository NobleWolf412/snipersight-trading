# SniperSight — Claude Operating Instructions

This file is the constitution: non-negotiables + how we work + where the detail lives.
Reference detail is NOT duplicated here — pull it on demand:

- **How it's actually built** (architecture, pipeline, methodology) → the **code**, via Serena
  (`read_memory` first, then `find_symbol` / `get_symbols_overview`). The code is the only
  source of truth that can't go stale.
- **File / module map** → generate live: `tree -L 3 backend src`, or Serena's overview. Do not
  trust a hand-written tree.
- **Relationship / orientation map** (what connects to what, where a symbol lives, cross-module
  bridges, blast radius) → graphify (`graphify-out/`). A derived index — fast to orient, but
  **can go stale**. Use it to find the right code; confirm in the code via Serena. Detail: §GRAPHIFY.
- **Contract shapes** (API / telemetry / pipeline / DB) → `backend/diagnostics/contracts/`
- Full 14-point audit rubric → `.claude/AUDIT_RUBRIC.md`
- Full task-router table → `.claude/ROUTER.md`
- Calibration history & past decisions → `backend/diagnostics/decisions/`
- `ARCHITECTURE.md` / `PROJECT_STRUCTURE.md` are **historical origin-story only — partially stale.**
  Useful for *why* it was built this way, NOT for what exists now. Cite the code when in doubt.

If you need structural detail that isn't below, read the code via Serena — don't guess, don't
re-derive, and don't trust the stale prose docs.

---

## IDENTITY
Trading intelligence on Smart Money Concepts. Confluence over conviction, precision over
volume, truth over narrative. No fluff logic. Every signal must be defensible.

## STACK
- Backend: Python / FastAPI, port 8000, uvicorn
- Frontend: React, port 5000
- Startup: `C:\start-sniper.bat` · Repo: NobleWolf412/snipersight-trading
- Pipeline is one `SniperContext` object through staged orchestration (`engine/orchestrator.py`,
  entry = `scan`). Extend the pattern, don't fight it. Full stage list -> read the orchestrator
  via Serena (`get_symbols_overview engine/orchestrator.py`); don't rely on the stale arch doc.

## SCANNER MODES (only these four — never reintroduce `recon` or `ghost`)
| Mode | Profile | Min Score | Planning TF |
|------|---------|-----------|-------------|
| OVERWATCH | `macro_surveillance` | 72.0 | 4h |
| STRIKE | `intraday_aggressive` | 68.0 | 15m |
| SURGICAL | `precision` | 70.0 | 15m |
| STEALTH | `stealth_balanced` | 70.0 | 1h |

Modes are configs into one engine, not separate processes (`scanner_modes.py`).

---

## STANDING FIXES — DO NOT REGRESS
These are tuned/earned. Breaking one = no commit, period. Treated as a hard gate, not a rubric item.
- Regime detector uses **percentage-based ATR**, not absolute
- **BOS ordering** fix preserved
- **Bull/bear signal symmetry** in scoring — both paths exercised in every relevant test
- **Real dominance data** — never mocked
- **Conflict density is mode-aware**: 5 for overwatch/macro, 3 elsewhere
- **RSI fade thresholds: 70/30**
- Pre-scoring gate failure skips scoring entirely; soft penalties cannot compensate for a failed gate

## HARD BOUNDARIES
- **No live-trading code path touched without explicit approval / documented design entry**
- Bot production mode is **STEALTH**. Bot mode source is `botConfig.sniperMode`, NEVER
  `ScannerContext.selectedMode`. The scanner mode picker is for strategy inspection only and
  must not write to bot state.
- Do not modify `min_confluence_score` or pre-scoring gate thresholds without documented
  baseline data + reasoning (tuned from session win-rate)
- Never suppress an exception or rejection log to make output cleaner — that destroys diagnosability
- No mock data where real data was integrated. No silent reformats. No scope creep on edits.
  No "improvements" to working logic unless requested.

---

## THE LOOP — OPTIMIZE FOR OBSERVABILITY
Work feeds this loop, never blocks it:
idea -> change -> run with logs -> run diagnostic -> paste output -> diagnose -> fix -> repeat.

The single biggest blocker to live capital is **bugs that don't surface until you look** —
silent scoring asymmetries, regime mislabeling, execution edge cases, stale data. Code that's
correct but invisible is barely better than code that's wrong. Therefore:
- Every non-trivial change produces inspectable output (logs, telemetry, or a one-shot script)
- When fixing a bug, the **diagnostic that proves it's gone (and catches its return) lands in the
  same diff** — `backend/diagnostics/` or `*_diagnostic.py` (match existing conventions)
- Prefer **loud failures** (assertions, explicit rejections with reason codes) over silent skips
- Add telemetry (`backend/bot/telemetry/`) for any decision point that can fail silently
- Output format: short summary first, structured detail second, raw data last

## FUNDAMENTALS FIRST — DIAGNOSE TO ROOT, DON'T BANDAID
Accuracy of fundamentals beats speed of patching. A fix on a symptom while the cause keeps
producing it is a wet bandaid — it falls off. Before concluding or coding:
- **Verify the fundamentals before reasoning on top of them.** Confirm the data's scale/units,
  the threshold's calibration, and the *actual live code path* — never reason from assumed values.
  A "sophisticated" system can be inert: e.g. a 9-state engine that emits ONE state because a
  threshold went stale vs the real data, while an always-on default silently applies its bias.
- **Find the ROOT before patching.** Trace upstream (what produces this?) and downstream (what
  consumes it?) — map the full pipeline, not the local view. Ask: "if I fix this, does the cause
  still generate it?" If yes, you're bandaging a symptom — find the cause (e.g. cap concentration
  vs. fix the overlay that forces the concentration).
- **Understand the scope of the workflow before concluding.** Always-on defaults, shared
  paper/live paths, blast radius, what's a toggle vs hardcoded — know them before calling
  something done or broken.
- **Use the whole toolshed deliberately.** Measure-before-build (diagnostics), Plan / adversarial /
  symmetry agents, the ledger + decisions log. A conclusion reached with the wrong tool, or half
  the tools, is how wet bandaids get shipped. Right tool, full picture, then act.

## TRIAGE ORDER (where to focus when something's wrong)
Top-down. Do not start a lower item while a higher one is open.
1. **BROKEN** — wrong output, data loss, money at risk (execution, orders, persistence, risk guards)
2. **RISKY** — silent failures, missing guards, unsafe defaults, unhandled None
3. **CORRECTNESS** — scanner/confluence producing wrong signals
4. **FRICTION** — fragile-but-working
5. **NICE-TO-HAVE** — polish, enhancements, refactors

If I ask for a #5 while a #1/#2 is open, flag it and recommend closing the higher item first.

## OPERATING POSTURE
- Direct and precise. No hand-holding. Assume fluency in SMC, trading mechanics, Python, React.
- Surgical edits / targeted diffs — never rewrite whole files unless asked.
- Flag downstream/blast-radius risk BEFORE implementing any fix that could ripple.
- If something looks wrong, say so. Don't paper over it. When uncertain about intent or breakage
  risk, ASK before coding — a wrong guess costs a full test cycle.

---

## VERIFICATION — THE AUDIT GATE (detail: `.claude/AUDIT_RUBRIC.md`)
The coder operates autonomously; the audit subagent is the verification gate. Loop:
code -> spawn audit subagent -> fix flagged gaps -> re-audit -> commit -> push -> next.

**Spawn the auditor before:** declaring a sub-step done · any commit · any change to scoring,
regime, execution, or threshold logic.

**Verbatim-paste rule (non-negotiable):** paste the subagent's raw output into the response —
no summarizing, no "all rubrics OK", no referencing by ID. The coder cannot operate the gate AND
report its verdict; those are the same hand. Summary instead of paste = treat as unaudited, halt.
This applies to clean passes too (highest-risk slip case).

**Halt:** if 3 audit rounds fail to clear a sub-step -> stop, write history to
`backend/diagnostics/audit_halts/<utc>__<phase>__<substep>.md`, don't commit, surface on next bootstrap.

**Auto-commit:** all-clear across the rubric -> commit + push + advance, no further confirmation.

**What it can't catch:** different priors, architectural alternatives, market-domain misjudgment
(same model, fresh context). Compensate by keeping the rubric tight and expanding it whenever a
bug class slips through.

## PRE-FLIGHT GATES (fire before code lands)
- **Feature / new endpoint / new page** -> Plan agent first; plan pasted verbatim; must enumerate
  affected files, new contracts, upstream callers, downstream consumers. Code doesn't start until
  plan is on record.
- **Bug fix** -> diagnostic extension in the same diff (or cite an equivalent regression test).
- **Scoring / regime / SMC edits** (`scorer.py`, `orchestrator.py`, `regime_detector.py`,
  `regime_policies.py`, `scanner_modes.py`, `backend/strategy/smc/*`) -> **symmetry-guard agent
  auto-invoked**, output pasted alongside the audit. Standing-fixes check is a hard gate.
- **Backend integrity** (any change to `engine/`, `strategy/`, `services/`, `bot/`, `analysis/`,
  `scanner_modes.py`, a FastAPI route, a telemetry event, or a DB/JSONL schema) -> blast-radius map
  (upstream callers + downstream consumers) pasted before code lands; contract diff clean
  (`python -m backend.diagnostics.capture_contracts diff`) + `pipeline_smoke.py` passes.

## TASK ROUTER — DECLARE UPFRONT
Every non-trivial response starts with one line so I catch wrong tooling on turn one:
```
Task type: <FEATURE|MODIFY|DEBUG|TEST|REFACTOR|UI|SCORING|DOCS|SECURITY|CONFIG|AUTOMATION|API-CODE>
Skills: <one or more, or none>
Agent: <one, or none — say so explicitly>
```
Full task-type -> tooling map lives in `.claude/ROUTER.md`. I can override; you accept the override.

## DECISIONS LOG
Calibration learnings die on context reset — so they go in the repo, not in this file.
Write a `backend/diagnostics/decisions/<utc-date>__<topic>.md` entry for: any audit halt, any
calibration near-miss (wrong tool, scope creep, slipped audit, silent contract break), any threshold
tune (with baseline), any architectural shift, any "tried X, didn't work, here's why."
This file stays lean; the decisions log is the authoritative history.

## GRAPHIFY — ORIENTATION LAYER (not a source of truth)
Knowledge graph at `graphify-out/` (`graph.json` + `GRAPH_REPORT.md` + `graph.html`), mapping
relationships, god nodes, and community structure across **code AND docs**. Use it to orient
before diving — never to decide. Division of labor with Serena is the whole point:
- **graphify answers** *what connects to what / where does X live / what's the blast radius*:
  `graphify query "<q>"`, `graphify path "<A>" "<B>"`, `graphify explain "<sym>"` — a scoped
  subgraph, cheaper than grep. `GRAPH_REPORT.md` for broad architecture review only.
- **Serena stays the source of truth** for precise symbols and ALL edits (`find_symbol`,
  `get_symbols_overview`). Confirm anything graphify surfaces in the code before acting on it.
- The graph is **commit-pinned and drifts stale** — a stale graph never overrides the code (§3:
  the code is the only source of truth that can't go stale).
- **Refresh model.** `graphify update .` is fast (~32s, AST + SHA256 cache; doc nodes survive via
  cache) and safe to run standalone — fine for a post-commit hook. BUT it **re-clusters from scratch
  and re-detects scope**: it wipes hand-assigned community labels and re-widens the node set past the
  `.graphifyignore` curation (≈+1.5k nodes from `.claude/`, etc.). So treat the labeled, scoped graph
  as a **periodic artifact of the full `/graphify` pipeline**, not something `update` preserves.
  (Only run the full pipeline with subagents serialized — the AST process pool throws
  `BrokenProcessPool` under heavy concurrent subagent load, which is what bit the first build.)
  Don't trust an unrebuilt graph after a refactor — re-orient from the code.
- **PreToolUse hooks** (`.claude/settings.json`) nudge graphify-first before grep/Read. They're a
  prompt, not a gate; the Serena-first triage and §18 pre-flight still govern.
