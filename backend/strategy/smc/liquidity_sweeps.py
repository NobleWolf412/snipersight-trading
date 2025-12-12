"""
Liquidity Sweep Detection Module

Implements Smart Money Concept liquidity sweep detection.

Liquidity sweeps occur when:
- Price briefly exceeds a key level (high/low) to trigger stop losses
- Price quickly reverses, showing the move was a "trap"
- Often precedes strong moves in opposite direction

Also includes Equal Highs/Lows (Liquidity Pool) detection:
- Clustered swing points at similar price levels
- Represent stop-loss liquidity accumulation
- High-probability sweep targets
"""

from typing import List, Optional
from datetime import datetime
import pandas as pd
import numpy as np

from backend.shared.models.smc import LiquiditySweep, LiquidityPool, grade_pattern
from backend.shared.config.smc_config import (
    SMCConfig, 
    scale_lookback,
    scale_eqhl_tolerance,
    get_eqhl_min_touches
)


def detect_liquidity_sweeps(
    df: pd.DataFrame,
    config: SMCConfig | dict | None = None
) -> List[LiquiditySweep]:
    """
    Detect liquidity sweeps in price data.
    
    Liquidity sweep characteristics:
    1. Price breaks above/below a recent swing high/low
    2. Breakout is brief (wick, not body close)
    3. Quick reversal back below/above the level
    4. Often accompanied by volume spike
    
    Args:
        df: DataFrame with OHLCV data and DatetimeIndex
        config: Configuration dict with:
            - swing_lookback: Candles for swing point detection (default 10)
            - max_sweep_candles: Max candles for sweep completion (default 3)
            - min_reversal_atr: Minimum reversal distance in ATR (default 1.0)
            - require_volume_spike: Whether to require volume confirmation (default False)
            
    Returns:
        List[LiquiditySweep]: Detected liquidity sweeps
        
    Raises:
        ValueError: If df is too short or missing required columns
    """
    required_cols = ['high', 'low', 'close', 'volume']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"DataFrame missing required columns: {missing_cols}")
    
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame must have DatetimeIndex")
    
    # Configuration
    if config is None:
        smc_cfg = SMCConfig.defaults()
    elif isinstance(config, dict):
        mapped = {}
        if 'swing_lookback' in config:
            mapped['sweep_swing_lookback'] = config['swing_lookback']
        if 'max_sweep_candles' in config:
            mapped['sweep_max_sweep_candles'] = config['max_sweep_candles']
        if 'min_reversal_atr' in config:
            mapped['sweep_min_reversal_atr'] = config['min_reversal_atr']
        if 'require_volume_spike' in config:
            mapped['sweep_require_volume_spike'] = config['require_volume_spike']
        smc_cfg = SMCConfig.from_dict(mapped)
    else:
        smc_cfg = config
    
    # Infer timeframe and apply scaling to lookback
    from backend.strategy.smc.bos_choch import _infer_timeframe
    inferred_tf = _infer_timeframe(df)
    swing_lookback = scale_lookback(smc_cfg.sweep_swing_lookback, inferred_tf)
    max_sweep_candles = smc_cfg.sweep_max_sweep_candles
    min_reversal_atr = smc_cfg.sweep_min_reversal_atr
    require_volume_spike = smc_cfg.sweep_require_volume_spike
    
    if len(df) < swing_lookback * 2 + 20:
        raise ValueError(f"DataFrame too short for liquidity sweep detection (need {swing_lookback * 2 + 20} rows, got {len(df)})")
    
    # Calculate ATR for filtering
    from backend.indicators.volatility import compute_atr
    atr = compute_atr(df, period=14)
    
    # Calculate average volume for spike detection
    avg_volume = df['volume'].rolling(window=20).mean()
    
    # Detect recent swing highs and lows
    from backend.strategy.smc.bos_choch import _detect_swing_highs, _detect_swing_lows
    swing_highs = _detect_swing_highs(df, swing_lookback)
    swing_lows = _detect_swing_lows(df, swing_lookback)
    
    liquidity_sweeps = []
    
    # Scan for sweeps
    for i in range(swing_lookback * 2, len(df) - max_sweep_candles):
        # Look for recent swing points before this candle
        recent_swing_highs = swing_highs[swing_highs.index < df.index[i]].tail(3)
        recent_swing_lows = swing_lows[swing_lows.index < df.index[i]].tail(3)
        
        if len(recent_swing_highs) == 0 and len(recent_swing_lows) == 0:
            continue
        
        current_candle = df.iloc[i]
        atr_value = atr.iloc[i] if pd.notna(atr.iloc[i]) else 0
        
        # Check for high sweep (price spikes above recent high then reverses)
        if len(recent_swing_highs) > 0:
            target_high = recent_swing_highs.iloc[-1]
            
            # Check if candle wicked above the high
            if current_candle['high'] > target_high and current_candle['close'] < target_high:
                # Check for reversal and get distance for grading
                reversal_distance = _get_downside_reversal_distance(
                    df, i, max_sweep_candles, target_high
                )
                
                if reversal_distance > 0:  # Any reversal detected
                    # Check volume if required
                    volume_spike = current_candle['volume'] > (avg_volume.iloc[i] * 1.5) if pd.notna(avg_volume.iloc[i]) else False
                    
                    if not require_volume_spike or volume_spike:
                        # Grade the sweep based on reversal strength
                        reversal_atr = reversal_distance / atr_value if atr_value > 0 else 0.0
                        grade_a_threshold = smc_cfg.grade_a_threshold * min_reversal_atr
                        grade_b_threshold = smc_cfg.grade_b_threshold * min_reversal_atr
                        grade = grade_pattern(reversal_atr, grade_a_threshold, grade_b_threshold)
                        
                        sweep = LiquiditySweep(
                            level=target_high,
                            sweep_type="high",
                            confirmation=volume_spike,
                            timestamp=current_candle.name.to_pydatetime(),
                            grade=grade
                        )
                        liquidity_sweeps.append(sweep)
        
        # Check for low sweep (price spikes below recent low then reverses)
        if len(recent_swing_lows) > 0:
            target_low = recent_swing_lows.iloc[-1]
            
            # Check if candle wicked below the low
            if current_candle['low'] < target_low and current_candle['close'] > target_low:
                # Check for reversal and get distance for grading
                reversal_distance = _get_upside_reversal_distance(
                    df, i, max_sweep_candles, target_low
                )
                
                if reversal_distance > 0:  # Any reversal detected
                    # Check volume if required
                    volume_spike = current_candle['volume'] > (avg_volume.iloc[i] * 1.5) if pd.notna(avg_volume.iloc[i]) else False
                    
                    if not require_volume_spike or volume_spike:
                        # Grade the sweep based on reversal strength
                        reversal_atr = reversal_distance / atr_value if atr_value > 0 else 0.0
                        grade_a_threshold = smc_cfg.grade_a_threshold * min_reversal_atr
                        grade_b_threshold = smc_cfg.grade_b_threshold * min_reversal_atr
                        grade = grade_pattern(reversal_atr, grade_a_threshold, grade_b_threshold)
                        
                        sweep = LiquiditySweep(
                            level=target_low,
                            sweep_type="low",
                            confirmation=volume_spike,
                            timestamp=current_candle.name.to_pydatetime(),
                            grade=grade
                        )
                        liquidity_sweeps.append(sweep)
    
    return liquidity_sweeps


