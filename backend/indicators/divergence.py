"""
Divergence Detection Module

Detects price-indicator divergences for trading signals:
- Regular Bullish Divergence: Price lower low + Indicator higher low (reversal signal)
- Regular Bearish Divergence: Price higher high + Indicator lower high (reversal signal)
- Hidden Bullish Divergence: Price higher low + Indicator lower low (continuation signal)
- Hidden Bearish Divergence: Price lower high + Indicator higher high (continuation signal)

Works with RSI, MACD, and volume indicators.
"""

from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np
from loguru import logger

from backend.indicators.momentum import compute_rsi, compute_macd


class DivergenceResult:
    """Container for divergence detection results"""

    def __init__(
        self,
        divergence_type: str,  # 'regular_bullish', 'regular_bearish', 'hidden_bullish', 'hidden_bearish'
        indicator: str,  # 'rsi', 'macd', 'volume'
        price_pivot_1: int,  # Index of first price pivot
        price_pivot_2: int,  # Index of second price pivot
        indicator_pivot_1: int,  # Index of first indicator pivot
        indicator_pivot_2: int,  # Index of second indicator pivot
        price_value_1: float,
        price_value_2: float,
        indicator_value_1: float,
        indicator_value_2: float,
        strength: float  # 0-100, strength of divergence
    ):
        self.divergence_type = divergence_type
        self.indicator = indicator
        self.price_pivot_1 = price_pivot_1
        self.price_pivot_2 = price_pivot_2
        self.indicator_pivot_1 = indicator_pivot_1
        self.indicator_pivot_2 = indicator_pivot_2
        self.price_value_1 = price_value_1
        self.price_value_2 = price_value_2
        self.indicator_value_1 = indicator_value_1
        self.indicator_value_2 = indicator_value_2
        self.strength = strength

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            'type': self.divergence_type,
            'indicator': self.indicator,
            'price_pivots': [self.price_pivot_1, self.price_pivot_2],
            'indicator_pivots': [self.indicator_pivot_1, self.indicator_pivot_2],
            'price_values': [self.price_value_1, self.price_value_2],
            'indicator_values': [self.indicator_value_1, self.indicator_value_2],
            'strength': self.strength
        }

    def is_bullish(self) -> bool:
        """Check if divergence is bullish"""
        return 'bullish' in self.divergence_type

    def is_bearish(self) -> bool:
        """Check if divergence is bearish"""
        return 'bearish' in self.divergence_type

    def is_reversal(self) -> bool:
        """Check if divergence signals reversal (regular divergence)"""
        return 'regular' in self.divergence_type

    def is_continuation(self) -> bool:
        """Check if divergence signals continuation (hidden divergence)"""
        return 'hidden' in self.divergence_type


def find_swing_highs(series: pd.Series, lookback: int = 5) -> List[int]:
    """
    Find swing highs (local peaks) in a series.

    Args:
        series: Price or indicator series
        lookback: Number of bars to look left/right for peak detection

    Returns:
        List of indices where swing highs occur
    """
    swing_highs = []

    for i in range(lookback, len(series) - lookback):
        is_peak = True
        current_value = series.iloc[i]

        # Check if current value is higher than lookback bars on both sides
        for j in range(1, lookback + 1):
            if (series.iloc[i - j] >= current_value or
                series.iloc[i + j] >= current_value):
                is_peak = False
                break

        if is_peak:
            swing_highs.append(i)

    return swing_highs


def find_swing_lows(series: pd.Series, lookback: int = 5) -> List[int]:
    """
    Find swing lows (local troughs) in a series.

    Args:
        series: Price or indicator series
        lookback: Number of bars to look left/right for trough detection

    Returns:
        List of indices where swing lows occur
    """
    swing_lows = []

    for i in range(lookback, len(series) - lookback):
        is_trough = True
        current_value = series.iloc[i]

        # Check if current value is lower than lookback bars on both sides
        for j in range(1, lookback + 1):
            if (series.iloc[i - j] <= current_value or
                series.iloc[i + j] <= current_value):
                is_trough = False
                break

        if is_trough:
            swing_lows.append(i)

    return swing_lows


