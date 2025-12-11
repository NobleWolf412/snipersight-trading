"""
Pullback Setup Detector

Detects counter-trend pullback opportunities when:
1. Price is extended from 4H 20-EMA (>3% distance)
2. Volume shows exhaustion (declining on rally or spike on reversal)
3. SMC structure confirms (bearish OB or CHoCH for shorts, vice versa for longs)

When all three conditions are met, the counter-trend penalty is removed,
allowing high-probability mean-reversion trades.
"""

import pandas as pd
import numpy as np
from typing import Optional, Literal
from dataclasses import dataclass
from loguru import logger


@dataclass
class PullbackSetup:
    """Result of pullback detection."""
    is_pullback: bool
    direction: Literal['LONG', 'SHORT']  # Direction of the pullback trade
    extension_pct: float  # How far price is from EMA (signed)
    volume_exhausted: bool
    volume_signal: str  # Description of volume pattern
    smc_confirms: bool
    smc_signal: str  # Which SMC structure confirmed
    override_counter_trend: bool  # If True, remove counter-trend penalty
    confidence: float  # 0-100 confidence in pullback setup
    rationale: str


def calculate_ema(df: pd.DataFrame, period: int = 20, column: str = 'close') -> pd.Series:
    """Calculate Exponential Moving Average."""
    return df[column].ewm(span=period, adjust=False).mean()


def is_price_extended(
    df: pd.DataFrame,
    threshold_pct: float = 3.0,
    ema_period: int = 20
) -> tuple[bool, float, str]:
    """
    Check if current price is extended from the EMA.
    
    Args:
        df: OHLCV DataFrame
        threshold_pct: Minimum % distance to consider "extended"
        ema_period: EMA period (default 20)
        
    Returns:
        Tuple of (is_extended, extension_pct, direction_hint)
        direction_hint: 'SHORT' if price above EMA (bearish pullback expected)
                       'LONG' if price below EMA (bullish pullback expected)
    """
    if df is None or len(df) < ema_period + 5:
        return False, 0.0, 'NEUTRAL'
    
    ema = calculate_ema(df, period=ema_period)
    current_price = df.iloc[-1]['close']
    current_ema = ema.iloc[-1]
    
    if current_ema <= 0:
        return False, 0.0, 'NEUTRAL'
    
    extension_pct = ((current_price - current_ema) / current_ema) * 100
    
    is_extended = abs(extension_pct) >= threshold_pct
    
    # Positive extension = price above EMA = bearish pullback expected (SHORT)
    # Negative extension = price below EMA = bullish pullback expected (LONG)
    if extension_pct > 0:
        direction_hint = 'SHORT'
    elif extension_pct < 0:
        direction_hint = 'LONG'
    else:
        direction_hint = 'NEUTRAL'
    
    return is_extended, extension_pct, direction_hint


def is_volume_exhausted(
    df: pd.DataFrame,
    lookback: int = 4,
    spike_threshold: float = 2.0
) -> tuple[bool, str]:
    """
    Check for volume exhaustion patterns.
    
    Two patterns indicate exhaustion:
    1. Declining volume on consecutive same-direction candles
    2. Volume spike on reversal candle (first opposite-direction candle)
    
    Args:
        df: OHLCV DataFrame
        lookback: Number of candles to analyze
        spike_threshold: Multiple of avg volume to consider "spike"
        
    Returns:
        Tuple of (is_exhausted, signal_description)
    """
    if df is None or len(df) < lookback + 20:
        return False, "Insufficient data"
    
    recent = df.tail(lookback + 1)  # +1 to check reversal candle
    
    # Calculate average volume for comparison
    avg_volume = df['volume'].tail(20).mean()
    
    # Check if we have consecutive green or red candles with declining volume
    candle_colors = []
    volumes = []
    
    for i in range(len(recent) - 1):  # Exclude last candle initially
        row = recent.iloc[i]
        is_green = row['close'] > row['open']
        candle_colors.append('green' if is_green else 'red')
        volumes.append(row['volume'])
    
    # Pattern 1: Declining volume on rally (for bearish pullback)
    if len(candle_colors) >= 3:
        # Check last 3 candles (excluding most recent)
        last_3_colors = candle_colors[-3:]
        last_3_volumes = volumes[-3:]
        
        # All green with declining volume = buying exhaustion
        if all(c == 'green' for c in last_3_colors):
            declining = all(last_3_volumes[i] > last_3_volumes[i+1] 
                          for i in range(len(last_3_volumes)-1))
            if declining:
                return True, "Declining volume on rally (buying exhaustion)"
        
        # All red with declining volume = selling exhaustion
        if all(c == 'red' for c in last_3_colors):
            declining = all(last_3_volumes[i] > last_3_volumes[i+1] 
                          for i in range(len(last_3_volumes)-1))
            if declining:
                return True, "Declining volume on selloff (selling exhaustion)"
    
    # Pattern 2: Volume spike on reversal candle
    last_candle = recent.iloc[-1]
    prev_candle = recent.iloc[-2]
    
    last_is_green = last_candle['close'] > last_candle['open']
    prev_is_green = prev_candle['close'] > prev_candle['open']
    
    # Check for reversal (color change) with volume spike
    if last_is_green != prev_is_green:
        if last_candle['volume'] >= avg_volume * spike_threshold:
            color = 'green' if last_is_green else 'red'
            return True, f"Volume spike on {color} reversal candle ({last_candle['volume']/avg_volume:.1f}x avg)"
    
    # Pattern 3: Current candles have below-average volume (weak push)
    recent_avg = recent['volume'].mean()
    if recent_avg < avg_volume * 0.7:
        return True, f"Below-average volume on recent candles ({recent_avg/avg_volume:.1f}x avg)"
    
    return False, "No volume exhaustion detected"


