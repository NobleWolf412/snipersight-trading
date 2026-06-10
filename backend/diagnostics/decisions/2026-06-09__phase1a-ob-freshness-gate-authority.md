# 2026-06-09 — Phase 1A: OB freshness — Gate-2 single authority (T2)

Operator decision #3 (LOCKED): retire the dead Gate-1 freshness filter; `filter_obs_by_mode`
(Gate 2) becomes the single OB freshness authority; unknown/None `mode_profile` must FAIL LOUD.

## Root cause
Two freshness filters compared `freshness_score` (0–100; `calculate_freshness` returns `*100`)
against `ob_min_freshness` (0–1, i.e. 0.05). `freshness_score >= 0.05` is true for any OB above
~0.05% remaining → both filters were DEAD (expired nothing; only fired past ~10 half-lives).
Gate 2 (`filter_obs_by_mode`, thresholds 38/19/12 on 0–100 ≈ 2.5 half-lives) already did the
real expiry per-TF in the live path — it just wasn't the *sole* authority, and it silently
returned the pool unfiltered on a None/unknown profile.

## Changes
1. `order_blocks.py detect_order_blocks()` — removed dead `freshness_score >= min_freshness`
   clause; kept `mitigation_level < max_mitigation`.
2. `order_blocks.py filter_obs_by_mode()` — empty pool still returns []; None/empty profile and
   unknown profile now RAISE ValueError (was silent passthrough).
3. `smc_service.py` detect() aggregation (~:818) — removed a SECOND identical dead filter + its
   misleading "Filtered N stale OBs" log; KEPT the freshness recalc. (Scope expansion beyond the
   literal 1A spec, Rubric-9-flagged: decision #3's "single authority" is false while a second
   dead filter survives.)
4. `tests/unit/test_ob_freshness_gate_authority.py` — None/unknown raise, empty exempt, 4
   profiles accepted, ~2.5-HL expiry boundary, bull/bear symmetry (parametrized).

## Six-concern table (§16 Rubric 1)
| Change | Collision-free keys | Concurrency | Silent-failure | Retrieval | Diagnostic | Schema/symmetry |
|--------|--------------------|-------------|----------------|-----------|------------|-----------------|
| Gate-1 clause removal (order_blocks) | N/A (no keys) | N/A (pure list-comp) | IMPROVED — removed a no-op that masqueraded as expiry | OB pool unchanged (dead clause) | regression asserts no-op | direction-agnostic list-comp; symmetric |
| filter_obs_by_mode fail-loud | N/A | N/A | IMPROVED — silent passthrough → ValueError | empty pool still []; valid profiles unaffected | tests for None/unknown/4-profiles | direction-blind (no `direction` branch); symmetric |
| smc_service dead filter removal | N/A | retains try/except wrapper | IMPROVED — removed dead filter + misleading log; recalc kept | pool size unchanged (proven) | covered by no-op assertion | recalc direction-agnostic |

## Blast radius
- Pool size UNCHANGED (both removed filters provably dead). Contract diff CLEAN (exit 0),
  pipeline_smoke CLEAN, 7/7 new tests + 23/23 related pass.
- Fail-loud has ZERO live blast radius: only production caller `smc_service.py:554` passes
  `self._mode_profile = MODE_TO_PROFILE.get(self._mode, "stealth_balanced")` (smc_service.py:89,
  set once, never None/unknown). Diagnostic caller sources identically. Only None/unknown inputs
  in the repo are the regression test's intentional negatives.

## Gate results
- symmetry-guard: PASS (no standing fix regressed; bull/bear freshness symmetry at the root).
- backend-integrity: CLEAN (contract diff exit 0, pipeline_smoke clean, pool delta zero).
- §16 audit: 13/14 ✅, 0 ❌; the lone 🟡 (Rubric 1 six-concern table) closed by THIS table.

## Pre-existing issue noted, NOT fixed (out of 1A scope, no live trigger)
`smc_service.update_config()` (:98-102) mutates `self._mode` but does NOT recompute
`self._mode_profile` → a runtime mode switch via update_config leaves `_mode_profile` stale.
Latent; irrelevant to the fail-loud guard (`_mode_profile` stays at its non-None __init__ value).
Surface if/when runtime mode-switching is exercised.
