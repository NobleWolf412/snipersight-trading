# 2026-05-30 — Fix design: TP1 reachability (wide-stop × TP-ladder mismatch)

**Type:** §15/§17 design entry — plan on record BEFORE code (shared paper+live path).
**Status:** DESIGN ONLY — not implemented. Gated on baseline collection (see §Baseline).
**Root cause:** `2026-05-30__stop-distance-structure-collapse.md` (verified, instrumented).
**Triage:** #1 BROKEN — paper expectancy +7.21 → −10.08/trade.

## Problem (verified, not inferred)

Stops are placed at genuine structural invalidation (live trace: 9/10 `used_structure=True`),
but in compressed regimes those levels are far (median 1.07 ATR, max 2.83, 40% ≥1.5). The 1.5R
first-target ladder multiplies stop distance, so TP1 lands at 1.5×(stop) — 2.25–4.2 ATR — well
beyond the ~0.6-ATR median favorable excursion. Trades stall before TP1 and round-trip to the
wide stop. Wide stops also enlarge the loss when hit. One mismatch, both symptoms.

## The design tension (why a TP1 clamp ALONE is insufficient)

A target-side clamp floored at the admission R:R (`min_rr=1.0`, `target_min_rr_after_clip=1.2`)
can only pull TP1 down to ~1.0–1.2 × stop_distance. When the STOP itself is wide (e.g. 2.83 ATR
structural), TP1 at 1.0R = 2.83 ATR — **still unreachable.** So:

- For **capped/fallback stops (~1.5 ATR):** a TP1 clamp helps (1.5R→1.0R: TP1 2.25→1.5 ATR).
- For **wide-structural stops (2–3 ATR):** the clamp cannot help — the STOP is the problem.

Therefore the fix must be **two-sided**. A 2.83-ATR stop on a *scalp* is a trade-type/stop
mismatch: a scalp should have a tight stop near local structure; if the nearest valid
invalidation is far, the setup is not a scalp.

## Options considered

- **(A) Target-side clamp only** — REJECTED as sole fix: insufficient for wide-structural (above).
- **(B) Stop-side only** (tighten/regime-scale stop) — addresses wide-structural + shrinks losses,
  but a stop tighter than structural invalidation gets swept (the `[[stop-placement-pwl-proximity]]`
  concern). Risky alone.
- **(C) Trade-type / stop coherence gate** — when stop_distance ≫ the trade type's intended range
  (scalp/intraday/swing), either reclassify to a higher tier (the cascade already supports
  swing/intraday/scalp) or reject. Treats the mis-classification directly.
- **(D) Two-sided: (C) gate + (A) clamp residual.** RECOMMENDED.

## Recommended approach (D) — phased

**Phase 1 — observability + baseline (NO threshold change; partially shipped):**
- `WIDE STOP` diagnostic shipped (risk_engine.py, fires dist≥1.33 ATR) + TP1-reachability
  diagnostic. Run ≥1 full paper session; collect the joint distribution of
  {stop_branch, stop_distance_atr, tp1_distance_atr, trade_type, realized targets_hit, exit_reason}.
- Deliverable: a documented baseline table (good-window vs current) so any threshold in Phase 2/3
  is set from data, per §15. **Do not set clamp/gate constants before this lands.**

**Phase 2 — trade-type/stop coherence (C), stop side:**
- In `_calculate_stop_loss` (or the planner caller), when `stop_distance_atr` exceeds the trade
  type's intended max (cascade-config-driven, NOT a new magic number — use existing
  `max_stop_atr` per mode/tier), prefer the NEAREST valid structural invalidation before
  accepting a distant one; if none qualifies, let the cascade try a higher tier rather than
  planting a far stop on a scalp.
- §10: symmetric for long/short (stop selection is already mirrored; verified by symmetry-guard).

**Phase 3 — residual TP1 reachability clamp (A), target side:**
- In `_calculate_targets`, clamp the ladder `dist` at risk_engine.py:2413 (BEFORE the `is_bullish`
  split — symmetry-guard confirmed the only symmetry-safe point) to a reachability ceiling derived
  from the Phase-1 baseline, floored so TP1 R never drops below `target_min_rr_after_clip` (1.2).
- Re-derive further rungs as monotonic offsets from the clamped TP1.

## §17 surface (for the eventual code phases)

