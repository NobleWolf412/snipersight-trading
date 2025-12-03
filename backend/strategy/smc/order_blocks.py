"""
Order Block Detection Module

Implements Smart Money Concept (SMC) order block detection.

Order Blocks are institutional supply/demand zones identified by:
- Strong rejection candles with large wicks
- Displacement: strong price move away from the zone
- Mitigation tracking: how much the zone has been revisited
- Freshness scoring: time-based decay of zone validity
"""

from typing import List, Optional
from dataclasses import replace
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from backend.shared.models.smc import OrderBlock
from backend.shared.config.smc_config import SMCConfig, scale_lookback


def detect_order_blocks(
    df: pd.DataFrame,
    config: SMCConfig | dict | None = None
) -> List[OrderBlock]:
    """
    Detect order blocks in price data.
    
    Order blocks are identified by:
    1. Strong rejection candles (large wicks relative to body)
    2. Displacement: strong move away from the zone (verified by subsequent candles)
    3. High volume confirmation (optional but preferred)
    
    Args:
        df: DataFrame with OHLCV data and DatetimeIndex
        config: Configuration dict with:
            - min_wick_ratio: Minimum wick/body ratio (default 2.0)
            - min_displacement_atr: Minimum displacement in ATR units (default 1.5)
            - lookback_candles: Number of candles to check for displacement (default 5)
            - volume_threshold: Volume spike threshold (default 1.5)
            
    Returns:
        List[OrderBlock]: Detected order blocks sorted by freshness
        
    Raises:
        ValueError: If df is too short or missing required columns
    """
    required_cols = ['open', 'high', 'low', 'close', 'volume']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"DataFrame missing required columns: {missing_cols}")
    
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame must have DatetimeIndex")
    
    # Normalize configuration to SMCConfig
    if config is None:
        smc_cfg = SMCConfig.defaults()
    elif isinstance(config, dict):
        # Map legacy keys to new dataclass fields
        mapped = {}
        if 'min_wick_ratio' in config:
            mapped['min_wick_ratio'] = config['min_wick_ratio']
        if 'min_displacement_atr' in config:
            mapped['min_displacement_atr'] = config['min_displacement_atr']
        if 'lookback_candles' in config:
            mapped['ob_lookback_candles'] = config['lookback_candles']
        if 'volume_threshold' in config:
            mapped['ob_volume_threshold'] = config['volume_threshold']
        if 'max_mitigation' in config:
            mapped['ob_max_mitigation'] = config['max_mitigation']
        if 'min_freshness' in config:
            mapped['ob_min_freshness'] = config['min_freshness']
        smc_cfg = SMCConfig.from_dict(mapped)
    else:
        smc_cfg = config  # already SMCConfig

    min_wick_ratio = smc_cfg.min_wick_ratio
    min_displacement_atr = smc_cfg.min_displacement_atr
    # Apply timeframe-aware scaling to lookback
    inferred_tf = _infer_timeframe(df)
    lookback_candles = scale_lookback(smc_cfg.ob_lookback_candles, inferred_tf)
    volume_threshold = smc_cfg.ob_volume_threshold
    
    if len(df) < lookback_candles + 20:  # Need enough data for ATR calculation
        raise ValueError(f"DataFrame too short for order block detection (need {lookback_candles + 20} rows, got {len(df)})")
    
    # Calculate ATR for displacement measurement
    from backend.indicators.volatility import compute_atr
    atr = compute_atr(df, period=14)
    
    # Calculate average volume
    avg_volume = df['volume'].rolling(window=20).mean()
    
    order_blocks = []
    
    # Scan for rejection candles
    for i in range(20, len(df) - lookback_candles):  # Start after ATR warmup, leave room for displacement check
        candle = df.iloc[i]
        
        # Calculate candle metrics
        body = abs(candle['close'] - candle['open'])
        upper_wick = candle['high'] - max(candle['open'], candle['close'])
        lower_wick = min(candle['open'], candle['close']) - candle['low']
        
        # Avoid division by zero
        if body < 1e-10:
            continue
        
        # Check for bullish order block (strong rejection from support)
        if lower_wick / body >= min_wick_ratio:
            # Verify displacement: price should move up strongly after this candle
            displacement = _calculate_displacement_bullish(df, i, lookback_candles)
            displacement_atr = displacement / atr.iloc[i] if atr.iloc[i] > 0 else 0
            
            if displacement_atr >= min_displacement_atr:
                # Volume confirmation (optional)
                volume_spike = candle['volume'] > (avg_volume.iloc[i] * volume_threshold) if pd.notna(avg_volume.iloc[i]) else False
                
                # Normalize displacement to 0-100 scale
                # 1.5 ATR = 50 (minimum), 3.0 ATR = 100 (maximum)
                normalized_displacement = min(100.0, (displacement_atr / 3.0) * 100.0)
                
                ob = OrderBlock(
                    timeframe=_infer_timeframe(df),
                    direction="bullish",
                    high=candle['high'],
                    low=candle['low'],
                    timestamp=candle.name.to_pydatetime(),
                    displacement_strength=normalized_displacement,
                    mitigation_level=0.0,  # Not yet mitigated
                    freshness_score=1.0  # Will be updated later
                )
                order_blocks.append(ob)
        
        # Check for bearish order block (strong rejection from resistance)
        if upper_wick / body >= min_wick_ratio:
            # Verify displacement: price should move down strongly after this candle
            displacement = _calculate_displacement_bearish(df, i, lookback_candles)
            displacement_atr = displacement / atr.iloc[i] if atr.iloc[i] > 0 else 0
            
            if displacement_atr >= min_displacement_atr:
                volume_spike = candle['volume'] > (avg_volume.iloc[i] * volume_threshold) if pd.notna(avg_volume.iloc[i]) else False
                
                # Normalize displacement to 0-100 scale
                normalized_displacement = min(100.0, (displacement_atr / 3.0) * 100.0)
                
                ob = OrderBlock(
                    timeframe=_infer_timeframe(df),
                    direction="bearish",
                    high=candle['high'],
                    low=candle['low'],
                    timestamp=candle.name.to_pydatetime(),
                    displacement_strength=normalized_displacement,
                    mitigation_level=0.0,
                    freshness_score=1.0
                )
                order_blocks.append(ob)
    
    # Update mitigation and freshness for all order blocks
    current_time = df.index[-1].to_pydatetime()
    current_price = df['close'].iloc[-1]
    
    for i, ob in enumerate(order_blocks):
        mitigation = check_mitigation(df, ob)
        freshness = calculate_freshness(ob, current_time)
        
        # Update order block with new values
        order_blocks[i] = replace(
            ob,
            mitigation_level=mitigation,
            freshness_score=freshness
        )
    
    # Filter out heavily mitigated or stale order blocks
    max_mitigation = smc_cfg.ob_max_mitigation
    min_freshness = smc_cfg.ob_min_freshness
    
    order_blocks = [
        ob for ob in order_blocks
        if ob.mitigation_level < max_mitigation and ob.freshness_score >= min_freshness
    ]
    
    # Sort by freshness (most recent first)
    order_blocks.sort(key=lambda ob: ob.freshness_score, reverse=True)
    
    return order_blocks


