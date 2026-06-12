# Phase 5-pre — P/D anchor disagreement baseline (window-50 vs structure-anchored)

**Date:** 2026-06-12
**Diagnostic:** `backend/diagnostics/phase5_pd_anchor_disagreement.py` (read-only, re-runnable)
**Run:** Part A — LIVE Phemex, 5 majors × {15m,1h,4h,1d} × 4 modes (80 grid cells).
Part B — 200 deduped historical gate-clearers from signals.jsonl replayed through the gate
step-5 `in_optimal_zone` predicate (scorer.py:1138-1140) on the gate HTF (1d), stealth swing
config; 182 evaluable (18 skipped no-data, incl. PEPE delisted-on-Phemex).
**Design:** `2026-06-12__phase5-design-pd-structure-anchored-dealing-range.md`

## Headline numbers

| Metric | Value |
|---|---|
| Part A classification flip rate (premium↔discount) | **16/80 (20%)** |
| Part A fallback rate (sparse structure) | **0/80 (0%)** |
| Part A flip direction | **ALL 16 flips premium → discount** |
| Part A per-TF flips | 15m 20% · 1h 20% · **4h 40%** · **1d 0%** |
| Part A median EQ delta (flipped TFs) | 0.34–0.78 ATR (max 1.42) |
| Part A per-mode | identical 20% across all four modes |
| **Part B gate `in_optimal_zone` flips** | **4/182 (2%)** — UPPER BOUND on -40 flips |
| Part B flip direction | 3 of 4 are False→True (**permissive**); 1 True→False |
| Part B fallback | 0 |

## Reading

1. **The structural anchor matters where it should.** 20% of live cells classify differently —
   the window range drags stale extremes into EQ; the structural range tracks the operative
   leg. In the current down-market every flip is premium→discount: the window-50 high anchors
   EQ too high, mislabeling prices as "premium" that are mid-range of the actual dealing leg.
   This is precisely the defect the locked decision targets. 4h is most affected (40%); 1d
   barely moves (0% — window-50 ≈ the structural range at 500-candle daily horizon).
2. **Sparse-structure fallback is a non-issue at these TFs** — 0% across 80 cells with
   500-candle dfs and TF-scaled lookbacks. The 1w concern from the design remains unmeasured
   (1w not in the bot's TF set; revisit only if 1w P/D ever becomes live).
3. **Mode-insensitive** — identical flip sets across all four modes (structure_swing_lookback
   resolves identically per TF across modes in current config). Simplifies reasoning: the
   anchor change is a per-TF effect, not a per-mode effect.
4. **§15 gate impact is SMALL and skews permissive.** ≤2% of historical gate-clearers flip
   `in_optimal_zone` (upper bound — the -40 also needs min_aligned_distance > 1.0 ATR, not
   reconstructable). 3 of the 4 flips make formerly out-of-zone entries in-zone (gate gets
   *less* likely to fire -40, and those entries already cleared anyway). Exactly 1 flip
   (INJ LONG, eqΔ 0.36 ATR) is in the restrictive direction.

## Q5 implication (operator sign-off for 5C, the gate flip)

The measured gate-input shift: ≤2% of gate-clearers affected, 3:1 permissive:restrictive.
No threshold changes anywhere. This is the baseline data §15 requires; sign-off decision
deferred to operator per design (after 5B's one live session per locked Q3).

## Caveats

- Single market era (down_normal-dominated history) — flip direction (all premium→discount)
  is market-state-dependent; in an up-leg the mirror (discount→premium) is expected by the
  algorithm's symmetry. Magnitude (20%) is the robust number, not direction.
- Part B uses today's fetched 1d history sliced to each signal's timestamp — identical to the
  candles the gate saw at the time for 1d data (immutable closed candles).
- Part B is gate-clearers only (the known sub-gate persistence blindspot, see 4F entry) —
  entries the OLD anchor -40'd out of existence never reached the log, so we cannot measure
  setups the NEW anchor would have admitted. The permissive skew suggests this population
  exists. Forward measurement in 5B/5D covers it.

## Mass conservation
Part A: flip 16 + same 64 + fallback 0 == 80 ✅ (runtime-asserted in the script)
Part B: flip 4 + same 178 + fallback 0 == 182 ✅ (runtime-asserted)

## Next (per design + locked Qs)
- 5A — capability behind `anchor="window"` default, zero behavior change + full test file.
- **STOP before 5B** — operator reviews these numbers (this entry is the review artifact).
- 5B → one live session → Q5 sign-off → 5C → 5D.
