"""
TTL-cached audit status with transition logging.

The HTTP router needs a *cheap* way to ask "is the cycle audit currently
DEGRADED?" on every request, without re-running drift detectors per call.
This module wraps the cycle / universe audits with a short TTL (default 5s)
and emits an INFO log every time the cached status FLIPS — so the operator
sees a real OK→DEGRADED transition the moment it stabilizes, even though
intermediate-request audits return cached values.

Without the transition log, the cache silently smooths over real status
changes and §11 observability degrades exactly when it matters most.

Thread-safety: same threading.Lock pattern as the upstream caches. Safe
for the FastAPI threadpool reader vs. orchestrator-finally writer pattern.
"""

from __future__ import annotations

import logging
import time
from threading import Lock
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_TTL_SECONDS = 5.0
_lock = Lock()

# Keyed by audit name ("cycles" or "universe") so the two audits are
# independent. Value: (expires_at, status, reason, warnings).
_cache: Dict[str, Tuple[float, str, Optional[str], list]] = {}
_last_status: Dict[str, str] = {}


def _refresh_cycles() -> Tuple[str, Optional[str], list]:
    """Run the cycle audit and reduce it to (status, reason, warnings)."""
    from backend.diagnostics.cycle_heartbeat_audit import audit_cycles
    report = audit_cycles()
    if not report.has_history:
        return "OK", None, []
    if not report.healthy:
        # Pick the first failure as the human-readable reason
        reason = report.failures[0] if report.failures else "unspecified"
        return "DEGRADED", reason, list(report.failures) + list(report.notes)
    if report.notes:
        return "OK", None, list(report.notes)
    return "OK", None, []


def _refresh_universe() -> Tuple[str, Optional[str], list]:
    """Run the universe audit and reduce it to (status, reason, warnings)."""
    from backend.diagnostics.universe_audit import audit_universe
    report = audit_universe()
    if not report.has_snapshot:
        return "OK", None, []
    if not report.healthy:
        reason = report.failures[0] if report.failures else "unspecified"
        return "DEGRADED", reason, list(report.failures) + list(report.notes)
    if report.notes:
        return "OK", None, list(report.notes)
    return "OK", None, []


_REFRESHERS = {
    "cycles": _refresh_cycles,
    "universe": _refresh_universe,
}


def get_status(name: str, *, force: bool = False) -> Tuple[str, Optional[str], list]:
    """
    Return cached (status, reason, warnings) for the named audit.

    `force=True` bypasses the TTL — used by tests and by transition checks.
    """
    if name not in _REFRESHERS:
        raise KeyError(f"unknown audit name: {name}")

    now = time.time()
    with _lock:
        cached = _cache.get(name)
        if cached and not force and now < cached[0]:
            return cached[1], cached[2], list(cached[3])

    # Refresh outside the lock (audit may take a few ms; we don't want to
    # block other readers).
    status, reason, warnings = _REFRESHERS[name]()

    with _lock:
        prior = _last_status.get(name)
        if prior is not None and prior != status:
            # Transition — log it so the operator sees the moment it flipped.
            logger.info(
                f"audit status TRANSITION for '{name}': {prior} -> {status} "
                f"(reason={reason!r})"
            )
        _last_status[name] = status
        _cache[name] = (now + _TTL_SECONDS, status, reason, list(warnings))

    return status, reason, list(warnings)


def clear() -> None:
    """Drop all cached status values. Used by tests."""
    with _lock:
        _cache.clear()
        _last_status.clear()
