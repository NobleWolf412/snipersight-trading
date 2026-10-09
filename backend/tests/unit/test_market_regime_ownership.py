import asyncio
import threading
from datetime import datetime, timezone
from types import SimpleNamespace as S
from unittest.mock import Mock

import pytest

from backend.services import market_regime_service as module
from backend.services.scanner_service import ScannerService
from backend.shared.config.scanner_modes import get_mode
from backend.shared.models.regime import MarketRegime, RegimeDimensions
from backend.tests.unit.test_mode_regime_policy import candles


@pytest.fixture
def reader(monkeypatch):
    observed = []
    def observe(value):
        observed.append(threading.get_ident())
        return value
    adapter = object()
    factory = Mock(side_effect=lambda: observe(adapter))
    service = module.MarketRegimeService(factory)
    data = S(timeframes={tf: candles(tf) for tf in ["1w", "1d", "4h"]})
    fetch = Mock(side_effect=lambda *a: observe(data))
    pipeline = S(fetch_multi_timeframe=fetch)
    monkeypatch.setattr(module, "IngestionPipeline", lambda supplied: observe(pipeline) if supplied is adapter else None)
    dominance = Mock(side_effect=lambda: observe((54., 42.5, 3.5)))
    monkeypatch.setattr(module, "get_dominance_for_macro", dominance)
    regime = MarketRegime(RegimeDimensions("up", "normal", "healthy", "risk_on", "balanced"),
                          "bullish_risk_on", 75., datetime(2026, 9, 1, tzinfo=timezone.utc),
                          70., 75., 70., 80., 50.)
    for context in (service._display, service._recommendation):
        context.indicators.compute = Mock(side_effect=lambda data: observe(S(by_timeframe={"1h": object()})))
        context.detector.detect_global_regime = Mock(side_effect=lambda *args, **kwargs: observe(regime))
        context.detector.analyze_timeframe_trend = Mock(return_value=("up", 70., "fixture"))
    return S(service=service, factory=factory, observed=observed, fetch=fetch,
             dominance=dominance, regime=regime, data=data)


def test_market_regime_ownership_fixed_contexts_and_detached_display_cache(reader):
    reader.factory.assert_not_called()
    service = reader.service
    assert service._display.detector is service._recommendation.detector
    assert service._display.detector.mode_profile == get_mode("stealth").profile
    assert service._display.timeframes == ("1w", "1d", "4h")
    assert service._recommendation.timeframes == ("1w", "1d", "4h")
    async def scenario():
        loop_thread = threading.get_ident()
        first = await service.get_global()
        assert first["dominance"] == {"btc_d": 54., "alt_d": 42.5, "stable_d": 3.5}
        first["dimensions"]["trend"] = "corrupted"
        assert (await service.get_global())["dimensions"]["trend"] == "up"
        rec = await service.get_recommendation()
        assert rec["dominance"] == {"btc_d": 54., "alt_d": 42.5, "stable_d": 3.5}
        assert set(rec["matrix"]) == {"1w", "1d", "4h"}
        assert all(tid != loop_thread for tid in reader.observed)
        assert [c.args[1] for c in reader.fetch.call_args_list] == [
            list(service._display.timeframes)]
        reader.factory.assert_called_once()
    asyncio.run(scenario())


@pytest.mark.parametrize("missing", ["data", "indicators", "regime", "dominance"])
def test_market_regime_ownership_missing_inputs_remain_unavailable(reader, missing, caplog):
    service = reader.service
    if missing == "data":
        reader.fetch.side_effect = lambda *a, **kw: None
    elif missing == "dominance":
        reader.dominance.side_effect = ValueError("stale fixture")
    else:
        for context in (service._display, service._recommendation):
            if missing == "indicators":
                context.indicators.compute.side_effect = lambda *a: S(by_timeframe={})
            else:
                context.detector.detect_global_regime.side_effect = lambda *a, **kw: None
    async def scenario():
        with pytest.raises(module.MarketRegimeUnavailable):
            await service.get_global()
        assert service._cached_display is None
        if missing == "dominance":
            assert "stale fixture" in caplog.text
        rec = await service.get_recommendation()
        assert rec["status"] == "unavailable" and rec["mode"] is None and rec["warning"]
        assert "regime" not in rec and "dominance" not in rec
    asyncio.run(scenario())


def test_market_regime_ownership_recommendation_uses_injected_reader(reader):
    scanner_engine = Mock()
    scanner = ScannerService(scanner_engine, {}, regime_reader=reader.service)
    result = asyncio.run(scanner.get_global_regime_recommendation())
    assert result["regime"]["composite"] == "bullish_risk_on"
    assert not scanner_engine.mock_calls


@pytest.mark.parametrize("failed", ["factory", "fetch", "indicator", "detector"])
def test_market_regime_ownership_input_failures_are_503_eligible_and_retryable(reader, failed):
    service = reader.service
    target = {"factory": reader.factory, "fetch": reader.fetch,
              "indicator": service._display.indicators.compute,
              "detector": service._display.detector.detect_global_regime}[failed]
    original = target.side_effect
    target.side_effect = RuntimeError("input fixture error")
    async def scenario():
        with pytest.raises(module.MarketRegimeUnavailable):
            await service.get_global()
        target.side_effect = original
        assert (await service.get_global())["score"] == 75.
    asyncio.run(scenario())
