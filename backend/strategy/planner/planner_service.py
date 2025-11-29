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

from typing import Optional, List, Literal, cast
from datetime import datetime
import pandas as pd
import numpy as np
from loguru import logger

from backend.shared.models.planner import TradePlan, EntryZone, StopLoss, Target

SetupArchetype = Literal[
    "TREND_OB_PULLBACK",
    "RANGE_REVERSION",
    "SWEEP_REVERSAL",
    "BREAKOUT_RETEST",
]

def _map_setup_to_archetype(setup_type: str) -> SetupArchetype:
    s = (setup_type or "").upper().replace(" ", "_")
    if "SWEEP" in s:
        return cast(SetupArchetype, "SWEEP_REVERSAL")
    if "BREAKOUT" in s or "RETEST" in s:
        return cast(SetupArchetype, "BREAKOUT_RETEST")
    if "RANGE" in s or "MEAN" in s:
        return cast(SetupArchetype, "RANGE_REVERSION")
    return cast(SetupArchetype, "TREND_OB_PULLBACK")
from backend.shared.models.smc import SMCSnapshot, OrderBlock, FVG
from backend.shared.models.indicators import IndicatorSet
from backend.shared.models.scoring import ConfluenceBreakdown
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.rr_matrix import validate_rr, classify_conviction