def _calculate_displacement_bullish(df: pd.DataFrame, candle_idx: int, lookback: int) -> float:
    """
    Calculate bullish displacement strength.
    
    Measures how much price moved up after the rejection candle.
    
    Args:
        df: OHLCV DataFrame
        candle_idx: Index of the rejection candle
        lookback: Number of candles to check
        
    Returns:
        float: Displacement amount (absolute price move)
    """
    rejection_low = df.iloc[candle_idx]['low']
    
    # Find highest high in the next N candles
    subsequent_highs = df.iloc[candle_idx + 1:candle_idx + 1 + lookback]['high']
    
    if len(subsequent_highs) == 0:
        return 0.0
    
    max_high = subsequent_highs.max()
    displacement = max_high - rejection_low
    
    return displacement


def _calculate_displacement_bearish(df: pd.DataFrame, candle_idx: int, lookback: int) -> float:
    """
    Calculate bearish displacement strength.
    
    Measures how much price moved down after the rejection candle.
    
    Args:
        df: OHLCV DataFrame
        candle_idx: Index of the rejection candle
        lookback: Number of candles to check
        
    Returns:
        float: Displacement amount (absolute price move)
    """
    rejection_high = df.iloc[candle_idx]['high']
    
    # Find lowest low in the next N candles
    subsequent_lows = df.iloc[candle_idx + 1:candle_idx + 1 + lookback]['low']
    
    if len(subsequent_lows) == 0:
        return 0.0
    
    min_low = subsequent_lows.min()
    displacement = rejection_high - min_low
    
    return displacement


def calculate_displacement_strength(df: pd.DataFrame, ob: OrderBlock) -> float:
    """
    Calculate displacement strength for an existing order block.
    
    Args:
        df: DataFrame with OHLC data
        ob: OrderBlock to analyze
        
    Returns:
        float: Displacement strength normalized to 0-100 scale
    """
    # Find the order block candle in the DataFrame
    ob_candles = df[df.index == ob.timestamp]
    
    if len(ob_candles) == 0:
        return ob.displacement_strength  # Return existing value if candle not found
    
    ob_idx = df.index.get_loc(ob.timestamp)
    
    # Recalculate displacement
    if ob.direction == "bullish":
        displacement = _calculate_displacement_bullish(df, ob_idx, 5)
    else:
        displacement = _calculate_displacement_bearish(df, ob_idx, 5)
    
    # Calculate in ATR units
    from backend.indicators.volatility import compute_atr
    atr = compute_atr(df, period=14)
    atr_value = atr.iloc[ob_idx] if ob_idx < len(atr) else atr.iloc[-1]
    
    displacement_atr = displacement / atr_value if atr_value > 0 else 0
    
    # Normalize to 0-100 scale (1.5 ATR = 50, 3.0 ATR = 100)
    normalized = min(100.0, (displacement_atr / 3.0) * 100.0)
    
    return normalized