def _get_downside_reversal_distance(
    df: pd.DataFrame,
    sweep_idx: int,
    max_candles: int,
    level: float
) -> float:
    """
    Get the maximum downside reversal distance after sweeping a high.
    
    Args:
        df: OHLCV DataFrame
        sweep_idx: Index of the sweep candle
        max_candles: Maximum candles to check for reversal
        level: The level that was swept
        
    Returns:
        float: Maximum distance below the level (0 if no reversal)
    """
    max_distance = 0.0
    
    # Check subsequent candles
    for i in range(sweep_idx + 1, min(sweep_idx + max_candles + 1, len(df))):
        candle = df.iloc[i]
        
        # Check distance below the swept level
        if candle['close'] < level:
            distance = level - candle['close']
            max_distance = max(max_distance, distance)
    
    return max_distance


def _get_upside_reversal_distance(
    df: pd.DataFrame,
    sweep_idx: int,
    max_candles: int,
    level: float
) -> float:
    """
    Get the maximum upside reversal distance after sweeping a low.
    
    Args:
        df: OHLCV DataFrame
        sweep_idx: Index of the sweep candle
        max_candles: Maximum candles to check for reversal
        level: The level that was swept
        
    Returns:
        float: Maximum distance above the level (0 if no reversal)
    """
    max_distance = 0.0
    
    # Check subsequent candles
    for i in range(sweep_idx + 1, min(sweep_idx + max_candles + 1, len(df))):
        candle = df.iloc[i]
        
        # Check distance above the swept level
        if candle['close'] > level:
            distance = candle['close'] - level
            max_distance = max(max_distance, distance)
    
    return max_distance


