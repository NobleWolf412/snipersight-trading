"""
Trade Planner Service Module

Generates complete, actionable trade plans based on confluence analysis.
Logic is delegated to specialized engines:
- Entry Engine: Entry zones, validation, archetype mapping
- Risk Engine: Stop loss, targets, leverage adjustments
- Regime Engine: Market regime analysis (volatility, trend)

Following the "No-Null, Actionable Outputs" principle.
"""

from typing import Optional, List, Literal, cast
from datetime import datetime
import pandas as pd
import numpy as np
from loguru import logger

from backend.shared.models.planner import TradePlan, EntryZone, StopLoss, Target
from backend.shared.models.data import MultiTimeframeData
from backend.shared.models.smc import SMCSnapshot
from backend.shared.models.indicators import IndicatorSet
from backend.shared.models.scoring import ConfluenceBreakdown
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.planner_config import PlannerConfig
from backend.bot.telemetry.logger import get_telemetry_logger
from backend.bot.telemetry.events import create_signal_rejected_event

# Engine Imports
from backend.strategy.planner.entry_engine import _calculate_entry_zone, _map_setup_to_archetype
from backend.strategy.planner.risk_engine import (
    _calculate_stop_loss, 
    _calculate_targets, 
    _derive_trade_type, 
    _adjust_stop_for_leverage, 
    _adjust_targets_for_leverage
)
from backend.strategy.planner.regime_engine import get_atr_regime

# Re-export SetupArchetype if needed by consumers, though ideally they import from models?
# For now, defining local type alias to match previous API surface if it was used
SetupArchetype = Literal[
    "TREND_OB_PULLBACK",
    "RANGE_REVERSION",
    "SWEEP_REVERSAL",
    "BREAKOUT_RETEST",
]

# === MODE TO TRADE LABEL MAPPING ===
# Maps scanner mode names AND profile names to trader-friendly trade labels
# Modes: overwatch, stealth, surgical, strike
MODE_TO_TRADE_LABEL = {
    # Overwatch = Position Trade (Days-Weeks, HTF macro positions)
    "overwatch": "Position Trade",
    "macro_surveillance": "Position Trade",
    
    # Stealth = Swing Trade (Hours-Days, balanced multi-TF)
    "stealth": "Swing Trade", 
    "stealth_balanced": "Swing Trade",
    
    # Surgical = Day Trade (Minutes-Hours, precision intraday)
    "surgical": "Day Trade",
    "precision": "Day Trade",
    
    # Strike = Scalp Trade (Minutes, aggressive momentum plays)
    "strike": "Scalp Trade",
    "intraday_aggressive": "Scalp Trade",
    
    # Fallback
    "balanced": "Swing Trade",
}

def get_trade_label_for_mode(mode: str) -> str:
    """Get trader-friendly trade label based on scanner mode or profile."""
    mode_lower = (mode or "stealth").lower()
    return MODE_TO_TRADE_LABEL.get(mode_lower, "Swing Trade")  # Default to Swing


