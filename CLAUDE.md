# SniperSight — Claude Operating Instructions

## 1. Project Identity
SniperSight is a trading intelligence system built on Smart Money Concepts. Core philosophy: confluence over conviction, precision over volume, truth over narrative. No fluff logic. Every signal must be defensible.

## 2. Stack & Environment
- Backend: Python / FastAPI, port 8000, uvicorn
- Frontend: React, port 5000
- Remote: SSH via Tailscale (100.83.37.108), user `macca`, machine `noblewolf`, auth via `sshuser`
- Startup: `C:\start-sniper.bat`
- Repo: NobleWolf412/snipersight-trading

## 3. Core Methodology (SMC)
Order Blocks, Fair Value Gaps, BOS, CHoCH, Liquidity Sweeps, Wyckoff cycle logic. Confluence scoring drives signal quality. WCL failure logic feeds active short bias. Bullish/bearish signals must be treated symmetrically.

## 4. Scanner Modes — All Filters On One Engine
Modes are configurations, not separate processes. Each mode passes a `profile` string into the same orchestrator pipeline. Defined in `backend/shared/config/scanner_modes.py`.

| Mode | Profile | Min Score | Critical TFs | Planning TF | Timeframes |
|------|---------|-----------|--------------|-------------|------------|
| OVERWATCH | `macro_surveillance` | 72.0 | 1w, 1d | 4h | 1w, 1d, 4h, 1h, 15m, 5m |
| STRIKE | `intraday_aggressive` | 68.0 | 15m | 15m | 4h, 1h, 15m, 5m |
| SURGICAL | `precision` | 70.0 | 15m | 15m | 4h, 1h, 15m, 5m |
| STEALTH | `stealth_balanced` | 70.0 | 4h, 1h | 1h | 1d, 4h, 1h, 15m, 5m |

Legacy `recon` and `ghost` modes were removed. Only the four above exist.

## 5. Signal Pipeline — Single Context Object
Pipeline is built around `SniperContext` (`backend/engine/context.py`). One dataclass passes through every stage and gets progressively populated. Stage order in `engine/orchestrator.py`:

1. Data ingestion → `multi_tf_data`
2. Indicators → `multi_tf_indicators`
3. SMC detection → `smc_snapshot`
4. Macro context → `macro_context`
5. Confluence scoring → `confluence_breakdown`
6. Trade planning → `plan`
7. Risk validation → `risk_plan`

Don't fight the pattern — extend it.

## 6. Confluence Scoring
Weighted sum with synergy bonuses, conflict penalties, and pre-scoring gates that hard-fail before scoring runs. Mode-aware MACD weights. HTF composite collapses correlated HTF inputs into one score. Per-mode minimum thresholds (table above). Frontend can override upward but not downward.

Pre-scoring gates (`run_pre_scoring_gates`): structural anchor, BTC impulse, regime, conflict density. Gate failure skips scoring entirely. Soft penalties cannot compensate for a failed gate.

## 7. Timeframe Hierarchy — Automated Top-Down
Driven by `RELATIVITY_MAP` in `scanner_modes.py`:
- Scalp: 1m exec / 5m plan / 15m context
- Intraday: 5m exec / 15m plan / 1h context
- Swing: 1h exec / 4h plan / 1d context

Each mode declares `critical_timeframes` and `primary_planning_timeframe`. HTF alignment is enforced inside the scorer.

## 8. Invalidation & Regime Gating — Both Automated
Invalidation lives in `position_manager._monitor_position`. Auto-exits: `stop_loss`, `target`, `trailing_stop`, `max_hours_open`, `stagnation` (with strikes counter), `orphan_price_feed_failure`.

Regime gating is enforced, not advisory. Each mode has a `RegimePolicy` (`backend/analysis/regime_policies.py`) with `min_regime_score`, `allow_in_risk_off`, position-size adjustments, and confluence adjustments per regime label.

## 9. Key Files
- `backend/strategy/confluence/scorer.py` — confluence scoring engine + pre-scoring gates
- `backend/engine/orchestrator.py` — pipeline controller (`scan` is the entry point)
- `backend/engine/context.py` — SniperContext dataclass
- `backend/bot/paper_trading_service.py` — paper trading orchestration
- `backend/bot/executor/paper_executor.py` — trade execution
- `backend/bot/executor/position_manager.py` — open position tracking + invalidation
- `backend/analysis/regime_detector.py` — regime classification (percentage ATR only)
- `backend/analysis/regime_policies.py` — per-mode regime gating
- `backend/shared/config/scanner_modes.py` — mode definitions + RELATIVITY_MAP
- `backend/services/{confluence,smc,indicator,scanner}_service.py` — domain service layer

