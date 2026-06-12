"""
Premium/Discount Zone Detection

Identifies where price is relative to the current range:
- Premium Zone: Upper 50% of range (sell zone for shorts)
- Discount Zone: Lower 50% of range (buy zone for longs)
- Equilibrium: The 50% level (fair value)

Institutional traders look to buy in discount and sell in premium.
"""

import logging
from dataclasses import dataclass
from typing import Optional, Literal, Tuple
import pandas as pd

logger = logging.getLogger(__name__)

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

    # Phase 5: dealing-range anchor provenance (additive; window-compatible defaults)
    range_anchor: str = "window"  # "structure" | "window" | "window_fallback"
    anchor_swing_high_ts: Optional[str] = None
    anchor_swing_low_ts: Optional[str] = None
    swing_lookback_used: Optional[int] = None

    def to_dict(self):
        return {
            "range_high": self.range_high,
            "range_low": self.range_low,
            "equilibrium": self.equilibrium,
            "extreme_premium": self.extreme_premium,
            "extreme_discount": self.extreme_discount,
            "current_zone": self.current_zone,
            "zone_percentage": self.zone_percentage,
            "range_anchor": self.range_anchor,
            "anchor_swing_high_ts": self.anchor_swing_high_ts,
            "anchor_swing_low_ts": self.anchor_swing_low_ts,
            "swing_lookback_used": self.swing_lookback_used,
        }


def _window_range(df: pd.DataFrame, lookback: int) -> Tuple[float, float]:
    """Legacy window range: high/low of the last `lookback` candles."""
    if len(df) < lookback:
        lookback = len(df)
    recent = df.tail(lookback)
    return float(recent["high"].max()), float(recent["low"].min())


def _compute_structural_dealing_range(
    df: pd.DataFrame, swing_lookback: int
) -> Optional[Tuple[float, float, object, object]]:
    """
    Structure-anchored dealing range (Phase 5, algorithm a*).

    The operative leg: most recent confirmed swing pair (raw bos_choch fractals,
    deduped to an alternating sequence) extended by running extremes —
        range_high = max(SH*, highest high AFTER SH*)
        range_low  = min(SL*, lowest low  AFTER SL*)
    The running-extreme extension is ICT current-leg semantics and preserves the
    "last candle inside range" invariant (no zone_percentage > 100 mid-expansion).

    Returns (range_high, range_low, sh_ts, sl_ts) or None when structure is too
    sparse / degenerate -> caller falls back to the window range (loudly).
    """
    from backend.strategy.smc.bos_choch import (
        _build_swing_sequence,
        _detect_swing_highs,
        _detect_swing_lows,
    )

    if swing_lookback < 1 or len(df) < swing_lookback * 2 + 1:
        return None

    swing_highs = _detect_swing_highs(df, swing_lookback)
    swing_lows = _detect_swing_lows(df, swing_lookback)
    if swing_highs.empty or swing_lows.empty:
        return None

    hl_order, level_order, idx_order = _build_swing_sequence(swing_highs, swing_lows)
    sh_px = sh_ts = sl_px = sl_ts = None
    for typ, level, ts in zip(hl_order, level_order, idx_order):
        if typ == 1:  # swing high
            sh_px, sh_ts = level, ts
        else:  # swing low
            sl_px, sl_ts = level, ts
    if sh_ts is None or sl_ts is None:
        return None

    after_sh = df[df.index > sh_ts]
    after_sl = df[df.index > sl_ts]
    range_high = max(float(sh_px), float(after_sh["high"].max()) if len(after_sh) else float(sh_px))
    range_low = min(float(sl_px), float(after_sl["low"].min()) if len(after_sl) else float(sl_px))

    if not (range_low <= range_high):  # degenerate geometry
        return None
    return range_high, range_low, sh_ts, sl_ts


def detect_premium_discount(
    df: pd.DataFrame,
    lookback: int = 50,
    current_price: Optional[float] = None,
    *,
    anchor: str = "window",
    swing_lookback: Optional[int] = None,
    timeframe: Optional[str] = None,
) -> PremiumDiscountZone:
    """
    Detect premium/discount zones from the current dealing range.

    anchor="window" (default): range = high/low of the last `lookback` candles.
        Byte-identical to pre-Phase-5 behavior — existing callers are unaffected.
    anchor="structure" (Phase 5): range = last confirmed swing pair extended by
        running extremes (see _compute_structural_dealing_range). Falls back to the
        window range — LOUDLY, stamped range_anchor="window_fallback" — when
        structure is too sparse.

    Zone levels (equilibrium/75%/25%) and classification use IDENTICAL formulas for
    both anchors; only the range endpoints differ.

    Args:
        df: OHLCV DataFrame
        lookback: window size for anchor="window" and the structure fallback
        current_price: price for zone classification (premium >= equilibrium)
        anchor: "window" | "structure"
        swing_lookback: fractal lookback for anchor="structure" (required for it;
            ignored for "window")
        timeframe: optional label for fallback diagnostics

    Returns:
        PremiumDiscountZone with all levels + anchor provenance fields
    """
    range_anchor = "window"
    sh_ts = sl_ts = None
    lb_used: Optional[int] = None

    if anchor == "structure":
        if swing_lookback is None:
            raise ValueError(
                "detect_premium_discount(anchor='structure') requires swing_lookback"
            )
        lb_used = swing_lookback
        structural = _compute_structural_dealing_range(df, swing_lookback)
        if structural is not None:
            range_high, range_low, sh_ts, sl_ts = structural
            range_anchor = "structure"
        else:
            # Never silent (CLAUDE.md §LOOP + design fallback clause).
            logger.warning(
                "P/D structure anchor fell back to window range (sparse structure): "
                "tf=%s swing_lookback=%s df_len=%s",
                timeframe, swing_lookback, len(df),
            )
            range_high, range_low = _window_range(df, lookback)
            range_anchor = "window_fallback"
    else:
        range_high, range_low = _window_range(df, lookback)

    # Calculate zone levels (identical for both anchors)
    range_size = range_high - range_low
    equilibrium = range_low + (range_size * 0.5)
    extreme_premium = range_low + (range_size * 0.75)
    extreme_discount = range_low + (range_size * 0.25)

    # Geometry-conservation invariant (§16 rubric 3). True by construction for any
    # finite range_high >= range_low; guards a future refactor that breaks the
    # 0.25/0.5/0.75 interpolation. Never fires on validated OHLCV (high >= low).
    assert range_low <= extreme_discount <= equilibrium <= extreme_premium <= range_high, (
        f"P/D geometry violated: low={range_low} ed={extreme_discount} eq={equilibrium} "
        f"ep={extreme_premium} high={range_high} anchor={range_anchor}"
    )

    zone = PremiumDiscountZone(
        range_high=range_high,
        range_low=range_low,
        equilibrium=equilibrium,
        premium_start=equilibrium,
        discount_end=equilibrium,
        extreme_premium=extreme_premium,
        extreme_discount=extreme_discount,
        range_anchor=range_anchor,
        anchor_swing_high_ts=str(sh_ts) if sh_ts is not None else None,
        anchor_swing_low_ts=str(sl_ts) if sl_ts is not None else None,
        swing_lookback_used=lb_used,
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
