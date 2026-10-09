"""
Market Regime Detector - Multi-dimensional analysis

Detects market regime across multiple dimensions with hysteresis
to prevent regime flip-flopping.
"""

from typing import List, Optional
from datetime import datetime, timezone
from types import SimpleNamespace
from dataclasses import replace
import logging
import math
import numpy as np

from backend.shared.models.regime import MarketRegime, RegimeDimensions, SymbolRegime
from backend.shared.models.data import MultiTimeframeData
from backend.shared.models.indicators import IndicatorSet
from backend.analysis.regime_inputs import validate_regime_candles

logger = logging.getLogger(__name__)


# Timeframe ordering by real duration (minutes). Used to pick the genuinely
# highest timeframe present. A naive lexicographic reverse-sort of
# ('1W','1D','4H','1H','15m','5m') returns '5m' (because '5' > '4' > '1' as the
# leading char) — the LOWEST timeframe — which pinned the structural volatility
# regime to 5-minute ATR% (~0.14% → perma-"compressed"). See
# backend/diagnostics/regime_tf_selection_diagnostic.py.
_TF_MINUTES = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "4h": 240, "6h": 360, "12h": 720,
    "1d": 1440, "3d": 4320, "1w": 10080,
}


def _highest_duration_tf(keys) -> Optional[str]:
    """Return the highest-duration timeframe key present (e.g. '1W' over '5m').

    Graceful fallback: if '1W' isn't present (e.g. Phemex weekly fetch failed),
    returns the next-longest available ('1D'). If no key has a known duration,
    returns the lexicographic max (prior behaviour) so an unknown-key set never
    raises.
    """
    present = list(keys)
    if not present:
        return None
    known = [k for k in present if k.lower() in _TF_MINUTES]
    if known:
        return max(known, key=lambda k: _TF_MINUTES[k.lower()])
    return max(present)


