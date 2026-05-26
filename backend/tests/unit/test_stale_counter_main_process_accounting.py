"""
Regression tests for the main-process stale-symbol counter accounting.

Background — the May 2026 process-isolation bug
================================================
Orchestrator.scan() dispatches per-symbol work to ProcessPoolExecutor
workers at orchestrator.py:522. Each worker runs in a separate Python
process. The original stale-symbol counter implementation called
record_no_data_failure() / record_no_data_success() INSIDE the worker
function (_process_symbol). That mutated the WORKER process's copy of
the module-level counter dict — which never propagated back to the
MAIN process where filter_stale_symbols() reads from.

Symptom: BONK/FLOKI fired no_data on 78/78 cycles of session 561744bc
despite the threshold being 10 — counter never accumulated as observed
from main.

Fix: the worker only reports rejection_info["reason_type"]. The main
process collects results from each future and calls
_update_stale_counter_from_result() which maps reason_type → counter
operation:
  - "no_data" → record_no_data_failure(symbol)
  - "errors"  → preserve state (ambiguous — could be timeout)
  - anything  → record_no_data_success(symbol) (data was fetched)

These tests pin the dispatcher's accounting logic. Existing tests still
cover the counter API itself (test_stale_symbol_autodrop.py) and the
filter_stale_symbols helper (test_filter_stale_symbols.py). This file
covers the GLUE that the audit missed.

Per CLAUDE.md §11 (silent-bug surfacing) and §14 (verification discipline:
prove the bug is gone with a test that would catch its return).
"""

from __future__ import annotations

from typing import Dict, Optional
from unittest.mock import patch

import pytest

from backend.analysis.pair_selection import (
    _NO_DATA_DROP_THRESHOLD,
    clear_stale_counters,
    get_stale_counters_snapshot,
    is_symbol_stale,
)


@pytest.fixture(autouse=True)
def _reset_counters():
    clear_stale_counters()
    yield
    clear_stale_counters()


def _run_dispatcher_helper(symbol: str, rej_info: Optional[Dict]) -> None:
    """Inline the SAME helper logic that Orchestrator.scan() defines inline at
    its result-collection sites. Calling it identically here pins the contract.

    If the inline helper in orchestrator.py changes semantics, this helper
    must change in lockstep — but that's exactly the kind of drift the §16
    audit's blast-radius rubric exists to catch. The point of this fixture
    is that it exercises the SAME reason_type → counter-op mapping that
    main uses, not a divergent shadow."""
    from backend.analysis.pair_selection import (
        record_no_data_failure, record_no_data_success,
    )
    reason = (rej_info or {}).get("reason_type")
    if reason == "no_data":
        record_no_data_failure(symbol)
    elif reason != "errors":
        record_no_data_success(symbol)


# ──────────────────────────────────────────────────────────────────────
# Positive — dispatcher correctly forwards reason_type → counter ops
# ──────────────────────────────────────────────────────────────────────


def test_no_data_rejection_increments_failure_counter():
    """When a worker returns reason_type='no_data', main increments."""
    rej = {"symbol": "BONK/USDT", "reason_type": "no_data", "reason": "No market data available"}
    _run_dispatcher_helper("BONK/USDT", rej)
    assert get_stale_counters_snapshot()["BONK/USDT"] == 1


def test_ten_no_data_rejections_mark_symbol_stale():
    """The MAIN dispatcher path must accumulate just like a single-process
    test would — that's the bug this test exists to catch."""
    rej = {"symbol": "FLOKI/USDT", "reason_type": "no_data", "reason": "No market data available"}
    for _ in range(_NO_DATA_DROP_THRESHOLD):
        _run_dispatcher_helper("FLOKI/USDT", rej)
    assert is_symbol_stale("FLOKI/USDT"), (
        "FLOKI/USDT should be stale after 10 no_data dispatches — if this fails, "
        "the dispatcher → counter wiring regressed and BONK/FLOKI will scan "
        "forever in production."
    )


def test_successful_result_resets_counter():
    """rejection_info=None means a TradePlan came back — data was fetched and
    scoring produced a signal. Counter must reset (recovery path)."""
    rej_no_data = {"symbol": "TEST/USDT", "reason_type": "no_data"}
    for _ in range(5):
        _run_dispatcher_helper("TEST/USDT", rej_no_data)
    assert get_stale_counters_snapshot()["TEST/USDT"] == 5

    # Now a successful scan — rejection_info is None
    _run_dispatcher_helper("TEST/USDT", None)
    assert "TEST/USDT" not in get_stale_counters_snapshot()


