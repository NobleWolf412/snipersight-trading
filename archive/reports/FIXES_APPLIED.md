# SniperSight Bug Fixes — Session b23bf405 Analysis
*Applied: 2026-03-22*

---

## Fixes Applied

### FIX 1 — Kill Zone UTC Conversion (CRITICAL)
**File:** `backend/strategy/smc/sessions.py` (lines 128-130 and 156-158)

**Bug:** Both `get_current_trading_session()` and `get_current_kill_zone()` had an inverted UTC→EST conversion. `est_offset = timedelta(hours=-5)` then `- est_offset` = subtracting a negative = adding 5 hours. The system was operating at UTC+5 (10 hours off from EST).

**Fix:** Changed `- est_offset` to `+ est_offset`. UTC time + UTC offset (→ UTC naive) + (-5 hours) = EST.

**Verified:** `07:30 UTC → london_open` ✓, `12:30 UTC → new_york_open` ✓

**Impact:** Kill Zone factor was scoring 0 for ~45% of signals because no active kill zone was ever found at the wrong time. Expect meaningful improvement in kill zone scores during actual NY/London opens.

---

### FIX 2 — FVG `size_atr` Not Wired (HIGH)
**File:** `backend/strategy/smc/fvg.py` (lines ~154-164 and ~200-211)

**Bug:** `gap_atr` was calculated from the gap size / ATR, used for min-size filtering and grading, but was NOT passed to the `FVG()` constructor. The `size_atr` field defaulted to 0.0. In the scorer at line 3003: `if getattr(best_fvg, "size_atr", 0.0) > 1.0: score += 15.0` — this +15 bonus **never fired** for any FVG.

**Fix:** Added `size_atr=gap_atr` to both bullish and bearish `FVG()` constructors.

**Impact:** FVGs with `size_atr > 1.0 ATR` (significant gaps) now award +15 pts, improving FVG scores from ~0 to meaningful values. This was contributing to the 91% FVG zero-score rate.

---

### FIX 3 — Scorer Self-Import Circular Reference (MEDIUM)
**File:** `backend/strategy/confluence/scorer.py` (line 2116)

**Bug:** The kill zone scoring block imported from itself: `from backend.strategy.confluence.scorer import get_current_kill_zone, _score_kill_zone_incremental`. This is a circular import that causes Python to load the module twice on first execution, causing subtle state issues. Both functions were already in scope — `get_current_kill_zone` imported from `sessions.py` at file top, `_score_kill_zone_incremental` defined in the same module.

**Fix:** Removed the circular import. Functions are used directly from their existing scope.

---

### FIX 4 — `plan_rr_low` Anomaly Fired on ALL Non-Executed Signals (MEDIUM)
**Files:** `backend/diagnostics/logger.py`, `backend/bot/paper_trading_service.py` (line 1324)

**Bug:** `diag_cat = ProbeCategory.EXEC_SUCCESS if result == "executed" else ProbeCategory.PLAN_RR_LOW` — this used `PLAN_RR_LOW` for every signal that wasn't executed, including the 440 filtered signals. This caused 440 false `plan_rr_low` anomaly entries in `anomalies.jsonl`, making it appear there were hundreds of trade plan quality issues when there were none.

**Fix:** Added `ProbeCategory.SIGNAL_FILTERED = "signal_filtered"` to `logger.py`. Updated routing: `executed → EXEC_SUCCESS`, `filtered → SIGNAL_FILTERED`, `else (bad R:R) → PLAN_RR_LOW`.

**Impact:** `anomalies.jsonl` will no longer be polluted with false plan quality warnings. Real R:R problems will now be distinguishable from normal filtering.

---

