# conviction_class — orphan classifier wired into planner

## Headline
`classify_conviction()` at [rr_matrix.py:87-144](backend/shared/config/rr_matrix.py#L87)
was added in commit 8b9b081 (2025-11-28, "Refactor R:R validation and
enhance planner with...conviction classification for improved trade
planning and execution") but **never called from any production code
path**. Every TradePlan since November 2025 has received the dataclass
default `conviction_class = "B"` from [planner.py:162](backend/shared/models/planner.py#L162).
Wired in now at planner_service.py:684, post-TradePlan-construction.

## Context
- Surfaced by 2026-05-26 `taken_trade_forensics.py`: 67/67 closed trades
  in `trade_journal.jsonl` had `conviction_class="B"` — perfect
  stuck-value signature.
- Git archaeology confirmed: `git log -S 'conviction_class = "A"'`
  returns only test files; no production assignment exists in any
  historical commit.
- The classifier itself is well-written and tested-via-this-commit:
  band-based with A=(SMC + ideal_rr + conf≥80 + all_critical_tfs),
  B=(near-ideal RR + conf≥65 OR SMC/HYBRID with min_rr + decent conf
  OR ATR_FALLBACK with min_rr + conf≥60), C=residual. ATR_FALLBACK
  capped at B.

## Resolution
- [planner_service.py:684-703](backend/strategy/planner/planner_service.py#L684)
  — added import + post-construction wire-up. The classifier reads
  `plan.plan_type`, `plan.risk_reward_ratio`, `plan.confidence_score`,
  and `missing_critical_timeframes` (function arg) and writes to
  `plan.conviction_class`. Wrapped in try/except with WARNING log so
  any future regression in the classifier surfaces loudly rather than
  silently degrading back to the default.
- 16 new tests in `backend/tests/unit/test_classify_conviction.py`:
  - Band logic across A/B/C for SMC, ATR_FALLBACK, HYBRID plan types
  - Edge cases (extreme inputs, floor inputs, boundary cases)
  - Output Literal contract (always returns "A"/"B"/"C")
  - **Static source-grep wire-up regression catch** at
    `test_planner_service_calls_classify_conviction` and
    `test_planner_service_wire_up_is_after_tradeplan_construction` —
    if a future refactor removes the import or the call, these tests
    fail immediately (pattern carried over from
    test_stale_counter_main_process_accounting + test_breakdown_field_regression).

## Why it matters next time
- The `conviction_class` field is now actually populated with signal,
  which makes the next `taken_trade_forensics` run informative for
  the A/B/C bucketing. Pre-fix, the field was useless for partition
  analysis.
- This is the third orphan-code bug surfaced today (htf_aligned bug
  read non-existent factor names; macro_state serialized enum int;
  conviction_class never called). All three were silent in the sense
  that no exception fired — the code just returned the wrong value
  or the default value forever. The pattern: a feature was added
  along with the data plumbing for it, but the wire-up step was
  missed.
- **Audit Rubric 15 candidate (orphan-function check)**: alongside the
  multiprocessing-shared-state Rubric 15 proposed in commit ed452b9,
  this commit motivates a second rubric candidate: "Any new function
  added to a backend module must either (a) be called from production
  code in the same commit OR (b) be explicitly marked as
  test-fixture-only / public-API-for-future-callers, with a TODO
  pointing at the planned call site." Three orphan bugs in one
  diagnostic run is enough signal to invest in catching the pattern.
- **Threshold/distribution caveat**: classify_conviction's bands
  (conf≥80 for A, conf≥65 for B-near-ideal, conf≥60 for ATR_FALLBACK)
  were tuned in 2025-11 without prior production data — they're
  authored thresholds, not data-derived. Per §15 if distribution
  audits show A/B/C is wildly skewed (e.g. 99% B), the bands may
  need re-tuning against the actual confluence/RR distribution
  observed post-fix. Flag follow-up task: 50 Tier 2 trades post-deploy,
  histogram conviction distribution, compare against intuition.

## Behavioral effect at deployment
- Existing code reads `plan.conviction_class` in:
  - `bot/executor/position_manager.py:413` (PositionState init — writes to journal)
  - `bot/paper_trading_service.py:2797` + `live_trading_service.py:1853`
    (CompletedTrade conversion — writes to journal)
  - Frontend HUD (per UI mapping in `src/types/api.ts` etc.)
- No production code currently *gates* execution on conviction_class
  (no `if plan.conviction_class == "A"` branches found via grep).
  The field is currently a telemetry-only signal that flows into the
  journal and the HUD display.
- Therefore the wire-up is **purely additive observability** for now —
  no signal pass-rate / execution behavior change at this commit.
  Future work could use the field to gate scaling or position sizing
  (e.g. A-tier setups get 1.2× sizing), but that's a separate change
  with its own §16 audit per §15 hard boundaries.

## Bugs not addressed in this commit
- `plan_type` (default "SMC" at planner.py:161) is also stuck — every
  trade in the journal is SMC. ATR_FALLBACK and HYBRID paths likely
  exist somewhere but never assign the field. Separate investigation.
- Setup qualifier "Strong vs Soft" win-rate reversal (n=12 vs 5) —
  still too small to act on. Track in future forensics runs.
