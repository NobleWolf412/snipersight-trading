# 2026-05-30 — Stop-distance root cause: structure-finding collapse → regime-blind fallback

**Type:** root-cause investigation (read-only forensics; no fix yet)
**Follow-on to:** `2026-05-29__longbook-degradation-rootcause.md` (this CORRECTS its primary attribution)
**Trigger:** operator asked to investigate why `stop_distance_atr` tripled (0.53→1.50 ATR median) before building the TP1 reachability clamp.

## Verified finding

The 2026-05-24 degradation's proximate driver is a **structure-finding success collapse**, not the
Tier 1.1 near_entry target change.

Stop-distance composition (from trade_journal.jsonl):

| Window | structural (<1.0 ATR) | fallback ~1.5 ATR | most common value |
|---|---|---|---|
| GOOD (≤05-23) | 77% | 11% | 0.35 (×12), 0.53 (×11) |
| DEGRADED (≥05-24) | 43% | 27% | **1.50 (×27)** |

When swing/OB/structure detection fails, `_calculate_stop_loss` falls back to a fixed
mode-based ATR multiple (risk_engine.py:1216-1240): **1.5× for scalp (precision/intraday),
2.5× for STEALTH, 3.0× for overwatch, 2.0× balanced.** Executed degraded trades were
scalp-tier → 1.5× fallback → the 1.50-ATR clustering. These fallback stops are ~3× wider than
the structural stops they replaced (median 0.53 ATR in the good window).

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
changed in 2026-05-20..05-24 (only Tier 1.1 target change, 1e0cbf8). So the shift is a change in
the structural-vs-fallback MIX (structure-finding failing more), exposed by market conditions —
NOT a code regression in the stop logic.

## Why structure-finding fails more (hypotheses — NOT yet verified)

Per-trade structural-vs-fallback rate is not in the journal and the planner's structural-success
logs are info-level (dropped by the WARNING+ dev_servers.log sink — observability gap). Candidates,
several already confirmed by the hot-path audit (`2026-05-29__hotpath-robustness-audit.md`):
- Market compressed into a low-structure regime (genuine absence of clean swings/OBs).
- #6 `smc_service.py:692-693` — bare `except: pass` zeroes equal-highs/lows + liquidity pools for
  a TF, silently → planner finds "no structure" → fallback.
- #12 `indicators.py:143-147` — flat-price Bollinger drops a TF → less structure.
- #11 `entry_engine.py:459-468` — freshness scale-confusion picks worse/wider entry zones.

## Fix direction (for design phase — §15 + live-path, needs design entry + baseline)

Two complementary levers, highest first:
1. **Restore structure-finding** — fix the silent SMC/BB failures (#6, #12) so trades find tight
   structural stops (the good-window behavior). Addresses the root, not the symptom.
2. **Make the fallback stop regime/range-aware** — when structure is absent, scale the fallback to
   the actual recent range (e.g. ATR-percentage or N-bar range) instead of a fixed 1.5/2.5× ATR, so
   compressed markets get proportionally tighter stops + reachable TPs. §15 threshold change.

The TP1 reachability clamp (Plan Option B) remains a valid symptom-side guard but is now secondary
to the structure/fallback root.

## Correction to prior attribution

`2026-05-29__longbook-degradation-rootcause.md` named the Tier 1.1 near_entry anchor as the single
confirmed root cause. That is **demoted to a minor target-side aggravator**. The dominant driver is
the structure-finding collapse → regime-blind fallback stop, verified above.
