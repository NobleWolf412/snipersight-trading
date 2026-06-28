# §15 — trade-type-aware TP1 reachable ceiling (2026-06-28)

Operator-signed-off threshold change (CLAUDE.md §15: tuned threshold on the shared paper/live
planner path requires documented baseline + reasoning + sign-off). This is the deferred **Stage 2 /
Lever A** from `2026-06-02__fix-design__reachability-clamp-overdecline.md`, scoped per-trade-type.

## The binding constraint (measured)
Full heart-change stack, overnight paper (down_normal tape): **67 thesis signals generated, 0
converted** — ALL declined `tp1_unreachable`. Telemetry:
`stop 1.88–3.53 ATR → a 1.00R target exceeds reachable ceiling 1.30 ATR`.

Root: `tp1_reachable_ceiling_atr = 1.3` was a SINGLE value for all trade types (`planner_config.py`).
Decline boundary = ceiling ÷ `target_min_rr_after_clip` = 1.30 ÷ 1.0 = **1.30 ATR** — any stop wider
than 1.30 declines. The 1.30 was tuned for SCALP (anti-stagnation). But chunk 5b's regime→type
selector routes down-trends → **intraday** (rank 2 > scalp), and intraday carries wide structural
stops (1.9–3.5 ATR, genuine structure in chop, within the intraday max_stop_atr=4.0 scale bound).
So 5b sends trades exactly where the scalp-calibrated ceiling kills them. (Stage 1 / Lever B —
`target_min_rr_after_clip` 1.2→1.0 — already shipped; 67/0 is the under-recovery evidence Stage 2
was gated on.)

## Baseline (the §15 data — `stop_reachability_baseline` + per-type journal MFE, n=358 historical)
MFE = max favorable excursion = the reachable-TP1 distance the market actually offered.

| type | n | med stop ATR | med MFE | **p75 MFE** |
|---|---|---|---|---|
| scalp | 279 | 0.65 | 0.57 | **1.01** |
| intraday | 30 | 1.38 | 0.93 | **2.18** |
| swing | 49 | 1.93 | 1.31 | **3.02** |

Confirms the principle: intraday reaches ~2× as far as scalp. The single 1.30 ceiling is the
over-decline. Scalp 1.30 is already ≈ p75 scalp MFE (keep). Intraday/​swing ceilings set to ≈ their
p75 MFE.

## Change
`PlannerConfig.defaults_for_mode` now sets `tp1_reachable_ceiling_atr` per type:
- **scalp** (`scalp`/`precision`): **1.30** (inherits the dataclass default — UNCHANGED; preserves
  the anti-stagnation it was tuned for).
- **intraday family** (`strike`/`intraday_aggressive` AND the `else` branch where the cascade
  `intraday_cascade` scale resolves): **2.0** (≈ p75 intraday MFE 2.18). New decline boundary 2.0
  ATR — recovers the 1.88–1.98 ATR cohort (admit at ~1R), still declines the genuinely-too-wide tail
  (2.27, 3.53 — TP1 above p75, rarely hit).
- **swing** (`swing`/`overwatch`): **3.0** (≈ p75 swing MFE 3.02; swing is deferred in 5b, set for
  completeness).
- `target_min_rr_after_clip` UNCHANGED at 1.0 (do NOT lower — at a 3.53-ATR stop it would admit a
  0.37R target that can't pay fees, the original stagnation bug).

## Honest caveat — shipped as a BOUNDED PROBE, not open-ended (adversarial-review CHALLENGE addressed)
adversarial-review challenged 2.0 hard and it was right on the mechanics: 2.0 is the **p75** of the
intraday MFE, and that MFE distribution is **wide-stop-era contaminated** (those big excursions exist
*because* targets were far; clamp TP1 and the tail that produced p75=2.18 shrinks). So a clamped TP1
at ~2.0 ATR on a ~1.9-ATR stop is, on the cited distribution, hit <25% of the time — re-opening the
exact targets_hit-collapse (stagnation / wide-stop round-trip; trailing stop at 1.5R can't engage
below it) that the 1.3 ceiling was created to prevent. Median intraday MFE is only 0.93 ATR.

Operator decision (2026-06-28): ship 2.0 as a **ONE-SESSION PROBE with a hard KILL-CRITERION**, NOT
"validate forward":
- **KILL-CRITERION:** revert intraday ceiling to 1.5 (or pursue the stop-side root fix) if, after a
  session with intraday fills, intraday `targets_hit` rate lands **below ~0.20** (mirrors the
  2026-05-30 revert bar). The probe's purpose is to GENERATE the intraday data we do not have
  (n=30, contaminated) — with a bounded downside.
- **DURABLE FIX (follow-up):** the root the 2026-05-30 doc named is **stop-side coherence** — the
  1.9–3.5 ATR structural stops are the disease; a wider target ceiling is the symptom. Queued.

## Thesis-mode resolution note (backend-integrity correction)
In THESIS mode, chunk 5b's `_build_cascade_config` overwrites `allowed_trade_types=("intraday",
"scalp")` for BOTH cascade scales, and the ceiling resolves from `current_trade_type =
allowed_trade_types[0] = "intraday"` (orchestrator.py:3076). So in thesis mode **BOTH cascade scales
(scalp + intraday) resolve to the intraday 2.0 ceiling** — the per-type 1.3-scalp value only takes
effect in LEGACY mode. This is acceptable: the ceiling only BINDS on stops wider than it, and genuine
scalps carry tight (~0.65 ATR) stops the 2.0 ceiling never touches; it only changes behavior for the
WIDE-stop cohort, which is exactly the probe's target. The kill-criterion covers it.

## Blast radius / verification
Shared paper+live planner (no separate live planner) → changes live too (desirable; same
over-decline). Regression: `test_reachability_decline_boundary.py` updated for the per-type
boundary. Gates: symmetry-guard (the ceiling/clamp is direction-agnostic — fires on rung i==0 before
the bull/bear split) + backend-integrity + adversarial-review. Rollback: revert the three
`tp1_reachable_ceiling_atr` lines (default 1.3 restored everywhere).