def _check_downside_reversal(
    df: pd.DataFrame,
    sweep_idx: int,
    max_candles: int,
    level: float,
    min_distance: float
) -> bool:
    """
    Check if price reversed to downside after sweeping a high.
    DEPRECATED: Use _get_downside_reversal_distance for grading.
    
    Args:
        df: OHLCV DataFrame
        sweep_idx: Index of the sweep candle
        max_candles: Maximum candles to check for reversal
        level: The level that was swept
        min_distance: Minimum reversal distance
        
    Returns:
        bool: True if reversal confirmed
    """
    return _get_downside_reversal_distance(df, sweep_idx, max_candles, level) >= min_distance


def _check_upside_reversal(
    df: pd.DataFrame,
    sweep_idx: int,
    max_candles: int,
    level: float,
    min_distance: float
) -> bool:
    """
    Check if price reversed to upside after sweeping a low.
    DEPRECATED: Use _get_upside_reversal_distance for grading.
    
    Args:
        df: OHLCV DataFrame
        sweep_idx: Index of the sweep candle
        max_candles: Maximum candles to check for reversal
        level: The level that was swept
        min_distance: Minimum reversal distance
        
    Returns:
        bool: True if reversal confirmed
    """
    return _get_upside_reversal_distance(df, sweep_idx, max_candles, level) >= min_distance


