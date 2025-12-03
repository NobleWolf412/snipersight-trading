"""
Break of Structure (BOS) and Change of Character (CHoCH) Detection Module

Implements Smart Money Concept structural break detection:
- BOS (Break of Structure): Continuation pattern, breaks previous high/low in trend direction
- CHoCH (Change of Character): Reversal signal, breaks counter-trend high/low

These patterns identify shifts in market structure and potential trend changes.
"""

from typing import List, Optional, Tuple, TYPE_CHECKING
from datetime import datetime
import pandas as pd
import numpy as np

from backend.shared.models.smc import StructuralBreak
from backend.shared.config.smc_config import SMCConfig

# Conditional import for type hints to avoid circular imports
if TYPE_CHECKING:
    from backend.shared.models.smc import CycleContext


def detect_structural_breaks(
    df: pd.DataFrame,
    config: SMCConfig | dict | None = None,
    htf_df: Optional[pd.DataFrame] = None,
    htf_trend: Optional[str] = None,
    cycle_context: Optional["CycleContext"] = None
) -> List[StructuralBreak]:
    """
    Detect Break of Structure (BOS) and Change of Character (CHoCH) patterns.
    
    Process:
    1. Identify swing highs and swing lows
    2. Track current market structure (uptrend/downtrend)
    3. Detect when structure breaks (BOS) or changes (CHoCH)
    4. Check alignment with higher timeframe trend if provided
    5. Apply cycle-aware bypass for CHoCH at cycle extremes (if cycle_context provided)
    
    Args:
        df: DataFrame with OHLC data and DatetimeIndex
        config: Configuration dict with:
            - swing_lookback: Candles to each side for swing detection (default 5)
            - min_break_distance_atr: Minimum break distance in ATR (default 0.5)
        htf_df: Optional higher timeframe DataFrame for alignment checks
        htf_trend: Optional explicit HTF trend ("uptrend", "downtrend") to use
                   instead of calculating from htf_df
        cycle_context: Optional CycleContext for cycle-aware HTF bypass at extremes
            
    Returns:
        List[StructuralBreak]: Detected structural breaks
        
    Raises:
        ValueError: If df is too short or missing required columns
    """
    required_cols = ['high', 'low', 'close']
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
            mapped['structure_swing_lookback'] = config['swing_lookback']
        if 'min_break_distance_atr' in config:
            mapped['structure_min_break_distance_atr'] = config['min_break_distance_atr']
        smc_cfg = SMCConfig.from_dict(mapped)
    else:
        smc_cfg = config
    swing_lookback = smc_cfg.structure_swing_lookback
    min_break_distance_atr = smc_cfg.structure_min_break_distance_atr
    
    if len(df) < swing_lookback * 2 + 20:
        raise ValueError(f"DataFrame too short for structural break detection (need {swing_lookback * 2 + 20} rows, got {len(df)})")
    
    # Calculate ATR for filtering
    from backend.indicators.volatility import compute_atr
    atr = compute_atr(df, period=14)
    
    # Determine HTF trend for alignment checks
    # Priority: explicit htf_trend > calculated from htf_df > None
    computed_htf_trend = None
    if htf_trend:
        computed_htf_trend = htf_trend
    elif htf_df is not None and len(htf_df) >= 20:
        computed_htf_trend = _calculate_htf_trend(htf_df)
    
    # Detect swing highs and lows
    swing_highs = _detect_swing_highs(df, swing_lookback)
    swing_lows = _detect_swing_lows(df, swing_lookback)
    
    # Track market structure and detect breaks
    structural_breaks = []
    
    # Determine initial trend (use first swing points)
    current_trend = _determine_initial_trend(swing_highs, swing_lows)
    
    last_swing_high = None
    last_swing_low = None
    
    # Iterate through price data
    for i in range(swing_lookback * 2, len(df)):
        current_idx = df.index[i]
        current_high = df['high'].iloc[i]
        current_low = df['low'].iloc[i]
        current_close = df['close'].iloc[i]
        
        # Update swing points up to current position
        if current_idx in swing_highs.index:
            last_swing_high = swing_highs.loc[current_idx]
        
        if current_idx in swing_lows.index:
            last_swing_low = swing_lows.loc[current_idx]
        
        # Need at least one swing point of each type to detect breaks
        if last_swing_high is None or last_swing_low is None:
            continue
        
        atr_value = atr.iloc[i] if pd.notna(atr.iloc[i]) else 0
        
        # Check for breaks in uptrend
        if current_trend == "uptrend":
            # BOS: Break above previous swing high (continuation)
            if current_close > last_swing_high + (min_break_distance_atr * atr_value):
                # HTF alignment: BOS in uptrend aligns if HTF is also uptrend or unknown
                htf_aligned = _check_bos_htf_alignment("uptrend", computed_htf_trend)
                
                structural_break = StructuralBreak(
                    timeframe=_infer_timeframe(df),
                    break_type="BOS",
                    level=last_swing_high,
                    timestamp=current_idx.to_pydatetime(),
                    htf_aligned=htf_aligned
                )
                structural_breaks.append(structural_break)
            
            # CHoCH: Break below previous swing low (reversal)
            elif current_close < last_swing_low - (min_break_distance_atr * atr_value):
                # HTF alignment: CHoCH in uptrend aligns if HTF is downtrend
                # Or bypassed if at cycle extreme (structure broken at cycle low/high)
                htf_aligned = _check_choch_htf_alignment("uptrend", computed_htf_trend, cycle_context)
                
                structural_break = StructuralBreak(
                    timeframe=_infer_timeframe(df),
                    break_type="CHoCH",
                    level=last_swing_low,
                    timestamp=current_idx.to_pydatetime(),
                    htf_aligned=htf_aligned
                )
                structural_breaks.append(structural_break)
                
                # Change trend
                current_trend = "downtrend"
        
        # Check for breaks in downtrend
        elif current_trend == "downtrend":
            # BOS: Break below previous swing low (continuation)
            if current_close < last_swing_low - (min_break_distance_atr * atr_value):
                # HTF alignment: BOS in downtrend aligns if HTF is also downtrend or unknown
                htf_aligned = _check_bos_htf_alignment("downtrend", computed_htf_trend)
                
                structural_break = StructuralBreak(
                    timeframe=_infer_timeframe(df),
                    break_type="BOS",
                    level=last_swing_low,
                    timestamp=current_idx.to_pydatetime(),
                    htf_aligned=htf_aligned
                )
                structural_breaks.append(structural_break)
            
            # CHoCH: Break above previous swing high (reversal)
            elif current_close > last_swing_high + (min_break_distance_atr * atr_value):
                # HTF alignment: CHoCH in downtrend aligns if HTF is uptrend
                # Or bypassed if at cycle extreme (structure broken at cycle low/high)
                htf_aligned = _check_choch_htf_alignment("downtrend", computed_htf_trend, cycle_context)
                
                structural_break = StructuralBreak(
                    timeframe=_infer_timeframe(df),
                    break_type="CHoCH",
                    level=last_swing_high,
                    timestamp=current_idx.to_pydatetime(),
                    htf_aligned=htf_aligned
                )
                structural_breaks.append(structural_break)
                
                # Change trend
                current_trend = "uptrend"
    
    return structural_breaks


