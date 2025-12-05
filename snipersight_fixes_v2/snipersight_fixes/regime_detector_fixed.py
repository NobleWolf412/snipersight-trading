"""
FIXED Market Regime Detector - Drop-in Replacement

This file contains fixed versions of the regime detection methods.

FIXES:
1. _detect_trend() - Uses real swing structure instead of bar-to-bar noise
2. _detect_volatility() - Uses ATR% (percentage) instead of absolute ATR values
3. _detect_risk_appetite() - Actually uses dominance data with proper thresholds

INSTALLATION:
Replace the methods in backend/analysis/regime_detector.py with these versions.
"""

from typing import List, Optional, Dict, Tuple
from datetime import datetime
import logging
import pandas as pd

from backend.shared.models.regime import (
    MarketRegime, RegimeDimensions, SymbolRegime
)
from backend.shared.models.data import MultiTimeframeData
from backend.shared.models.indicators import IndicatorSet

logger = logging.getLogger(__name__)


class RegimeDetectorFixed:
    """Fixed regime detector with proper calculations"""
    
    def __init__(self):
        self.regime_history: List[MarketRegime] = []
        self.hysteresis_bars = 3
    
    # ============================================================================
    # FIX #1: TREND DETECTION - Uses real swing structure
    # ============================================================================
    
    def _detect_trend(self, data: MultiTimeframeData) -> Tuple[str, float]:
        """
        FIXED: Detect trend using REAL swing structure, not bar-to-bar noise.
        
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
    
    # ============================================================================
    # FIX #2: VOLATILITY DETECTION - Uses ATR% not absolute ATR
    # ============================================================================
    
    def _detect_volatility(self, indicators: IndicatorSet) -> Tuple[str, float]:
        """
        FIXED: Detect volatility using ATR as PERCENTAGE of price.
        
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
            logger.warning(f"Cannot determine current price for ATR%, using raw ATR fallback")
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
        atr_contracting = False
        
        if atr_series and len(atr_series) >= 10:
            recent_atr = atr_series[-5:]
            older_atr = atr_series[-10:-5]
            recent_avg = sum(recent_atr) / len(recent_atr)
            older_avg = sum(older_atr) / len(older_atr)
            
            if recent_avg > older_avg * 1.15:  # 15% increase
                atr_expanding = True
            elif recent_avg < older_avg * 0.85:  # 15% decrease
                atr_contracting = True
        
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
    
    # ============================================================================
    # FIX #3: RISK APPETITE - Actually uses dominance with proper thresholds
    # ============================================================================
    
    def _detect_risk_appetite(self, dominance_data: Optional[Dict] = None) -> Tuple[str, float]:
        """
        FIXED: Detect risk appetite using REAL dominance data with PROPER thresholds.
        
        Changes:
        1. Actually accepts dominance_data parameter (old code ignored it)
        2. Uses proper thresholds (USDT.D > 8% is edge, should be >10% for risk_off)
        3. Checks BTC.D TREND (increasing = flight, decreasing = alt season)
        4. Falls back gracefully if dominance unavailable
        
        Args:
            dominance_data: Dict with:
                - btc_dominance: float
                - usdt_dominance: float (or stable_dominance)
                - btc_dominance_30d_change: float (optional)
        
        Returns: (risk_label, score)
        """
        # Try to get dominance from parameter first
        if dominance_data:
            btc_d = dominance_data.get('btc_dominance')
            usdt_d = dominance_data.get('usdt_dominance') or dominance_data.get('stable_dominance')
            btc_d_30d_change = dominance_data.get('btc_dominance_30d_change', 0)
        else:
            # Fallback: try to fetch from DominanceService
            try:
                from backend.analysis.dominance_service import get_dominance_for_macro
                btc_d, alt_d, stable_d = get_dominance_for_macro()
                usdt_d = stable_d
                btc_d_30d_change = 0  # Can't get historical without more work
            except Exception as e:
                logger.debug(f"Dominance data unavailable: {e}")
                return "balanced", 50.0
        
        # Check if we have valid data
        if btc_d is None or usdt_d is None:
            logger.debug("Risk appetite: no dominance data, returning balanced")
            return "balanced", 50.0
        
        logger.info(f"Risk Appetite: BTC.D={btc_d:.1f}% (Δ30d={btc_d_30d_change:+.1f}%), USDT.D={usdt_d:.1f}%")
        
        # 1. Check USDT.D (flight to stables = risk off)
        # USDT.D normal range: 3-7%
        # USDT.D risk-off: 8-12%
        # USDT.D extreme risk-off: >12%
        
        if usdt_d > 12.0:
            # Extreme risk-off: money fleeing to stables
            logger.info("Risk: extreme_risk_off (high stable dominance)")
            return "extreme_risk_off", 15.0
        
        elif usdt_d > 9.0:
            # Risk-off: significant stable allocation
            logger.info("Risk: risk_off (elevated stable dominance)")
            return "risk_off", 30.0
        
        elif usdt_d > 7.5:
            # Cautious: moderate stable allocation
            logger.info("Risk: cautious (moderate stable dominance)")
            return "cautious", 45.0
        
        # 2. Check BTC.D TREND (not just absolute value)
        # BTC.D increasing = capital consolidating into BTC (altcoin bleed)
        # BTC.D decreasing = capital flowing to alts (alt season)
        
        if btc_d > 60.0 and btc_d_30d_change > 3.0:
            # BTC.D high AND rising fast = capital flight to BTC
            logger.info("Risk: btc_flight (BTC.D high and rising)")
            return "btc_flight", 40.0
        
        elif btc_d > 58.0 and btc_d_30d_change > 1.0:
            # BTC.D high and slowly rising = BTC dominance
            logger.info("Risk: btc_dominant (BTC.D high)")
            return "btc_dominant", 50.0
        
        elif btc_d < 48.0 and btc_d_30d_change < -2.0:
            # BTC.D low and falling = alt season brewing
            logger.info("Risk: alt_season (BTC.D low and falling)")
            return "alt_season", 85.0
        
        elif btc_d < 50.0:
            # BTC.D lowish = some alt strength
            logger.info("Risk: risk_on (BTC.D low, alt strength)")
            return "risk_on", 75.0
        
        else:
            # BTC.D stable in normal range (50-58%)
            if usdt_d < 5.0:
                # Low stable allocation = healthy risk-on
                logger.info("Risk: risk_on (low stable allocation)")
                return "risk_on", 80.0
            else:
                # Moderate stable allocation = balanced
                logger.info("Risk: balanced (normal conditions)")
                return "balanced", 60.0
    
    # ============================================================================
    # UPDATED: detect_global_regime to use dominance_data parameter
    # ============================================================================
    
    def detect_global_regime(
        self,
        btc_data: MultiTimeframeData,
        btc_indicators: IndicatorSet,
        dominance_data: Optional[Dict] = None  # NEW PARAMETER
    ) -> MarketRegime:
        """
        Detect global market regime from BTC as market leader.
        
        UPDATED: Now accepts dominance_data parameter for risk appetite detection.
        
        Args:
            btc_data: BTC multi-timeframe OHLCV data
            btc_indicators: BTC technical indicators
            dominance_data: Optional dict with btc_dominance, usdt_dominance, etc.
            
        Returns:
            MarketRegime with all dimensions analyzed
        """
        
        # 1. Trend Regime (FIXED - uses real swing structure)
        trend, trend_score = self._detect_trend(btc_data)
        
        # 2. Volatility Regime (FIXED - uses ATR%)
        volatility, vol_score = self._detect_volatility(btc_indicators)
        
        # 3. Liquidity Regime (volume-based - no changes needed)
        liquidity, liq_score = self._detect_liquidity(btc_data)
        
        # 4. Risk Appetite (FIXED - uses dominance data)
        risk_appetite, risk_score = self._detect_risk_appetite(dominance_data)
        
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
            "🌍 Global Regime: %s (score=%.1f) | trend=%s(%.0f) vol=%s(%.0f) liq=%s(%.0f) risk=%s(%.0f)",
            regime.composite, regime.score, 
            trend, trend_score, 
            volatility, vol_score,
            liquidity, liq_score, 
            risk_appetite, risk_score
        )
        
        return regime
    
    # ============================================================================
    # HELPER METHODS (copy these if not present)
    # ============================================================================
    
    def _detect_liquidity(self, data: MultiTimeframeData) -> Tuple[str, float]:
        """
        Detect liquidity regime from volume.
        (No changes needed - this was already correct)
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
    
    def _generate_composite_label(self, dim: RegimeDimensions) -> str:
        """Generate composite regime label from dimensions."""
        
        if dim.trend == "sideways" and dim.risk_appetite == "risk_off":
            return "choppy_risk_off"
        elif dim.trend in ["strong_up", "up"] and dim.risk_appetite == "risk_on":
            return "bullish_risk_on"
        elif dim.trend in ["strong_down", "down"] and dim.risk_appetite == "risk_off":
            return "bearish_risk_off"
        elif dim.volatility == "chaotic":
            return "chaotic"
        elif dim.trend == "sideways" and dim.volatility in ["compressed", "normal"]:
            return "consolidation"
        elif dim.trend in ["strong_up", "up"]:
            return "uptrend"
        elif dim.trend in ["strong_down", "down"]:
            return "downtrend"
        else:
            return "mixed"
    
    def _apply_hysteresis(self, regime: MarketRegime) -> MarketRegime:
        """
        Apply hysteresis to prevent flip-flopping.
        Require N bars of consistent regime before switching.
        """
        if not self.regime_history:
            self.regime_history.append(regime)
            return regime
        
        last_regime = self.regime_history[-1]
        
        # If regime changed, check if it's been consistent
        if regime.composite != last_regime.composite:
            # Count recent occurrences of new regime
            recent_count = sum(
                1 for r in self.regime_history[-self.hysteresis_bars:]
                if r.composite == regime.composite
            )
            
            # Need hysteresis_bars of consistent new regime to flip
            if recent_count < self.hysteresis_bars - 1:
                # Not enough evidence, keep old regime
                return last_regime
        
        self.regime_history.append(regime)
        
        # Keep history bounded
        if len(self.regime_history) > 100:
            self.regime_history = self.regime_history[-100:]
        
        return regime


# ============================================================================
# INTEGRATION INSTRUCTIONS
# ============================================================================

"""
HOW TO INTEGRATE THESE FIXES:

