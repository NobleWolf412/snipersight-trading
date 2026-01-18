"""
Fair Value Gap (FVG) Detection Module

Implements Smart Money Concept Fair Value Gap detection.

Fair Value Gaps are price inefficiencies where:
- Candle 1's high/low does not overlap with Candle 3's low/high
- Candle 2 creates a "gap" in price action
- These gaps often act as support/resistance when revisited
"""

from typing import List, Optional
from datetime import datetime
import pandas as pd
import numpy as np
import logging

from backend.shared.models.smc import FVG, grade_pattern
from backend.shared.config.smc_config import SMCConfig

logger = logging.getLogger(__name__)


# Mode-specific FVG minimum sizes (in ATR units)
MODE_FVG_MIN_SIZE = {
    "macro_surveillance": 0.6,   # OVERWATCH: Large institutional gaps only
    "stealth_balanced": 0.4,      # STEALTH: Balanced medium gaps
    "intraday_aggressive": 0.25,  # STRIKE: Smaller for faster intraday moves
    "precision": 0.15,            # SURGICAL: Micro-gaps for precision scalp entries
}


def detect_fvgs(
    df: pd.DataFrame, 
    config: SMCConfig | dict | None = None,
    mode_profile: Optional[str] = None
) -> List[FVG]:
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
        mode_profile: Scanner mode profile for size filtering (optional)
            
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
    
    # Get mode-specific minimum size (if mode provided)
    if mode_profile and mode_profile in MODE_FVG_MIN_SIZE:
        min_gap_atr = MODE_FVG_MIN_SIZE[mode_profile]
    else:
        min_gap_atr = smc_cfg.fvg_min_gap_atr
    
    max_overlap = smc_cfg.fvg_max_overlap
    
    # Calculate ATR for gap size filtering
    from backend.indicators.volatility import compute_atr
    atr = compute_atr(df, period=14)
    
    fvgs = []
    
    # Diagnostic counters
    potential_bullish_gaps = 0
    bullish_overlap_fails = 0
    bullish_size_fails = 0
    potential_bearish_gaps = 0
    bearish_overlap_fails = 0
    bearish_size_fails = 0
    
    # Scan for FVGs (need at least 3 candles)
    for i in range(2, len(df)):
        candle_0 = df.iloc[i - 2]  # First candle
        candle_1 = df.iloc[i - 1]  # Middle candle (creates the gap)
        candle_2 = df.iloc[i]      # Third candle
        
        # Check for bullish FVG
        # Gap exists if candle_0.high < candle_2.low
        if candle_0['high'] < candle_2['low']:
            potential_bullish_gaps += 1
            gap_top = candle_2['low']
            gap_bottom = candle_0['high']
            gap_size = gap_top - gap_bottom
            
            # Check overlap with middle candle (should be minimal)
            overlap = _calculate_overlap_bullish(candle_1, gap_bottom, gap_top)
            
            if overlap > max_overlap:
                bullish_overlap_fails += 1
                logger.debug("⚠️ %s Bullish FVG @ %.2f-%.2f: overlap=%.1f%% > %.1f%% max",
                            _infer_timeframe(df), gap_bottom, gap_top,
                            overlap * 100, max_overlap * 100)
            
            if overlap <= max_overlap:
                # Calculate gap size in ATR units
                atr_value = atr.iloc[i] if pd.notna(atr.iloc[i]) else 0
                gap_atr = gap_size / atr_value if atr_value > 0 else 0.0
                
                # Mode-specific filtering: Skip FVGs below minimum size
                if gap_atr < min_gap_atr:
                    bullish_size_fails += 1
                    logger.debug("⚠️ %s Bullish FVG rejected @ %.2f-%.2f: gap_atr=%.3f < %.3f required",
                                _infer_timeframe(df), gap_bottom, gap_top,
                                gap_atr, min_gap_atr)
                    continue
                
                # Grade the FVG based on gap size (A = significant, B = moderate, C = small)
                grade_a_threshold = smc_cfg.grade_a_threshold * min_gap_atr
                grade_b_threshold = smc_cfg.grade_b_threshold * min_gap_atr
                grade = grade_pattern(gap_atr, grade_a_threshold, grade_b_threshold)
                
                fvg = FVG(
                    timeframe=_infer_timeframe(df),
                    direction="bullish",
                    top=gap_top,
                    bottom=gap_bottom,
                    timestamp=candle_2.name.to_pydatetime(),
                    size=gap_size,
                    overlap_with_price=0.0,  # Will be updated if price revisits
                    freshness_score=1.0,  # Start fresh, decay applied later
                    grade=grade
                )
                fvgs.append(fvg)
        
        # Check for bearish FVG
        # Gap exists if candle_0.low > candle_2.high
        if candle_0['low'] > candle_2['high']:
            gap_top = candle_0['low']
            gap_bottom = candle_2['high']
            gap_size = gap_top - gap_bottom
            
            # Check overlap with middle candle (should be minimal)
            overlap = _calculate_overlap_bearish(candle_1, gap_bottom, gap_top)
            
            if overlap <= max_overlap:
                # Calculate gap size in ATR units
                atr_value = atr.iloc[i] if pd.notna(atr.iloc[i]) else 0
                gap_atr = gap_size / atr_value if atr_value > 0 else 0.0
                
                # Mode-specific filtering: Skip FVGs below minimum size
                if gap_atr < min_gap_atr:
                    bearish_size_fails += 1
                    logger.debug("⚠️ %s Bearish FVG rejected @ %.2f-%.2f: gap_atr=%.3f < %.3f required",
                                _infer_timeframe(df), gap_bottom, gap_top,
                                gap_atr, min_gap_atr)
                    continue
                
                # Grade the FVG based on gap size (A = significant, B = moderate, C = small)
                grade_a_threshold = smc_cfg.grade_a_threshold * min_gap_atr
                grade_b_threshold = smc_cfg.grade_b_threshold * min_gap_atr
                grade = grade_pattern(gap_atr, grade_a_threshold, grade_b_threshold)
                
                fvg = FVG(
                    timeframe=_infer_timeframe(df),
                    direction="bearish",
                    top=gap_top,
                    bottom=gap_bottom,
                    timestamp=candle_2.name.to_pydatetime(),
                    size=gap_size,
                    overlap_with_price=0.0,
                    freshness_score=1.0,  # Start fresh, decay applied later
                    grade=grade
                )
                fvgs.append(fvg)
    
    # Update overlap_with_price and freshness_score for all FVGs based on current price and time
    if len(fvgs) > 0 and len(df) > 0:
        current_price = df['close'].iloc[-1]
        current_time = df.index[-1].to_pydatetime()
        
        # Get timeframe decay factor (similar to OB freshness)
        tf_str = _infer_timeframe(df)
        decay_factor = _get_freshness_decay_factor(tf_str)
        
        for i, fvg in enumerate(fvgs):
            overlap = check_price_overlap(current_price, fvg)
            
            # Calculate freshness based on candles since formation
            candles_since = len(df[df.index > fvg.timestamp])
            freshness = max(0.0, 1.0 - (candles_since * decay_factor))
            
            # Update FVG (since dataclass is frozen, we need to replace)
            from dataclasses import replace
            fvgs[i] = replace(fvg, overlap_with_price=overlap, freshness_score=freshness)
    
    # Log diagnostic summary
    if potential_bullish_gaps > 0 or potential_bearish_gaps > 0:
        logger.info(
            "🔍 %s FVG Detection: Found %d bullish gaps (%d overlap fails, %d size fails) | "
            "%d bearish gaps (%d overlap fails, %d size fails) → %d FVGs passed",
            _infer_timeframe(df),
            potential_bullish_gaps, bullish_overlap_fails, bullish_size_fails,
            potential_bearish_gaps, bearish_overlap_fails, bearish_size_fails,
            len(fvgs)
        )
    
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