**Affected files:**
- `backend/strategy/planner/risk_engine.py` — `_calculate_stop_loss` (Phase 2), `_calculate_targets`
  L2413 (Phase 3). §20 trigger; shared paper+live.
- `backend/strategy/planner/planner_service.py` — sole caller (L406 targets; stop call earlier);
  metadata for diagnostics (additive keys, schema-stable).
- `backend/shared/config/scanner_modes.py` — only if a per-tier coherence bound is read (use
  existing `max_stop_atr`; do NOT add new threshold fields without baseline).
- Tests: extend `test_target_generation_near_entry.py` + a new stop-coherence test (paired L/S).

**Contracts:** additive `plan.metadata` keys only (tp1_planned_rr / tp1_realized_rr /
tp1_reachability_atr / tp1_clamped / stop_coherence_action). pipeline/telemetry/db diff must stay
clean (`/contract-check diff`). No signature change to `_calculate_targets`.

**Upstream:** `planner_service.py:406` (sole caller, unchanged signature).
**Downstream:** TradePlan, PositionState, position_manager (TP1-closer BENEFITS stagnation logic),
trade_journal, HUD — all read levels as values; value-shift only, schema stable.

**Same-diff diagnostic:** already partly shipped (WIDE STOP + TP1 reachability). Phase 2/3 add
the realized-vs-planned-R metric + a test asserting TP1 can't exceed the reachability ceiling and
the coherence gate fires when stop ≫ tier range.

## Risks / hard boundaries

- **§15:** clamp ceiling + any coherence bound are thresholds → MUST cite Phase-1 baseline data.
  `min_rr` / `target_min_rr_after_clip` / `min_confluence_score` NOT to be modified.
- **§10:** all geometry symmetric L/S; clamp on `dist` before the split; coherence gate mirrored.
- **Live path (§15):** risk_engine.py is shared paper+live → this design entry is the required
  record; each code phase needs symmetry-guard + backend-integrity + §16 audit before commit.
- **Stop-sweep risk:** Phase 2 must NOT tighten stops INSIDE structure (see
  `[[project_stop_placement_pwl_proximity]]`) — prefer nearest VALID invalidation, not arbitrary
  tightening.
- **R:R admission collapse:** clamp floored at `target_min_rr_after_clip` (1.2); if a clamp would
  push below, let the existing R:R gate reject — no silent sub-floor admission.
- **Revert criterion:** if win-rate degrades >10pp or targets_hit fails to recover above ~0.20 in
  the next paper session, revert.

## Phase 1 BASELINE — recorded 2026-05-31 (session 8e698270, 13h, n=37)

Extractor: `python -m backend.diagnostics.stop_reachability_baseline`.

| metric | this run (8e698270) | GOOD ref (<05-24) | degraded window (05-24..29) |
|---|---|---|---|
| n | 37 | 44 | 105 |
| win% | 54 | 70 | 37 |
| **avg win** | **+2.40** | **+11.37** | +19.44 |
| avg loss | −2.66 | −2.72 | −27.52 |
| payoff | 0.90 | 4.19 | 0.71 |
| expectancy/trade | **+0.08** | +7.21 | −10.08 |
| targets_hit | 0.14 | 0.34 | 0.13 |
| median stop ATR | **1.50** | 0.53 | 1.50 |

Stop-distance buckets (this run): structural<1.0 = 41%, ~1.5 fallback/cap = 32%, wide≥1.5 = 22%.
Exit mix: target 5, stagnation 10, direction_flip 9, stop_loss 7, session_stopped 6.
Raw stop_distance_atr: 12 trades pinned at exactly 1.50; tail to 3.72 ATR.

**Interpretation (confirms the design's mechanism):** losses are now controlled (−2.66 ≈ healthy
−2.72) — the calm market didn't trigger the wide stops. But wins collapsed to +2.40 (vs +11.37)
because targets are unreachable (0.14 hit; only 5/37 exited on target; 19 exited via
stagnation/flip — drifting trades closed small before reaching the far TP). Same wide-stop root as
the degraded window (median stop 1.50 ATR identical), different expression: breakeven-by-tiny-wins
in calm vs big-losses in chop. The 54% win rate shows direction selection is fine — the bot just
can't BANK a meaningful win.

Caveat: WIDE STOP diagnostic logged nothing this run (bot likely on pre-5617f36 code / log
rotated). Journal data is authoritative for this baseline regardless; ensure latest code on next run.

