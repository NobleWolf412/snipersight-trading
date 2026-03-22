# SniperSight Backend Debug Report
**Generated:** 2026-03-21
**Audited by:** Claude (Cowork overnight session)
**Scope:** Full backend Python codebase + TypeScript frontend errors

---

## Summary

All Python files pass syntax checks — no import crashes or parse errors. The backend is structurally solid and well-organized. The issues below are logic bugs, error-handling gaps, type mismatches, and code hygiene problems that could silently affect scan accuracy, risk enforcement, and operational stability.

---

## 🔴 High Priority — Fix These First

### 1. Silent Leverage Injection Failure (`services/scanner_service.py`, line 283–286)
```python
try:
    setattr(self._orchestrator.config, "leverage", params["leverage"])
except Exception:
    pass
```
If leverage injection fails, the scan continues silently with the wrong leverage value. This is a risk management failure — wrong leverage means wrong stop sizing. The exception should at minimum be logged, and the scan should probably abort or default to 1x explicitly.

---

### 2. Bare `except:` Swallowing All Exceptions — 11 Locations
The following files contain `except: pass` (bare except — catches SystemExit, KeyboardInterrupt, and all OS signals, not just Exception):

- `backend/analysis/htf_levels.py:272`
- `backend/engine/orchestrator.py:1370`
- `backend/strategy/confluence/scorer.py`: lines 2244, 2347, 2376, 2424, 2433, 2446, 2454, 2550
- `backend/strategy/smc/order_blocks.py:1368`
- `backend/strategy/smc/symbol_cycle_detector.py:306`

**Scorer.py is the worst offender** with 8 bare excepts — this is the core of the signal engine. Silent failures here mean a signal could score incorrectly and you'd never know. Replace with `except Exception` at minimum, and add a `logger.warning()`.

---

### 3. `RiskManager.reset_daily_stats()` is a No-Op (`risk/risk_manager.py`, line 482)
```python
def reset_daily_stats(self) -> None:
    """Reset daily statistics (call at start of each trading day)."""
    # In production, this would track daily high water mark
    # For now, we rely on trade history timestamps
```
This method does absolutely nothing. If the paper bot or any external caller uses this expecting a reset, it silently fails. Either implement it or remove it and update all callers so there's no false confidence it's working.

---

### 4. TOCTOU Race Condition in Risk Validation (`risk/risk_manager.py`, line 275)
`validate_new_trade()` acquires a lock for checks 1–3, releases it, then does checks 4–6 (daily loss, weekly loss, position concentration) without the lock. In a concurrent scan scenario (which the orchestrator explicitly uses via `ThreadPoolExecutor`), two trades could pass loss limit checks simultaneously, both proceeding before either has updated `trade_history`. The daily/weekly loss guard could be bypassed under load.

---

## 🟡 Medium Priority — Should Be Fixed

### 5. `_transform_signals` Return Type Annotation is Wrong (`services/scanner_service.py`, line 375)
```python
def _transform_signals(self, trade_plans: List, mode, adapter=None) -> List[Dict]:
```
The actual return value is a **tuple** `(signals, rejected_signals)`, matching how it's called on line 330:
```python
signals, rejected_signals = self._transform_signals(trade_plans, mode, current_adapter)
```
Wrong type annotation causes misleading IDE hints and makes future refactoring dangerous.

---

### 6. `logger.error()` Used for Debug Statement (`engine/orchestrator.py`, line 535)
```python
logger.error(f"DEBUG APPEND rejection for {rejection_info.get('symbol')}...")
```
This is a debug statement incorrectly logged at ERROR level. It will appear as a critical failure in any log monitoring tool. Should be `logger.debug()` or removed.

---

### 7. Duplicate `import threading` (`api_server.py`, lines 25 and 104)
`import threading` is imported twice. The second import at line 104 is inside a comment block explaining `ThreadSafeCache`. Harmless but messy — indicates old code wasn't cleaned up when `ThreadSafeCache` was restructured.

---

### 8. Meme Symbol Classifier Called Twice in `pair_selection.py` (lines 192, 230–255)
```python
memes_list = [s for s in all_symbols if _is_meme_symbol(s)]  # First call
# ... then inside logging:
memes_cnt = len([s for s in all_symbols if _is_meme_symbol(s)])  # Second call
```
`_is_meme_symbol()` hits the SymbolClassifier which may query CoinGecko data. Running it twice per symbol per scan just for logging is wasteful. Cache the result from the first pass.

---

