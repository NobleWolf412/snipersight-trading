"""Fibonacci Retracement Calculator

Calculates Fibonacci retracement levels from swing high/low points.
Used by HTF opportunity detection to identify key retracement zones.

NOTE: Statistical research shows Fibonacci has NO predictive edge on its own.
These levels work via self-fulfilling prophecy - institutional algos and retail
traders watch them, creating temporary order clustering. The 61.8% level shows
reversals ~40% of the time (barely better than a coin flip).

We include only the statistically relevant levels:
- 50%: Psychological midpoint (not even a Fibonacci number)
- 61.8%: Most watched = most self-fulfilling

Treat these as "monitored zones" not predictive levels.
"""

from dataclasses import dataclass
from typing import List, Literal, Optional

# Only statistically meaningful Fib ratios (based on research)
# Other ratios (23.6%, 38.2%, 78.6%) are statistical noise
FIB_RATIOS = {
    "fib_500": 0.500,  # Psychological midpoint
    "fib_618": 0.618,  # Most watched = most self-fulfilling (~40% hit rate)
}

# Most-watched ratio (61.8% has most institutional attention)
MONITORED_RATIOS = ["fib_618"]


@dataclass
class FibLevel:
    """A Fibonacci retracement level."""

    price: float
    ratio: float
    ratio_name: str  # e.g., 'fib_618'
    swing_high: float
    swing_low: float
    trend_direction: Literal["bullish", "bearish"]  # Direction of the measured move
    timeframe: str

    @property
    def is_monitored(self) -> bool:
        """Check if this is the most-watched ratio (61.8%)."""
        return self.ratio_name in MONITORED_RATIOS

    @property
    def display_ratio(self) -> str:
        """Human-readable ratio string like '61.8%'."""
        return f"{self.ratio * 100:.1f}%"


def calculate_fib_levels(
    swing_high: float,
    swing_low: float,
    trend_direction: Literal["bullish", "bearish"],
    timeframe: str,
    ratios: Optional[dict] = None,
) -> List[FibLevel]:
    """
    Calculate Fibonacci retracement levels from a swing range.

    For BULLISH trend (price moved up): Fib levels are potential BUY zones
      - Price retraces DOWN from swing_high toward swing_low
      - We calculate retracement FROM swing_high

    For BEARISH trend (price moved down): Fib levels are potential SELL zones
      - Price retraces UP from swing_low toward swing_high
      - We calculate retracement FROM swing_low

    Args:
        swing_high: The swing high price
        swing_low: The swing low price
        trend_direction: 'bullish' if price moved up, 'bearish' if moved down
        timeframe: Timeframe of the swing (e.g., '4h', '1d')
        ratios: Optional custom ratios dict (defaults to FIB_RATIOS)

    Returns:
        List of FibLevel objects sorted by price
    """
    if swing_high <= swing_low:
        return []

    ratios = ratios or FIB_RATIOS
    range_size = swing_high - swing_low
    levels = []

    for ratio_name, ratio in ratios.items():
        if trend_direction == "bullish":
            # Bullish trend: retracement goes DOWN from high
            # 61.8% retracement = high - (range * 0.618)
            price = swing_high - (range_size * ratio)
        else:
            # Bearish trend: retracement goes UP from low
            # 61.8% retracement = low + (range * 0.618)
            price = swing_low + (range_size * ratio)

        levels.append(
            FibLevel(
                price=price,
                ratio=ratio,
                ratio_name=ratio_name,
                swing_high=swing_high,
                swing_low=swing_low,
                trend_direction=trend_direction,
                timeframe=timeframe,
            )
        )

    # Sort by price (descending for bullish, ascending for bearish)
    levels.sort(key=lambda x: x.price, reverse=(trend_direction == "bullish"))

    return levels


def find_nearest_fib(current_price: float, fib_levels: List[FibLevel]) -> Optional[FibLevel]:
    """
    Find the closest Fib level to the current price.

    Args:
        current_price: Current market price
        fib_levels: List of calculated Fib levels

    Returns:
        Nearest FibLevel or None if no levels
    """
    if not fib_levels:
        return None

    return min(fib_levels, key=lambda f: abs(f.price - current_price))


def get_fib_proximity_pct(current_price: float, fib_level: FibLevel) -> float:
    """
    Calculate how close price is to a Fib level as a percentage.

    Args:
        current_price: Current market price
        fib_level: The Fib level to check

    Returns:
        Distance as percentage of price (e.g., 0.5 = 0.5% away)
    """
    if current_price == 0:
        return float("inf")

    return abs(current_price - fib_level.price) / current_price * 100


def is_price_at_fib(current_price: float, fib_level: FibLevel, tolerance_pct: float = 0.5) -> bool:
    """
    Check if price is at a Fib level within tolerance.

    Args:
        current_price: Current market price
        fib_level: The Fib level to check
        tolerance_pct: How close price must be (default 0.5%)

    Returns:
        True if price is within tolerance of the Fib level
    """
    proximity = get_fib_proximity_pct(current_price, fib_level)
    return proximity <= tolerance_pct