def generate_trade_plan(
    symbol: str,
    direction: str,
    setup_type: str,
    smc_snapshot: SMCSnapshot,
    indicators: IndicatorSet,
    confluence_breakdown: ConfluenceBreakdown,
    config: ScanConfig,
    current_price: float,
    missing_critical_timeframes: Optional[List[str]] = None,
    multi_tf_data: Optional[MultiTimeframeData] = None,
    expected_trade_type: Optional[str] = None
) -> TradePlan:
    """
    Generate a complete, actionable trade plan.
    
    Args:
        symbol: Trading pair symbol
        direction: "bullish" or "bearish"
        setup_type: Type of setup (e.g., "OB_FVG_BOS", "Liquidity_Sweep")
        smc_snapshot: SMC patterns detected
        indicators: Technical indicators
        confluence_breakdown: Confluence score breakdown
        config: Scan configuration
        current_price: Current market price
        missing_critical_timeframes: List of critical TFs that failed to load
        multi_tf_data: Optional multi-timeframe candle data for swing-based stops
        expected_trade_type: Optional trade type hint (swing, scalp, intraday)
        
    Returns:
        TradePlan: Complete trade plan with entries, stops, targets
        
    Raises:
        ValueError: If unable to generate valid plan (insufficient structure)
    """
    if missing_critical_timeframes is None:
        missing_critical_timeframes = []
    
    # Type check: indicators should be IndicatorSet, not IndicatorSnapshot
    if not hasattr(indicators, 'by_timeframe'):
        raise ValueError(
            f"Expected IndicatorSet with 'by_timeframe' attribute, "
            f"got {type(indicators).__name__}. Ensure orchestrator passes "
            f"context.multi_tf_indicators (IndicatorSet), not a single IndicatorSnapshot."
        )
    
    # Get primary timeframe indicators
    if not indicators.by_timeframe:
        raise ValueError("No indicators available for trade planning")
    
    primary_tf = getattr(config, "primary_planning_timeframe", None)
    
    # Intelligent fallback if explicit config missing or not valid
    if not primary_tf or (indicators.by_timeframe and primary_tf not in indicators.by_timeframe):
        # normalize provided config
        if primary_tf and primary_tf.lower() in indicators.by_timeframe:
            primary_tf = primary_tf.lower()
        else:
            # Search for best available anchor
            found = False
            for tf_candidate in ['15m', '1h', '5m', '4h', '1d']:
                if tf_candidate in indicators.by_timeframe:
                    primary_tf = tf_candidate
                    found = True
                    break
            
            if not found and indicators.by_timeframe:
                # Last resort: first available key
                primary_tf = list(indicators.by_timeframe.keys())[0]
                logger.warning(f"Primary planning TF fallback to {primary_tf}")
    
    primary_indicators = indicators.by_timeframe[primary_tf]
    
    # Determine Planner Configuration
    if getattr(config, 'planner', None):
        planner_cfg = config.planner
    elif expected_trade_type:
        planner_cfg = PlannerConfig.defaults_for_mode(expected_trade_type)
        logger.debug(f"Using PlannerConfig for expected_trade_type={expected_trade_type}")
    else:
        planner_cfg = PlannerConfig.defaults_for_mode("intraday")
    
    # Apply overlays
    overrides = getattr(config, 'overrides', None) or {}
    if overrides:
        for key, value in overrides.items():
            if hasattr(planner_cfg, key):
                setattr(planner_cfg, key, value)
    
    telemetry = get_telemetry_logger()
    run_id = datetime.utcnow().strftime("run-%Y%m%d")

    if primary_indicators.atr is None or primary_indicators.atr <= 0:
        telemetry.log_event(create_signal_rejected_event(
            run_id=run_id,
            symbol=symbol,
            reason="atr_invalid",
            diagnostics={"atr": primary_indicators.atr}
        ))
        raise ValueError("ATR required for trade planning and must be positive")
    atr = primary_indicators.atr

    leverage = max(1, int(getattr(config, 'leverage', 1) or 1))
    
    is_bullish = (direction.lower() == "bullish")
    
    # Map raw setup string to archetype
    # Now imported from entry_engine
    archetype = _map_setup_to_archetype(setup_type)
    
    logger.info(f"Generating plan for {symbol} ({direction}) | ATR={atr:.2f} | Setup={setup_type} ({archetype})")
    
    # === 1. Calculate Entry Zone (Delegate to Entry Engine) ===
    entry_zone, used_structure_entry = _calculate_entry_zone(
        is_bullish=is_bullish,
        smc_snapshot=smc_snapshot,
        current_price=current_price,
        atr=atr,
        primary_tf=primary_tf,
        setup_archetype=archetype,
        config=config,
        planner_cfg=planner_cfg,
        confluence_breakdown=confluence_breakdown,
        multi_tf_data=multi_tf_data,
        indicators=indicators  # Pass full set for regime detection
    )
    
    # === 2. Calculate Stop Loss (Delegate to Risk Engine) ===
    try:
        stop_loss, used_structure_stop = _calculate_stop_loss(
            is_bullish=is_bullish,
            entry_zone=entry_zone,
            smc_snapshot=smc_snapshot,
            atr=atr,
            primary_tf=primary_tf,
            setup_archetype=archetype,
            config=config,
            planner_cfg=planner_cfg,
            multi_tf_data=multi_tf_data,
            current_price=current_price,
            indicators_by_tf=indicators.by_timeframe  # Pass dict for structure TF lookup
        )
    except ValueError as e:
        logger.warning(f"Stop loss calculation failed: {e}")
        telemetry.log_event(create_signal_rejected_event(
            run_id=run_id,
            symbol=symbol,
            reason="stop_loss_calc_failed",
            diagnostics={"error": str(e)}
        ))
        raise

    # === 3. Leverage Adjustment for Stop (Delegate to Risk Engine) ===
    # Check liquidation risk
    adjusted_stop_level, was_adjusted, adj_meta = _adjust_stop_for_leverage(
        stop_level=stop_loss.level,
        near_entry=entry_zone.near_entry,
        leverage=leverage,
        is_bullish=is_bullish
    )
    
    if was_adjusted:
        logger.warning(f"Stop loss adjusted for {leverage}x leverage: {stop_loss.level} -> {adjusted_stop_level}")
        stop_loss = StopLoss(
            level=adjusted_stop_level,
            distance_atr=abs(entry_zone.far_entry - adjusted_stop_level) / atr,
            rationale=f"{stop_loss.rationale} [Liquidation Safety Adjusted]"
        )
        # We might want to store the reason in metadata later
    
    # === 4. Calculate Targets (Delegate to Risk Engine) ===
    # Get regime label for target adjustment
    regime_label = get_atr_regime(indicators, current_price)
    
    targets = _calculate_targets(
        is_bullish=is_bullish,
        entry_zone=entry_zone,
        stop_loss=stop_loss,
        smc_snapshot=smc_snapshot,
        atr=atr,
        config=config,
        planner_cfg=planner_cfg,
        setup_archetype=archetype,
        regime_label=regime_label,
        rr_scale=1.0,
        confluence_breakdown=confluence_breakdown,
        multi_tf_data=multi_tf_data,
        indicators=indicators
    )
    
    # === 5. Leverage Adjustment for Targets (Delegate to Risk Engine) ===
    targets, target_adj_meta = _adjust_targets_for_leverage(
        targets=targets,
        leverage=leverage,
        entry_price=(entry_zone.near_entry + entry_zone.far_entry) / 2,
        is_bullish=is_bullish
    )
    
    # === 6. Determine Trade Type (Delegate to Risk Engine) ===
    # Collect structure TFs used
    # Fix: explicitly handle list creation to avoid type errors
    structure_tfs = []
    if entry_zone.entry_tf_used and entry_zone.entry_tf_used != "N/A":
        structure_tfs.append(entry_zone.entry_tf_used)
    if stop_loss.structure_tf_used and stop_loss.structure_tf_used != "N/A":
        structure_tfs.append(stop_loss.structure_tf_used)
    
    structure_tfs_tuple = tuple(set(structure_tfs))
    
    tp1_move_pct = 0.0
    if targets:
        tp1_dist = abs(targets[0].level - ((entry_zone.near_entry + entry_zone.far_entry)/2))
        tp1_move_pct = (tp1_dist / current_price) * 100
        
    trade_type = _derive_trade_type(
        target_move_pct=tp1_move_pct,
        stop_distance_atr=stop_loss.distance_atr,
        structure_timeframes=structure_tfs_tuple,
        primary_tf=primary_tf
    )
    
    # === 7. Construct Final Trade Plan ===
    plan = TradePlan(
        symbol=symbol,
        direction=direction,
        timestamp=datetime.utcnow(),
        entry_zone=entry_zone,
        stop_loss=stop_loss,
        targets=targets,
        risk_reward_ratio=targets[-1].rr_ratio if targets else 0.0,
        setup_type=get_trade_label_for_mode(config.profile),  # Use mode-based trade label
        timeframe=primary_tf,
        status="PENDING",
        trade_type=trade_type
    )
    
    # Attach metadata
    plan.metadata = {
        "archetype": archetype,
        "atr_regime": regime_label,
        "leverage": leverage,
        "leverage_stop_adjustment": adj_meta if was_adjusted else None,
        "target_adjustment": target_adj_meta,
        "structure_tfs_used": list(structure_tfs_tuple),
        "missing_critical_tfs": missing_critical_timeframes,
        # NEW: R:R best/worst case for transparent risk assessment
        # Best case: Fill at near entry (better R:R), Worst case: Fill at far entry
        "rr_best": None,
        "rr_worst": None,
        # NEW: Pullback probability from entry zone
        "pullback_probability": getattr(entry_zone, 'pullback_probability', None),
        # NEW: Entry structure details for frontend display
        "entry_structure": {
            "timeframe": getattr(entry_zone, 'entry_tf_used', None) or primary_tf,
            "zone_high": entry_zone.far_entry if is_bullish else entry_zone.near_entry,
            "zone_low": entry_zone.near_entry if is_bullish else entry_zone.far_entry,
            "type": "OB" if "order block" in (entry_zone.rationale or "").lower() else "FVG" if "fvg" in (entry_zone.rationale or "").lower() else "Zone"
        }
    }
    
    # Calculate R:R best/worst after targets are finalized
    if targets:
        tp1_level = targets[0].level
        near_risk = abs(entry_zone.near_entry - stop_loss.level)
        far_risk = abs(entry_zone.far_entry - stop_loss.level)
        
        if near_risk > 0 and far_risk > 0:
            near_reward = abs(tp1_level - entry_zone.near_entry)
            far_reward = abs(tp1_level - entry_zone.far_entry)
            plan.metadata["rr_best"] = round(near_reward / near_risk, 2)
            plan.metadata["rr_worst"] = round(far_reward / far_risk, 2)
    
    return plan
