# 2026-05-29 — Hot-Path Robustness Audit (live trade path)

**Type:** Audit findings + methodology calibration (slipped-audit near-miss)
**Scope:** Live trade hot path — data → indicators/SMC → scoring/gates → planner → sizing → execution → fill/exit/reconcile.
**Method:** Multi-agent workflow — 10 finder dimensions → 3-lens adversarial verify (reachability/guard/impact, 2-of-3 to confirm) → synthesis.

---

## METHODOLOGY CALIBRATION — the false-negative that almost shipped

Run 1 of the workflow returned **0 confirmed / "clean round."** This was a **false negative**: every one of the ~63 verifier subagents was forced to emit a `StructuredOutput` schema and all failed it (`completed without calling StructuredOutput`). Failed agents resolve to `null`; `votes.filter(Boolean)` → empty; `realCount >= 2` → false for every finding. The synthesis agent received an empty confirmed-list and faithfully reported "clean."

**Lesson (apply going forward):** Do NOT force `StructuredOutput` schema on reasoning-heavy adversarial verifier agents — they end the turn in prose and the schema-retry fails silently, inverting into false confidence. Use a parseable sentinel (`VERDICT: REAL|REFUTED — …`) parsed in JS, and **bucket "insufficient valid votes" as UNVERIFIED, never as refuted.** A dead verifier must never be able to masquerade as a refutation. This is the §11 "loud failures over silent skips" rule applied to the audit harness itself.

Run 2 (sentinel + UNVERIFIED bucket): **13 CONFIRMED, 0 UNVERIFIED, 17 REFUTED.** Same code, same cached finders — only the verification layer changed.

---

## CONFIRMED BUGS (13)

### 1_BROKEN — money at risk / stranded positions
1. `position_manager.py:1354-1377` — `_execute_exit` discards the executor success bool, falls through to `return True`. Rejected reduce-only exit → PositionState settled CLOSED/STOPPED_OUT, dropped from monitoring, native stop already cancelled → **live position stranded naked**. `_execute_partial_exit` (1379) has the identical defect (books realized_pnl on a failed partial).
2. `live_trading_service.py:909-915` — pending limit entry fills while `active_count >= max_positions` (cap gate at 1192 ignores `_pending_plans`) → code `cancel_order`s an already-FILLED order (no-op, returns False at `live_executor.py:565`), pops the plan; `open_position`/`_place_exchange_stop` never run → **filled position with no software monitoring** until next `_startup_reconcile`.
3. `orchestrator.py:3684-3702, 3762-3774, 2907-2922` — cascade per-scale direction flip writes `metadata['chosen_direction']` but `_generate_trade_plan` passes the unchanged session-level `confluence_breakdown` → plan emits SHORT carrying the LONG confidence/breakdown; wrong-dir score ranks the candidate and persists to the live signal. **Bull/bear symmetry break.** (Geometry-is-wrong sub-claim was refuted; entry/stop are direction-correct.)
4. `phemex.py:221-234` — Direct-REST fallback guesses scale `1e8 if rows[0][1] > 1e6 else 1.0`; sub-$0.01 coins stay unscaled → 1e8× prices into sizing/liquidation. **Confirmed 2-1** — guard lens says the 15% independent-ticker drift gate (`defaults.py:72`, `ohlcv_cache.py:285`) should reject it; mitigant to verify on the same-cycle cache-miss path.

### 2_RISKY — silent failure / lost diagnosability (CLAUDE.md hard-boundary class)
5. `indicator_service.py:297-361` — all `_safe_compute_*` failures `logger.debug` + `return None`; prod uvicorn runs `log_level=info` → invisible; broken indicator scored neutral and weight-redistributed so it still clears `min_confluence_score`.
6. `smc_service.py:692-693` — bare `except: pass` zeroes equal-highs/lows + liquidity pools for a TF; no log, no `smc_rejections` entry.
7. `live_executor.py:239-248` — leverage-mismatch reject sets no `rejection_reason`; caller persists bare "REJECTED" → reason destroyed on the JSONL autopsy record. (Metadata sev 4, but the "destroy a rejection reason" hard-boundary class.)