## 10. Standing Fixes — Do Not Regress
- Regime detector uses percentage-based ATR, not absolute
- BOS ordering fix preserved
- Bullish/bearish signal symmetry in scoring
- Real dominance data integrated (never mocked)
- Conflict density threshold is mode-aware (5 for overwatch/macro, 3 elsewhere)
- RSI fade thresholds standardized to 70/30
- Only four scanner modes exist — do not reintroduce `recon` or `ghost`

## 11. Top Priority — Hidden Bug Surfacing
The single biggest blocker to live capital is bugs that don't show up until you go looking for them: silent scoring asymmetries, regime mislabeling, execution edge cases, stale data slipping through. Optimize every change for *observability*. Code that's correct but invisible is barely better than code that's wrong.

## 12. Workflow Integration
Loop: idea → prompt AI → AI executes → run app with logs → stop bot → run analysis script → paste output to AI → diagnose → fix → repeat.

Operate to feed that loop, not block it:
- Every non-trivial change should produce inspectable output (logs, telemetry events, or a one-shot diagnostic script)
- When fixing a bug, also produce or extend a diagnostic script that proves the bug is gone — and would catch its return
- Diagnostic scripts go in `backend/diagnostics/` or top-level `*_diagnostic.py` (matching existing conventions like `confluence_diagnostic.py`, `fetch_diagnostics.py`)
- Output formats should be paste-friendly: short summary first, structured detail second, raw data last
- When you suspect a bug but can't prove it, write the script that would prove it before you change code
- Add telemetry events (`backend/bot/telemetry/`) for any decision point that could fail silently
- Prefer loud failures (assertions, explicit rejections logged with reason codes) over silent skips

## 13. How To Operate
- Direct and precise. No hand-holding.
- Targeted diffs or surgical edits — never rewrite whole files unless asked
- Assume fluency in SMC, trading mechanics, Python, React
- Flag downstream risk before implementing any fix that could ripple
- If something looks wrong, say so. Don't paper over it.
- When uncertain about intent or breakage risk, ask before coding

## 14. Verification Discipline
- After any change to scoring, regime, or execution logic — show what was tested or what should be tested
- Never claim a fix works without validating against the symmetry rule and standing fixes
- Surface assumptions that weren't explicit in the request
- For any logic change, suggest the diagnostic script or log query that would catch a regression
- Reference existing reports (`CONFLUENCE_REJECTION_REPORT.md`, `SNIPERSIGHT_DEBUG_REPORT.md`, `FIXES_APPLIED.md`) when relevant

## 15. Hard Boundaries
- No live trading code paths get touched without explicit approval
- No silent reformats, no scope creep on edits
- No mock data swapped in where real data was integrated
- No "improvements" to working logic unless requested
- Do not modify `min_confluence_score` or pre-scoring gate thresholds without a documented reason — these were tuned from session win-rate data
- Never suppress an exception or rejection log to make output cleaner — that destroys diagnosability
- Bot production mode is STEALTH. Bot mode source is botConfig.sniperMode, never ScannerContext.selectedMode. Scanner mode picker is for strategy inspection only and must not write to bot state.

## 16. Audit Discipline — Autonomous Subagent Verification

### Operating mode
The coder operates autonomously. The audit subagent is the sole verification gate. No operator approval is required to commit, push, or advance to the next sub-step. The loop runs: code → spawn audit subagent → fix flagged gaps → re-audit → commit → push → next sub-step.

### Trigger conditions
Spawn the audit subagent before any of the following:
- Declaring a sub-step complete
- Committing a phase or milestone closure
- Any change to scoring, regime, execution, or pre-scoring gate logic
- Setting or modifying any threshold value

### Invocation rules
- Use the Task tool with `subagent_type="general-purpose"`
- Pass the rubric below + sub-step claims + relevant diffs (file:line refs minimum, full diff preferred)
- For harness-tracked files (`~/.claude/plans/*`, etc.), paste actual lines verbatim — git artifacts unavailable
- Paste subagent output verbatim into the response, no summarization
- Address every flagged gap before declaring complete
- Never skip the audit step because "the change is small" — small changes are exactly where silent regressions land

