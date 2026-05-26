# Stale-symbol counter — process-isolation architectural fix

## Headline
The `record_no_data_failure` / `record_no_data_success` calls in `_process_symbol`
ran inside `ProcessPoolExecutor` worker processes, mutating each worker's local
copy of the module-level counter dict — state that never propagated back to
the main process where `filter_stale_symbols()` reads from. Two consecutive
sessions (e5e00ebc, 561744bc) showed BONK/FLOKI scanned on **100% of cycles**
despite the 10-cycle threshold, because the main-process counter stayed empty
forever.

Fix: worker emits `rejection_info["reason_type"]` only; main process accumulates
the counter from those return values via a new `_update_stale_counter_from_result()`
helper at three result-collection sites in `Orchestrator.scan()`.

## Context
- The original stale-drop landed in commit `5f32b87` (close-stale-symbol-bypass).
  Unit tests passed in single-process pytest, the §16 audit returned 14 ✅, and
  the user re-armed expecting the auto-drop to fire on cycle 11.
- Session e5e00ebc (2.5h, 51 cycles): BONK/FLOKI fired no_data 51/51.
  Initially diagnosed as "bot not restarted after commit" — wrong.
- Session 561744bc (3h 51m, 78 cycles): BONK/FLOKI fired no_data 78/78
  after a verified fresh `npm run dev:all`. That ruled out the restart
  hypothesis and forced the architectural diagnosis.
- Root cause located at [orchestrator.py:522](backend/engine/orchestrator.py#L522)
  — `ProcessPoolExecutor` forks separate Python processes per worker. Each
  worker imports `backend.analysis.pair_selection` fresh and has its own copy
  of `_consecutive_no_data_failures: Dict[str, int]`. Worker mutations are
  scoped to that worker's memory.

## Resolution
- [orchestrator.py:1130-1162](backend/engine/orchestrator.py#L1130): removed both
  worker-side calls (`record_no_data_failure`, `record_no_data_success`).
  Replaced with comments documenting why they cannot live here.
- [orchestrator.py:516-535](backend/engine/orchestrator.py#L516): added inline
  helper `_update_stale_counter_from_result(symbol, rejection_info)` in
  `scan()`. Reads `rejection_info["reason_type"]`:
  - `"no_data"` → `record_no_data_failure(symbol)`
  - `"errors"` → preserve state (ambiguous: timeout vs runtime exception)
  - anything else (incl. None / successful result) → `record_no_data_success(symbol)`
- Helper called at three result-collection sites:
  - normal completion (L555)
  - timeout fallback (L572)
  - unhandled-exception fallback (L592)
- New test file `backend/tests/unit/test_stale_counter_main_process_accounting.py`
  with 7 cases covering: positive (no_data → increment, threshold-cross →
  stale), negative (success → reset, non-no_data gate → reset, errors → no-op),
  state-persistence-across-dispatches, and a STATIC source-grep test that
  asserts `_process_symbol` does NOT contain the forbidden worker-side calls
  (catches re-introduction of the bug).

## Why it matters next time
- This is the §16 rubric's blind spot — **the audit rubric does not include
  a multiprocessing-shared-state check**. The existing rubric items (mass
  conservation, blast radius, contract diff) all passed for commit 5f32b87
  because the bug was invisible from a single-process viewpoint. Add Rubric
  15 candidate: "module-level mutable state used across `ProcessPoolExecutor`
  or `multiprocessing.Pool` workers must be explicitly designed for IPC OR
  the code path must be documented as main-process-only."
- The new static-grep regression test (`test_orchestrator_process_symbol_does_not_call_counter_api`)
  is intentionally coarse — it checks the function body string for literal
  forbidden calls. If a future refactor restores the worker-side counter
  calls (well-intended but wrong), this test fails immediately. Pairs with
  the §11 silent-bug surfacing principle.
- Secondary finding (separate commit): the BONK/FLOKI no_data failures had
  an UPSTREAM cause — those tickers don't exist on Phemex. Real tickers are
  `1000BONK/USDT` and `1000FLOKI/USDT` (memecoin "1000x" convention for
  small per-coin price). The architectural fix is the correct safety net,
  but for these specific symbols the cure is to use the right ticker name.
- Contract: no API, telemetry, pipeline, or DB schema changes. Pre-flight
  blast-radius enumeration:
  - Upstream callers: `Orchestrator.scan()` itself; `_process_symbol` called by
    worker + `bot_simulation_diagnostic.py` (single-process, unaffected).
  - Downstream consumers: `pair_selection._consecutive_no_data_failures` dict
    (unchanged shape), `filter_stale_symbols`, `is_symbol_stale`.
  - No telemetry events changed.