### FIX 5 — Dead Code Removal (LOW/MAINTENANCE)
**Files removed/cleaned:**
- Deleted: `backend/strategy/smc/reversal_validator_snippet.py` — orphaned duplicate of `validate_reversal_profile()`, never imported anywhere
- Removed: 3 `NotImplementedError` stub methods from `backend/engine/orchestrator.py` (`_compute_indicators`, `_detect_smc_patterns`, `_compute_confluence_score`) — replaced by service calls long ago, documented with misleading docstrings
- Removed: `calculate_displacement_strength()` from `backend/strategy/smc/order_blocks.py` — fully implemented but never called (internal displacement calc handles it at OB creation time)
- Removed: `get_timeframe_minutes()` from `backend/shared/config/smc_config.py` — never called anywhere

---

### FIX 6 — LONG Bias Root Cause + Partial Fix (HIGH)
**Files:** `backend/strategy/confluence/scorer.py`

**Root Cause (3 factors combining):**

1. **Sweep scoring inflates LONG in downtrends**: In a sell-off (RSI ~26), there are many "sweep of low" events — price dips below a swing low and briefly recovers. The scorer treats these as bullish reversal signals (45-85 pts). Meanwhile SHORT has no "sweep of high" events (price isn't making new highs in a sell-off). Net: 45-85 pt LONG advantage per scan.

2. **OB scoring inflates LONG**: Price sits on fresh bullish demand OBs at the bottom of a range. Bearish supply OBs are above current price (price broke through them on the way down = mitigated = penalized). OBs score higher for LONG.

3. **Climax RSI threshold too tight**: `fade_threshold_rsi = 75.0` → threshold for oversold = `100 - 75 = 25.0`. ETH at RSI 26.1 does NOT trigger "climax" despite being clearly oversold. This means counter-trend LONGs got a weak `-5` penalty instead of the correct `+5` climax bonus.

**Fixes Applied:**

**A) HTF trend discount on sweep scoring** (scorer.py ~line 2103):
When the HTF swing structure (4H or 1D) confirms a trend against the sweep direction, bullish/bearish sweep scores are capped at 30 pts. This prevents cascade sweeps in a trending market from inflating counter-trend confidence.

**B) Climax RSI threshold corrected** (scorer.py ~line 847-857):
- STEALTH mode: `fade_threshold_rsi` 75.0 → 70.0 (oversold threshold 25 → 30)
- OVERWATCH mode: `fade_threshold_rsi` 75.0 → 70.0 (same fix)
- RSI 26 is now recognized as climax territory → counter-trend allowed with +5 bonus instead of -5 penalty

**Remaining LONG bias factor (not yet fixed):**
OB scoring asymmetry is inherent to price position — when price is at the bottom, fresh bullish OBs exist but bearish OBs don't. This is actually correct behavior if the system is designed for counter-trend setups at extremes. However, the sweep HTF discount + climax fix should significantly reduce the LONG ratio from 436:6 toward something more balanced.

---

## Expected Impact on Session Stats

| Metric | Before | Expected After |
|--------|--------|----------------|
| Kill Zone factor zero rate | ~45% | ~15% (only truly outside KZ) |
| FVG size bonus fires | Never | ~40% of FVGs with size > 1 ATR |
| plan_rr_low anomalies | 440 false entries | Near zero false entries |
| Signal direction split | 436 LONG / 6 SHORT | ~70% LONG / 30% SHORT (still bullish bias at bottoms, but moderated) |
| Avg confluence score | 55.5 | Est. 60-65 (kill zone + FVG fixes add points) |

---

## Files Modified
```
backend/strategy/smc/sessions.py           — Kill zone UTC fix (2 locations)
backend/strategy/smc/fvg.py               — size_atr wired in both FVG constructors
backend/strategy/confluence/scorer.py     — Self-import removed; sweep HTF discount; climax threshold fix
backend/bot/paper_trading_service.py      — PLAN_RR_LOW routing fixed
backend/diagnostics/logger.py             — SIGNAL_FILTERED category added
backend/engine/orchestrator.py            — 3 dead stub methods removed
backend/strategy/smc/order_blocks.py      — calculate_displacement_strength() removed
backend/shared/config/smc_config.py       — get_timeframe_minutes() removed
backend/strategy/smc/reversal_validator_snippet.py  — DELETED (orphaned file)
```