### 3_CORRECTNESS — wrong signals, no crash/strand
8. `orchestrator.py:4862-4865 / 1360` — worker `current_regime` always None → `metadata['global_regime']` None every symbol → HTF-alignment +5/+2 bonus dead, `is_ranging` permanently False. **OVERLAPS prior gap A** (current_regime in worker); localizes the two scoring consequences.
9. `scorer.py:2524-2536` — `htf_trend` param reassigned inside the sweep-discount block to the swing-structure trend, then read at 2803 → HTF Alignment sub-score sourced from swing structure, not regime.
10. `risk_engine.py:73-77` — opposing-OB target filter uses `> 0.5` against 0-100 freshness (`order_blocks.py:649`) → ~always-true, over-blocks valid TPs, biases R:R down. Sibling checks use the correct 0-100 threshold.
11. `entry_engine.py:459-468` — nested-entry score mixes 0.7 default + 0-100 freshness with 0-1 mitigation/width terms → freshness swamps ~100×; picks worse entry zone.
12. `indicators.py:143-147` — flat-price (std==0) Bollinger raises in `__post_init__`, TF dropped (warning only); STEALTH critical-TF gate checks raw OHLCV not the IndicatorSet → scan proceeds on partial set and awards 100.0 to the HTF structural-proximity gate (`scorer.py:2844`).
13. `orchestrator.py:3351-3367` — post-plan ATR-drift gate: `plan.metadata['atr']` never set (planner writes `diagnostics['atr']` at 243) → `drift_atr` forced 0.0 → `> 3.0` check dead. **Confirmed 2-1** — impact lens names the ±1.5% stale-entry reject (`live_trading_service.py:1320-1329`) as backstop; verify a low-vol multi-ATR-but-<1.5% move can't slip.

---

## SYSTEMIC CLUSTERS
- **(I) ProcessPool / async lifecycle state** — #2, #3, #8 + cooldown gap B. State in main-process / `_pending_plans` not propagated to workers or the position lifecycle. Highest leverage: a state-propagation contract fix touches four findings.
- **(II) Fail-silent not fail-loud** — #1, #5, #6, #7. All §11 violations; #1 strands capital, rest destroy diagnosability.
- **(III) 0-1 vs 0-100 scale-unit confusion** — #4, #10, #11. Localized drift (siblings correct), not a shared helper; argues for a unit-check lint on new freshness/scale comparisons.
- HTF Composite is corrupted from three directions: #8 (None regime), #9 (clobbered htf_trend), #12 (flat-BB perfect-100).

## STILL OPEN (not in this candidate set — carried from gap analysis, NOT cleared)
- Cooldown dict forked-at-spawn (`cooldown_manager.py:110`) — gap B
- `trailing_stop` toggle dead backend-side — gap C
- Exchange SL qty not resized post-TP1 — gap D
- No TP reachability clamp (`risk_engine.py:2470-2495`) — see [[project_longbook_degradation_fix]]
- Stops at raw liquidity extremes, no PWL/PDH/EQL offset — see [[project_stop_placement_pwl_proximity]]; research (Osler 2005) corroborates.

## HARD-BOUNDARY NOTE FOR FIXES
Fixes to #1, #2 (and reconciliation around #3, #4) touch the **live execution path** (`position_manager.py`, `live_trading_service.py`, `live_executor.py`). Per CLAUDE.md §15: **no live-trading code path touched without explicit approval / a documented design entry.** Each of these needs its own design entry + same-diff regression diagnostic before code lands.

## RECOMMENDED FIX ORDER
Strict triage: #1 → #2 → #3 → #4 (BROKEN), then #5/#6/#7 (RISKY), then #8-#13 (CORRECTNESS). Per-bug proving diagnostics enumerated in the workflow synthesis (task `wme32v4qs`).
