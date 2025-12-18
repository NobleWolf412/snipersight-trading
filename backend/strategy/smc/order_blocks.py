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


# --- Helper Functions for Enhanced OB Detection ---

def _has_structure_context(
    df: pd.DataFrame,
    candle_idx: int,
    direction: str,
    atr_value: float,
    swing_lookback: int = 20
) -> tuple:
    """
    Check if rejection candle is at a meaningful structural level.
    
    Args:
        df: OHLCV DataFrame
        candle_idx: Index of the rejection candle
        direction: 'bullish' or 'bearish'
        atr_value: Current ATR for distance normalization
        swing_lookback: Candles to look back for swing detection
        
    Returns:
        tuple: (has_context: bool, context_type: str)
    """
    if candle_idx < swing_lookback:
        return True, "insufficient_data"
    
    candle = df.iloc[candle_idx]
    lookback_df = df.iloc[candle_idx - swing_lookback:candle_idx]
    
    if len(lookback_df) < 10:
        return True, "insufficient_data"
    
    if direction == "bullish":
        # Check if near recent swing low
        recent_lows = lookback_df['low'].nsmallest(3)
        for low_price in recent_lows:
            distance = abs(candle['low'] - low_price)
            if distance < atr_value * 1.5:
                return True, "near_swing_low"
    else:  # bearish
        # Check if near recent swing high
        recent_highs = lookback_df['high'].nlargest(3)
        for high_price in recent_highs:
            distance = abs(candle['high'] - high_price)
            if distance < atr_value * 1.5:
                return True, "near_swing_high"
    
    return False, "no_structure"


