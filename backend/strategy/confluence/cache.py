"""
In-memory confluence breakdown cache.

A bounded ring buffer that stores the most recent ConfluenceBreakdowns
produced by the scorer, keyed by signal id. Powers:

  - GET /api/signals/{id}/confluence
  - GET /api/signals/confluence/distribution

Lookup by id is O(N) over the buffer; rolling distribution is O(N*F).
N is bounded (default 500), F is the number of factors per breakdown
(typically <= 10), so both fit comfortably inside a request handler.

This module is process-local — no persistence. A restart loses the buffer;
older breakdowns can be reconstructed from logs/confluence_breakdown.log
if needed.
"""

from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Deque, Dict, List, Optional, Tuple

from backend.shared.models.scoring import ConfluenceBreakdown

_BUFFER_SIZE = 500

# (signal_id, breakdown) tuples in arrival order
_buffer: Deque[Tuple[str, ConfluenceBreakdown]] = deque(maxlen=_BUFFER_SIZE)
_lock = Lock()

# Visibility counters — exposed via stats(). Failures here would otherwise
# be invisible (the cache is best-effort and doesn't block signal logging).
_records_total = 0
_record_errors_total = 0
_lookups_total = 0
_lookup_misses_total = 0


def record(signal_id: str, breakdown: ConfluenceBreakdown) -> bool:
    """
    Push a breakdown into the ring buffer.

    Returns True on success, False on failure. Increments visibility
    counters either way. Caller is responsible for surfacing False.
    """
    global _records_total, _record_errors_total
    if not signal_id or breakdown is None:
        with _lock:
            _record_errors_total += 1
        return False
    try:
        with _lock:
            _buffer.append((signal_id, breakdown))
            _records_total += 1
        return True
    except Exception:
        with _lock:
            _record_errors_total += 1
        return False


def get(signal_id: str) -> Optional[ConfluenceBreakdown]:
    """Return the most recent breakdown for the given id, or None."""
    global _lookups_total, _lookup_misses_total
    if not signal_id:
        return None
    with _lock:
        _lookups_total += 1
        # newest-first
        for sid, br in reversed(_buffer):
            if sid == signal_id:
                return br
        _lookup_misses_total += 1
    return None


def recent(n: int) -> List[Tuple[str, ConfluenceBreakdown]]:
    """Return the last `n` (signal_id, breakdown) tuples, newest-last."""
    if n <= 0:
        return []
    with _lock:
        if n >= len(_buffer):
            return list(_buffer)
        return list(_buffer)[-n:]


def buffer_size() -> int:
    """Current number of breakdowns held."""
    with _lock:
        return len(_buffer)


def clear() -> None:
    """Drop all cached breakdowns. Used by tests."""
    global _records_total, _record_errors_total, _lookups_total, _lookup_misses_total
    with _lock:
        _buffer.clear()
        _records_total = 0
        _record_errors_total = 0
        _lookups_total = 0
        _lookup_misses_total = 0


def stats() -> Dict[str, int]:
    """
    Visibility counters for diagnostics / health endpoints.

    A growing _record_errors_total or _lookup_misses_total > _records_total
    indicates the cache is silently dropping breakdowns or being asked for
    ids that were never recorded — both regressions worth surfacing.
    """
    with _lock:
        return {
            "buffer_size": len(_buffer),
            "buffer_capacity": _BUFFER_SIZE,
            "records_total": _records_total,
            "record_errors_total": _record_errors_total,
            "lookups_total": _lookups_total,
            "lookup_misses_total": _lookup_misses_total,
        }


def aggregate_distribution(n: int = 200) -> Dict[str, object]:
    """
    Compute rolling factor-contribution averages over the last `n` breakdowns.

    Returns a dict shaped for the wire format:
      {
        "sample_count": int,
        "avg_total_score": float,
        "avg_synergy_bonus": float,
        "avg_conflict_penalty": float,
        "factors": [
          { "name": str, "avg_score": float, "avg_weight": float,
            "avg_weighted_score": float, "sample_count": int }, ...
        ],
      }
    """
    samples = recent(n)
    if not samples:
        return {
            "sample_count": 0,
            "avg_total_score": 0.0,
            "avg_synergy_bonus": 0.0,
            "avg_conflict_penalty": 0.0,
            "factors": [],
        }

    totals = 0.0
    synergy = 0.0
    conflict = 0.0

    # factor_name -> (sum_score, sum_weight, sum_weighted, count)
    factor_acc: Dict[str, List[float]] = {}

    for _, br in samples:
        totals += br.total_score
        synergy += br.synergy_bonus
        conflict += br.conflict_penalty
        for f in br.factors:
            slot = factor_acc.setdefault(f.name, [0.0, 0.0, 0.0, 0.0])
            slot[0] += f.score
            slot[1] += f.weight
            slot[2] += f.weighted_score
            slot[3] += 1.0

    n_samples = len(samples)
    factors_out = []
    for name, (s_score, s_weight, s_weighted, count) in sorted(
        factor_acc.items(), key=lambda kv: -kv[1][2]
    ):
        if count <= 0:
            continue
        factors_out.append({
            "name": name,
            "avg_score": s_score / count,
            "avg_weight": s_weight / count,
            "avg_weighted_score": s_weighted / count,
            "sample_count": int(count),
        })

    return {
        "sample_count": n_samples,
        "avg_total_score": totals / n_samples,
        "avg_synergy_bonus": synergy / n_samples,
        "avg_conflict_penalty": conflict / n_samples,
        "factors": factors_out,
    }
