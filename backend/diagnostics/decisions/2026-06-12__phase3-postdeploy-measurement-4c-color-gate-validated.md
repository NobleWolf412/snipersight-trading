# Phase 3 post-deploy measurement — 4C color gate VALIDATED, starvation question still open

**Date:** 2026-06-12
**Diagnostic:** `backend/diagnostics/diag_ob_source_composition.py` (extended this session: per-`source` wrong-color split)
**Run:** LIVE Phemex, 5 majors (BTC/ETH/SOL/BNB/XRP) × {15m,1h,4h} × 4 modes, n≈1,727 OBs
**Baseline:** `2026-06-09__phase0-baseline-ob-composition-and-neutral50.md`

## Why this ran

Two open items converged on the same diagnostic:
1. Phase 3 (bos_choch 3A/3B/3C) post-deploy: rerun vs Phase-0 baseline to decide whether the
   Grade-A starvation option (emit volume-rejected breaks tagged `volume_confirmed=False`,
   OB-taggable) goes to operator.
2. 4F left 4C's wick demotion **inconclusive at n=9** — needed a large-sample check that the
   wick color gate actually fires in the live detector path.

## Result

| Metric | Phase-0 baseline | Post-3/4C | Read |
|---|---|---|---|
| **rejection_wick wrong-color** | 64% (blended w/ engulfing) | **0/140 (0%)** | ✅ 4C gate validated |
| engulfing wrong-color | (not split out) | 60/68 (88%) | by-design bypass / new flag |
| Pool: bos/struct/wick | 31/51/18% | 28/60/12% | structural now dominates |
| Gate-2 survivors: bos/struct/wick | 35/44/21% | 23/64/14% | wick share to scorer ↓ |
| Wick agreement | 39% | 43% | stable |

## Findings

1. **4C color gate CONFIRMED working — `rejection_wick` 0% wrong-color on n=140 live OBs.**
   This is the large-sample validation 4F couldn't give. The diagnostic predated 4C and
   call-site-tagged ALL wick-detector output (rejection_wick + engulfing) as one pool, so the
   blended 29% understated the gate. Extended the diag this session to split by the production
   `ob.source` field → rejection_wick isolates to 0%. Engulfing carries the whole 29% residual.

2. **Grade-A starvation question STILL OPEN — not resolved by this rerun.** The bos/structural/
   wick composition deltas (bos 31→28%, structural 51→60%) conflate Phase-3 code changes with
   MARKET DRIFT — baseline and rerun are different market days, not same-data replay. The
   wrong-color validation is robust to this (per-OB property), but composition share is not.
   Resolving starvation needs same-data replay, which requires baseline candle snapshots we did
   not persist. **Do not conclude starvation is relieved/worsened from this rerun.**

3. **NEW FLAG (open, unverified): engulfing OBs are 88% "wrong-color" by the wick doctrine.**
   Likely correct — engulfing OBs anchor on the engulfing candle (green=bullish / red=bearish),
   which the wick-color metric (bullish origin = RED) flags but which is a different, defensible
   SMC doctrine. NOT asserted as a defect. Open question: does the engulfing branch anchor/color
   OBs per a correct engulfing doctrine, or is there a latent color/direction defect analogous to
   the one 4C fixed for wicks? #3-correctness at most; verify before any action.

## Decisions

- **4C: closed-validated.** The wick color gate works in the live path. The 4F "inconclusive"
  verdict on 4C is now superseded by this n=140 / 0% result.
- **Phase 3 starvation option: deferred, NOT decided.** This rerun cannot isolate the code effect
  from market drift. Revisit only with same-data replay (needs persisted baseline candles) — or
  fold into a future calibration that captures both eras on identical data.
- **Engulfing color/anchor doctrine: logged as a new open item.** No code change now.

## Artifact

`diag_ob_source_composition.py` now permanently emits the per-source wrong-color split
("by 4C source:" line) — future reruns are 4C-aware by default. Read-only; no engine surface.
