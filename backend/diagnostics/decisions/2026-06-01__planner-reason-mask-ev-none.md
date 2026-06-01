# 2026-06-01 — Planner reason-masking bug (EV-on-None) found via diagnostic series

**Type:** Bug fix (RISKY — observability destruction, §11) + diagnostic-method note.
**Found by:** the /autopsy → /rejection-survey → /scan-autopsy → confluence-trace sweep (2026-06-01).
**Fix:** orchestrator.py `_generate_trade_plan` EV block wrapped in `if plan is not None:`.

## What it was
`orchestrator._generate_trade_plan` computed an EV estimate (`R = float(plan.risk_reward)`,
then `plan.metadata["ev"] = ...`) at ~orchestrator.py:3310 WITHOUT a plan-is-None guard
(unlike its ~12 sibling metadata blocks, all `if plan and ...`). When the planner returns
None on a legitimate decline (TP1 reachability decline, entry-depth gate, etc.):
1. `plan.risk_reward` → `AttributeError: 'NoneType'…'risk_reward'`
2. caught by the EV block's own `except Exception:`, whose body `plan.metadata["ev"] = None`
   **re-threw** `'NoneType' object has no attribute 'metadata'`
3. that escaped to the outer catch (:3430), which set
   `context.metadata["plan_failure_reason"] = str(e)` → the generic NoneType string
   **overwrote the real decline reason**.

## Impact
~2218 occurrences in a single session log; ~1431 in one session's signals.jsonl. It masked
roughly HALF the PLANNER-stage rejections (gate=no_trade_plan) — including the TP1
reachability declines — making the dominant rejection bucket (41% of all kills) undiagnosable.
No money/decision impact (the planner already declined; only the recorded REASON was corrupted),
but it blocked the reachability-clamp verification (the data we'd tune on was poisoned).

## Why the diagnostic sweep mattered (method note)
/rejection-survey (aggregate) buried the NoneType reason in the long tail. /confluence-trace
(per-symbol) surfaced it instantly (73 on DOT + 43 on DOGE). Lesson: per-symbol breadth catches
exception-as-rejection masking that aggregate ranking hides. The full traceback was available in
backend.err.log (logged at orchestrator.py:3433-3434) — that pinned the exact throw site.

## Fix + follow-ups
- FIXED: guard the EV block with `if plan is not None:`. Regression: test_ev_none_plan_reason_mask.py
  (None-plan-no-mask + valid-plan-still-EV). symmetry-guard PASS, backend-integrity CLEAN, §16 14/14.
- FOLLOW-UP (advisory, not done): the sibling revalidation block at orchestrator.py:3357 also lacks
  an `if plan` guard — harmless today (its except only debug-logs, no plan.metadata deref → cannot
  re-mask) but worth mirroring the guard in a hardening pass.
- FOLLOW-UP: planner_service.py:432 logs `"TP1 unreachable for %s — …"` with `%s` under loguru
  ({}-style) → symbol+reason not interpolated. Fix to {} so reachability declines self-document.
- UNBLOCKS: the TP1 reachability clamp re-tune (longbook 99303ff VERIFY-NEXT) — now that real
  decline reasons survive, a paper session + stop_reachability_baseline can measure over/under-decline
  on clean data. Baseline already suggests over-declining (1.3 ATR ceiling vs 1.5 ATR median stop).