def detect_equal_highs_lows(
    df: pd.DataFrame,
    tolerance_pct: float = 0.002,
    config: SMCConfig | dict | None = None,
    timeframe: Optional[str] = None
) -> dict:
    """
    Detect equal highs and equal lows (liquidity pools).
    
    Equal highs/lows represent clustered liquidity that often gets swept.
    
    ENHANCED: Now supports timeframe-aware adaptive parameters via SMCConfig.
    
    Args:
        df: DataFrame with OHLC data
        tolerance_pct: Price tolerance for "equal" determination (default 0.2%)
                       DEPRECATED: Use config.eqhl_base_tolerance_pct instead
        config: SMCConfig for adaptive parameters (recommended)
        timeframe: Timeframe string for scaling (auto-detected if None)
        
    Returns:
        dict: {
            'equal_highs': List[float],  # DEPRECATED - use 'pools' instead
            'equal_lows': List[float],   # DEPRECATED - use 'pools' instead
            'pools': List[LiquidityPool],  # NEW: structured pool objects
            'metadata': {
                'timeframe': str,
                'tolerance_used': float,
                'min_touches': int,
                'highs_detected': int,
                'lows_detected': int
            }
        }
    """
    from backend.strategy.smc.bos_choch import _detect_swing_highs, _detect_swing_lows, _infer_timeframe
    from backend.shared.models.smc import LiquidityPool
    
    # Determine timeframe
    if timeframe is None:
        timeframe = _infer_timeframe(df)
    
    # Get configuration
    if config is None:
        smc_cfg = SMCConfig.defaults()
    elif isinstance(config, dict):
        smc_cfg = SMCConfig.from_dict(config)
    else:
        smc_cfg = config
    
    # Calculate ATR for ATR-based tolerance (if enabled)
    atr_value = None
    if smc_cfg.eqhl_use_atr_tolerance:
        from backend.indicators.volatility import compute_atr
        atr = compute_atr(df, period=14)
        if len(atr) > 0 and pd.notna(atr.iloc[-1]):
            atr_value = atr.iloc[-1]
    
    # Scale parameters based on timeframe
    scaled_lookback = scale_lookback(smc_cfg.eqhl_swing_lookback, timeframe)
    scaled_tolerance = scale_eqhl_tolerance(smc_cfg.eqhl_base_tolerance_pct, timeframe)
    min_touches = get_eqhl_min_touches(timeframe)
    
    # Use ATR-based tolerance if enabled and ATR available
    if smc_cfg.eqhl_use_atr_tolerance and atr_value and atr_value > 0:
        # Use ATR tolerance: cluster_within_atr * ATR
        current_price = df['close'].iloc[-1] if len(df) > 0 else 1.0
        atr_tolerance = (smc_cfg.eqhl_cluster_within_atr * atr_value) / current_price
        # Use the tighter of ATR-based or percentage tolerance
        effective_tolerance = min(atr_tolerance, scaled_tolerance)
    else:
        effective_tolerance = scaled_tolerance
    
    # Detect swing points with scaled lookback
    swing_highs = _detect_swing_highs(df, scaled_lookback)
    swing_lows = _detect_swing_lows(df, scaled_lookback)
    
    # Find clustered equal levels with metadata
    high_clusters = _find_equal_levels_enhanced(
        swing_highs, effective_tolerance, min_touches, df
    )
    low_clusters = _find_equal_levels_enhanced(
        swing_lows, effective_tolerance, min_touches, df
    )
    
    # Create LiquidityPool objects
    pools = []
    
    for cluster in high_clusters:
        grade = _grade_pool_by_touches(cluster['touches'], smc_cfg.eqhl_grade_by_touches)
        pool = LiquidityPool(
            level=cluster['level'],
            pool_type="equal_highs",
            touches=cluster['touches'],
            timeframe=timeframe,
            grade=grade,
            first_touch=cluster.get('first_touch'),
            last_touch=cluster.get('last_touch'),
            tolerance_used=effective_tolerance,
            spread=cluster.get('spread', 0.0)
        )
        pools.append(pool)
    
    for cluster in low_clusters:
        grade = _grade_pool_by_touches(cluster['touches'], smc_cfg.eqhl_grade_by_touches)
        pool = LiquidityPool(
            level=cluster['level'],
            pool_type="equal_lows",
            touches=cluster['touches'],
            timeframe=timeframe,
            grade=grade,
            first_touch=cluster.get('first_touch'),
            last_touch=cluster.get('last_touch'),
            tolerance_used=effective_tolerance,
            spread=cluster.get('spread', 0.0)
        )
        pools.append(pool)
    
    # Sort pools by touch count (strongest first)
    pools.sort(key=lambda p: p.touches, reverse=True)
    
    # Extract simple lists for backward compatibility
    equal_highs = [c['level'] for c in high_clusters]
    equal_lows = [c['level'] for c in low_clusters]
    
    return {
        'equal_highs': equal_highs,
        'equal_lows': equal_lows,
        'pools': pools,
        'metadata': {
            'timeframe': timeframe,
            'tolerance_used': effective_tolerance,
            'min_touches': min_touches,
            'highs_detected': len(equal_highs),
            'lows_detected': len(equal_lows),
            'atr_tolerance_active': smc_cfg.eqhl_use_atr_tolerance and atr_value is not None
        }
    }