def check_smc_pullback_confirmation(
    smc_snapshot,
    pullback_direction: str
) -> tuple[bool, str]:
    """
    Check if SMC structure confirms the pullback direction.
    
    For SHORT pullbacks: Need bearish OB or bearish CHoCH
    For LONG pullbacks: Need bullish OB or bullish CHoCH
    
    Args:
        smc_snapshot: SMCSnapshot with OBs, FVGs, BOS/CHoCH
        pullback_direction: 'SHORT' or 'LONG'
        
    Returns:
        Tuple of (confirms, signal_description)
    """
    if smc_snapshot is None:
        return False, "No SMC data"
    
    # Get order blocks
    order_blocks = getattr(smc_snapshot, 'order_blocks', []) or []
    bos_choch = getattr(smc_snapshot, 'bos_choch', None)
    
    expected_ob_direction = 'bearish' if pullback_direction == 'SHORT' else 'bullish'
    
    # Check for confirming order block on 1H or 4H
    htf_timeframes = ['1h', '4h']
    for ob in order_blocks:
        if hasattr(ob, 'timeframe') and hasattr(ob, 'direction'):
            if ob.timeframe in htf_timeframes and ob.direction == expected_ob_direction:
                return True, f"{expected_ob_direction.capitalize()} OB on {ob.timeframe}"
    
    # Check for CHoCH confirmation
    if bos_choch:
        choch_direction = getattr(bos_choch, 'direction', None)
        if pullback_direction == 'SHORT' and choch_direction == 'bearish':
            return True, "Bearish CHoCH confirms reversal"
        if pullback_direction == 'LONG' and choch_direction == 'bullish':
            return True, "Bullish CHoCH confirms reversal"
    
    return False, "No SMC confirmation"


def detect_pullback_setup(
    df_4h: pd.DataFrame,
    smc_snapshot,
    requested_direction: str,  # The direction user/scanner wants to trade
    extension_threshold: float = 3.0
) -> PullbackSetup:
    """
    Detect if conditions are right for a counter-trend pullback trade.
    
    Args:
        df_4h: 4H OHLCV DataFrame
        smc_snapshot: SMCSnapshot with detected structures
        requested_direction: 'LONG' or 'SHORT' - the trade we want to take
        extension_threshold: Minimum % from EMA to consider extended
        
    Returns:
        PullbackSetup with detection results
    """
    # Default result
    default = PullbackSetup(
        is_pullback=False,
        direction=requested_direction,
        extension_pct=0.0,
        volume_exhausted=False,
        volume_signal="",
        smc_confirms=False,
        smc_signal="",
        override_counter_trend=False,
        confidence=0.0,
        rationale="No pullback setup detected"
    )
    
    if df_4h is None or len(df_4h) < 30:
        default.rationale = "Insufficient 4H data for pullback detection"
        return default
    
    # Step 1: Check if price is extended
    is_extended, extension_pct, expected_direction = is_price_extended(
        df_4h, threshold_pct=extension_threshold
    )
    
    # If not extended, or extension doesn't match requested direction, no pullback
    if not is_extended:
        default.extension_pct = extension_pct
        default.rationale = f"Price not extended (only {abs(extension_pct):.1f}% from EMA)"
        return default
    
    if expected_direction != requested_direction:
        default.extension_pct = extension_pct
        default.rationale = f"Extension favors {expected_direction}, not {requested_direction}"
        return default
    
    # Step 2: Check volume exhaustion
    volume_exhausted, volume_signal = is_volume_exhausted(df_4h)
    
    # Step 3: Check SMC confirmation
    smc_confirms, smc_signal = check_smc_pullback_confirmation(smc_snapshot, requested_direction)
    
    # Calculate confidence
    conditions_met = sum([is_extended, volume_exhausted, smc_confirms])
    
    if conditions_met >= 2:
        # At least 2 of 3 conditions met - allow pullback
        confidence = 50.0 + (conditions_met * 15.0)  # 65-95 based on conditions
        override = True
        is_pullback = True
        
        rationale_parts = [f"Price {abs(extension_pct):.1f}% from 4H EMA"]
        if volume_exhausted:
            rationale_parts.append(volume_signal)
        if smc_confirms:
            rationale_parts.append(smc_signal)
        rationale = "; ".join(rationale_parts)
        
        logger.info(f"Pullback setup detected: {rationale} (confidence: {confidence}%)")
    else:
        confidence = 25.0
        override = False
        is_pullback = False
        rationale = f"Only {conditions_met}/3 conditions met"
    
    return PullbackSetup(
        is_pullback=is_pullback,
        direction=requested_direction,
        extension_pct=extension_pct,
        volume_exhausted=volume_exhausted,
        volume_signal=volume_signal,
        smc_confirms=smc_confirms,
        smc_signal=smc_signal,
        override_counter_trend=override,
        confidence=confidence,
        rationale=rationale
    )
