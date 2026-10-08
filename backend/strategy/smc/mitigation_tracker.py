"""
SMC Mitigation & Fill Tracking

Tracks the real-time status of:
- Order Block mitigation (how much has been revisited)
- FVG fill status (how much of the gap has been filled)

This filters out stale/mitigated zones so only fresh ones are used for entries.
"""

from dataclasses import dataclass, replace
from numbers import Number
from typing import List, Tuple
import pandas as pd
from loguru import logger

from backend.shared.models.smc import OrderBlock, FVG


class FormationTimeError(ValueError):
    """The candle/formation clock cannot establish causal zone state."""


def candles_after_formation(df: pd.DataFrame, formation_time) -> pd.DataFrame:
    """Compare instants in UTC; naive exchange timestamps denote UTC.

    Never fall back to pre-formation candles when the time contract is invalid.
    Return the original rows so callers retain OHLCV values and index identity.
    """
    try:
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("candles require a DatetimeIndex")
        if df.index.hasnans or not df.index.is_monotonic_increasing:
            raise ValueError("candle timestamps must be valid and chronological")
        if formation_time is None or isinstance(formation_time, Number):
            raise ValueError("formation requires a timestamp, not a numeric epoch")
        formed = pd.Timestamp(formation_time)
        if pd.isna(formed):
            raise ValueError("formation timestamp is missing")
        formed = formed.tz_localize("UTC") if formed.tzinfo is None else formed.tz_convert("UTC")
        clock = df.index.tz_localize("UTC") if df.index.tz is None else df.index.tz_convert("UTC")
        return df.loc[clock > formed]
    except (TypeError, ValueError, OverflowError) as exc:
        raise FormationTimeError(f"SMC_FORMATION_TIME_INVALID: {exc}") from exc


@dataclass
class MitigationStatus:
    """Status of OB/FVG mitigation."""

    original_count: int
    fresh_count: int
    partially_mitigated_count: int
    fully_mitigated_count: int


def update_ob_mitigation(
    order_blocks: List[OrderBlock], df: pd.DataFrame, max_mitigation: float = 0.5
) -> Tuple[List[OrderBlock], MitigationStatus]:
    """
    Update Order Block mitigation levels based on price action.

    An OB is mitigated when price revisits the zone:
    - 0%: Never touched since formation (fresh)
    - 50%: Price entered but didn't fill completely
    - 100%: Price swept through entire zone

    Args:
        order_blocks: List of OrderBlocks to update
        df: Recent OHLCV data to check for mitigation
        max_mitigation: Maximum mitigation level to keep (0.5 = 50%)

    Returns:
        Tuple of (filtered fresh OBs, mitigation status)
    """
    if not order_blocks:
        return [], MitigationStatus(0, 0, 0, 0)

    updated = []
    fresh = []
    partially_mitigated = 0
    fully_mitigated = 0

    for ob in order_blocks:
        new_mitigation = _calculate_ob_mitigation(ob, df)

        # Update the OB with new mitigation level
        updated_ob = replace(ob, mitigation_level=new_mitigation)
        updated.append(updated_ob)

        if new_mitigation >= 1.0:
            fully_mitigated += 1
        elif new_mitigation > max_mitigation:
            partially_mitigated += 1
        else:
            fresh.append(updated_ob)

    status = MitigationStatus(
        original_count=len(order_blocks),
        fresh_count=len(fresh),
        partially_mitigated_count=partially_mitigated,
        fully_mitigated_count=fully_mitigated,
    )

    logger.debug(
        f"OB Mitigation: {len(fresh)}/{len(order_blocks)} fresh (max_mitigation={max_mitigation})"
    )

    return fresh, status


def _calculate_ob_mitigation(ob: OrderBlock, df: pd.DataFrame) -> float:
    """
    Calculate how much an OB has been mitigated by recent price action.

    Returns value from 0.0 (fresh) to 1.0 (fully mitigated).
    """
    if df.empty:
        return ob.mitigation_level

    after_formation = candles_after_formation(df, ob.timestamp)

    if after_formation.empty:
        return ob.mitigation_level

    ob_range = ob.high - ob.low
    if ob_range <= 0:
        return 1.0  # Invalid OB

    if ob.direction == "bullish":
        # Bullish OB: demand zone, mitigated when price sweeps through from above
        lowest_low = after_formation["low"].min()
        if lowest_low <= ob.low:
            return 1.0  # Fully swept
        elif lowest_low < ob.high:
            # Partial mitigation
            penetration = ob.high - lowest_low
            return min(1.0, penetration / ob_range)
    else:
        # Bearish OB: supply zone, mitigated when price sweeps through from below
        highest_high = after_formation["high"].max()
        if highest_high >= ob.high:
            return 1.0  # Fully swept
        elif highest_high > ob.low:
            # Partial mitigation
            penetration = highest_high - ob.low
            return min(1.0, penetration / ob_range)

    return ob.mitigation_level


