"""
Higher Timeframe (HTF) Alignment Module

Quantified trend strength analysis across multiple timeframes.
Replaces binary alignment checks with scored alignment based on:
- Higher highs/lows validation
- ADX trend strength
- Swing structure consistency
- Timeframe cascade alignment

This addresses the professional review feedback:
"HTF alignment is mentioned but seems more binary (yes/no) than quantified.
I'd want to see trend strength measured (ADX, slope, swing consistency)."
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
import numpy as np
from loguru import logger


@dataclass
class TrendStrength:
    """
    Quantified trend strength measurement.
    
    Attributes:
        direction: 'bullish', 'bearish', or 'ranging'
        strength_score: 0-100 score (0=no trend, 100=very strong trend)
        adx_value: ADX indicator value
        swing_consistency: % of swings following trend (0-100)
        higher_highs_count: Number of higher highs (bullish)
        lower_lows_count: Number of lower lows (bearish)
        slope: Linear regression slope of closing prices
        rationale: Explanation of trend assessment
    """
    direction: str
    strength_score: float
    adx_value: float
    swing_consistency: float
    higher_highs_count: int
    lower_lows_count: int
    slope: float
    rationale: str


@dataclass
class HTFAlignment:
    """
    Multi-timeframe alignment analysis.
    
    Attributes:
        aligned: Whether LTF signal aligns with HTF trend
        alignment_score: 0-100 score quantifying alignment strength
        htf_trend: Higher timeframe trend analysis
        ltf_trend: Lower timeframe trend analysis
        timeframe_cascade: List of aligned timeframes
        rationale: Detailed explanation
    """
    aligned: bool
    alignment_score: float
    htf_trend: TrendStrength
    ltf_trend: TrendStrength
    timeframe_cascade: List[str]
    rationale: str


def calculate_trend_strength(
    df: pd.DataFrame,
    timeframe: str,
    swing_lookback: int = 5,
    adx_period: int = 14
) -> TrendStrength:
    """
    Calculate quantified trend strength for a single timeframe.
    
    Combines multiple metrics:
    1. ADX: Trend strength indicator (0-100)
    2. Swing analysis: Higher highs/lows validation
    3. Linear regression slope: Price momentum
    
    Args:
        df: DataFrame with OHLC data
        timeframe: Timeframe label (e.g., '4h', '1h')
        swing_lookback: Periods for swing detection
        adx_period: ADX calculation period
        
    Returns:
        TrendStrength with quantified measurements
    """
    if len(df) < adx_period + swing_lookback * 2:
        # Insufficient data - return neutral
        return TrendStrength(
            direction='ranging',
            strength_score=0.0,
            adx_value=0.0,
            swing_consistency=0.0,
            higher_highs_count=0,
            lower_lows_count=0,
            slope=0.0,
            rationale=f"Insufficient data for trend analysis ({len(df)} bars)"
        )
    
    # --- Calculate ADX ---
    adx_value = _calculate_adx(df, adx_period)
    
    # --- Analyze Swing Structure ---
    swing_analysis = _analyze_swing_structure(df, swing_lookback)
    higher_highs = swing_analysis['higher_highs']
    lower_lows = swing_analysis['lower_lows']
    swing_consistency = swing_analysis['consistency']
    
    # --- Calculate Price Slope ---
    slope = _calculate_slope(df['close'])
    
    # --- Determine Trend Direction ---
    if higher_highs > lower_lows and slope > 0:
        direction = 'bullish'
    elif lower_lows > higher_highs and slope < 0:
        direction = 'bearish'
    else:
        direction = 'ranging'
    
    # --- Calculate Strength Score (0-100) ---
    # Component weights:
    # - ADX: 40% (primary trend strength)
    # - Swing consistency: 35% (structure validation)
    # - Slope magnitude: 25% (momentum)
    
    # ADX contribution (ADX > 25 = strong trend)
    adx_score = min(adx_value / 25.0 * 100, 100) * 0.40
    
    # Swing consistency contribution
    swing_score = swing_consistency * 0.35
    
    # Slope contribution (normalize by ATR)
    try:
        from backend.indicators.volatility import compute_atr
        atr = compute_atr(df, period=14).iloc[-1]
        if atr > 0:
            slope_normalized = abs(slope) / atr
            slope_score = min(slope_normalized * 20, 100) * 0.25
        else:
            slope_score = 0.0
    except Exception:
        slope_score = 0.0
    
    strength_score = adx_score + swing_score + slope_score
    strength_score = min(max(strength_score, 0.0), 100.0)  # Clamp 0-100
    
    # --- Generate Rationale ---
    rationale_parts = []
    rationale_parts.append(f"ADX: {adx_value:.1f} ({'strong' if adx_value > 25 else 'weak'} trend)")
    
    if direction == 'bullish':
        rationale_parts.append(f"{higher_highs} higher highs, {lower_lows} lower lows")
    elif direction == 'bearish':
        rationale_parts.append(f"{lower_lows} lower lows, {higher_highs} higher highs")
    else:
        rationale_parts.append("Mixed swing structure")
    
    rationale_parts.append(f"Swing consistency: {swing_consistency:.0f}%")
    rationale_parts.append(f"Slope: {slope:.4f}")
    
    rationale = " | ".join(rationale_parts)
    
    logger.debug(
        f"Trend strength {timeframe}: {direction.upper()} "
        f"({strength_score:.1f}/100) - {rationale}"
    )
    
    return TrendStrength(
        direction=direction,
        strength_score=strength_score,
        adx_value=adx_value,
        swing_consistency=swing_consistency,
        higher_highs_count=higher_highs,
        lower_lows_count=lower_lows,
        slope=slope,
        rationale=rationale
    )


def check_htf_alignment(
    htf_data: pd.DataFrame,
    ltf_data: pd.DataFrame,
    ltf_direction: str,
    htf_timeframe: str = '4h',
    ltf_timeframe: str = '15m',
    min_alignment_score: float = 60.0
) -> HTFAlignment:
    """
    Check if lower timeframe signal aligns with higher timeframe trend.
    
    Provides quantified alignment scoring instead of binary yes/no.
    
    Args:
        htf_data: Higher timeframe OHLC data
        ltf_data: Lower timeframe OHLC data
        ltf_direction: Direction of LTF signal ('bullish' or 'bearish')
        htf_timeframe: HTF label
        ltf_timeframe: LTF label
        min_alignment_score: Minimum score to consider aligned
        
    Returns:
        HTFAlignment with quantified alignment analysis
    """
    # Calculate trend strength for both timeframes
    htf_trend = calculate_trend_strength(htf_data, htf_timeframe)
    ltf_trend = calculate_trend_strength(ltf_data, ltf_timeframe)
    
    # Normalize LTF direction
    ltf_direction_normalized = ltf_direction.lower()
    if ltf_direction_normalized in ['long', 'buy']:
        ltf_direction_normalized = 'bullish'
    elif ltf_direction_normalized in ['short', 'sell']:
        ltf_direction_normalized = 'bearish'
    
    # --- Calculate Alignment Score ---
    
    # 1. Direction alignment (50% weight)
    if htf_trend.direction == ltf_direction_normalized:
        direction_score = 100.0
    elif htf_trend.direction == 'ranging':
        # Neutral HTF doesn't confirm or deny
        direction_score = 50.0
    else:
        # Counter-trend
        direction_score = 0.0
    
    # 2. HTF trend strength (30% weight)
    # Stronger HTF trend = more reliable alignment
    strength_score = htf_trend.strength_score
    
    # 3. LTF-HTF strength consistency (20% weight)
    # Both strong = high confidence
    # Both weak = low confidence
    if htf_trend.strength_score > 60 and ltf_trend.strength_score > 60:
        consistency_score = 100.0
    elif htf_trend.strength_score > 60:
        consistency_score = 75.0
    elif htf_trend.strength_score < 40 and ltf_trend.strength_score < 40:
        consistency_score = 25.0
    else:
        consistency_score = 50.0
    
    # Weighted alignment score
    alignment_score = (
        direction_score * 0.50 +
        strength_score * 0.30 +
        consistency_score * 0.20
    )
    
    # Determine if aligned
    aligned = (
        alignment_score >= min_alignment_score and
        htf_trend.direction == ltf_direction_normalized
    )
    
    # Build timeframe cascade (aligned timeframes)
    timeframe_cascade = []
    if aligned:
        timeframe_cascade = [htf_timeframe, ltf_timeframe]
    
    # --- Generate Rationale ---
    rationale_parts = []
    rationale_parts.append(
        f"HTF ({htf_timeframe}): {htf_trend.direction.upper()} "
        f"strength {htf_trend.strength_score:.1f}/100"
    )
    rationale_parts.append(
        f"LTF ({ltf_timeframe}): {ltf_direction_normalized.upper()} signal"
    )
    
    if aligned:
        rationale_parts.append(
            f"✓ ALIGNED (score: {alignment_score:.1f}/100) - "
            f"HTF trend supports LTF direction"
        )
    else:
        if htf_trend.direction != ltf_direction_normalized:
            rationale_parts.append(
                f"✗ COUNTER-TREND (score: {alignment_score:.1f}/100) - "
                f"HTF {htf_trend.direction} vs LTF {ltf_direction_normalized}"
            )
        else:
            rationale_parts.append(
                f"⚠ WEAK ALIGNMENT (score: {alignment_score:.1f}/100) - "
                f"Trend strength insufficient"
            )
    
    rationale = "\n".join(rationale_parts)
    
    logger.info(f"HTF Alignment: {aligned} ({alignment_score:.1f}/100)")
    logger.debug(rationale)
    
    return HTFAlignment(
        aligned=aligned,
        alignment_score=alignment_score,
        htf_trend=htf_trend,
        ltf_trend=ltf_trend,
        timeframe_cascade=timeframe_cascade,
        rationale=rationale
    )


def check_multi_timeframe_alignment(
    data_by_timeframe: Dict[str, pd.DataFrame],
    signal_direction: str,
    timeframe_hierarchy: List[str]
) -> HTFAlignment:
    """
    Check alignment across multiple timeframes (cascade).
    
    Example hierarchy: ['1d', '4h', '1h', '15m']
    Checks if all higher timeframes align with signal direction.
    
    Args:
        data_by_timeframe: Dict mapping timeframe -> OHLC data
        signal_direction: Direction to check ('bullish' or 'bearish')
        timeframe_hierarchy: Timeframes ordered highest to lowest
        
    Returns:
        HTFAlignment with multi-timeframe analysis
    """
    if not timeframe_hierarchy or len(timeframe_hierarchy) < 2:
        raise ValueError("Need at least 2 timeframes for alignment check")
    
    # Calculate trend strength for all timeframes
    trends = {}
    for tf in timeframe_hierarchy:
        if tf not in data_by_timeframe:
            logger.warning(f"Missing data for timeframe {tf}")
            continue
        trends[tf] = calculate_trend_strength(data_by_timeframe[tf], tf)
    
    if not trends:
        raise ValueError("No valid trend data available")
    
    # Normalize signal direction
    signal_dir = signal_direction.lower()
    if signal_dir in ['long', 'buy']:
        signal_dir = 'bullish'
    elif signal_dir in ['short', 'sell']:
        signal_dir = 'bearish'
    
    # Check alignment for each timeframe
    aligned_tfs = []
    alignment_scores = []
    
    for tf in timeframe_hierarchy:
        if tf not in trends:
            continue
        
        trend = trends[tf]
        
        # Calculate alignment score for this TF
        if trend.direction == signal_dir:
            tf_score = trend.strength_score
            aligned_tfs.append(tf)
        elif trend.direction == 'ranging':
            tf_score = 50.0
        else:
            tf_score = 0.0
        
        alignment_scores.append(tf_score)
    
    # Overall alignment score (weighted average, higher TFs weighted more)
    if alignment_scores:
        # Weight decay: highest TF gets 1.0, lowest gets 0.5
        weights = np.linspace(1.0, 0.5, len(alignment_scores))
        overall_score = np.average(alignment_scores, weights=weights)
    else:
        overall_score = 0.0
    
    # Determine if aligned (majority of TFs align)
    aligned = len(aligned_tfs) >= len(timeframe_hierarchy) / 2
    
    # Get primary HTF and LTF
    htf_tf = timeframe_hierarchy[0]
    ltf_tf = timeframe_hierarchy[-1]
    htf_trend = trends.get(htf_tf)
    ltf_trend = trends.get(ltf_tf)
    
    # Build rationale
    rationale_lines = []
    rationale_lines.append(f"Multi-TF Alignment Check: {signal_dir.upper()}")
    rationale_lines.append(f"Aligned Timeframes: {aligned_tfs} ({len(aligned_tfs)}/{len(timeframe_hierarchy)})")
    rationale_lines.append("")
    
    for tf in timeframe_hierarchy:
        if tf in trends:
            trend = trends[tf]
            status = "✓" if tf in aligned_tfs else "✗"
            rationale_lines.append(
                f"{status} {tf}: {trend.direction.upper()} "
                f"({trend.strength_score:.0f}/100, ADX: {trend.adx_value:.1f})"
            )
    
    rationale_lines.append("")
    rationale_lines.append(f"Overall Alignment Score: {overall_score:.1f}/100")
    
    rationale = "\n".join(rationale_lines)
    
    logger.info(f"Multi-TF Alignment: {aligned} ({overall_score:.1f}/100) - {aligned_tfs}")
    
    return HTFAlignment(
        aligned=aligned,
        alignment_score=overall_score,
        htf_trend=htf_trend,
        ltf_trend=ltf_trend,
        timeframe_cascade=aligned_tfs,
        rationale=rationale
    )


# --- Helper Functions ---

def _calculate_adx(df: pd.DataFrame, period: int = 14) -> float:
    """
    Calculate Average Directional Index (ADX).
    
    ADX measures trend strength regardless of direction.
    Values: 0-100
    - 0-25: Weak or no trend
    - 25-50: Strong trend
    - 50-75: Very strong trend
    - 75-100: Extremely strong trend
    """
    if len(df) < period + 1:
        return 0.0
    
    try:
        high = df['high']
        low = df['low']
        close = df['close']
        
        # Calculate True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Calculate Directional Movement
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        plus_dm = pd.Series(plus_dm, index=df.index)
        minus_dm = pd.Series(minus_dm, index=df.index)
        
        # Smooth with Wilder's smoothing (exponential moving average)
        atr = tr.ewm(span=period, adjust=False).mean()
        plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)
        
        # Calculate DX and ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.ewm(span=period, adjust=False).mean()
        
        # Return most recent ADX value
        return float(adx.iloc[-1]) if pd.notna(adx.iloc[-1]) else 0.0
    
    except Exception as e:
        logger.error(f"Error calculating ADX: {e}")
        return 0.0


def _analyze_swing_structure(df: pd.DataFrame, lookback: int = 5) -> Dict:
    """
    Analyze swing structure to count higher highs/lows.
    
    Returns dict with:
    - higher_highs: Count of higher highs
    - lower_lows: Count of lower lows
    - consistency: Percentage of swings following dominant trend
    """
    if len(df) < lookback * 2 + 10:
        return {
            'higher_highs': 0,
            'lower_lows': 0,
            'consistency': 0.0
        }
    
    # Detect swing highs
    swing_highs = []
    for i in range(lookback, len(df) - lookback):
        window = df['high'].iloc[i - lookback:i + lookback + 1]
        if df['high'].iloc[i] == window.max():
            swing_highs.append((i, df['high'].iloc[i]))
    
    # Detect swing lows
    swing_lows = []
    for i in range(lookback, len(df) - lookback):
        window = df['low'].iloc[i - lookback:i + lookback + 1]
        if df['low'].iloc[i] == window.min():
            swing_lows.append((i, df['low'].iloc[i]))
    
    # Count higher highs
    higher_highs = 0
    for i in range(1, len(swing_highs)):
        if swing_highs[i][1] > swing_highs[i-1][1]:
            higher_highs += 1
    
    # Count lower lows
    lower_lows = 0
    for i in range(1, len(swing_lows)):
        if swing_lows[i][1] < swing_lows[i-1][1]:
            lower_lows += 1
    
    # Calculate consistency
    total_swings = higher_highs + lower_lows
    if total_swings > 0:
        dominant_count = max(higher_highs, lower_lows)
        consistency = (dominant_count / total_swings) * 100
    else:
        consistency = 0.0
    
    return {
        'higher_highs': higher_highs,
        'lower_lows': lower_lows,
        'consistency': consistency
    }


def _calculate_slope(series: pd.Series) -> float:
    """
    Calculate linear regression slope of price series.
    
    Positive slope = uptrend
    Negative slope = downtrend
    """
    if len(series) < 2:
        return 0.0
    
    try:
        x = np.arange(len(series))
        y = series.values
        
        # Remove NaN values
        mask = ~np.isnan(y)
        x = x[mask]
        y = y[mask]
        
        if len(x) < 2:
            return 0.0
        
        # Linear regression
        slope, _ = np.polyfit(x, y, 1)
        
        return float(slope)
    
    except Exception as e:
        logger.error(f"Error calculating slope: {e}")
        return 0.0
