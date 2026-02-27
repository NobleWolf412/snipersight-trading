"""
Test bearish FVG entry zone calculation - simplified version.

Critical test: validates bearish FVG entries have near_entry > far_entry
"""

from datetime import datetime
from backend.strategy.planner.planner_service import _calculate_entry_zone
from backend.shared.models.smc import SMCSnapshot, FVG
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.planner_config import PlannerConfig


def test_bearish_fvg_entry_ordering():
    """CRITICAL: Bearish FVGs must have near_entry > far_entry (near is closer to price, higher value)."""

    planner_cfg = PlannerConfig.defaults_for_mode("intraday")
    config = ScanConfig(profile="intraday")

    # Current price: 100.0
    # Create bearish FVG above current price (103-105)
    current_price = 100.0
    fvg = FVG(
        direction="bearish",
        top=105.0,
        bottom=103.0,
        timestamp=datetime.utcnow(),
        timeframe="15m",
        size=2.0,  # Must match top - bottom
        overlap_with_price=0.0,  # Fresh, unfilled (0% overlap)
    )

    smc_snapshot = SMCSnapshot(
        order_blocks=[], fvgs=[fvg], structural_breaks=[], liquidity_sweeps=[]
    )

    # Calculate entry zone for bearish setup
    entry_zone, used_structure = _calculate_entry_zone(
        is_bullish=False,
        smc_snapshot=smc_snapshot,
        current_price=current_price,
        atr=2.0,
        primary_tf="15m",
        setup_archetype="TREND_OB_PULLBACK",
        config=config,
        planner_cfg=planner_cfg,
        confluence_breakdown=None,
        multi_tf_data=None,
    )

    # CRITICAL ASSERTION: For shorts, near_entry must be > far_entry
    assert (
        entry_zone.near_entry > entry_zone.far_entry
    ), f"Bearish FVG FAILED ordering: near_entry={entry_zone.near_entry:.2f} should be > far_entry={entry_zone.far_entry:.2f}"

    # Near entry should be near FVG top (just below it with offset)
    assert abs(entry_zone.near_entry - fvg.top) < 1.0, "Near entry should be close to FVG top"

    # Far entry should be near FVG bottom (just above it with offset)
    assert abs(entry_zone.far_entry - fvg.bottom) < 1.0, "Far entry should be close to FVG bottom"

    # Should use structure
    assert used_structure, "Should use FVG structure for entry"

    print(
        f"✓ Bearish FVG ordering correct: near={entry_zone.near_entry:.2f} > far={entry_zone.far_entry:.2f}"
    )


def test_bearish_fvg_overlap_filtering():
    """Bearish FVGs with overlap >= threshold should be filtered out."""

    planner_cfg = PlannerConfig.defaults_for_mode("intraday")
    config = ScanConfig(profile="intraday")
    current_price = 100.0

    # Create one fresh and one heavily filled FVG
    fvg_fresh = FVG(
        direction="bearish",
        top=105.0,
        bottom=103.0,
        timestamp=datetime.utcnow(),
        timeframe="15m",
        size=2.0,  # Must match top - bottom
        overlap_with_price=0.2,  # 20% filled - should pass filter (< 50%)
    )

    fvg_filled = FVG(
        direction="bearish",
        top=107.0,
        bottom=105.5,
        timestamp=datetime.utcnow(),
        timeframe="15m",
        size=1.5,  # Must match top - bottom
        overlap_with_price=0.6,  # 60% filled - should be filtered out (>= 50%)
    )

    smc_snapshot = SMCSnapshot(
        order_blocks=[], fvgs=[fvg_fresh, fvg_filled], structural_breaks=[], liquidity_sweeps=[]
    )

    entry_zone, used_structure = _calculate_entry_zone(
        is_bullish=False,
        smc_snapshot=smc_snapshot,
        current_price=current_price,
        atr=2.0,
        primary_tf="15m",
        setup_archetype="TREND_OB_PULLBACK",
        config=config,
        planner_cfg=planner_cfg,
        confluence_breakdown=None,
        multi_tf_data=None,
    )

    # Should use fresh FVG (near 105.0), not filled one (near 107.0)
    assert entry_zone.near_entry < 106.0, "Should use fresh FVG, not filled one"
    assert used_structure, "Should use FVG structure"

    print(
        f"✓ Overlap filtering works: used fresh FVG at {entry_zone.near_entry:.2f}, ignored filled one at 107"
    )


def test_bearish_atr_fallback_ordering():
    """When no valid bearish structure exists, ATR fallback should still maintain near > far ordering."""

    planner_cfg = PlannerConfig.defaults_for_mode("intraday")
    config = ScanConfig(profile="intraday")
    current_price = 100.0

    # No FVGs or OBs
    smc_snapshot = SMCSnapshot(order_blocks=[], fvgs=[], structural_breaks=[], liquidity_sweeps=[])

    entry_zone, used_structure = _calculate_entry_zone(
        is_bullish=False,
        smc_snapshot=smc_snapshot,
        current_price=current_price,
        atr=2.0,
        primary_tf="15m",
        setup_archetype="TREND_OB_PULLBACK",
        config=config,
        planner_cfg=planner_cfg,
        confluence_breakdown=None,
        multi_tf_data=None,
    )

    # Even for ATR fallback, must maintain near > far ordering for shorts
    assert (
        entry_zone.near_entry > entry_zone.far_entry
    ), f"ATR fallback FAILED bearish ordering: near={entry_zone.near_entry:.2f} should be > far={entry_zone.far_entry:.2f}"

    # Should indicate no structure used
    assert not used_structure, "Should indicate no structure used"

    # Bearish entry should be above current price
    assert entry_zone.near_entry > current_price, "Bearish entry should be above current price"
    assert "ATR" in entry_zone.rationale, "Rationale should mention ATR fallback"

    print(
        f"✓ ATR fallback maintains ordering: near={entry_zone.near_entry:.2f} > far={entry_zone.far_entry:.2f}"
    )


if __name__ == "__main__":
    print("Running bearish FVG tests...")
    test_bearish_fvg_entry_ordering()
    test_bearish_fvg_overlap_filtering()
    test_bearish_atr_fallback_ordering()
    print("\n✅ All bearish FVG tests passed!")
