"""
Cycle Detection Module - Camel Finance Methodology

Implements cycle timing detection for crypto markets based on Camel Finance theory:
- Daily Cycle Low (DCL): ~18-28 trading days for crypto
- Weekly Cycle Low (WCL): ~35-50 trading days (nests 2-3 DCLs)
- Cycle Translation: LTR (bearish) / MTR (neutral) / RTR (bullish)

Cycle theory helps identify:
- LONG entries: At confirmed DCL/WCL zones (accumulation phase)
- SHORT entries: After LTR translation confirmed (distribution/markdown phase)

This module is backwards compatible - all functions accept Optional cycle params.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Literal
import pandas as pd
import numpy as np
import logging

from backend.shared.models.smc import (
    CycleContext, 
    CyclePhase, 
    CycleTranslation, 
    CycleConfirmation,
    StructuralBreak
)

logger = logging.getLogger(__name__)


# --- Cycle Timing Configuration ---

@dataclass(frozen=True)
class CycleConfig:
    """
    Cycle timing configuration for crypto markets.
    
    Default values based on Camel Finance research for BTC/crypto:
    - DCL appears every 18-28 trading days
    - WCL appears every 35-50 trading days (contains 2-3 DCLs)
    - YCL appears every 200-250 trading days
    
    Note: These are trading days, not calendar days.
    Crypto trades 24/7, so we use calendar days as approximation.
    """
    # Daily Cycle Low timing windows
    dcl_min_days: int = 18
    dcl_max_days: int = 28
    dcl_early_zone: int = 15  # Start looking for DCL after this many days
    
    # Weekly Cycle Low timing windows  
    wcl_min_days: int = 35
    wcl_max_days: int = 50
    wcl_early_zone: int = 30  # Start looking for WCL after this many days
    
    # Yearly Cycle Low (for reference)
    ycl_min_days: int = 200
    ycl_max_days: int = 250
    
    # Translation thresholds (as % of cycle)
    ltr_threshold: float = 0.40  # Top before 40% = left-translated
    rtr_threshold: float = 0.60  # Top after 60% = right-translated
    
    # Confirmation requirements
    min_swing_lookback: int = 5  # Candles each side for swing detection
    confirmation_bars: int = 2  # Bars after low/high to confirm
    
    # ATR multiplier for cycle low/high detection
    min_displacement_atr: float = 1.0  # Minimum move from low/high to confirm


# Default config for crypto
CRYPTO_CYCLE_CONFIG = CycleConfig()


def detect_cycle_context(
    df: pd.DataFrame,
    config: Optional[CycleConfig] = None,
    structural_breaks: Optional[List[StructuralBreak]] = None,
    current_price: Optional[float] = None
) -> CycleContext:
    """
    Detect complete cycle context from price data.
    
    Combines DCL/WCL detection with translation analysis to produce
    a comprehensive cycle context for trade decision making.
    
    Args:
        df: DataFrame with OHLC data and DatetimeIndex (daily preferred)
        config: Cycle timing configuration (uses crypto defaults if None)
        structural_breaks: Optional structural breaks for CHoCH detection
        current_price: Current market price (uses df close if None)
        
    Returns:
        CycleContext with phase, translation, timing info, and trade bias
    """
    if config is None:
        config = CRYPTO_CYCLE_CONFIG
    
    if len(df) < config.wcl_max_days:
        logger.debug("Insufficient data for cycle detection (need %d days, have %d)",
                    config.wcl_max_days, len(df))
        return CycleContext()  # Return empty context
    
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame must have DatetimeIndex")
    
    required_cols = ['high', 'low', 'close']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame missing required columns: {missing}")
    
    if current_price is None:
        current_price = float(df['close'].iloc[-1])
    
    # Detect cycle lows
    dcl_info = _detect_dcl(df, config)
    wcl_info = _detect_wcl(df, config, dcl_info)
    
    # Detect cycle high and translation
    cycle_high_info = _detect_cycle_high(df, dcl_info, config)
    translation = _calculate_translation(dcl_info, cycle_high_info, config)
    
    # Determine phase
    phase = _determine_phase(df, dcl_info, cycle_high_info, current_price, config)
    
    # Calculate timing zone flags
    in_dcl_zone = _in_timing_zone(dcl_info, config.dcl_early_zone, config.dcl_max_days)
    in_wcl_zone = _in_timing_zone(wcl_info, config.wcl_early_zone, config.wcl_max_days)
    
    # Calculate midpoint
    midpoint = None
    if dcl_info.get('price') and cycle_high_info.get('price'):
        midpoint = (dcl_info['price'] + cycle_high_info['price']) / 2
    
    # Determine trade bias
    trade_bias, confidence = _calculate_trade_bias(
        phase=phase,
        translation=translation,
        in_dcl_zone=in_dcl_zone,
        in_wcl_zone=in_wcl_zone,
        dcl_confirmation=dcl_info.get('confirmation', CycleConfirmation.UNCONFIRMED),
        structural_breaks=structural_breaks
    )
    
    return CycleContext(
        phase=phase,
        translation=translation,
        dcl_days_since=dcl_info.get('days_since'),
        dcl_confirmation=dcl_info.get('confirmation', CycleConfirmation.UNCONFIRMED),
        dcl_price=dcl_info.get('price'),
        dcl_timestamp=dcl_info.get('timestamp'),
        wcl_days_since=wcl_info.get('days_since'),
        wcl_confirmation=wcl_info.get('confirmation', CycleConfirmation.UNCONFIRMED),
        wcl_price=wcl_info.get('price'),
        wcl_timestamp=wcl_info.get('timestamp'),
        cycle_high_price=cycle_high_info.get('price'),
        cycle_high_timestamp=cycle_high_info.get('timestamp'),
        cycle_midpoint_price=midpoint,
        in_dcl_zone=in_dcl_zone,
        in_wcl_zone=in_wcl_zone,
        trade_bias=trade_bias,
        confidence=confidence
    )


def _detect_dcl(df: pd.DataFrame, config: CycleConfig) -> dict:
    """
    Detect Daily Cycle Low from price data.
    
    A DCL is confirmed when:
    1. Price makes a swing low (lower than N bars on each side)
    2. Sufficient time has passed since last DCL (dcl_early_zone)
    3. Price moves up from the low by at least min_displacement_atr
    
    Args:
        df: OHLC DataFrame with DatetimeIndex
        config: Cycle configuration
        
    Returns:
        Dict with price, timestamp, days_since, confirmation
    """
    lookback = config.min_swing_lookback
    
    if len(df) < lookback * 2 + config.confirmation_bars:
        return {'confirmation': CycleConfirmation.UNCONFIRMED}
    
    # Find swing lows in recent data (look back dcl_max_days * 2 for context)
    analysis_window = min(len(df), config.dcl_max_days * 2)
    recent_df = df.tail(analysis_window)
    
    swing_lows = []
    
    for i in range(lookback, len(recent_df) - lookback):
        current_low = recent_df['low'].iloc[i]
        
        # Check if this is a swing low
        is_swing = True
        
        # Check left side
        for j in range(i - lookback, i):
            if recent_df['low'].iloc[j] <= current_low:
                is_swing = False
                break
        
        # Check right side
        if is_swing:
            for j in range(i + 1, i + lookback + 1):
                if recent_df['low'].iloc[j] <= current_low:
                    is_swing = False
                    break
        
        if is_swing:
            swing_lows.append({
                'idx': i,
                'price': current_low,
                'timestamp': recent_df.index[i]
            })
    
    if not swing_lows:
        return {'confirmation': CycleConfirmation.UNCONFIRMED}
    
    # Find the most recent swing low that qualifies as a DCL
    # DCL should be the lowest point in the dcl timing window
    last_swing = swing_lows[-1]
    
    # Calculate ATR for displacement check
    atr = _calculate_atr(df, period=14)
    
    # Check if price has moved up from swing low (confirmation)
    current_price = df['close'].iloc[-1]
    displacement = current_price - last_swing['price']
    
    # Determine confirmation status
    if atr > 0 and displacement >= config.min_displacement_atr * atr:
        confirmation = CycleConfirmation.CONFIRMED
    elif displacement > 0:
        confirmation = CycleConfirmation.UNCONFIRMED
    else:
        # Price went below the swing low - cancelled
        confirmation = CycleConfirmation.CANCELLED
    
    # Calculate days since
    days_since = (df.index[-1] - last_swing['timestamp']).days
    
    return {
        'price': last_swing['price'],
        'timestamp': last_swing['timestamp'].to_pydatetime() if hasattr(last_swing['timestamp'], 'to_pydatetime') else last_swing['timestamp'],
        'days_since': days_since,
        'confirmation': confirmation
    }


def _detect_wcl(df: pd.DataFrame, config: CycleConfig, dcl_info: dict) -> dict:
    """
    Detect Weekly Cycle Low from price data.
    
    A WCL is a deeper swing low that typically nests 2-3 DCLs.
    WCL timing: 35-50 days for crypto.
    
    Args:
        df: OHLC DataFrame
        config: Cycle configuration
        dcl_info: DCL detection results
        
    Returns:
        Dict with price, timestamp, days_since, confirmation
    """
    lookback = config.min_swing_lookback
    
    if len(df) < config.wcl_max_days:
        return {'confirmation': CycleConfirmation.UNCONFIRMED}
    
    # Look back further for WCL
    analysis_window = min(len(df), config.wcl_max_days * 2)
    recent_df = df.tail(analysis_window)
    
    # Find swing lows with larger lookback (more significant lows)
    wcl_lookback = lookback * 2  # Double lookback for weekly significance
    swing_lows = []
    
    for i in range(wcl_lookback, len(recent_df) - wcl_lookback):
        current_low = recent_df['low'].iloc[i]
        
        is_swing = True
        
        for j in range(i - wcl_lookback, i):
            if recent_df['low'].iloc[j] <= current_low:
                is_swing = False
                break
        
        if is_swing:
            for j in range(i + 1, i + wcl_lookback + 1):
                if recent_df['low'].iloc[j] <= current_low:
                    is_swing = False
                    break
        
        if is_swing:
            swing_lows.append({
                'idx': i,
                'price': current_low,
                'timestamp': recent_df.index[i]
            })
    
    if not swing_lows:
        return {'confirmation': CycleConfirmation.UNCONFIRMED}
    
    # Get the most significant (lowest) swing low in WCL window
    wcl_candidate = min(swing_lows, key=lambda x: x['price'])
    
    # Calculate ATR for confirmation
    atr = _calculate_atr(df, period=14)
    current_price = df['close'].iloc[-1]
    displacement = current_price - wcl_candidate['price']
    
    if atr > 0 and displacement >= config.min_displacement_atr * atr * 1.5:  # Higher threshold for WCL
        confirmation = CycleConfirmation.CONFIRMED
    elif displacement > 0:
        confirmation = CycleConfirmation.UNCONFIRMED
    else:
        confirmation = CycleConfirmation.CANCELLED
    
    days_since = (df.index[-1] - wcl_candidate['timestamp']).days
    
    return {
        'price': wcl_candidate['price'],
        'timestamp': wcl_candidate['timestamp'].to_pydatetime() if hasattr(wcl_candidate['timestamp'], 'to_pydatetime') else wcl_candidate['timestamp'],
        'days_since': days_since,
        'confirmation': confirmation
    }


def _detect_cycle_high(df: pd.DataFrame, dcl_info: dict, config: CycleConfig) -> dict:
    """
    Detect cycle high since last DCL.
    
    The cycle high is the highest point between the last DCL and now.
    Used for translation calculation (when did cycle top?).
    
    Args:
        df: OHLC DataFrame
        dcl_info: DCL detection results
        config: Cycle configuration
        
    Returns:
        Dict with price, timestamp, days_since_dcl
    """
    dcl_ts = dcl_info.get('timestamp')
    
    if dcl_ts is None:
        # No DCL - find highest point in recent window
        window = min(len(df), config.dcl_max_days)
        recent_df = df.tail(window)
        high_idx = recent_df['high'].idxmax()
        return {
            'price': recent_df.loc[high_idx, 'high'],
            'timestamp': high_idx.to_pydatetime() if hasattr(high_idx, 'to_pydatetime') else high_idx,
            'days_since_dcl': None
        }
    
    # Find highest point since DCL
    dcl_ts_pd = pd.Timestamp(dcl_ts)
    post_dcl = df[df.index >= dcl_ts_pd]
    
    if len(post_dcl) < 2:
        return {'price': None, 'timestamp': None, 'days_since_dcl': None}
    
    high_idx = post_dcl['high'].idxmax()
    days_since_dcl = (high_idx - dcl_ts_pd).days
    
    return {
        'price': post_dcl.loc[high_idx, 'high'],
        'timestamp': high_idx.to_pydatetime() if hasattr(high_idx, 'to_pydatetime') else high_idx,
        'days_since_dcl': days_since_dcl
    }


def _calculate_translation(dcl_info: dict, cycle_high_info: dict, config: CycleConfig) -> CycleTranslation:
    """
    Calculate cycle translation based on when cycle topped.
    
    Per Camel Finance:
    - LTR (Left-Translated): Cycle topped before 40% of timing window = bearish
    - MTR (Mid-Translated): Topped between 40-60% = neutral
    - RTR (Right-Translated): Topped after 60% = bullish
    
    Args:
        dcl_info: DCL detection results
        cycle_high_info: Cycle high detection results
        config: Cycle configuration
        
    Returns:
        CycleTranslation enum
    """
    dcl_days = dcl_info.get('days_since')
    high_days_since_dcl = cycle_high_info.get('days_since_dcl')
    
    if dcl_days is None or high_days_since_dcl is None:
        return CycleTranslation.UNKNOWN
    
    if dcl_days == 0:
        return CycleTranslation.UNKNOWN  # Just started new cycle
    
    # Calculate where in the cycle the high occurred
    # Use midpoint of DCL timing window as expected cycle length
    expected_cycle_length = (config.dcl_min_days + config.dcl_max_days) / 2
    
    # Position of high relative to expected cycle length
    high_position_pct = high_days_since_dcl / expected_cycle_length
    
    if high_position_pct < config.ltr_threshold:
        return CycleTranslation.LTR  # 🟥 Bearish - topped early
    elif high_position_pct > config.rtr_threshold:
        return CycleTranslation.RTR  # 🟩 Bullish - topped late
    else:
        return CycleTranslation.MTR  # 🟧 Neutral


def _determine_phase(
    df: pd.DataFrame,
    dcl_info: dict,
    cycle_high_info: dict,
    current_price: float,
    config: CycleConfig
) -> CyclePhase:
    """
    Determine current cycle phase based on price position and timing.
    
    Phases:
    - ACCUMULATION: At or near cycle low, price consolidating
    - MARKUP: Rising from cycle low
    - DISTRIBUTION: At or near cycle high, price topping
    - MARKDOWN: Falling from cycle high toward next low
    
    Args:
        df: OHLC DataFrame
        dcl_info: DCL detection results
        cycle_high_info: Cycle high detection results
        current_price: Current market price
        config: Cycle configuration
        
    Returns:
        CyclePhase enum
    """
    dcl_price = dcl_info.get('price')
    high_price = cycle_high_info.get('price')
    dcl_days = dcl_info.get('days_since', 0) or 0
    
    if dcl_price is None:
        return CyclePhase.UNKNOWN
    
    # Calculate range and position
    if high_price and high_price > dcl_price:
        cycle_range = high_price - dcl_price
        price_position = (current_price - dcl_price) / cycle_range if cycle_range > 0 else 0.5
    else:
        price_position = 0.5  # Unknown position
    
    # Determine phase based on timing and price position
    
    # Early in cycle (first third of timing) + near lows = accumulation
    if dcl_days <= config.dcl_early_zone and price_position < 0.3:
        return CyclePhase.ACCUMULATION
    
    # Middle timing + rising price = markup
    if price_position > 0.3 and price_position < 0.7 and dcl_days < config.dcl_max_days:
        return CyclePhase.MARKUP
    
    # Late timing or high price position = distribution
    if price_position > 0.7 or dcl_days >= config.dcl_max_days:
        return CyclePhase.DISTRIBUTION
    
    # Falling price after high = markdown
    if high_price and current_price < high_price * 0.95 and price_position < 0.5:
        return CyclePhase.MARKDOWN
    
    # Default to markup if unclear
    if price_position >= 0.3:
        return CyclePhase.MARKUP
    
    return CyclePhase.UNKNOWN


def _in_timing_zone(cycle_info: dict, early_zone: int, max_days: int) -> bool:
    """Check if we're in the timing zone for a cycle low."""
    days_since = cycle_info.get('days_since')
    if days_since is None:
        return False
    return early_zone <= days_since <= max_days


