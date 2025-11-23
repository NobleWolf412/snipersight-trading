"""
Trade Planner Service Module

Generates complete, actionable trade plans based on confluence analysis.

Following the "No-Null, Actionable Outputs" principle:
- Every plan must have dual entries (near/far)
- Structure-based stop loss (never arbitrary)
- Tiered targets with clear rationale
- Minimum R:R enforcement
- Complete rationale for every decision
"""

from typing import Optional, List
from datetime import datetime
import pandas as pd
import numpy as np
from loguru import logger

from backend.shared.models.planner import TradePlan, EntryZone, StopLoss, Target
from backend.shared.models.smc import SMCSnapshot, OrderBlock, FVG
from backend.shared.models.indicators import IndicatorSet
from backend.shared.models.scoring import ConfluenceBreakdown
from backend.shared.config.defaults import ScanConfig


def generate_trade_plan(
    symbol: str,
    direction: str,
    setup_type: str,
    smc_snapshot: SMCSnapshot,
    indicators: IndicatorSet,
    confluence_breakdown: ConfluenceBreakdown,
    config: ScanConfig,
    current_price: float
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
        
    Returns:
        TradePlan: Complete trade plan with entries, stops, targets
        
    Raises:
        ValueError: If unable to generate valid plan (insufficient structure)
    """
    # Get primary timeframe indicators
    if not indicators.by_timeframe:
        raise ValueError("No indicators available for trade planning")
    
    primary_tf = list(indicators.by_timeframe.keys())[0]
    primary_indicators = indicators.by_timeframe[primary_tf]
    
    if primary_indicators.atr is None:
        raise ValueError("ATR required for trade planning")
    
    atr = primary_indicators.atr
    
    # --- Determine Entry Zone ---
    
    entry_zone = _calculate_entry_zone(
        direction=direction,
        smc_snapshot=smc_snapshot,
        current_price=current_price,
        atr=atr
    )
    
    # --- Calculate Stop Loss ---
    
    stop_loss = _calculate_stop_loss(
        direction=direction,
        entry_zone=entry_zone,
        smc_snapshot=smc_snapshot,
        atr=atr
    )
    
    # --- Calculate Targets ---
    
    targets = _calculate_targets(
        direction=direction,
        entry_zone=entry_zone,
        stop_loss=stop_loss,
        smc_snapshot=smc_snapshot,
        atr=atr,
        config=config
    )
    
    # --- Calculate Risk:Reward ---
    
    avg_entry = (entry_zone.near_entry + entry_zone.far_entry) / 2
    risk = abs(avg_entry - stop_loss.level)
    
    if risk == 0:
        raise ValueError("Invalid stop loss: zero risk distance")
    
    # Use first target for R:R calculation
    reward = abs(targets[0].level - avg_entry)
    risk_reward = reward / risk
    
    # Enforce minimum R:R
    if risk_reward < config.min_rr_ratio:
        raise ValueError(f"Risk:Reward {risk_reward:.2f} below minimum {config.min_rr_ratio}")
    
    # --- Generate Rationale ---
    
    rationale = _generate_rationale(
        setup_type=setup_type,
        confluence_breakdown=confluence_breakdown,
        smc_snapshot=smc_snapshot,
        entry_zone=entry_zone,
        stop_loss=stop_loss,
        targets=targets,
        risk_reward=risk_reward
    )
    
    # --- Build Trade Plan ---
    
    trade_plan = TradePlan(
        symbol=symbol,
        direction=direction,
        setup_type=setup_type,
        entry_zone=entry_zone,
        stop_loss=stop_loss,
        targets=targets,
        risk_reward=risk_reward,
        confidence_score=confluence_breakdown.total_score,
        confluence_breakdown=confluence_breakdown,
        rationale=rationale,
        metadata={
            "atr": atr,
            "current_price": current_price,
            "timestamp": datetime.utcnow().isoformat()
        }
    )
    
    return trade_plan


def _calculate_entry_zone(
    direction: str,
    smc_snapshot: SMCSnapshot,
    current_price: float,
    atr: float
) -> EntryZone:
    """
    Calculate dual entry zone based on SMC structure.
    
    Near entry: Closer to current price, safer but lower R:R
    Far entry: Deeper into structure, riskier but better R:R
    """
    logger.critical(f"_calculate_entry_zone CALLED: direction={direction}, current_price={current_price}, atr={atr}, num_obs={len(smc_snapshot.order_blocks)}, num_fvgs={len(smc_snapshot.fvgs)}")
    
    # Normalize direction to lowercase
    direction_lower = direction.lower()
    is_bullish = direction_lower in ["bullish", "long"]
    
    # Find relevant order block or FVG
    if is_bullish:
        # Look for bullish OB or FVG below current price
        obs = [ob for ob in smc_snapshot.order_blocks if ob.direction == "bullish" and ob.high < current_price]
        fvgs = [fvg for fvg in smc_snapshot.fvgs if fvg.direction == "bullish" and fvg.top < current_price]
        
        logger.critical(f"Bullish entry zone: found {len(obs)} OBs and {len(fvgs)} FVGs below current price")
        if obs:
            # Use most recent/fresh OB
            best_ob = max(obs, key=lambda ob: ob.freshness_score)
            logger.critical(f"ENTRY ZONE: Using bullish OB - high={best_ob.high}, low={best_ob.low}, ATR={atr}")
            near_entry = best_ob.high - (0.1 * atr)  # Top of OB (aggressive entry)
            far_entry = best_ob.low + (0.1 * atr)    # Bottom of OB (conservative, deeper)
            logger.critical(f"ENTRY ZONE: Calculated near={near_entry}, far={far_entry}")
            rationale = f"Entry zone based on {best_ob.timeframe} bullish order block"
        
        elif fvgs:
            # Use nearest unfilled FVG
            best_fvg = min([fvg for fvg in fvgs if fvg.overlap_with_price < 0.5], 
                          key=lambda fvg: abs(fvg.top - current_price), 
                          default=fvgs[0])
            near_entry = best_fvg.top - (0.1 * atr)      # Top of FVG (aggressive)
            far_entry = best_fvg.bottom + (0.1 * atr)    # Bottom of FVG (conservative)
            rationale = f"Entry zone based on {best_fvg.timeframe} bullish FVG"
        
        else:
            # Fallback: use ATR-based zone below current price
            logger.critical(f"ENTRY ZONE FALLBACK: current_price={current_price}, atr={atr}")
            near_entry = current_price - (0.5 * atr)
            far_entry = current_price - (1.5 * atr)
            logger.critical(f"ENTRY ZONE FALLBACK: near={near_entry}, far={far_entry}")
            rationale = "Entry zone based on ATR pullback (no clear SMC structure)"
    
    else:  # bearish
        # Look for bearish OB or FVG above current price
        obs = [ob for ob in smc_snapshot.order_blocks if ob.direction == "bearish" and ob.low > current_price]
        fvgs = [fvg for fvg in smc_snapshot.fvgs if fvg.direction == "bearish" and fvg.bottom > current_price]
        
        if obs:
            best_ob = max(obs, key=lambda ob: ob.freshness_score)
            near_entry = best_ob.low + (0.1 * atr)   # Bottom of OB (aggressive entry)
            far_entry = best_ob.high - (0.1 * atr)   # Top of OB (conservative, deeper)
            rationale = f"Entry zone based on {best_ob.timeframe} bearish order block"
        
        elif fvgs:
            best_fvg = min([fvg for fvg in fvgs if fvg.overlap_with_price < 0.5],
                          key=lambda fvg: abs(fvg.bottom - current_price),
                          default=fvgs[0])
            near_entry = best_fvg.bottom + (0.1 * atr)
            far_entry = best_fvg.top - (0.1 * atr)
            rationale = f"Entry zone based on {best_fvg.timeframe} bearish FVG"
        
        else:
            # Fallback: use ATR-based zone above current price
            near_entry = current_price + (0.5 * atr)
            far_entry = current_price + (1.5 * atr)
            rationale = "Entry zone based on ATR retracement (no clear SMC structure)"
    
    return EntryZone(
        near_entry=near_entry,
        far_entry=far_entry,
        rationale=rationale
    )


def _calculate_stop_loss(
    direction: str,
    entry_zone: EntryZone,
    smc_snapshot: SMCSnapshot,
    atr: float
) -> StopLoss:
    """
    Calculate structure-based stop loss.
    
    Never arbitrary - always beyond invalidation point.
    """
    direction_lower = direction.lower()
    is_bullish = direction_lower in ["bullish", "long"]
    
    if is_bullish:
        # Stop below the entry structure
        # Look for recent swing low or OB low
        potential_stops = []
        
        logger.debug(f"Calculating bullish stop: entry_zone.far_entry={entry_zone.far_entry}, entry_zone.near_entry={entry_zone.near_entry}")
        
        # Check for OBs near entry
        for ob in smc_snapshot.order_blocks:
            if ob.direction == "bullish" and ob.low < entry_zone.far_entry:
                potential_stops.append(ob.low)
                logger.debug(f"Found bullish OB: low={ob.low}, high={ob.high}")
        
        # Check for FVGs
        for fvg in smc_snapshot.fvgs:
            if fvg.direction == "bullish" and fvg.bottom < entry_zone.far_entry:
                potential_stops.append(fvg.bottom)
                logger.debug(f"Found bullish FVG: bottom={fvg.bottom}, top={fvg.top}")
        
        logger.debug(f"Potential stops before filtering: {potential_stops}")
        
        # Filter stops that are actually below entry
        valid_stops = [s for s in potential_stops if s < entry_zone.far_entry]
        
        logger.debug(f"Valid stops after filtering: {valid_stops}")
        
        if valid_stops:
            # Use closest structure below entry (highest of the valid stops)
            stop_level = max(valid_stops)
            stop_level -= (0.3 * atr)  # Buffer beyond structure
            rationale = "Stop below entry structure invalidation point"
            logger.debug(f"Using structure-based stop: {stop_level} (before buffer: {max(valid_stops)})")
            distance_atr = (entry_zone.far_entry - stop_level) / atr
        else:
            # CRITICAL: Never use ATR-only stops - reject trade without structure
            logger.warning(f"No structure-based stop found for bullish {direction} trade - rejecting")
            raise ValueError("Cannot generate trade plan: no clear structure for stop loss placement")
    
    else:  # bearish
        # Stop above the entry structure
        potential_stops = []
        
        for ob in smc_snapshot.order_blocks:
            if ob.direction == "bearish" and ob.high > entry_zone.far_entry:
                potential_stops.append(ob.high)
        
        for fvg in smc_snapshot.fvgs:
            if fvg.direction == "bearish" and fvg.top > entry_zone.far_entry:
                potential_stops.append(fvg.top)
        
        # Filter stops that are actually above entry
        valid_stops = [s for s in potential_stops if s > entry_zone.far_entry]
        
        if valid_stops:
            # Use closest structure above entry (lowest of the valid stops)
            stop_level = min(valid_stops)
            stop_level += (0.3 * atr)  # Buffer beyond structure
            rationale = "Stop above entry structure invalidation point"
            distance_atr = (stop_level - entry_zone.far_entry) / atr
        else:
            # CRITICAL: Never use ATR-only stops - reject trade without structure
            logger.warning(f"No structure-based stop found for bearish {direction} trade - rejecting")
            raise ValueError("Cannot generate trade plan: no clear structure for stop loss placement")
    
    # CRITICAL DEBUG
    logger.critical(f"STOP CALC: direction={direction}, entry_near={entry_zone.near_entry}, entry_far={entry_zone.far_entry}, stop={stop_level}, atr={atr}")
    
    return StopLoss(
        level=stop_level,
        distance_atr=distance_atr,
        rationale=rationale
    )


def _calculate_targets(
    direction: str,
    entry_zone: EntryZone,
    stop_loss: StopLoss,
    smc_snapshot: SMCSnapshot,
    atr: float,
    config: ScanConfig
) -> List[Target]:
    """
    Calculate tiered targets based on structure and R:R multiples.
    
    Returns 3 targets: conservative, moderate, aggressive.
    """
    avg_entry = (entry_zone.near_entry + entry_zone.far_entry) / 2
    risk_distance = abs(avg_entry - stop_loss.level)
    
    targets = []
    
    direction_lower = direction.lower()
    is_bullish = direction_lower in ["bullish", "long"]
    
    if is_bullish:
        # Target 1: Conservative (1.5R or nearest resistance)
        target1_rr = avg_entry + (risk_distance * 1.5)
        
        # Look for FVG or OB resistance
        resistances = []
        for fvg in smc_snapshot.fvgs:
            if fvg.direction == "bearish" and fvg.bottom > avg_entry:
                resistances.append(fvg.bottom)
        for ob in smc_snapshot.order_blocks:
            if ob.direction == "bearish" and ob.low > avg_entry:
                resistances.append(ob.low)
        
        if resistances and min(resistances) < target1_rr:
            target1_level = min(resistances)
            target1_rationale = "Nearest bearish structure (resistance)"
        else:
            target1_level = target1_rr
            target1_rationale = "1.5R target"
        
        targets.append(Target(
            level=target1_level,
            percentage=50.0,  # Close 50% of position at first target
            rationale=target1_rationale
        ))
        
        # Target 2: Moderate (2.5R or mid-structure)
        target2_level = avg_entry + (risk_distance * 2.5)
        targets.append(Target(
            level=target2_level,
            percentage=30.0,  # Close 30% of position at second target
            rationale="2.5R target (moderate)"
        ))
        
        # Target 3: Aggressive (4R or major structure)
        target3_level = avg_entry + (risk_distance * 4.0)
        targets.append(Target(
            level=target3_level,
            percentage=20.0,  # Close final 20% at third target
            rationale="4R target (aggressive)"
        ))
    
    else:  # bearish
        # Target 1: Conservative
        target1_rr = avg_entry - (risk_distance * 1.5)
        
        # Look for support
        supports = []
        for fvg in smc_snapshot.fvgs:
            if fvg.direction == "bullish" and fvg.top < avg_entry:
                supports.append(fvg.top)
        for ob in smc_snapshot.order_blocks:
            if ob.direction == "bullish" and ob.high < avg_entry:
                supports.append(ob.high)
        
        if supports and max(supports) > target1_rr:
            target1_level = max(supports)
            target1_rationale = "Nearest bullish structure (support)"
        else:
            target1_level = target1_rr
            target1_rationale = "1.5R target"
        
        targets.append(Target(
            level=target1_level,
            percentage=50.0,  # Close 50% of position at first target
            rationale=target1_rationale
        ))
        
        # Target 2: Moderate
        target2_level = avg_entry - (risk_distance * 2.5)
        targets.append(Target(
            level=target2_level,
            percentage=30.0,  # Close 30% of position at second target
            rationale="2.5R target (moderate)"
        ))
        
        # Target 3: Aggressive
        target3_level = avg_entry - (risk_distance * 4.0)
        targets.append(Target(
            level=target3_level,
            percentage=20.0,  # Close final 20% at third target
            rationale="4R target (aggressive)"
        ))
    
    return targets


def _generate_rationale(
    setup_type: str,
    confluence_breakdown: ConfluenceBreakdown,
    smc_snapshot: SMCSnapshot,
    entry_zone: EntryZone,
    stop_loss: StopLoss,
    targets: List[Target],
    risk_reward: float
) -> str:
    """
    Generate comprehensive human-readable rationale for the trade plan.
    """
    lines = []
    
    # Setup overview
    lines.append(f"**{setup_type} Setup**")
    lines.append(f"Confluence Score: {confluence_breakdown.total_score:.1f}/100 ({_score_to_rating(confluence_breakdown.total_score)})")
    lines.append("")
    
    # Key factors
    lines.append("**Key Confluence Factors:**")
    top_factors = sorted(confluence_breakdown.factors, key=lambda f: f.score * f.weight, reverse=True)[:3]
    for factor in top_factors:
        lines.append(f"• {factor.name} ({factor.score:.0f}/100): {factor.rationale}")
    lines.append("")
    
    # Market regime
    lines.append(f"**Market Regime:** {confluence_breakdown.regime.title()}")
    if confluence_breakdown.htf_aligned:
        lines.append("✓ Higher timeframe aligned")
    if confluence_breakdown.btc_impulse_gate:
        lines.append("✓ BTC impulse gate clear")
    lines.append("")
    
    # Trade structure
    lines.append("**Trade Structure:**")
    lines.append(f"• Entry: {entry_zone.rationale}")
    lines.append(f"• Stop: {stop_loss.rationale} ({stop_loss.distance_atr:.1f}x ATR)")
    lines.append(f"• Targets: {len(targets)} tiered levels")
    lines.append(f"• Risk:Reward: {risk_reward:.2f}:1")
    lines.append("")
    
    # Synergies and warnings
    if confluence_breakdown.synergy_bonus > 0:
        lines.append(f"⚡ Synergy Bonus: +{confluence_breakdown.synergy_bonus:.1f} (multiple factors align)")
    if confluence_breakdown.conflict_penalty > 0:
        lines.append(f"⚠️  Conflict Penalty: -{confluence_breakdown.conflict_penalty:.1f} (mixed signals)")
    
    return "\n".join(lines)


def _score_to_rating(score: float) -> str:
    """Convert numeric score to rating."""
    if score >= 80:
        return "Excellent"
    elif score >= 65:
        return "Good"
    elif score >= 50:
        return "Fair"
    else:
        return "Weak"


def validate_trade_plan(plan: TradePlan, config: ScanConfig) -> bool:
    """
    Validate that a trade plan meets all quality criteria.
    
    Args:
        plan: Trade plan to validate
        config: Scan configuration with requirements
        
    Returns:
        bool: True if valid, False otherwise
    """
    # Check R:R minimum
    if plan.risk_reward < config.min_rr_ratio:
        return False
    
    # Check confluence minimum
    if plan.confidence_score < config.min_confluence_score:
        return False
    
    # Check entry zone is valid
    if plan.direction == "bullish":
        if plan.entry_zone.near_entry >= plan.entry_zone.far_entry:
            return False
        if plan.stop_loss.level >= plan.entry_zone.far_entry:
            return False
    else:
        if plan.entry_zone.near_entry <= plan.entry_zone.far_entry:
            return False
        if plan.stop_loss.level <= plan.entry_zone.far_entry:
            return False
    
    # Check targets are in correct direction
    avg_entry = (plan.entry_zone.near_entry + plan.entry_zone.far_entry) / 2
    for target in plan.targets:
        if plan.direction == "bullish" and target.level <= avg_entry:
            return False
        if plan.direction == "bearish" and target.level >= avg_entry:
            return False
    
    return True