### Verbatim-paste enforcement
Subagent output without verbatim paste does not count as a triggered audit. If the coder summarizes, paraphrases, or references the subagent output by ID without pasting the raw text in the response, treat the change as unaudited and halt. The audit step is the gate-not-checkpoint principle from §16; pasting the gate's actual output is non-negotiable. Coders cannot operate the gate AND report the gate's verdict — those are the same hand. Operator-facing trust depends on the raw output being inspectable.

Calibrated on the 3a'/3a'' Phase-3 follow-up round: three consecutive turns shipped with the coder describing the subagent's findings instead of pasting them. Each round's gaps got addressed but the gate's actual output was invisible to the operator. The pattern is the failure mode this subsection is meant to prevent. If you find yourself writing "the auditor flagged…" or "open items #1/#2/…" in a response without the literal Section 1/Section 2/Section 3 block above it, stop and paste.

Clean-pass calibration: the same paste applies when the subagent returns all ✅ with no open items. Phrases like "All 12 rubrics ✅, no open items" or "audit returned clean — committing" are coder-authored summaries, not the subagent's Section 1/2/3 block. The verbatim-paste rule fires regardless of audit outcome. Clean passes are the highest-risk slip case because there's no flagged item forcing structural engagement with the subagent's output. Calibrated on 3z.h where commit 54d0923 shipped with the literal phrase "All 12 rubrics ✅, no open items" replacing the auditor's actual table; the operator caught it and halted, treating the change as unaudited per the rule above. The fix shape on a clean pass is identical to a flagged pass — paste the Section 1/2/3 block verbatim before any commit framing.

### Rubric (subagent must verify all 14)
1. Six-concern table per change: collision-free keys, concurrency, silent-failure, retrieval, diagnostic, schema/symmetry
2. Standing fixes (§10) not regressed — percentage ATR, BOS ordering, bull/bear symmetry, real dominance data, mode-aware conflict density (5 for overwatch/macro, 3 elsewhere), 70/30 RSI, four scanner modes only
3. Mass conservation wherever counts split across categories — runtime assertion in the function body, not just an external test
4. Negative tests proving the detector does NOT fire on noise, paired with every positive test that proves it fires on trigger
5. Threshold discipline — relative metrics (vs prior-N median/mode) over absolute numbers; baselines documented before tuning
6. Output format §12 paste-friendly: short summary first, structured detail second, raw data last
7. Try/finally for any code that can fail silently mid-flow
8. Prior-round asks not silently dropped — most common regression in agent loops, flag by ask number
9. Scope creep — new endpoints, files, env vars, or fields not in design plan flagged for explicit confirmation
10. Diff visibility — every claimed change accompanied by file:line refs minimum, full diff preferred; harness files require verbatim line-range paste
11. §15 hard boundaries enforced — no live trading code paths touched without a documented design entry, no `min_confluence_score` or pre-scoring gate threshold modifications without baseline data + reasoning, no mock data swapped for real data, no exception/rejection log suppression, no destructive git operations (force push, history rewrite, branch deletion on shared refs)
12. Symmetry assertions — bull and bear paths exercised in every relevant test; any direction-aware code carries explicit `__long`/`__short` test pairs or a documented "direction-agnostic" rationale
13. **Blast-radius enumeration** (§20) — for any change touching `backend/engine/`, `backend/strategy/`, `backend/services/`, `backend/bot/`, `backend/analysis/`, `backend/shared/config/scanner_modes.py`, a FastAPI route, a telemetry event, or a DB/JSONL schema: upstream callers + downstream consumers listed explicitly. Pasted in audit output, not just claimed. "No upstream/downstream impact" is an acceptable verdict only if the auditor has searched and confirmed.
14. **Contract diff clean** (§20) — `backend/diagnostics/contracts/*.json` snapshots either match pre-change baseline OR every delta has a documented downstream-update line. `python -m backend.diagnostics.capture_contracts diff` exits clean (or its deltas are explicitly justified). For pipeline changes, `pipeline_smoke.py` passes against `golden_scan.json`.

### Subagent output shape
- Status table: claim → ✅ verified / 🟡 partial / ❌ unverified
- Numbered open items with explicit asks routed to the coder
- Single routing line at end: "auditor track unblocks when [condition]"

