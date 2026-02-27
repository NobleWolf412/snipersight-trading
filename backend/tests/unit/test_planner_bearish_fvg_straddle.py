"""Test: Bearish FVG wide straddling current price triggers ATR fallback.

Scenario: FVG spans across the current price; planner should not produce a zone that
straddles price. It must fallback to ATR-based zone strictly above current price
with near > far ordering.
"""

from datetime import datetime

from backend.shared.config.defaults import ScanConfig
from backend.shared.config.planner_config import PlannerConfig
from backend.shared.models.smc import FVG, SMCSnapshot
from backend.strategy.planner.planner_service import _calculate_entry_zone


def test_bearish_fvg_straddling_price_triggers_fallback():
    planner_cfg = PlannerConfig.defaults_for_mode("intraday")
    config = ScanConfig(profile="intraday")
    current_price = 100.0
    atr = 2.0

    # Create a very wide bearish FVG that touches and spans below current price
    # Example: bottom=99.0 (below price), top=106.0 (above price)
    fvg_straddle = FVG(
        direction="bearish",
        top=106.0,
        bottom=99.0,
        timestamp=datetime.utcnow(),
        timeframe="15m",
        size=7.0,
        overlap_with_price=1.0,  # fully overlapped at current price
    )

    smc_snapshot = SMCSnapshot(
        order_blocks=[], fvgs=[fvg_straddle], structural_breaks=[], liquidity_sweeps=[]
    )

    entry_zone, used_structure = _calculate_entry_zone(
        is_bullish=False,
        smc_snapshot=smc_snapshot,
        current_price=current_price,
        atr=atr,
        primary_tf="15m",
        setup_archetype="TREND_OB_PULLBACK",
        config=config,
        planner_cfg=planner_cfg,
        confluence_breakdown=None,
        multi_tf_data=None,
    )

    # Since the gap straddles price, sanity should fallback to ATR-based zone
    # For intraday + atr=2 and explosive regime (2.0%), offsets: near=+1.5*atr=+3.0, far=+0.5*atr=+1.0
    # near ≈ 104.5, far ≈ 101.5
    assert used_structure is False, "Should fallback to ATR (not use FVG structure)"
    assert entry_zone.near_entry > entry_zone.far_entry, "Bearish ordering near > far must hold"
    assert (
        entry_zone.near_entry > current_price and entry_zone.far_entry > current_price
    ), "Both bearish entries must be strictly above current price after fallback"

    print(
        f"✓ Bearish straddle fallback: near={entry_zone.near_entry:.2f} > far={entry_zone.far_entry:.2f} > price={current_price:.2f}"
    )
