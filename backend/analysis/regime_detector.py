"""
Market Regime Detector - Multi-dimensional analysis

Detects market regime across multiple dimensions with hysteresis
to prevent regime flip-flopping.
"""
from typing import List
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
    
    def __init__(self):
        self.regime_history: List[MarketRegime] = []
        self.hysteresis_bars = 3  # Require N bars before flip
        
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
        
        logger.info(
            "Global regime: %s (score=%.1f) - trend=%s, vol=%s, liq=%s, risk=%s",
            regime.composite, regime.score, trend, volatility, liquidity, risk_appetite
        )
        
        return regime
    
    def detect_symbol_regime(
        self,
        symbol: str,
        data: MultiTimeframeData,
        indicators: IndicatorSet
    ) -> SymbolRegime:
        """
        Detect per-symbol local regime.
        
        Args:
            symbol: Trading pair symbol
            data: Symbol multi-timeframe data
            indicators: Symbol indicators
            
        Returns:
            SymbolRegime with local trend/vol assessment
        """
        
        trend, _ = self._detect_trend(data)
        volatility, _ = self._detect_volatility(indicators)
        
        # Symbol score based on trend clarity + volatility quality
        score = self._score_symbol_regime(trend, volatility)
        
        return SymbolRegime(
            symbol=symbol,
            trend=trend,
            volatility=volatility,
            score=score
        )
    
    def _detect_trend(self, data: MultiTimeframeData):
        """
        Detect trend using REAL swing structure, not bar-to-bar noise.
        
        Uses existing swing_structure detector for proper HH/HL/LH/LL analysis.
        
        Returns: (trend_label, score)
        """
        from backend.strategy.smc.swing_structure import detect_swing_structure
        
        # Use highest available TF for trend
        tfs = sorted(data.timeframes.keys(), reverse=True)
        if not tfs:
            return "sideways", 50.0
            
        df = data.timeframes[tfs[0]]
        if len(df) < 50:  # Need more data for reliable swing detection
            return "sideways", 50.0
        
        try:
            # Use your EXISTING swing structure detector
            swing_struct = detect_swing_structure(df, lookback=15)
            
            # It already gives you trend: 'bullish', 'bearish', or 'neutral'
            trend = swing_struct.trend
            
            # Also check momentum strength (are recent swings strong?)
            recent_swings = swing_struct.swing_points[-5:] if len(swing_struct.swing_points) >= 5 else []
            strong_swings = [s for s in recent_swings if s.strength > 1.5]
            has_strong_momentum = len(strong_swings) >= 3
            
            # Also check MA slope for confirmation
            df_copy = df.copy()
            df_copy['ma20'] = df_copy['close'].rolling(20).mean()
            
            if not df_copy['ma20'].iloc[-20:].isna().all():
                # Calculate slope over full MA period (20 bars for 20MA)
                slope = (df_copy['ma20'].iloc[-1] - df_copy['ma20'].iloc[-20]) / df_copy['ma20'].iloc[-20] * 100
                
                # Normalize by volatility
                atr = df_copy['high'].rolling(14).max() - df_copy['low'].rolling(14).min()
                current_price = df_copy['close'].iloc[-1]
                atr_pct = (atr.iloc[-1] / current_price * 100) if current_price > 0 else 1.0
                normalized_slope = slope / max(atr_pct, 0.5)
            else:
                normalized_slope = 0
            
            # Classify based on swing structure + momentum
            if trend == 'bullish':
                if has_strong_momentum and normalized_slope > 2.0:
                    logger.debug("Trend: strong_up (swing structure + momentum)")
                    return "strong_up", 85.0
                else:
                    logger.debug("Trend: up (swing structure, weak momentum)")
                    return "up", 70.0
            
            elif trend == 'bearish':
                if has_strong_momentum and normalized_slope < -2.0:
                    logger.debug("Trend: strong_down (swing structure + momentum)")
                    return "strong_down", 15.0
                else:
                    logger.debug("Trend: down (swing structure, weak momentum)")
                    return "down", 30.0
            
            else:
                logger.debug("Trend: sideways (no clear structure)")
                return "sideways", 50.0
        
        except Exception as e:
            logger.warning(f"Swing structure detection failed: {e}, using fallback")
            # Fallback to simple MA slope if swing detection fails
            df_copy = df.copy()
            df_copy['ma20'] = df_copy['close'].rolling(20).mean()
            
            if df_copy['ma20'].iloc[-10:].isna().all():
                return "sideways", 50.0
            
            slope = (df_copy['ma20'].iloc[-1] - df_copy['ma20'].iloc[-10]) / df_copy['ma20'].iloc[-10] * 100
            
            if slope > 3:
                return "up", 70.0
            elif slope < -3:
                return "down", 35.0
            else:
                return "sideways", 50.0
    
    def _detect_volatility(self, indicators: IndicatorSet):
        """
        Detect volatility regime from ATR as PERCENTAGE of price.
        
        CRITICAL FIX: ATR 1470 @ $97k BTC = 1.5% (normal)
                      ATR 1470 @ $10k ETH = 14.7% (chaotic)
        
        Old code used absolute ATR which was completely broken.
        
        Returns: (vol_label, score)
        """
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
_regime_detector = RegimeDetector()

def get_regime_detector() -> RegimeDetector:
    """Get singleton regime detector instance."""
    return _regime_detector