def check_fvg_fill(df: pd.DataFrame, fvg: FVG, use_wicks: bool = True) -> bool:
    """
    Check if an FVG has been filled (price fully closed the gap).
    
    Args:
        df: DataFrame with OHLC data
        fvg: FVG to check
        use_wicks: If True, use high/low for fill detection (more accurate).
                   If False, use close price only (more conservative).
        
    Returns:
        bool: True if FVG has been completely filled
    """
    # Get candles after the FVG formation
    future_candles = df[df.index > fvg.timestamp]
    
    if len(future_candles) == 0:
        return False  # No future data, FVG unfilled
    
    if fvg.direction == "bullish":
        # Bullish FVG is filled if price drops back through the gap
        if use_wicks:
            # Check if any wick touched below the gap bottom
            lowest_price = future_candles['low'].min()
        else:
            # Conservative: only count closes below
            lowest_price = future_candles['close'].min()
        return lowest_price < fvg.bottom
    
    else:  # bearish
        # Bearish FVG is filled if price rises through the gap
        if use_wicks:
            # Check if any wick touched above the gap top
            highest_price = future_candles['high'].max()
        else:
            # Conservative: only count closes above
            highest_price = future_candles['close'].max()
        return highest_price > fvg.top


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


def _get_freshness_decay_factor(timeframe: str) -> float:
    """
    Get freshness decay rate per candle based on timeframe.
    
    Higher timeframes decay slower (OBs/FVGs stay relevant longer).
    Lower timeframes decay faster (zones go stale quicker).
    
    Args:
        timeframe: Timeframe string (e.g., "1H", "4H", "1D")
        
    Returns:
        float: Decay per candle (0.01 = 1% per candle)
    """
    # Map timeframes to decay factors
    # After N candles at decay D, freshness = 1 - (N * D)
    # Goal: ~50% freshness after typical "good" number of candles
    decay_map = {
        '1W': 0.02,   # ~50% after 25 candles (25 weeks)
        '1D': 0.025,  # ~50% after 20 candles (20 days)
        '4H': 0.03,   # ~50% after 17 candles (68 hours)
        '1H': 0.04,   # ~50% after 12-13 candles (12 hours)
        '15m': 0.05,  # ~50% after 10 candles (2.5 hours)
        '5m': 0.06,   # ~50% after 8 candles (40 minutes)
    }
    
    # Try exact match first
    tf_upper = timeframe.upper()
    if tf_upper in decay_map:
        return decay_map[tf_upper]
    
    # Normalize common variants
    tf_normalized = tf_upper.replace('MIN', 'm').replace('H', 'H').replace('D', 'D')
    if tf_normalized in decay_map:
        return decay_map[tf_normalized]
    
    # Default moderate decay
    return 0.04


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


