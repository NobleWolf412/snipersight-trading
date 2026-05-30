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

## Next concrete step

Phase 1: run a paper session with the shipped diagnostics, then write the baseline table here.
Code does not start until that baseline is on record (§15).