def _calculate_trade_bias(
    phase: CyclePhase,
    translation: CycleTranslation,
    in_dcl_zone: bool,
    in_wcl_zone: bool,
    dcl_confirmation: CycleConfirmation,
    structural_breaks: Optional[List[StructuralBreak]] = None
) -> Tuple[Literal["LONG", "SHORT", "NEUTRAL"], float]:
    """
    Calculate trade direction bias based on cycle context.
    
    Long bias conditions:
    - At confirmed DCL/WCL (accumulation phase)
    - RTR translation (bullish cycle history)
    - Markup phase with bullish structure
    
    Short bias conditions:
    - LTR translation confirmed (bearish cycle)
    - Distribution/markdown phase
    - Below cycle midpoint with bearish structure
    
    Args:
        phase: Current cycle phase
        translation: Cycle translation
        in_dcl_zone: In DCL timing window
        in_wcl_zone: In WCL timing window  
        dcl_confirmation: DCL confirmation state
        structural_breaks: Recent structural breaks
        
    Returns:
        Tuple of (direction, confidence)
    """
    confidence = 50.0  # Base confidence
    
    # Check for CHoCH in structural breaks
    has_bullish_choch = False
    has_bearish_choch = False
    
    if structural_breaks:
        for sb in structural_breaks:
            if sb.break_type == "CHoCH":
                # Determine CHoCH direction from recent price action
                # CHoCH in downtrend = turning bullish
                # CHoCH in uptrend = turning bearish
                # For now, use timestamp proximity as proxy
                has_bullish_choch = True  # Simplified - would need context
    
    # === LONG BIAS CONDITIONS ===
    
    # Strong long: Confirmed DCL/WCL in accumulation
    if phase == CyclePhase.ACCUMULATION:
        if dcl_confirmation == CycleConfirmation.CONFIRMED:
            confidence = 80.0
        elif in_dcl_zone or in_wcl_zone:
            confidence = 70.0
        else:
            confidence = 60.0
        return ("LONG", confidence)
    
    # Moderate long: Markup phase with RTR
    if phase == CyclePhase.MARKUP:
        if translation == CycleTranslation.RTR:
            return ("LONG", 75.0)
        elif translation == CycleTranslation.MTR:
            return ("LONG", 60.0)
        else:  # LTR in markup = cautious
            return ("NEUTRAL", 50.0)
    
    # === SHORT BIAS CONDITIONS ===
    
    # Strong short: Distribution with LTR
    if phase == CyclePhase.DISTRIBUTION:
        if translation == CycleTranslation.LTR:
            return ("SHORT", 80.0)
        elif translation == CycleTranslation.MTR:
            return ("SHORT", 65.0)
        else:  # RTR in distribution = less clear
            return ("NEUTRAL", 50.0)
    
    # Moderate short: Markdown phase
    if phase == CyclePhase.MARKDOWN:
        if translation == CycleTranslation.LTR:
            return ("SHORT", 75.0)
        else:
            return ("SHORT", 60.0)
    
    # === TRANSLATION-BASED BIAS (when phase unclear) ===
    
    if translation == CycleTranslation.LTR:
        return ("SHORT", 60.0)
    elif translation == CycleTranslation.RTR:
        return ("LONG", 60.0)
    
    return ("NEUTRAL", 50.0)


