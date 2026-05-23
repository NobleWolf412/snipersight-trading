# SniperSight Dead Code & Broken Wiring Audit
**Generated:** 2026-03-22
**Scope:** Full backend — SMC engine, scorer, services, risk manager, orchestrator

---

## 🔴 Broken Wiring (Set But Never Used)

### 1. FVG `size_atr` Calculated But Never Passed to Constructor
**File:** `backend/strategy/smc/fvg.py` — lines 134, 154 (bullish) and 180, 200 (bearish)

`gap_atr` is calculated for the size filter, then immediately thrown away when the `FVG` object is built. The scorer has a +15 "Large Gap" bonus gated on `best_fvg.size_atr > 1.0` that has never fired as a result.

**Fix:** Add `size_atr=gap_atr` to both FVG constructors (bullish and bearish). One line each.
**Risk of removing:** N/A — this needs to be added, not removed.

---

### 2. `use_enhanced` Config Flag Wired to Nothing
**File:** `backend/shared/config/smc_config.py` — lines 810–826

The config has `use_enhanced: True` in the OVERWATCH, STEALTH, and SURGICAL profiles, with a comment: *"use_enhanced: Use new check_mitigation_enhanced() function"*. But nowhere in `order_blocks.py` or `smc_service.py` does any code check for this flag or conditionally call `check_mitigation_enhanced()`. The flag is set but never read.

`check_mitigation_enhanced()` itself is a complete, higher-quality function — it tracks tap counts, deepest penetration, and reaction quality — but is never called anywhere. The basic `check_mitigation()` (which only returns a single float with no depth) is used everywhere instead.

**Options:**
- Wire it up: check `use_enhanced` flag in `smc_service.py` where `update_ob_mitigation` is called, and branch to use the enhanced version
- Or remove both the flag and the function

**Risk of removing:** None — `check_mitigation_enhanced` is not called anywhere, removing it won't break anything.

---

### 3. `SMCSnapshot.htf_sweep_context` Built but Not Stored on Snapshot
**File:** `backend/services/smc_service.py` — lines 422 and 436

```python
htf_sweep_context = self._build_htf_sweep_context(all_liquidity_sweeps)  # line 422
# ... then passed as kwarg to SMCSnapshot:
htf_sweep_context=htf_sweep_context   # line 436
```

This one is actually wired correctly — `SMCSnapshot` has the field (`models/smc.py` line 475) and the scorer reads it (`scorer.py` line 4179). ✓ This is fine, just confirming it works.

---

## 🟠 Duplicate / Orphaned Files

### 4. `reversal_validator_snippet.py` Is a Stranded Duplicate
**File:** `backend/strategy/smc/reversal_validator_snippet.py`

This file contains a complete implementation of `validate_reversal_profile()`. The orchestrator imports the same-named function from `reversal_detector.py` (line 70: `from backend.strategy.smc.reversal_detector import ... validate_reversal_profile`). The snippet file is **never imported anywhere** in the codebase.

The two implementations appear to be the same function — the snippet file was likely used as a staging area while the function was being developed, then the real version was committed to `reversal_detector.py` and the snippet was never deleted.

**Action:** Safe to delete. Confirm the content matches `reversal_detector.py` first, then remove the file entirely.
**Risk of removing:** Zero — it is not imported or used anywhere.

---

## 🟡 Dead Code — Worth Implementing

### 5. Three Cycle Integration Functions in `cycle_detector.py` — Never Called
**File:** `backend/strategy/smc/cycle_detector.py` — lines 741–820+

Three public functions exist with complete docstrings and implementations, designed to be called by the confluence scorer or orchestrator:

| Function | Purpose | Lines |
|----------|---------|-------|
| `get_trade_bias_from_cycle(cycle_context)` | Returns `(direction, confidence_boost)` from cycle phase | 741–753 |
| `should_boost_direction(cycle_context, direction)` | Returns `(bool, boost_amount)` if cycle phase boosts given direction | 756–789 |
| `should_bypass_htf_alignment(cycle_context, direction, ...)` | Returns `(bool, reason)` if cycle extreme justifies HTF bypass | 792–820+ |

The scorer and orchestrator do partial cycle logic inline (the synergy bonus section in `_calculate_synergy_bonus()` duplicates what `should_boost_direction` would do). These functions look like a cleaner API that was written in anticipation of refactoring the cycle logic out of the scorer — but the refactor never happened.

