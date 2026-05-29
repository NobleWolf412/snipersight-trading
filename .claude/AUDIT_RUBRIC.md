# SniperSight — Audit Rubric & Subagent Protocol

Referenced by CLAUDE.md → "Verification — The Audit Gate". CLAUDE.md holds the *rule*
(spawn before X, paste verbatim, halt at 3, auto-commit on clear). This file holds the
operational detail: invocation, the 14 points, output shape.

Calibration war-stories do NOT live here — they go in `backend/diagnostics/decisions/`.
This file is the rubric, not the history.

---

## Invocation rules
- Use the Task tool with `subagent_type="general-purpose"`.
- Pass: this rubric + the sub-step claims + relevant diffs (file:line refs minimum, full diff preferred).
- For harness-tracked files (`~/.claude/plans/*`, etc.), paste actual lines verbatim — git artifacts unavailable.
- Paste subagent output verbatim into the response. No summarization.
- Address every flagged gap before declaring complete.
- Never skip the audit because "the change is small" — small changes are exactly where silent regressions land.

## Verbatim-paste enforcement
Subagent output without verbatim paste does not count as a triggered audit. If you summarize,
paraphrase, or reference output by ID without pasting the raw text, treat the change as
**unaudited and halt**. The coder cannot operate the gate AND report its verdict — same hand.
This fires on clean passes too: "All N rubrics ✅, no open items" is a coder-authored summary,
NOT the subagent's block. The rule applies regardless of outcome. Clean passes are the
highest-risk slip case because no flagged item forces engagement with the output.

## The 14-point rubric (subagent must verify all)
1. **Six-concern table per change:** collision-free keys, concurrency, silent-failure, retrieval, diagnostic, schema/symmetry.
2. **Standing fixes not regressed** — percentage ATR, BOS ordering, bull/bear symmetry, real dominance data, mode-aware conflict density (5 overwatch/macro, 3 elsewhere), 70/30 RSI, four scanner modes only.
3. **Mass conservation** wherever counts split across categories — runtime assertion in the function body, not just an external test.
4. **Negative tests** proving the detector does NOT fire on noise, paired with every positive test.
5. **Threshold discipline** — relative metrics (vs prior-N median/mode) over absolute numbers; baselines documented before tuning.
6. **Output format paste-friendly** — short summary first, structured detail second, raw data last.
7. **Try/finally** for any code that can fail silently mid-flow.
8. **Prior-round asks not silently dropped** — most common regression in agent loops; flag by ask number.
9. **Scope creep** — new endpoints, files, env vars, or fields not in the design plan flagged for explicit confirmation.
10. **Diff visibility** — every claimed change has file:line refs minimum, full diff preferred; harness files require verbatim line-range paste.
11. **Hard boundaries enforced** — no live-trading path without documented design entry; no `min_confluence_score` / pre-scoring threshold change without baseline + reasoning; no mock-for-real swap; no exception/rejection log suppression; no destructive git (force push, history rewrite, shared-branch deletion).
12. **Symmetry assertions** — bull and bear paths exercised in every relevant test; direction-aware code carries explicit `__long`/`__short` test pairs or a documented "direction-agnostic" rationale.
13. **Blast-radius enumeration** — for any change touching `backend/engine/`, `backend/strategy/`, `backend/services/`, `backend/bot/`, `backend/analysis/`, `scanner_modes.py`, a FastAPI route, a telemetry event, or a DB/JSONL schema: upstream callers + downstream consumers listed explicitly and pasted in output. "No impact" is acceptable only if the auditor searched and confirmed.
14. **Contract diff clean** — `backend/diagnostics/contracts/*.json` snapshots match baseline OR every delta has a documented downstream-update line. `python -m backend.diagnostics.capture_contracts diff` exits clean (or deltas justified). For pipeline changes, `pipeline_smoke.py` passes against `golden_scan.json`.

## Subagent output shape
- Status table: claim → ✅ verified / 🟡 partial / ❌ unverified
- Numbered open items with explicit asks routed to the coder
- Single routing line at end: "auditor track unblocks when [condition]"

## Auto-commit authorization
All-✅ across the 14 points → coder commits + pushes to `origin/main` + advances, no further confirmation.

## Iteration cap & halt
3 audit rounds on the same sub-step fail to clear →
- Halt the loop
- Write full audit history to `backend/diagnostics/audit_halts/<utc-timestamp>__<phase>__<sub-step>.md` (create dir if absent)
- Do not commit. Do not advance.
- Surface the halt path in the next session bootstrap.

## What the audit CANNOT catch
Same model, fresh context. Catches dropped asks, missing assertions, scope drift, rubric violations.
Does NOT catch adversarial-review issues — different priors, architectural alternatives, market-domain
misjudgments. Those can pass and ship. The autonomous loop accepts that risk for unattended operation.
Compensate: keep the rubric tight, expand it whenever a bug class slips through, treat every halt-log
entry as feedback for the next rubric revision.
