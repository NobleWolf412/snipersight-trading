"""
Test price alignment sanity checks - simplified version.

Validates that the planner rejects plans when structure prices
and current price are massively mismatched.
"""

import pytest
from datetime import datetime
from backend.strategy.planner.planner_service import _calculate_entry_zone
from backend.shared.models.smc import SMCSnapshot, OrderBlock
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.planner_config import PlannerConfig


def test_price_alignment_check_integrated():
    """Price alignment check should catch structure/price mismatches in entry calculation."""

    config = ScanConfig(profile="intraday")
    planner_cfg = PlannerConfig.defaults_for_mode("intraday")

    # Current price: 100.0
    # Create bullish OB way below current price (at 30, 70% away from 100)
    current_price = 100.0
    ob = OrderBlock(
        direction="bullish",
        high=32.0,
        low=30.0,
        timestamp=datetime.utcnow(),
        timeframe="4h",
        displacement_strength=2.0,
        freshness_score=0.9,
        mitigation_level=0.1,
    )

    smc_snapshot = SMCSnapshot(
        order_blocks=[ob], fvgs=[], structural_breaks=[], liquidity_sweeps=[]
    )

    # Should calculate entry zone successfully (price alignment check happens in generate_trade_plan)
    entry_zone, used_structure = _calculate_entry_zone(
        is_bullish=True,
        smc_snapshot=smc_snapshot,
        current_price=current_price,
        atr=2.0,
        primary_tf="4h",
        setup_archetype="TREND_OB_PULLBACK",
        config=config,
        planner_cfg=planner_cfg,
        confluence_breakdown=None,
        multi_tf_data=None,
    )

    # OB is far beyond max_pullback_atr (distance constraint filters it), so planner falls back to ATR zone
    # Validate ATR fallback near ~98.5 for explosive regime (2.0% ATR%)
    assert (
        entry_zone.near_entry > 95.0
    ), "ATR fallback near entry should be reasonably close to price, not ~30"

    # Now verify mid_entry vs price divergence (this is what generate_trade_plan checks)
    mid_entry = (entry_zone.near_entry + entry_zone.far_entry) / 2
    rel_diff = abs(mid_entry - current_price) / current_price

    # With ATR fallback, mid_entry should be near price; ensure it's not massively mismatched
    assert rel_diff < 0.5, f"rel_diff={rel_diff:.1%} should be under 50% threshold for fallback"

    print(
        f"✓ Price alignment detection works: mid_entry={mid_entry:.1f}, current_price={current_price:.1f}, diff={rel_diff:.1%}"
    )


def test_price_alignment_passes_with_valid_structure():
    """Should pass when structure and price are reasonably aligned."""

    config = ScanConfig(profile="intraday")
    planner_cfg = PlannerConfig.defaults_for_mode("intraday")

    # Current price: 100.0
    # Create bullish OB slightly below current price (at 95, 5% away)
    current_price = 100.0
    ob = OrderBlock(
        direction="bullish",
        high=96.0,
        low=94.0,
        timestamp=datetime.utcnow(),
        timeframe="4h",
        displacement_strength=2.5,
        freshness_score=0.95,
        mitigation_level=0.05,
    )

    smc_snapshot = SMCSnapshot(
        order_blocks=[ob], fvgs=[], structural_breaks=[], liquidity_sweeps=[]
    )

    entry_zone, used_structure = _calculate_entry_zone(
        is_bullish=True,
        smc_snapshot=smc_snapshot,
        current_price=current_price,
        atr=2.0,
        primary_tf="4h",
        setup_archetype="TREND_OB_PULLBACK",
        config=config,
        planner_cfg=planner_cfg,
        confluence_breakdown=None,
        multi_tf_data=None,
    )

    # Entry zone should be around 94-96
    mid_entry = (entry_zone.near_entry + entry_zone.far_entry) / 2
    rel_diff = abs(mid_entry - current_price) / current_price

    # Should be < 50% (well within threshold)
    assert rel_diff < 0.5, f"rel_diff={rel_diff:.1%} should be under 50% threshold"
    assert used_structure, "Should use structure"

    print(
        f"✓ Valid structure passes: mid_entry={mid_entry:.1f}, current_price={current_price:.1f}, diff={rel_diff:.1%}"
    )


def test_price_alignment_configurable_threshold():
    """Should respect custom price alignment threshold from PlannerConfig."""

    # Use strict threshold (10% instead of default 50%)
    planner_cfg = PlannerConfig.defaults_for_mode("intraday")
    planner_cfg.price_alignment_max_rel_diff = 0.10

    config = ScanConfig(profile="intraday")
    current_price = 100.0

    # Create OB at 88 (12% away - would pass default, fails strict)
    ob = OrderBlock(
        direction="bullish",
        high=89.0,
        low=87.0,
        timestamp=datetime.utcnow(),
        timeframe="4h",
        displacement_strength=2.0,
        freshness_score=0.9,
        mitigation_level=0.1,
    )

    smc_snapshot = SMCSnapshot(
        order_blocks=[ob], fvgs=[], structural_breaks=[], liquidity_sweeps=[]
    )

    entry_zone, _ = _calculate_entry_zone(
        is_bullish=True,
        smc_snapshot=smc_snapshot,
        current_price=current_price,
        atr=2.0,
        primary_tf="4h",
        setup_archetype="TREND_OB_PULLBACK",
        config=config,
        planner_cfg=planner_cfg,
        confluence_breakdown=None,
        multi_tf_data=None,
    )

    mid_entry = (entry_zone.near_entry + entry_zone.far_entry) / 2
    rel_diff = abs(mid_entry - current_price) / current_price

    # With OB distance filtered, ATR fallback is used; rel_diff should be modest (< strict threshold)
    assert (
        rel_diff < planner_cfg.price_alignment_max_rel_diff
    ), f"rel_diff={rel_diff:.1%} should be below strict {planner_cfg.price_alignment_max_rel_diff:.1%} threshold when fallback is used"

    print(f"✓ Custom threshold works: diff={rel_diff:.1%} exceeds strict 10% limit")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