class RegimeDetector:
    """Detects market regime across multiple dimensions"""

    def __init__(self, mode_profile: str = "stealth_balanced"):
        self.regime_history: List[MarketRegime] = []
        self.hysteresis_bars = 5  # INCREASED: Require 5 bars before flip (was 3)
        self.mode_profile = mode_profile

        # === NEW: Confirmation counter for regime changes ===
        self._confirmed_regime: Optional[MarketRegime] = None
        self._pending_regime: Optional[str] = None  # Composite label being tested
        self._pending_count: int = 0
        self._confirmation_required: int = 3  # Need 3 consecutive readings to confirm
        
        # Cache for performance (Gap #4)
        self._global_regime_cache = None
        self._global_regime_cache_time = None
        self._global_regime_cache_key = None
        self._last_confirmation_evidence = None
        self._global_regime_ttl = 300  # 5 minutes for BTC global regime

        self._symbol_regime_cache = {}  # {symbol: (regime, timestamp)}
        self._symbol_regime_ttl = 60  # 1 minute for individual symbols

        # Mode-specific regime detection thresholds
        self.MODE_REGIME_THRESHOLDS = {
            "macro_surveillance": {  # OVERWATCH: Stricter trend requirements
                "min_trend_adx": 25,
                "strong_trend_adx": 35,
                "strong_momentum_slope": 3.0,
            },
            "stealth_balanced": {  # STEALTH: Balanced (default)
                "min_trend_adx": 20,
                "strong_trend_adx": 30,
                "strong_momentum_slope": 2.0,
            },
            "intraday_aggressive": {  # STRIKE: More permissive for intraday
                "min_trend_adx": 15,
                "strong_trend_adx": 25,
                "strong_momentum_slope": 1.5,
            },
            "precision": {  # SURGICAL: Micro-trend detection
                "min_trend_adx": 12,
                "strong_trend_adx": 20,
                "strong_momentum_slope": 1.0,
            },
        }

        # Get mode-specific thresholds
        self.thresholds = self.MODE_REGIME_THRESHOLDS.get(
            mode_profile, self.MODE_REGIME_THRESHOLDS["stealth_balanced"]
        )

    def detect_global_regime(
        self,
        btc_data: MultiTimeframeData,
        btc_indicators: IndicatorSet,
        dominance=None,
        confirmed=True,
    ) -> MarketRegime:
        """
        Detect global market regime from BTC as market leader.

        Args:
            btc_data: BTC multi-timeframe OHLCV data
            btc_indicators: BTC technical indicators

        Returns:
            MarketRegime with all dimensions analyzed
        """

        # Global context always means daily BTC, regardless of the selected mode.
        daily = btc_data.timeframes.get("1d")
        daily_indicator = btc_indicators.by_timeframe.get("1d")
        if daily is None or daily_indicator is None or len(daily) < 50:
            raise ValueError("REGIME_INPUT_UNAVAILABLE: daily BTC history is required")
        evidence_id = validate_regime_candles(daily, 24, datetime.now(timezone.utc))
        cache_key = (evidence_id, tuple(float(daily[column].iloc[-1]) for column in ("high", "low", "close", "volume")))
        if (self._global_regime_cache is not None and self._global_regime_cache_key == cache_key
                and self._global_regime_cache_time is not None
                and (datetime.utcnow() - self._global_regime_cache_time).total_seconds() < self._global_regime_ttl):
            return self._confirmed_view(self._global_regime_cache) if confirmed else self._global_regime_cache
        daily_data = SimpleNamespace(timeframes={"1d": daily})
        daily_indicators = SimpleNamespace(by_timeframe={"1d": daily_indicator})

        # 1. Trend Regime (HTF structure + MA slope)
        trend, trend_score, _ = RegimeDetector().analyze_timeframe_trend(daily, "1d")

        # 2. Volatility Regime (ATR-based)
        volatility, vol_score = self._detect_volatility(daily_indicators)

        # 3. Liquidity Regime (volume-based)
        liquidity, liq_score = self._detect_liquidity(daily_data)

        # 4. Risk Appetite (simplified - would use BTC.D, USDT.D)
        risk_appetite, risk_score = self._detect_risk_appetite(dominance)

        # 5. Derivatives (placeholder - needs funding rate data)
        derivatives, deriv_score = "balanced", 50.0

        dimensions = RegimeDimensions(
            trend=trend,
            volatility=volatility,
            liquidity=liquidity,
            risk_appetite=risk_appetite,
            derivatives=derivatives,
        )

        # Composite label
        composite = self._generate_composite_label(dimensions)

        # Overall score (weighted average)
        score = (
            trend_score * 0.3
            + vol_score * 0.2
            + liq_score * 0.2
            + risk_score * 0.2
            + deriv_score * 0.1
        )

        regime = MarketRegime(
            dimensions=dimensions,
            composite=composite,
            score=score,
            timestamp=datetime.now(timezone.utc),
            trend_score=trend_score,
            volatility_score=vol_score,
            liquidity_score=liq_score,
            risk_score=risk_score,
            derivatives_score=deriv_score,
        )

        # Apply hysteresis to prevent flip-flopping
        self._apply_hysteresis(regime, evidence_id=evidence_id)

        # Cache result (Gap #4)
        self._global_regime_cache_key = cache_key
        self._global_regime_cache = regime
        self._global_regime_cache_time = datetime.utcnow()

        # === DETAILED REGIME BREAKDOWN LOG ===
        logger.info(
            "\n"
            "╔══════════════════════════════════════════════════════════════╗\n"
            "║               GLOBAL REGIME BREAKDOWN                        ║\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
            "║  COMPOSITE: %-20s  SCORE: %.1f               ║\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
            "║  DIMENSIONS:                                                 ║\n"
            "║    • Trend:        %-15s (score: %.1f)          ║\n"
            "║    • Volatility:   %-15s (score: %.1f)          ║\n"
            "║    • Liquidity:    %-15s (score: %.1f)          ║\n"
            "║    • Risk Appetite:%-15s (score: %.1f)          ║\n"
            "║    • Derivatives:  %-15s (score: %.1f)          ║\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
            "║  CONFIRMATION:                                               ║\n"
            "║    • Confirmed:    %-20s                     ║\n"
            "║    • Pending:      %-20s (%d/%d)               ║\n"
            "╚══════════════════════════════════════════════════════════════╝",
            regime.composite, regime.score,
            trend, trend_score,
            volatility, vol_score,
            liquidity, liq_score,
            risk_appetite, risk_score,
            derivatives, deriv_score,
            self._confirmed_regime.composite if self._confirmed_regime else "None",
            self._pending_regime or "None", self._pending_count, self._confirmation_required,
        )

        return self._confirmed_view(regime) if confirmed else regime

    def detect_symbol_regime(
        self,
        symbol: str,
        data: MultiTimeframeData,
        indicators: IndicatorSet,
        cycle_context: Optional["CycleContext"] = None,  # NEW: Cycle-aware override
    ) -> SymbolRegime:
        """
        Detect per-symbol local regime.

        Args:
            symbol: Trading pair symbol
            data: Symbol multi-timeframe data
            indicators: Symbol indicators
            cycle_context: Optional cycle context for extreme-zone overrides

        Returns:
            SymbolRegime with local trend/vol assessment
        """

        # Check cache (Gap #4)
        if symbol in self._symbol_regime_cache:
            cached_regime, cached_time = self._symbol_regime_cache[symbol]
            age = (datetime.utcnow() - cached_time).total_seconds()
            if age < self._symbol_regime_ttl:
                logger.debug(f"🗄️ Returning cached regime for {symbol} (age={age:.1f}s)")
                return cached_regime

        trend, _ = self._detect_trend(data)
        volatility, _ = self._detect_volatility(indicators)

        # Symbol score based on trend clarity + volatility quality
        score = self._score_symbol_regime(trend, volatility)

        # === CYCLE-AWARE OVERRIDE (Gap #2) ===
        # At cycle extremes, override regime to avoid penalizing valid reversal trades
        if cycle_context:
            from backend.shared.models.smc import CyclePhase, CycleTranslation

            # Override bearish regime at accumulation zones (DCL/WCL)
            if trend in ("down", "strong_down"):
                if (
                    cycle_context.in_dcl_zone
                    or cycle_context.in_wcl_zone
                    or cycle_context.phase == CyclePhase.ACCUMULATION
                ):
                    logger.info(
                        f"🔄 Regime override: {trend} → sideways at cycle low zone (allows longs)"
                    )
                    trend = "sideways"
                    score += 10  # Bonus for counter-trend at extreme

            # Override bullish regime at distribution / cycle topping
            if trend in ("up", "strong_up"):
                if (
                    cycle_context.translation == CycleTranslation.LTR
                    or cycle_context.phase == CyclePhase.DISTRIBUTION
                    or cycle_context.trade_bias == "SHORT"
                ):
                    logger.info(
                        f"🔄 Regime override: {trend} → sideways at cycle high/LTR (allows shorts)"
                    )
                    trend = "sideways"
                    score += 10  # Bonus for counter-trend at extreme

        regime = SymbolRegime(symbol=symbol, trend=trend, volatility=volatility, score=score)

        # Cache result (Gap #4)
        self._symbol_regime_cache[symbol] = (regime, datetime.utcnow())

        return regime

    def detect_intermediate_regime(
        self,
        data: MultiTimeframeData,
        indicators: IndicatorSet,
    ) -> Optional[SymbolRegime]:
        """
        Detect intermediate (4H) regime for scalp/intraday mode gating.

        Unlike detect_symbol_regime() which uses the highest available TF,
        this explicitly anchors to 4H so scalp modes (Surgical/Strike) check
        alignment against the 4H structure rather than the daily macro regime.

        Returns None if 4H data is not available.
        """
        if "4h" not in data.timeframes:
            return None

        df = data.timeframes["4h"]
        trend, score, _ = self.analyze_timeframe_trend(df, "4h")
        volatility, _ = self._detect_volatility(indicators)
        regime_score = self._score_symbol_regime(trend, volatility)

        logger.debug(
            "Intermediate regime (4H): trend=%s, vol=%s, score=%.1f",
            trend, volatility, regime_score,
        )
        return SymbolRegime(
            symbol="intermediate",
            trend=trend,
            volatility=volatility,
            score=regime_score,
        )

    def analyze_timeframe_trend(self, df, timeframe_label: str) -> tuple[str, float]:
        """
        Analyze trend for a specific single timeframe dataframe.

        Uses hybrid approach:
        1. Swing structure detection (primary) - 50-bar lookback
        2. ADX check (secondary) - confirms sideways when ADX < 20

        Returns: (trend_label, score, reason)
        """
        from backend.strategy.smc.swing_structure import detect_swing_structure
        from backend.shared.config.smc_config import scale_lookback

        if df is None or len(df) < 50 or not all(c in df for c in ("high", "low", "close")):
            raise ValueError(f"REGIME_INPUT_UNAVAILABLE: insufficient {timeframe_label} history")
        values = df[["high", "low", "close"]].to_numpy(dtype=float)
        if not np.isfinite(values).all() or (values <= 0).any() or (values[:, 0] < values[:, 1]).any():
            raise ValueError(f"REGIME_INPUT_UNAVAILABLE: invalid {timeframe_label} prices")
        from backend.indicators.momentum import compute_adx
        adx_value, _, _ = compute_adx(df)
        if adx_value is None or not math.isfinite(adx_value):
            raise ValueError(f"REGIME_INPUT_UNAVAILABLE: invalid {timeframe_label} ADX")

        # === 2. Swing Structure Detection (50-bar lookback) ===
        try:
            # INCREASED: Base lookback from 15 to 50 for better trend detection
            # This gives ~8 days on 4H, ~50 days on 1D
            scaled_lookback = scale_lookback(50, timeframe_label, min_lookback=30, max_lookback=80)

            # Use swing structure detector
            swing_struct = detect_swing_structure(df, lookback=scaled_lookback)
            trend = swing_struct.trend

            # Log swing points for debugging
            if len(swing_struct.swing_points) > 0:
                recent_5 = swing_struct.swing_points[-5:]
                logger.info(
                    f"📊 {timeframe_label} SWINGS (last 5): "
                    + " | ".join(
                        [
                            f"{s.swing_type.upper()}@{s.price:.2f} (str={s.strength:.1f})"
                            for s in recent_5
                        ]
                    )
                )
            else:
                logger.info(f"📊 {timeframe_label} SWINGS: No swings detected")

            # Check momentum strength
            recent_swings = (
                swing_struct.swing_points[-5:] if len(swing_struct.swing_points) >= 5 else []
            )
            strong_swings = [s for s in recent_swings if s.strength > 1.5]
            has_strong_momentum = len(strong_swings) >= 3

            # Check MA slope
            df_copy = df.copy()
            df_copy["ma20"] = df_copy["close"].rolling(20).mean()

            if not df_copy["ma20"].isna().all():
                ma20_now = df_copy["ma20"].iloc[-1]
                ma20_before = df_copy["ma20"].iloc[-20]
                slope = (ma20_now - ma20_before) / ma20_before * 100

                atr = df_copy["high"].rolling(14).max() - df_copy["low"].rolling(14).min()
                current_price = df_copy["close"].iloc[-1]
                atr_pct = (atr.iloc[-1] / current_price * 100) if current_price > 0 else 1.0
                normalized_slope = slope / max(atr_pct, 0.5)

                logger.info(
                    f"📈 {timeframe_label} MA20: now={ma20_now:.2f} | 20bars_ago={ma20_before:.2f} | "
                    f"slope={slope:.2f}% | norm_slope={normalized_slope:.2f} | price={current_price:.2f}"
                )
            else:
                normalized_slope = 0
                logger.info(f"📈 {timeframe_label} MA20: Insufficient data for slope")

            # === 3. Classification with ADX Confirmation ===

            # Get mode-specific thresholds
            strong_slope_threshold = self.thresholds["strong_momentum_slope"]
            
            # Helper to generate context description from slope
            def get_trend_desc(trend_lbl, cur_slope):
                if trend_lbl == "bullish":
                    if cur_slope > 4.0: return "Explosive Trend"
                    if cur_slope > 2.0: return "Strong Momentum"
                    return "Steady Uptrend"
                elif trend_lbl == "bearish":
                    if cur_slope < -4.0: return "Aggressive Selling"
                    if cur_slope < -2.0: return "Momentum Breakdown"
                    return "Steady Downtrend"
                return "Ranging Structure"

            # === MA SLOPE OVERRIDE ===
            # If MA slope is strongly negative OR positive, override swing structure
            MA_SLOPE_OVERRIDE_THRESHOLD = 0.06  
            RAW_SLOPE_OVERRIDE_THRESHOLD = 3.0  
            
            if slope < -RAW_SLOPE_OVERRIDE_THRESHOLD and trend == "bullish":
                logger.warning(
                    f"⚠️ RAW SLOPE OVERRIDE {timeframe_label}: swing=bullish BUT raw slope={slope:.2f}% < -{RAW_SLOPE_OVERRIDE_THRESHOLD} → DOWN"
                )
                # §10 bull/bear symmetry: down=70 mirrors up=70 (line 509).
                return "down", 70.0, "Momentum Breakdown"
            
            if slope > RAW_SLOPE_OVERRIDE_THRESHOLD and trend == "bearish":
                logger.warning(
                    f"⚠️ RAW SLOPE OVERRIDE {timeframe_label}: swing=bearish BUT raw slope={slope:.2f}% > {RAW_SLOPE_OVERRIDE_THRESHOLD} → UP"
                )
                return "up", 70.0, "Explosive Rebound"
            
            if normalized_slope < -MA_SLOPE_OVERRIDE_THRESHOLD and trend == "bullish":
                logger.warning(
                    f"⚠️ MA SLOPE OVERRIDE {timeframe_label}: swing=bullish BUT norm_slope={normalized_slope:.2f} < -{MA_SLOPE_OVERRIDE_THRESHOLD} → DOWN"
                )
                # §10 bull/bear symmetry: down=70 mirrors up=70 (line 521).
                # Trend *clarity* drives quality; *direction* doesn't.
                return "down", 70.0, "Structural Fatigue"
            
            if normalized_slope > MA_SLOPE_OVERRIDE_THRESHOLD and trend == "bearish":
                logger.warning(
                    f"⚠️ MA SLOPE OVERRIDE {timeframe_label}: swing=bearish BUT norm_slope={normalized_slope:.2f} > {MA_SLOPE_OVERRIDE_THRESHOLD} → UP"
                )
                return "up", 70.0, "Impulsive Recovery"

            # If swing structure found a trend
            if trend == "bullish":
                desc = get_trend_desc("bullish", slope)
                if has_strong_momentum and normalized_slope > strong_slope_threshold:
                    return "strong_up", 85.0, desc
                else:
                    return "up", 70.0, desc

            elif trend == "bearish":
                desc = get_trend_desc("bearish", slope)
                # §10 bull/bear symmetry: scores mirror the bullish branch above
                # (strong_down 85, down 70). Standard trend-following research
                # treats both directions as equally tradeable for a system that
                # trades LONG and SHORT — directional clarity is the quality
                # signal, not the direction itself. Prior asymmetric scores
                # (15 / 30) implicitly weighted "buy-and-hold direction" and
                # produced a structural drag on SHORT performance via the
                # composite regime score (trend_score * 0.3 at L121).
                if has_strong_momentum and normalized_slope < -strong_slope_threshold:
                    return "strong_down", 85.0, desc
                else:
                    return "down", 70.0, desc

            else:
                # Swing structure returned neutral/sideways
                # Use mode-specific ADX thresholds to confirm
                min_adx = self.thresholds["min_trend_adx"]

                logger.info(
                    f"🔄 {timeframe_label} SIDEWAYS: swing_trend={trend} | "
                    f"strong_swings={len(strong_swings)}/5 | has_momentum={has_strong_momentum}"
                )

                if adx_value is not None:
                    if adx_value < min_adx:
                        logger.info(
                            f"✅ {timeframe_label}: SIDEWAYS (ADX={adx_value:.1f} < {min_adx}, confirmed ranging)"
                        )
                        return "sideways", 50.0, f"Ranging (ADX={adx_value:.1f})"
                    elif adx_value < min_adx + 5:
                        logger.info(
                            f"✅ {timeframe_label}: SIDEWAYS (ADX={adx_value:.1f}, weak trend)"
                        )
                        return "sideways", 50.0, f"Weak Trend (ADX={adx_value:.1f})"
                    else:
                        # ADX > threshold but no swing pattern = choppy/transitional
                        logger.info(
                            f"✅ {timeframe_label}: SIDEWAYS (ADX={adx_value:.1f} but no clear swing pattern)"
                        )
                        return "sideways", 50.0, "Choppy / Transitional"
                else:
                    logger.info(
                        f"✅ {timeframe_label}: SIDEWAYS (no swing pattern, ADX unavailable)"
                    )
                    return "sideways", 50.0, "Choppy / No Trend"

        except Exception as e:
            error_type = type(e).__name__
            df_len = len(df) if df is not None else 0
            logger.warning(
                f"🔍 Swing Structure DIAGNOSTIC [{timeframe_label}]: Detection FAILED with {error_type}. "
                f"DataFrame length: {df_len}, Error: {str(e)[:150]}"
            )
            logger.debug(
                f"🔍 Swing Structure DIAGNOSTIC [{timeframe_label}]: Full error", exc_info=True
            )

            raise ValueError(f"REGIME_INPUT_UNAVAILABLE: {timeframe_label} trend calculation failed") from e

    def _detect_trend(self, data: MultiTimeframeData):
        """
        Detect global trend using the highest available timeframe.
        """
        # Use highest available TF for trend
        # Sort manually to ensure correct order (1d > 4h > 1h)
        # We prefer 1d if available, else 4h
        preferred_order = ["1w", "1d", "4h", "1h", "30m", "15m"]
        htf = None

        for tf in preferred_order:
            if tf in data.timeframes:
                htf = tf
                break

        if not htf and data.timeframes:
            # Fallback to whatever is there
            htf = list(data.timeframes.keys())[0]

        if not htf:
            raise ValueError("REGIME_INPUT_UNAVAILABLE: no trend timeframe")

        df = data.timeframes[htf]
        # Unpack 3 values, return 2 for compatibility with existing callers
        trend, score, _ = self.analyze_timeframe_trend(df, htf)
        return trend, score

    def _detect_volatility(self, indicators: IndicatorSet, current_price: Optional[float] = None):
        """
        Detect volatility regime from ATR as PERCENTAGE of price.

        CRITICAL FIX: ATR 1470 @ $97k BTC = 1.5% (normal)
                      ATR 1470 @ $10k ETH = 14.7% (chaotic)

        Old code used absolute ATR which was completely broken.

        Returns: (vol_label, score)
        """
        if not getattr(indicators, "by_timeframe", None):
            raise ValueError("VOLATILITY_INPUT_UNAVAILABLE: missing timeframe indicators")
        primary_tf = _highest_duration_tf(indicators.by_timeframe.keys())
        if primary_tf is None:
            raise ValueError("VOLATILITY_INPUT_UNAVAILABLE: missing primary timeframe")
        ind = indicators.by_timeframe[primary_tf]
        atr_value = getattr(ind, "atr", None)
        frame = getattr(ind, "dataframe", None)
        if frame is not None and "close" in frame.columns:
            if frame.empty:
                raise ValueError("VOLATILITY_INPUT_UNAVAILABLE: empty price frame")
            current_price = frame["close"].iloc[-1]
        elif current_price is None:
            # Legacy snapshots may only retain their BB middle price proxy.
            current_price = getattr(ind, "bb_middle", None)
        try:
            if isinstance(atr_value, (bool, np.bool_)) or isinstance(current_price, (bool, np.bool_)):
                raise ValueError("boolean ATR or price")
            atr = float(atr_value)
            current_price = float(current_price)
            if not math.isfinite(atr) or atr < 0 or not math.isfinite(current_price) or current_price <= 0:
                raise ValueError("ATR/price must be finite with ATR >= 0 and price > 0")
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"VOLATILITY_INPUT_UNAVAILABLE: {exc}") from exc
        atr_pct = (atr / current_price) * 100
        if not math.isfinite(atr_pct):
            raise ValueError("VOLATILITY_INPUT_UNAVAILABLE: nonfinite ATR percentage")

        # Also check ATR trend (expanding = building momentum)
        atr_series = getattr(ind, "atr_series", None)
        atr_expanding = False

        if atr_series is not None and len(atr_series) >= 10:
            recent_atr = atr_series[-5:]
            older_atr = atr_series[-10:-5]
            recent_avg = sum(recent_atr) / len(recent_atr)
            older_avg = sum(older_atr) / len(older_atr)

            if recent_avg > older_avg * 1.15:  # 15% increase
                atr_expanding = True

        # Classify based on ATR% — bands calibrated for the DAILY timeframe
        # (the structural TF now selected by _highest_duration_tf). Derived from
        # backend/diagnostics/daily_atr_baseline.py (BTC + alt basket, n~2900):
        # BTC daily ranges ~1.8-6.7% (median 3.24%), pooled basket p10≈2.8 /
        # p50≈5.3 / p80≈7.4 / p95≈9.8. Anchored so BTC's normal day reads
        # "normal" and BTC's max reads "elevated" (never "chaotic"); alts at
        # 8-10% read "volatile/chaotic". Old bands (0.8/1.5/2.5/4.0) were tuned
        # for the wrong TF (5-minute ATR%) and mislabelled daily ranges.

        if atr_pct < 2.5:
            # Compressed — genuinely dead daily range (below pooled ~p10)
            logger.info(
                f"Volatility: compressed (ATR={atr:.1f}, price={current_price:.1f}, ATR%={atr_pct:.2f}%)"
            )
            return "compressed", 60.0

        elif atr_pct < 5.0:
            # Normal healthy daily volatility (~p10..p50)
            logger.info(
                f"Volatility: normal (ATR={atr:.1f}, price={current_price:.1f}, ATR%={atr_pct:.2f}%)"
            )
            return "normal", 75.0

        elif atr_pct < 7.0:
            # Elevated but manageable (~p50..p80)
            if atr_expanding:
                logger.info(
                    f"Volatility: elevated_expanding (ATR={atr:.1f}, price={current_price:.1f}, ATR%={atr_pct:.2f}%)"
                )
                return "elevated", 55.0
            else:
                logger.info(
                    f"Volatility: elevated (ATR={atr:.1f}, price={current_price:.1f}, ATR%={atr_pct:.2f}%)"
                )
                return "elevated", 60.0

        elif atr_pct < 9.5:
            # High volatility - caution (~p80..p95)
            logger.info(
                f"Volatility: volatile (ATR={atr:.1f}, price={current_price:.1f}, ATR%={atr_pct:.2f}%)"
            )
            return "volatile", 40.0

        else:
            # Chaotic/crash conditions (>~p95 daily ATR%)
            logger.warning(
                f"Volatility: chaotic (ATR={atr:.1f}, price={current_price:.1f}, ATR%={atr_pct:.2f}%)"
            )
            return "chaotic", 20.0

    def _detect_liquidity(self, data: MultiTimeframeData):
        """
        Detect liquidity regime from volume.

        Returns: (liquidity_label, score)
        """
        tf = _highest_duration_tf(data.timeframes)
        if tf is None:
            raise ValueError("REGIME_INPUT_UNAVAILABLE: missing volume history")
        df = data.timeframes[tf]
        if len(df) < 25 or "volume" not in df:
            raise ValueError("REGIME_INPUT_UNAVAILABLE: insufficient volume history")
        volume = df["volume"].tail(25).to_numpy(dtype=float)
        if not np.isfinite(volume).all() or (volume < 0).any():
            raise ValueError("REGIME_INPUT_UNAVAILABLE: invalid volume history")
        avg_vol = volume[:-5].mean()
        recent_vol = volume[-5:].mean()
        if avg_vol <= 0:
            raise ValueError("REGIME_INPUT_UNAVAILABLE: no historical participation")
        ratio = recent_vol / avg_vol

        if ratio < 0.5:
            return "thin", 40.0
        elif ratio < 1.5:
            return "healthy", 75.0
        else:
            return "heavy", 65.0

    def _detect_risk_appetite(self, dominance=None) -> tuple[str, float]:
        """
        Detect risk appetite using REAL dominance data with PROPER thresholds.

        FIXED:
        1. Uses proper thresholds (USDT.D > 9% for risk_off, not 8%)
        2. Checks BTC.D absolute level AND trend direction
        3. More granular classifications

        Returns: (risk_label, score)
        """
        try:
            from backend.analysis.dominance_service import get_dominance_for_macro

            btc_dom, alt_dom, stable_dom = dominance if dominance is not None else get_dominance_for_macro()

            logger.info(
                f"Risk Appetite: BTC.D={btc_dom:.1f}%, Alt.D={alt_dom:.1f}%, Stable.D={stable_dom:.1f}%"
            )

            # 1. Check USDT.D (flight to stables = risk off)
            # USDT.D normal range in 2025/2026: 3.5-4.5%
            # USDT.D risk-off: 5.0-6.0%
            # USDT.D extreme risk-off: >6.0%

            if stable_dom > 6.0:
                # Extreme risk-off: money fleeing to stables
                logger.info("Risk: extreme_risk_off (high stable dominance)")
                return "extreme_risk_off", 15.0

            elif stable_dom > 5.0:
                # Risk-off: significant stable allocation
                logger.info("Risk: risk_off (elevated stable dominance)")
                return "risk_off", 30.0

            elif stable_dom > 4.5:
                # Cautious: moderate stable allocation
                logger.info("Risk: cautious (moderate stable dominance)")
                return "cautious", 45.0

            # 2. Check BTC.D level for capital flow direction
            if btc_dom > 58.0:
                # BTC.D high = capital flight to BTC (alt weakness)
                logger.info("Risk: btc_flight (BTC.D high)")
                return "btc_flight", 40.0

            elif btc_dom > 55.0:
                # BTC.D moderately high = BTC dominant
                logger.info("Risk: btc_dominant (BTC.D moderately high)")
                return "btc_dominant", 50.0

            elif btc_dom < 52.0:
                # BTC.D low = alt season brewing
                logger.info("Risk: alt_season (BTC.D low)")
                return "alt_season", 85.0

            elif btc_dom < 54.0:
                # BTC.D lowish = some alt strength
                logger.info("Risk: risk_on (BTC.D low, alt strength)")
                return "risk_on", 75.0

            else:
                # BTC.D stable in normal range (54-55%)
                if stable_dom < 4.0:
                    # Low stable allocation = healthy risk-on
                    logger.info("Risk: risk_on (low stable allocation)")
                    return "risk_on", 80.0
                else:
                    # Moderate stable allocation = balanced
                    logger.info("Risk: balanced (normal conditions)")
                    return "balanced", 60.0

        except Exception as e:
            logger.warning("RISK_APPETITE_UNAVAILABLE: %s", e)
            raise ValueError(f"DOMINANCE_UNAVAILABLE: {e}") from e

    def _generate_composite_label(self, dim: RegimeDimensions) -> str:
        """Generate composite regime label from dimensions."""

        if dim.volatility == "chaotic":
            return "chaotic_volatile"
        if dim.trend == "sideways" and dim.risk_appetite == "risk_off":
            return "choppy_risk_off"
        elif dim.trend in ["strong_up", "up"] and dim.risk_appetite == "risk_on":
            return "bullish_risk_on"
        elif dim.trend in ["strong_down", "down"] and dim.risk_appetite == "risk_off":
            return "bearish_risk_off"
        elif dim.volatility == "chaotic":
            return "chaotic_volatile"
        elif dim.trend == "sideways" and dim.volatility == "compressed":
            return "range_coiling"
        else:
            return f"{dim.trend}_{dim.volatility}"

    def _score_symbol_regime(self, trend, volatility) -> float:
        """Score symbol regime quality (0-100)."""
        score = 50.0

        # Reward clear trends
        if trend in ["strong_up", "strong_down"]:
            score += 25
        elif trend in ["up", "down"]:
            score += 15

        # Reward normal volatility, penalize chaos
        if volatility == "normal":
            score += 20
        elif volatility == "elevated":
            score += 5
        elif volatility == "compressed":
            score += 10  # Coiling can be good
        elif volatility == "chaotic":
            score -= 20

        return max(0.0, min(100.0, score))

    def _confirmed_view(self, observed):
        """Confirm structural trend only; fresh volatility/risk must never be hidden."""
        if self._confirmed_regime is None:
            return observed
        dims = replace(observed.dimensions, trend=self._confirmed_regime.dimensions.trend)
        trend_score = self._confirmed_regime.trend_score
        return replace(observed, dimensions=dims, trend_score=trend_score,
                       composite=self._generate_composite_label(dims),
                       score=trend_score * .3 + observed.volatility_score * .2
                       + observed.liquidity_score * .2 + observed.risk_score * .2
                       + observed.derivatives_score * .1)

    def _apply_hysteresis(self, new_regime: MarketRegime, evidence_id=None) -> MarketRegime:
        """
        Apply hysteresis with confirmation counter to prevent regime flip-flopping.

        NEW LOGIC:
        1. If no confirmed regime yet, accept the first one
        2. If new regime matches confirmed, reset pending counter
        3. If new regime differs, increment pending counter
        4. Only switch when pending counter reaches confirmation_required
        """
        if evidence_id is not None:
            # Global callers supply canonical UTC close times. A replayed or
            # regressed observation cannot advance structural confirmation.
            if self._last_confirmation_evidence is not None and evidence_id <= self._last_confirmation_evidence:
                return self._confirmed_regime or new_regime
            self._last_confirmation_evidence = evidence_id

        # First regime - accept and confirm immediately
        if self._confirmed_regime is None:
            self._confirmed_regime = new_regime
            self._pending_regime = None
            self._pending_count = 0
            self.regime_history.append(new_regime)
            logger.info(
                "📊 REGIME CONFIRMED (initial): %s (score=%.1f)",
                new_regime.composite, new_regime.score
            )
            return new_regime

        # Same as confirmed - reset any pending transition
        if new_regime.dimensions.trend == self._confirmed_regime.dimensions.trend:
            if self._pending_regime is not None:
                logger.info(
                    "📊 REGIME STABLE: %s (pending %s cancelled after %d readings)",
                    self._confirmed_regime.composite,
                    self._pending_regime,
                    self._pending_count
                )
            self._pending_regime = None
            self._pending_count = 0
            
            # Update confirmed with fresh data (same label, new scores)
            self._confirmed_regime = new_regime
            self.regime_history.append(new_regime)
            if len(self.regime_history) > 20:
                self.regime_history = self.regime_history[-20:]
            return new_regime

        # Different from confirmed - check if continuing pending or starting new
        if self._pending_regime == new_regime.dimensions.trend:
            # Same as pending - increment counter
            self._pending_count += 1
            logger.info(
                "📊 REGIME TRANSITION PENDING: %s → %s (%d/%d)",
                self._confirmed_regime.composite,
                self._pending_regime,
                self._pending_count,
                self._confirmation_required
            )
            
            # Check if confirmed
            if self._pending_count >= self._confirmation_required:
                old_regime = self._confirmed_regime.composite
                self._confirmed_regime = new_regime
                self._pending_regime = None
                self._pending_count = 0
                self.regime_history.append(new_regime)
                if len(self.regime_history) > 20:
                    self.regime_history = self.regime_history[-20:]
                logger.info(
                    "✅ REGIME CONFIRMED (changed): %s → %s (score=%.1f)",
                    old_regime, new_regime.composite, new_regime.score
                )
                return new_regime
            
            # Not yet confirmed - return confirmed regime
            return self._confirmed_regime
        else:
            # Different from both confirmed AND pending - start new pending
            logger.info(
                "📊 REGIME TRANSITION STARTED: %s → %s (1/%d)",
                self._confirmed_regime.composite,
                new_regime.composite,
                self._confirmation_required
            )
            self._pending_regime = new_regime.dimensions.trend
            self._pending_count = 1
            
            # Keep history
            self.regime_history.append(new_regime)
            if len(self.regime_history) > 20:
                self.regime_history = self.regime_history[-20:]
            
            # Return confirmed until transition completes
            return self._confirmed_regime

    def get_confirmed_regime(self) -> Optional["MarketRegime"]:
        """Return the current confirmed regime, or None if not yet established."""
        return self._confirmed_regime


# Singleton instance
_regime_detector = None


def get_regime_detector(mode_profile: str = "stealth_balanced") -> RegimeDetector:
    """Get singleton regime detector instance with mode profile."""
    global _regime_detector
    if _regime_detector is None or _regime_detector.mode_profile != mode_profile:
        _regime_detector = RegimeDetector(mode_profile)
    return _regime_detector