**Recommendation:** Wire them up or delete them. If you want to clean up the scorer's inline cycle logic, these functions provide the right interface. If not, they're dead weight.
**Risk of removing:** None — they are not imported or called anywhere outside `cycle_detector.py`.

---

## 🟡 Dead Code — Safe to Remove

### 6. `calculate_displacement_strength()` — Defined, Never Called
**File:** `backend/strategy/smc/order_blocks.py` — lines 451–487

Function recalculates displacement strength for an existing OrderBlock. Never called anywhere outside its own file — not in `smc_service.py`, not in the scorer, not in the orchestrator.

**Action:** Safe to remove.
**Risk:** None.

---

### 7. `check_mitigation_enhanced()` — Defined, Never Called
**File:** `backend/strategy/smc/order_blocks.py` — lines 542–636

Complete implementation that returns a richer dict (tap count, deepest penetration, reaction quality, grade). The only references to it are in the `use_enhanced` config comment (see finding #2) and the function definition itself. Neither `smc_service.py` nor `mitigation_tracker.py` calls it — both call the basic `check_mitigation()`.

**Action:** Safe to remove, OR wire it up via the `use_enhanced` flag. The function itself is better than `check_mitigation()` and would improve OB filtering quality if used.
**Risk:** None if removed.

---

### 8. `get_timeframe_minutes()` in `smc_config.py` — Defined, Never Called
**File:** `backend/shared/config/smc_config.py`

Utility function that converts timeframe strings to minutes. Never called anywhere.

**Action:** Safe to remove.
**Risk:** None.

---

### 9. Three `NotImplementedError` Stub Methods in Orchestrator
**File:** `backend/engine/orchestrator.py` — lines 1807–1850

Three orchestrator methods exist only to throw `NotImplementedError` with a message saying "use the service instead":

- `_compute_indicators()` → "Use self.indicator_service.compute instead"
- `_detect_smc_patterns()` → "Use self.smc_service.detect instead"
- `_compute_confluence_score()` → "Use self.confluence_service.score instead"

These are leftover stubs from when those operations were moved into dedicated services. The comments in `indicator_service.py` and `smc_service.py` reference these methods by name to explain their origin. They serve no runtime purpose and will cause crashes if anything accidentally calls them.

**Action:** Safe to delete the three methods. The comments in the service files are enough documentation of the history.
**Risk:** None if removed — would actually prevent accidental runtime crashes.

---

## 🟢 Intentional / Correctly Implemented

These were investigated and confirmed correct:

- `validate_reversal_profile()` in `reversal_detector.py` — correctly imported and used by orchestrator ✓
- `detect_obs_from_bos()`, `filter_overlapping_order_blocks()`, `filter_obs_by_mode()` — all imported and called in `smc_service.py` ✓
- `update_ob_mitigation()` in `mitigation_tracker.py` — called in `smc_service.py` ✓
- `htf_levels` on `SMCSnapshot` — populated by orchestrator, read by scorer and risk engine ✓
- `htf_sweep_context` — built and passed in `smc_service.py`, read by scorer ✓
- All private `_detect_*` functions in `cycle_detector.py` — called internally by `detect_cycle_context()` ✓
- `reset_daily_stats()` in `risk_manager.py` — has real implementation (trim to 7 days), though it's not called by any scheduler currently ✓

---

## Summary: Prioritized Action List

| Priority | Action | File | Risk |
|----------|--------|------|------|
| 🔴 Now | Add `size_atr=gap_atr` to FVG constructors | `fvg.py` | None |
| 🟠 Soon | Delete `reversal_validator_snippet.py` | standalone file | Zero |
| 🟡 Next | Wire up `check_mitigation_enhanced` via `use_enhanced` flag OR remove both | `order_blocks.py`, `smc_config.py` | Low |
| 🟡 Next | Decide: wire up or delete the 3 cycle API functions | `cycle_detector.py` | None either way |
| 🟢 Cleanup | Remove 3 `NotImplementedError` stub methods | `orchestrator.py` | None |
| 🟢 Cleanup | Remove `calculate_displacement_strength()` | `order_blocks.py` | None |
| 🟢 Cleanup | Remove `get_timeframe_minutes()` | `smc_config.py` | None |
| 🟢 Cleanup | Remove `use_enhanced` config key (if not wiring it up) | `smc_config.py` | None |