## Data-derived threshold targets (PROPOSALS — validate in Phase 2/3)

- Healthy TP1 was reachable at stop ≈0.53 ATR → TP1 @1.5R ≈ 0.8 ATR. Median favorable excursion
  ~0.6 ATR. So a reachable TP1 ceiling is ≈ **1.0–1.3 ATR** absolute.
- This run's TP1 @1.5R off a 1.50-ATR stop ≈ 2.25 ATR — ~2× the reachable ceiling.
- Implies BOTH levers needed: pull stops toward the ~0.5–0.8 ATR structural band where reachable
  (Phase 2 coherence — don't run a 1.5–3.7 ATR stop on a scalp), and clamp residual TP1 to the
  ~1.0–1.3 ATR ceiling floored at target_min_rr_after_clip=1.2 (Phase 3).

Baseline on record → Phase 2 code may proceed (with symmetry-guard + backend-integrity + §16 audit).

## Phase 2 design CORRECTED (2026-05-31, after reading `_calculate_stop_loss` 777-1503)

The original Phase 2 ("prefer nearest valid invalidation") was based on a WRONG assumption —
**the stop builder ALREADY picks the nearest structure**: L1085-1087 selects
`max(valid_stops, key=low)` = the closest invalidation below entry; structure-TF ATR
normalization (L1094-1136) already prevents HTF-ATR-mismatch rejections. A "prefer nearest"
change would be a no-op. (Caught by reading before coding — the discipline this session lacked
earlier.)

Verified selection chain (LONG; SHORT mirrored): consolidation-stop (if passed+quality) →
swing-mode (overwatch only) → OB/FVG below entry filtered to `allowed_tfs`, nearest chosen →
entry-OB edge → `_find_swing_level` (primary then HTF) → ATR fallback (1.5 scalp / 2.5 STEALTH).

So wide stops are LEGITIMATE outcomes, not misplacement:
- **wide-structural:** the nearest QUALIFYING OB/FVG (on the tier's `allowed_tfs`, below entry) is
  genuinely far — no closer invalidation exists on those TFs.
- **1.5/2.5 fallback:** NO qualifying structure on the tier's TFs → ATR fallback.

**Revised fix space (neither moves the stop → no sweep risk):**
- **(a) Adaptive R:R / reachability clamp** (target-side, Phase 3): on wide-stop trades, lower the
  first target's R:R toward the admission floor so it's reachable. Tradeoff: smaller R:R per trade
  (down to ~1:1) in exchange for a higher hit rate. §15 risk-appetite decision — OPERATOR call.
- **(b) Coherence decline gate** (planner/orchestrator): if even a min-R:R target off the computed
  stop exceeds the reachable ceiling for the tier, decline the trade (or let the cascade try a
  higher tier). Tradeoff: fewer trades, higher quality. Reduces volume — §15 behavior change.

Both depend on the same operator tradeoff (accept lower-R:R reachable trades vs take fewer trades).
Operator decision (2026-05-31): **BOTH — clamp if moderate, decline if extreme.**

## WIDE STOP branch attribution — 2026-05-31, fresh backend (n=1113 stop calcs ≥1.33 ATR)

Captured after restarting the backend onto current code (the prior baseline ran on stale
ProcessPool workers → no WIDE STOP logs). Extractor:
`python -m backend.diagnostics.stop_reachability_baseline`.

| branch | n | % | meaning |
|---|---|---|---|
| max-stop-cap | 467 | 42% | structure found but > max_stop_atr → capped to min(max_stop,1.5)=1.5 ATR (L1487-1501) |
| structural-wide | 427 | 38% | genuine far structural invalidation used as-is (to 3.98 ATR) |
| other | 157 | 14% | — |
| no-structure-fallback | 62 | 6% | no qualifying structure → ATR fallback (L1216-1240) |

**80% of wide stops = "structure found, but far"** (cap 42% + structural-wide 38%). The
no-structure ATR fallback is only 6% — earlier fallback-dominance hypotheses are quantitatively
refuted. The defect is NOT detection and NOT fallback; it is the fixed 1.5R target ladder applied
to a far (but legitimate) structural stop.

## Data-derived thresholds (§15 — now evidence-backed)

- **Reachable TP1 ceiling ≈ 1.3 ATR.** Good window: median stop 0.53 ATR → TP1@1.5R ≈ 0.8 ATR,
  targets_hit 0.34 (reachable). Median favorable excursion ~0.6 ATR. 1.3 ATR is a conservative
  (generous) ceiling above the proven-reachable 0.8.
- **min R:R floor = 1.0** (`min_rr`); `target_min_rr_after_clip` = 1.2.
- Therefore, with ceiling 1.3 ATR and floor 1.0R:
  - stop ≤ ~0.87 ATR → TP1@1.5R ≤ 1.3 → reachable, NO change (the healthy ~47% structural<1.0).
  - 0.87 < stop ≤ 1.3 ATR → CLAMP TP1 from 1.5R down to fit 1.3-ATR ceiling, R:R stays ≥ 1.0.
  - stop > 1.3 ATR → even a 1.0R target exceeds the ceiling → DECLINE (the cap'd-1.5 + structural-wide).

**Volume implication (material — flagged for operator):** in the traded sample ~27% (cap 1.5) +
~20% (wide) ≈ **~47% of trades would be DECLINED**. That is a large volume cut, justified by the
baseline (those wide-stop trades are the breakeven/loss cohort), but it IS a significant behavior
change. The 1.3-ATR ceiling is the dial controlling decline aggressiveness — raise it to decline
fewer (clamp more at lower R:R), lower it to decline more.

Operator selected ceiling: **1.3 ATR** (balanced).

## IMPLEMENTATION SPEC (mechanical — execute next)

Admission-gate reality (verified, planner_service.py:772-786): rejects when TP1 R:R <
`config.min_rr_ratio`. Per-mode: overwatch 2.0, strike 1.2, surgical 1.5, **STEALTH 1.5**. The
"after-clip" floor `target_min_rr_after_clip` (planner_config.py:115 = 1.2; scalp = 1.0) is
**DEAD** — only referenced in test_trade_type_aware.py, never wired into the gate. Because STEALTH
floor (1.5) == ladder TP1 (1.5R), a naive clamp has NO admit band → pure decline. "Both" therefore
REQUIRES wiring the after-clip floor for clamped targets.

Changes (3 files + tests):
1. **planner_config.py** — add field `tp1_reachable_ceiling_atr: float = 1.3` (NEW field — Rubric 9
   flag). Document §15 baseline (this doc).
2. **risk_engine.py `_calculate_targets`** — at the ladder TP1 rung (i==0), BEFORE the is_bullish
   split (symmetry-safe, the L2413 `dist` line):
   - `ceiling = planner_cfg.tp1_reachable_ceiling_atr * atr`
   - if `dist > ceiling`:
     - `clamped_rr = ceiling / max(risk_distance,1e-9)`
     - if `clamped_rr >= planner_cfg.target_min_rr_after_clip`: `dist = ceiling`; mark
       `targets[0]` clamped (set attr, mirror of stop_loss.structure_tf_used pattern).
     - else: signal DECLINE (stop too wide for a reachable target at the after-clip floor) — raise
       a dedicated `ReachabilityDecline` exception.
   - Symmetric: clamp `dist` once before the L/S branch; no per-direction divergence (§10).
3. **planner_service.py** —
   - wrap `_calculate_targets` call: catch `ReachabilityDecline` → `return None` (clean skip, like
     the entry-zone depth gate at L287-291) + `create_signal_rejected_event(reason="tp1_unreachable")`.
   - admission gate (L772-786): if `targets[0]` is reachability-clamped, use
     `config-resolved target_min_rr_after_clip` as the floor instead of `min_rr_ratio`. Wires the
     dead field for its documented purpose; normal targets still gated at `min_rr_ratio`.
4. **diagnostic/metadata:** plan.metadata additive `tp1_clamped`, `tp1_realized_rr`,
   `tp1_reachable_ceiling_atr`. WIDE STOP diagnostic already shipped.
5. **tests:** paired L/S clamp tests; decline test (stop > ceiling/after_clip → skip); admission
   gate admits clamped @ after-clip floor but rejects unclamped < min_rr_ratio; healthy tight-stop
   trade unaffected (no-op). Mass/symmetry per §16 R3/R12.

Gates each step: symmetry-guard (auto, scoring/planner) + backend-integrity (§20: risk_engine,
planner_service, telemetry event, plan.metadata) + §16 audit. Contract diff: new telemetry reason
+ metadata keys are additive (document downstream). Revert criterion in §Risks above.
