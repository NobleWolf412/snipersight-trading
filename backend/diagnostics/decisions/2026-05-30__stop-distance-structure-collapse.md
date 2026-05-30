# 2026-05-30 — Stop-distance investigation: wide stops are the mechanism; precise cause NOT isolated

> **CORRECTED 2026-05-30 (same day):** the original title/claim "structure-finding collapse"
> is WRONG and is struck. A direct repro (fetch real candles for INJ/OP/ARB on 15m/1h/4h via
> /api/market/candles, run the detectors with loguru silenced) shows **structure detection is
> HEALTHY** — swings 5–11, OBs 0–11, consolidations present, ZERO exceptions. Detection is not
> failing. The stop-BUILDER produces wide stops *despite* good detection. The precise reason
> (fallback-selection rejecting structural levels, vs. distant structural levels being chosen,
> vs. entry-zone interaction) is **NOT yet isolated** — needs an instrumented trace of
> `_calculate_stop_loss` on real degraded inputs. Do not treat the cause below as verified.

**Type:** root-cause investigation (read-only forensics; no fix yet) — PARTIAL, cause not isolated
**Follow-on to:** `2026-05-29__longbook-degradation-rootcause.md`
**Trigger:** operator asked to investigate why `stop_distance_atr` tripled (0.53→1.50 ATR median) before building the TP1 reachability clamp.

## What IS solid (verified)

The 2026-05-24 degradation's proximate **mechanism** is **wider stops**, and that mechanism is
well-evidenced. The single *cause* of the wider stops within the planner is NOT yet isolated.

Stop-distance composition (from trade_journal.jsonl):

| Window | <1.0 ATR | exactly ~1.5 ATR (fallback fingerprint) | "other" (mostly ≥1.5) | median |
|---|---|---|---|---|
| GOOD (≤05-23) | 77% | 11% | ~12% | 0.53 |
| DEGRADED (≥05-24) | 43% | 27% | ~30% | **1.50** |

`_calculate_stop_loss` falls back to a fixed mode-based ATR multiple when no SUITABLE structural
stop is selected (risk_engine.py:1216-1240): **1.5× scalp, 2.5× STEALTH, 3.0× overwatch, 2.0×
balanced.** The 1.50-ATR cluster (27 of 105 degraded) is the scalp fallback fingerprint. BUT the
fallback is NOT triggered by detection returning empty (detection works — see correction banner);
it must be triggered by the stop-builder's SELECTION/validity logic not using the detected
structure, OR degraded trades are taking wider *structural* stops. Which one is unverified.

These wider stops (whatever their precise origin) are ~3× the good-window structural stops (0.53 ATR).

Mechanism — one root, both symptoms:
- Wider stop (1.5 vs ~0.5 ATR) → **bigger losses** (avg loss −2.72 → −27.52).
- At a fixed 1.5R ladder, TP1 = 1.5 × stop = ~2.25 ATR from fill, but favorable excursion is
  ~0.6 ATR → **TP1 unreachable** → targets_hit 0.34→0.13, stagnation 4→28, 61% favorable-then-lost.

Live confirmation (paper session af72d038, 2026-05-29): the new TP1-reachability diagnostic
fired 7× (2.32/2.60/4.10 ATR; 2.32 = scalp 1.5× fallback × ~1.5R; 4.10 = STEALTH 2.5× fallback).
Planner regime_label observed = "calm" (volatility-mapped via get_atr_regime) — re-confirms the
regime-key no-op correction.

## Not a stop-code regression

`git blame`: the 1.5 scalp fallback is from the initial commit (8e8f01e, 2026-02-27); the 2.5
STEALTH fallback from 5c4bb23 (2026-03-13). Both predate the good window. No stop-placement code
changed in 2026-05-20..05-24 (only Tier 1.1 target change, 1e0cbf8). So the wider-stop shift is
NOT a code regression in the stop logic — it is a behavioral shift in what the stop-builder
produces, driven by inputs/market.

