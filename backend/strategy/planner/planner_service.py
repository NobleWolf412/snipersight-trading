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
from backend.shared.models.data import MultiTimeframeData

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
from backend.bot.telemetry.logger import get_telemetry_logger
from backend.bot.telemetry.events import create_signal_rejected_event, create_alt_stop_suggested_event


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
    multi_tf_data: Optional['MultiTimeframeData'] = None
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
    
    telemetry = get_telemetry_logger()
    run_id = datetime.utcnow().strftime("run-%Y%m%d")  # coarse run grouping

    if primary_indicators.atr is None or primary_indicators.atr <= 0:
        telemetry.log_event(create_signal_rejected_event(
            run_id=run_id,
            symbol=symbol,
            reason="atr_invalid",
            diagnostics={"atr": primary_indicators.atr}
        ))
        raise ValueError("ATR required for trade planning and must be positive")
    atr = primary_indicators.atr

    # --- Leverage parameters (RR scaling removed) ---
    # We preserve incoming leverage for metadata transparency but do NOT adapt
    # target RR ladder or structural buffers based on it for manual scanning.
    leverage = max(1, int(getattr(config, 'leverage', 1) or 1))
    rr_scale = 1.0  # Explicitly neutralized
    leverage_adjustments = {
        "leverage": leverage,
        "rr_scale": rr_scale,
        "mode": "neutral"
    }
    
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
        config=config,
        confluence_breakdown=confluence_breakdown
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
        config=config,
        multi_tf_data=multi_tf_data
    )
    plan_composition['stop_from_structure'] = stop_used_structure
    
    # --- Structural collapse guards before targets (prevent .15 DOGE case) ---
    avg_entry_pre = (entry_zone.near_entry + entry_zone.far_entry) / 2.0
    spread = abs(entry_zone.near_entry - entry_zone.far_entry)
    risk_distance_pre = abs(avg_entry_pre - stop_loss.level)
    price_eps = max(1e-6, current_price * 0.0001)  # Dynamic epsilon (~0.01%)
    if spread <= price_eps:
        logger.warning(f"Rejecting plan: entry zone collapsed (near={entry_zone.near_entry}, far={entry_zone.far_entry}, eps={price_eps})")
        telemetry.log_event(create_signal_rejected_event(
            run_id=run_id,
            symbol=symbol,
            reason="entry_zone_collapsed",
            diagnostics={"near_entry": entry_zone.near_entry, "far_entry": entry_zone.far_entry, "eps": price_eps}
        ))
        raise ValueError("Entry zone collapsed: insufficient spread")
    if risk_distance_pre <= price_eps:
        logger.warning(f"Rejecting plan: risk distance collapsed (avg_entry={avg_entry_pre}, stop={stop_loss.level}, eps={price_eps})")
        telemetry.log_event(create_signal_rejected_event(
            run_id=run_id,
            symbol=symbol,
            reason="risk_distance_collapsed",
            diagnostics={"avg_entry": avg_entry_pre, "stop": stop_loss.level, "eps": price_eps}
        ))
        raise ValueError("Risk distance collapsed: stop too close to entry")

    # --- Calculate Targets ---
    targets = _calculate_targets(
        is_bullish=is_bullish,
        entry_zone=entry_zone,
        stop_loss=stop_loss,
        smc_snapshot=smc_snapshot,
        atr=atr,
        config=config,
        setup_archetype=setup_archetype,
        regime_label=confluence_breakdown.regime,
        rr_scale=rr_scale
    )
    
    # --- Calculate Risk:Reward ---
    
    avg_entry = (entry_zone.near_entry + entry_zone.far_entry) / 2
    # Targets collapse guard: ensure at least one target offers meaningful reward distance
    target_dists = [abs(t.level - avg_entry) for t in targets]
    if all(d <= price_eps for d in target_dists):
        logger.warning(f"Rejecting plan: targets collapsed near entry (targets={[t.level for t in targets]}, avg_entry={avg_entry}, eps={price_eps})")
        telemetry.log_event(create_signal_rejected_event(
            run_id=run_id,
            symbol=symbol,
            reason="targets_collapsed",
            diagnostics={"targets": [t.level for t in targets], "avg_entry": avg_entry, "eps": price_eps}
        ))
        raise ValueError("Targets collapsed: no meaningful reward distance")
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

    # Apply R:R threshold appropriate for plan type (mode-aware)
    # Pass EV and confluence to enable intelligent override for borderline R:R
    is_valid_rr, rr_reason = validate_rr(
        plan_type, 
        risk_reward, 
        mode_profile=config.profile,
        expected_value=expected_value,
        confluence_score=confluence_breakdown.total_score
    )
    if not is_valid_rr:
        raise ValueError(rr_reason)
    
    # --- Classify Conviction ---
    
    has_all_critical_tfs = len(missing_critical_timeframes) == 0
    conviction_class = classify_conviction(
        plan_type=plan_type,
        risk_reward=risk_reward,
        confluence_score=confluence_breakdown.total_score,
        has_all_critical_tfs=has_all_critical_tfs,
        mode_profile=config.profile
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

    # Extract ATR regime & alt stop metadata (flattened logic replaced by helpers)
    atr_pct = (atr / max(current_price, 1e-12)) * 100.0
    regime_label = (
        "calm" if atr_pct < 0.5 else
        "normal" if atr_pct < 1.2 else
        "elevated" if atr_pct < 2.0 else
        "explosive"
    )
    recommended_buffer_atr = (
        0.25 if atr_pct < 0.5 else
        0.30 if atr_pct < 1.2 else
        0.40 if atr_pct < 2.0 else
        0.50
    )
    used_stop_buffer_atr = round(abs(stop_loss.level - entry_zone.far_entry) / atr, 4)

    liquidation_meta = _calculate_liquidation_metadata(
        is_bullish=is_bullish,
        near_entry=entry_zone.near_entry,
        stop_level=stop_loss.level,
        leverage=leverage
    )

    alt_stop_meta = None
    if liquidation_meta.get("risk_band") == "high":
        # Suggest extended stop only if structurally further away
        extended_buffer = (
            0.35 if atr_pct < 0.5 else
            0.40 if atr_pct < 1.2 else
            0.50 if atr_pct < 2.0 else
            0.60
        )
        suggested_level = (
            entry_zone.far_entry - extended_buffer * atr if is_bullish
            else entry_zone.far_entry + extended_buffer * atr
        )
        if (is_bullish and suggested_level < stop_loss.level) or ((not is_bullish) and suggested_level > stop_loss.level):
            alt_stop_meta = {
                "level": suggested_level,
                "rationale": f"Extended buffer for high liquidation risk ({liquidation_meta.get('risk_band')})",
                "recommended_buffer_atr": extended_buffer
            }
            # Emit telemetry event
            telemetry.log_event(create_alt_stop_suggested_event(
                run_id=run_id,
                symbol=symbol,
                direction=trade_direction,
                cushion_pct=liquidation_meta.get('cushion_pct', 0.0),
                risk_band=liquidation_meta.get('risk_band', ''),
                suggested_level=suggested_level,
                current_stop=stop_loss.level,
                leverage=leverage,
                regime_label=regime_label,
                recommended_buffer_atr=extended_buffer
            ))

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
            },
            "leverage_adjustments": leverage_adjustments,
            "liquidation": liquidation_meta,
            "atr_regime": {
                "label": regime_label,
                "atr_pct": round(atr_pct, 4),
                "recommended_stop_buffer_atr": recommended_buffer_atr,
                "used_stop_buffer_atr": used_stop_buffer_atr
            },
            "alt_stop": alt_stop_meta
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
    config: ScanConfig,
    confluence_breakdown: Optional[ConfluenceBreakdown] = None
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
            offset = 0.1 * atr
            # If HTF proximity aligns (support, within thresholds), bias entries closer to level
            try:
                if (
                    getattr(config, 'htf_bias_entry', False)
                    and confluence_breakdown is not None
                    and confluence_breakdown.nearest_htf_level_type == 'support'
                    and (confluence_breakdown.htf_proximity_atr or 99) <= getattr(config, 'htf_proximity_atr_max', 1.0)
                ):
                    offset = float(getattr(config, 'htf_bias_entry_offset_atr', 0.05)) * atr
            except Exception:
                pass
            near_entry = best_ob.high - offset
            far_entry = best_ob.low + offset
            logger.critical(f"ENTRY ZONE: Calculated near={near_entry}, far={far_entry}")
            rationale = f"Entry zone based on {best_ob.timeframe} bullish order block"
            used_structure = True
        
        elif fvgs:
            # Use nearest unfilled FVG
            best_fvg = min([fvg for fvg in fvgs if fvg.overlap_with_price < 0.5], 
                          key=lambda fvg: abs(fvg.top - current_price), 
                          default=fvgs[0])
            offset = 0.1 * atr
            try:
                if (
                    getattr(config, 'htf_bias_entry', False)
                    and confluence_breakdown is not None
                    and confluence_breakdown.nearest_htf_level_type == 'support'
                    and (confluence_breakdown.htf_proximity_atr or 99) <= getattr(config, 'htf_proximity_atr_max', 1.0)
                ):
                    offset = float(getattr(config, 'htf_bias_entry_offset_atr', 0.05)) * atr
            except Exception:
                pass
            near_entry = best_fvg.top - offset
            far_entry = best_fvg.bottom + offset
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
            offset = 0.1 * atr
            try:
                if (
                    getattr(config, 'htf_bias_entry', False)
                    and confluence_breakdown is not None
                    and confluence_breakdown.nearest_htf_level_type == 'resistance'
                    and (confluence_breakdown.htf_proximity_atr or 99) <= getattr(config, 'htf_proximity_atr_max', 1.0)
                ):
                    offset = float(getattr(config, 'htf_bias_entry_offset_atr', 0.05)) * atr
            except Exception:
                pass
            near_entry = best_ob.low + offset
            far_entry = best_ob.high - offset
            rationale = f"Entry zone based on {best_ob.timeframe} bearish order block"
            used_structure = True
        
        elif fvgs:
            best_fvg = min([fvg for fvg in fvgs if fvg.overlap_with_price < 0.5],
                          key=lambda fvg: abs(fvg.bottom - current_price),
                          default=fvgs[0])
            offset = 0.1 * atr
            try:
                if (
                    getattr(config, 'htf_bias_entry', False)
                    and confluence_breakdown is not None
                    and confluence_breakdown.nearest_htf_level_type == 'resistance'
                    and (confluence_breakdown.htf_proximity_atr or 99) <= getattr(config, 'htf_proximity_atr_max', 1.0)
                ):
                    offset = float(getattr(config, 'htf_bias_entry_offset_atr', 0.05)) * atr
            except Exception:
                pass
            near_entry = best_fvg.bottom + offset
            far_entry = best_fvg.top - offset
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


