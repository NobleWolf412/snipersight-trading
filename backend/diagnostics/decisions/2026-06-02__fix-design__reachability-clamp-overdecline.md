# 2026-06-02 — FIX DESIGN (§15 threshold tune): TP1 reachability clamp is over-declining

**Status:** DESIGN — awaiting operator calibration decision. NO CODE/CONFIG CHANGED.
**Type:** Planner threshold re-tune (CLAUDE.md §15 — needs documented baseline + reasoning + operator sign-off).
**Builds on:** [[2026-05-30__fix-design__tp1-reachability]] (the clamp), [[2026-06-01__planner-reason-mask-ev-none]] (un-poisoned the data this rests on).

---

## PROBLEM (baseline-documented, triply-confirmed)

The TP1 reachability clamp (planner_config.py: `tp1_reachable_ceiling_atr=1.3`,
`target_min_rr_after_clip=1.2`) fixed the original longbook pathology (stops 3-4 ATR ×
1.5R ladder → TP1 at 5-6 ATR → stagnation). But it is now **over-declining** — it kills
the entire structural-stop cohort, not just the extreme tail.

**Decline math:** a plan is DECLINED when `ceiling / stop_atr < min_rr_after_clip`, i.e.
`stop_atr > ceiling / min_rr_after_clip = 1.3 / 1.2 = 1.083 ATR`. So **any stop wider than
~1.08 ATR is declined** (≈1.3 ATR where the scalp `min_rr_after_clip=1.0` tier applies).

**Evidence (3 independent confirmations):**
- stop_reachability_baseline, session 562c7b13: taken trades 0% wide (≥1.5 ATR); good
  window (<2026-05-24) 11% wide; expectancy +0.56 vs +7.21.
- stop_reachability_baseline, session 0202c781 (post-reason-mask-fix, clean reasons):
  taken 0% wide, expectancy **-1.90** (DEGRADED), 29% win; every taken trade stop
  0.47-1.05 ATR. `tp1_unreachable` = 22% of rejections (241).
- WIDE-STOP diagnostic: 2078 wide stops computed, median 1.50 ATR, 551 genuinely
  structural-wide — and 0% reach a taken trade.

**Consequence chain:** over-decline → engine restricted to tight-stop (<1.08 ATR) setups →
predominantly scalps (the [[project_cascade_scalp_monoculture]]) → tight-stop scalps in a
compressed/choppy regime get whipsawed (0202c781: 5/7 stop-outs) → degraded expectancy.
The profitable +7.21 reference window EARNED its edge partly on the 11% wide-stop cohort
the clamp now declines.

## TWO LEVERS (the key design insight)

The decline boundary = `ceiling / min_rr_after_clip`. Both knobs move it, with different
side effects:

| Lever | Effect on decline boundary | Side effect |
|---|---|---|
| **A. Raise `tp1_reachable_ceiling_atr`** (1.3 → 1.8 / 2.0) | 1.8→ decline at 1.5 ATR; 2.0→ at 1.67 ATR | Also raises the CLAMP target distance → TP1 can be pulled to 1.8-2.0 ATR. Risk: re-introduces some unreachable-TP1 stagnation (the original bug) if the true reachable move is ~1.3 ATR. |
| **B. Lower `target_min_rr_after_clip`** (1.2 → 1.0) | decline at `ceiling/1.0 = 1.3 ATR` | Keeps the reachability ceiling at 1.3 (no new stagnation), just accepts a tighter clamped R:R (down to 1.0) on wider stops. Already what the scalp tier uses (config:163). |

**Lever B is the lower-risk first move:** it widens the accepted stop range to ~1.3 ATR
*without* moving the reachability ceiling (so TP1 stays clamped to a genuinely-reachable
1.3 ATR), recovering a chunk of the structural cohort while keeping the anti-stagnation
property. Lever A goes further (recovers stops up to 1.5-1.67 ATR) but trades against the
reachability guarantee and needs stagnation re-measurement.

## PROPOSED CALIBRATION (operator to choose the starting point)

Recommend a **staged A/B**, not a blind set:
1. **Stage 1 — Lever B only:** `target_min_rr_after_clip 1.2 → 1.0` (decline boundary 1.08 → 1.30 ATR).
   Run a paper session, re-run stop_reachability_baseline. Success = some wide-stop cohort
   returns AND expectancy improves AND `targets_hit`/stagnation does NOT worsen.
2. **Stage 2 (only if Stage 1 under-recovers) — Lever A:** raise `tp1_reachable_ceiling_atr`
   1.3 → 1.5 (decline boundary → 1.25 ATR at min_rr 1.2, or 1.5 ATR combined with B).
   Re-measure stagnation explicitly (the thing the original clamp fixed).

DO NOT widen both aggressively at once — that risks re-opening the longbook stagnation bug.

## WHY OPERATOR SIGN-OFF IS REQUIRED (§15)
These are planner thresholds tuned from outcome data. The baseline here is the documented
evidence §15 requires, but: (a) the degraded sample is small (n=7, one down_compressed
session), (b) the "good" reference is pre-2026-05-24 (possible regime difference), (c) the
re-tune trades against the anti-stagnation property the clamp exists for. So this is a
controlled-experiment decision, not an autonomous threshold edit. The coder will implement
the chosen Stage-1 value + the same-diff regression + audit gate ONLY after sign-off.

## VERIFICATION PROTOCOL (per stage)
symmetry-guard (planner/scoring-adjacent) · §16 audit · backend-integrity · same-diff
regression asserting the decline boundary moved as intended (a stop at 1.2 ATR is now
clamp-accepted not declined under Stage 1) · paper session + stop_reachability_baseline
re-run showing wide-stop cohort recovery WITHOUT stagnation regression.

## RELATED CHEAP CLEANUPS (independent, can land anytime)
- planner_service.py:432 `%s`→`{}` (loguru) so reachability declines log their symbol+geometry.
- orchestrator.py:3357 revalidation block — add the `if plan is not None` guard (mirror the EV fix).
