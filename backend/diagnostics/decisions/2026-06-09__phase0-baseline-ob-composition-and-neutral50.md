# 2026-06-09 — Phase 0 baseline: OB source composition + neutral-50 counterfactual

Measure-first baseline for the SMC/scoring remediation (T2/T3). Operator acknowledged;
gate recalibration (4F) and wick demotion weights (4C) derive from these numbers.

## Diagnostics (landed `backend/diagnostics/`)
- `diag_neutral50_contribution.py` — A/B/C counterfactual scoring policies (T3-2 sizing)
- `diag_ob_source_composition.py` — per-source OB pool composition (T3-3 sizing)
  - One deviation from "import-paths-only": `load_live()` called `IngestionPipeline()` with
    no args, but ctor requires `adapter`. Fixed to `IngestionPipeline(PhemexAdapter())`,
    mirroring `_smc_perception_probe.py`. Diagnostic plumbing only; no engine touched.

## 0.2 — OB source composition (LIVE Phemex, 5 symbols × {15m,1h,4h} × 4 modes, n≈1,772 OBs)
- **Pool composition:** bos 31% · structural 51% · rejection_wick 18%
- **Wick wrong-color rate: 64% (204/320)** — audit claim CONFIRMED & large. Wick detector
  never checks SMC origin-candle color (bullish OB should originate RED, bearish GREEN).
- **Wick dual-tag candles: 0** — audit's "same candle tagged both directions" claim does
  NOT reproduce on real data (or synthetic). Drop from T3-3 rationale unless seen elsewhere.
- **Wick agreement rate: 39% (124/320)** — the demotion-keeps number. ~39% of wick OBs sit
  ≥50% inside a same-direction structure-confirmed OB (retain value as confluence/agreement
  bonus); ~61% go standalone-ineligible. The "keep, tag, confluence-only" decision preserves
  ~2 of every 5 wick OBs as confirmation, silences the rest.
- **Gate-2 survivor mix: bos 35% · structural 44% · wick 21%** — wick OBs are 21% of what the
  scorer currently sees, anonymized + weight-equal. Size of the T3-3 (4C) re-weight.

## 0.4 — Stealth/Overwatch Grade-A starvation: CONFIRMED on real data
Swing modes (overwatch, stealth) get ~0–2 BOS-linked Grade-A OBs while strike/surgical get
13–27 on identical candles, across all 5 symbols and all TFs. Tracks the `SMC_BREAK_MODES`
split (`bos_choch.py:28-32`, `macro_surveillance` → `"4swing"` + volume gates). HYPOTHESIS
(not concluded): 4-swing + volume gating on structural-break detection, inherited by stealth's
config, suppresses the BOS events `detect_obs_from_bos` needs. → Phase 3 (3A/3B/3C) confirms
the stealth→break-mode mapping BEFORE proposing any gate loosening (propose, don't apply).

## 0.3 — DEFERRED (operator chose Option B)
Gate-recal input (mean A−C inflation, per-mode pass-rate) NOT produced cleanly now:
`pipeline_smoke` never calls `calculate_confluence_score`; `backend.cli scan` is a typer demo
(`--profile balanced`, default binance, min_score=65 — wrong gate/mode). Root cause: the
diagnostic's own documented instrumentation gap — breakdowns are never persisted, so no
historical factor-level data to replay. **Plan:** land the breakdown-persistence line in 4B,
run a real paper session, then replay via `--scan-json` at 4F. Synthetic math validated only
(A−C=+22.67 fixture-driven, B>A 3/3 → confirms 4B's three sub-changes must ship together).
