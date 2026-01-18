"""
Key Price Levels Detection

Extracts institutional reference levels:
- PWH/PWL: Previous Week High/Low
- PDH/PDL: Previous Day High/Low
- PMH/PML: Previous Month High/Low (optional)

These levels are watched by institutions and act as liquidity targets.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict
import pandas as pd
from loguru import logger


@dataclass
class KeyLevel:
    """A significant price level."""

    price: float
    level_type: str  # 'PWH', 'PWL', 'PDH', 'PDL', 'PMH', 'PML'
    timestamp: datetime  # When this level was formed
    timeframe: str
    touched: bool = False  # Has price touched this level since?
    swept: bool = False  # Has price swept through and reversed?

    def __repr__(self):
        status = "SWEPT" if self.swept else ("TOUCHED" if self.touched else "FRESH")
        return f"{self.level_type}: {self.price:.4f} ({status})"


@dataclass
class KeyLevels:
    """Collection of key levels for a symbol."""

    symbol: str
    pwh: Optional[KeyLevel] = None  # Previous Week High
    pwl: Optional[KeyLevel] = None  # Previous Week Low
    pdh: Optional[KeyLevel] = None  # Previous Day High
    pdl: Optional[KeyLevel] = None  # Previous Day Low
    pmh: Optional[KeyLevel] = None  # Previous Month High (optional)
    pml: Optional[KeyLevel] = None  # Previous Month Low (optional)

    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses."""
        return {
            "symbol": self.symbol,
            "pwh": {"price": self.pwh.price, "swept": self.pwh.swept} if self.pwh else None,
            "pwl": {"price": self.pwl.price, "swept": self.pwl.swept} if self.pwl else None,
            "pdh": {"price": self.pdh.price, "swept": self.pdh.swept} if self.pdh else None,
            "pdl": {"price": self.pdl.price, "swept": self.pdl.swept} if self.pdl else None,
        }

    def all_levels(self) -> List[KeyLevel]:
        """Return all non-None levels as a list."""
        return [l for l in [self.pwh, self.pwl, self.pdh, self.pdl, self.pmh, self.pml] if l]


def detect_key_levels(
    df_daily: pd.DataFrame,
    df_weekly: Optional[pd.DataFrame] = None,
    current_price: Optional[float] = None,
) -> KeyLevels:
    """
    Detect PWH/PWL/PDH/PDL from daily and weekly data.

    Args:
        df_daily: Daily OHLCV DataFrame with DatetimeIndex
        df_weekly: Weekly OHLCV DataFrame (optional, will derive from daily if not provided)
        current_price: Current price for touch/sweep detection

    Returns:
        KeyLevels object with all detected levels
    """
    if len(df_daily) < 2:
        logger.warning("Not enough daily data for key level detection")
        return KeyLevels(symbol="UNKNOWN")

    symbol = "UNKNOWN"  # Will be set by caller if needed

    # Get previous day high/low (second to last complete candle)
    # Last candle might be incomplete
    prev_day = df_daily.iloc[-2]
    pdh = KeyLevel(
        price=float(prev_day["high"]),
        level_type="PDH",
        timestamp=prev_day.name if isinstance(prev_day.name, datetime) else datetime.now(),
        timeframe="1D",
    )
    pdl = KeyLevel(
        price=float(prev_day["low"]),
        level_type="PDL",
        timestamp=prev_day.name if isinstance(prev_day.name, datetime) else datetime.now(),
        timeframe="1D",
    )

    # Get previous week high/low
    pwh = None
    pwl = None

    if df_weekly is not None and len(df_weekly) >= 2:
        prev_week = df_weekly.iloc[-2]
        pwh = KeyLevel(
            price=float(prev_week["high"]),
            level_type="PWH",
            timestamp=prev_week.name if isinstance(prev_week.name, datetime) else datetime.now(),
            timeframe="1W",
        )
        pwl = KeyLevel(
            price=float(prev_week["low"]),
            level_type="PWL",
            timestamp=prev_week.name if isinstance(prev_week.name, datetime) else datetime.now(),
            timeframe="1W",
        )
    else:
        # Derive from daily data - find last 7 complete days
        if len(df_daily) >= 8:
            last_week = df_daily.iloc[-8:-1]  # 7 days before today
            pwh = KeyLevel(
                price=float(last_week["high"].max()),
                level_type="PWH",
                timestamp=last_week["high"].idxmax(),
                timeframe="1W",
            )
            pwl = KeyLevel(
                price=float(last_week["low"].min()),
                level_type="PWL",
                timestamp=last_week["low"].idxmin(),
                timeframe="1W",
            )

    # Check touch/sweep status if current price provided
    if current_price is not None:
        _update_level_status(pdh, current_price, is_high=True)
        _update_level_status(pdl, current_price, is_high=False)
        if pwh:
            _update_level_status(pwh, current_price, is_high=True)
        if pwl:
            _update_level_status(pwl, current_price, is_high=False)

    return KeyLevels(symbol=symbol, pwh=pwh, pwl=pwl, pdh=pdh, pdl=pdl)


def _update_level_status(
    level: KeyLevel, current_price: float, is_high: bool, sweep_threshold: float = 0.001
):
    """
    Update touched/swept status based on current price.

    Args:
        level: The KeyLevel to update
        current_price: Current market price
        is_high: True if this is a high level (PWH/PDH), False for lows
        sweep_threshold: Percentage beyond level to consider a sweep (0.1%)
    """
    if is_high:
        # For highs: touched if price >= level, swept if price went above then came back
        if current_price >= level.price:
            level.touched = True
        if current_price >= level.price * (1 + sweep_threshold):
            level.swept = True
    else:
        # For lows: touched if price <= level, swept if price went below then came back
        if current_price <= level.price:
            level.touched = True
        if current_price <= level.price * (1 - sweep_threshold):
            level.swept = True


def get_nearest_level(
    levels: KeyLevels, current_price: float, direction: str = "both"
) -> Optional[KeyLevel]:
    """
    Find the nearest key level to current price.

    Args:
        levels: KeyLevels object
        current_price: Current price
        direction: 'above', 'below', or 'both'

    Returns:
        Nearest KeyLevel or None
    """
    all_levels = levels.all_levels()
    if not all_levels:
        return None

    if direction == "above":
        above = [l for l in all_levels if l.price > current_price]
        return min(above, key=lambda l: l.price - current_price) if above else None
    elif direction == "below":
        below = [l for l in all_levels if l.price < current_price]
        return max(below, key=lambda l: current_price - l.price) if below else None
    else:
        return min(all_levels, key=lambda l: abs(l.price - current_price))