def merge_consecutive_fvgs(
    fvgs: List[FVG],
    max_gap_atr: float = 0.5,
    atr_value: float = 1.0
) -> List[FVG]:
    """
    Merge overlapping or adjacent consecutive FVGs of the same direction.
    
    When multiple FVGs form in close succession, they create one larger
    imbalance zone. Merging them provides cleaner S/R levels.
    
    STOLEN from smartmoneyconcepts library.
    
    Args:
        fvgs: List of FVG objects (should be sorted by timestamp)
        max_gap_atr: Maximum gap between FVGs to merge (in ATR units)
        atr_value: ATR value for proximity calculation
        
    Returns:
        List[FVG]: Merged FVGs (fewer, larger zones)
    """
    if len(fvgs) < 2:
        return fvgs
    
    # Sort by timestamp
    sorted_fvgs = sorted(fvgs, key=lambda f: f.timestamp)
    
    merged = []
    current = sorted_fvgs[0]
    
    for next_fvg in sorted_fvgs[1:]:
        # Check if same direction
        if next_fvg.direction != current.direction:
            merged.append(current)
            current = next_fvg
            continue
        
        # Calculate gap between FVGs
        if current.direction == "bullish":
            # Bullish: check if next_fvg.bottom overlaps or is close to current.top
            gap = next_fvg.bottom - current.top
        else:
            # Bearish: check if current.bottom overlaps or is close to next_fvg.top
            gap = current.bottom - next_fvg.top
        
        # Merge if overlapping or close enough
        max_gap = max_gap_atr * atr_value if atr_value > 0 else 0.001
        
        if gap <= max_gap:
            # Merge: extend current to include next
            from dataclasses import replace
            
            new_top = max(current.top, next_fvg.top)
            new_bottom = min(current.bottom, next_fvg.bottom)
            new_size = new_top - new_bottom
            
            # Take best grade between merged FVGs
            best_grade = 'A' if ('A' in [current.grade, next_fvg.grade]) else \
                         ('B' if 'B' in [current.grade, next_fvg.grade] else 'C')
            
            current = replace(
                current,
                top=new_top,
                bottom=new_bottom,
                size=new_size,
                grade=best_grade
            )
        else:
            # Too far apart - keep separate
            merged.append(current)
            current = next_fvg
    
    # Don't forget the last one
    merged.append(current)
    
    return merged