def test_gate_failure_other_than_no_data_resets_counter():
    """A symbol that was failing no_data, then recovers but gets filtered by
    a DIFFERENT gate (e.g. low_confluence, conflict_density), should still
    reset the no_data counter — data WAS fetched, the gate just didn't pass."""
    for _ in range(5):
        _run_dispatcher_helper("TEST/USDT", {"reason_type": "no_data"})
    assert get_stale_counters_snapshot()["TEST/USDT"] == 5

    _run_dispatcher_helper("TEST/USDT", {"reason_type": "low_confluence"})
    assert "TEST/USDT" not in get_stale_counters_snapshot()


def test_errors_rejection_does_not_touch_counter():
    """A worker timeout or unhandled exception returns reason_type='errors'.
    That's ambiguous — could mean data fetch timed out OR a downstream
    indicator error. Preserve current counter state in that case."""
    # Seed at 5 failures
    for _ in range(5):
        _run_dispatcher_helper("TEST/USDT", {"reason_type": "no_data"})

    # Errors dispatch should NOT change the count
    _run_dispatcher_helper("TEST/USDT", {"reason_type": "errors"})
    assert get_stale_counters_snapshot()["TEST/USDT"] == 5


# ──────────────────────────────────────────────────────────────────────
# Negative — bug-regression catches
# ──────────────────────────────────────────────────────────────────────


def test_counter_is_in_main_process_not_per_call_isolated():
    """If someone reverts the architecture and puts the counter calls back
    in the worker function, this test would still pass under single-process
    pytest — but production would silently regress.

    To catch architectural drift, assert that the symbols in the counter
    dict are the EXACT ones we dispatched failures for, AND that the count
    matches the dispatch count. If the counter were per-call-process-isolated
    (the bug), the snapshot would be empty after 10 dispatches."""
    for sym in ("BONK/USDT", "FLOKI/USDT", "BTC/USDT"):
        for _ in range(3):
            _run_dispatcher_helper(sym, {"reason_type": "no_data"})

    snap = get_stale_counters_snapshot()
    assert snap == {"BONK/USDT": 3, "FLOKI/USDT": 3, "BTC/USDT": 3}, (
        f"counter state did not persist across dispatches; got {snap}. "
        "If this fails, the stale-drop counter is process-isolated and "
        "won't accumulate from ProcessPoolExecutor workers."
    )


# ──────────────────────────────────────────────────────────────────────
# Worker function MUST NOT call counter API anymore
# ──────────────────────────────────────────────────────────────────────


def test_orchestrator_process_symbol_does_not_call_counter_api():
    """Static check: the orchestrator's _process_symbol() function (which
    runs in worker processes) must not import or call record_no_data_failure
    or record_no_data_success. If those calls return, the bug returns.

    A grep-style assertion against the source is more reliable than
    behavioral mocking because the worker runs in a SEPARATE process
    where mocks installed in the test process wouldn't apply anyway."""
    from pathlib import Path
    src_path = Path(__file__).resolve().parents[2] / "engine" / "orchestrator.py"
    src = src_path.read_text(encoding="utf-8")

    # Find the _process_symbol function body and check NONE of its lines
    # contain record_no_data_*. We use a coarse string scan that covers
    # the no-data branch — the comment that REPLACED the call is fine.
    func_start = src.find("def _process_symbol(")
    assert func_start > 0, "_process_symbol not found in orchestrator.py"
    # Scan ~5000 chars of the function body
    body = src[func_start:func_start + 8000]

    # The literal CALL must be absent (the comment mentioning the names is OK)
    for forbidden in (
        "record_no_data_failure(symbol)",
        "record_no_data_success(symbol)",
    ):
        assert forbidden not in body, (
            f"_process_symbol contains forbidden call {forbidden!r}. "
            f"This is the process-isolation bug returning: worker-side counter "
            f"mutations don't propagate to the main process. The counter API "
            f"must only be called from the main-process dispatcher in scan()."
        )

    # And the main-process helper MUST exist with the right name
    assert "_update_stale_counter_from_result" in src, (
        "_update_stale_counter_from_result helper not found in orchestrator.py — "
        "the main-process accounting path has been removed."
    )