def detect_regular_bullish_divergence(
    df: pd.DataFrame,
    indicator_series: pd.Series,
    indicator_name: str,
    lookback: int = 5,
    min_pivot_distance: int = 10,
    max_lookback_bars: int = 100
) -> Optional[DivergenceResult]:
    """
    Detect regular bullish divergence: Price makes lower low, indicator makes higher low.
    This signals a potential reversal from downtrend to uptrend.

    Args:
        df: DataFrame with 'low' column for price
        indicator_series: Indicator series (RSI, MACD, etc.)
        indicator_name: Name of the indicator
        lookback: Lookback period for swing detection
        min_pivot_distance: Minimum bars between pivots
        max_lookback_bars: Maximum bars to look back for divergence

    Returns:
        DivergenceResult if divergence found, None otherwise
    """
    # Find swing lows in both price and indicator
    price_lows_indices = find_swing_lows(df['low'], lookback)
    indicator_lows_indices = find_swing_lows(indicator_series, lookback)

    if len(price_lows_indices) < 2 or len(indicator_lows_indices) < 2:
        return None

    # Check recent pivots (within max_lookback_bars)
    recent_price_lows = [i for i in price_lows_indices if len(df) - i <= max_lookback_bars]
    recent_indicator_lows = [i for i in indicator_lows_indices if len(indicator_series) - i <= max_lookback_bars]

    if len(recent_price_lows) < 2 or len(recent_indicator_lows) < 2:
        return None

    # Get the two most recent pivots
    price_pivot_2 = recent_price_lows[-1]  # Most recent
    price_pivot_1 = recent_price_lows[-2]  # Previous

    # Check if pivots are far enough apart
    if price_pivot_2 - price_pivot_1 < min_pivot_distance:
        return None

    # Find corresponding indicator pivots (within reasonable range)
    indicator_pivot_2 = min(recent_indicator_lows, key=lambda x: abs(x - price_pivot_2))
    indicator_pivot_1 = min(recent_indicator_lows, key=lambda x: abs(x - price_pivot_1))

    # Check if indicator pivots align reasonably with price pivots
    if abs(indicator_pivot_2 - price_pivot_2) > lookback * 2:
        return None
    if abs(indicator_pivot_1 - price_pivot_1) > lookback * 2:
        return None

    # Get values
    price_value_1 = df['low'].iloc[price_pivot_1]
    price_value_2 = df['low'].iloc[price_pivot_2]
    indicator_value_1 = indicator_series.iloc[indicator_pivot_1]
    indicator_value_2 = indicator_series.iloc[indicator_pivot_2]

    # Regular bullish divergence: price lower low + indicator higher low
    if price_value_2 < price_value_1 and indicator_value_2 > indicator_value_1:
        # Calculate strength based on divergence magnitude
        price_change_pct = abs((price_value_2 - price_value_1) / price_value_1) * 100
        indicator_change_pct = abs((indicator_value_2 - indicator_value_1) / max(indicator_value_1, 1)) * 100

        # Strength: higher when both price and indicator diverge significantly
        strength = min(100, (price_change_pct + indicator_change_pct) * 5)

        return DivergenceResult(
            divergence_type='regular_bullish',
            indicator=indicator_name,
            price_pivot_1=price_pivot_1,
            price_pivot_2=price_pivot_2,
            indicator_pivot_1=indicator_pivot_1,
            indicator_pivot_2=indicator_pivot_2,
            price_value_1=price_value_1,
            price_value_2=price_value_2,
            indicator_value_1=indicator_value_1,
            indicator_value_2=indicator_value_2,
            strength=strength
        )

    return None