def _has_bos_confirmation(
    df: pd.DataFrame,
    candle_idx: int,
    direction: str,
    lookback: int
) -> bool:
    """
    Verify that displacement culminated in break of structure.
    
    Args:
        df: OHLCV DataFrame
        candle_idx: Index of the OB candle
        direction: 'bullish' or 'bearish'
        lookback: Candles to check before/after
        
    Returns:
        bool: True if structure was broken
    """
    prior_start = max(0, candle_idx - lookback)
    future_end = min(len(df), candle_idx + 1 + lookback)
    
    prior_df = df.iloc[prior_start:candle_idx]
    future_df = df.iloc[candle_idx + 1:future_end]
    
    if len(prior_df) < 3 or len(future_df) < 2:
        return False
    
    if direction == "bullish":
        # Get prior swing high
        prior_swing_high = prior_df['high'].max()
        # Check if future candles broke it
        return any(future_df['high'] > prior_swing_high)
    else:
        # Get prior swing low
        prior_swing_low = prior_df['low'].min()
        # Check if future candles broke it
        return any(future_df['low'] < prior_swing_low)


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
        
        # Avoid division by zero and filter doji/micro-body candles
        # Use ATR-based threshold: 5% of ATR as minimum body size
        min_body = atr.iloc[i] * 0.05 if i < len(atr) and atr.iloc[i] > 0 else 1e-10
        if body < min_body:
            continue
        
        # Check for bullish order block (strong rejection from support OR strong engulfing)
        is_engulfing = body > (atr.iloc[i] * 1.2)
        
        if (lower_wick / body >= min_wick_ratio) or (is_engulfing and body > min_body):
            # Verify displacement: price should move up strongly after this candle
            displacement = _calculate_displacement_bullish(df, i, lookback_candles)
            displacement_atr = displacement / atr.iloc[i] if atr.iloc[i] > 0 else 0
            
            # Calculate base grade from displacement
            grade = smc_cfg.calculate_grade(displacement_atr)
            
            # NEW: Structure context check
            # Grade C OBs must be at meaningful structure to qualify
            has_context, context_type = _has_structure_context(df, i, "bullish", atr.iloc[i])
            if not has_context and grade == 'C':
                continue  # Skip weak OBs without structure context
            
            # Volume confirmation
            volume_spike = candle['volume'] > (avg_volume.iloc[i] * volume_threshold) if pd.notna(avg_volume.iloc[i]) else False
            
            # NEW: BOS confirmation bonus and Volume Bonus
            # Use extended lookback for BOS
            bos_lookback = int(lookback_candles * 1.5)
            
            if displacement_atr >= 0.6:
                has_bos = _has_bos_confirmation(df, i, "bullish", bos_lookback)
                if has_bos and grade == 'B':
                    grade = 'A'  # Upgrade B to A with BOS
                elif not has_bos and grade == 'A':
                    grade = 'B'  # Downgrade A without BOS
            
            # Volume Boost: Significant volume upgrades grade
            if volume_spike and grade == 'B':
                grade = 'A'
            elif volume_spike and grade == 'C':
                grade = 'B'
            
            # Normalize displacement to 0-100 scale
            normalized_displacement = max(0.0, min(100.0, (displacement_atr / 3.0) * 100.0))
            
            # LuxAlgo-style median-based range: bullish OBs use low → median
            # This gives tighter zones where institutional buying actually occurred
            median_price = (candle['high'] + candle['low']) / 2
            
            ob = OrderBlock(
                timeframe=_infer_timeframe(df),
                direction="bullish",
                high=median_price,  # Tighter: median instead of full high
                low=candle['low'],
                timestamp=candle.name.to_pydatetime(),
                displacement_strength=normalized_displacement,
                mitigation_level=0.0,
                freshness_score=1.0,
                grade=grade,
                displacement_atr=displacement_atr,
            )
            order_blocks.append(ob)
        
        # Check for bearish order block (strong rejection from resistance OR strong engulfing)
        # Engulfing check: Large body relative to ATR
        is_engulfing = body > (atr.iloc[i] * 1.2)
        
        if (upper_wick / body >= min_wick_ratio) or (is_engulfing and body > min_body):
            # Verify displacement: price should move down strongly after this candle
            displacement = _calculate_displacement_bearish(df, i, lookback_candles)
            displacement_atr = displacement / atr.iloc[i] if atr.iloc[i] > 0 else 0
            
            # Calculate base grade from displacement
            grade = smc_cfg.calculate_grade(displacement_atr)
            
            # NEW: Structure context check
            has_context, context_type = _has_structure_context(df, i, "bearish", atr.iloc[i])
            if not has_context and grade == 'C':
                continue  # Skip weak OBs without structure context
            
            # Volume confirmation
            volume_spike = candle['volume'] > (avg_volume.iloc[i] * volume_threshold) if pd.notna(avg_volume.iloc[i]) else False
            
            # NEW: BOS confirmation bonus
            # Use extended lookback for BOS (structure takes longer to break than initial impulse)
            bos_lookback = int(lookback_candles * 1.5)
            
            if displacement_atr >= 0.6:
                has_bos = _has_bos_confirmation(df, i, "bearish", bos_lookback)
                if has_bos and grade == 'B':
                    grade = 'A'
                elif not has_bos and grade == 'A':
                    grade = 'B'

            # Volume Boost
            if volume_spike and grade == 'B':
                grade = 'A'
            elif volume_spike and grade == 'C':
                grade = 'B'
            
            # Normalize displacement to 0-100 scale
            normalized_displacement = max(0.0, min(100.0, (displacement_atr / 3.0) * 100.0))
            
            # LuxAlgo-style median-based range: bearish OBs use median → high
            # This gives tighter zones where institutional selling actually occurred
            median_price = (candle['high'] + candle['low']) / 2
            
            ob = OrderBlock(
                timeframe=_infer_timeframe(df),
                direction="bearish",
                high=candle['high'],
                low=median_price,  # Tighter: median instead of full low
                timestamp=candle.name.to_pydatetime(),
                displacement_strength=normalized_displacement,
                mitigation_level=0.0,
                freshness_score=1.0,
                grade=grade,
                displacement_atr=displacement_atr,
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


def check_mitigation_enhanced(df: pd.DataFrame, ob: OrderBlock) -> dict:
    """
    Enhanced mitigation tracking with quality grading.
    
    Returns detailed mitigation info including:
    - Tap count: How many times zone was revisited
    - Tap depth: How deep the deepest penetration was
    - Reaction quality: How strongly price bounced after tap
    - Grade: fresh/tapped/partial/heavy/invalidated
    
    Args:
        df: DataFrame with OHLC data
        ob: OrderBlock to check
        
    Returns:
        dict with level, grade, taps, deepest_penetration, best_reaction
    """
    future_candles = df[df.index > ob.timestamp]
    
    if len(future_candles) == 0:
        return {
            "level": 0.0, 
            "grade": "fresh", 
            "taps": 0,
            "deepest_penetration": 0.0,
            "best_reaction": 0.0
        }
    
    ob_range = ob.high - ob.low
    if ob_range < 1e-10:
        return {
            "level": 0.0, 
            "grade": "fresh", 
            "taps": 0,
            "deepest_penetration": 0.0,
            "best_reaction": 0.0
        }
    
    taps = 0
    deepest_penetration = 0.0
    best_reaction = 0.0
    
    for i in range(len(future_candles)):
        candle = future_candles.iloc[i]
        
        if ob.direction == "bullish":
            # Check if candle tapped the OB zone (wick or body entered)
            if candle['low'] <= ob.high:
                taps += 1
                penetration = (ob.high - candle['low']) / ob_range
                deepest_penetration = max(deepest_penetration, penetration)
                
                # Measure reaction quality (how far did it bounce after tap?)
                # Look at next 3 candles
                if i + 3 < len(future_candles):
                    reaction_high = future_candles.iloc[i+1:i+4]['high'].max()
                    reaction = reaction_high - candle['low']
                    best_reaction = max(best_reaction, reaction)
        else:  # bearish
            # Check if candle tapped the OB zone
            if candle['high'] >= ob.low:
                taps += 1
                penetration = (candle['high'] - ob.low) / ob_range
                deepest_penetration = max(deepest_penetration, penetration)
                
                # Measure reaction quality
                if i + 3 < len(future_candles):
                    reaction_low = future_candles.iloc[i+1:i+4]['low'].min()
                    reaction = candle['high'] - reaction_low
                    best_reaction = max(best_reaction, reaction)
    
    # Determine mitigation grade based on tap depth and count
    if deepest_penetration >= 1.0:
        grade = "invalidated"
        level = 1.0
    elif deepest_penetration > 0.7:
        grade = "heavy"
        level = deepest_penetration
    elif deepest_penetration > 0.3:
        grade = "partial"
        level = deepest_penetration
    elif taps > 0:
        grade = "tapped"
        level = deepest_penetration
    else:
        grade = "fresh"
        level = 0.0
    
    return {
        "level": level,
        "grade": grade,
        "taps": taps,
        "deepest_penetration": deepest_penetration,
        "best_reaction": best_reaction
    }


def calculate_freshness(ob: OrderBlock, current_time: datetime) -> float:
    """
    Calculate freshness score for an order block.
    
    Freshness decays over time - older order blocks are less reliable.
    UPDATED: Faster decay based on timeframe (Issue #5 fix)
    
    Args:
        ob: OrderBlock to score
        current_time: Current timestamp for comparison
        
    Returns:
        float: Freshness score (0-100 scale, 100 = just formed, decays over time)
    """
    age = current_time - ob.timestamp
    age_hours = age.total_seconds() / 3600
    
    # UPDATED: Timeframe-aware half-life (faster decay for LTF)
    # This prevents using stale OBs from days ago on short timeframes
    half_life_map = {
        '1m': 4,     # 4 hours for 1m OBs
        '5m': 12,    # 12 hours for 5m OBs
        '15m': 24,   # 24 hours for 15m OBs
        '1H': 48,    # 2 days for 1H OBs
        '4H': 96,    # 4 days for 4H OBs
        '1D': 168,   # 1 week for daily OBs
        '1W': 336,   # 2 weeks for weekly OBs
    }
    
    # Normalize timeframe format for lookup
    tf_normalized = ob.timeframe.upper().replace('M', 'm').replace('H', 'H')
    # Try exact match first, then pattern match
    half_life_hours = half_life_map.get(tf_normalized)
    if half_life_hours is None:
        # Pattern match fallback
        if 'm' in ob.timeframe.lower():
            mins = int(''.join(filter(str.isdigit, ob.timeframe)) or 15)
            half_life_hours = 12 if mins <= 5 else 24
        elif 'h' in ob.timeframe.lower():
            hours = int(''.join(filter(str.isdigit, ob.timeframe)) or 1)
            half_life_hours = 48 if hours <= 1 else 96
        elif 'd' in ob.timeframe.lower():
            half_life_hours = 168
        else:
            half_life_hours = 72  # Default fallback
    
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


def detect_obs_from_bos(
    df: pd.DataFrame,
    structural_breaks: List,
    config: SMCConfig | dict | None = None,
    lookback: int = 7
) -> List[OrderBlock]:
    """
    Detect Order Blocks using LuxAlgo method: last opposite-color candle before BOS.
    
    THIS IS THE CORRECT SMC METHOD:
    - Bearish OB = Last GREEN candle before bearish BOS (sellers absorbed buyers)
    - Bullish OB = Last RED candle before bullish BOS (buyers absorbed sellers)
    
    OBs detected this way get Grade A (structure-confirmed).
    
    Args:
        df: OHLCV DataFrame with DatetimeIndex
        structural_breaks: List of StructuralBreak objects
        config: SMC configuration
        lookback: Max candles to look back from BOS for OB candle (scales with TF)
        
    Returns:
        List[OrderBlock]: Grade A order blocks linked to structure breaks
    """
    from backend.shared.models.smc import StructuralBreak
    from backend.indicators.volatility import compute_atr
    
    if config is None:
        smc_cfg = SMCConfig.defaults()
    elif isinstance(config, dict):
        smc_cfg = SMCConfig.from_dict(config)
    else:
        smc_cfg = config
    
    if len(df) < 30 or not structural_breaks:
        return []
    
    atr = compute_atr(df, period=14)
    order_blocks = []
    used_bos = set()  # Avoid duplicate OBs from same BOS
    
    for bos in structural_breaks:
        bos_ts = getattr(bos, 'timestamp', None)
        bos_dir = getattr(bos, 'direction', None)
        bos_type = getattr(bos, 'break_type', None)
        
        if not bos_ts or not bos_dir:
            continue
        
        # Avoid duplicates
        bos_key = (bos_ts, bos_dir)
        if bos_key in used_bos:
            continue
        used_bos.add(bos_key)
        
        try:
            bos_idx = df.index.get_loc(bos_ts)
        except KeyError:
            # BOS timestamp not in this dataframe (different TF)
            continue
        
        # Scale lookback based on timeframe
        tf = _infer_timeframe(df)
        scaled_lookback = scale_lookback(lookback, tf)
        
        # Find last opposite-color candle before BOS
        ob_idx = None
        
        for i in range(bos_idx - 1, max(0, bos_idx - scaled_lookback), -1):
            candle = df.iloc[i]
            is_green = candle['close'] > candle['open']
            is_red = candle['close'] < candle['open']
            
            if bos_dir == 'bearish' and is_green:
                # Last green candle before bearish BOS = bearish OB (supply zone)
                ob_idx = i
                ob_direction = 'bearish'
                break
            elif bos_dir == 'bullish' and is_red:
                # Last red candle before bullish BOS = bullish OB (demand zone)
                ob_idx = i
                ob_direction = 'bullish'
                break
        
        if ob_idx is None:
            continue
        
        ob_candle = df.iloc[ob_idx]
        atr_val = atr.iloc[ob_idx] if ob_idx < len(atr) and pd.notna(atr.iloc[ob_idx]) else 1
        
        # Calculate displacement (from OB to BOS)
        if ob_direction == 'bullish':
            displacement = df.iloc[bos_idx]['high'] - ob_candle['low']
        else:
            displacement = ob_candle['high'] - df.iloc[bos_idx]['low']
        
        disp_atr = displacement / atr_val if atr_val > 0 else 0
        
        # Structure-confirmed OBs get Grade A (unless displacement is very weak)
        if disp_atr >= 1.0:
            grade = 'A'  # Strong structure-confirmed
        elif disp_atr >= 0.5:
            grade = 'A'  # Still gets A because it caused a BOS
        else:
            grade = 'B'  # Weak displacement but still structure-linked
        
        # LuxAlgo-style range: use median for tighter zones
        median_price = (ob_candle['high'] + ob_candle['low']) / 2
        
        if ob_direction == 'bullish':
            ob_high = median_price
            ob_low = ob_candle['low']
        else:
            ob_high = ob_candle['high']
            ob_low = median_price
        
        normalized_disp = max(0.0, min(100.0, (disp_atr / 3.0) * 100.0))
        
        ob = OrderBlock(
            timeframe=tf,
            direction=ob_direction,
            high=ob_high,
            low=ob_low,
            timestamp=df.index[ob_idx].to_pydatetime(),
            displacement_strength=normalized_disp,
            mitigation_level=0.0,
            freshness_score=100.0,  # Will be recalculated later
            grade=grade,
            displacement_atr=disp_atr,
        )
        order_blocks.append(ob)
    
    return order_blocks


def detect_order_blocks_structural(
    df: pd.DataFrame,
    swing_highs: pd.Series,
    swing_lows: pd.Series,
    config: SMCConfig | dict | None = None
) -> List[OrderBlock]:
    """
    Detect order blocks using "last candle before BOS" structural method.
    
    STOLEN from smartmoneyconcepts library - finds the institutional footprint
    candle that formed just before a structural break.
    
    This method complements rejection-wick detection. Use both and score
    higher when they agree on the same zone.
    
    Args:
        df: OHLCV DataFrame with DatetimeIndex
        swing_highs: Series of swing high prices indexed by timestamp
        swing_lows: Series of swing low prices indexed by timestamp
        config: SMC configuration
        
    Returns:
        List[OrderBlock]: Detected order blocks from structural method
    """
    if config is None:
        smc_cfg = SMCConfig.defaults()
    elif isinstance(config, dict):
        smc_cfg = SMCConfig.from_dict(config)
    else:
        smc_cfg = config
    
    n = len(df)
    if n < 30:
        return []
    
    _high = df['high'].values
    _low = df['low'].values
    _close = df['close'].values
    _volume = df['volume'].values if 'volume' in df.columns else np.ones(n)
    
    # Track which swing highs/lows have been crossed
    crossed_highs = set()
    crossed_lows = set()
    
    order_blocks = []
    
    # Calculate ATR
    from backend.indicators.volatility import compute_atr
    atr = compute_atr(df, period=14)
    
    # Get swing high/low indices
    swing_high_times = set(swing_highs.index)
    swing_low_times = set(swing_lows.index)
    
    # === BULLISH OBs: Close above swing high ===
    for close_idx in range(1, n):
        # Find the last swing high before this candle
        prior_swing_highs = swing_highs[swing_highs.index < df.index[close_idx]]
        
        if len(prior_swing_highs) == 0:
            continue
            
        last_swing_high_ts = prior_swing_highs.index[-1]
        last_swing_high_val = prior_swing_highs.iloc[-1]
        
        # Check if we broke this swing high
        if _close[close_idx] > last_swing_high_val and last_swing_high_ts not in crossed_highs:
            crossed_highs.add(last_swing_high_ts)
            
            # Find the lowest candle between swing high and break (this is the OB)
            swing_idx = df.index.get_loc(last_swing_high_ts)
            
            if close_idx - swing_idx > 1:
                segment_low = _low[swing_idx + 1:close_idx]
                if len(segment_low) > 0:
                    min_val = segment_low.min()
                    candidates = np.where(segment_low == min_val)[0]
                    ob_idx = swing_idx + 1 + candidates[-1]
                else:
                    ob_idx = close_idx - 1
            else:
                ob_idx = close_idx - 1
            
            # Calculate volume imbalance (lower = more imbalanced = stronger)
            vol_cur = _volume[close_idx]
            vol_prev1 = _volume[close_idx - 1] if close_idx >= 1 else 0
            vol_prev2 = _volume[close_idx - 2] if close_idx >= 2 else 0
            high_vol = vol_cur + vol_prev1
            low_vol = vol_prev2 if vol_prev2 > 0 else 1
            max_vol = max(high_vol, low_vol)
            volume_imbalance = (min(high_vol, low_vol) / max_vol * 100) if max_vol > 0 else 100
            
            # Grade based on ATR displacement
            displacement = _high[close_idx] - _low[ob_idx]
            atr_val = atr.iloc[close_idx] if close_idx < len(atr) and pd.notna(atr.iloc[close_idx]) else 1
            disp_atr = displacement / atr_val if atr_val > 0 else 0
            grade = smc_cfg.calculate_grade(disp_atr)
            
            # Boost grade if strong volume imbalance (<30% = very imbalanced)
            if volume_imbalance < 30 and grade == 'B':
                grade = 'A'
            
            normalized_disp = max(0.0, min(100.0, (disp_atr / 3.0) * 100.0))
            
            # LuxAlgo-style median-based range: bullish OBs use low → median
            median_price = (_high[ob_idx] + _low[ob_idx]) / 2
            
            ob = OrderBlock(
                timeframe=_infer_timeframe(df),
                direction="bullish",
                high=median_price,  # Tighter: median instead of full high
                low=_low[ob_idx],
                timestamp=df.index[ob_idx].to_pydatetime(),
                displacement_strength=normalized_disp,
                mitigation_level=0.0,
                freshness_score=100.0,
                grade=grade,
                displacement_atr=disp_atr,
            )
            order_blocks.append(ob)
    
    # === BEARISH OBs: Close below swing low ===
    for close_idx in range(1, n):
        # Find the last swing low before this candle
        prior_swing_lows = swing_lows[swing_lows.index < df.index[close_idx]]
        
        if len(prior_swing_lows) == 0:
            continue
            
        last_swing_low_ts = prior_swing_lows.index[-1]
        last_swing_low_val = prior_swing_lows.iloc[-1]
        
        # Check if we broke this swing low
        if _close[close_idx] < last_swing_low_val and last_swing_low_ts not in crossed_lows:
            crossed_lows.add(last_swing_low_ts)
            
            # Find the highest candle between swing low and break (this is the OB)
            swing_idx = df.index.get_loc(last_swing_low_ts)
            
            if close_idx - swing_idx > 1:
                segment_high = _high[swing_idx + 1:close_idx]
                if len(segment_high) > 0:
                    max_val = segment_high.max()
                    candidates = np.where(segment_high == max_val)[0]
                    ob_idx = swing_idx + 1 + candidates[-1]
                else:
                    ob_idx = close_idx - 1
            else:
                ob_idx = close_idx - 1
            
            # Calculate volume imbalance
            vol_cur = _volume[close_idx]
            vol_prev1 = _volume[close_idx - 1] if close_idx >= 1 else 0
            vol_prev2 = _volume[close_idx - 2] if close_idx >= 2 else 0
            high_vol = vol_cur + vol_prev1
            low_vol = vol_prev2 if vol_prev2 > 0 else 1
            max_vol = max(high_vol, low_vol)
            volume_imbalance = (min(high_vol, low_vol) / max_vol * 100) if max_vol > 0 else 100
            
            # Grade based on ATR displacement
            displacement = _high[ob_idx] - _low[close_idx]
            atr_val = atr.iloc[close_idx] if close_idx < len(atr) and pd.notna(atr.iloc[close_idx]) else 1
            disp_atr = displacement / atr_val if atr_val > 0 else 0
            grade = smc_cfg.calculate_grade(disp_atr)
            
            # Boost grade if strong volume imbalance
            if volume_imbalance < 30 and grade == 'B':
                grade = 'A'
            
            normalized_disp = max(0.0, min(100.0, (disp_atr / 3.0) * 100.0))
            
            # LuxAlgo-style median-based range: bearish OBs use median → high
            median_price = (_high[ob_idx] + _low[ob_idx]) / 2
            
            ob = OrderBlock(
                timeframe=_infer_timeframe(df),
                direction="bearish",
                high=_high[ob_idx],
                low=median_price,  # Tighter: median instead of full low
                timestamp=df.index[ob_idx].to_pydatetime(),
                displacement_strength=normalized_disp,
                mitigation_level=0.0,
                freshness_score=100.0,
                grade=grade,
                displacement_atr=disp_atr,
            )
            order_blocks.append(ob)
    
    return order_blocks


def update_ob_lifecycle(
    df: pd.DataFrame,
    order_blocks: List[OrderBlock],
    preset: str = "defaults"
) -> List[OrderBlock]:
    """
    Update Order Block lifecycle states based on price action.
    
    Lifecycle: Fresh → Mitigated → Breaker → Invalidated
    
    - Fresh: OB just detected, not yet revisited
    - Mitigated: Price has revisited the zone but not broken through
    - Breaker: Price closed through the zone (flips to opposite S/R)
    - Invalidated: Breaker failed (price broke back through)
    
    STOLEN from smartmoneyconcepts library lifecycle tracking.
    
    Args:
        df: OHLCV DataFrame with DatetimeIndex
        order_blocks: List of OrderBlock objects
        preset: SMC preset for behavior tuning
        
    Returns:
        List[OrderBlock]: Updated order blocks (invalidated ones filtered out)
    """
    from backend.shared.config.smc_config import get_enhanced_mitigation_config
    config = get_enhanced_mitigation_config(preset)
    
    updated_blocks = []
    
    for ob in order_blocks:
        # Skip already invalidated
        if ob.invalidated:
            continue
        
        # Get future candles after OB formation
        future_candles = df[df.index > ob.timestamp]
        
        if len(future_candles) == 0:
            updated_blocks.append(ob)
            continue
        
        is_breaker = ob.breaker
        is_invalidated = ob.invalidated
        
        # Track through each candle
        for ts, candle in future_candles.iterrows():
            if is_invalidated:
                break
            
            if ob.direction == "bullish":
                # Bullish OB broken = price closed below OB low
                if not is_breaker and candle['close'] < ob.low:
                    is_breaker = True
                # Breaker invalidated = price closed back above OB high
                elif is_breaker and candle['close'] > ob.high:
                    is_invalidated = True
            else:  # bearish
                # Bearish OB broken = price closed above OB high
                if not is_breaker and candle['close'] > ob.high:
                    is_breaker = True
                # Breaker invalidated = price closed back below OB low
                elif is_breaker and candle['close'] < ob.low:
                    is_invalidated = True
        
        # Create updated OB with new lifecycle state
        from dataclasses import replace
        updated_ob = replace(ob, breaker=is_breaker, invalidated=is_invalidated)
        
        # Filter based on config
        if config.get('invalidate_on_deep_tap', True) and updated_ob.invalidated:
            continue  # Skip invalidated OBs
        
        updated_blocks.append(updated_ob)
    
    return updated_blocks


def filter_to_active_obs(
    order_blocks: List[OrderBlock],
    df: pd.DataFrame,
    structure_breaks: List = None,
    max_mitigation: float = 0.5,
    require_structure_confirmation: bool = True,
    confirmation_window_candles: int = 10
) -> List[OrderBlock]:
    """
    Filter order blocks to only 'active' ones matching LuxAlgo behavior.
    
    LuxAlgo shows fewer, higher-quality OBs by:
    1. Structure-confirmed: OB must precede a BOS/CHoCH
    2. Fresh: Not fully mitigated (price hasn't swept through)
    3. Not invalidated: Zone still valid for trading
    
    This reduces noise while keeping liquidity awareness under the hood
    (raw OBs can be preserved separately for analysis).
    
    Args:
        order_blocks: Raw detected OBs
        df: Price data for mitigation checking
        structure_breaks: Detected BOS/CHoCH for confirmation
        max_mitigation: Maximum mitigation level to keep (0.5 = 50%)
        require_structure_confirmation: If True, only keep OBs that precede a break
        confirmation_window_candles: How many candles after OB to look for break
        
    Returns:
        List of active, tradeable order blocks
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not order_blocks:
        return []
    
    structure_breaks = structure_breaks or []
    active_obs = []
    
    for ob in order_blocks:
        # --- Filter 1: Skip invalidated OBs ---
        if getattr(ob, 'invalidated', False):
            continue
        
        # --- Filter 2: Skip heavily mitigated OBs ---
        if ob.mitigation_level > max_mitigation:
            logger.debug("🚫 OB filtered (mitigation %.1f%% > %.1f%%): %s @ %s", 
                        ob.mitigation_level * 100, max_mitigation * 100,
                        ob.direction, ob.timestamp)
            continue
        
        # --- Filter 3: Structure confirmation check ---
        if require_structure_confirmation and structure_breaks:
            confirmed = _check_structure_confirmation(
                ob, structure_breaks, df, confirmation_window_candles
            )
            if not confirmed:
                logger.debug("🚫 OB filtered (no structure confirmation): %s @ %s",
                            ob.direction, ob.timestamp)
                continue
        
        # OB passes all filters
        active_obs.append(ob)
    
    logger.info("🎯 OB Filter: %d/%d OBs are active (structure-confirmed + fresh)",
                len(active_obs), len(order_blocks))
    
    return active_obs


def _check_structure_confirmation(
    ob: OrderBlock,
    structure_breaks: List,
    df: pd.DataFrame,
    window_candles: int = 10
) -> bool:
    """
    Check if an order block is confirmed by a subsequent structure break.
    
    An OB is 'structure-confirmed' if a BOS or CHoCH occurred within N candles
    AFTER the OB formed, in the same direction.
    
    This matches LuxAlgo's approach: only show OBs that actually caused
    a structural shift in the market.
    
    Args:
        ob: OrderBlock to check
        structure_breaks: List of StructuralBreak objects
        df: Price DataFrame for index lookups
        window_candles: How many candles after OB to look for break
        
    Returns:
        bool: True if OB is structure-confirmed
    """
    if not structure_breaks:
        return False
    
    # Get OB index in dataframe
    try:
        ob_idx = df.index.get_loc(ob.timestamp)
    except (KeyError, TypeError):
        # Try finding closest timestamp
        try:
            closest_idx = df.index.get_indexer([ob.timestamp], method='nearest')[0]
            ob_idx = closest_idx
        except:
            return False
    
    # Define confirmation window
    window_start_idx = ob_idx + 1
    window_end_idx = min(ob_idx + 1 + window_candles, len(df))
    
    if window_start_idx >= len(df):
        # OB is too recent - no data to confirm yet, keep it
        return True
    
    window_start_time = df.index[window_start_idx]
    window_end_time = df.index[min(window_end_idx, len(df) - 1)]
    
    # Check each structure break
    for brk in structure_breaks:
        brk_time = getattr(brk, 'timestamp', None)
        if brk_time is None:
            continue
        
        # Convert to comparable format if needed
        if hasattr(brk_time, 'to_pydatetime'):
            brk_time = brk_time.to_pydatetime()
        
        # Check if break is in confirmation window
        try:
            if window_start_time <= brk_time <= window_end_time:
                # Check direction alignment
                brk_direction = getattr(brk, 'direction', None)
                if brk_direction == ob.direction:
                    return True
        except TypeError:
            # Timestamp comparison failed, skip
            continue
    
    return False
