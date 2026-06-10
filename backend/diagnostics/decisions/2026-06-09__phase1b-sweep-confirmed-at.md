# 2026-06-09 — Phase 1B: LiquiditySweep.confirmed_at (look-ahead-safe sweep time)

Operator decision #6 (LOCKED): add `confirmed_at` to LiquiditySweep.

## Why
A sweep's `timestamp` is WHEN price penetrated the level; the sweep is only CONFIRMED once
its reversal completes — `reversal_bar_count` bars later. Any replay/backtest entry simulation
that treats a sweep as actionable at `timestamp` uses the completed-reversal information before
it existed → look-ahead bias. `confirmed_at = timestamp + reversal_bar_count * bar_duration` is
the earliest look-ahead-safe time the sweep is actionable.

## Changes
- `shared/models/smc.py` — `confirmed_at: Optional[datetime] = None` on LiquiditySweep (optional,
  last position, backward-compatible).
- `strategy/smc/liquidity_sweeps.py` — `_confirmed_at()` helper (direction-agnostic) +
  `bar_duration` (median df.index spacing) + populated at BOTH construction sites (high + low),
  byte-identical.
- `tests/unit/test_sweep_confirmed_at.py` — helper formula + bars==0 edge + never-precedes-timestamp;
  backward-compat default; detection populates both sweep_types; look-ahead-block invariant. 7 passed.

## IMPORTANT scope finding (Rubric 9): the consumer-redirect sub-task has NO TARGET
The task said "replay/backtest consumers must act on confirmed_at, never timestamp." Verified +
backend-integrity confirmed: **no sweep-triggered entry simulation exists** —
`backtest_engine.py` has zero sweep references; `replay.py`/`replay_engine.py` only serialize
sweeps generically (no entry gate); the live `entry_engine.py:302` reads `.timestamp` but is
explicitly OUT of 1B scope (verified-correct, do-not-touch). So `confirmed_at` lands as a
forward-looking schema SEED for a future entry gate, not a redirect of existing code. NOT a
missed consumer — correct scope.

## Notes
- `replay_engine.py:350` serializes sweeps via `__dict__`, so `confirmed_at` now rides along as
  an additive payload key (datetime coerced). Non-breaking; consumers read by key.
- Contract diff CLEAN (LiquiditySweep is not a tracked contract surface — nested in
  SMCSnapshot.liquidity_sweeps; the dataclass field LIST is tracked, not nested member fields).
  pipeline_smoke CLEAN.

## Pre-existing issue flagged, NOT fixed (out of 1B scope)
`tests/fixtures/smc_patterns.py:136` constructs LiquiditySweep with fields that no longer exist
(direction, swept_level, wick_high/low, candle_index, sweep_strength, liquidity_type,
follow_through) — would TypeError if called; only caller is `test_orchestrator_workflow.py.skip`
(disabled). Pre-existing drift, #4 FRICTION. Candidate for repo-janitor / a future cleanup pass.

## Gate results
- symmetry-guard: PASS (high/low mirror-identical; confirmed_at >= timestamp invariant proven).
- backend-integrity: CLEAN (contract diff exit 0, pipeline_smoke clean, additive-safe, no redirect target).
- §16 audit: 14/14 ✅, 0 🟡, 0 ❌.
