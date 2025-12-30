"""
Regime Engine Module

Handles higher-order market context analysis for the Trade Planner, including:
- ATR Regime Classification (Delegates to RegimeDetector for system-wide consistency)
- HTF Bias Factor Calculation (Proximity Gradients)
- HTF Fibonacci Alignment Checks
"""

import logging
from typing import Optional, Dict
import pandas as pd

from backend.shared.config.planner_config import PlannerConfig
from backend.analysis.fibonacci import calculate_fib_levels, FibLevel
from backend.analysis.regime_detector import get_regime_detector
from backend.shared.models.indicators import IndicatorSet

logger = logging.getLogger(__name__)


def get_atr_regime(
    indicators,  # Accepts IndicatorSet OR IndicatorSnapshot (for backward compat)
    current_price: Optional[float] = None
) -> str:
    """
    Get ATR regime using system-standard RegimeDetector.
    
    Acts as a bridge/adapter for the Planner to consume Analysis logic.
    Prioritizes RegimeDetector's logic over local calculations.
    
    Args:
        indicators: IndicatorSet OR IndicatorSnapshot (for backward compatibility).
                   If a single IndicatorSnapshot is passed, it's wrapped in a temp IndicatorSet.
        current_price: Optional current price (used by detector fallback)
        
    Returns:
        Regime label: "compressed", "normal", "elevated", "volatile", "chaotic"
    """
    # Handle both IndicatorSet and IndicatorSnapshot for backward compatibility
    # risk_engine.py passes a single IndicatorSnapshot, entry_engine.py passes IndicatorSet
    if not hasattr(indicators, 'by_timeframe'):
        # It's a single IndicatorSnapshot - wrap it in a temporary IndicatorSet
        from backend.shared.models.indicators import IndicatorSnapshot
        if isinstance(indicators, IndicatorSnapshot):
            # Create a minimal IndicatorSet wrapper with the snapshot under a generic TF key
            class _TempIndicatorSet:
                def __init__(self, snapshot):
                    self.by_timeframe = {'_primary': snapshot}
            indicators = _TempIndicatorSet(indicators)
            logger.debug("get_atr_regime: Wrapped single IndicatorSnapshot in temp IndicatorSet")
        else:
            # Completely unknown type - log error and return fallback
            logger.error(f"get_atr_regime: Unknown indicator type {type(indicators).__name__}")
            return "normal"
    
    # Use the internal detector logic
    # RegimeDetector._detect_volatility returns (label, score)
    label, score = get_regime_detector()._detect_volatility(indicators)
    
    # Map detector labels to planner labels if necessary
    # Detector: compressed, normal, elevated, volatile, chaotic
    # Planner Config expects: variable keys. Standard mapping:
    # calm -> compressed
    # normal -> normal
    # elevated -> elevated
    # explosive -> volatile/chaotic
    
    # We will return the detector's raw label and let the PlannerConfig adapt via keys
    # or we map it here to match legacy planner config keys ("calm", "normal", "elevated", "explosive")
    
    # Mapping for backward compatibility with PlannerConfig keys
    mapping = {
        "compressed": "calm",
        "normal": "normal",
        "elevated": "elevated",
        "volatile": "explosive",  # > 2.5%
        "chaotic": "explosive"    # > 4.0%
    }
    
    mapped = mapping.get(label, "normal")
    logger.debug(f"ATR Regime: {label} -> {mapped} (score={score})")
    return mapped


def _check_htf_fib_alignment(
    entry_price: float,
    ohlcv_data: dict,
    tolerance_pct: float = 1.0,
    mode_profile: str = 'balanced'
) -> tuple[bool, Optional[str], float]:
    """
    Check if entry price aligns with HTF Fibonacci retracement levels.
    
    Mode-aware behavior:
    - Scalp modes (Strike, Surgical): Skip (Fib alignment is noise)
    - Swing modes: Use mode-appropriate HTFs
    
    Only checks 50% and 61.8% levels (statistically meaningful).
    
    Args:
        entry_price: The calculated entry price from SMC structure
        ohlcv_data: Dict of {timeframe: DataFrame} with candle data
        tolerance_pct: How close entry must be to Fib (default 1%)
        mode_profile: Scanner mode for mode-aware filtering
        
    Returns:
        Tuple of (is_aligned, alignment_note, boost_value)
    """
    if not ohlcv_data:
        return False, None, 0.0
    
    profile = (mode_profile or 'balanced').lower()
    
    # Skip Fibs entirely for scalp/intraday modes
    if profile in ('precision', 'surgical', 'intraday_aggressive', 'strike'):
        return False, None, 0.0
    
    # Mode-specific HTF timeframes for Fib alignment
    fib_tf_map = {
        'macro_surveillance': ('1w', '1d'),  # Overwatch: Weekly + Daily
        'overwatch': ('1w', '1d'),
        'stealth_balanced': ('1d', '4h'),    # Stealth: Daily + 4H
        'stealth': ('1d', '4h'),
        'balanced': ('1d', '4h'),
    }
    
    htf_timeframes = fib_tf_map.get(profile, ('1d', '4h'))
    
    for tf in htf_timeframes:
        df = ohlcv_data.get(tf) or ohlcv_data.get(tf.lower()) or ohlcv_data.get(tf.upper())
        if df is None or len(df) < 30:
            continue
            
        try:
            # Find swing range in last 50 candles
            recent = df.tail(50)
            swing_high = recent['high'].max()
            swing_low = recent['low'].min()
            
            if swing_high <= swing_low:
                continue
            
            # Determine trend direction
            current_price = df.iloc[-1]['close']
            mid_range = (swing_high + swing_low) / 2
            trend_direction = 'bullish' if current_price > mid_range else 'bearish'
            
            # Calculate Fib levels
            fib_levels = calculate_fib_levels(
                swing_high=swing_high,
                swing_low=swing_low,
                trend_direction=trend_direction,
                timeframe=tf
            )
            
            # Check if entry aligns with 50% or 61.8% Fib
            for fib in fib_levels:
                distance_pct = abs(entry_price - fib.price) / fib.price * 100
                
                if distance_pct <= tolerance_pct:
                    boost = 7.0 if fib.ratio == 0.618 else 5.0
                    note = f"Entry aligns with {tf.upper()} Fib {fib.display_ratio}"
                    return True, note, boost
                    
        except Exception as e:
            logger.debug(f"Fib alignment check failed for {tf}: {e}")
            continue
    
    return False, None, 0.0


def _calculate_htf_bias_factor(
    distance_atr: float,
    planner_cfg: PlannerConfig
) -> float:
    """Calculate HTF bias offset factor using linear gradient.
    
    Closer to HTF level -> smaller offsets (factor approaches min_factor)
    Further from HTF level -> normal offsets (factor approaches 1.0)
    
    Args:
        distance_atr: Distance to nearest HTF level in ATRs (always >= 0)
        planner_cfg: Planner configuration
        
    Returns:
        Offset scaling factor between min_factor and 1.0
    """
    if not planner_cfg.htf_bias_enabled:
        return 1.0
    
    max_dist = planner_cfg.htf_bias_max_atr_distance
    min_factor = planner_cfg.htf_bias_offset_min_factor
    
    # Clamp distance to [0, max_dist]
    distance_clamped = min(max(distance_atr, 0.0), max_dist)
    
    # Linear interpolation: t = 0 (on level) -> min_factor, t = 1 (far) -> 1.0
    t = distance_clamped / max_dist if max_dist > 0 else 1.0
    
    return min_factor + (1.0 - min_factor) * t
