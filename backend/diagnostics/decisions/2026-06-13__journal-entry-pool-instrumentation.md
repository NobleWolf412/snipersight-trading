# 2026-06-13 — Journal entry-time liquidity-pool instrumentation (observability-only)

**Track:** EXIT/stop half of the loss problem — closes the DATA WALL the stop-pool agent
flagged (Phase 1 baseline + Phase 2 design, both 2026-06-13). **No scoring / gating / stop /
execution behavior changed.** Pure journal enrichment.

**Gate:** §20 backend-integrity (touches `backend/strategy/`, `backend/bot/`, and the tracked
`trade_journal.jsonl` db_contract) + §16 14-point + symmetry-guard (direction-aware logic).

---

## Problem (the wall)

`stop_in_pool_audit.py` (Phase 1) proved the thesis "stops land in/near SMC liquidity pools and
get swept" is **not testable from stored data**: the full pool set at entry is persisted
nowhere — not in `trade_journal.jsonl`, paper `signals.jsonl`, nor telemetry `signal_generated`.
So "stop landed in an undetected pool" and "nearest same-side pool distance" cannot be computed
post-hoc. Phase 2 (a4a7a69) revived the dead static PWL/PWH/PDH/PDL buffer branch but explicitly
deferred this instrumentation to "the journal thread."

## Root cause of the wall (traced, not assumed)

`key_levels` (`SMCSnapshot.key_levels = KeyLevels.to_dict()`, shape
`{pwl/pwh/pdh/pdl: {"price","swept"} | None}`) is read in `planner_service.py:330` **only** to
feed `_buffer_stop_from_liquidity`, then dropped. The orchestrator's `scan_with_heartbeat`
returns only `(trade_plans, rejection_summary)` — `key_levels` reaches **no** bot-layer consumer.
`TradePlan` has no `key_levels` field and `plan.metadata` did not carry it. So the bot literally
could not see the pools. Fixing this at the journal layer alone is impossible; the data must be
threaded out of the planner.

## Change (read-additive, three touch points)

1. **`planner_service.py` (~:330)** — one read-additive line: stash the already-computed `_kl`
   dict onto `plan.metadata["entry_key_levels"]` (guarded `isinstance(plan.metadata, dict)`,
   stores `None` if `_kl` is not a dict). The dict is ALREADY computed here for the buffer call;
   we only also expose it. No scoring/stop/execution change.
2. **`paper_trading_service.py`**
   - `_nearest_same_side_pool(key_levels, entry_ref, direction, atr)` + `_pool_price_swept(node)`
     module-level helpers. Direction-aware + MIRROR-symmetric (standing fix): LONG → pools below
     entry (`pwl`/`pdl`), SHORT → above (`pwh`/`pdh`) — the SAME `_attrs` + side guards
     `_buffer_stop_from_liquidity` uses, so the journal distance is on the buffer's basis.
     Distance in ATR. `swept` flag REPORTED (not filtered). All-None on missing/malformed/atr≤0;
     never raises.
   - `CompletedTrade` gains 5 nullable fields + emits them in `to_dict()`: `entry_key_levels`,
     `nearest_same_side_pool_{dist_atr,label,price,swept}`.
   - `_process_signal` (after `open_position`): computes the snapshot off `fill.price` +
     `plan.metadata["atr"]` + `entry_key_levels`, stashes it on the live `PositionState` via
     `setattr`. **Loud WARNING + null persist** if `entry_key_levels` is absent/malformed
     (never silent). Wrapped so capture can never block/crash the trade.
   - `_sync_closed_positions`: reads the stashed attrs via `getattr(pos, …, None)` into the
     `CompletedTrade`.
3. **Regression test** `backend/tests/unit/test_entry_pool_journal_instrumentation.py` — LONG vs
   SHORT mirror selection, wrong-side rejection (both dirs), no-pool→None (both dirs), swept
   surfaced, ATR scaling, malformed/empty/None guard (parametrized), and two synthetic
   `CompletedTrade.to_dict()` round-trips (keys land / null-safe + JSON-serializable). 18 pass.

## Honesty / scope caveats (flagged loud, per adversarial review)

