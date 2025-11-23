"""
Fair Value Gap (FVG) Detection Module

Implements Smart Money Concept Fair Value Gap detection.

Fair Value Gaps are price inefficiencies where:
- Candle 1's high/low does not overlap with Candle 3's low/high
- Candle 2 creates a "gap" in price action
- These gaps often act as support/resistance when revisited
"""

from typing import List
from datetime import datetime
import pandas as pd
import numpy as np

from backend.shared.models.smc import FVG
from backend.shared.config.smc_config import SMCConfig


def detect_fvgs(df: pd.DataFrame, config: SMCConfig | dict | None = None) -> List[FVG]:
    """
    Detect Fair Value Gaps in price data.
    
    FVG formation:
    - Bullish FVG: Gap between candle[i-2].high and candle[i].low (candle[i-1] creates gap)
    - Bearish FVG: Gap between candle[i-2].low and candle[i].high (candle[i-1] creates gap)
    
    Args:
        df: DataFrame with OHLC data and DatetimeIndex
        config: Configuration dict with:
            - min_gap_atr: Minimum gap size in ATR units (default 0.3)
            - max_overlap: Maximum allowed overlap percentage (default 0.1)
            
    Returns:
        List[FVG]: Detected fair value gaps
        
    Raises:
        ValueError: If df is too short or missing required columns
    """
    required_cols = ['open', 'high', 'low', 'close']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"DataFrame missing required columns: {missing_cols}")
    
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame must have DatetimeIndex")
    
    if len(df) < 20:  # Need minimum data for ATR
        raise ValueError(f"DataFrame too short for FVG detection (need at least 20 rows, got {len(df)})")
    
    # Configuration
    if config is None:
        smc_cfg = SMCConfig.defaults()
    elif isinstance(config, dict):
        mapped = {}
        if 'min_gap_atr' in config:
            mapped['fvg_min_gap_atr'] = config['min_gap_atr']
        if 'max_overlap' in config:
            mapped['fvg_max_overlap'] = config['max_overlap']
        smc_cfg = SMCConfig.from_dict(mapped)
    else:
        smc_cfg = config
    min_gap_atr = smc_cfg.fvg_min_gap_atr
    max_overlap = smc_cfg.fvg_max_overlap
    
    # Calculate ATR for gap size filtering
    from backend.indicators.volatility import compute_atr
    atr = compute_atr(df, period=14)
    
    fvgs = []
    
    # Scan for FVGs (need at least 3 candles)
    for i in range(2, len(df)):
        candle_0 = df.iloc[i - 2]  # First candle
        candle_1 = df.iloc[i - 1]  # Middle candle (creates the gap)
        candle_2 = df.iloc[i]      # Third candle
        
        # Check for bullish FVG
        # Gap exists if candle_0.high < candle_2.low
        if candle_0['high'] < candle_2['low']:
            gap_top = candle_2['low']
            gap_bottom = candle_0['high']
            gap_size = gap_top - gap_bottom
            
            # Filter by minimum gap size
            atr_value = atr.iloc[i] if pd.notna(atr.iloc[i]) else 0
            if atr_value > 0 and gap_size / atr_value >= min_gap_atr:
                # Check overlap with middle candle (should be minimal)
                overlap = _calculate_overlap_bullish(candle_1, gap_bottom, gap_top)
                
                if overlap <= max_overlap:
                    fvg = FVG(
                        timeframe=_infer_timeframe(df),
                        direction="bullish",
                        top=gap_top,
                        bottom=gap_bottom,
                        timestamp=candle_2.name.to_pydatetime(),
                        size=gap_size,
                        overlap_with_price=0.0  # Will be updated if price revisits
                    )
                    fvgs.append(fvg)
        
        # Check for bearish FVG
        # Gap exists if candle_0.low > candle_2.high
        if candle_0['low'] > candle_2['high']:
            gap_top = candle_0['low']
            gap_bottom = candle_2['high']
            gap_size = gap_top - gap_bottom
            
            # Filter by minimum gap size
            atr_value = atr.iloc[i] if pd.notna(atr.iloc[i]) else 0
            if atr_value > 0 and gap_size / atr_value >= min_gap_atr:
                # Check overlap with middle candle (should be minimal)
                overlap = _calculate_overlap_bearish(candle_1, gap_bottom, gap_top)
                
                if overlap <= max_overlap:
                    fvg = FVG(
                        timeframe=_infer_timeframe(df),
                        direction="bearish",
                        top=gap_top,
                        bottom=gap_bottom,
                        timestamp=candle_2.name.to_pydatetime(),
                        size=gap_size,
                        overlap_with_price=0.0
                    )
                    fvgs.append(fvg)
    
    # Update overlap_with_price for all FVGs based on current price
    if len(fvgs) > 0 and len(df) > 0:
        current_price = df['close'].iloc[-1]
        
        for i, fvg in enumerate(fvgs):
            overlap = check_price_overlap(current_price, fvg)
            # Update FVG (since dataclass is frozen, we need to replace)
            from dataclasses import replace
            fvgs[i] = replace(fvg, overlap_with_price=overlap)
    
    return fvgs