def _calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Calculate ATR from DataFrame."""
    if len(df) < period:
        return 0.0
    
    high = df['high']
    low = df['low']
    close = df['close'].shift(1)
    
    tr = pd.concat([
        high - low,
        (high - close).abs(),
        (low - close).abs()
    ], axis=1).max(axis=1)
    
    atr = tr.rolling(window=period).mean().iloc[-1]
    return float(atr) if pd.notna(atr) else 0.0


# --- Public API Functions ---

def get_trade_bias_from_cycle(cycle_context: CycleContext) -> Tuple[str, float]:
    """
    Get trade direction bias from existing cycle context.
    
    Convenience function for use in confluence scoring.
    
    Args:
        cycle_context: Pre-computed CycleContext
        
    Returns:
        Tuple of (direction, confidence)
    """
    return (cycle_context.trade_bias, cycle_context.confidence)


def should_boost_direction(
    cycle_context: CycleContext,
    direction: str
) -> Tuple[bool, float]:
    """
    Check if cycle context should boost a specific trade direction.
    
    Used by orchestrator to add bonus instead of penalty.
    
    Args:
        cycle_context: Cycle context
        direction: Trade direction ("LONG" or "SHORT")
        
    Returns:
        Tuple of (should_boost, boost_amount)
    """
    if direction == "LONG":
        if cycle_context.suggests_long:
            if cycle_context.is_at_cycle_low:
                return (True, 5.0)  # Strong boost at cycle low
            elif cycle_context.translation == CycleTranslation.RTR:
                return (True, 3.0)  # Moderate boost with bullish translation
            else:
                return (True, 1.0)  # Small boost
        return (False, 0.0)
    
    elif direction == "SHORT":
        if cycle_context.suggests_short:
            if cycle_context.is_at_cycle_high:
                return (True, 5.0)  # Strong boost at distribution
            elif cycle_context.translation == CycleTranslation.LTR:
                return (True, 3.0)  # Moderate boost with bearish translation
            else:
                return (True, 1.0)
        return (False, 0.0)
    
    return (False, 0.0)


def should_bypass_htf_alignment(
    cycle_context: CycleContext,
    structural_break: Optional[StructuralBreak] = None
) -> bool:
    """
    Check if HTF EMA alignment should be bypassed due to cycle extreme.
    
    Bypass conditions (when structure is broken at cycle extreme):
    - LONG CHoCH at confirmed DCL/WCL zone
    - SHORT CHoCH with LTR translation in distribution/markdown
    
    Args:
        cycle_context: Cycle context
        structural_break: The CHoCH that might bypass alignment
        
    Returns:
        True if HTF alignment should be bypassed
    """
    if structural_break is None or structural_break.break_type != "CHoCH":
        return False
    
    # At cycle low extreme - bypass for bullish reversals
    if cycle_context.is_at_cycle_low:
        return True
    
    # At cycle high with LTR - bypass for bearish reversals
    if (cycle_context.is_at_cycle_high and 
        cycle_context.translation == CycleTranslation.LTR):
        return True
    
    # In DCL/WCL timing zone with accumulation phase
    if cycle_context.phase == CyclePhase.ACCUMULATION and cycle_context.in_dcl_zone:
        return True
    
    return False