Option 1: Replace entire RegimeDetector class
----------------------------------------------
1. Backup your current backend/analysis/regime_detector.py
2. Replace the RegimeDetector class with RegimeDetectorFixed
3. Rename RegimeDetectorFixed to RegimeDetector
4. Keep all imports and other code the same

Option 2: Replace individual methods
-------------------------------------
1. Open backend/analysis/regime_detector.py
2. Replace _detect_trend() with the fixed version above
3. Replace _detect_volatility() with the fixed version above
4. Replace _detect_risk_appetite() with the fixed version above
5. Update detect_global_regime() signature to accept dominance_data parameter

Then update orchestrator.py:
-----------------------------
In backend/engine/orchestrator.py, around line 260-280, update regime detection:

# OLD CODE:
btc_data = prefetched_data.get('BTC/USDT')
self.current_regime = self._detect_global_regime(prefetched_btc_data=btc_data)

# NEW CODE:
btc_data = prefetched_data.get('BTC/USDT')

# Get dominance data
dominance_data = None
try:
    if self.macro_context and hasattr(self.macro_context, 'btc_dominance'):
        dominance_data = {
            'btc_dominance': self.macro_context.btc_dominance,
            'usdt_dominance': self.macro_context.stable_dominance,
            'btc_dominance_30d_change': 0  # TODO: track 30d change
        }
except Exception:
    pass

# Pass dominance data to regime detector
self.current_regime = self._detect_global_regime(
    prefetched_btc_data=btc_data,
    dominance_data=dominance_data
)


EXPECTED IMPACT:
----------------
After these fixes, your regime scores should improve significantly:

Before: "chaotic" volatility (30 pts) + "risk_off" (30 pts) = ~45-50 regime score
After:  "normal" volatility (75 pts) + "balanced" (50-60 pts) = ~60-70 regime score

This alone could increase your signal rate from 10% to 20-30%.
"""
