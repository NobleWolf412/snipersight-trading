# 2026-05-31 — Audit: SMC structural-level detection across timeframes + mode/type routing

**Type:** read-only correctness audit (no code change) — findings on record before any fix.
**Trigger:** operator asked how well structural levels are computed considering different
timeframes and trade modes/types.
**Method:** two parallel read-only auditor agents — (A) detection-side (per-TF detector
correctness), (B) consumption-side (mode/type → TF routing for stop/entry/target + HTF/LTF roles).
**Scope:** backend/strategy/smc/* , backend/services/smc_service.py , backend/shared/config/
scanner_modes.py + planner_config.py , backend/strategy/planner/{risk_engine,entry_engine}.py ,
backend/strategy/confluence/scorer.py , backend/services/confluence_service.py.

**Caveat:** these are agent findings, relayed faithfully but NOT yet independently line-verified
by the coder. Each must be confirmed at the cited file:line before a fix lands.

## Headline

Core routing is SOUND. The "scalp pulls 4h structure for its stop" fear is **REFUTED**: the
cascade rebuilds per-tier TFs (`_build_cascade_config`, orchestrator.py:3514) and pre-filters the
SMC snapshot to those TFs (orchestrator.py:2867-2885), so a scalp tier genuinely uses 15m/5m.
ATR is computed per-TF in every detector (no cross-TF leakage). Swing structure is correctly
HTF-gated (1w/1d/4h). HTF/LTF roles are cleanly separated (HTF=bias, LTF=entry). Hot-path #8
(worker current_regime None) and #9 (htf_trend clobber) are CONFIRMED FIXED.

Six real defects found (severity-ordered):

## Findings

### 1_RISKY / 2_RISKY (money-path)

**F1 (RISKY, CONFIRMED) — `track_pool_sweeps` uses `swept` before assignment.**
`liquidity_sweeps.py:1028-1033`: `swept` is bound only inside `if swept_mask.any():`. On the first
pool whose mask is empty, `if swept:` raises `NameError`, swallowed by the caller's except
(smc_service.py:692) → `result["liquidity_pools"]` becomes `[]` for the ENTIRE timeframe, logged
only generically. After any pool sets `swept=True`, the stale value (+ swept_idx/swept_ts) leaks to
later empty-mask pools → wrong pools marked swept. Effect: a whole TF's liquidity pools silently
vanish → `liquidity_sweep` confluence factor scored as if no liquidity existed. Fix: `swept = False`
(+ reset swept_idx/swept_ts) at top of loop body; regression test with an all-unswept pool list.

**F2 (RISKY, CONFIRMED) — HTF-swing stop FALLBACK bypasses `stop_timeframes`.**
`risk_engine.py:1182-1214` (long) / `1359-1391` (short): the no-structure swing fallback gates only
on `overrides["htf_swing_allowed"]`, never on `stop_timeframes`. Cascade tiers are `copy.copy(config)`
so they inherit STEALTH's `overrides={"htf_swing_allowed":("4h","1h")}` (scanner_modes.py:363).
An intraday tier (`stop_timeframes=("1h","15m","5m")`, max_stop_atr 4.0) can therefore pull a **4h**
swing for its stop though 4h is not in its stop allowlist → wider-than-intended stop. The OB/FVG
stop path correctly honors `allowed_tfs`; only this fallback leaks. Backstopped (not fixed) by the
all-types max_stop_atr cap (risk_engine.py:1496). This is a SECOND wide-stop pathway alongside the
Tier 1.1 near_entry geometry (separate, already fixed via the reachability clamp 99303ff).

**F3 (RISKY, CONFIRMED) — intraday cascade tier resolves to the wrong PlannerConfig.**
`orchestrator.py:2891` sets `current_trade_type = cascade_allowed[0]` = "intraday";
`planner_service.py:216` calls `defaults_for_mode("intraday")` which falls into the DEFAULT/balanced
branch (`stop_use_htf_swings=True`, min_rr 2.0, stop_buffer_atr 1.0), NOT `intraday_aggressive`
(`stop_use_htf_swings=False`, min_rr 1.8) — planner_config.py:176 vs 235. The `stop_use_htf_swings=True`
is what ENABLES F2 on the intraday tier. Scalp tier unaffected ("scalp"→precision branch, htf swings off).

### 3_CORRECTNESS

**F4 (CONFIRMED) — `_calculate_targets` ignores `config.target_timeframes`.**
`risk_engine.py:2250-2255`: structural target TFs are hardcoded by `mode_profile` (overwatch→1w/1d,
stealth→1d/4h, else 4h/1h); `target_timeframes` is never read. Swing cascade tier sets
`target_timeframes=("1d","4h","1h","15m")` but only ("1d","4h") is used by swing/EQH/BOS/Fib finders.
Partial mitigation: orchestrator pre-filters FVG targets to allowed_target (orchestrator.py:2873),
so FVG magnets are constrained — swing/liquidity/BOS/Fib finders are not.

**F5 (CONFIRMED) — fixed bar-counts not TF-scaled.**
(a) `consolidation_detector.py:19-22,52`: min_duration_candles=10 / window_size fixed → 10 bars =
50min on 5m vs 40h on 4h. No `scale_lookback`. (b) `smc_service.py:490-494`: structural-OB swing
lookback uses raw `structure_swing_lookback` with NO scale_lookback, unlike OB/sweep/eqhl/HTF-swing
which all scale. 5m has no per-TF override → falls to base 7, unscaled.

### 4_FRICTION

**F6 (CONFIRMED/SUSPECT).** (a) Short-TF detector skips (swing_structure.py:88-92,
liquidity_sweeps.py:135-144, indicator_service.py:106-110) degrade to empty with only debug/warning
logs → a too-short TF is indistinguishable downstream from a genuinely clean one (erodes §11
observability). (b) Three `_infer_timeframe` impls (swing_structure.py:354, bos_choch.py:765,
fvg.py:526) return mixed case ("4H","1D" but "5m","15m") — currently safe only because config dicts
carry both cases; a future single-case lookup would silently drop a TF. (c) fvg.py:193-201 bearish
path missing the bullish path's overlap diagnostic log (diagnostic asymmetry, not detection).

## Confirmed GOOD (no action)
- ATR per-TF in every detector (no cross-TF ATR leakage).
- `scale_lookback` applied in OB / sweep / eqhl / HTF-swing detectors.
- Swing-structure HTF gating (1w/1d/4h) correct.
- Cascade rebuilds per-tier TF context + re-filters snapshot + re-runs pre-scoring gates per scale.
- HTF/LTF role separation: htf_trend regime-derived (intermediate-4h for scalp/intraday), LTF OB/FVG
  drives entry; no leakage either direction.
- max_stop_atr now caps ALL stop types (risk_engine.py:1496).
- Hot-path #8 (orchestrator.py:4705 worker regime sync) + #9 (scorer.py:2526 swing_htf_trend local,
  regression test exists) FIXED.

## Recommended triage / fix order (each gated: symmetry-guard + backend-integrity + §16 audit)
1. **F1** — `swept` init (one-line + regression). Smallest, highest silent-impact (liquidity factor).
2. **F3 → F2** — route intraday cascade tier to intraday_aggressive (or pass tier profile into
   defaults_for_mode); gate the HTF-swing stop fallback on `stop_timeframes ∩ htf_swing_allowed`.
   Closes the second wide-stop pathway.
3. **F4** — make `_calculate_targets` consume `config.target_timeframes` for structural finders.
4. **F5 / F6** — TF-scale consolidation + structural-OB lookback; convert silent skips to reason
   codes; unify `_infer_timeframe` to one canonical-case impl.

All observable via existing logs (`📐 WIDE STOP`, `🔍 TRADE TYPE DERIVATION`). No code changed.
