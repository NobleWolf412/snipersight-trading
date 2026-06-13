# P/D factor is INVERTED as a predictor in trending regimes (finding)

**Date:** 2026-06-13
**Diagnostic:** `backend/diagnostics/pd_direction_efficacy.py` (read-only, re-runnable)
**Origin:** Operator chart-reading session — BTC 4h/1d structure walk surfaced that the
Premium/Discount factor's "premium=sell / discount=buy" rule fights with-trend BOS
continuation, with no wiring between the P/D factor and the BOS/structure factor.

## Confirmed wiring gap (code facts)
- `scorer.py` P/D factor (~:2870) reads ONLY `current_zone`, `zone_percentage`,
  `direction`, VWAP. Zero reference to structural breaks.
- HTF gate `evaluate_htf_structural_proximity` (935-1230): grep for
  `structural_break|BOS|CHoCH|continuation|with-trend` → **nothing**. The −40
  PremiumDiscount_VIOLATION fires off OB/FVG/swing proximity, never off continuation.
- "Market Structure (CHoCH/BOS)" is a SEPARATE additive factor (~:2532, weight ~0.11).
  Nothing arbitrates between it and P/D — on a continuation breakout they point opposite
  and are simply summed.

## Measurement (clean cut)
Per-trade matched to its own originating signal; post-clamp era only (entry ≥ 2026-06-01,
removes the wide-stop confound); three buckets. **n=123 matched (0 unmatched), 201 pre-era
skipped.**

| Bucket | n | Win-rate | Avg PnL | Total |
|---|---|---|---|---|
| **P/D FAVORED the direction** | 48 | **38%** | **−4.42** | **−211.97** |
| **P/D OPPOSED + aligned BOS (conflict)** | 39 | **54%** | **+1.71** | **+66.60** |
| P/D OPPOSED, no BOS | 36 | 58% | −1.03 | −36.95 |

**The P/D factor's endorsement is inverted.** Trades P/D *favored* were the worst cohort;
trades that *overrode* P/D to follow a confirmed aligned BOS continuation were the only
clearly profitable cohort. The control (opposed, no BOS) sits in the middle → it's
specifically the **BOS-continuation override** that's the winning condition.

Earlier exploratory (symbol-level, all-era) cut agreed directionally: conflict cohort
+28 vs others −915 — but that was confounded (symbol-level matching, wide-stop era pooled).
The clean per-trade era-filtered cut above supersedes it.

## Mechanism
"Premium=sell / discount=buy" is a RANGING/REVERSAL rule. In a confirmed trend continuation
it's a category error — premium during an uptrend is just price advancing, not a sell signal.
The running-extreme anchoring (Phase 5) amplifies it: price stays pinned at the range
extreme during trends, so the P/D direction-reward is maximally wrong exactly during
continuation moves.

## Decision: DEFER the scoring change; design queued
NOT rewiring the standing-fix-protected scorer on this sample. Per the same discipline as
the 4F gate-recal deferral:
- **n is modest** (~40/bucket); 54% vs 38% WR is ~1.5σ, not airtight.
- **Single regime** — post-Jun-1 is down_normal-dominated. Honest finding is "P/D inverted
  IN TRENDS"; it may be CORRECT in ranging markets (fading extremes). No ranging sample yet.
- **Modeled PnL** — relative-better ≠ net-profitable after real fees (edge-after-fees verdict
  still stands).

**Revisit-to-ship threshold:** grow n (the sub-gate breakdown-persistence track feeds this),
and ideally catch a ranging-regime sample to confirm the conditional (P/D good in ranges, bad
in trends) before committing the change. Design queued at
`decisions/2026-06-13__phase5e-design-pd-trend-conditioning.md`.

## Re-run
`python -X utf8 -m backend.diagnostics.pd_direction_efficacy` — re-check as n grows and after
any fix lands (efficacy should flip: P/D-favored should stop being the worst bucket).
