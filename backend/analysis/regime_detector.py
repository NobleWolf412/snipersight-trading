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
        Detect trend regime from price action.
        
        Returns: (trend_label, score)
        """
        # Use highest available TF for trend
        tfs = sorted(data.timeframes.keys(), reverse=True)
        if not tfs:
            return "sideways", 50.0
            
        df = data.timeframes[tfs[0]]
        if len(df) < 20:
            return "sideways", 50.0
        
        # Calculate 20-period MA slope
        df_copy = df.copy()
        df_copy['ma20'] = df_copy['close'].rolling(20).mean()
        
        if df_copy['ma20'].iloc[-10:].isna().all():
            return "sideways", 50.0
        
        slope = (df_copy['ma20'].iloc[-1] - df_copy['ma20'].iloc[-10]) / df_copy['ma20'].iloc[-10] * 100
        
        # Check for HH/HL pattern (bullish) or LH/LL (bearish)
        highs = df_copy['high'].tail(10)
        lows = df_copy['low'].tail(10)
        
        hh_count = sum(
            1 for i in range(1, len(highs)) 
            if highs.iloc[i] > highs.iloc[i-1]
        )
        hl_count = sum(
            1 for i in range(1, len(lows)) 
            if lows.iloc[i] > lows.iloc[i-1]
        )
        
        # Classify trend
        if slope > 5 and hh_count >= 6:
            return "strong_up", 85.0
        elif slope > 2 and hh_count >= 4:
            return "up", 70.0
        elif slope < -5 and hl_count <= 3:
            return "strong_down", 20.0
        elif slope < -2 and hl_count <= 5:
            return "down", 35.0
        else:
            return "sideways", 50.0
    
    def _detect_volatility(self, indicators: IndicatorSet):
        """
        Detect volatility regime from ATR.
        
        Returns: (vol_label, score)
        """
        if not indicators.by_timeframe:
            return "normal", 50.0
        
        # Get highest timeframe indicator
        primary_tf = sorted(indicators.by_timeframe.keys(), reverse=True)[0]
        ind = indicators.by_timeframe[primary_tf]
        
        if ind.atr is None:
            return "normal", 50.0
        
        # Classify based on ATR magnitude
        # (This is simplified - ideal would compare to rolling ATR)
        atr = ind.atr
        
        if atr < 100:
            return "compressed", 60.0  # Low vol can be good (coiling)
        elif atr < 300:
            return "normal", 75.0
        elif atr < 600:
            return "elevated", 55.0
        else:
            return "chaotic", 30.0
    
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
    
    def _detect_risk_appetite(self):
        """
        Detect risk appetite regime.
        
        Placeholder - would use BTC.D, USDT.D, ALT.D data.
        
        Returns: (risk_label, score)
        """
        # Default to risk_on for now
        return "risk_on", 60.0
    
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
