"""
Consolidation Detector Module

Detects horizontal trading ranges (consolidations) for trend continuation entries.
Identifies ranges with multiple touches, clean breakouts, and retest confirmations.
"""

import pandas as pd
import numpy as np
from typing import List, Optional, Tuple
from loguru import logger

from backend.shared.models.smc import Consolidation


def detect_consolidations(
    df: pd.DataFrame,
    timeframe: str,
    min_touches: int = 5,
    max_height_pct: float = 0.02,
    min_duration_candles: int = 10,
    atr: Optional[float] = None,
) -> List[Consolidation]:
    """
    Detect consolidation ranges in price data.

    A consolidation is a horizontal channel where price oscillates between
    support and resistance, accumulating liquidity before a breakout.

    Args:
        df: OHLCV DataFrame with datetime index
        timeframe: Timeframe string (e.g., '4h', '15m')
        min_touches: Minimum bounces required (default 5)
        max_height_pct: Max range height as % of price (default 2%)
        min_duration_candles: Minimum consolidation duration in candles
        atr: Average True Range for validation (optional)

    Returns:
        List of detected Consolidation objects
    """
    if df is None or len(df) < min_duration_candles:
        return []

    # FIX: Ensure no duplicate columns (prevents ambiguous truth value errors)
    # If duplicates exist (e.g. two 'high' columns), operations return Series instead of scalars
    if not df.columns.is_unique:
        df = df.loc[:, ~df.columns.duplicated()]

    consolidations = []

    # Rolling window to detect ranges
    window_size = max(min_duration_candles, 15)

    for i in range(window_size, len(df) - 5):  # Leave room for breakout confirmation
        window = df.iloc[i - window_size : i]

        # Calculate range boundaries
        high_level = window["high"].max()
        low_level = window["low"].min()
        height = high_level - low_level
        mid_price = (high_level + low_level) / 2

        # Check height constraint
        if height / mid_price > max_height_pct:
            continue

        # Count touches (bounces off support/resistance)
        touches = _count_touches(window, high_level, low_level, tolerance_pct=0.005)

        if touches < min_touches:
            continue

        # Calculate strength score
        strength = _calculate_strength_score(
            touches=touches,
            duration_candles=len(window),
            height_pct=height / mid_price,
            volume_profile=window["volume"].values if "volume" in window.columns else None,
        )

        # Check for breakout
        breakout_data = _detect_breakout(
            df=df,
            start_idx=i,
            high_level=high_level,
            low_level=low_level,
            atr=atr or (height / 2),  # Fallback ATR estimate
        )

        if breakout_data:
            breakout_confirmed, breakout_direction, retest_level, fvg_at_breakout = breakout_data

            consolidation = Consolidation(
                high=high_level,
                low=low_level,
                timestamp_start=window.index[0],
                timestamp_end=window.index[-1],
                touches=touches,
                strength_score=strength,
                timeframe=timeframe,
                breakout_confirmed=breakout_confirmed,
                breakout_direction=breakout_direction,
                retest_level=retest_level,
                fvg_at_breakout=fvg_at_breakout,
            )

            consolidations.append(consolidation)
            logger.debug(
                f"Detected consolidation on {timeframe}: {touches} touches, strength={strength:.2f}, breakout={breakout_direction}"
            )

    return consolidations


def _count_touches(
    window: pd.DataFrame, high_level: float, low_level: float, tolerance_pct: float = 0.005
) -> int:
    """
    Count number of touches (bounces) within the consolidation range.

    A touch is when price approaches support/resistance within tolerance.
    """
    high_tolerance = high_level * tolerance_pct
    low_tolerance = low_level * tolerance_pct

    touches = 0

    for _, row in window.iterrows():
        # Check resistance touch
        if abs(row["high"] - high_level) <= high_tolerance:
            touches += 1
        # Check support touch
        elif abs(row["low"] - low_level) <= low_tolerance:
            touches += 1

    return touches


def _calculate_strength_score(
    touches: int,
    duration_candles: int,
    height_pct: float,
    volume_profile: Optional[np.ndarray] = None,
) -> float:
    """
    Calculate consolidation strength score (0-1).

    Higher score = better quality consolidation:
    - More touches = stronger
    - Longer duration = stronger
    - Tighter range = stronger
    - Consistent volume = stronger
    """
    # Touch score (5 touches = 0.5, 10+ touches = 1.0)
    touch_score = min(touches / 10.0, 1.0)

    # Duration score (10 candles = 0.5, 20+ candles = 1.0)
    duration_score = min(duration_candles / 20.0, 1.0)

    # Tightness score (2% height = 0.5, 1% = 1.0)
    tightness_score = 1.0 - (height_pct / 0.02)
    tightness_score = max(0.0, min(1.0, tightness_score))

    # Volume consistency score (optional)
    volume_score = 0.5  # Default neutral
    if volume_profile is not None and len(volume_profile) > 0:
        # Lower variance = more consistent = better
        vol_std = np.std(volume_profile)
        vol_mean = np.mean(volume_profile)
        if vol_mean > 0:
            cv = vol_std / vol_mean  # Coefficient of variation
            volume_score = max(0.0, min(1.0, 1.0 - cv))

    # Weighted average
    strength = (
        touch_score * 0.35 + duration_score * 0.25 + tightness_score * 0.25 + volume_score * 0.15
    )

    return strength