def check_mitigation(df: pd.DataFrame, ob: OrderBlock) -> float:
    """
    Check how much an order block has been mitigated (revisited by price).
    
    Mitigation occurs when price re-enters the order block zone.
    
    Args:
        df: DataFrame with OHLC data
        ob: OrderBlock to check
        
    Returns:
        float: Mitigation level (0.0 = untouched, 1.0 = fully mitigated)
    """
    # Get candles after the order block formation
    future_candles = df[df.index > ob.timestamp]
    
    if len(future_candles) == 0:
        return 0.0  # No mitigation if no future data
    
    ob_range = ob.high - ob.low
    
    if ob_range < 1e-10:
        return 0.0  # Avoid division by zero
    
    # Check how deep price penetrated back into the zone
    if ob.direction == "bullish":
        # For bullish OB, check how low price went back into the zone
        lowest_revisit = future_candles['low'].min()
        
        if lowest_revisit >= ob.high:
            return 0.0  # Never touched
        elif lowest_revisit <= ob.low:
            return 1.0  # Fully mitigated (broke below)
        else:
            # Partial mitigation
            penetration = ob.high - lowest_revisit
            return penetration / ob_range
    
    else:  # bearish
        # For bearish OB, check how high price went back into the zone
        highest_revisit = future_candles['high'].max()
        
        if highest_revisit <= ob.low:
            return 0.0  # Never touched
        elif highest_revisit >= ob.high:
            return 1.0  # Fully mitigated (broke above)
        else:
            # Partial mitigation
            penetration = highest_revisit - ob.low
            return penetration / ob_range


def calculate_freshness(ob: OrderBlock, current_time: datetime) -> float:
    """
    Calculate freshness score for an order block.
    
    Freshness decays over time - older order blocks are less reliable.
    
    Args:
        ob: OrderBlock to score
        current_time: Current timestamp for comparison
        
    Returns:
        float: Freshness score (0-100 scale, 100 = just formed, decays over time)
    """
    age = current_time - ob.timestamp
    age_hours = age.total_seconds() / 3600
    
    # Decay function: exponential decay with half-life of 168 hours (1 week)
    half_life_hours = 168
    freshness = 2 ** (-age_hours / half_life_hours)
    
    # Scale to 0-100 (model expects 0-100, is_fresh checks > 70)
    return freshness * 100.0


def _infer_timeframe(df: pd.DataFrame) -> str:
    """
    Infer timeframe from DataFrame index.
    
    Args:
        df: DataFrame with DatetimeIndex
        
    Returns:
        str: Timeframe string (e.g., "1H", "4H", "1D")
    """
    if len(df) < 2:
        return "unknown"
    
    # Calculate average time delta between candles
    time_deltas = df.index.to_series().diff().dropna()
    avg_delta = time_deltas.mean()
    
    # Map to common timeframes
    total_seconds = avg_delta.total_seconds()
    
    if total_seconds < 60:
        return f"{int(total_seconds)}s"
    elif total_seconds < 3600:
        return f"{int(total_seconds / 60)}m"
    elif total_seconds < 86400:
        return f"{int(total_seconds / 3600)}H"
    elif total_seconds < 604800:
        return f"{int(total_seconds / 86400)}D"
    else:
        return f"{int(total_seconds / 604800)}W"


def filter_overlapping_order_blocks(order_blocks: List[OrderBlock], max_overlap: float = 0.5) -> List[OrderBlock]:
    """
    Filter out overlapping order blocks, keeping the strongest ones.
    
    Args:
        order_blocks: List of order blocks to filter
        max_overlap: Maximum allowed overlap ratio (default 0.5)
        
    Returns:
        List[OrderBlock]: Filtered list with minimal overlap
    """
    if len(order_blocks) <= 1:
        return order_blocks
    
    # Sort by displacement strength (strongest first)
    sorted_obs = sorted(order_blocks, key=lambda ob: ob.displacement_strength, reverse=True)
    
    filtered = []
    
    for ob in sorted_obs:
        # Check if this OB significantly overlaps with any already selected
        overlaps = False
        
        for selected_ob in filtered:
            if ob.direction != selected_ob.direction:
                continue  # Different directions don't conflict
            
            # Calculate overlap
            overlap_high = min(ob.high, selected_ob.high)
            overlap_low = max(ob.low, selected_ob.low)
            
            if overlap_high > overlap_low:
                overlap_range = overlap_high - overlap_low
                ob_range = ob.high - ob.low
                overlap_ratio = overlap_range / ob_range if ob_range > 0 else 0
                
                if overlap_ratio > max_overlap:
                    overlaps = True
                    break
        
        if not overlaps:
            filtered.append(ob)
    
    return filtered
