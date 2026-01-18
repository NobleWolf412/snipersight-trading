"""
Premium/Discount Zone Detection

Identifies where price is relative to the current range:
- Premium Zone: Upper 50% of range (sell zone for shorts)
- Discount Zone: Lower 50% of range (buy zone for longs)
- Equilibrium: The 50% level (fair value)

Institutional traders look to buy in discount and sell in premium.
"""

from dataclasses import dataclass
from typing import Optional, Literal
import pandas as pd

ZoneType = Literal["premium", "discount", "equilibrium"]


@dataclass
class PremiumDiscountZone:
    """Premium/Discount zone analysis."""

    range_high: float
    range_low: float
    equilibrium: float  # 50% level
    premium_start: float  # 50% level (same as equilibrium)
    discount_end: float  # 50% level (same as equilibrium)

    # Finer zones for precision
    extreme_premium: float  # 75% level
    extreme_discount: float  # 25% level

    current_price: Optional[float] = None
    current_zone: Optional[ZoneType] = None
    zone_percentage: Optional[float] = None  # 0-100, where in the range

    def to_dict(self):
        return {
            "range_high": self.range_high,
            "range_low": self.range_low,
            "equilibrium": self.equilibrium,
            "extreme_premium": self.extreme_premium,
            "extreme_discount": self.extreme_discount,
            "current_zone": self.current_zone,
            "zone_percentage": self.zone_percentage,
        }


def detect_premium_discount(
    df: pd.DataFrame, lookback: int = 50, current_price: Optional[float] = None
) -> PremiumDiscountZone:
    """
    Detect premium/discount zones from recent price range.

    Uses the swing high and swing low from the lookback period
    to define the trading range, then calculates zones.

    Args:
        df: OHLCV DataFrame
        lookback: Number of candles to consider for range
        current_price: Current price for zone classification

    Returns:
        PremiumDiscountZone with all levels
    """
    if len(df) < lookback:
        lookback = len(df)

    recent = df.tail(lookback)

    range_high = float(recent["high"].max())
    range_low = float(recent["low"].min())

    # Calculate zone levels
    range_size = range_high - range_low
    equilibrium = range_low + (range_size * 0.5)
    extreme_premium = range_low + (range_size * 0.75)
    extreme_discount = range_low + (range_size * 0.25)

    zone = PremiumDiscountZone(
        range_high=range_high,
        range_low=range_low,
        equilibrium=equilibrium,
        premium_start=equilibrium,
        discount_end=equilibrium,
        extreme_premium=extreme_premium,
        extreme_discount=extreme_discount,
    )

    # Classify current price if provided
    if current_price is not None:
        zone.current_price = current_price
        zone.zone_percentage = (
            ((current_price - range_low) / range_size * 100) if range_size > 0 else 50
        )

        if current_price >= equilibrium:
            zone.current_zone = "premium"
        else:
            zone.current_zone = "discount"

    return zone


def get_optimal_entry_zone(direction: str, zone: PremiumDiscountZone) -> dict:
    """
    Get the optimal entry zone for a given direction.

    Args:
        direction: 'long' or 'short'
        zone: PremiumDiscountZone analysis

    Returns:
        Dict with optimal entry range
    """
    if direction.lower() in ("long", "bullish"):
        return {
            "optimal_start": zone.range_low,
            "optimal_end": zone.equilibrium,
            "best_entry": zone.extreme_discount,
            "zone_name": "discount",
            "description": "Buy in discount zone (below equilibrium)",
        }
    else:
        return {
            "optimal_start": zone.equilibrium,
            "optimal_end": zone.range_high,
            "best_entry": zone.extreme_premium,
            "zone_name": "premium",
            "description": "Sell in premium zone (above equilibrium)",
        }


def is_price_in_optimal_zone(price: float, direction: str, zone: PremiumDiscountZone) -> bool:
    """
    Check if price is in the optimal zone for the given direction.

    Args:
        price: Price to check
        direction: 'long' or 'short'
        zone: PremiumDiscountZone

    Returns:
        True if price is in optimal zone
    """
    if direction.lower() in ("long", "bullish"):
        return price <= zone.equilibrium
    else:
        return price >= zone.equilibrium
