"""
Symbol Cycle Detector - Dynamic Translation Analysis

Detects cycle state for any symbol at Daily and Weekly timeframes.
Based on Camel Finance methodology - translation is the key signal.

Translation Logic:
- RIGHT TRANSLATED (RTR): Peak occurs AFTER midpoint = Bullish, expect higher low
- LEFT TRANSLATED (LTR): Peak occurs BEFORE midpoint = Bearish, expect lower low  
- MID TRANSLATED (MTR): Peak near midpoint = Neutral

Failed Cycle:
- Price breaks below the cycle low = Trend confirmed bearish for remainder of cycle

This applies fractally:
- Daily Cycle (DCL): 18-28 bars on daily chart
- Weekly Cycle (WCL): 35-50 bars on daily chart (or 5-7 bars on weekly)

Usage:
    from backend.strategy.smc.symbol_cycle_detector import detect_symbol_cycles
    
    cycles = detect_symbol_cycles(daily_df, symbol="ETH/USDT")
    print(f"DCL: {cycles.dcl.translation} - Day {cycles.dcl.bars_since_low}")
    print(f"WCL: {cycles.wcl.translation} - Day {cycles.wcl.bars_since_low}")
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Literal, List, Dict, Any, Tuple
from enum import Enum
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class Translation(str, Enum):
    """Cycle translation - determines trend bias."""
    RTR = "right_translated"   # 🟢 Bullish - peak after midpoint
    MTR = "mid_translated"     # 🟡 Neutral - peak near midpoint
    LTR = "left_translated"    # 🔴 Bearish - peak before midpoint
    UNKNOWN = "unknown"


class CycleStatus(str, Enum):
    """Overall cycle health status."""
    HEALTHY = "healthy"           # RTR, no failure
    CAUTION = "caution"           # MTR or approaching failure
    WARNING = "warning"           # LTR detected
    FAILED = "failed"             # Broke cycle low
    EARLY = "early"               # Too early to determine
    UNKNOWN = "unknown"


@dataclass
class CycleState:
    """
    State of a single cycle (DCL or WCL).
    
    Attributes:
        cycle_type: "DCL" or "WCL"
        bars_since_low: Bars elapsed since cycle low
        expected_length: Expected cycle duration range
        midpoint: Midpoint bar number
        
        cycle_low_price: Price at cycle low
        cycle_low_bar: Bar index of cycle low
        cycle_low_timestamp: Timestamp of cycle low
        
        cycle_high_price: Highest price since cycle low
        cycle_high_bar: Bar index of cycle high
        peak_bar: Bars from low to peak
        
        translation: RTR/MTR/LTR based on peak position
        translation_pct: Peak position as percentage (>50% = RTR)
        
        is_failed: True if price broke below cycle low
        is_in_window: True if in expected cycle low window
        
        status: Overall health assessment
        bias: Trade direction bias from this cycle
    """
    cycle_type: Literal["DCL", "WCL"]
    
    # Timing
    bars_since_low: int
    expected_length: Tuple[int, int]  # (min, max)
    midpoint: float
    
    # Cycle Low
    cycle_low_price: float
    cycle_low_bar: int
    cycle_low_timestamp: Optional[datetime] = None
    
    # Cycle High (Peak)
    cycle_high_price: Optional[float] = None
    cycle_high_bar: Optional[int] = None
    peak_bar: Optional[int] = None  # Bars from low to peak
    
    # Translation
    translation: Translation = Translation.UNKNOWN
    translation_pct: float = 0.0  # Where peak occurred (0-100%)
    
    # Status
    is_failed: bool = False
    is_in_window: bool = False
    current_price: float = 0.0
    
    # Derived
    status: CycleStatus = CycleStatus.UNKNOWN
    bias: Literal["LONG", "SHORT", "NEUTRAL"] = "NEUTRAL"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "cycle_type": self.cycle_type,
            "bars_since_low": self.bars_since_low,
            "expected_length": {
                "min": self.expected_length[0],
                "max": self.expected_length[1]
            },
            "midpoint": self.midpoint,
            "cycle_low": {
                "price": self.cycle_low_price,
                "bar": self.cycle_low_bar,
                "timestamp": self.cycle_low_timestamp.isoformat() if self.cycle_low_timestamp else None
            },
            "cycle_high": {
                "price": self.cycle_high_price,
                "bar": self.cycle_high_bar,
                "peak_bar": self.peak_bar
            },
            "translation": self.translation.value,
            "translation_pct": round(self.translation_pct, 1),
            "is_failed": self.is_failed,
            "is_in_window": self.is_in_window,
            "status": self.status.value,
            "bias": self.bias
        }


@dataclass
class SymbolCycles:
    """
    Complete cycle context for a symbol.
    
    Contains both DCL and WCL states plus aggregate assessment.
    """
    symbol: str
    dcl: CycleState
    wcl: CycleState
    
    # Aggregate
    overall_bias: Literal["LONG", "SHORT", "NEUTRAL"] = "NEUTRAL"
    alignment: Literal["ALIGNED", "MIXED", "CONFLICTING"] = "MIXED"
    warnings: List[str] = field(default_factory=list)
    
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "symbol": self.symbol,
            "dcl": self.dcl.to_dict(),
            "wcl": self.wcl.to_dict(),
            "overall_bias": self.overall_bias,
            "alignment": self.alignment,
            "warnings": self.warnings,
            "timestamp": self.timestamp.isoformat()
        }


# ==============================================================================
# CYCLE CONFIGURATION
# ==============================================================================

# Cycle length expectations (in daily bars)
CYCLE_CONFIG = {
    "DCL": {
        "min_length": 18,
        "max_length": 28,
        "lookback_multiplier": 2.5,  # Look back 2.5x max length to find cycle low
        "swing_lookback": 3,  # Bars each side for swing detection
    },
    "WCL": {
        "min_length": 35,
        "max_length": 50,
        "lookback_multiplier": 2.0,
        "swing_lookback": 5,
    }
}

# Translation thresholds
TRANSLATION_THRESHOLDS = {
    "rtr_min": 0.55,  # Peak after 55% = Right Translated
    "ltr_max": 0.45,  # Peak before 45% = Left Translated
    # Between 45-55% = Mid Translated
}


# ==============================================================================
# CORE DETECTION FUNCTIONS
# ==============================================================================

def detect_symbol_cycles(
    df: pd.DataFrame,
    symbol: str = "UNKNOWN",
    current_price: Optional[float] = None
) -> SymbolCycles:
    """
    Detect cycle state for a symbol from daily OHLC data.
    
    Args:
        df: DataFrame with OHLC data (daily timeframe preferred)
        symbol: Symbol name for labeling
        current_price: Current price (uses last close if not provided)
        
    Returns:
        SymbolCycles with DCL and WCL states
    """
    if len(df) < CYCLE_CONFIG["WCL"]["max_length"] * 2:
        logger.warning("Insufficient data for cycle detection: %d bars", len(df))
        return _empty_cycles(symbol)
    
    if current_price is None:
        current_price = float(df['close'].iloc[-1])
    
    # Detect each cycle
    dcl = _detect_cycle(df, "DCL", current_price)
    wcl = _detect_cycle(df, "WCL", current_price)
    
    # Calculate aggregate assessment
    overall_bias, alignment, warnings = _assess_cycles(dcl, wcl)
    
    return SymbolCycles(
        symbol=symbol,
        dcl=dcl,
        wcl=wcl,
        overall_bias=overall_bias,
        alignment=alignment,
        warnings=warnings,
        timestamp=datetime.utcnow()
    )


def _detect_cycle(
    df: pd.DataFrame,
    cycle_type: Literal["DCL", "WCL"],
    current_price: float
) -> CycleState:
    """
    Detect a single cycle (DCL or WCL) from price data.
    
    Process:
    1. Find most recent significant swing low (cycle low)
    2. Count bars since that low
    3. Find highest high since the low (cycle peak)
    4. Calculate translation based on peak position
    5. Check for cycle failure
    """
    config = CYCLE_CONFIG[cycle_type]
    min_len = config["min_length"]
    max_len = config["max_length"]
    lookback = int(max_len * config["lookback_multiplier"])
    swing_lb = config["swing_lookback"]
    
    # Ensure we have enough data
    if len(df) < lookback:
        lookback = len(df)
    
    # Work with recent data
    recent_df = df.tail(lookback).copy()
    recent_df = recent_df.reset_index(drop=True)
    
    # Find swing lows
    swing_lows = _find_swing_lows(recent_df, swing_lb)
    
    if not swing_lows:
        return _empty_cycle_state(cycle_type, min_len, max_len, current_price)
    
    # Get most recent significant swing low
    # For WCL, we want a more significant low (deeper)
    if cycle_type == "WCL" and len(swing_lows) > 1:
        # Find the lowest low in the valid range
        valid_lows = [s for s in swing_lows if s['bars_ago'] <= max_len * 1.5]
        if valid_lows:
            cycle_low = min(valid_lows, key=lambda x: x['price'])
        else:
            cycle_low = swing_lows[-1]
    else:
        # For DCL, use most recent swing low
        cycle_low = swing_lows[-1]
    
    # Calculate bars since low
    bars_since_low = cycle_low['bars_ago']
    cycle_low_idx = len(recent_df) - 1 - bars_since_low
    
    # Get timestamp if available
    cycle_low_ts = None
    if hasattr(df.index, 'to_pydatetime') or isinstance(df.index, pd.DatetimeIndex):
        try:
            original_idx = len(df) - 1 - bars_since_low
            if original_idx >= 0:
                ts = df.index[original_idx]
                cycle_low_ts = ts.to_pydatetime() if hasattr(ts, 'to_pydatetime') else ts
        except:
            pass
    
    # Find cycle high (highest point since cycle low)
    post_low_df = recent_df.iloc[cycle_low_idx:]
    if len(post_low_df) > 0:
        high_idx_rel = post_low_df['high'].idxmax()
        cycle_high_price = float(post_low_df['high'].max())
        peak_bar = high_idx_rel - cycle_low_idx
    else:
        cycle_high_price = current_price
        peak_bar = bars_since_low
    
    # Calculate translation percentage (where peak occurred)
    # Translation = where did the peak occur relative to current cycle progress?
    if bars_since_low > 0:
        translation_pct = (peak_bar / bars_since_low) * 100
    else:
        translation_pct = 50.0
    
    # Calculate midpoint for buffer logic
    midpoint = (min_len + max_len) / 2
    
    # Determine translation with buffer (3 weeks for WCL, 1 week for DCL)
    translation = _determine_translation(
        translation_pct, 
        bars_since_low=bars_since_low, 
        midpoint=midpoint, 
        cycle_type=cycle_type
    )
    
    # Check if in cycle low window
    is_in_window = min_len <= bars_since_low <= max_len
    
    # Check for cycle failure
    is_failed = current_price < cycle_low['price']
    
    # Determine status and bias
    status = _determine_status(translation, is_failed, bars_since_low, min_len)
    bias = _determine_bias(translation, is_failed, is_in_window)
    
    return CycleState(
        cycle_type=cycle_type,
        bars_since_low=bars_since_low,
        expected_length=(min_len, max_len),
        midpoint=midpoint,
        cycle_low_price=cycle_low['price'],
        cycle_low_bar=cycle_low_idx,
        cycle_low_timestamp=cycle_low_ts,
        cycle_high_price=cycle_high_price,
        cycle_high_bar=cycle_low_idx + peak_bar if peak_bar else None,
        peak_bar=peak_bar,
        translation=translation,
        translation_pct=translation_pct,
        is_failed=is_failed,
        is_in_window=is_in_window,
        current_price=current_price,
        status=status,
        bias=bias
    )


def _find_swing_lows(df: pd.DataFrame, lookback: int = 3) -> List[Dict]:
    """
    Find swing lows in price data.
    
    A swing low is a bar where the low is lower than N bars on each side.
    
    Args:
        df: OHLC DataFrame
        lookback: Bars to check on each side
        
    Returns:
        List of dicts with price, index, bars_ago
    """
    swing_lows = []
    
    for i in range(lookback, len(df) - lookback):
        current_low = df['low'].iloc[i]
        
        # Check if lower than all bars on left
        is_swing = True
        for j in range(i - lookback, i):
            if df['low'].iloc[j] <= current_low:
                is_swing = False
                break
        
        # Check if lower than all bars on right
        if is_swing:
            for j in range(i + 1, i + lookback + 1):
                if df['low'].iloc[j] <= current_low:
                    is_swing = False
                    break
        
        if is_swing:
            swing_lows.append({
                'price': float(current_low),
                'index': i,
                'bars_ago': len(df) - 1 - i
            })
    
    return swing_lows


def _determine_translation(
    translation_pct: float, 
    bars_since_low: int = 0, 
    midpoint: float = 0, 
    cycle_type: str = "DCL"
) -> Translation:
    """
    Determine translation based on peak position percentage WITH buffer logic.
    
    Buffer Logic:
    - DCL: 3 day buffer past midpoint before confirming LTR/RTR
    - WCL: 5 day buffer past midpoint before confirming LTR/RTR
    - If within buffer zone, return MTR (waiting for confirmation)
    
    This ensures confirmation happens ~3 days before cycle max to remain actionable.
    
    Args:
        translation_pct: Where peak occurred as % of cycle (0-100)
        bars_since_low: Current bars into the cycle
        midpoint: Midpoint bar number for the cycle
        cycle_type: "DCL" or "WCL"
    """
    # Buffer in bars/days (confirm ~3 days before cycle max)
    buffer = 5 if cycle_type == "WCL" else 3  # 5 days for WCL, 3 days for DCL
    
    # First check basic translation thresholds
    if translation_pct >= TRANSLATION_THRESHOLDS["rtr_min"] * 100:
        raw_translation = Translation.RTR
    elif translation_pct <= TRANSLATION_THRESHOLDS["ltr_max"] * 100:
        raw_translation = Translation.LTR
    else:
        return Translation.MTR  # Clearly mid-translated, no buffer needed
    
    # Apply buffer: must be past midpoint + buffer to confirm non-MTR translation
    confirmation_threshold = midpoint + buffer
    
    if bars_since_low < confirmation_threshold:
        # Not enough time has passed - still could change
        # Return MTR (pending) instead of premature LTR/RTR
        return Translation.MTR
    
    # Past the buffer - translation is confirmed
    return raw_translation


def _determine_status(
    translation: Translation,
    is_failed: bool,
    bars_since_low: int,
    min_length: int
) -> CycleStatus:
    """Determine overall cycle status."""
    if is_failed:
        return CycleStatus.FAILED
    
    if bars_since_low < min_length * 0.5:
        return CycleStatus.EARLY
    
    if translation == Translation.LTR:
        return CycleStatus.WARNING
    elif translation == Translation.MTR:
        return CycleStatus.CAUTION
    elif translation == Translation.RTR:
        return CycleStatus.HEALTHY
    
    return CycleStatus.UNKNOWN


def _determine_bias(
    translation: Translation,
    is_failed: bool,
    is_in_window: bool
) -> Literal["LONG", "SHORT", "NEUTRAL"]:
    """Determine trade direction bias from cycle state."""
    if is_failed:
        return "SHORT"
    
    if translation == Translation.RTR:
        return "LONG"
    elif translation == Translation.LTR:
        return "SHORT"
    
    # MTR or in window - neutral
    return "NEUTRAL"


def _assess_cycles(
    dcl: CycleState,
    wcl: CycleState
) -> Tuple[Literal["LONG", "SHORT", "NEUTRAL"], Literal["ALIGNED", "MIXED", "CONFLICTING"], List[str]]:
    """
    Assess overall cycle context from DCL and WCL states.
    
    Returns:
        Tuple of (overall_bias, alignment, warnings)
    """
    warnings = []
    
    # Check for failures first
    if dcl.is_failed:
        warnings.append("Daily cycle FAILED - price below DCL low")
    if wcl.is_failed:
        warnings.append("Weekly cycle FAILED - price below WCL low")
    
    # Check for LTR warnings
    if dcl.translation == Translation.LTR:
        warnings.append("Daily cycle left-translated - short-term weakness")
    if wcl.translation == Translation.LTR:
        warnings.append("Weekly cycle left-translated - intermediate weakness")
    
    # Check for window
    if dcl.is_in_window:
        warnings.append(f"In DCL window (Day {dcl.bars_since_low}) - watch for bounce")
    if wcl.is_in_window:
        warnings.append(f"In WCL window (Day {wcl.bars_since_low}) - major support zone")
    
    # Determine alignment
    biases = [dcl.bias, wcl.bias]
    
    if dcl.bias == wcl.bias and dcl.bias != "NEUTRAL":
        alignment = "ALIGNED"
        overall_bias = dcl.bias
    elif "LONG" in biases and "SHORT" in biases:
        alignment = "CONFLICTING"
        # WCL takes precedence
        overall_bias = wcl.bias if wcl.bias != "NEUTRAL" else dcl.bias
    else:
        alignment = "MIXED"
        # Use non-neutral bias if available
        if wcl.bias != "NEUTRAL":
            overall_bias = wcl.bias
        elif dcl.bias != "NEUTRAL":
            overall_bias = dcl.bias
        else:
            overall_bias = "NEUTRAL"
    
    return overall_bias, alignment, warnings


def _empty_cycle_state(
    cycle_type: str,
    min_len: int,
    max_len: int,
    current_price: float
) -> CycleState:
    """Return empty cycle state when detection fails."""
    return CycleState(
        cycle_type=cycle_type,
        bars_since_low=0,
        expected_length=(min_len, max_len),
        midpoint=(min_len + max_len) / 2,
        cycle_low_price=current_price,
        cycle_low_bar=0,
        current_price=current_price,
        status=CycleStatus.UNKNOWN,
        bias="NEUTRAL"
    )


def _empty_cycles(symbol: str) -> SymbolCycles:
    """Return empty cycles when detection fails."""
    dcl_config = CYCLE_CONFIG["DCL"]
    wcl_config = CYCLE_CONFIG["WCL"]
    
    return SymbolCycles(
        symbol=symbol,
        dcl=_empty_cycle_state("DCL", dcl_config["min_length"], dcl_config["max_length"], 0.0),
        wcl=_empty_cycle_state("WCL", wcl_config["min_length"], wcl_config["max_length"], 0.0),
        overall_bias="NEUTRAL",
        alignment="MIXED",
        warnings=["Insufficient data for cycle detection"]
    )


# ==============================================================================
# NOTIFICATION TRIGGERS
# ==============================================================================

@dataclass
class CycleAlert:
    """A cycle-related alert/notification."""
    symbol: str
    alert_type: Literal["INFO", "WARNING", "CRITICAL"]
    cycle: Literal["DCL", "WCL", "4YC"]
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


def check_cycle_alerts(cycles: SymbolCycles) -> List[CycleAlert]:
    """
    Check for alertable conditions in cycle state.
    
    Returns list of alerts that should be triggered.
    """
    alerts = []
    symbol = cycles.symbol
    
    # DCL Alerts
    dcl = cycles.dcl
    
    # Entering DCL window
    if dcl.is_in_window and dcl.bars_since_low == dcl.expected_length[0]:
        alerts.append(CycleAlert(
            symbol=symbol,
            alert_type="INFO",
            cycle="DCL",
            message=f"{symbol} entering Daily Cycle Low window",
            details={"day": dcl.bars_since_low, "window": dcl.expected_length}
        ))
    
    # DCL Failed
    if dcl.is_failed:
        alerts.append(CycleAlert(
            symbol=symbol,
            alert_type="WARNING",
            cycle="DCL",
            message=f"{symbol} Daily Cycle FAILED - broke ${dcl.cycle_low_price:.2f}",
            details={"cycle_low": dcl.cycle_low_price, "current": dcl.current_price}
        ))
    
    # DCL Left Translated
    if dcl.translation == Translation.LTR and dcl.bars_since_low > dcl.midpoint:
        alerts.append(CycleAlert(
            symbol=symbol,
            alert_type="WARNING",
            cycle="DCL",
            message=f"{symbol} Daily Cycle left-translated - short-term weakness",
            details={"translation_pct": dcl.translation_pct, "peak_day": dcl.peak_bar}
        ))
    
    # WCL Alerts
    wcl = cycles.wcl
    
    # Entering WCL window
    if wcl.is_in_window and wcl.bars_since_low == wcl.expected_length[0]:
        alerts.append(CycleAlert(
            symbol=symbol,
            alert_type="INFO",
            cycle="WCL",
            message=f"{symbol} entering Weekly Cycle Low window",
            details={"day": wcl.bars_since_low, "window": wcl.expected_length}
        ))
    
    # WCL Failed
    if wcl.is_failed:
        alerts.append(CycleAlert(
            symbol=symbol,
            alert_type="CRITICAL",
            cycle="WCL",
            message=f"🚨 {symbol} Weekly Cycle FAILED - trend reversal confirmed",
            details={"cycle_low": wcl.cycle_low_price, "current": wcl.current_price}
        ))
    
    # WCL Left Translated
    if wcl.translation == Translation.LTR and wcl.bars_since_low > wcl.midpoint:
        alerts.append(CycleAlert(
            symbol=symbol,
            alert_type="WARNING",
            cycle="WCL",
            message=f"⚠️ {symbol} Weekly Cycle left-translated - intermediate weakness",
            details={"translation_pct": wcl.translation_pct, "peak_day": wcl.peak_bar}
        ))
    
    return alerts


# ==============================================================================
# SIGNAL CONTEXT HELPER
# ==============================================================================

def get_cycle_context_for_signal(
    cycles: SymbolCycles,
    signal_direction: Literal["LONG", "SHORT"]
) -> Dict[str, Any]:
    """
    Get cycle context summary for a trading signal.
    
    Used to attach cycle info to scanner results.
    
    Args:
        cycles: Symbol's cycle state
        signal_direction: The signal's direction
        
    Returns:
        Dict with alignment info and any warnings
    """
    dcl = cycles.dcl
    wcl = cycles.wcl
    
    # Check if signal aligns with cycles
    dcl_aligned = (
        (signal_direction == "LONG" and dcl.bias in ["LONG", "NEUTRAL"]) or
        (signal_direction == "SHORT" and dcl.bias in ["SHORT", "NEUTRAL"])
    )
    wcl_aligned = (
        (signal_direction == "LONG" and wcl.bias in ["LONG", "NEUTRAL"]) or
        (signal_direction == "SHORT" and wcl.bias in ["SHORT", "NEUTRAL"])
    )
    
    # Build context
    context = {
        "dcl": {
            "day": dcl.bars_since_low,
            "of": f"{dcl.expected_length[0]}-{dcl.expected_length[1]}",
            "translation": dcl.translation.value.replace("_translated", "").upper(),
            "status": dcl.status.value,
            "aligned": dcl_aligned
        },
        "wcl": {
            "day": wcl.bars_since_low,
            "of": f"{wcl.expected_length[0]}-{wcl.expected_length[1]}",
            "translation": wcl.translation.value.replace("_translated", "").upper(),
            "status": wcl.status.value,
            "aligned": wcl_aligned
        },
        "overall_aligned": dcl_aligned and wcl_aligned,
        "alignment": cycles.alignment,
        "warnings": cycles.warnings
    }
    
    # Add conflict warnings
    if signal_direction == "LONG":
        if dcl.translation == Translation.LTR:
            context["warnings"].append(f"⚠️ LONG signal but DCL is left-translated")
        if wcl.translation == Translation.LTR:
            context["warnings"].append(f"⚠️ LONG signal but WCL is left-translated")
        if dcl.is_failed or wcl.is_failed:
            context["warnings"].append(f"🚨 LONG signal but cycle(s) FAILED")
    else:  # SHORT
        if dcl.translation == Translation.RTR:
            context["warnings"].append(f"⚠️ SHORT signal but DCL is right-translated")
        if wcl.translation == Translation.RTR:
            context["warnings"].append(f"⚠️ SHORT signal but WCL is right-translated")
    
    return context