def _detect_swing_highs(df: pd.DataFrame, lookback: int) -> pd.Series:
    """
    Detect swing highs in price data.
    
    A swing high is a candle whose high is greater than the highs of
    N candles on both sides.
    
    Args:
        df: DataFrame with OHLC data
        lookback: Number of candles to each side
        
    Returns:
        pd.Series: Swing high levels indexed by timestamp
    """
    swing_highs = {}
    
    for i in range(lookback, len(df) - lookback):
        current_high = df['high'].iloc[i]
        
        # Check if this is a swing high
        is_swing_high = True
        
        # Check left side
        for j in range(i - lookback, i):
            if df['high'].iloc[j] >= current_high:
                is_swing_high = False
                break
        
        # Check right side
        if is_swing_high:
            for j in range(i + 1, i + lookback + 1):
                if df['high'].iloc[j] >= current_high:
                    is_swing_high = False
                    break
        
        if is_swing_high:
            swing_highs[df.index[i]] = current_high
    
    return pd.Series(swing_highs)


def _detect_swing_lows(df: pd.DataFrame, lookback: int) -> pd.Series:
    """
    Detect swing lows in price data.
    
    A swing low is a candle whose low is less than the lows of
    N candles on both sides.
    
    Args:
        df: DataFrame with OHLC data
        lookback: Number of candles to each side
        
    Returns:
        pd.Series: Swing low levels indexed by timestamp
    """
    swing_lows = {}
    
    for i in range(lookback, len(df) - lookback):
        current_low = df['low'].iloc[i]
        
        # Check if this is a swing low
        is_swing_low = True
        
        # Check left side
        for j in range(i - lookback, i):
            if df['low'].iloc[j] <= current_low:
                is_swing_low = False
                break
        
        # Check right side
        if is_swing_low:
            for j in range(i + 1, i + lookback + 1):
                if df['low'].iloc[j] <= current_low:
                    is_swing_low = False
                    break
        
        if is_swing_low:
            swing_lows[df.index[i]] = current_low
    
    return pd.Series(swing_lows)


