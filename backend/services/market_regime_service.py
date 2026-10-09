"""One privately owned, timestamped market snapshot for display and mode advice."""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import time

from backend.analysis.regime_inputs import validate_regime_candles

from backend.analysis.dominance_service import get_dominance_for_macro
from backend.analysis.mode_recommendation import recommend_mode, unavailable_recommendation
from backend.analysis.regime_detector import RegimeDetector
from backend.data.ingestion_pipeline import IngestionPipeline
from backend.services.indicator_service import IndicatorService
from backend.shared.async_worker import SerializedWorker

logger = logging.getLogger(__name__)


class MarketRegimeUnavailable(ValueError):
    pass


@dataclass
class _Context:
    timeframes: tuple
    detector: RegimeDetector
    indicators: IndicatorService


class MarketRegimeService:
    def __init__(self, adapter_factory):
        self._adapter_factory = adapter_factory
        self._pipeline = None
        self._worker = SerializedWorker()
        self._display = _Context(("1w", "1d", "4h"), RegimeDetector(), IndicatorService())
        self._display.detector._global_regime_ttl = 0
        # One source observation owns both consumers; scanner mutations cannot affect it.
        self._recommendation = self._display
        self._cached_display = None
        self._display_expires = 0.0

    async def get_global(self):
        return await self._worker.run(self._read_global)

    async def get_recommendation(self):
        return await self._worker.run(self._read_recommendation)

    @staticmethod
    def _source_times(data, now):
        source_times = {}
        for tf, hours in (("1d", 24), ("4h", 4), ("1w", 168)):
            frame = data.timeframes.get(tf)
            required = tf != "1w"
            try:
                source_times[tf] = validate_regime_candles(frame, hours, now)
            except (ValueError, KeyError, TypeError) as exc:
                if required:
                    raise MarketRegimeUnavailable(f"{tf} market data unavailable: {exc}") from exc
        return source_times

    def _inputs(self, context):
        try:
            if self._pipeline is None:
                self._pipeline = IngestionPipeline(self._adapter_factory())
            data = self._pipeline.fetch_multi_timeframe("BTC/USDT", list(context.timeframes))
            if not data or not data.timeframes:
                raise MarketRegimeUnavailable("Market data unavailable")
            source_times = self._source_times(data, datetime.now(timezone.utc))
            indicators = context.indicators.compute(data)
            if not indicators.by_timeframe:
                raise MarketRegimeUnavailable("Market indicators unavailable")
            dominance = get_dominance_for_macro()
            regime = context.detector.detect_global_regime(data, indicators, dominance=dominance, confirmed=False)
            if regime is None:
                raise MarketRegimeUnavailable("Market regime unavailable")
            return data, regime, dominance, source_times
        except MarketRegimeUnavailable:
            raise
        except Exception as exc:
            logger.exception("Market regime inputs failed")
            raise MarketRegimeUnavailable("Market analysis could not verify its required inputs") from exc

    def _read_global(self):
        if self._cached_display is not None and time.monotonic() < self._display_expires:
            return deepcopy(self._cached_display)
        data, regime, (btc, alt, stable), source_times = self._inputs(self._display)
        matrix = {}
        for tf in source_times:
            trend, score, description = self._display.detector.analyze_timeframe_trend(data.timeframes[tf], tf)
            matrix[tf] = {"trend": trend, "context": description, "score": score,
                          "color": "green" if trend in ("up", "strong_up") else "red" if trend in ("down", "strong_down") else "yellow"}
        now = datetime.now(timezone.utc)
        deadline = min(datetime.fromisoformat(source_times[tf]) + timedelta(hours=hours, minutes=5)
                       for tf, hours in (("1d", 24), ("4h", 4), ("1w", 168)) if tf in source_times)
        expires = min(now + timedelta(seconds=120), deadline)
        if expires <= now:
            raise MarketRegimeUnavailable("Market evidence expired during analysis")
        result = {
            "composite": regime.composite, "score": regime.score,
            "dimensions": {
                "trend": regime.dimensions.trend, "volatility": regime.dimensions.volatility,
                "liquidity": regime.dimensions.liquidity, "risk_appetite": regime.dimensions.risk_appetite,
                "derivatives": regime.dimensions.derivatives,
            },
            "trend_score": regime.trend_score, "volatility_score": regime.volatility_score,
            "liquidity_score": regime.liquidity_score, "risk_score": regime.risk_score,
            "derivatives_score": regime.derivatives_score, "derivatives_available": False,
            "dominance": {"btc_d": round(btc, 2), "alt_d": round(alt, 2), "stable_d": round(stable, 2)},
            "dominance_source": "Top-100 market-cap basket plus tracked stablecoins; shares, not measured capital flows",
            "reference_timeframe": "1d", "source_times": source_times, "matrix": matrix,
            "timestamp": now.isoformat(), "expires_at": expires.isoformat(),
            "calibration": "uncalibrated", "regime_version": "daily-regime-v2",
        }
        self._cached_display = deepcopy(result)
        self._display_expires = time.monotonic() + max(0., min(60., (expires - now).total_seconds()))
        return result

    def _read_recommendation(self):
        try:
            snapshot = self._read_global()
            result = recommend_mode(snapshot)
            result["dominance"] = snapshot["dominance"]
            return result
        except Exception:
            logger.exception("Failed to generate regime recommendation")
            return unavailable_recommendation()