def _find_swing_level(
    is_bullish: bool,
    reference_price: float,
    candles_df: pd.DataFrame,
    lookback: int = 20
) -> Optional[float]:
    """
    Find swing high or swing low from price action.
    
    A swing low is a bar where the low is lower than N bars before and after.
    A swing high is a bar where the high is higher than N bars before and after.
    
    Args:
        is_bullish: If True, find swing low (for stop). If False, find swing high.
        reference_price: Entry price to anchor search from
        candles_df: OHLCV dataframe for the timeframe
        lookback: Number of bars to search back
        
    Returns:
        Swing level price or None if no clear swing found
    """
    if candles_df is None or len(candles_df) < 5:
        return None
    
    # Use last N candles
    recent = candles_df.tail(lookback)
    
    if is_bullish:
        # Find swing lows below reference price
        swing_lows = []
        for i in range(2, len(recent) - 2):
            low = recent.iloc[i]['low']
            # Check if local minimum (lower than 2 bars before and after)
            if (low < recent.iloc[i-1]['low'] and 
                low < recent.iloc[i-2]['low'] and
                low < recent.iloc[i+1]['low'] and 
                low < recent.iloc[i+2]['low'] and
                low < reference_price):
                swing_lows.append(low)
        
        # Return the highest swing low (closest to entry)
        return max(swing_lows) if swing_lows else None
    else:
        # Find swing highs above reference price
        swing_highs = []
        for i in range(2, len(recent) - 2):
            high = recent.iloc[i]['high']
            # Check if local maximum (higher than 2 bars before and after)
            if (high > recent.iloc[i-1]['high'] and 
                high > recent.iloc[i-2]['high'] and
                high > recent.iloc[i+1]['high'] and 
                high > recent.iloc[i+2]['high'] and
                high > reference_price):
                swing_highs.append(high)
        
        # Return the lowest swing high (closest to entry)
        return min(swing_highs) if swing_highs else None


