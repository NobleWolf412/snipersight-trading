"""
Liquidity Sweep Detection Module

Implements Smart Money Concept liquidity sweep detection.

Liquidity sweeps occur when:
- Price briefly exceeds a key level (high/low) to trigger stop losses
- Price quickly reverses, showing the move was a "trap"
- Often precedes strong moves in opposite direction
"""

from typing import List, Optional
from datetime import datetime
import pandas as pd
import numpy as np

from backend.shared.models.smc import LiquiditySweep


def detect_liquidity_sweeps(
    df: pd.DataFrame,
    config: dict = None
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
        config = {}
    swing_lookback = config.get('swing_lookback', 10)
    max_sweep_candles = config.get('max_sweep_candles', 3)
    min_reversal_atr = config.get('min_reversal_atr', 1.0)
    require_volume_spike = config.get('require_volume_spike', False)
    
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
                # Check for reversal in next few candles
                reversal_confirmed = _check_downside_reversal(
                    df, i, max_sweep_candles, target_high, min_reversal_atr * atr_value
                )
                
                if reversal_confirmed:
                    # Check volume if required
                    volume_spike = current_candle['volume'] > (avg_volume.iloc[i] * 1.5) if pd.notna(avg_volume.iloc[i]) else False
                    
                    if not require_volume_spike or volume_spike:
                        sweep = LiquiditySweep(
                            level=target_high,
                            sweep_type="high",
                            confirmation=volume_spike,
                            timestamp=current_candle.name.to_pydatetime()
                        )
                        liquidity_sweeps.append(sweep)
        
        # Check for low sweep (price spikes below recent low then reverses)
        if len(recent_swing_lows) > 0:
            target_low = recent_swing_lows.iloc[-1]
            
            # Check if candle wicked below the low
            if current_candle['low'] < target_low and current_candle['close'] > target_low:
                # Check for reversal in next few candles
                reversal_confirmed = _check_upside_reversal(
                    df, i, max_sweep_candles, target_low, min_reversal_atr * atr_value
                )
                
                if reversal_confirmed:
                    # Check volume if required
                    volume_spike = current_candle['volume'] > (avg_volume.iloc[i] * 1.5) if pd.notna(avg_volume.iloc[i]) else False
                    
                    if not require_volume_spike or volume_spike:
                        sweep = LiquiditySweep(
                            level=target_low,
                            sweep_type="low",
                            confirmation=volume_spike,
                            timestamp=current_candle.name.to_pydatetime()
                        )
                        liquidity_sweeps.append(sweep)
    
    return liquidity_sweeps


def _check_downside_reversal(
    df: pd.DataFrame,
    sweep_idx: int,
    max_candles: int,
    level: float,
    min_distance: float
) -> bool:
    """
    Check if price reversed to downside after sweeping a high.
    
    Args:
        df: OHLCV DataFrame
        sweep_idx: Index of the sweep candle
        max_candles: Maximum candles to check for reversal
        level: The level that was swept
        min_distance: Minimum reversal distance
        
    Returns:
        bool: True if reversal confirmed
    """
    # Check subsequent candles
    for i in range(sweep_idx + 1, min(sweep_idx + max_candles + 1, len(df))):
        candle = df.iloc[i]
        
        # Check if price moved significantly below the swept level
        if candle['close'] < level - min_distance:
            return True
    
    return False


def _check_upside_reversal(
    df: pd.DataFrame,
    sweep_idx: int,
    max_candles: int,
    level: float,
    min_distance: float
) -> bool:
    """
    Check if price reversed to upside after sweeping a low.
    
    Args:
        df: OHLCV DataFrame
        sweep_idx: Index of the sweep candle
        max_candles: Maximum candles to check for reversal
        level: The level that was swept
        min_distance: Minimum reversal distance
        
    Returns:
        bool: True if reversal confirmed
    """
    # Check subsequent candles
    for i in range(sweep_idx + 1, min(sweep_idx + max_candles + 1, len(df))):
        candle = df.iloc[i]
        
        # Check if price moved significantly above the swept level
        if candle['close'] > level + min_distance:
            return True
    
    return False


def detect_equal_highs_lows(
    df: pd.DataFrame,
    tolerance_pct: float = 0.002
) -> dict:
    """
    Detect equal highs and equal lows (liquidity pools).
    
    Equal highs/lows represent clustered liquidity that often gets swept.
    
    Args:
        df: DataFrame with OHLC data
        tolerance_pct: Price tolerance for "equal" determination (default 0.2%)
        
    Returns:
        dict: {'equal_highs': List[float], 'equal_lows': List[float]}
    """
    from backend.strategy.smc.bos_choch import _detect_swing_highs, _detect_swing_lows
    
    swing_highs = _detect_swing_highs(df, lookback=5)
    swing_lows = _detect_swing_lows(df, lookback=5)
    
    equal_highs = _find_equal_levels(swing_highs.values, tolerance_pct)
    equal_lows = _find_equal_levels(swing_lows.values, tolerance_pct)
    
    return {
        'equal_highs': equal_highs,
        'equal_lows': equal_lows
    }


def _find_equal_levels(levels: np.ndarray, tolerance_pct: float) -> List[float]:
    """
    Find levels that are approximately equal (within tolerance).
    
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