def detect_regular_bearish_divergence(
    df: pd.DataFrame,
    indicator_series: pd.Series,
    indicator_name: str,
    lookback: int = 5,
    min_pivot_distance: int = 10,
    max_lookback_bars: int = 100
) -> Optional[DivergenceResult]:
    """
    Detect regular bearish divergence: Price makes higher high, indicator makes lower high.
    This signals a potential reversal from uptrend to downtrend.

    Args:
        df: DataFrame with 'high' column for price
        indicator_series: Indicator series (RSI, MACD, etc.)
        indicator_name: Name of the indicator
        lookback: Lookback period for swing detection
        min_pivot_distance: Minimum bars between pivots
        max_lookback_bars: Maximum bars to look back for divergence

    Returns:
        DivergenceResult if divergence found, None otherwise
    """
    # Find swing highs in both price and indicator
    price_highs_indices = find_swing_highs(df['high'], lookback)
    indicator_highs_indices = find_swing_highs(indicator_series, lookback)

    if len(price_highs_indices) < 2 or len(indicator_highs_indices) < 2:
        return None

    # Check recent pivots (within max_lookback_bars)
    recent_price_highs = [i for i in price_highs_indices if len(df) - i <= max_lookback_bars]
    recent_indicator_highs = [i for i in indicator_highs_indices if len(indicator_series) - i <= max_lookback_bars]

    if len(recent_price_highs) < 2 or len(recent_indicator_highs) < 2:
        return None

    # Get the two most recent pivots
    price_pivot_2 = recent_price_highs[-1]  # Most recent
    price_pivot_1 = recent_price_highs[-2]  # Previous

    # Check if pivots are far enough apart
    if price_pivot_2 - price_pivot_1 < min_pivot_distance:
        return None

    # Find corresponding indicator pivots (within reasonable range)
    indicator_pivot_2 = min(recent_indicator_highs, key=lambda x: abs(x - price_pivot_2))
    indicator_pivot_1 = min(recent_indicator_highs, key=lambda x: abs(x - price_pivot_1))

    # Check if indicator pivots align reasonably with price pivots
    if abs(indicator_pivot_2 - price_pivot_2) > lookback * 2:
        return None
    if abs(indicator_pivot_1 - price_pivot_1) > lookback * 2:
        return None

    # Get values
    price_value_1 = df['high'].iloc[price_pivot_1]
    price_value_2 = df['high'].iloc[price_pivot_2]
    indicator_value_1 = indicator_series.iloc[indicator_pivot_1]
    indicator_value_2 = indicator_series.iloc[indicator_pivot_2]

    # Regular bearish divergence: price higher high + indicator lower high
    if price_value_2 > price_value_1 and indicator_value_2 < indicator_value_1:
        # Calculate strength based on divergence magnitude
        price_change_pct = abs((price_value_2 - price_value_1) / price_value_1) * 100
        indicator_change_pct = abs((indicator_value_2 - indicator_value_1) / max(indicator_value_1, 1)) * 100

        # Strength: higher when both price and indicator diverge significantly
        strength = min(100, (price_change_pct + indicator_change_pct) * 5)

        return DivergenceResult(
            divergence_type='regular_bearish',
            indicator=indicator_name,
            price_pivot_1=price_pivot_1,
            price_pivot_2=price_pivot_2,
            indicator_pivot_1=indicator_pivot_1,
            indicator_pivot_2=indicator_pivot_2,
            price_value_1=price_value_1,
            price_value_2=price_value_2,
            indicator_value_1=indicator_value_1,
            indicator_value_2=indicator_value_2,
            strength=strength
        )

    return None


def detect_hidden_bullish_divergence(
    df: pd.DataFrame,
    indicator_series: pd.Series,
    indicator_name: str,
    lookback: int = 5,
    min_pivot_distance: int = 10,
    max_lookback_bars: int = 100
) -> Optional[DivergenceResult]:
    """
    Detect hidden bullish divergence: Price makes higher low, indicator makes lower low.
    This signals trend continuation in an uptrend.

    Args:
        df: DataFrame with 'low' column for price
        indicator_series: Indicator series (RSI, MACD, etc.)
        indicator_name: Name of the indicator
        lookback: Lookback period for swing detection
        min_pivot_distance: Minimum bars between pivots
        max_lookback_bars: Maximum bars to look back for divergence

    Returns:
        DivergenceResult if divergence found, None otherwise
    """
    price_lows_indices = find_swing_lows(df['low'], lookback)
    indicator_lows_indices = find_swing_lows(indicator_series, lookback)

    if len(price_lows_indices) < 2 or len(indicator_lows_indices) < 2:
        return None

    recent_price_lows = [i for i in price_lows_indices if len(df) - i <= max_lookback_bars]
    recent_indicator_lows = [i for i in indicator_lows_indices if len(indicator_series) - i <= max_lookback_bars]

    if len(recent_price_lows) < 2 or len(recent_indicator_lows) < 2:
        return None

    price_pivot_2 = recent_price_lows[-1]
    price_pivot_1 = recent_price_lows[-2]

    if price_pivot_2 - price_pivot_1 < min_pivot_distance:
        return None

    indicator_pivot_2 = min(recent_indicator_lows, key=lambda x: abs(x - price_pivot_2))
    indicator_pivot_1 = min(recent_indicator_lows, key=lambda x: abs(x - price_pivot_1))

    if abs(indicator_pivot_2 - price_pivot_2) > lookback * 2:
        return None
    if abs(indicator_pivot_1 - price_pivot_1) > lookback * 2:
        return None

    price_value_1 = df['low'].iloc[price_pivot_1]
    price_value_2 = df['low'].iloc[price_pivot_2]
    indicator_value_1 = indicator_series.iloc[indicator_pivot_1]
    indicator_value_2 = indicator_series.iloc[indicator_pivot_2]

    # Hidden bullish divergence: price higher low + indicator lower low
    if price_value_2 > price_value_1 and indicator_value_2 < indicator_value_1:
        price_change_pct = abs((price_value_2 - price_value_1) / price_value_1) * 100
        indicator_change_pct = abs((indicator_value_2 - indicator_value_1) / max(indicator_value_1, 1)) * 100
        strength = min(100, (price_change_pct + indicator_change_pct) * 4)

        return DivergenceResult(
            divergence_type='hidden_bullish',
            indicator=indicator_name,
            price_pivot_1=price_pivot_1,
            price_pivot_2=price_pivot_2,
            indicator_pivot_1=indicator_pivot_1,
            indicator_pivot_2=indicator_pivot_2,
            price_value_1=price_value_1,
            price_value_2=price_value_2,
            indicator_value_1=indicator_value_1,
            indicator_value_2=indicator_value_2,
            strength=strength
        )

    return None


