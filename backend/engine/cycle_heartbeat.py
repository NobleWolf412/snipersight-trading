"""
Per-scan-cycle heartbeat ring buffer.

Records one snapshot per scan cycle from the orchestrator, including
failed cycles (try/finally guarantee — a missing cycle is worse than a
noisy one). Powers:

  - GET /api/cycles/last
  - GET /api/cycles/history
  - GET /api/cycles/trend
  - backend.diagnostics.cycle_heartbeat_audit

Storage is process-local. Restart drops history. At default cadences
(60s / 90s) `maxlen=50` retains roughly 50–75 minutes of cycles —
sufficient for "is the scanner healthy right now?" and "did the
bottleneck shift in the last hour?" without growing unbounded.

Threading model:
  - Writer: orchestrator.scan() finally block, sync code on main loop.
  - Readers: FastAPI handlers (potentially threadpool workers), audit
    script, in-process diagnostic calls.
  Same cross-thread reader pattern as confluence.cache and
  pair_selection. threading.Lock is the correct primitive — works from
  both sync and async-event-loop contexts. CPython's GIL makes
  deque.append atomic; iteration must occur under lock.

Bottleneck definition:
  Count-based: the per-stage rejection bucket with the highest count.
  Rate-based ("lowest pass-through") would be more diagnostic but
  requires stage-entering counts the orchestrator does not expose
  today. Future enhancement is gated on per-stage entry instrumentation.

Mass conservation:
  plans_emitted + sum(signals_per_stage.values()) == symbols_scanned
  Asserted inside record() before push. A future change that silently
  consumes a symbol will trip this loudly.
"""

from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Any, Deque, Dict, List, Optional


_HISTORY_SIZE = 50

_lock = Lock()
_history: Deque[Dict[str, Any]] = deque(maxlen=_HISTORY_SIZE)

# Visibility counters for diagnostics
_records_total = 0
_record_errors_total = 0
_failed_cycles_total = 0


def record(snapshot: Dict[str, Any]) -> bool:
    """
    Push a heartbeat snapshot into the ring buffer.

    Required keys:
      ts_start (float), ts_end (float|None), wall_ms (int|None),
      run_id (str), mode (str|None), symbols_scanned (int),
      plans_emitted (int), total_rejected (int),
      signals_per_stage (dict[str, int]), bottleneck_stage (str|None),
      failed (bool), exception_class (str|None).

    Optional keys:
      direction_stats (dict), regime (dict|None),
      next_cycle_eta_ts (float|None).

    Returns True on success, False on validation failure. Increments
    visibility counters either way. The orchestrator's finally block
    is the sole writer — it must observe a False return and surface it.
    """
    global _records_total, _record_errors_total, _failed_cycles_total

    if not isinstance(snapshot, dict):
        with _lock:
            _record_errors_total += 1
        return False

    required = (
        "ts_start", "run_id", "symbols_scanned", "plans_emitted",
        "total_rejected", "signals_per_stage", "failed",
    )
    for k in required:
        if k not in snapshot:
            with _lock:
                _record_errors_total += 1
            return False

    # Mass conservation invariant — asserted at the source. Skipped for
    # failed cycles since partial counts are explicitly incomplete.
    if not snapshot.get("failed", False):
        emitted = int(snapshot.get("plans_emitted", 0))
        per_stage = snapshot.get("signals_per_stage") or {}
        per_stage_sum = sum(int(v) for v in per_stage.values())
        scanned = int(snapshot.get("symbols_scanned", 0))
        if emitted + per_stage_sum != scanned:
            # Loud failure: the orchestrator silently lost or duplicated a
            # symbol. The heartbeat itself is the most reliable place to
            # catch this — every cycle passes through here.
            with _lock:
                _record_errors_total += 1
            raise AssertionError(
                f"cycle_heartbeat mass conservation breach: "
                f"plans_emitted={emitted} + per_stage_sum={per_stage_sum} "
                f"!= symbols_scanned={scanned} "
                f"(per_stage={per_stage}, run_id={snapshot.get('run_id')})"
            )

    try:
        with _lock:
            _history.append(snapshot)
            _records_total += 1
            if snapshot.get("failed"):
                _failed_cycles_total += 1
        return True
    except Exception:
        with _lock:
            _record_errors_total += 1
        return False


def get_latest() -> Optional[Dict[str, Any]]:
    """Return a shallow copy of the most recent heartbeat, or None."""
    with _lock:
        if not _history:
            return None
        return dict(_history[-1])


def recent(n: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Return the last `n` heartbeats (oldest-first). If `n` is None,
    returns every snapshot in the buffer. Each entry is a shallow copy.
    """
    with _lock:
        if not _history:
            return []
        if n is None or n >= len(_history):
            return [dict(s) for s in _history]
        return [dict(s) for s in list(_history)[-n:]]


def filter_by_mode(mode: str, n: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Return recent heartbeats filtered to a single scanner mode. Used by
    the audit's per-mode trend so different mode baselines (overwatch
    vs surgical) don't get mixed.
    """
    if not mode:
        return recent(n)
    rows = recent(None)
    filtered = [r for r in rows if r.get("mode") == mode]
    if n is not None and n < len(filtered):
        return filtered[-n:]
    return filtered


def stats() -> Dict[str, int]:
    """Visibility counters for diagnostics / health endpoints."""
    with _lock:
        return {
            "buffer_size": len(_history),
            "buffer_capacity": _HISTORY_SIZE,
            "records_total": _records_total,
            "record_errors_total": _record_errors_total,
            "failed_cycles_total": _failed_cycles_total,
        }


def clear() -> None:
    """Drop all cached heartbeats. Used by tests."""
    global _records_total, _record_errors_total, _failed_cycles_total
    with _lock:
        _history.clear()
        _records_total = 0
        _record_errors_total = 0
        _failed_cycles_total = 0


def history_size() -> int:
    with _lock:
        return len(_history)