def _detect_breakout(
    df: pd.DataFrame,
    start_idx: int,
    high_level: float,
    low_level: float,
    atr: float,
    min_displacement_atr: float = 1.0,
) -> Optional[Tuple[bool, str, Optional[float], bool]]:
    """
    Detect if consolidation has a clean breakout + retest.

    Returns:
        Tuple of (breakout_confirmed, direction, retest_level, fvg_at_breakout)
        or None if no valid breakout
    """
    # Check next 10 candles after consolidation for breakout
    future_window = df.iloc[start_idx : start_idx + 10]

    if len(future_window) < 3:
        return None

    breakout_candle = None
    breakout_direction = None

    for idx, (i, row) in enumerate(future_window.iterrows()):
        # Bullish breakout: close above high with displacement
        if row["close"] > high_level:
            displacement = row["close"] - high_level
            if displacement >= (min_displacement_atr * atr):
                breakout_candle = idx
                breakout_direction = "bullish"
                break

        # Bearish breakout: close below low with displacement
        elif row["close"] < low_level:
            displacement = low_level - row["close"]
            if displacement >= (min_displacement_atr * atr):
                breakout_candle = idx
                breakout_direction = "bearish"
                break

    if breakout_candle is None:
        return None

    # Check for hold confirmation (2 candles beyond range)
    if not _confirm_breakout_hold(
        future_window, breakout_candle + 1, high_level, low_level, breakout_direction
    ):
        return None

    # Check for FVG at breakout
    fvg_at_breakout = _has_fvg_at_breakout(future_window, breakout_candle, breakout_direction)

    # Check for retest
    retest_level = _detect_retest(
        df=df,
        start_idx=start_idx + breakout_candle + 1,
        breakout_level=high_level if breakout_direction == "bullish" else low_level,
        breakout_direction=breakout_direction,
        atr=atr,
    )

    return (True, breakout_direction, retest_level, fvg_at_breakout)


def _confirm_breakout_hold(
    window: pd.DataFrame,
    start_idx: int,
    high_level: float,
    low_level: float,
    direction: str,
    hold_candles: int = 2,
) -> bool:
    """
    Confirm breakout holds (doesn't break back into range) for N candles.
    """
    if start_idx + hold_candles > len(window):
        return False

    hold_window = window.iloc[start_idx : start_idx + hold_candles]

    for _, row in hold_window.iterrows():
        if direction == "bullish":
            # Must stay above low (can wick into range slightly)
            if row["close"] < low_level:
                return False
        else:  # bearish
            # Must stay below high
            if row["close"] > high_level:
                return False

    return True


def _has_fvg_at_breakout(window: pd.DataFrame, breakout_idx: int, direction: str) -> bool:
    """
    Check if FVG formed at breakout candle (institutional confirmation).
    """
    if breakout_idx < 1 or breakout_idx >= len(window) - 1:
        return False

    prev_candle = window.iloc[breakout_idx - 1]
    breakout_candle = window.iloc[breakout_idx]
    next_candle = window.iloc[breakout_idx + 1]

    if direction == "bullish":
        # Bullish FVG: prev_candle high < next_candle low
        if prev_candle["high"] < next_candle["low"]:
            return True
    else:  # bearish
        # Bearish FVG: prev_candle low > next_candle high
        if prev_candle["low"] > next_candle["high"]:
            return True

    return False


def _detect_retest(
    df: pd.DataFrame,
    start_idx: int,
    breakout_level: float,
    breakout_direction: str,
    atr: float,
    retest_tolerance_atr: float = 0.5,
    lookback_candles: int = 10,
) -> Optional[float]:
    """
    Detect if price retests the breakout level.

    Returns retest entry level if found, None otherwise.
    """
    retest_window = df.iloc[start_idx : start_idx + lookback_candles]

    if len(retest_window) < 2:
        return None

    tolerance = retest_tolerance_atr * atr

    for _, row in retest_window.iterrows():
        if breakout_direction == "bullish":
            # Bullish retest: price comes back down to breakout level
            if abs(row["low"] - breakout_level) <= tolerance:
                # Ensure doesn't break back below (failed breakout)
                if row["close"] >= breakout_level - tolerance:
                    return breakout_level  # Retest confirmed
        else:  # bearish
            # Bearish retest: price comes back up to breakout level
            if abs(row["high"] - breakout_level) <= tolerance:
                # Ensure doesn't break back above
                if row["close"] <= breakout_level + tolerance:
                    return breakout_level  # Retest confirmed

    return None
