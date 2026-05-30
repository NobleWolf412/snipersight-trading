"""
Regression for hot-path audit bug #5 (2_RISKY): the IndicatorService._safe_compute_*
methods logged computation failures at logger.debug and returned None. Production
uvicorn runs at log_level=info with no basicConfig, so DEBUG was below threshold —
a persistently failing indicator (e.g. the pandas-ta column-drift class, commit
25ec544) produced ZERO visible output, scored as a neutral factor, and the missing
factor's weight was redistributed to survivors so the degraded signal still cleared
min_confluence_score. A silent failure on a money path (CLAUDE.md §11 violation).

Fix: the seven failure paths now log at logger.warning so they surface under prod
INFO logging. (The benign success-debug line in _safe_compute_volume_acceleration
stays at DEBUG.)

NOTE (separate follow-up, NOT in this fix): the weight-redistribution in
scorer.py:3026-3049 silently absorbing a missing factor is its own concern in a
symmetry-guard-gated file — tracked separately, not bundled here.

See backend/diagnostics/decisions/2026-05-29__hotpath-robustness-audit.md (bug #5).
Per CLAUDE.md §11 (loud-failure surfacing), §14 rubric 4 (negative+positive pair).
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from backend.services import indicator_service as ind_mod
from backend.services.indicator_service import IndicatorService

_LOGGER_NAME = "backend.services.indicator_service"
_DF = pd.DataFrame(
    {"open": [1, 2], "high": [1, 2], "low": [1, 2], "close": [1, 2], "volume": [1, 2]}
)


def _svc() -> IndicatorService:
    s = object.__new__(IndicatorService)
    s._scanner_mode = SimpleNamespace(volume_accel_lookback=5)
    return s


def _assert_failure_warns(caplog, compute_name: str, call):
    """Patch the underlying compute fn to raise; assert the _safe_compute_*
    wrapper logs at WARNING (not the old, invisible DEBUG) and returns None."""
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        with patch.object(ind_mod, compute_name, side_effect=RuntimeError("boom")):
            result = call()
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings, (
        f"{compute_name} failure must log at WARNING (was DEBUG → invisible under prod "
        f"INFO); got levels {[r.levelname for r in caplog.records]}"
    )
    return result


def test_macd_failure_warns(caplog):
    assert _assert_failure_warns(
        caplog, "compute_macd", lambda: _svc()._safe_compute_macd(_DF, "1h")
    ) == (None, None, None)


def test_adx_failure_warns(caplog):
    assert _assert_failure_warns(
        caplog, "compute_adx", lambda: _svc()._safe_compute_adx(_DF, "1h")
    ) == (None, None, None)


def test_realized_volatility_failure_warns(caplog):
    assert _assert_failure_warns(
        caplog, "compute_realized_volatility",
        lambda: _svc()._safe_compute_realized_volatility(_DF, "1h"),
    ) is None


def test_volume_ratio_failure_warns(caplog):
    assert _assert_failure_warns(
        caplog, "compute_relative_volume",
        lambda: _svc()._safe_compute_volume_ratio(_DF, "1h"),
    ) is None


def test_volume_acceleration_failure_warns(caplog):
    assert _assert_failure_warns(
        caplog, "detect_volume_acceleration",
        lambda: _svc()._safe_compute_volume_acceleration(_DF, "1h"),
    ) is None


def test_stoch_rsi_failure_warns(caplog):
    assert _assert_failure_warns(
        caplog, "compute_stoch_rsi", lambda: _svc()._safe_compute_stoch_rsi(_DF, "1h")
    ) is None


def test_vwap_failure_warns(caplog):
    assert _assert_failure_warns(
        caplog, "compute_vwap", lambda: _svc()._safe_compute_vwap(_DF, "1h")
    ) is None


def test_success_emits_no_warning(caplog):
    """Positive pair: a SUCCESSFUL compute must NOT emit a warning (no false alarm
    that would re-pollute the prod log it just got cleaned up for)."""
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        with patch.object(ind_mod, "compute_macd", return_value=(1.0, 2.0, 3.0)):
            result = _svc()._safe_compute_macd(_DF, "1h")
    assert result == (1.0, 2.0, 3.0)
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
