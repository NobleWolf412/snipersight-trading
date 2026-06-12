# Phase 5 DESIGN ENTRY — structure-anchored Premium/Discount dealing range

**Date:** 2026-06-12
**Status:** DESIGN APPROVED — operator locked Q1–Q4; Q5 (§15 sign-off) pending 5-pre numbers
**Plan provenance:** Plan agent (read-only), full graphify orientation first (§18 gate),
all claims confirmed in code. Plan pasted verbatim in-session per §18.

## Locked operator decision (pre-existing, from remediation kickoff 2026-06-09)
"P/D structure-anchored" — equilibrium derived from actual dealing-range structure, not
a fixed `lookback=50` candle window.

## Operator decisions locked THIS session (do not re-ask)
- **Q1 — swing source:** RAW confirmed fractals (`_detect_swing_highs/_lows` +
  `_build_swing_sequence` from bos_choch.py), TF-scaled `structure_swing_lookback` — the same
  structure the BOS/CHoCH engine sees. NOT ATR-filtered.
- **Q2 — telemetry tag:** YES — append `[struct]` / `[fallback]` to the "Premium/Discount Zone"
  factor rationale string (4F-style code-signature cohort detection from signals.jsonl).
  Factor NAME stays byte-identical.
- **Q3 — 5C timing:** HOLD — 5B (snapshot/factor flip) runs one live session before 5C
  (the §15 gate flip) lands. Gate keeps window EQ in the interim; divergence is intentional,
  time-boxed, documented.
- **Q4 — dead functions:** `get_optimal_entry_zone` / `is_price_in_optimal_zone`
  (premium_discount.py:105,134; zero callers repo-wide) → repo-janitor list. NOT touched in
  Phase 5.
- **Q5 — §15 sign-off:** PENDING. Contingent on 5-pre gate-counterfactual flip rates.

## Approved algorithm (a*: last confirmed swing pair, extended by running extremes)
Per TF: SH* = most recent confirmed swing high, SL* = most recent confirmed swing low
(raw fractals, TF-scaled lookback via `get_tf_smc_config(tf, mode)` / `scale_lookback`).
- `range_high = max(SH*.price, max(high) after SH*)`
- `range_low  = min(SL*.price, min(low) after SL*)`
- EQ / 25% / 75% / classification formulas UNCHANGED (premium_discount.py:74-100, same
  `>=` tie-break). Only the endpoints change.
- Running-extreme extension = ICT current-leg semantics; preserves "last candle inside range"
  invariant (no zone_percentage > 100, no pathological gate violations mid-expansion);
  bull/bear symmetric by construction.

**Rejected alternatives:** (a) swing pair w/o extension — price exits range on expansion legs,
gate -40 fires on every breakout continuation. (b) BOS/CHoCH origin→extreme — StructuralBreak
doesn't store origin swing; break availability mode/TF-uneven → silent per-mode degradation.
(c) HTF swing pair for all TFs — collapses per-TF contract; double-counts HTF swings already
consumed by gate step 4. Also rejected `detect_swing_structure` as swing source (ATR-filters +
needs lookback*2+20 candles → inflated HTF fallback).

**Sparse-structure fallback (loud):** no confirmed SH or SL → fall back to tail(lookback)
window, stamped `range_anchor="window_fallback"`, WARNING log w/ symbol/TF/df-len, per-TF
fallback counter. Never silent.

**Runtime sanity assertion:** `range_low <= extreme_discount <= equilibrium <=
extreme_premium <= range_high`, `range_size >= 0`, structure-anchor ⇒ last close in range;
violation → ERROR + degrade to window fallback (no exception up the stack).

## Blast radius (confirmed in code)
- `analysis/premium_discount.py:49` detect_premium_discount — MODIFIED (new anchor + fallback)
- `analysis/premium_discount.py:20` PremiumDiscountZone — EXTENDED additive only:
  `range_anchor`, `anchor_swing_high_ts`, `anchor_swing_low_ts`, `swing_lookback_used`
- `services/smc_service.py:743` _detect_premium_discount (← _detect_timeframe_patterns:666,
  EVERY TF) — MODIFIED in 5B (anchor="structure" + TF-scaled lookback + fallback telemetry)
- `strategy/confluence/scorer.py:1132` gate step 5 of evaluate_htf_structural_proximity:935 —
  §15 PRE-SCORING GATE — MODIFIED in 5C ONLY (sign-off gated, separate revertible commit)
- Snapshot readers (no code change, input shifts): scorer factor block :2857-2881 (weights
  OW .12/STRIKE .07/SURG .09/STEALTH .08), surgical conflict-override :847, surgical tier
  anchors :3158-3161 (**P/D is a surgical TIER ANCHOR — tier churn expected, measured in
  5-pre**), planner `_is_in_correct_pd_zone` entry_engine.py:224 (+:621,:763,:1014,:1132;
  hard filter ACTIVE only OVERWATCH/STEALTH per planner_config.py:212,233)
- Untouched: MODE_FACTOR_WEIGHTS, min_confluence_score, all gate thresholds/ATR bands,
  pd_compliance_tolerance, factor name string, debug_confluence*.py (signature unchanged)

## Sub-steps
- **5-pre** — `diagnostics/phase5_pd_anchor_disagreement.py`: old-window vs structural side
  by side (live data): classification flip rate, EQ delta (ATR units), fallback rate per
  TF/mode, mass conservation (premium+discount+fallback==total); gate counterfactual on
  recent signals.jsonl gate-clearers (violation flips per mode — feeds Q5); planner
  counterfactual OVERWATCH/STEALTH. → decisions entry. **STOP: operator reviews before 5B/5C.**
- **5A** — capability, zero behavior change: `_compute_structural_dealing_range()` + extended
  kw-only signature (`anchor="window"` default → existing callers byte-identical). Full test
  file lands here. Contract diff clean (additive).
- **5B** — flip snapshot producer (smc_service) to anchor="structure" + [struct]/[fallback]
  rationale suffix (Q2). One live session of data before 5C (Q3).
- **5C** — flip the §15 gate input (scorer.py:1132). Thresholds byte-identical. Requires Q5
  sign-off w/ 5-pre + 5B live numbers. Separate, independently revertible commit.
- **5D** — default flip to anchor="structure" + post-deploy live measurement + capstone
  decisions entry + janitor note (Q4).

## Known/accepted risks
Discrete EQ jumps on new swing confirmation (auditable via anchor timestamps) · swing
confirmation lag post-reversal (bounded by running-extreme) · HTF fallback rate on
short-history symbols (1w needs 31+ candles — 5-pre measures; floor = operator call if high) ·
intentional 5B↔5C gate/factor divergence window · surgical tier churn.

## Additional findings logged during design
- `ZoneType` includes "equilibrium" but classifier NEVER emits it — binary premium/discount,
  tie → premium. Factor block defaults missing zone to "neutral" (scorer.py:2865). Not changed
  in Phase 5; documented behavior.
- Test plan highlights: bull/bear symmetry via price-mirrored df
  (`zone_pct_mirror == 100 - zone_pct`), expansion legs both directions, sparse-fallback
  caplog WARNING assertion (loudness is tested), flat-df range_size==0 → 50% no ZeroDivision,
  gate non-regression (structural EQ == window EQ ⇒ byte-identical gate output).