def detect_hidden_bearish_divergence(
    df: pd.DataFrame,
    indicator_series: pd.Series,
    indicator_name: str,
    lookback: int = 5,
    min_pivot_distance: int = 10,
    max_lookback_bars: int = 100
) -> Optional[DivergenceResult]:
    """
    Detect hidden bearish divergence: Price makes lower high, indicator makes higher high.
    This signals trend continuation in a downtrend.

    Args:
        df: DataFrame with 'high' column for price
        indicator_series: Indicator series (RSI, MACD, etc.)
        indicator_name: Name of the indicator
        lookback: Lookback period for swing detection
        min_pivot_distance: Minimum bars between pivots
        max_lookback_bars: Maximum bars to look back for divergence

    Returns:
        DivergenceResult if divergence found, None otherwise
    """
    price_highs_indices = find_swing_highs(df['high'], lookback)
    indicator_highs_indices = find_swing_highs(indicator_series, lookback)

    if len(price_highs_indices) < 2 or len(indicator_highs_indices) < 2:
        return None

    recent_price_highs = [i for i in price_highs_indices if len(df) - i <= max_lookback_bars]
    recent_indicator_highs = [i for i in indicator_highs_indices if len(indicator_series) - i <= max_lookback_bars]

    if len(recent_price_highs) < 2 or len(recent_indicator_highs) < 2:
        return None

    price_pivot_2 = recent_price_highs[-1]
    price_pivot_1 = recent_price_highs[-2]

    if price_pivot_2 - price_pivot_1 < min_pivot_distance:
        return None

    indicator_pivot_2 = min(recent_indicator_highs, key=lambda x: abs(x - price_pivot_2))
    indicator_pivot_1 = min(recent_indicator_highs, key=lambda x: abs(x - price_pivot_1))

    if abs(indicator_pivot_2 - price_pivot_2) > lookback * 2:
        return None
    if abs(indicator_pivot_1 - price_pivot_1) > lookback * 2:
        return None

    price_value_1 = df['high'].iloc[price_pivot_1]
    price_value_2 = df['high'].iloc[price_pivot_2]
    indicator_value_1 = indicator_series.iloc[indicator_pivot_1]
    indicator_value_2 = indicator_series.iloc[indicator_pivot_2]

    # Hidden bearish divergence: price lower high + indicator higher high
    if price_value_2 < price_value_1 and indicator_value_2 > indicator_value_1:
        price_change_pct = abs((price_value_2 - price_value_1) / price_value_1) * 100
        indicator_change_pct = abs((indicator_value_2 - indicator_value_1) / max(indicator_value_1, 1)) * 100
        strength = min(100, (price_change_pct + indicator_change_pct) * 4)

        return DivergenceResult(
            divergence_type='hidden_bearish',
            indicator=indicator_name,
            price_pivot_1=price_pivot_1,
            price_pivot_2=price_pivot_2,
            indicator_pivot_1=indicator_pivot_1,
            indicator_pivot_2=indicator_pivot_2,
            price_value_1=price_value_1,
            price_value_2=price_value_2,
            indicator_value_1=indicator_value_1,
            indicator_value_2=indicator_value_2,
            strength=strength
        )

    return None