def _determine_initial_trend(swing_highs: pd.Series, swing_lows: pd.Series) -> str:
    """
    Determine initial market trend based on first swing points.
    
    Args:
        swing_highs: Series of swing highs
        swing_lows: Series of swing lows
        
    Returns:
        str: "uptrend", "downtrend", or "ranging"
    """
    if len(swing_highs) < 2 and len(swing_lows) < 2:
        return "ranging"
    
    # Check if making higher highs and higher lows
    if len(swing_highs) >= 2:
        highs_values = swing_highs.values
        if highs_values[-1] > highs_values[-2]:
            return "uptrend"
        elif highs_values[-1] < highs_values[-2]:
            return "downtrend"
    
    if len(swing_lows) >= 2:
        lows_values = swing_lows.values
        if lows_values[-1] > lows_values[-2]:
            return "uptrend"
        elif lows_values[-1] < lows_values[-2]:
            return "downtrend"
    
    return "ranging"


def _calculate_htf_trend(htf_df: pd.DataFrame) -> str:
    """
    Calculate trend direction from higher timeframe data.
    
    Uses EMA crossover and swing structure to determine trend.
    
    Args:
        htf_df: Higher timeframe OHLC DataFrame (must have >= 20 rows)
        
    Returns:
        str: "uptrend", "downtrend", or "ranging"
    """
    if len(htf_df) < 20:
        return "ranging"
    
    recent_closes = htf_df['close'].tail(50) if len(htf_df) >= 50 else htf_df['close']
    
    # Calculate EMAs
    ema_fast = recent_closes.ewm(span=8, adjust=False).mean()
    ema_slow = recent_closes.ewm(span=21, adjust=False).mean()
    
    # Current EMA positions
    fast_current = ema_fast.iloc[-1]
    slow_current = ema_slow.iloc[-1]
    
    # EMA slope (compare current to 5 bars ago)
    if len(ema_fast) > 5:
        fast_slope = fast_current - ema_fast.iloc[-6]
        slow_slope = slow_current - ema_slow.iloc[-6]
    else:
        fast_slope = 0
        slow_slope = 0
    
    # Determine trend
    if fast_current > slow_current and fast_slope > 0:
        return "uptrend"
    elif fast_current < slow_current and fast_slope < 0:
        return "downtrend"
    else:
        return "ranging"


def _check_bos_htf_alignment(ltf_trend: str, htf_trend: Optional[str]) -> bool:
    """
    Check if a BOS (continuation) aligns with HTF trend.
    
    BOS is HTF-aligned when:
    - LTF uptrend BOS + HTF uptrend = aligned (bullish continuation confirmed by HTF)
    - LTF downtrend BOS + HTF downtrend = aligned (bearish continuation confirmed by HTF)
    - If HTF trend is unknown/ranging, give benefit of the doubt (True)
    
    Args:
        ltf_trend: Lower timeframe trend ("uptrend" or "downtrend")
        htf_trend: Higher timeframe trend or None
        
    Returns:
        bool: True if HTF supports the continuation
    """
    if htf_trend is None or htf_trend == "ranging":
        # No HTF context - can't confirm alignment, default to True
        # (BOS is trend-following, so it's at least consistent with LTF)
        return True
    
    # BOS aligns when LTF and HTF trends match
    return ltf_trend == htf_trend