### 9. `ScanJobLogHandler` Not Concurrent-Scan Safe (`api_server.py`, line 64)
There's a single global log handler (`scan_job_log_handler`) that tracks `current_job`. If two scans run concurrently, logs from scan B could be attributed to scan A's job, or vice versa. The handler only supports one "current job" at a time — fine for sequential scans but could be misleading if parallelism is ever introduced at the scan level.

---

### 10. Dead Code Branch in Confluence Tiebreaker (`services/confluence_service.py`, line 407)
Inside the `if (bullish_breakdown.total_score > 70 and bearish_breakdown.total_score > 70):` block, the final `else: raise ConflictingDirectionsException` is unreachable. If both scores are `> 70`, then `both_scores_high` (which checks `>= 70`) is always `True`, so `elif both_scores_high:` always matches, and the else never fires. This is dead code that creates confusion and could mislead future devs into thinking this exception path is active.

---

## 🟢 Low Priority — Cleanup / Housekeeping

### 11. Debug Log Statements Left in Production Code
The following files have development debug logs that should either be gated behind `SS_DEBUG` or removed:
- `backend/routers/data.py`: `🔍 [CACHE DEBUG]` prefix on multiple lines (lines 270, 277, 281) — these log on every cache hit/miss
- `backend/strategy/planner/planner_service.py`: lines 254, 322, 371, 476, 488, 581, 662, 678 — detailed DEBUG logging of internal values
- `backend/strategy/planner/risk_engine.py`: lines 1186, 1837, 2185, 2279 — `# CRITICAL DEBUG` / `# === DEBUG LOGGING ===` blocks

These produce significant log noise in production and make it harder to find real issues.

---

### 12. Duplicate `_get_asset_exposure` / `_get_correlated_exposure` Methods (`risk/risk_manager.py`)
There are two pairs of near-identical methods:
- `_get_asset_exposure_unsafe()` (line 314) and `_get_asset_exposure()` (line 498)
- `_get_correlated_exposure_unsafe()` (line 329) and `_get_correlated_exposure()` (line 512)

The `_unsafe` variants are used inside the lock context, the others are used from `get_risk_summary()`. Logic duplication is a maintenance trap — if the exposure calculation ever changes, both versions need updating. Consider refactoring to a single implementation with a note that the caller is responsible for locking.

---

## 📋 TypeScript Frontend Errors (from `typescript-errors.txt`)

These are existing TS errors that are suppressed at build time (`--noCheck`) but represent real type safety gaps:

| File | Error | Severity |
|------|-------|----------|
| `PriceCard.stories.tsx:19,26,33` | `'label'` prop doesn't exist on PriceCard type | Low (Storybook only) |
| `HolographicGlobe.tsx:87` | Missing required `args` property on Float32BufferAttribute | Medium |
| `ModeVisuals.tsx:289,290` | `opacity`/`transparent` don't exist on `Material[]` — needs array narrowing | Medium |
| `SceneContainer.tsx:52,53,55,56` | `undefined` not assignable to `Element` — missing null checks | High |
| `WaveformMonitor.tsx:62` | Three.js `Line` ref typed as SVGLineElement — wrong ref type entirely | High |
| `CycleStatusStrip.tsx:57` | `isLoading` missing from `UseSymbolCyclesResult` return type | Medium |
| `Intel.tsx:267` | `FourYearCycleData` missing `days_until_expected_low` and `zones` — likely backend/frontend type mismatch | High |

**Most critical:** `Intel.tsx` — the `FourYearCycleData` type mismatch suggests the backend added new fields (`days_until_expected_low`, `zones`) that the frontend type wasn't updated to include. This could cause a runtime crash if those fields are accessed.

---

## 🧪 Test Infrastructure Issue

Running `pytest backend/tests/smoke/` fails with a `PermissionError` on a `.coverage` file. This is a `pytest-cov` plugin conflict with the Linux VM filesystem. Tests themselves may be fine — try running with `--no-cov` flag:

```bash
python3 -m pytest backend/tests/smoke/ -q --no-cov
```

---

## Quick Win Priority Order

1. Fix silent leverage injection failure → add logging + explicit fallback
2. Replace all `except: pass` → `except Exception as e: logger.warning(...)`
3. Implement or remove `reset_daily_stats()`
4. Fix `_transform_signals` return type annotation
5. Change `logger.error()` debug statement to `logger.debug()`
6. Fix `Intel.tsx` type mismatch (backend/frontend sync issue)
7. Fix `SceneContainer.tsx` and `WaveformMonitor.tsx` null/type issues
8. Remove duplicate `import threading` in `api_server.py`
9. Cache meme symbol classification results in `pair_selection.py`
10. Gate debug log statements behind `SS_DEBUG` flag or remove them