def detect_rsi_divergence(
    df: pd.DataFrame,
    direction: str,
    lookback: int = 5,
    min_pivot_distance: int = 10,
    max_lookback_bars: int = 100
) -> List[DivergenceResult]:
    """
    Detect all RSI divergences for a given direction.

    Args:
        df: DataFrame with OHLC data
        direction: 'bullish' or 'bearish'
        lookback: Lookback period for swing detection
        min_pivot_distance: Minimum bars between pivots
        max_lookback_bars: Maximum bars to look back

    Returns:
        List of DivergenceResult objects
    """
    if len(df) < 50:
        return []

    try:
        rsi = compute_rsi(df, period=14, validate_input=False)
    except Exception as e:
        logger.warning(f"Failed to compute RSI for divergence: {e}")
        return []

    divergences = []

    if direction == 'bullish':
        # Regular bullish (reversal)
        regular = detect_regular_bullish_divergence(
            df, rsi, 'rsi', lookback, min_pivot_distance, max_lookback_bars
        )
        if regular:
            divergences.append(regular)

        # Hidden bullish (continuation)
        hidden = detect_hidden_bullish_divergence(
            df, rsi, 'rsi', lookback, min_pivot_distance, max_lookback_bars
        )
        if hidden:
            divergences.append(hidden)

    elif direction == 'bearish':
        # Regular bearish (reversal)
        regular = detect_regular_bearish_divergence(
            df, rsi, 'rsi', lookback, min_pivot_distance, max_lookback_bars
        )
        if regular:
            divergences.append(regular)

        # Hidden bearish (continuation)
        hidden = detect_hidden_bearish_divergence(
            df, rsi, 'rsi', lookback, min_pivot_distance, max_lookback_bars
        )
        if hidden:
            divergences.append(hidden)

    return divergences


def detect_macd_divergence(
    df: pd.DataFrame,
    direction: str,
    lookback: int = 5,
    min_pivot_distance: int = 10,
    max_lookback_bars: int = 100
) -> List[DivergenceResult]:
    """
    Detect all MACD histogram divergences for a given direction.

    Args:
        df: DataFrame with OHLC data
        direction: 'bullish' or 'bearish'
        lookback: Lookback period for swing detection
        min_pivot_distance: Minimum bars between pivots
        max_lookback_bars: Maximum bars to look back

    Returns:
        List of DivergenceResult objects
    """
    if len(df) < 50:
        return []

    try:
        macd_line, signal_line, histogram = compute_macd(df)
    except Exception as e:
        logger.warning(f"Failed to compute MACD for divergence: {e}")
        return []

    divergences = []

    if direction == 'bullish':
        # Regular bullish (reversal)
        regular = detect_regular_bullish_divergence(
            df, histogram, 'macd', lookback, min_pivot_distance, max_lookback_bars
        )
        if regular:
            divergences.append(regular)

        # Hidden bullish (continuation)
        hidden = detect_hidden_bullish_divergence(
            df, histogram, 'macd', lookback, min_pivot_distance, max_lookback_bars
        )
        if hidden:
            divergences.append(hidden)

    elif direction == 'bearish':
        # Regular bearish (reversal)
        regular = detect_regular_bearish_divergence(
            df, histogram, 'macd', lookback, min_pivot_distance, max_lookback_bars
        )
        if regular:
            divergences.append(regular)

        # Hidden bearish (continuation)
        hidden = detect_hidden_bearish_divergence(
            df, histogram, 'macd', lookback, min_pivot_distance, max_lookback_bars
        )
        if hidden:
            divergences.append(hidden)

    return divergences


def detect_all_divergences(
    df: pd.DataFrame,
    direction: str,
    lookback: int = 5,
    min_pivot_distance: int = 10,
    max_lookback_bars: int = 100
) -> Dict[str, List[DivergenceResult]]:
    """
    Detect all divergences (RSI and MACD) for a given direction.

    Args:
        df: DataFrame with OHLC data
        direction: 'bullish' or 'bearish'
        lookback: Lookback period for swing detection
        min_pivot_distance: Minimum bars between pivots
        max_lookback_bars: Maximum bars to look back

    Returns:
        Dictionary with 'rsi' and 'macd' keys, each containing list of divergences
    """
    return {
        'rsi': detect_rsi_divergence(df, direction, lookback, min_pivot_distance, max_lookback_bars),
        'macd': detect_macd_divergence(df, direction, lookback, min_pivot_distance, max_lookback_bars)
    }