## Ruled OUT and STILL OPEN (corrected)

RULED OUT by the candle repro (real INJ/OP/ARB, 15m/1h/4h, 2026-05-30):
- "Structure detection collapsed" — REFUTED. Detection is healthy (swings 5–11, OBs 0–11,
  consolidations present, no exceptions). The stop-builder has structure available.
- #12 `indicators.py:143-147` flat-BB TF drop — NOT firing (0 warnings in live session af72d038).
- #6 `smc_service.py:692-693` silent liquidity-pool except — affects the `liquidity_sweep`
  CONFLUENCE factor, NOT the swing/OB/consolidation inputs the STOP uses. Not the stop cause.

## ISOLATED (2026-05-30 instrumented trace) — wide STRUCTURAL stops, not fallback/cap

Added a branch-summary log at `_calculate_stop_loss` exit (WARNING-level so the prod sink keeps
it; conditional on dist ≥1.33 ATR to avoid spam) and ran a live STEALTH paper session
(ae4d1970). 10 stop-branch samples:

| branch | n | distance (ATR) |
|---|---|---|
| structural (used_structure=True) | 9 | 0.35, 0.53, 0.99, 1.07, 1.16, 1.88, 2.83 … |
| other | 1 | — |

- median 1.07 ATR, mean 1.40, max 2.83. **40% of stops ≥1.5 ATR** (→ TP1@1.5R ≥2.25 ATR).
- All wide stops were `used_structure=True` — genuine swing/OB invalidation levels, NOT the
  no-structure fallback (1/10) and NOT the max-stop cap (0/10 in this sample).

**Verified mechanism:** the stop-builder is working correctly — it places stops at real
structural invalidation. But in this regime those levels are often FAR (up to 2.83 ATR), and the
1.5R first-target ladder multiplies that distance → TP1 lands beyond the ~0.6-ATR favorable
excursion → stagnation / round-trip. It is a **stop-distance × TP-ladder vs market-range
mismatch**, not a fallback/cap/detection bug. (Caveat: 10 samples from the CURRENT regime; the
degraded-window journal's 27× exactly-1.50 indicates caps/fallbacks fired MORE during 05-24..29.
Both paths — wide-structural and 1.5-capped — converge on the same unreachable-TP1 outcome.)

This refutes (in order, all today): Gate-3 bypass, regime-key, Tier 1.1-as-primary, structure-
detection collapse, no-structure-fallback-dominance, max-stop-cap-dominance. The surviving,
evidence-backed conclusion is the mismatch above.

## Fix direction (now evidence-backed — design phase, §15 + live-path)

The fix must handle ALL stop-derivation paths (wide-structural, capped, fallback), so a
stop-side patch alone is insufficient. **TP1 reachability clamp (Plan Option B)** is the right
primary lever — clamp TP1 absolute distance regardless of how the stop was derived, floored at
the real admission R:R (`min_rr=1.0` / `target_min_rr_after_clip=1.2`, NOT the 1.5 the Plan
assumed). Secondary: in calm regimes prefer the nearest valid structural invalidation (reduce
wide-structural selection). Both §15 + live-path → design entry + baseline before code.

## Correction to prior attribution

`2026-05-29__longbook-degradation-rootcause.md` named Tier 1.1 near_entry as the single root cause;
that is demoted to a minor target-side aggravator. The MECHANISM (wider stops → bigger losses +
unreachable TP1) is solid; the single CAUSE within the stop-builder is NOT yet isolated. Four
hypotheses have been raised and refuted/demoted in one day (Gate-3 bypass, regime-key, Tier 1.1,
structure-detection collapse) — see `2026-05-29__regime-label-premise-miss.md`. Lesson reinforced:
reproduce on real data BEFORE asserting a cause. Next correct step is an instrumented
`_calculate_stop_loss` trace, not another inference.
