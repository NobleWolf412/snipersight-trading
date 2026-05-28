# Quality-aware direction selection — DIRECTION-SHORT-CIRCUIT fix

## Headline
Direction selection at [orchestrator.py:1690](backend/engine/orchestrator.py#L1690)
previously used raw OB/BOS COUNT majority. Symbols with stacked bullish-count
structure but higher-quality bearish primitives (INJ today, SOL yesterday)
got LONG-evaluated despite quality decisively favoring SHORT. New override
compares per-direction aggregate quality (OB+FVG+Sweep+MS) and flips when
delta > 20pt AND quality direction opposes count direction. Gated per-mode
via `ScannerMode.enable_quality_override` — STEALTH=True (where calibration
data exists), other modes False until baseline data accrues.

## Context
- Calibrated on session 2f35590b (2026-05-27, 14h 51m, 32 trades):
  - 18 LONG trades = -$759.56
  - 14 SHORT trades = **+$220.81 profitable**
  - Universe-wide direction skew: 5,273 LONG vs 1,354 SHORT (3.89:1)
  - Biggest single loss: INJ #27 LONG -$124.32, fired when quality favored SHORT
- /confluence-trace on INJ/USDT exposed the count-vs-quality mismatch:
  - 10 OBs (8 bullish / 2 bearish) → count picks LONG
  - Per-direction aggregate quality: SHORT=230pt, LONG=146pt, delta=84pt
  - The 2 bearish OBs are grade A/B / fresh / displaced; 8 bullish ones are
    weaker grade C
- The same DIRECTION-SHORT-CIRCUIT pattern was diagnosed on SOL/USDT 2026-05-26
- Plan agent risk register surfaced 2 risks; both addressed in this commit
  (HTF-discount replication + per-mode kill switch)

## Resolution
- Added `Orchestrator._aggregate_direction_quality(snap, direction)` —
  pure static method computing OB+FVG+Sweep+MS factor scores per direction.
  Replicates the HTF-trend sweep discount from [scorer.py:2520-2536](backend/strategy/confluence/scorer.py#L2520)
  so the override doesn't spuriously favor SHORT against a bullish HTF.
- Added `Orchestrator._apply_quality_override(snap, pre_dir, pre_dir_tie_break, threshold=20.0)`
  static method — returns `(final_direction, final_tie_break, override_meta_or_None)`.
  Strict greater-than threshold; exact-20 defers to count (test #4 protects boundary).
- Wired into the call site at [orchestrator.py:1690](backend/engine/orchestrator.py#L1690)
  inside the `if not _pre_dir` block, AFTER `_derive_pre_direction` but
  BEFORE `run_pre_scoring_gates`. Gated by `self.scanner_mode.enable_quality_override`.
- Added `ScannerMode.enable_quality_override: bool = False` field; STEALTH
  config sets True. Other modes default False per §15 (no baseline data yet).
- New tie_break enum value `"quality_override"`. Flows through existing
  telemetry: `pre_dir_tie_break` field, `signal_generated` event, journal,
  taken_trade_forensics. No schema change — value is opaque string.
- Mass-conservation runtime assertion (§16 rubric 3): exactly ONE of
  three resolution paths owns the tie_break — {strict-majority, regime
  tie-break, quality_override}. Assertion fires loudly if violated.
- New `context.metadata["quality_override"]` dict published when override
  fires, carrying {from, to, quality_long, quality_short, delta, threshold}
  for downstream telemetry / autopsy queries.

## Tests
- `backend/tests/unit/test_quality_aware_direction_override.py` — 15 tests:
  - Scenarios 1-2: positive (Δ > 20 AND opposite → override); paired LONG↔SHORT
  - Scenarios 3-4: negative (Δ below threshold OR exactly at boundary → defer); paired
  - Scenarios 5-6: negative (Δ > 20 but same direction → no-op; zero quality → no-op)
  - Scenario 7: INJ regression fixture — calibration sample MUST flip
  - Static source-grep: orchestrator.py must contain `_apply_quality_override`,
    `_aggregate_direction_quality`, `enable_quality_override`, mass-conservation
    assert, `"quality_override"` literal
  - ScannerMode config: stealth must have True; others must have False
- All 34 tests pass (15 new + 19 existing pre-direction tests untouched)
- §16 rubric 12 (bull/bear symmetry): every test runs paired LONG↔SHORT

## Validation diagnostic
- `backend/diagnostics/direction_selection_audit.py` — runs OLD vs NEW
  selector on live SMC data for the 2026-05-27 known-problem symbols.
- Live run on 2026-05-27 confirms:
  - INJ/USDT: FLIPPED LONG → SHORT (Δ=+84.2, calibration fixture passes)
  - OP/USDT: FLIPPED LONG → SHORT (Δ=+31.9 — also saves the -$116 intraday pattern)
  - SOL/USDT: SHORT → SHORT (already correct via count, quality agrees)
  - ARB/USDT: LONG → LONG (Δ=-15.4 below threshold, correctly defers)
  - APT/USDT: SHORT → SHORT (no change, agreement)
  - BTC/USDT: SHORT → SHORT (control, no change)
- Strict-mode regression assertion passes (`PASS: INJ/USDT correctly
  flipped LONG -> SHORT`)

## Why it matters next time
- The bot's direction-selection is now grade-aware, not just count-aware.
  Symbols with stacked bullish-count structure but higher-quality bearish
  primitives will get SHORT-evaluated. Counter-cyclical alts in risk-off
  macros are the prime use case.
- Behavioral impact estimate from today's data: 2 of 6 audit symbols flip
  to SHORT (INJ + OP). If extrapolated to today's losing pattern: INJ #27
  -$124, OP #9 -$116, and possibly DOGE/INJ #2/INJ #15 retrace into
  SHORT-tier signals. Could have saved ~$300-500 of today's $-538 loss.
- The 20pt threshold is operator-set, not data-derived. After 50+ trades
  with the override active, re-tune against the actual quality_delta
  distribution (per §15 — but with empirical justification).
- Counter-HTF Bounce setups will still fire in alignment with HTF on
  symbols where count and quality agree (most bull market continuations).
  The override only fires when count and quality genuinely disagree by
  margin — the discriminator the existing code lacked.
- Two other modes (OVERWATCH, STRIKE, SURGICAL) default to False. When
  calibration data exists for any of them, flip individually with a
  decisions log entry citing the baseline.

## Audit-caught critical interaction (round 1) — flip-retry guard

Both the §16 audit (Open Item #1) and the adversarial review (Risk #3)
independently caught a subtle interaction that would have silently
neutralized the override:

  1. Override picks SHORT (count was LONG, quality favored SHORT)
  2. Pre-scoring `conflict_density` gate rejects SHORT (the 8 bullish OBs
     that count favored are now "opposing" SHORT)
  3. The existing flip-retry at [orchestrator.py:1765](backend/engine/orchestrator.py#L1765)
     tries LONG (the original count-pick the override rejected)
  4. LONG passes (only 2 bearish OBs opposing) → `chosen_direction = LONG`
  5. `pre_dir_tie_break` still reads `"quality_override"` in metadata —
     contradictory state where telemetry says one thing, execution does another

Fix: guard the flip-retry block at orchestrator.py:1765 with
`context.metadata.get("pre_dir_tie_break") != "quality_override"`. When
the direction came via quality_override, accept the conflict_density
rejection — flipping back to the count-pick that quality REJECTED is
circular reasoning.

Static source-grep regression test (`test_orchestrator_skips_flip_retry_on_quality_override`)
prevents future refactors from removing the guard.

This was the single critical finding across all 4 audit gates and was
addressed before commit. Per §16: auditor track unblocks when open
item #1 is fixed with code + test + decisions-log note. All three
delivered.

## Caveats / open items
- Threshold 20pt is authored, not data-tuned. Plan called this out (Risk
  register entry #1 → carried over). Validate against next 50 Tier 2
  trades' quality_delta distribution; re-tune if skew is wrong.
- Cascade per-scale `_derive_cascade_direction` (orchestrator.py:3640) does
  NOT use the override. The override sets `_pre_dir` at session level but
  the cascade re-derives direction per scale with its own count tally,
  using `_session_direction` only as fallback on a per-scale tie. Surfaced
  by adversarial review (Risk #1, 2026-05-27). Means the override
  guarantees behavior at the session-gate layer; per-scale plan generation
  could still flip back if scalp-tier structure_tfs counts disagree.
  Acceptable for round 1 — the gate-level fix is the highest-leverage
  intervention. Cascade-level wiring deferred until empirical data shows
  the override is dying at scalp tier in practice.
- Adversarial review Risk #2 (threshold 20pt may be too low against
  single-factor 40pt OB-grade deltas): track in same threshold-recalibration
  follow-up.
- HTF-discount replication is a duplicated code path. Acceptable until
  the discount logic is extracted into a shared helper that both
  `calculate_confluence_score` and `_aggregate_direction_quality` can call.
  Mark as repo-janitor candidate.
- Symmetry-guard agent should confirm bull/bear paths are symmetric — the
  threshold is identical in both directions and the predicate uses `abs()`
  so the property is structural. Audit verifies this.
- The override does NOT touch the cascade per-scale planning path at
  [orchestrator.py:3563+](backend/engine/orchestrator.py#L3563) where
  `chosen_direction` is set per-scale. Each cascade tier already re-runs
  pre-scoring gates with its own scoped data; the override would need
  per-cascade-tier wiring to apply there. Out of scope for this commit;
  follow-up if cascade-tier direction issues surface.
- Pre/post deploy comparison: re-run `direction_selection_audit.py` after
  next 24h paper session and compare flip counts. If >5 flips per cycle
  is typical, threshold may be too low.
