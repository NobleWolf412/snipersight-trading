"""
Regression for hot-path audit bug #6 (2_RISKY): SMCService._detect_equal_highs_lows
wrapped detection in `try: ... except Exception: pass`, silently zeroing the TF's
equal-highs/lows and liquidity pools with NO log and NO smc_rejections entry. A real
liquidity-pool setup then scored as if no pool existed (CLAUDE.md §11 silent-failure).

Fix: the except now logs at WARNING, records the failure in the module's existing
self._diagnostics["smc_rejections"] channel (matching the sibling convention at
smc_service.py:270-274), and sets empty defaults so downstream degrades gracefully
instead of KeyError-ing.

See backend/diagnostics/decisions/2026-05-29__hotpath-robustness-audit.md (bug #6).
Per CLAUDE.md §11 (loud-failure surfacing), §14 rubric 4 (negative+positive pair).
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import patch

from backend.services import smc_service as smc_mod
from backend.services.smc_service import SMCDetectionService

_LOGGER_NAME = "backend.services.smc_service"


def _svc() -> SMCDetectionService:
    s = object.__new__(SMCDetectionService)
    s._diagnostics = {"smc_rejections": []}
    s._smc_config = SimpleNamespace()  # passed through to the (patched) detect fn
    return s


def test_detect_failure_is_loud_and_recorded(caplog):
    """detect_equal_highs_lows raises → WARNING logged, smc_rejections entry added,
    keys default to empty (graceful degrade), no exception propagates."""
    s = _svc()
    result: dict = {}
    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        with patch.object(smc_mod, "detect_equal_highs_lows", side_effect=RuntimeError("boom")):
            s._detect_equal_highs_lows("1h", object(), result)  # must not raise

    assert any(r.levelno >= logging.WARNING for r in caplog.records), "failure must log at WARNING"
    assert s._diagnostics["smc_rejections"], "failure must be recorded in smc_rejections"
    assert s._diagnostics["smc_rejections"][0]["timeframe"] == "1h"
    assert result["equal_highs"] == [] and result["equal_lows"] == []
    assert result["liquidity_pools"] == []


def test_sweep_failure_preserves_detected_equal_highs(caplog):
    """If equal highs/lows were detected but track_pool_sweeps then raises, the
    already-detected equal highs/lows are preserved and only liquidity_pools defaults."""
    s = _svc()
    result: dict = {}
    ehl = {"equal_highs": [1], "equal_lows": [2], "pools": [{"x": 1}], "metadata": {}}
    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        with patch.object(smc_mod, "detect_equal_highs_lows", return_value=ehl), \
             patch.object(smc_mod, "track_pool_sweeps", side_effect=RuntimeError("sweep boom")):
            s._detect_equal_highs_lows("4h", object(), result)

    assert any(r.levelno >= logging.WARNING for r in caplog.records)
    assert s._diagnostics["smc_rejections"]
    assert result["equal_highs"] == [1]          # detected before the failure — preserved
    assert result["liquidity_pools"] == []        # defaulted on failure


def test_success_records_no_rejection():
    """Positive pair: a successful detection populates pools and records NO rejection."""
    s = _svc()
    result: dict = {}
    ehl = {
        "equal_highs": [1], "equal_lows": [2], "pools": [{"x": 1}],
        "metadata": {"tolerance_used": 0.001, "min_touches": 2},
    }
    with patch.object(smc_mod, "detect_equal_highs_lows", return_value=ehl), \
         patch.object(smc_mod, "track_pool_sweeps", return_value=[{"x": 1, "swept": False}]):
        s._detect_equal_highs_lows("4h", object(), result)

    assert s._diagnostics["smc_rejections"] == []
    assert result["equal_highs"] == [1]
    assert result["liquidity_pools"] == [{"x": 1, "swept": False}]
