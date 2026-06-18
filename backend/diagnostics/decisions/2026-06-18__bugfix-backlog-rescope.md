# 2026-06-18 — §11.6 bug-fix backlog RESCOPE (3-agent scoping pass)

Updates `2026-06-16__regime-strategy-router-design.md` §11.6. A 3-agent scoping pass (deep-scope #2,
scope-ahead #3, adversarial review of the sequencing) changed the plan. Source-of-truth correction.

## #3 (FVG grade-after-TF-ATR) — CLOSED, ALREADY FIXED (phantom)
The doc cited `scorer.py:1023-1043` as grading FVGs with entry-TF ATR. WRONG against current code:
- FVG `grade`/`size_atr` are computed at DETECTION in `backend/strategy/smc/fvg.py:detect_fvgs`
  against that TF's OWN DataFrame ATR (`fvg.py:106,151-152,169-175,233-239`) — never entry-TF.
- The cited scorer block (`evaluate_htf_structural_proximity`) already looks up own-TF ATR via
  `_get_tf_indicators(indicators, fvg.timeframe)` (`scorer.py:~1027/1035`) — landed commit
  **2929a213 (2026-04-14)**, two months before the design doc. No fix needed.
- ACTION: mark §11.6 #3 done. Optional: a source-invariant guard test so it can't silently regress.
- SEPARATE latent finding (NOT #3): `scorer.py:~1024` does `fvg.timeframe not in structure_tfs`
  where `fvg.timeframe` is uppercase ("4H" from `_infer_timeframe`) and `structure_tfs` defaults
  lowercase ("4h") → case-sensitive membership can SILENTLY skip HTF FVGs. Verify the actual casing
  of `mode_config.structure_timeframes` per mode; if it bites, normalize both sides `.lower()`.

## #6 (regime ATR% bands vs TF) — REAL, but PRODUCTION-CLEAN; defer (needs per-TF bands)
`regime_detector.py:_detect_volatility` classifies on `_highest_duration_tf(by_timeframe)` (:700) with
bands "calibrated for the DAILY timeframe" (:750-758). Impact is MODE-dependent:
- **STEALTH (production): highest TF = `1d`** (timeframes `("1d","4h","1h","15m","5m")`) → daily ATR%
  on daily bands → **CORRECT.** The bug does NOT bite production, and the STEALTH trade-journal
  cohorts (+6.42/−1.06/−8.32) were labeled on daily — **NOT #6-contaminated.**
- OVERWATCH: has `1w` → weekly ATR% on daily bands → mislabels TOO VOLATILE.
- STRIKE / SURGICAL: top out at `4h`, NO daily present → 4h ATR% on daily bands → mislabels TOO
  COMPRESSED. There is no daily to "pin to" — these need 4h-calibrated (per-TF) bands.
- ACTION: DEFER. Real correctness gap for non-STEALTH modes, but it needs a per-TF band design
  (not a one-line pin), changes those modes' labels (live-behavior for them), and does NOT block #2.
  This **weakens the adversarial "do #6 before #2" objection** — production's label is already clean.

## #2 (P/D inverted in trends) — NEXT fundamental; ship as REGIME-BLIND BOS ARBITRATION
Confirmed bug: `scorer.py:~2873-2904` (`strategy/confluence/scorer.py`, NOT the doc's stale
`strategy/smc/` path). The P/D factor applies fade-the-extreme (mean-reversion) UNCONDITIONALLY and is
summed with the Market-Structure/BOS factor with NO arbitration. In a confirmed trend, a with-trend
entry gets the 30 penalty for being in the "wrong" zone (downtrend SHORT sits at discount → penalized;
uptrend LONG advancing into premium → penalized). The finding's only PROFITABLE cohort was the
BOS-continuation override (+1.71, 54% WR); P/D-favored was the WORST (38% WR, −212).

**Chosen design (adversarial-recommended): regime-BLIND.** When an aligned, HTF, direction-matching
BOS is present (structure = trend evidence, locally, no regime label needed), floor the P/D penalty
arm from 30 → 50 (NEUTRALIZE, do not reward). Avoids the suspect regime label entirely; matches §11.5
(edge is structure/sequence). Symmetric by construction (premium-in-downtrend short == discount-in-
uptrend long). Keep fade-the-extreme everywhere else (ranges unaffected).

**OPEN OPERATOR FORKS (live STEALTH scoring change → §15 approval + this entry required):**
1. Arbitration source: regime-BLIND BOS-only (recommended) vs regime+BOS vs regime-only.
2. Penalty when continuation: NEUTRALIZE →50 (recommended, conservative) vs REWARD →75 (stronger claim).
3. Scope: factor-only first (recommended) vs also condition the HTF gate −40 (`scorer.py:~1162-1169`,
   same blind spot, bigger lever, partially masks the factor fix if left).

**Live-behavior note:** `paper_trading_service.py:~2312-2338` reads `confidence_score` to GATE and
SIZE (full/half/skip). Raising P/D 30→50 on continuations lets more with-trend trades pass / size up
on the STEALTH paper path → NOT "just context." Needs symmetry-guard + backend-integrity + a regression
diagnostic (the existing `pd_direction_efficacy.py` is the forward-test) before commit.

## Revised order
#3 ✅closed · **#2 (BOS-blind) NEXT** (pending operator fork decisions) · #6 deferred (per-TF band
design) · #5 re-rank after #2 lands · #7 re-bucket+re-measure last.
