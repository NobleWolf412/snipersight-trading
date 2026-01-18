"""
Market Regime Detector - Multi-dimensional analysis

Detects market regime across multiple dimensions with hysteresis
to prevent regime flip-flopping.
"""
from typing import List, Optional
from datetime import datetime
import logging

from backend.shared.models.regime import (
    MarketRegime, RegimeDimensions, SymbolRegime
)
from backend.shared.models.data import MultiTimeframeData
from backend.shared.models.indicators import IndicatorSet

logger = logging.getLogger(__name__)


class RegimeDetector:
    """Detects market regime across multiple dimensions"""
    
    def __init__(self, mode_profile: str = "stealth_balanced"):
        self.regime_history: List[MarketRegime] = []
        self.hysteresis_bars = 3  # Require N bars before flip
        self.mode_profile = mode_profile
        
        # Cache for performance (Gap #4)
        self._global_regime_cache = None
        self._global_regime_cache_time = None
        self._global_regime_ttl = 300  # 5 minutes for BTC global regime
        
        self._symbol_regime_cache = {}  # {symbol: (regime, timestamp)}
        self._symbol_regime_ttl = 60  # 1 minute for individual symbols
        
        # Mode-specific regime detection thresholds
        self.MODE_REGIME_THRESHOLDS = {
            "macro_surveillance": {  # OVERWATCH: Stricter trend requirements
                "min_trend_adx": 25,
                "strong_trend_adx": 35,
                "strong_momentum_slope": 3.0
            },
            "stealth_balanced": {  # STEALTH: Balanced (default)
                "min_trend_adx": 20,
                "strong_trend_adx": 30,
                "strong_momentum_slope": 2.0
            },
            "intraday_aggressive": {  # STRIKE: More permissive for intraday
                "min_trend_adx": 15,
                "strong_trend_adx": 25,
                "strong_momentum_slope": 1.5
            },
            "precision": {  # SURGICAL: Micro-trend detection
                "min_trend_adx": 12,
                "strong_trend_adx": 20,
                "strong_momentum_slope": 1.0
            }
        }
        
        # Get mode-specific thresholds
        self.thresholds = self.MODE_REGIME_THRESHOLDS.get(
            mode_profile, 
            self.MODE_REGIME_THRESHOLDS["stealth_balanced"]
        )
        
    def detect_global_regime(
        self,
        btc_data: MultiTimeframeData,
        btc_indicators: IndicatorSet,
    ) -> MarketRegime:
        """
        Detect global market regime from BTC as market leader.
        
        Args:
            btc_data: BTC multi-timeframe OHLCV data
            btc_indicators: BTC technical indicators
            
        Returns:
            MarketRegime with all dimensions analyzed
        """
        
        # Check cache (Gap #4)
        if self._global_regime_cache is not None and self._global_regime_cache_time is not None:
            age = (datetime.utcnow() - self._global_regime_cache_time).total_seconds()
            if age < self._global_regime_ttl:
                logger.debug(f"🗄️ Returning cached global regime (age={age:.1f}s)")
                return self._global_regime_cache
        
        # 1. Trend Regime (HTF structure + MA slope)
        trend, trend_score = self._detect_trend(btc_data)
        
        # 2. Volatility Regime (ATR-based)
        volatility, vol_score = self._detect_volatility(btc_indicators)
        
        # 3. Liquidity Regime (volume-based)
        liquidity, liq_score = self._detect_liquidity(btc_data)
        
        # 4. Risk Appetite (simplified - would use BTC.D, USDT.D)
        risk_appetite, risk_score = self._detect_risk_appetite()
        
        # 5. Derivatives (placeholder - needs funding rate data)
        derivatives, deriv_score = "balanced", 50.0
        
        dimensions = RegimeDimensions(
            trend=trend,
            volatility=volatility,
            liquidity=liquidity,
            risk_appetite=risk_appetite,
            derivatives=derivatives
        )
        
        # Composite label
        composite = self._generate_composite_label(dimensions)
        
        # Overall score (weighted average)
        score = (
            trend_score * 0.3 +
            vol_score * 0.2 +
            liq_score * 0.2 +
            risk_score * 0.2 +
            deriv_score * 0.1
        )
        
        regime = MarketRegime(
            dimensions=dimensions,
            composite=composite,
            score=score,
            timestamp=datetime.utcnow(),
            trend_score=trend_score,
            volatility_score=vol_score,
            liquidity_score=liq_score,
            risk_score=risk_score,
            derivatives_score=deriv_score
        )
        
        # Apply hysteresis to prevent flip-flopping
        regime = self._apply_hysteresis(regime)
        
        # Cache result (Gap #4)
        self._global_regime_cache = regime
        self._global_regime_cache_time = datetime.utcnow()
        
        logger.info(
            "Global regime: %s (score=%.1f) - trend=%s, vol=%s, liq=%s, risk=%s",
            regime.composite, regime.score, trend, volatility, liquidity, risk_appetite
        )
        
        return regime
    
    def detect_symbol_regime(
        self,
        symbol: str,
        data: MultiTimeframeData,
        indicators: IndicatorSet,
        cycle_context: Optional["CycleContext"] = None  # NEW: Cycle-aware override
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
                if (cycle_context.in_dcl_zone or 
                    cycle_context.in_wcl_zone or 
                    cycle_context.phase == CyclePhase.ACCUMULATION):
                    logger.info(f"🔄 Regime override: {trend} → sideways at cycle low zone (allows longs)")
                    trend = "sideways"
                    score += 10  # Bonus for counter-trend at extreme
            
            # Override bullish regime at distribution with LTR
            if trend in ("up", "strong_up"):
                if (cycle_context.translation == CycleTranslation.LTR or
                    cycle_context.phase == CyclePhase.DISTRIBUTION):
                    logger.info(f"🔄 Regime override: {trend} → sideways at cycle high/LTR (allows shorts)")
                    trend = "sideways"
                    score += 10  # Bonus for counter-trend at extreme
        
        regime = SymbolRegime(
            symbol=symbol,
            trend=trend,
            volatility=volatility,
            score=score
        )
        
        # Cache result (Gap #4)
        self._symbol_regime_cache[symbol] = (regime, datetime.utcnow())
        
        return regime
    
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
        
        if df is None or len(df) < 50:
            return "sideways", 50.0, "Insufficient data"
        
        # === 1. Calculate ADX for secondary confirmation ===
        adx_value = None
        adx_diagnostic = {}  # Track WHY ADX might fail
        
        try:
            # Diagnostic: Check input data quality
            df_len = len(df)
            has_required_cols = all(col in df.columns for col in ['high', 'low', 'close'])
            
            if not has_required_cols:
                logger.warning(f"🔍 ADX DIAGNOSTIC [{timeframe_label}]: Missing required columns. Have: {df.columns.tolist()}")
                adx_diagnostic['reason'] = 'missing_columns'
                raise ValueError(f"Missing required columns for ADX calculation")
            
            logger.debug(f"🔍 ADX DIAGNOSTIC [{timeframe_label}]: Starting calculation with {df_len} bars")
            
            # Calculate ADX manually (14-period standard)
            df_copy = df.copy()
            
            # True Range
            df_copy['tr'] = df_copy.apply(
                lambda row: max(
                    row['high'] - row['low'],
                    abs(row['high'] - df_copy['close'].shift(1).loc[row.name]) if row.name > df_copy.index[0] else row['high'] - row['low'],
                    abs(row['low'] - df_copy['close'].shift(1).loc[row.name]) if row.name > df_copy.index[0] else row['high'] - row['low']
                ), axis=1
            )
            
            # Diagnostic: Check TR calculation
            tr_valid_count = df_copy['tr'].notna().sum()
            logger.debug(f"🔍 ADX DIAGNOSTIC [{timeframe_label}]: TR calculated, {tr_valid_count}/{df_len} valid values")
            
            # +DM and -DM
            df_copy['plus_dm'] = df_copy['high'].diff()
            df_copy['minus_dm'] = -df_copy['low'].diff()
            df_copy['plus_dm'] = df_copy.apply(
                lambda row: row['plus_dm'] if row['plus_dm'] > row['minus_dm'] and row['plus_dm'] > 0 else 0, axis=1
            )
            df_copy['minus_dm'] = df_copy.apply(
                lambda row: row['minus_dm'] if row['minus_dm'] > row['plus_dm'] and row['minus_dm'] > 0 else 0, axis=1
            )
            
            # Smoothed averages (14-period)
            period = 14
            df_copy['atr14'] = df_copy['tr'].rolling(period).mean()
            df_copy['plus_di'] = 100 * (df_copy['plus_dm'].rolling(period).mean() / df_copy['atr14'])
            df_copy['minus_di'] = 100 * (df_copy['minus_dm'].rolling(period).mean() / df_copy['atr14'])
            
            # Diagnostic: Check DI values
            plus_di_final = df_copy['plus_di'].iloc[-1] if not df_copy['plus_di'].isna().all() else None
            minus_di_final = df_copy['minus_di'].iloc[-1] if not df_copy['minus_di'].isna().all() else None
            logger.debug(f"🔍 ADX DIAGNOSTIC [{timeframe_label}]: +DI={plus_di_final:.1f if plus_di_final is not None else None}, -DI={minus_di_final:.1f if minus_di_final is not None else None}")
            
            # DX and ADX
            df_copy['dx'] = 100 * abs(df_copy['plus_di'] - df_copy['minus_di']) / (df_copy['plus_di'] + df_copy['minus_di'] + 1e-10)
            df_copy['adx'] = df_copy['dx'].rolling(period).mean()
            
            # Extract final ADX value
            adx_value = df_copy['adx'].iloc[-1]
            
            # Diagnostic: Check if ADX is valid
            if adx_value is None or (isinstance(adx_value, float) and (adx_value != adx_value)):  # NaN check
                logger.warning(f"🔍 ADX DIAGNOSTIC [{timeframe_label}]: Calculated ADX is None/NaN. DX series has {df_copy['dx'].notna().sum()} valid values")
                adx_diagnostic['reason'] = 'nan_result'
                adx_diagnostic['dx_valid_count'] = df_copy['dx'].notna().sum()
                adx_value = None
            else:
                logger.info(f"✅ ADX [{timeframe_label}]: {adx_value:.1f} (valid calculation)")
                adx_diagnostic['reason'] = 'success'
                adx_diagnostic['value'] = adx_value
                
        except Exception as e:
            error_type = type(e).__name__
            logger.warning(f"🔍 ADX DIAGNOSTIC [{timeframe_label}]: Calculation FAILED with {error_type}: {str(e)[:100]}")
            logger.debug(f"🔍 ADX DIAGNOSTIC [{timeframe_label}]: Full error: {e}", exc_info=True)
            adx_diagnostic['reason'] = f'exception_{error_type}'
            adx_diagnostic['error'] = str(e)[:200]
            adx_value = None
        
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
                logger.info(f"📊 {timeframe_label} SWINGS (last 5): " + 
                           " | ".join([f"{s.swing_type.upper()}@{s.price:.2f} (str={s.strength:.1f})" 
                                       for s in recent_5]))
            else:
                logger.info(f"📊 {timeframe_label} SWINGS: No swings detected")
            
            # Check momentum strength
            recent_swings = swing_struct.swing_points[-5:] if len(swing_struct.swing_points) >= 5 else []
            strong_swings = [s for s in recent_swings if s.strength > 1.5]
            has_strong_momentum = len(strong_swings) >= 3
            
            # Check MA slope
            df_copy = df.copy()
            df_copy['ma20'] = df_copy['close'].rolling(20).mean()
            
            if not df_copy['ma20'].isna().all():
                ma20_now = df_copy['ma20'].iloc[-1]
                ma20_before = df_copy['ma20'].iloc[-20]
                slope = (ma20_now - ma20_before) / ma20_before * 100
                
                atr = df_copy['high'].rolling(14).max() - df_copy['low'].rolling(14).min()
                current_price = df_copy['close'].iloc[-1]
                atr_pct = (atr.iloc[-1] / current_price * 100) if current_price > 0 else 1.0
                normalized_slope = slope / max(atr_pct, 0.5)
                
                logger.info(f"📈 {timeframe_label} MA20: now={ma20_now:.2f} | 20bars_ago={ma20_before:.2f} | "
                           f"slope={slope:.2f}% | norm_slope={normalized_slope:.2f} | price={current_price:.2f}")
            else:
                normalized_slope = 0
                logger.info(f"📈 {timeframe_label} MA20: Insufficient data for slope")
            
            # === 3. Classification with ADX Confirmation ===
            
            # Get mode-specific thresholds
            strong_slope_threshold = self.thresholds["strong_momentum_slope"]
            
            # If swing structure found a trend
            if trend == 'bullish':
                if has_strong_momentum and normalized_slope > strong_slope_threshold:
                    adx_str = f"{adx_value:.1f}" if adx_value is not None else "N/A"
                    logger.info(f"Regime {timeframe_label}: STRONG_UP (swing=bullish, slope={normalized_slope:.1f}, ADX={adx_str})")
                    return "strong_up", 85.0, "Impulsive Buy Pressure"
                else:
                    adx_str = f"{adx_value:.1f}" if adx_value is not None else "N/A"
                    logger.info(f"Regime {timeframe_label}: UP (swing=bullish, ADX={adx_str})")
                    return "up", 70.0, "Higher Highs & Lows"
            
            elif trend == 'bearish':
                if has_strong_momentum and normalized_slope < -strong_slope_threshold:
                    adx_str = f"{adx_value:.1f}" if adx_value is not None else "N/A"
                    logger.info(f"Regime {timeframe_label}: STRONG_DOWN (swing=bearish, slope={normalized_slope:.1f}, ADX={adx_str})")
                    return "strong_down", 15.0, "Heavy Sell Pressure"
                else:
                    adx_str = f"{adx_value:.1f}" if adx_value is not None else "N/A"
                    logger.info(f"Regime {timeframe_label}: DOWN (swing=bearish, ADX={adx_str})")
                    return "down", 30.0, "Lower Highs & Lows"
            
            else:
                # Swing structure returned neutral/sideways
                # Use mode-specific ADX thresholds to confirm
                min_adx = self.thresholds["min_trend_adx"]
                
                logger.info(f"🔄 {timeframe_label} SIDEWAYS: swing_trend={trend} | "
                           f"strong_swings={len(strong_swings)}/5 | has_momentum={has_strong_momentum}")
                
                if adx_value is not None:
                    if adx_value < min_adx:
                        logger.info(f"✅ {timeframe_label}: SIDEWAYS (ADX={adx_value:.1f} < {min_adx}, confirmed ranging)")
                        return "sideways", 50.0, f"Ranging (ADX={adx_value:.1f})"
                    elif adx_value < min_adx + 5:
                        logger.info(f"✅ {timeframe_label}: SIDEWAYS (ADX={adx_value:.1f}, weak trend)")
                        return "sideways", 50.0, f"Weak Trend (ADX={adx_value:.1f})"
                    else:
                        # ADX > threshold but no swing pattern = choppy/transitional
                        logger.info(f"✅ {timeframe_label}: SIDEWAYS (ADX={adx_value:.1f} but no clear swing pattern)")
                        return "sideways", 50.0, "Choppy / Transitional"
                else:
                    logger.info(f"✅ {timeframe_label}: SIDEWAYS (no swing pattern, ADX unavailable)")
                    return "sideways", 50.0, "Choppy / No Trend"
        
        except Exception as e:
            error_type = type(e).__name__
            df_len = len(df) if df is not None else 0
            logger.warning(f"🔍 Swing Structure DIAGNOSTIC [{timeframe_label}]: Detection FAILED with {error_type}. "
                          f"DataFrame length: {df_len}, Error: {str(e)[:150]}")
            logger.debug(f"🔍 Swing Structure DIAGNOSTIC [{timeframe_label}]: Full error", exc_info=True)
            
            # Fallback to simple MA slope
            if df.empty or 'close' not in df:
                return "sideways", 50.0, "Insufficient Data"
                
            df_copy = df.copy()
            df_copy['ma20'] = df_copy['close'].rolling(20).mean()
            
            if df_copy['ma20'].iloc[-10:].isna().all():
                return "sideways", 50.0, "Insufficient Data"
            
            slope = (df_copy['ma20'].iloc[-1] - df_copy['ma20'].iloc[-10]) / df_copy['ma20'].iloc[-10] * 100
            
            if slope > 3:
                return "up", 70.0, "Momentum Divergence"
            elif slope < -3:
                return "down", 35.0, "Momentum Breakdown"
            else:
                return "sideways", 50.0, "Flat Structure"

    def _detect_trend(self, data: MultiTimeframeData):
        """
        Detect global trend using the highest available timeframe.
        """
        # Use highest available TF for trend
        # Sort manually to ensure correct order (1d > 4h > 1h)
        # We prefer 1d if available, else 4h
        preferred_order = ['1w', '1d', '4h', '1h', '30m', '15m']
        htf = None
        
        for tf in preferred_order:
            if tf in data.timeframes:
                htf = tf
                break
        
        if not htf and data.timeframes:
            # Fallback to whatever is there
            htf = list(data.timeframes.keys())[0]
            
        if not htf:
            return "sideways", 50.0
            
        df = data.timeframes[htf]
        # Unpack 3 values, return 2 for compatibility with existing callers
        trend, score, _ = self.analyze_timeframe_trend(df, htf)
        return trend, score
    
    def _detect_volatility(self, indicators: IndicatorSet):
        """
        Detect volatility regime from ATR as PERCENTAGE of price.
        
        CRITICAL FIX: ATR 1470 @ $97k BTC = 1.5% (normal)
                      ATR 1470 @ $10k ETH = 14.7% (chaotic)
        
        Old code used absolute ATR which was completely broken.
        
        Returns: (vol_label, score)
        """
        # Type check: ensure we received IndicatorSet, not IndicatorSnapshot
        if not hasattr(indicators, 'by_timeframe'):
            logger.error(
                "CRITICAL: _detect_volatility received %s instead of IndicatorSet. "
                "Check get_atr_regime() call chain.",
                type(indicators).__name__
            )
            return "normal", 75.0
        
        if not indicators.by_timeframe:
            return "normal", 75.0
        
        # Get highest timeframe indicator
        primary_tf = sorted(indicators.by_timeframe.keys(), reverse=True)[0]
        ind = indicators.by_timeframe[primary_tf]
        
        if ind.atr is None:
            return "normal", 75.0
        
        # CRITICAL: Get current price to calculate ATR%
        current_price = None
        
        # Try to get price from indicator dataframe
        if hasattr(ind, 'dataframe') and ind.dataframe is not None and 'close' in ind.dataframe.columns:
            current_price = ind.dataframe['close'].iloc[-1]
        
        # Try to get price from bb_middle (it's close to current price)
        if current_price is None and ind.bb_middle is not None:
            current_price = ind.bb_middle
        
        if current_price is None or current_price <= 0:
            logger.warning("Cannot determine current price for ATR%%, using raw ATR fallback")
            # Fallback: assume reasonable normalized ATR
            atr = ind.atr
            if atr < 100:
                return "compressed", 60.0
            elif atr < 300:
                return "normal", 75.0
            else:
                return "elevated", 55.0
        
        # Calculate ATR as PERCENTAGE of price (this is the critical fix)
        atr_pct = (ind.atr / current_price) * 100
        
        # Also check ATR trend (expanding = building momentum)
        atr_series = getattr(ind, 'atr_series', None)
        atr_expanding = False
        
        if atr_series and len(atr_series) >= 10:
            recent_atr = atr_series[-5:]
            older_atr = atr_series[-10:-5]
            recent_avg = sum(recent_atr) / len(recent_atr)
            older_avg = sum(older_atr) / len(older_atr)
            
            if recent_avg > older_avg * 1.15:  # 15% increase
                atr_expanding = True
        
        # Classify based on ATR% (proper volatility-adjusted thresholds)
        # These thresholds are for crypto - adjust if needed for other assets
        
        if atr_pct < 0.8:
            # Very compressed - coiling for a move
            logger.info(f"Volatility: compressed (ATR={ind.atr:.1f}, price={current_price:.1f}, ATR%={atr_pct:.2f}%)")
            return "compressed", 60.0
        
        elif atr_pct < 1.5:
            # Normal healthy volatility
            logger.info(f"Volatility: normal (ATR={ind.atr:.1f}, price={current_price:.1f}, ATR%={atr_pct:.2f}%)")
            return "normal", 75.0
        
        elif atr_pct < 2.5:
            # Elevated but manageable
            if atr_expanding:
                logger.info(f"Volatility: elevated_expanding (ATR={ind.atr:.1f}, price={current_price:.1f}, ATR%={atr_pct:.2f}%)")
                return "elevated", 55.0
            else:
                logger.info(f"Volatility: elevated (ATR={ind.atr:.1f}, price={current_price:.1f}, ATR%={atr_pct:.2f}%)")
                return "elevated", 60.0
        
        elif atr_pct < 4.0:
            # High volatility - caution
            logger.info(f"Volatility: volatile (ATR={ind.atr:.1f}, price={current_price:.1f}, ATR%={atr_pct:.2f}%)")
            return "volatile", 40.0
        
        else:
            # Chaotic/crash conditions (>4% ATR)
            logger.warning(f"Volatility: chaotic (ATR={ind.atr:.1f}, price={current_price:.1f}, ATR%={atr_pct:.2f}%)")
            return "chaotic", 20.0
    
    def _detect_liquidity(self, data: MultiTimeframeData):
        """
        Detect liquidity regime from volume.
        
        Returns: (liquidity_label, score)
        """
        tfs = sorted(data.timeframes.keys())
        if not tfs:
            return "healthy", 60.0
        
        df = data.timeframes[tfs[0]]
        if len(df) < 20:
            return "healthy", 60.0
        
        # Compare recent volume to average
        avg_vol = df['volume'].tail(20).mean()
        recent_vol = df['volume'].tail(5).mean()
        
        ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0
        
        if ratio < 0.5:
            return "thin", 40.0
        elif ratio < 1.5:
            return "healthy", 75.0
        else:
            return "heavy", 65.0
    
    def _detect_risk_appetite(self) -> tuple[str, float]:
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
            btc_dom, alt_dom, stable_dom = get_dominance_for_macro()
            
            logger.info(f"Risk Appetite: BTC.D={btc_dom:.1f}%, Alt.D={alt_dom:.1f}%, Stable.D={stable_dom:.1f}%")
            
            # 1. Check USDT.D (flight to stables = risk off)
            # USDT.D normal range: 3-7%
            # USDT.D risk-off: 8-12%
            # USDT.D extreme risk-off: >12%
            
            if stable_dom > 12.0:
                # Extreme risk-off: money fleeing to stables
                logger.info("Risk: extreme_risk_off (high stable dominance)")
                return "extreme_risk_off", 15.0
            
            elif stable_dom > 9.0:
                # Risk-off: significant stable allocation
                logger.info("Risk: risk_off (elevated stable dominance)")
                return "risk_off", 30.0
            
            elif stable_dom > 7.5:
                # Cautious: moderate stable allocation
                logger.info("Risk: cautious (moderate stable dominance)")
                return "cautious", 45.0
            
            # 2. Check BTC.D level for capital flow direction
            if btc_dom > 60.0:
                # BTC.D high = capital flight to BTC (alt weakness)
                logger.info("Risk: btc_flight (BTC.D high)")
                return "btc_flight", 40.0
            
            elif btc_dom > 55.0:
                # BTC.D moderately high = BTC dominant
                logger.info("Risk: btc_dominant (BTC.D moderately high)")
                return "btc_dominant", 50.0
            
            elif btc_dom < 48.0:
                # BTC.D low = alt season brewing
                logger.info("Risk: alt_season (BTC.D low)")
                return "alt_season", 85.0
            
            elif btc_dom < 52.0:
                # BTC.D lowish = some alt strength
                logger.info("Risk: risk_on (BTC.D low, alt strength)")
                return "risk_on", 75.0
            
            else:
                # BTC.D stable in normal range (52-55%)
                if stable_dom < 5.0:
                    # Low stable allocation = healthy risk-on
                    logger.info("Risk: risk_on (low stable allocation)")
                    return "risk_on", 80.0
                else:
                    # Moderate stable allocation = balanced
                    logger.info("Risk: balanced (normal conditions)")
                    return "balanced", 60.0
                
        except Exception as e:
            # Fallback if DominanceService unavailable
            logger.debug(f"Risk appetite detection fallback: {e}")
            return "balanced", 50.0
    
    def _generate_composite_label(self, dim: RegimeDimensions) -> str:
        """Generate composite regime label from dimensions."""
        
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
    
    def _apply_hysteresis(self, new_regime: MarketRegime) -> MarketRegime:
        """
        Apply hysteresis to prevent regime flip-flopping.
        
        Only accept regime change if it persists for N bars.
        """
        if not self.regime_history:
            self.regime_history.append(new_regime)
            return new_regime
        
        last_regime = self.regime_history[-1]
        
        # If composite label hasn't changed, accept new regime
        if last_regime.composite == new_regime.composite:
            self.regime_history.append(new_regime)
            # Keep history limited
            if len(self.regime_history) > 20:
                self.regime_history = self.regime_history[-20:]
            return new_regime
        
        # Check if we have enough history for hysteresis
        if len(self.regime_history) < self.hysteresis_bars:
            self.regime_history.append(new_regime)
            return new_regime
        
        # Check if last N regimes were stable
        recent_labels = [r.composite for r in self.regime_history[-self.hysteresis_bars:]]
        if all(label == last_regime.composite for label in recent_labels):
            # Stable regime, require more confirmation before flip
            # Store new but return old
            self.regime_history.append(new_regime)
            if len(self.regime_history) > 20:
                self.regime_history = self.regime_history[-20:]
            logger.debug("Regime hysteresis: keeping %s despite new %s", last_regime.composite, new_regime.composite)
            return last_regime
        
        # Regime already in transition, accept change
        self.regime_history.append(new_regime)
        if len(self.regime_history) > 20:
            self.regime_history = self.regime_history[-20:]
        return new_regime


# Singleton instance
_regime_detector = None

def get_regime_detector(mode_profile: str = "stealth_balanced") -> RegimeDetector:
    """Get singleton regime detector instance with mode profile."""
    global _regime_detector
    if _regime_detector is None or _regime_detector.mode_profile != mode_profile:
        _regime_detector = RegimeDetector(mode_profile)
    return _regime_detector
