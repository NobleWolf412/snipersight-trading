"""
Swing Structure Detection

Labels swing points with market structure context:
- HH: Higher High (bullish continuation)
- HL: Higher Low (bullish continuation)
- LH: Lower High (bearish continuation)
- LL: Lower Low (bearish continuation)

These labels define the trend structure and identify potential reversal points.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Literal
import pandas as pd
import numpy as np
from loguru import logger

SwingType = Literal["HH", "HL", "LH", "LL"]
TrendState = Literal["bullish", "bearish", "neutral"]

# Flag to toggle deduplication (for testing/comparison)
USE_SWING_DEDUPLICATION = True


@dataclass
class SwingPoint:
    """A labeled swing high or low."""

    price: float
    timestamp: datetime
    swing_type: SwingType  # HH, HL, LH, LL
    is_high: bool  # True for swing high, False for swing low
    index: int  # Bar index in the DataFrame
    strength: float = 1.0  # How significant this swing is (based on ATR)

    def __repr__(self):
        return f"{self.swing_type} @ {self.price:.4f} ({self.timestamp})"


@dataclass
class SwingStructure:
    """Complete swing structure analysis for a timeframe."""

    timeframe: str
    swing_points: List[SwingPoint]
    trend: TrendState
    last_hh: Optional[SwingPoint] = None
    last_hl: Optional[SwingPoint] = None
    last_lh: Optional[SwingPoint] = None
    last_ll: Optional[SwingPoint] = None

    def to_dict(self):
        return {
            "timeframe": self.timeframe,
            "trend": self.trend,
            "swing_points": [
                {
                    "type": sp.swing_type,
                    "price": sp.price,
                    "timestamp": sp.timestamp.isoformat(),
                    "is_high": sp.is_high,
                }
                for sp in self.swing_points[-10:]  # Last 10 for API
            ],
            "last_hh": self.last_hh.price if self.last_hh else None,
            "last_hl": self.last_hl.price if self.last_hl else None,
            "last_lh": self.last_lh.price if self.last_lh else None,
            "last_ll": self.last_ll.price if self.last_ll else None,
        }


def detect_swing_structure(
    df: pd.DataFrame, lookback: int = 15, min_swing_atr: float = 0.5
) -> SwingStructure:
    """
    Detect and label swing structure (HH/HL/LH/LL).

    Args:
        df: OHLCV DataFrame with DatetimeIndex
        lookback: Candles to each side for swing detection
        min_swing_atr: Minimum swing size in ATR to be significant

    Returns:
        SwingStructure with labeled swing points and trend
    """
    if len(df) < lookback * 2 + 20:
        logger.warning(
            f"Not enough data for swing structure detection (need {lookback * 2 + 20}, got {len(df)})"
        )
        return SwingStructure(timeframe=_infer_timeframe(df), swing_points=[], trend="neutral")

    # Calculate ATR for significance filtering
    from backend.indicators.volatility import compute_atr

    atr = compute_atr(df, period=14)
    avg_atr = atr.mean()

    # Detect raw swing highs and lows
    swing_highs = _detect_swing_highs(df, lookback)
    swing_lows = _detect_swing_lows(df, lookback)

    # Merge and sort by timestamp
    raw_swings = []

    for idx, price in swing_highs.items():
        if pd.notna(price):
            bar_idx = int(df.index.get_loc(idx))  # type: ignore[arg-type]
            atr_val = atr.iloc[bar_idx] if bar_idx < len(atr) else avg_atr
            strength = abs(price - df["close"].iloc[bar_idx]) / atr_val if atr_val > 0 else 1.0
            raw_swings.append(
                {
                    "timestamp": idx,
                    "price": price,
                    "is_high": True,
                    "index": bar_idx,
                    "strength": strength,
                }
            )

    for idx, price in swing_lows.items():
        if pd.notna(price):
            bar_idx = int(df.index.get_loc(idx))  # type: ignore[arg-type]
            atr_val = atr.iloc[bar_idx] if bar_idx < len(atr) else avg_atr
            strength = abs(price - df["close"].iloc[bar_idx]) / atr_val if atr_val > 0 else 1.0
            raw_swings.append(
                {
                    "timestamp": idx,
                    "price": price,
                    "is_high": False,
                    "index": bar_idx,
                    "strength": strength,
                }
            )

    # Sort by timestamp
    raw_swings.sort(key=lambda x: x["timestamp"])

    # NEW: Deduplicate consecutive same-type swings
    # This ensures alternating High-Low-High-Low pattern for proper BOS/CHoCH detection
    if USE_SWING_DEDUPLICATION:
        raw_swings = _deduplicate_swings(raw_swings)

    # Label swings with HH/HL/LH/LL
    labeled_swings = _label_swings(raw_swings, min_swing_atr, avg_atr)

    # Determine overall trend from recent structure
    trend = _determine_trend(labeled_swings)

    # Extract last of each type
    last_hh = next((sp for sp in reversed(labeled_swings) if sp.swing_type == "HH"), None)
    last_hl = next((sp for sp in reversed(labeled_swings) if sp.swing_type == "HL"), None)
    last_lh = next((sp for sp in reversed(labeled_swings) if sp.swing_type == "LH"), None)
    last_ll = next((sp for sp in reversed(labeled_swings) if sp.swing_type == "LL"), None)

    return SwingStructure(
        timeframe=_infer_timeframe(df),
        swing_points=labeled_swings,
        trend=trend,
        last_hh=last_hh,
        last_hl=last_hl,
        last_lh=last_lh,
        last_ll=last_ll,
    )


def _detect_swing_highs(df: pd.DataFrame, lookback: int) -> pd.Series:
    """Detect swing highs using rolling window."""
    highs = df["high"]
    swing_highs = pd.Series(index=df.index, dtype=float)

    for i in range(lookback, len(df) - lookback):
        window_start = i - lookback
        window_end = i + lookback + 1

        current_high = highs.iloc[i]
        window_highs = highs.iloc[window_start:window_end]

        if current_high == window_highs.max():
            swing_highs.iloc[i] = current_high

    return swing_highs.dropna()


def _detect_swing_lows(df: pd.DataFrame, lookback: int) -> pd.Series:
    """Detect swing lows using rolling window."""
    lows = df["low"]
    swing_lows = pd.Series(index=df.index, dtype=float)

    for i in range(lookback, len(df) - lookback):
        window_start = i - lookback
        window_end = i + lookback + 1

        current_low = lows.iloc[i]
        window_lows = lows.iloc[window_start:window_end]

        if current_low == window_lows.min():
            swing_lows.iloc[i] = current_low

    return swing_lows.dropna()


def _label_swings(raw_swings: List[dict], min_swing_atr: float, avg_atr: float) -> List[SwingPoint]:
    """
    Label raw swings with HH/HL/LH/LL based on structure.
    """
    if not raw_swings:
        return []

    labeled = []
    last_swing_high = None
    last_swing_low = None

    for swing in raw_swings:
        # Filter out insignificant swings
        if swing["strength"] < min_swing_atr:
            continue

        if swing["is_high"]:
            # Determine if HH or LH
            if last_swing_high is None:
                swing_type = "HH"  # First high, assume HH
            elif swing["price"] > last_swing_high["price"]:
                swing_type = "HH"
            else:
                swing_type = "LH"

            sp = SwingPoint(
                price=swing["price"],
                timestamp=(
                    swing["timestamp"].to_pydatetime()
                    if hasattr(swing["timestamp"], "to_pydatetime")
                    else swing["timestamp"]
                ),
                swing_type=swing_type,
                is_high=True,
                index=swing["index"],
                strength=swing["strength"],
            )
            labeled.append(sp)
            last_swing_high = swing

        else:
            # Determine if HL or LL
            if last_swing_low is None:
                swing_type = "HL"  # First low, assume HL
            elif swing["price"] > last_swing_low["price"]:
                swing_type = "HL"
            else:
                swing_type = "LL"

            sp = SwingPoint(
                price=swing["price"],
                timestamp=(
                    swing["timestamp"].to_pydatetime()
                    if hasattr(swing["timestamp"], "to_pydatetime")
                    else swing["timestamp"]
                ),
                swing_type=swing_type,
                is_high=False,
                index=swing["index"],
                strength=swing["strength"],
            )
            labeled.append(sp)
            last_swing_low = swing

    return labeled


def _determine_trend(swings: List[SwingPoint]) -> TrendState:
    """Determine trend from recent swing structure."""
    if len(swings) < 4:
        return "neutral"

    # Look at last 6 swings
    recent = swings[-6:]

    hh_count = sum(1 for s in recent if s.swing_type == "HH")
    hl_count = sum(1 for s in recent if s.swing_type == "HL")
    lh_count = sum(1 for s in recent if s.swing_type == "LH")
    ll_count = sum(1 for s in recent if s.swing_type == "LL")

    bullish_score = hh_count + hl_count
    bearish_score = lh_count + ll_count

    if bullish_score > bearish_score + 1:
        return "bullish"
    elif bearish_score > bullish_score + 1:
        return "bearish"
    else:
        return "neutral"


def _infer_timeframe(df: pd.DataFrame) -> str:
    """Infer timeframe from DataFrame index."""
    if len(df) < 2:
        return "unknown"

    delta = df.index[1] - df.index[0]
    minutes = delta.total_seconds() / 60

    if minutes <= 5:
        return "5m"
    elif minutes <= 15:
        return "15m"
    elif minutes <= 60:
        return "1H"
    elif minutes <= 240:
        return "4H"
    elif minutes <= 1440:
        return "1D"
    else:
        return "1W"


def _deduplicate_swings(raw_swings: List[dict]) -> List[dict]:
    """
    Remove consecutive same-type swings, keeping only the most extreme.

    Ensures alternating High-Low-High-Low pattern which is required for
    proper 4-swing BOS/CHoCH pattern detection.

    STOLEN from smartmoneyconcepts library - vectorized deduplication.

    Args:
        raw_swings: List of swing dicts with 'is_high', 'price', 'timestamp', etc.

    Returns:
        List with consecutive same-type swings removed (keeps extreme)
    """
    if len(raw_swings) < 2:
        return raw_swings

    # Iterate and remove duplicates
    cleaned = []

    for swing in raw_swings:
        if not cleaned:
            cleaned.append(swing)
            continue

        last = cleaned[-1]

        # Check if same type (both highs or both lows)
        if swing["is_high"] == last["is_high"]:
            # Same type - keep the more extreme one
            if swing["is_high"]:  # Both are highs - keep higher
                if swing["price"] > last["price"]:
                    cleaned[-1] = swing  # Replace with higher high
            else:  # Both are lows - keep lower
                if swing["price"] < last["price"]:
                    cleaned[-1] = swing  # Replace with lower low
        else:
            # Different type - keep both (alternating pattern)
            cleaned.append(swing)

    logger.debug(f"Swing deduplication: {len(raw_swings)} -> {len(cleaned)} swings")
    return cleaned


def detect_swings_vectorized(df: pd.DataFrame, swing_length: int = 10) -> pd.DataFrame:
    """
    Vectorized swing detection with deduplication.

    STOLEN from smartmoneyconcepts library - faster than loop-based detection.
    Returns DataFrame compatible with BOS/CHoCH pattern matching.

    Args:
        df: OHLC DataFrame with DatetimeIndex
        swing_length: Lookback/forward for swing detection (each side)

    Returns:
        DataFrame with columns: HighLow (1=high, -1=low), Level (price)
    """
    n = len(df)
    swing_length_total = swing_length * 2

    if n < swing_length_total + 1:
        return pd.DataFrame({"HighLow": [], "Level": []}, index=df.index[:0])

    # Initial detection using rolling window (vectorized)
    high_roll_max = df["high"].shift(-swing_length).rolling(swing_length_total, min_periods=1).max()
    low_roll_min = df["low"].shift(-swing_length).rolling(swing_length_total, min_periods=1).min()

    swing_highs_lows = np.where(
        df["high"] == high_roll_max, 1, np.where(df["low"] == low_roll_min, -1, np.nan)
    ).astype(float)

    # DEDUPLICATION LOOP - Remove consecutive same-type swings
    while True:
        positions = np.where(~np.isnan(swing_highs_lows))[0]

        if len(positions) < 2:
            break

        current = swing_highs_lows[positions[:-1]]
        next_swing = swing_highs_lows[positions[1:]]

        highs = df["high"].iloc[positions[:-1]].values
        lows = df["low"].iloc[positions[:-1]].values

        next_highs = df["high"].iloc[positions[1:]].values
        next_lows = df["low"].iloc[positions[1:]].values

        index_to_remove = np.zeros(len(positions), dtype=bool)

        # Consecutive highs - keep the higher one
        consecutive_highs = (current == 1) & (next_swing == 1)
        index_to_remove[:-1] |= consecutive_highs & (highs < next_highs)
        index_to_remove[1:] |= consecutive_highs & (highs >= next_highs)

        # Consecutive lows - keep the lower one
        consecutive_lows = (current == -1) & (next_swing == -1)
        index_to_remove[:-1] |= consecutive_lows & (lows > next_lows)
        index_to_remove[1:] |= consecutive_lows & (lows <= next_lows)

        if not index_to_remove.any():
            break

        swing_highs_lows[positions[index_to_remove]] = np.nan

    # Build level array
    level = np.where(
        ~np.isnan(swing_highs_lows), np.where(swing_highs_lows == 1, df["high"], df["low"]), np.nan
    )

    return pd.DataFrame({"HighLow": swing_highs_lows, "Level": level}, index=df.index)