def _calculate_overlap_bullish(candle: pd.Series, gap_bottom: float, gap_top: float) -> float:
    """
    Calculate how much a candle overlaps with a bullish FVG.
    
    Args:
        candle: Middle candle that creates the gap
        gap_bottom: Bottom of the gap
        gap_top: Top of the gap
        
    Returns:
        float: Overlap percentage (0.0 = no overlap, 1.0 = full overlap)
    """
    # Check if candle penetrates into the gap
    overlap_high = min(candle['high'], gap_top)
    overlap_low = max(candle['low'], gap_bottom)
    
    if overlap_high <= overlap_low:
        return 0.0  # No overlap
    
    overlap_size = overlap_high - overlap_low
    gap_size = gap_top - gap_bottom
    
    return overlap_size / gap_size if gap_size > 0 else 0.0


def _calculate_overlap_bearish(candle: pd.Series, gap_bottom: float, gap_top: float) -> float:
    """
    Calculate how much a candle overlaps with a bearish FVG.
    
    Args:
        candle: Middle candle that creates the gap
        gap_bottom: Bottom of the gap
        gap_top: Top of the gap
        
    Returns:
        float: Overlap percentage (0.0 = no overlap, 1.0 = full overlap)
    """
    # Same logic as bullish - just checking middle candle penetration
    overlap_high = min(candle['high'], gap_top)
    overlap_low = max(candle['low'], gap_bottom)
    
    if overlap_high <= overlap_low:
        return 0.0  # No overlap
    
    overlap_size = overlap_high - overlap_low
    gap_size = gap_top - gap_bottom
    
    return overlap_size / gap_size if gap_size > 0 else 0.0


def calculate_fvg_size(fvg: FVG) -> float:
    """
    Calculate the size of a Fair Value Gap.
    
    Args:
        fvg: FVG to measure
        
    Returns:
        float: Gap size (absolute price difference)
    """
    return fvg.size


def check_price_overlap(price: float, fvg: FVG) -> float:
    """
    Check if current price overlaps with an FVG.
    
    Args:
        price: Current price level
        fvg: FVG to check
        
    Returns:
        float: Overlap percentage (0.0 = no overlap, 1.0 = price at center of gap)
    """
    if price < fvg.bottom or price > fvg.top:
        return 0.0  # Price outside the gap
    
    # Price is within the gap
    gap_size = fvg.top - fvg.bottom
    
    if gap_size < 1e-10:
        return 1.0  # Avoid division by zero
    
    # Calculate how far into the gap the price is (from bottom)
    penetration = price - fvg.bottom
    overlap_ratio = penetration / gap_size
    
    return min(1.0, max(0.0, overlap_ratio))


def check_fvg_fill(df: pd.DataFrame, fvg: FVG) -> bool:
    """
    Check if an FVG has been filled (price fully closed the gap).
    
    Args:
        df: DataFrame with OHLC data
        fvg: FVG to check
        
    Returns:
        bool: True if FVG has been completely filled
    """
    # Get candles after the FVG formation
    future_candles = df[df.index > fvg.timestamp]
    
    if len(future_candles) == 0:
        return False  # No future data, FVG unfilled
    
    if fvg.direction == "bullish":
        # Bullish FVG is filled if price drops back and closes below the gap bottom
        lowest_close = future_candles['close'].min()
        return lowest_close < fvg.bottom
    
    else:  # bearish
        # Bearish FVG is filled if price rises and closes above the gap top
        highest_close = future_candles['close'].max()
        return highest_close > fvg.top


def filter_unfilled_fvgs(df: pd.DataFrame, fvgs: List[FVG]) -> List[FVG]:
    """
    Filter to only unfilled FVGs.
    
    Args:
        df: DataFrame with OHLC data
        fvgs: List of FVGs to filter
        
    Returns:
        List[FVG]: Only FVGs that have not been filled
    """
    return [fvg for fvg in fvgs if not check_fvg_fill(df, fvg)]


def get_nearest_fvg(fvgs: List[FVG], price: float, direction: str = None) -> FVG:
    """
    Get the nearest FVG to current price.
    
    Args:
        fvgs: List of FVGs
        price: Current price
        direction: Optional filter by direction ("bullish" or "bearish")
        
    Returns:
        FVG or None: Nearest FVG, or None if list is empty
    """
    if not fvgs:
        return None
    
    # Filter by direction if specified
    if direction:
        fvgs = [fvg for fvg in fvgs if fvg.direction == direction]
    
    if not fvgs:
        return None
    
    # Calculate distance to each FVG (use midpoint)
    def distance_to_fvg(fvg: FVG) -> float:
        fvg_midpoint = (fvg.top + fvg.bottom) / 2
        return abs(price - fvg_midpoint)
    
    nearest = min(fvgs, key=distance_to_fvg)
    return nearest


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
    
    if len(time_deltas) == 0:
        return "unknown"
    
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