def _calculate_stop_loss(
    is_bullish: bool,
    entry_zone: EntryZone,
    smc_snapshot: SMCSnapshot,
    atr: float,
    primary_tf: str,
    setup_archetype: SetupArchetype,
    config: ScanConfig,
    multi_tf_data: Optional[MultiTimeframeData] = None
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
            # Fallback: swing-based stop from primary timeframe
            logger.info(f"No SMC structure for stop - attempting swing-based fallback on {primary_tf}")
            swing_level = None
            if multi_tf_data and primary_tf in multi_tf_data.timeframes:
                candles_df = multi_tf_data.timeframes[primary_tf]
                swing_level = _find_swing_level(
                    is_bullish=True,
                    reference_price=entry_zone.far_entry,
                    candles_df=candles_df,
                    lookback=20
                )
            
            if swing_level:
                stop_level = swing_level - (0.3 * atr)  # Buffer below swing
                rationale = f"Stop below swing low on {primary_tf} (no SMC structure)"
                distance_atr = (entry_zone.far_entry - stop_level) / atr
                used_structure = False  # Swing level, not SMC structure
                logger.info(f"Using swing-based stop: {stop_level}")
            else:
                # Last resort: check HTF for structure
                logger.warning(f"No swing level found - rejecting trade")
                raise ValueError("Cannot generate trade plan: no clear structure or swing level for stop loss placement")
    
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
            # Fallback: swing-based stop from primary timeframe
            logger.info(f"No SMC structure for stop - attempting swing-based fallback on {primary_tf}")
            swing_level = None
            if multi_tf_data and primary_tf in multi_tf_data.timeframes:
                candles_df = multi_tf_data.timeframes[primary_tf]
                swing_level = _find_swing_level(
                    is_bullish=False,
                    reference_price=entry_zone.far_entry,
                    candles_df=candles_df,
                    lookback=20
                )
            
            if swing_level:
                stop_level = swing_level + (0.3 * atr)  # Buffer above swing
                rationale = f"Stop above swing high on {primary_tf} (no SMC structure)"
                distance_atr = (stop_level - entry_zone.far_entry) / atr
                used_structure = False  # Swing level, not SMC structure
                logger.info(f"Using swing-based stop: {stop_level}")
            else:
                # Last resort: reject if no swing level
                logger.warning(f"No swing level found - rejecting trade")
                raise ValueError("Cannot generate trade plan: no clear structure or swing level for stop loss placement")
    
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
    regime_label: str,
    rr_scale: float = 1.0
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
        base_rr = [1.2, 2.0, 3.0]
    elif setup_archetype == "RANGE_REVERSION":
        base_rr = [1.2, 2.0, 3.0]
    elif setup_archetype == "BREAKOUT_RETEST":
        base_rr = [1.5, 2.5, 4.0] if not trending else [2.0, 3.0, 5.0]
    else:  # TREND_OB_PULLBACK
        base_rr = [1.5, 2.5, 4.0] if not trending else [2.0, 3.0, 5.0]
    rr_levels = [r * rr_scale for r in base_rr]
    
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
            percentage=50.0,
            rationale=f"{target1_rationale} (RR≈{rr_levels[0]:.2f})"
        ))
        
        # Target 2: Moderate
        target2_level = avg_entry + (risk_distance * rr_levels[1])
        targets.append(Target(
            level=target2_level,
            percentage=30.0,
            rationale=f"Mid target RR≈{rr_levels[1]:.2f}"
        ))
        
        # Target 3: Aggressive
        target3_level = avg_entry + (risk_distance * rr_levels[2])
        targets.append(Target(
            level=target3_level,
            percentage=20.0,
            rationale=f"Aggressive RR≈{rr_levels[2]:.2f}"
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
            percentage=50.0,
            rationale=f"{target1_rationale} (RR≈{rr_levels[0]:.2f})"
        ))
        
        # Target 2: Moderate
        target2_level = avg_entry - (risk_distance * rr_levels[1])
        targets.append(Target(
            level=target2_level,
            percentage=30.0,
            rationale=f"Mid target RR≈{rr_levels[1]:.2f}"
        ))
        
        # Target 3: Aggressive
        target3_level = avg_entry - (risk_distance * rr_levels[2])
        targets.append(Target(
            level=target3_level,
            percentage=20.0,
            rationale=f"Aggressive RR≈{rr_levels[2]:.2f}"
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


def _calculate_liquidation_metadata(
    is_bullish: bool,
    near_entry: float,
    stop_level: float,
    leverage: int,
    mmr: float = 0.004
) -> dict:
    """Approximate liquidation price and cushion.

    Formula (simplified isolated margin):
      Long:  P_liq = Entry * (1 + mmr - 1/L)
      Short: P_liq = Entry * (1 - mmr + 1/L)

    Cushion pct (long): (stop - liq) / (entry - liq) * 100
    Cushion pct (short): (liq - stop) / (liq - entry) * 100
    """
    leverage = max(1, leverage)
    entry = near_entry
    if is_bullish:
        liq_price = entry * (1 + mmr - (1.0 / leverage))
        cushion_raw = (stop_level - liq_price) / max(entry - liq_price, 1e-12)
    else:
        liq_price = entry * (1 - mmr + (1.0 / leverage))
        cushion_raw = (liq_price - stop_level) / max(liq_price - entry, 1e-12)

    cushion_pct = round(cushion_raw * 100, 4)
    if cushion_pct < 30:
        risk_band = "high"
    elif cushion_pct < 55:
        risk_band = "moderate"
    else:
        risk_band = "comfortable"

    return {
        "assumed_mmr": mmr,
        "approx_liq_price": round(liq_price, 8),
        "cushion_pct": cushion_pct,
        "risk_band": risk_band,
        "direction": "long" if is_bullish else "short"
    }
