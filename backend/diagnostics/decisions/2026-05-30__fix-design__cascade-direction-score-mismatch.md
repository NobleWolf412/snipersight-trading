# 2026-05-30 — FIX DESIGN (scoring/symmetry): cascade direction-flip emits a plan scored for the opposite direction

**Status:** DESIGN — awaiting operator decision (a correctness + strategy fork). NO CODE WRITTEN.
**Bug:** Hot-path audit #3 (1_BROKEN). See [[2026-05-29__hotpath-robustness-audit]].
**Gate:** Scoring/orchestration change → CLAUDE.md §18 symmetry-guard auto-invokes + §16 audit. NOT §15 (no live-execution path), but it directly determines what direction trades fire and at what score.

---

## ROOT CAUSE (verified against HEAD)

`ConfluenceService.score()` (`confluence_service.py:148-730`) scores BOTH directions every call
(`_score_direction("bullish")` + `_score_direction("bearish")`), selects one as `chosen`, sets
`context.metadata["chosen_direction"]`, returns `chosen` (→ `context.confluence_breakdown`), and
stores ONLY the two raw total_scores in `context.metadata["alt_confluence"]`. The non-chosen full
breakdown is discarded. **Then it applies direction-specific adjustments to `chosen` only:**
- HTF-alignment bonus: +5 (macro+local aligned) / +2 (local only) — `confluence_service.py` HTF block.
- Counter-HTF penalty: −5/−10/−15/−20 by confirmation quality — counter-HTF block.

The cascade (`orchestrator.py:3668-3789`) then, per scale:
1. Re-derives `_scale_direction` via `_derive_cascade_direction` (3684) — a lightweight structural
   re-vote on the scale's own TFs, independent of the session direction.
2. Writes `context.metadata["chosen_direction"] = _scale_direction` (3702).
3. Re-runs **pre-scoring gates** for the scale direction (3739) — these ARE direction-correct.
4. Calls `_generate_trade_plan` (3762), which reads the flipped `chosen_direction` (2827) for
   geometry but passes the **unchanged `context.confluence_breakdown`** (2913) — i.e. the
   SESSION-direction breakdown, with the SESSION direction's factors, total_score, AND its
   HTF/counter-HTF adjustments.
5. `plan.confidence_score` (from that breakdown) → `effective = confidence_score + bonus` (3773)
   ranks the cascade candidates and persists into the live signal (2557).

**Net:** when a scale flips direction (e.g. session LONG, scale SHORT), the trade fires SHORT but
carries the LONG confluence score, LONG factor breakdown, and LONG-regime HTF adjustment. Geometry
(entry/stop/targets) is direction-correct (the "geometry also wrong" sub-claim was refuted in
verification); the SCORE and breakdown are the opposite direction's. This both (a) mis-ranks the
candidate vs other scales and other symbols, and (b) writes a misleading score to the signal/journal.

Note: the conflict-density flip (`orchestrator.py:1816`) is NOT affected — it sets the flip BEFORE
the main `score()` at 1922, so the main path scores the flipped direction correctly. Only the
cascade flip (post-score) is broken.

## THE FORK (operator decision)

### Option A — Retain both breakdowns; cascade passes the matching one
Store both full breakdowns from `score()` on context (e.g. `_breakdown_long` / `_breakdown_short`).
When `_scale_direction` ≠ session direction, `_generate_trade_plan` uses the matching pre-computed
breakdown.
- **Pro:** the raw both-direction breakdowns already exist — near-zero added cost.
- **Con (correctness gap):** the HTF-alignment bonus / counter-HTF penalty were applied only to
  `chosen`. The retained alt breakdown has the correct raw factors/total for its direction but NOT
  its own HTF/counter-HTF adjustment → still slightly mis-scored for the flipped direction. Requires
  also extracting the adjustment block into a helper and applying it to the alt (→ becomes Option B
  in practice).

### Option B — Re-score the flipped direction properly (recommended IF the feature stays)
Extract the post-selection adjustment block (HTF-alignment bonus + counter-HTF penalty) into a pure
helper `_apply_directional_adjustments(breakdown, direction, context)`. Then for a cascade flip,
run `_score_direction(flipped)` + the helper, and pass that breakdown. The main path calls the same
helper on `chosen` → symmetric by construction (one code path applies the adjustment for both).
- **Pro:** fully correct; the extraction also de-risks future drift between the two directions'
  adjustment logic (a latent symmetry hazard today).
- **Con:** more code; touches `scorer`/`confluence_service` adjustment logic → symmetry-guard must
  bless the extraction.

### Option C — Don't let the cascade flip DIRECTION at all (simplest; removes the bug class)
Restrict `_derive_cascade_direction` so a scale may flip TRADE-TYPE (swing/intraday/scalp) but always
inherits the session `chosen_direction`. Deletes the post-score direction mutation (3702) entirely.
- **Pro:** removes the whole bug class + a large block of complexity (per-scale gate re-run for a
  flipped direction, scalp counter-HTF block, restore-on-failure). No score mismatch is possible.
- **Con:** loses the intended feature — scales trading their own structure's direction (the comments
  at 3672-3678 describe this as deliberate: MTF/LTF scales may favour the opposite of an HTF-dominated
  session direction). This is a STRATEGY decision: is the cascade direction-flip earning its keep?

## RECOMMENDATION
This hinges on a question only the operator can answer with session data: **does the cascade
direction-flip produce winning trades, or is it an unproven complication?**
- If it is a valued, working feature → **Option B** (do it correctly; extract the shared adjustment
  helper for symmetry).
- If it is unproven / rarely fires / suspect → **Option C** (remove it; simplest and safest, and it
  eliminates an entire symmetry-hazard surface). Given the triage posture (we are de-risking the
  engine before tuning), C is the conservative default unless the flip has demonstrated edge.

Suggested pre-decision diagnostic: `/rejection-survey` + a grep of telemetry for the
`🔀 ... CASCADE ... direction %s→%s` log to quantify how often the flip fires and whether those
became taken/winning trades. I can run that before you decide.

## BLAST RADIUS (§20)
- **Upstream:** `_cascade_plan_generation` loop (3668), `_generate_trade_plan` (2797), `score()` (148).
- **Downstream:** `plan.confidence_score` → cascade ranking (3773), signal persistence (2557),
  `alt_confluence` metadata, `/confluence-trace` + `/scan-autopsy` consumers, trade_journal score field.
- **Symmetry:** this IS a bull/bear symmetry fix — any option must exercise LONG-session→SHORT-scale
  AND SHORT-session→LONG-scale in tests. Option B's extracted helper must be symmetric.
- **Contract:** no API/DB schema change expected; `alt_confluence` may gain a field (additive).

## REGRESSION DIAGNOSTIC (same diff — §18)
- Fixture: session direction = LONG, a scale whose `_derive_cascade_direction` returns SHORT.
  Assert the emitted plan's `confluence_breakdown` direction/total_score/factors match `plan.direction`
  (SHORT), NOT the session (LONG) — and the mirror (session SHORT → scale LONG).
- Option B: assert `_apply_directional_adjustments` produces identical results on the main path and
  the cascade re-score path for the same direction (symmetry).
- Option C: assert `_derive_cascade_direction` never returns a direction ≠ session; a cascade can
  change trade_type but not direction; negative test that no post-score `chosen_direction` mutation occurs.
- Live confirm via `/confluence-trace` (it already inspects cascade tier + direction comparison).

## VERIFICATION PLAN
symmetry-guard (mandatory — orchestrator/scorer touched) · §16 14-point audit · backend-integrity
blast-radius + `capture_contracts diff` + `pipeline_smoke` · new regression test green.