def _find_equal_levels_enhanced(
    swing_series: pd.Series,
    tolerance_pct: float,
    min_touches: int,
    df: pd.DataFrame
) -> List[dict]:
    """
    Find levels that are approximately equal (within tolerance) with metadata.
    
    Enhanced version that returns structured cluster info including:
    - Average level price
    - Touch count
    - First/last touch timestamps
    - Price spread within cluster
    
    Args:
        swing_series: Series of swing prices (index=timestamp, value=price)
        tolerance_pct: Tolerance as percentage (e.g., 0.002 = 0.2%)
        min_touches: Minimum number of touches required
        df: Original DataFrame for timestamp lookups
        
    Returns:
        List[dict]: Clusters with level, touches, timestamps, spread
    """
    if len(swing_series) < min_touches:
        return []
    
    levels = swing_series.values
    timestamps = swing_series.index
    
    # Build clusters using union-find style grouping
    used = set()
    clusters = []
    
    for i in range(len(levels)):
        if i in used:
            continue
        
        level = levels[i]
        tolerance = level * tolerance_pct
        
        # Find all levels within tolerance of this one
        cluster_indices = [i]
        cluster_prices = [level]
        cluster_timestamps = [timestamps[i]]
        
        for j in range(len(levels)):
            if j != i and j not in used:
                if abs(levels[j] - level) <= tolerance:
                    cluster_indices.append(j)
                    cluster_prices.append(levels[j])
                    cluster_timestamps.append(timestamps[j])
        
        # Only keep clusters meeting minimum touch requirement
        if len(cluster_indices) >= min_touches:
            # Mark all indices as used
            for idx in cluster_indices:
                used.add(idx)
            
            # Calculate cluster stats
            avg_level = np.mean(cluster_prices)
            spread = max(cluster_prices) - min(cluster_prices)
            
            # Convert timestamps
            ts_list = [ts.to_pydatetime() if hasattr(ts, 'to_pydatetime') else ts 
                      for ts in cluster_timestamps]
            first_touch = min(ts_list)
            last_touch = max(ts_list)
            
            clusters.append({
                'level': avg_level,
                'touches': len(cluster_indices),
                'prices': cluster_prices,
                'first_touch': first_touch,
                'last_touch': last_touch,
                'spread': spread
            })
    
    return clusters


def _grade_pool_by_touches(touches: int, grade_by_touches: bool = True) -> str:
    """
    Grade a liquidity pool by touch count.
    
    Args:
        touches: Number of touches in the pool
        grade_by_touches: Whether to grade by touches (if False, returns 'B')
        
    Returns:
        Grade string ('A', 'B', or 'C')
    """
    if not grade_by_touches:
        return 'B'
    
    if touches >= 4:
        return 'A'  # Strong liquidity pool
    elif touches >= 3:
        return 'B'  # Moderate pool
    else:
        return 'C'  # Weak pool (minimum 2 touches)


def _find_equal_levels(levels: np.ndarray, tolerance_pct: float) -> List[float]:
    """
    Find levels that are approximately equal (within tolerance).
    
    DEPRECATED: Use detect_equal_highs_lows() with config parameter instead.
    This function is kept for backward compatibility only.
    
    Args:
        levels: Array of price levels
        tolerance_pct: Tolerance as percentage (e.g., 0.002 = 0.2%)
        
    Returns:
        List[float]: Levels that have at least one "equal" match
    """
    if len(levels) < 2:
        return []
    
    equal_levels = []
    
    for i in range(len(levels)):
        level = levels[i]
        tolerance = level * tolerance_pct
        
        # Check if any other level is within tolerance
        for j in range(len(levels)):
            if i != j and abs(levels[j] - level) <= tolerance:
                if level not in equal_levels:
                    equal_levels.append(level)
                break
    
    return equal_levels


def get_latest_sweep(sweeps: List[LiquiditySweep], sweep_type: str = None) -> Optional[LiquiditySweep]:
    """
    Get the most recent liquidity sweep.
    
    Args:
        sweeps: List of liquidity sweeps
        sweep_type: Optional filter by type ("high" or "low")
        
    Returns:
        LiquiditySweep or None: Latest sweep, or None if list is empty
    """
    if not sweeps:
        return None
    
    # Filter by type if specified
    if sweep_type:
        sweeps = [s for s in sweeps if s.sweep_type == sweep_type]
    
    if not sweeps:
        return None
    
    return max(sweeps, key=lambda s: s.timestamp)