def _check_choch_htf_alignment(
    ltf_trend: str, 
    htf_trend: Optional[str],
    cycle_context: Optional["CycleContext"] = None
) -> bool:
    """
    Check if a CHoCH (reversal) aligns with HTF trend.
    
    CHoCH is HTF-aligned when:
    - LTF uptrend CHoCH (turning bearish) + HTF downtrend = aligned
    - LTF downtrend CHoCH (turning bullish) + HTF uptrend = aligned
    - If HTF is ranging/unknown, CHoCH might be early reversal = False
    
    CYCLE BYPASS: When cycle_context indicates we're at a cycle extreme,
    the HTF alignment requirement is bypassed because:
    - At DCL/WCL zone: Bullish reversal is valid even without HTF confirmation
    - At distribution with LTR: Bearish reversal is valid even without HTF confirmation
    
    Args:
        ltf_trend: Lower timeframe trend BEFORE the CHoCH
        htf_trend: Higher timeframe trend or None
        cycle_context: Optional cycle context for bypass logic
        
    Returns:
        bool: True if HTF supports the reversal direction OR cycle bypass active
    """
    # === CYCLE BYPASS CHECK ===
    # If we have cycle context, check for bypass conditions
    if cycle_context is not None:
        # Import here to avoid circular imports at module level
        from backend.shared.models.smc import CyclePhase, CycleTranslation, CycleConfirmation
        
        # Bullish CHoCH (from downtrend) - bypass at cycle lows
        if ltf_trend == "downtrend":
            # At confirmed DCL/WCL zone - allow bullish reversal
            if (cycle_context.in_dcl_zone or cycle_context.in_wcl_zone):
                return True
            if cycle_context.phase == CyclePhase.ACCUMULATION:
                return True
            if cycle_context.dcl_confirmation == CycleConfirmation.CONFIRMED:
                return True
        
        # Bearish CHoCH (from uptrend) - bypass at distribution with LTR
        if ltf_trend == "uptrend":
            # LTR translation confirmed - bearish bias
            if cycle_context.translation == CycleTranslation.LTR:
                return True
            # Distribution/markdown phase - bearish context
            if cycle_context.phase in [CyclePhase.DISTRIBUTION, CyclePhase.MARKDOWN]:
                return True
    
    # === STANDARD HTF ALIGNMENT CHECK ===
    if htf_trend is None or htf_trend == "ranging":
        # No clear HTF context - CHoCH is counter-trend by nature
        # Without HTF confirmation, treat as unaligned
        return False
    
    # CHoCH aligns when it reverses TOWARD the HTF trend
    # LTF uptrend + CHoCH => turning bearish => aligns if HTF is downtrend
    # LTF downtrend + CHoCH => turning bullish => aligns if HTF is uptrend
    if ltf_trend == "uptrend":
        # CHoCH in uptrend means turning bearish
        return htf_trend == "downtrend"
    else:
        # CHoCH in downtrend means turning bullish
        return htf_trend == "uptrend"


def check_htf_alignment(
    ltf_break: StructuralBreak,
    htf_df: pd.DataFrame
) -> bool:
    """
    Check if a lower timeframe break aligns with higher timeframe trend.
    
    Args:
        ltf_break: Lower timeframe structural break
        htf_df: Higher timeframe OHLC DataFrame
        
    Returns:
        bool: True if aligned with HTF trend
    """
    if len(htf_df) < 20:
        return False  # Not enough data
    
    # Get HTF trend at the time of the break
    htf_candles_before_break = htf_df[htf_df.index <= pd.Timestamp(ltf_break.timestamp)]
    
    if len(htf_candles_before_break) < 10:
        return False
    
    # Simple trend detection: compare recent EMAs
    recent_closes = htf_candles_before_break['close'].tail(20)
    ema_fast = recent_closes.ewm(span=5).mean().iloc[-1]
    ema_slow = recent_closes.ewm(span=20).mean().iloc[-1]
    
    htf_uptrend = ema_fast > ema_slow
    
    # Check alignment
    if ltf_break.break_type == "BOS":
        # BOS should align with trend
        # Determine BOS direction from context (simplified)
        return True  # Would need more context to determine precisely
    else:  # CHoCH
        # CHoCH is counter-trend by nature
        return False


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
    
    time_deltas = df.index.to_series().diff().dropna()
    
    if len(time_deltas) == 0:
        return "unknown"
    
    avg_delta = time_deltas.mean()
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


def get_latest_structural_break(breaks: List[StructuralBreak]) -> Optional[StructuralBreak]:
    """
    Get the most recent structural break.
    
    Args:
        breaks: List of structural breaks
        
    Returns:
        StructuralBreak or None: Latest break, or None if list is empty
    """
    if not breaks:
        return None
    
    return max(breaks, key=lambda b: b.timestamp)


def filter_by_type(breaks: List[StructuralBreak], break_type: str) -> List[StructuralBreak]:
    """
    Filter structural breaks by type.
    
    Args:
        breaks: List of structural breaks
        break_type: "BOS" or "CHoCH"
        
    Returns:
        List[StructuralBreak]: Filtered breaks
    """
    return [b for b in breaks if b.break_type == break_type]