### Auto-commit authorization
When the audit subagent returns all ✅ verified across the 14-point rubric:
- Coder commits the change without further confirmation
- Coder pushes to `origin/main` without further confirmation
- Coder advances to the next sub-step

### Iteration cap and halt
If 3 audit rounds on the same sub-step fail to clear:
- Halt the loop
- Write the full audit history to `backend/diagnostics/audit_halts/<utc-timestamp>__<phase>__<sub-step>.md` (one file per halt; create the directory if absent)
- Do not commit
- Do not advance
- Surface the halt path in the next session bootstrap so the operator finds it on resume

### What the audit cannot catch
The audit subagent runs the same model with a fresh context. It catches dropped asks, missing assertions, scope drift, and rubric violations. It does NOT catch adversarial-review issues — different priors, architectural alternatives, market-domain misjudgments. These can pass the audit and ship anyway. The autonomous loop accepts that risk in exchange for unattended operation. To compensate: keep the rubric tight, expand it whenever a class of bug slips through, and treat every halt-log entry as feedback signal for the next rubric revision.

## 17. Task Router — Declare Skill + Agent Upfront

Every work-doing response (non-conversational) starts with a one-line declaration:

```
Task type: <FEATURE | MODIFY | DEBUG | TEST | REFACTOR | UI | SCORING | DOCS | SECURITY | CONFIG | AUTOMATION | API-CODE>
Skills: </one or more>
Agent: <one or none>
```

If wrong tools are picked, operator catches it in the first turn instead of after work lands.

### Task type → tools

| Task type | Primary skills | Agents | Verification gate |
|---|---|---|---|
| **FEATURE** (add new) | `/init` (context), `/impeccable` or `/ui-ux-pro-max` (if UI), `/verify` (post) | **Plan** → general-purpose → §16 audit | `/verify` + `/security-review` if auth/data |
| **MODIFY** (existing) | `/simplify` (post-change), `/verify` | **Explore** (locate) → §16 audit | `/verify` |
| **DEBUG** (post-run) | `/autopsy` (entry) → `/scan-autopsy` / `/trade-autopsy` / `/confluence-trace` / `/rejection-survey` | **rejection-forensics** (single-signal kill chain) | diagnostic script per §12 |
| **TEST** | `/verify`, `/run` | general-purpose | snapshot framework for UI |
| **REFACTOR** | `/simplify`, **repo-janitor** | **symmetry-guard** (auto on scoring/regime files) | §16 |
| **UI** | `/impeccable`, `/ui-ux-pro-max`, `/verify` | **Plan** (IA) → general-purpose | snapshot framework + `/verify` |
| **SCORING/WEIGHTS** | `/tune-confluence-weights` | **symmetry-guard** (mandatory) | built-in skill checks + §16 |
| **DOCS** | `/init`, `/review` | — | — |
| **SECURITY** | `/security-review` | — | manual sign-off |
| **CONFIG / HOOKS** | `/update-config`, `/fewer-permission-prompts`, `/keybindings-help` | — | — |
| **AUTOMATION** | `/loop`, `/schedule` | — | — |
| **API-CODE** (Claude/Anthropic SDK) | `/claude-api` | — | — |

Rules:
- The router declaration line is non-negotiable for any non-trivial work. Trivial responses (typo, single-line tweak, conversational reply) may skip.
- Multiple skills allowed; declare them.
- "Agent: none" is valid — say so explicitly.
- Operator can override the declared choice; the coder accepts the override.

## 18. Pre-flight Discipline

For three classes of work, additional gates fire **before** code lands:

### Feature / new-endpoint / new-page work
- **Plan agent** invocation required. Plan agent output pasted verbatim in the response (same rule as §16 audit output). No exceptions.
- Plan must enumerate: affected files, new contracts (API/telemetry/DB), upstream callers, downstream consumers.
- Operator may redirect the plan. Code does not start until plan is on record.

### Bug-fix work
- A diagnostic script extension lands in the **same diff** that proves the bug gone. New file in `backend/diagnostics/` or extension to an existing `*_diagnostic.py`.
- Audit Rubric 13 is restated for bug-fix scope: the auditor verifies the diagnostic exists and exercises the reproduction case, not just the fix.
- Acceptable exception: if a regression test in `backend/tests/` covers the same ground with the same loud-failure guarantees, cite it instead.