def check_double_sweep(sweeps: List[LiquiditySweep], level_tolerance_pct: float = 0.001) -> List[tuple]:
    """
    Detect double sweeps (same level swept twice) - strong reversal signal.
    
    Args:
        sweeps: List of liquidity sweeps
        level_tolerance_pct: Tolerance for considering levels "equal"
        
    Returns:
        List[tuple]: Pairs of sweeps at same level (sweep1, sweep2)
    """
    if len(sweeps) < 2:
        return []
    
    double_sweeps = []
    
    for i in range(len(sweeps)):
        for j in range(i + 1, len(sweeps)):
            sweep1 = sweeps[i]
            sweep2 = sweeps[j]
            
            # Check if same type and similar level
            if sweep1.sweep_type == sweep2.sweep_type:
                tolerance = sweep1.level * level_tolerance_pct
                if abs(sweep1.level - sweep2.level) <= tolerance:
                    double_sweeps.append((sweep1, sweep2))
    
    return double_sweeps


def validate_sweep_with_structure(
    sweep: LiquiditySweep,
    structural_breaks: List
) -> bool:
    """
    Validate that a liquidity sweep preceded a structural break.
    
    Sweeps are more significant when followed by BOS/CHoCH.
    
    Args:
        sweep: Liquidity sweep to validate
        structural_breaks: List of StructuralBreak objects
        
    Returns:
        bool: True if sweep was followed by structural break
    """
    if not structural_breaks:
        return False
    
    # Find structural breaks that occurred after the sweep
    subsequent_breaks = [
        sb for sb in structural_breaks
        if sb.timestamp > sweep.timestamp
    ]
    
    if not subsequent_breaks:
        return False
    
    # Check if any break occurred within reasonable timeframe
    # (Within next 10 candles worth of time - simplified)
    nearest_break = min(subsequent_breaks, key=lambda sb: sb.timestamp)
    
    time_diff = nearest_break.timestamp - sweep.timestamp
    
    # If break happened within reasonable time, consider it related
    # This is a simplified check - in practice would be more sophisticated
    return time_diff.total_seconds() < 3600 * 24  # Within 24 hours


def track_pool_sweeps(
    df: pd.DataFrame,
    pools: List[LiquidityPool]
) -> List[LiquidityPool]:
    """
    Update LiquidityPool objects with sweep tracking information.
    
    When price breaks through a pool level, marks the pool as swept
    with the bar index and timestamp of the sweep.
    
    STOLEN from smartmoneyconcepts library.
    
    Args:
        df: OHLCV DataFrame with DatetimeIndex
        pools: List of LiquidityPool objects
        
    Returns:
        List[LiquidityPool]: Updated pools with sweep tracking
    """
    from dataclasses import replace
    
    if not pools or len(df) == 0:
        return pools
    
    updated_pools = []
    
    for pool in pools:
        if pool.swept:
            # Already swept, keep as-is
            updated_pools.append(pool)
            continue
        
        swept = False
        swept_idx = None
        swept_ts = None
        
        # Check each candle for sweep
        for i in range(len(df)):
            candle = df.iloc[i]
            
            if pool.pool_type == "equal_highs":
                # Pool swept when price closes above the level
                if candle['close'] > pool.level:
                    swept = True
                    swept_idx = i
                    swept_ts = df.index[i].to_pydatetime()
                    break
            else:  # equal_lows
                # Pool swept when price closes below the level
                if candle['close'] < pool.level:
                    swept = True
                    swept_idx = i
                    swept_ts = df.index[i].to_pydatetime()
                    break
        
        if swept:
            updated_pool = replace(
                pool,
                swept=True,
                swept_index=swept_idx,
                swept_timestamp=swept_ts
            )
            updated_pools.append(updated_pool)
        else:
            updated_pools.append(pool)
    
    return updated_pools