def update_fvg_fill_status(
    fvgs: List[FVG], df: pd.DataFrame, max_fill: float = 0.5
) -> Tuple[List[FVG], MitigationStatus]:
    """
    Update FVG fill status based on price action.

    An FVG is filled when price returns to close the gap:
    - 0%: Gap completely open (fresh)
    - 50%: Gap partially filled
    - 100%: Gap completely closed

    Args:
        fvgs: List of FVGs to update
        df: Recent OHLCV data to check for fills
        max_fill: Maximum fill level to keep (0.5 = 50%)

    Returns:
        Tuple of (filtered fresh FVGs, fill status)
    """
    if not fvgs:
        return [], MitigationStatus(0, 0, 0, 0)

    fresh = []
    partially_filled = 0
    fully_filled = 0

    for fvg in fvgs:
        new_fill = _calculate_fvg_fill(fvg, df)

        # Update the FVG with new fill level
        updated_fvg = replace(fvg, overlap_with_price=new_fill)

        if new_fill >= 1.0:
            fully_filled += 1
        elif new_fill > max_fill:
            partially_filled += 1
        else:
            fresh.append(updated_fvg)

    status = MitigationStatus(
        original_count=len(fvgs),
        fresh_count=len(fresh),
        partially_mitigated_count=partially_filled,
        fully_mitigated_count=fully_filled,
    )

    logger.debug(f"FVG Fill: {len(fresh)}/{len(fvgs)} fresh (max_fill={max_fill})")

    return fresh, status


def _calculate_fvg_fill(fvg: FVG, df: pd.DataFrame) -> float:
    """
    Calculate how much an FVG has been filled by price action.

    Returns value from 0.0 (open) to 1.0 (fully filled).
    """
    if df.empty:
        return fvg.overlap_with_price

    after_formation = candles_after_formation(df, fvg.timestamp)

    if after_formation.empty:
        return fvg.overlap_with_price

    gap_size = fvg.top - fvg.bottom
    if gap_size <= 0:
        return 1.0

    if fvg.direction == "bullish":
        # Bullish FVG: gap up, filled when price comes back down
        lowest_low = after_formation["low"].min()
        if lowest_low <= fvg.bottom:
            return 1.0  # Fully filled
        elif lowest_low < fvg.top:
            # Partial fill
            fill_amount = fvg.top - lowest_low
            return min(1.0, fill_amount / gap_size)
    else:
        # Bearish FVG: gap down, filled when price comes back up
        highest_high = after_formation["high"].max()
        if highest_high >= fvg.top:
            return 1.0  # Fully filled
        elif highest_high > fvg.bottom:
            # Partial fill
            fill_amount = highest_high - fvg.bottom
            return min(1.0, fill_amount / gap_size)

    return fvg.overlap_with_price


def filter_fresh_zones(
    order_blocks: List[OrderBlock],
    fvgs: List[FVG],
    df: pd.DataFrame,
    ob_max_mitigation: float = 0.5,
    fvg_max_fill: float = 0.5,
) -> Tuple[List[OrderBlock], List[FVG]]:
    """
    Convenience function to filter both OBs and FVGs for fresh zones only.

    Args:
        order_blocks: List of OrderBlocks
        fvgs: List of FVGs
        df: Recent OHLCV data
        ob_max_mitigation: Max OB mitigation to keep
        fvg_max_fill: Max FVG fill to keep

    Returns:
        Tuple of (fresh OBs, fresh FVGs)
    """
    fresh_obs, _ = update_ob_mitigation(order_blocks, df, ob_max_mitigation)
    fresh_fvgs, _ = update_fvg_fill_status(fvgs, df, fvg_max_fill)

    return fresh_obs, fresh_fvgs
