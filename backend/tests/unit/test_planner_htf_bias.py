from datetime import datetime, timedelta
from typing import Literal
from backend.strategy.planner.planner_service import _calculate_entry_zone
from backend.shared.models.smc import SMCSnapshot, OrderBlock, FVG
from backend.shared.config.defaults import ScanConfig
from backend.shared.models.scoring import ConfluenceBreakdown, ConfluenceFactor
from backend.shared.config.planner_config import PlannerConfig


def _dummy_breakdown(
    htf_type: Literal["support", "resistance"], 
    htf_prox_atr: float
) -> ConfluenceBreakdown:
    # Minimal valid breakdown with single factor weight 1.0
    factor = ConfluenceFactor(name="Dummy", score=50.0, weight=1.0, rationale="test")
    return ConfluenceBreakdown(
        total_score=50.0,
        factors=[factor],
        synergy_bonus=0.0,
        conflict_penalty=0.0,
        regime="range",
        htf_aligned=False,
        btc_impulse_gate=True,
        htf_proximity_atr=htf_prox_atr,
        htf_proximity_pct=1.0,
        nearest_htf_level_timeframe="1d",
        nearest_htf_level_type=htf_type,  # 'support' or 'resistance'
    )


def test_bullish_entry_biases_toward_support_level_when_within_threshold():
    # OB below current price for bullish entry
    ob = OrderBlock(
        timeframe="4H",
        direction="bullish",
        high=98.0,
        low=96.0,
        timestamp=datetime.utcnow() - timedelta(days=1),
        displacement_strength=50.0,
        mitigation_level=0.1,
        freshness_score=80.0,
    )
    smc = SMCSnapshot(order_blocks=[ob], fvgs=[], structural_breaks=[], liquidity_sweeps=[])

    current_price = 100.0
    atr = 2.0
    cfg = ScanConfig()
    cfg.primary_planning_timeframe = "4H"
    cfg.htf_bias_entry = True
    cfg.htf_proximity_atr_max = 1.0
    cfg.htf_bias_entry_offset_atr = 0.05  # 0.05*ATR = 0.1

    # With support and proximity <= 1 ATR, offsets should use 0.05*ATR instead of 0.1*ATR
    breakdown = _dummy_breakdown("support", 0.5)

    entry_zone, used_structure = _calculate_entry_zone(
        is_bullish=True,
        smc_snapshot=smc,
        current_price=current_price,
        atr=atr,
        primary_tf="4H",
        setup_archetype="TREND_OB_PULLBACK",
        config=cfg,
        planner_cfg=PlannerConfig.defaults_for_mode("intraday"),
        confluence_breakdown=breakdown,
    )

    assert used_structure is True
    expected_near = ob.high - (cfg.htf_bias_entry_offset_atr * atr)
    expected_far = ob.low + (cfg.htf_bias_entry_offset_atr * atr)
    # Allow small differences due to regime multipliers and gradient scaling factors
    assert abs(entry_zone.near_entry - expected_near) < 0.2
    assert abs(entry_zone.far_entry - expected_far) < 0.2


def test_bearish_entry_biases_toward_resistance_level_when_within_threshold():
    # Bearish OB above current price
    ob = OrderBlock(
        timeframe="4H",
        direction="bearish",
        high=104.0,
        low=102.0,
        timestamp=datetime.utcnow() - timedelta(days=1),
        displacement_strength=50.0,
        mitigation_level=0.1,
        freshness_score=80.0,
    )
    smc = SMCSnapshot(order_blocks=[ob], fvgs=[], structural_breaks=[], liquidity_sweeps=[])

    current_price = 100.0
    atr = 2.0
    cfg = ScanConfig()
    cfg.primary_planning_timeframe = "4H"
    cfg.htf_bias_entry = True
    cfg.htf_proximity_atr_max = 1.0
    cfg.htf_bias_entry_offset_atr = 0.05

    breakdown = _dummy_breakdown("resistance", 0.5)

    entry_zone, used_structure = _calculate_entry_zone(
        is_bullish=False,
        smc_snapshot=smc,
        current_price=current_price,
        atr=atr,
        primary_tf="4H",
        setup_archetype="TREND_OB_PULLBACK",
        config=cfg,
        planner_cfg=PlannerConfig.defaults_for_mode("intraday"),
        confluence_breakdown=breakdown,
    )

    assert used_structure is True
    expected_near = ob.low + (cfg.htf_bias_entry_offset_atr * atr)
    expected_far = ob.high - (cfg.htf_bias_entry_offset_atr * atr)
    assert abs(entry_zone.near_entry - expected_near) < 0.2
    assert abs(entry_zone.far_entry - expected_far) < 0.2