- **`entry_key_levels` is the STATIC pool set only (pwl/pwh/pdh/pdl).** `KeyLevels.to_dict()`
  does NOT include EQH/EQL — those come from the separate `_find_eqh_eql_zones` multi_tf scan
  inside `_buffer_stop_from_liquidity` and are NOT in this dict. The buffer-fire rationale string
  (`"Buffered 0.3 ATR from liquidity pool @ <level>"`, already in the journal) still records the
  EQH/EQL pool that actually fired. So the audit reads BOTH: `entry_key_levels` (static prior-
  week/day pools the dead branch now also buffers) AND the rationale (EQH/EQL). The field name is
  honest about its source (`SMCSnapshot.key_levels`); the limitation is documented in the
  `CompletedTrade` field docstring and the helper docstring.
- **`swept` is reported, not filtered.** `nearest_same_side_pool_swept` lets the audit
  distinguish spent liquidity; distance is still computed regardless of swept-status (matches the
  buffer, which also ignores `swept` — filtering would be a behavior change, deferred).
- **`_save_state` asdict caveat.** The crash-recovery checkpoint does `dataclasses.asdict(pos)`,
  which enumerates only DECLARED `PositionState` fields — the `setattr` pool attrs are therefore
  ABSENT from `state.json`. Consequence: a position still OPEN at a crash loses its pool context
  on restore; a cleanly-closed position keeps it (the close path reads the live object).
  Acceptable for a close-path observability field (recomputable at open). Declaring the fields on
  `PositionState` would fix it but that dataclass is out-of-bounds for this thread; flagged to the
  operator for a future declared-field migration if recovery-path fidelity is wanted.

## §20 contract re-baseline (trade_journal.jsonl is a tracked db_contract)

`backend/diagnostics/contracts/db_contracts.json` sniffs the **first line** of the canonical
`backend/cache/trade_journal.jsonl` (gitignored runtime data; per-session `logs/` files are
excluded). That baseline first line was a STALE 2026-05-21 record carrying only **25 keys** —
already **~11 keys behind** what `CompletedTrade.to_dict()` has emitted since (realized_rr,
stop_loss_level, target_levels, stop_loss_rationale, tp1_clamped, tp1_realized_rr, execution_mode,
final_targets_remaining, targets_stripped_count, btc/alt_velocity_1h_at_entry, macro_state_at_entry,
regime_trend_at_entry, htf_aligned_at_entry, setup_qualifier). The contract had been blind to that
drift because the fixture line was never refreshed.

**Re-baseline action:** regenerated the canonical fixture's first line from the CURRENT
`to_dict()` (45 keys incl. `session_id`) and re-ran `capture_contracts capture`. The re-baseline
therefore registers, in one move: the **~11 pre-existing untracked keys** PLUS the **5 new pool
keys** (`entry_key_levels`, `nearest_same_side_pool_{dist_atr,label,price,swept}`). This is
enumerated here (not silent) so "diff clean" does not certify a hidden jump.

Downstream consumers confirmed SAFE for additive keys (Explore sweep, 20 consumers): all read via
`dict.get(...)` with defaults — `backend/bot/trade_journal.py`, `diagnostics/*` (session_debrief,
stop_in_pool_audit, direction_cohort, edge_significance, autopsy_report, entry_rr_distortion,
fill_rate, taken_trade_forensics, factor_contribution, …), `ml/signal_dataset_builder.py`, the
FastAPI `/api/trades/journal` route (delegates to TradeJournalService), and the React frontend
(non-strict JSON→TS). No consumer uses `extra=forbid` / fixed-schema parse. CSV export
(`DictWriter`) picks up new columns automatically.

## VERIFY-NEXT (post-deploy, operator-run after hard restart)

This worktree cannot run a live session (deployed backend runs elsewhere; per
`[[feedback_bot_hard_restart_required]]` the bot-service parent is long-lived/stale). Verified
here: 18 unit tests, synthetic `to_dict()` round-trip, contract re-baseline + clean diff,
`pipeline_smoke`. **After the next HARD-RESTART + fresh paper session:**
1. Confirm closed-trade rows in `trade_journal.jsonl` carry `entry_key_levels` (non-null on
   symbols with prior-week/day levels) + `nearest_same_side_pool_*`.
2. Re-run `python -m backend.diagnostics.stop_in_pool_audit` — its LIMITATION #1 ("full pool set
   at entry persisted nowhere") should now be closable; the nearest-same-side distance is readable
   per trade. True sweep-reduction verdict still needs ≥30 setups / ≥2 regimes (Phase-1 power
   floor) and post-stop OHLCV replay (separate gap, unchanged).