### Scoring / regime / SMC file edits
- **symmetry-guard agent** auto-invoked. Trigger files: `scorer.py`, `orchestrator.py`, `regime_detector.py`, `regime_policies.py`, `scanner_modes.py`, and any file under `backend/strategy/smc/`.
- Output pasted verbatim alongside the §16 audit, not in place of it.
- §10 standing-fixes check is treated as a hard gate, not a rubric item — a regression here means no commit, period.

## 19. Decisions Log

### Purpose
Calibration learnings die when memory is reset. The decisions log keeps them in the repo.

### Location
`backend/diagnostics/decisions/<utc-yyyy-mm-dd>__<topic-kebab>.md`

One file per decision. Frontmatter optional. Filename is human-readable + sortable.

### When to write
- Any §16 audit halt (already covered by `audit_halts/`; cross-link in the decisions entry)
- Any calibration learning from a near-miss — wrong tool chosen, scope creep landed, audit slipped, contract broke silently
- Any threshold tune (with the baseline data that motivated it — §15 hard boundary)
- Any architectural shift that future-me would need to know about
- Any "we tried X, it didn't work, here's why" entry — saves the next attempt

### Format
- **Headline:** one line — what was decided / learned
- **Context:** what triggered it (commit hash, sub-step, symptom)
- **Resolution:** what changed (file refs, line refs)
- **Why it matters next time:** the part that survives context loss

MEMORY.md keeps only one-line pointers — *"see decisions/2026-05-21__verbatim-paste-rule.md"*. Decisions log is authoritative; memory is the index.

## 20. Backend Integrity Discipline

### Trigger
Any change to:
- `backend/engine/` (orchestrator, context)
- `backend/strategy/` (scorer, planner, risk)
- `backend/services/` (confluence/smc/indicator/scanner service layer)
- `backend/bot/` (paper trader, executor, position manager, telemetry)
- `backend/analysis/` (regime detector, policies, macro context)
- `backend/shared/config/scanner_modes.py`
- Any FastAPI route (`@app.get`, `@app.post`, `@router.get`, etc.)
- Any telemetry event emission (`backend/bot/telemetry/events.py`)
- Any DB table or JSONL schema

### Pre-flight: blast-radius map
Required before code lands, pasted in the response:

- **Upstream callers** — who imports / calls the function I'm touching
- **Downstream consumers** — what stages / services / frontend modules read the output
- **Telemetry surface** — what event names / payload keys are affected
- **API surface** — what endpoint response shapes change
- **DB / JSONL surface** — what columns / keys change

"No upstream/downstream impact" is a verdict, not a default — back it with grep evidence.

### Contract snapshots
Frozen baselines live in `backend/diagnostics/contracts/`:

- `api_contracts.json` — `/api/*` route inventory: path, method, response model name (when declared)
- `telemetry_contracts.json` — `EventType` enum members + factory function payload keys
- `pipeline_contracts.json` — `SniperContext` field set + stage outputs
- `db_contracts.json` — SQLite table schemas + JSONL canonical keys
- `golden_scan.json` — output of `pipeline_smoke.py` on a fixed market-data fixture

Driver script: `backend/diagnostics/capture_contracts.py`.

Two modes:
- `python -m backend.diagnostics.capture_contracts capture` — re-baseline (intentional contract change; commit body must document why)
- `python -m backend.diagnostics.capture_contracts diff` — compare current code against baseline (default; non-zero exit on drift). This is what the §16 audit runs.

### Pipeline smoke
`backend/diagnostics/pipeline_smoke.py`:
- Loads a frozen market snapshot (CSV/JSON fixture under `backend/tests/fixtures/`)
- Runs `orchestrator.scan(profile='stealth_balanced')` end-to-end
- Asserts every stage entered, every expected field populated, no silent skips
- Compares output against `golden_scan.json`
- Runs on every backend change before commit; failure blocks commit

### Frontend↔backend contract validation
- Backend response shapes feed `src/types/api.ts` (hand-maintained or `/contract-check ts-emit` if/when that skill lands).
- Pre-commit check: TS types match backend response shapes. Closes the "HUD compiles fine but reads undefined" silent-break vector.

### Audit integration
Rubrics 13 + 14 (see §16) verify the blast-radius map was pasted and the contract diff is clean. The audit subagent is expected to run `capture_contracts.py diff` and report its output.
