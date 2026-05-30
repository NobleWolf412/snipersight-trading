"""
Regression for hot-path audit bug #8 (3_CORRECTNESS): the ProcessPool worker built
a fresh Orchestrator and synced macro_context + scanner_mode per scan, but NEVER
synced current_regime. It therefore stayed at its __init__ value (None) in every
worker, so context.metadata["global_regime"] was None for every symbol. Downstream
that disabled the HTF-alignment bonus (confluence_service: `if global_regime and
symbol_regime`) and forced is_ranging=False (volatility defaulted to "normal"),
silently degrading scoring on every signal.

Fix: current_regime is now threaded through worker_args (between macro_context and
scanner_mode) and assigned onto the cached worker orchestrator alongside the others.

See backend/diagnostics/decisions/2026-05-29__hotpath-robustness-audit.md (bug #8,
overlaps gap A). Per CLAUDE.md §11, §14 rubric 4.
"""

from __future__ import annotations

import pickle
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.engine import orchestrator as orch_mod
from backend.shared.models.regime import MarketRegime, RegimeDimensions


def test_market_regime_is_picklable():
    """current_regime now crosses the ProcessPool boundary in worker_args, so it
    MUST pickle (else the whole scan dispatch would break). MarketRegime is a plain
    dataclass of dataclass/str/float/datetime — verify it round-trips."""
    regime = MarketRegime(
        dimensions=RegimeDimensions(
            trend="up", volatility="compressed", liquidity="healthy",
            risk_appetite="risk_on", derivatives="balanced",
        ),
        composite="bullish_risk_on",
        score=72.0,
        timestamp=datetime(2026, 5, 30),
        trend_score=70.0, volatility_score=60.0, liquidity_score=65.0,
        risk_score=70.0, derivatives_score=50.0,
    )
    restored = pickle.loads(pickle.dumps(regime))
    assert restored.dimensions.trend == "up"
    assert restored.dimensions.volatility == "compressed"
    assert restored.score == 72.0


def test_worker_syncs_current_regime_onto_orchestrator():
    """The worker must assign the unpacked current_regime onto the cached
    orchestrator (it previously synced only macro_context + scanner_mode, leaving
    current_regime None). Pre-seed the module globals to skip the heavy orchestrator
    rebuild and drive straight to the sync + _process_symbol call."""
    saved_orch = orch_mod._WORKER_ORCHESTRATOR
    saved_cfg_id = orch_mod._WORKER_CONFIG_ID
    try:
        mock_orch = MagicMock()
        mock_orch._process_symbol.return_value = ("plan", None)
        cfg = SimpleNamespace()              # stand-in config object
        sentinel_regime = object()           # identity check — was never assigned pre-fix

        orch_mod._WORKER_ORCHESTRATOR = mock_orch
        orch_mod._WORKER_CONFIG_ID = id(cfg)  # match → skip rebuild branch

        # worker_args tuple order: sym, run_id, ts, data, config, macro_context,
        # current_regime, scanner_mode, tick_size, lot_size
        args = (
            "BTC/USDT", "run-1", 1730000000, None, cfg,
            "macro_ctx", sentinel_regime, "scanner_mode", 0.0, 0.0,
        )
        result = orch_mod._parallel_process_symbol_worker(args)

        assert mock_orch.current_regime is sentinel_regime  # propagated (was None pre-fix)
        assert mock_orch.macro_context == "macro_ctx"        # still synced
        assert mock_orch.scanner_mode == "scanner_mode"      # still synced
        assert result == ("plan", None)
        mock_orch._process_symbol.assert_called_once()
    finally:
        orch_mod._WORKER_ORCHESTRATOR = saved_orch
        orch_mod._WORKER_CONFIG_ID = saved_cfg_id