def generate_trade_plan(
    symbol: str,
    direction: str,
    setup_type: str,
    smc_snapshot: SMCSnapshot,
    indicators: IndicatorSet,
    confluence_breakdown: ConfluenceBreakdown,
    config: ScanConfig,
    current_price: float,
    missing_critical_timeframes: Optional[List[str]] = None
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
        
    Returns:
        TradePlan: Complete trade plan with entries, stops, targets
        
    Raises:
        ValueError: If unable to generate valid plan (insufficient structure)
    """
    if missing_critical_timeframes is None:
        missing_critical_timeframes = []
    
    # Get primary timeframe indicators
    if not indicators.by_timeframe:
        raise ValueError("No indicators available for trade planning")
    
    primary_tf = getattr(config, "primary_planning_timeframe", None) or list(indicators.by_timeframe.keys())[-1]
    primary_indicators = indicators.by_timeframe[primary_tf]
    
    if primary_indicators.atr is None:
        raise ValueError("ATR required for trade planning")
    
    atr = primary_indicators.atr
    
    # Track plan composition for type classification
    plan_composition = {
        'entry_from_structure': False,
        'stop_from_structure': False,
        'targets_from_structure': False
    }
    
    # Normalize direction and setup semantics
    direction_norm = direction.upper()
    if direction_norm not in ("LONG", "SHORT"):
        raise ValueError(f"Unsupported direction: {direction_norm}")
    is_bullish = direction_norm == "LONG"
    setup_archetype = _map_setup_to_archetype(setup_type)

    # --- Determine Entry Zone ---
    
    entry_zone, entry_used_structure = _calculate_entry_zone(
        is_bullish=is_bullish,
        smc_snapshot=smc_snapshot,
        current_price=current_price,
        atr=atr,
        primary_tf=primary_tf,
        setup_archetype=setup_archetype,
        config=config
    )
    plan_composition['entry_from_structure'] = entry_used_structure
    
    # --- Calculate Stop Loss ---
    
    stop_loss, stop_used_structure = _calculate_stop_loss(
        is_bullish=is_bullish,
        entry_zone=entry_zone,
        smc_snapshot=smc_snapshot,
        atr=atr,
        primary_tf=primary_tf,
        setup_archetype=setup_archetype,
        config=config
    )
    plan_composition['stop_from_structure'] = stop_used_structure
    
    # --- Calculate Targets ---
    
    targets = _calculate_targets(
        is_bullish=is_bullish,
        entry_zone=entry_zone,
        stop_loss=stop_loss,
        smc_snapshot=smc_snapshot,
        atr=atr,
        config=config,
        setup_archetype=setup_archetype,
        regime_label=confluence_breakdown.regime
    )
    
    # --- Calculate Risk:Reward ---
    
    avg_entry = (entry_zone.near_entry + entry_zone.far_entry) / 2
    risk = abs(avg_entry - stop_loss.level)
    
    if risk == 0:
        raise ValueError("Invalid stop loss: zero risk distance")
    
    # Use first target for R:R calculation
    reward = abs(targets[0].level - avg_entry)
    risk_reward = reward / risk

    # --- Approximate Expected Value (EV) ---
    # Derive a coarse win probability from confluence (bounded for sanity)
    p_win_raw = confluence_breakdown.total_score / 100.0
    p_win = max(0.2, min(0.85, p_win_raw))
    # EV with first target R:R: EV = p*R - (1-p)*1
    expected_value = (p_win * risk_reward) - ((1.0 - p_win) * 1.0)
    
    # --- Classify Plan Type ---
    
    # Determine plan type based on structure usage
    if plan_composition['entry_from_structure'] and plan_composition['stop_from_structure']:
        plan_type = "SMC"
    elif not plan_composition['entry_from_structure'] and not plan_composition['stop_from_structure']:
        plan_type = "ATR_FALLBACK"
    else:
        plan_type = "HYBRID"
    
    # --- Sanity gates and Tiered R:R Validation ---
    # Stop distance sanity using config bounds if present
    max_stop_atr = getattr(config, "max_stop_atr", 6.0)
    min_stop_atr = getattr(config, "min_stop_atr", 0.3)
    if stop_loss.distance_atr > max_stop_atr:
        raise ValueError("Stop too wide relative to ATR")
    if stop_loss.distance_atr < min_stop_atr:
        raise ValueError("Stop too tight relative to ATR")

    # Apply R:R threshold appropriate for plan type
    is_valid_rr, rr_reason = validate_rr(plan_type, risk_reward)
    if not is_valid_rr:
        raise ValueError(rr_reason)
    
    # --- Classify Conviction ---
    
    has_all_critical_tfs = len(missing_critical_timeframes) == 0
    conviction_class = classify_conviction(
        plan_type=plan_type,
        risk_reward=risk_reward,
        confluence_score=confluence_breakdown.total_score,
        has_all_critical_tfs=has_all_critical_tfs
    )
    
    # --- Generate Rationale ---
    
    rationale = _generate_rationale(
        setup_type=setup_type,
        confluence_breakdown=confluence_breakdown,
        smc_snapshot=smc_snapshot,
        entry_zone=entry_zone,
        stop_loss=stop_loss,
        targets=targets,
        risk_reward=risk_reward,
        primary_tf=primary_tf
    )
    
    # --- Build Trade Plan ---
    
    # Normalize to expected TradePlan literal types
    _dir_lower = direction.lower()
    trade_direction = "LONG" if is_bullish else "SHORT"
    trade_setup = setup_type if setup_type in ["scalp", "swing", "intraday"] else "intraday"

    trade_plan = TradePlan(
        symbol=symbol,
        direction=trade_direction,
        setup_type=cast(Literal['scalp', 'swing', 'intraday'], trade_setup),
        entry_zone=entry_zone,
        stop_loss=stop_loss,
        targets=targets,
        risk_reward=risk_reward,
        confidence_score=confluence_breakdown.total_score,
        confluence_breakdown=confluence_breakdown,
        rationale=rationale,
        plan_type=plan_type,
        conviction_class=conviction_class,
        missing_critical_timeframes=missing_critical_timeframes,
        metadata={
            "atr": atr,
            "current_price": current_price,
            "timestamp": datetime.utcnow().isoformat(),
            "plan_composition": plan_composition,
            "rr_components": {
                "avg_entry": avg_entry,
                "stop": stop_loss.level,
                "first_target": targets[0].level,
                "risk_distance": risk,
                "reward_distance": reward
            },
            "ev": {
                "p_win": p_win,
                "risk_reward": risk_reward,
                "expected_value": expected_value
            }
        }
    )
    
    return trade_plan


def _calculate_entry_zone(
    is_bullish: bool,
    smc_snapshot: SMCSnapshot,
    current_price: float,
    atr: float,
    primary_tf: str,
    setup_archetype: SetupArchetype,
    config: ScanConfig
) -> tuple[EntryZone, bool]:
    """
    Calculate dual entry zone based on SMC structure.
    
    Near entry: Closer to current price, safer but lower R:R
    Far entry: Deeper into structure, riskier but better R:R
    
    Returns:
        Tuple of (EntryZone, used_structure_flag)
    """
    logger.critical(f"_calculate_entry_zone CALLED: is_bullish={is_bullish}, current_price={current_price}, atr={atr}, num_obs={len(smc_snapshot.order_blocks)}, num_fvgs={len(smc_snapshot.fvgs)}")
    
    # Find relevant order block or FVG
    if is_bullish:
        # Look for bullish OB or FVG below current price
        obs = [ob for ob in smc_snapshot.order_blocks if ob.direction == "bullish" and ob.high < current_price]
        # Filter out OBs too far (distance constraint)
        max_pullback_atr = getattr(config, "max_pullback_atr", 3.0)
        obs = [ob for ob in obs if (current_price - ob.high) / atr <= max_pullback_atr]
        # Prefer higher timeframe / freshness
        tf_weight = {"1m": 0.5, "5m": 0.8, "15m": 1.0, "1h": 1.2, "4h": 1.5, "1d": 2.0}
        def _ob_score(ob: OrderBlock) -> float:
            return ob.freshness_score * tf_weight.get(ob.timeframe, 1.0)
        fvgs = [fvg for fvg in smc_snapshot.fvgs if fvg.direction == "bullish" and fvg.top < current_price]
        
        logger.critical(f"Bullish entry zone: found {len(obs)} OBs and {len(fvgs)} FVGs below current price")
        if obs:
            # Use most recent/fresh OB
            best_ob = max(obs, key=_ob_score)
            logger.critical(f"ENTRY ZONE: Using bullish OB - high={best_ob.high}, low={best_ob.low}, ATR={atr}")
            near_entry = best_ob.high - (0.1 * atr)  # Top of OB (aggressive entry)
            far_entry = best_ob.low + (0.1 * atr)    # Bottom of OB (conservative, deeper)
            logger.critical(f"ENTRY ZONE: Calculated near={near_entry}, far={far_entry}")
            rationale = f"Entry zone based on {best_ob.timeframe} bullish order block"
            used_structure = True
        
        elif fvgs:
            # Use nearest unfilled FVG
            best_fvg = min([fvg for fvg in fvgs if fvg.overlap_with_price < 0.5], 
                          key=lambda fvg: abs(fvg.top - current_price), 
                          default=fvgs[0])
            near_entry = best_fvg.top - (0.1 * atr)      # Top of FVG (aggressive)
            far_entry = best_fvg.bottom + (0.1 * atr)    # Bottom of FVG (conservative)
            rationale = f"Entry zone based on {best_fvg.timeframe} bullish FVG"
            used_structure = True
        
        else:
            # Fallback: use ATR-based zone below current price
            logger.critical(f"ENTRY ZONE FALLBACK: current_price={current_price}, atr={atr}")
            near_entry = current_price - (0.5 * atr)
            far_entry = current_price - (1.5 * atr)
            logger.critical(f"ENTRY ZONE FALLBACK: near={near_entry}, far={far_entry}")
            rationale = "Entry zone based on ATR pullback (no clear SMC structure)"
            used_structure = False
    
    else:  # bearish
        # Look for bearish OB or FVG above current price
        obs = [ob for ob in smc_snapshot.order_blocks if ob.direction == "bearish" and ob.low > current_price]
        max_pullback_atr = getattr(config, "max_pullback_atr", 3.0)
        obs = [ob for ob in obs if (ob.low - current_price) / atr <= max_pullback_atr]
        tf_weight = {"1m": 0.5, "5m": 0.8, "15m": 1.0, "1h": 1.2, "4h": 1.5, "1d": 2.0}
        def _ob_score_b(ob: OrderBlock) -> float:
            return ob.freshness_score * tf_weight.get(ob.timeframe, 1.0)
        fvgs = [fvg for fvg in smc_snapshot.fvgs if fvg.direction == "bearish" and fvg.bottom > current_price]
        
        if obs:
            best_ob = max(obs, key=_ob_score_b)
            near_entry = best_ob.low + (0.1 * atr)   # Bottom of OB (aggressive entry)
            far_entry = best_ob.high - (0.1 * atr)   # Top of OB (conservative, deeper)
            rationale = f"Entry zone based on {best_ob.timeframe} bearish order block"
            used_structure = True
        
        elif fvgs:
            best_fvg = min([fvg for fvg in fvgs if fvg.overlap_with_price < 0.5],
                          key=lambda fvg: abs(fvg.bottom - current_price),
                          default=fvgs[0])
            near_entry = best_fvg.bottom + (0.1 * atr)
            far_entry = best_fvg.top - (0.1 * atr)
            rationale = f"Entry zone based on {best_fvg.timeframe} bearish FVG"
            used_structure = True
        
        else:
            # Fallback: use ATR-based zone above current price
            near_entry = current_price + (0.5 * atr)
            far_entry = current_price + (1.5 * atr)
            rationale = "Entry zone based on ATR retracement (no clear SMC structure)"
            used_structure = False
    
    return EntryZone(
        near_entry=near_entry,
        far_entry=far_entry,
        rationale=rationale
    ), used_structure


def _calculate_stop_loss(
    is_bullish: bool,
    entry_zone: EntryZone,
    smc_snapshot: SMCSnapshot,
    atr: float,
    primary_tf: str,
    setup_archetype: SetupArchetype,
    config: ScanConfig
) -> tuple[StopLoss, bool]:
    """
    Calculate structure-based stop loss.
    
    Never arbitrary - always beyond invalidation point.
    
    Returns:
        Tuple of (StopLoss, used_structure_flag)
    """
    # Direction provided via is_bullish
    
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
            used_structure = True
        else:
            # CRITICAL: Never use ATR-only stops - reject trade without structure
            logger.warning(f"No structure-based stop found for bullish trade - rejecting")
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
            used_structure = True
        else:
            # CRITICAL: Never use ATR-only stops - reject trade without structure
            logger.warning(f"No structure-based stop found for bearish trade - rejecting")
            raise ValueError("Cannot generate trade plan: no clear structure for stop loss placement")
    
    # CRITICAL DEBUG
    logger.critical(f"STOP CALC: is_bullish={is_bullish}, entry_near={entry_zone.near_entry}, entry_far={entry_zone.far_entry}, stop={stop_level}, atr={atr}")
    
    return StopLoss(
        level=stop_level,
        distance_atr=distance_atr,
        rationale=rationale
    ), used_structure


def _calculate_targets(
    is_bullish: bool,
    entry_zone: EntryZone,
    stop_loss: StopLoss,
    smc_snapshot: SMCSnapshot,
    atr: float,
    config: ScanConfig,
    setup_archetype: SetupArchetype,
    regime_label: str
) -> List[Target]:
    """
    Calculate tiered targets based on structure and R:R multiples.
    
    Returns 3 targets: conservative, moderate, aggressive.
    """
    avg_entry = (entry_zone.near_entry + entry_zone.far_entry) / 2
    risk_distance = abs(avg_entry - stop_loss.level)
    
    targets = []
    
    # Determine RR ladder based on archetype and regime
    regime_lower = (regime_label or "").lower()
    trending = any(k in regime_lower for k in ["trend", "drive"]) or 'aligned' in regime_lower
    if setup_archetype == "SWEEP_REVERSAL":
        rr_levels = [1.2, 2.0, 3.0]
    elif setup_archetype == "RANGE_REVERSION":
        rr_levels = [1.2, 2.0, 3.0]
    elif setup_archetype == "BREAKOUT_RETEST":
        rr_levels = [1.5, 2.5, 4.0] if not trending else [2.0, 3.0, 5.0]
    else:  # TREND_OB_PULLBACK
        rr_levels = [1.5, 2.5, 4.0] if not trending else [2.0, 3.0, 5.0]
    
    if is_bullish:
        # Target 1: Conservative (1.5R or nearest resistance)
        target1_rr = avg_entry + (risk_distance * rr_levels[0])
        
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
        
        # Target 2: Moderate
        target2_level = avg_entry + (risk_distance * rr_levels[1])
        targets.append(Target(
            level=target2_level,
            percentage=30.0,  # Close 30% of position at second target
            rationale="2.5R target (moderate)"
        ))
        
        # Target 3: Aggressive
        target3_level = avg_entry + (risk_distance * rr_levels[2])
        targets.append(Target(
            level=target3_level,
            percentage=20.0,  # Close final 20% at third target
            rationale="4R target (aggressive)"
        ))
    
    else:  # bearish
        # Target 1: Conservative
        target1_rr = avg_entry - (risk_distance * rr_levels[0])
        
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
        target2_level = avg_entry - (risk_distance * rr_levels[1])
        targets.append(Target(
            level=target2_level,
            percentage=30.0,  # Close 30% of position at second target
            rationale="2.5R target (moderate)"
        ))
        
        # Target 3: Aggressive
        target3_level = avg_entry - (risk_distance * rr_levels[2])
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
    risk_reward: float,
    primary_tf: str
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

    # Explicit invalidation guidance
    lines.append("**Invalidation:**")
    lines.append(f"Trade idea invalid if price closes beyond {stop_loss.level:.4f} on the {primary_tf} timeframe.")
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
