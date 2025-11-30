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
from backend.shared.config.planner_config import PlannerConfig
from backend.shared.config.rr_matrix import validate_rr, classify_conviction
from backend.bot.telemetry.logger import get_telemetry_logger
from backend.bot.telemetry.events import create_signal_rejected_event, create_alt_stop_suggested_event


def _get_allowed_structure_tfs(config: ScanConfig) -> tuple:
    """Extract structure_timeframes from config, or return empty tuple if unrestricted."""
    return getattr(config, 'structure_timeframes', ())


def _get_allowed_entry_tfs(config: ScanConfig) -> tuple:
    """Extract entry_timeframes from config, or return empty tuple if unrestricted."""
    return getattr(config, 'entry_timeframes', ())


def _classify_atr_regime(atr: float, current_price: float, planner_cfg: PlannerConfig) -> str:
    """Classify current ATR regime based on ATR% of price.
    
    Args:
        atr: Current ATR value
        current_price: Current market price
        planner_cfg: Planner configuration with regime thresholds
        
    Returns:
        Regime label: "calm", "normal", "elevated", or "explosive"
    """
    atr_pct = (atr / max(current_price, 1e-12)) * 100.0
    
    thresholds = planner_cfg.atr_regime_thresholds
    if atr_pct < thresholds.get("calm", 0.5):
        return "calm"
    elif atr_pct < thresholds.get("normal", 1.2):
        return "normal"
    elif atr_pct < thresholds.get("elevated", 2.0):
        return "elevated"
    else:
        return "explosive"


def _calculate_htf_bias_factor(
    distance_atr: float,
    planner_cfg: PlannerConfig
) -> float:
    """Calculate HTF bias offset factor using linear gradient.
    
    Closer to HTF level -> smaller offsets (factor approaches min_factor)
    Further from HTF level -> normal offsets (factor approaches 1.0)
    
    Args:
        distance_atr: Distance to nearest HTF level in ATRs (always >= 0)
        planner_cfg: Planner configuration
        
    Returns:
        Offset scaling factor between min_factor and 1.0
    """
    if not planner_cfg.htf_bias_enabled:
        return 1.0
    
    max_dist = planner_cfg.htf_bias_max_atr_distance
    min_factor = planner_cfg.htf_bias_offset_min_factor
    
    # Clamp distance to [0, max_dist]
    distance_clamped = min(max(distance_atr, 0.0), max_dist)
    
    # Linear interpolation: t = 0 (on level) -> min_factor, t = 1 (far) -> 1.0
    t = distance_clamped / max_dist if max_dist > 0 else 1.0
    
    return min_factor + (1.0 - min_factor) * t


def _is_order_block_valid(ob: OrderBlock, df: pd.DataFrame, current_price: float) -> bool:
    """Validate an order block is not broken and not currently being mitigated."""
    if df is None or len(df) == 0:
        return True
    try:
        future_candles = df[df.index > ob.timestamp]
    except Exception:
        return True
    if len(future_candles) == 0:
        return True
    if ob.direction == "bullish":
        lowest = future_candles['low'].min()
        if lowest < ob.low:  # broken through
            return False
        if ob.low <= current_price <= ob.high:  # currently inside zone
            return False
    else:
        highest = future_candles['high'].max()
        if highest > ob.high:
            return False
        if ob.low <= current_price <= ob.high:
            return False
    return True

def _time_since_last_touch(ob: OrderBlock, df: pd.DataFrame) -> float:
    """Hours since OB last touched; infinity if never."""
    if df is None or len(df) == 0:
        return float('inf')
    try:
        future_candles = df[df.index > ob.timestamp]
    except Exception:
        return float('inf')
    if len(future_candles) == 0:
        return float('inf')
    if ob.direction == "bullish":
        touches = future_candles[future_candles['low'] <= ob.high]
    else:
        touches = future_candles[future_candles['high'] >= ob.low]
    if len(touches) == 0:
        return float('inf')
    last_touch = touches.index[-1]
    return (df.index[-1] - last_touch).total_seconds() / 3600.0


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
    
    # Get or create PlannerConfig from ScanConfig
    planner_cfg = getattr(config, 'planner', None) or PlannerConfig.defaults_for_mode(config.profile)
    
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
        planner_cfg=planner_cfg,
        confluence_breakdown=confluence_breakdown,
        multi_tf_data=multi_tf_data
    )
    plan_composition['entry_from_structure'] = entry_used_structure
    
    # --- Price Alignment Sanity Check ---
    # Fail fast if structure and current price are massively mismatched
    mid_entry = (entry_zone.near_entry + entry_zone.far_entry) / 2
    rel_diff = abs(mid_entry - current_price) / max(current_price, 1e-12)
    
    if rel_diff > planner_cfg.price_alignment_max_rel_diff:
        telemetry.log_event(create_signal_rejected_event(
            run_id=run_id,
            symbol=symbol,
            reason="price_structure_mismatch",
            diagnostics={"mid_entry": mid_entry, "current_price": current_price, "rel_diff": rel_diff, "threshold": planner_cfg.price_alignment_max_rel_diff}
        ))
        raise ValueError(f"Current price and structure prices diverge ({rel_diff:.1%} > {planner_cfg.price_alignment_max_rel_diff:.1%}); check symbol feed.")
    
    # --- Calculate Stop Loss ---
    
    stop_loss, stop_used_structure = _calculate_stop_loss(
        is_bullish=is_bullish,
        entry_zone=entry_zone,
        smc_snapshot=smc_snapshot,
        atr=atr,
        primary_tf=primary_tf,
        setup_archetype=setup_archetype,
        config=config,
        planner_cfg=planner_cfg,
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
        planner_cfg=planner_cfg,
        setup_archetype=setup_archetype,
        regime_label=confluence_breakdown.regime,
        rr_scale=rr_scale,
        confluence_breakdown=confluence_breakdown
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
    
    # --- Minimum Target Move % Validation (TF Responsibility Enforcement) ---
    min_target_move_pct = getattr(config, 'min_target_move_pct', 0.0)
    if min_target_move_pct > 0:
        # Calculate TP1 move % from current price
        tp1_move_pct = abs(targets[0].level - current_price) / max(current_price, 1e-12) * 100.0
        if tp1_move_pct < min_target_move_pct:
            logger.warning(f"Rejecting plan: TP1 move {tp1_move_pct:.2f}% < threshold {min_target_move_pct:.2f}%")
            telemetry.log_event(create_signal_rejected_event(
                run_id=run_id,
                symbol=symbol,
                reason="insufficient_target_move",
                diagnostics={
                    "tp1_level": targets[0].level,
                    "current_price": current_price,
                    "move_pct": tp1_move_pct,
                    "threshold": min_target_move_pct,
                    "mode": config.profile
                }
            ))
            raise ValueError(f"TP1 move {tp1_move_pct:.2f}% below mode minimum {min_target_move_pct:.2f}%")
    else:
        tp1_move_pct = abs(targets[0].level - current_price) / max(current_price, 1e-12) * 100.0
    
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

    # --- Final real-time price sanity (optional drift gate) ---
    max_drift_pct = float(getattr(config, 'max_entry_drift_pct', 0.15))  # 15% default
    max_drift_atr = float(getattr(config, 'max_entry_drift_atr', 3.0))    # 3 ATR default
    avg_entry_live = (entry_zone.near_entry + entry_zone.far_entry) / 2.0
    drift_abs = abs(current_price - avg_entry_live)
    drift_pct = drift_abs / max(avg_entry_live, 1e-12)
    drift_atr = drift_abs / max(atr, 1e-12)
    # Allow equality (touch) as valid; only reject if strictly above for bullish
    if is_bullish and entry_zone.near_entry > current_price:
        telemetry.log_event(create_signal_rejected_event(
            run_id=run_id,
            symbol=symbol,
            reason="entry_above_price",
            diagnostics={"near_entry": entry_zone.near_entry, "price": current_price}
        ))
        raise ValueError("Invalid bullish entry: entry above current price")
    # For bearish, reject only if far_entry strictly below price (zone flipped)
    if (not is_bullish) and entry_zone.far_entry < current_price:
        telemetry.log_event(create_signal_rejected_event(
            run_id=run_id,
            symbol=symbol,
            reason="entry_below_price",
            diagnostics={"far_entry": entry_zone.far_entry, "price": current_price}
        ))
        raise ValueError("Invalid bearish entry: entry below current price")
    if drift_pct > max_drift_pct or drift_atr > max_drift_atr:
        telemetry.log_event(create_signal_rejected_event(
            run_id=run_id,
            symbol=symbol,
            reason="price_drift",
            diagnostics={"drift_pct": drift_pct, "drift_atr": drift_atr, "max_drift_pct": max_drift_pct, "max_drift_atr": max_drift_atr}
        ))
        raise ValueError("Price drift invalidates entry zone")

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
            "alt_stop": alt_stop_meta,
            "tf_responsibility": {
                "bias_tfs": list(getattr(config, 'bias_timeframes', config.timeframes)),  # Use bias_timeframes or fallback
                "entry_tfs_allowed": list(getattr(config, 'entry_timeframes', [])),  # Entry TFs for precise triggers
                "structure_tfs_allowed": list(getattr(config, 'structure_timeframes', [])),  # Structure TFs for SL/TP
                "entry_tf_used": getattr(entry_zone, 'entry_tf_used', None),
                "structure_tf_used": getattr(stop_loss, 'structure_tf_used', None),
                "move_pct": round(tp1_move_pct, 4),
                "min_move_threshold": min_target_move_pct,
                "min_rr_passed": is_valid_rr
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
    config: ScanConfig,
    planner_cfg: PlannerConfig,
    confluence_breakdown: Optional[ConfluenceBreakdown] = None,
    multi_tf_data: Optional[MultiTimeframeData] = None
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
    allowed_tfs = _get_allowed_entry_tfs(config)  # CHANGED: Use entry TFs, not structure TFs
    
    if is_bullish:
        # Look for bullish OB or FVG below current price
        obs = [ob for ob in smc_snapshot.order_blocks if ob.direction == "bullish" and ob.high < current_price]
        # Filter to allowed ENTRY timeframes if specified
        if allowed_tfs:
            obs = [ob for ob in obs if ob.timeframe in allowed_tfs]
            logger.debug(f"Filtered bullish OBs to entry_timeframes {allowed_tfs}: {len(obs)} remain")
        # Filter out OBs too far (distance constraint)
        max_pullback_atr = getattr(config, "max_pullback_atr", 3.0)
        obs = [ob for ob in obs if (current_price - ob.high) / atr <= max_pullback_atr]
        # Filter out heavily mitigated OBs
        obs = [ob for ob in obs if ob.mitigation_level <= planner_cfg.ob_mitigation_max]
        # Validate OB integrity (not broken / not currently tapped)
        if multi_tf_data and primary_tf in getattr(multi_tf_data, 'timeframes', {}):
            df_primary = multi_tf_data.timeframes[primary_tf]
            validated = []
            for ob in obs:
                if _is_order_block_valid(ob, df_primary, current_price):
                    validated.append(ob)
                else:
                    logger.debug(f"Filtered invalid bullish OB (broken or tapped): low={ob.low} high={ob.high} ts={ob.timestamp}")
            obs = validated
        # Prefer higher timeframe / freshness / displacement / low mitigation
        tf_weight = {"1m": 0.5, "5m": 0.8, "15m": 1.0, "1h": 1.2, "4h": 1.5, "1d": 2.0}
        def _ob_score(ob: OrderBlock) -> float:
            base_score = ob.freshness_score * tf_weight.get(ob.timeframe, 1.0)
            displacement_factor = 1.0 + (ob.displacement_strength * planner_cfg.ob_displacement_weight)
            mitigation_penalty = (1.0 - min(ob.mitigation_level, 1.0))
            return base_score * displacement_factor * mitigation_penalty
        fvgs = [fvg for fvg in smc_snapshot.fvgs if fvg.direction == "bullish" and fvg.top < current_price]
        # Filter to allowed ENTRY timeframes if specified
        if allowed_tfs:
            fvgs = [fvg for fvg in fvgs if fvg.timeframe in allowed_tfs]
            logger.debug(f"Filtered bullish FVGs to entry_timeframes {allowed_tfs}: {len(fvgs)} remain")
        
        logger.critical(f"Bullish entry zone: found {len(obs)} OBs and {len(fvgs)} FVGs below current price")
        if obs:
            # Use most recent/fresh OB
            best_ob = max(obs, key=_ob_score)
            entry_tf_used = best_ob.timeframe  # Track for metadata
            logger.critical(f"ENTRY ZONE: Using bullish OB - high={best_ob.high}, low={best_ob.low}, ATR={atr}, TF={entry_tf_used}")
            
            # Calculate regime-aware base offset
            regime = _classify_atr_regime(atr, current_price, planner_cfg)
            regime_multiplier = planner_cfg.atr_regime_multipliers.get(regime, 1.0)
            base_offset = planner_cfg.entry_zone_offset_atr * regime_multiplier
            
            # Apply HTF bias gradient if HTF support is nearby
            htf_factor = 1.0
            try:
                if (
                    planner_cfg.htf_bias_enabled
                    and confluence_breakdown is not None
                    and confluence_breakdown.nearest_htf_level_type == 'support'
                    and (confluence_breakdown.htf_proximity_atr or 99) <= planner_cfg.htf_bias_max_atr_distance
                ):
                    htf_distance = confluence_breakdown.htf_proximity_atr or 99
                    htf_factor = _calculate_htf_bias_factor(htf_distance, planner_cfg)
            except Exception:
                pass
            
            offset = base_offset * htf_factor * atr
            near_entry = best_ob.high - offset
            far_entry = best_ob.low + offset
            logger.critical(f"ENTRY ZONE: Calculated near={near_entry}, far={far_entry}")
            rationale = f"Entry zone based on {best_ob.timeframe} bullish order block"
            used_structure = True
            entry_zone = EntryZone(
                near_entry=near_entry,
                far_entry=far_entry,
                rationale=rationale
            )
            # Attach entry_tf_used for metadata tracking
            entry_zone.entry_tf_used = entry_tf_used  # type: ignore
            return entry_zone, used_structure
        
        elif fvgs:
            # Use nearest unfilled FVG (filter by overlap threshold)
            best_fvg = min([fvg for fvg in fvgs if fvg.overlap_with_price < planner_cfg.fvg_overlap_max], 
                          key=lambda fvg: abs(fvg.top - current_price), 
                          default=fvgs[0])
            entry_tf_used = best_fvg.timeframe  # Track for metadata
            
            # Calculate regime-aware base offset
            regime = _classify_atr_regime(atr, current_price, planner_cfg)
            regime_multiplier = planner_cfg.atr_regime_multipliers.get(regime, 1.0)
            base_offset = planner_cfg.entry_zone_offset_atr * regime_multiplier
            
            # Apply HTF bias gradient if HTF support is nearby
            htf_factor = 1.0
            try:
                if (
                    planner_cfg.htf_bias_enabled
                    and confluence_breakdown is not None
                    and confluence_breakdown.nearest_htf_level_type == 'support'
                    and (confluence_breakdown.htf_proximity_atr or 99) <= planner_cfg.htf_bias_max_atr_distance
                ):
                    htf_distance = confluence_breakdown.htf_proximity_atr or 99
                    htf_factor = _calculate_htf_bias_factor(htf_distance, planner_cfg)
            except Exception:
                pass
            
            offset = base_offset * htf_factor * atr
            near_entry = best_fvg.top - offset
            far_entry = best_fvg.bottom + offset
            rationale = f"Entry zone based on {best_fvg.timeframe} bullish FVG"
            used_structure = True
            entry_zone = EntryZone(
                near_entry=near_entry,
                far_entry=far_entry,
                rationale=rationale
            )
            entry_zone.entry_tf_used = entry_tf_used  # type: ignore
            return entry_zone, used_structure
        
        else:
            # Fallback: use ATR-based zone below current price
            logger.critical(f"ENTRY ZONE FALLBACK: current_price={current_price}, atr={atr}")
            regime = _classify_atr_regime(atr, current_price, planner_cfg)
            regime_multiplier = planner_cfg.atr_regime_multipliers.get(regime, 1.0)
            near_entry = current_price - (planner_cfg.fallback_entry_near_atr * regime_multiplier * atr)
            far_entry = current_price - (planner_cfg.fallback_entry_far_atr * regime_multiplier * atr)
            logger.critical(f"ENTRY ZONE FALLBACK: near={near_entry}, far={far_entry}")
            rationale = "Entry zone based on ATR pullback (no clear SMC structure)"
            used_structure = False
            entry_zone = EntryZone(
                near_entry=near_entry,
                far_entry=far_entry,
                rationale=rationale
            )
            entry_zone.entry_tf_used = None  # type: ignore
            return entry_zone, used_structure
    
    else:  # bearish
        # Look for bearish OB or FVG above current price
        obs = [ob for ob in smc_snapshot.order_blocks if ob.direction == "bearish" and ob.low > current_price]
        # Filter to allowed ENTRY timeframes if specified
        if allowed_tfs:
            obs = [ob for ob in obs if ob.timeframe in allowed_tfs]
            logger.debug(f"Filtered bearish OBs to entry_timeframes {allowed_tfs}: {len(obs)} remain")
        max_pullback_atr = getattr(config, "max_pullback_atr", 3.0)
        obs = [ob for ob in obs if (ob.low - current_price) / atr <= max_pullback_atr]
        # Filter out heavily mitigated OBs
        obs = [ob for ob in obs if ob.mitigation_level <= planner_cfg.ob_mitigation_max]
        if multi_tf_data and primary_tf in getattr(multi_tf_data, 'timeframes', {}):
            df_primary = multi_tf_data.timeframes[primary_tf]
            validated_b = []
            for ob in obs:
                if _is_order_block_valid(ob, df_primary, current_price):
                    validated_b.append(ob)
                else:
                    logger.debug(f"Filtered invalid bearish OB (broken or tapped): low={ob.low} high={ob.high} ts={ob.timestamp}")
            obs = validated_b
        tf_weight = {"1m": 0.5, "5m": 0.8, "15m": 1.0, "1h": 1.2, "4h": 1.5, "1d": 2.0}
        def _ob_score_b(ob: OrderBlock) -> float:
            base_score = ob.freshness_score * tf_weight.get(ob.timeframe, 1.0)
            displacement_factor = 1.0 + (ob.displacement_strength * planner_cfg.ob_displacement_weight)
            mitigation_penalty = (1.0 - min(ob.mitigation_level, 1.0))
            return base_score * displacement_factor * mitigation_penalty
        fvgs = [fvg for fvg in smc_snapshot.fvgs if fvg.direction == "bearish" and fvg.bottom > current_price]
        # Filter to allowed ENTRY timeframes if specified
        if allowed_tfs:
            fvgs = [fvg for fvg in fvgs if fvg.timeframe in allowed_tfs]
            logger.debug(f"Filtered bearish FVGs to entry_timeframes {allowed_tfs}: {len(fvgs)} remain")
        
        if obs:
            best_ob = max(obs, key=_ob_score_b)
            entry_tf_used = best_ob.timeframe  # Track for metadata
            
            # Calculate regime-aware base offset
            regime = _classify_atr_regime(atr, current_price, planner_cfg)
            regime_multiplier = planner_cfg.atr_regime_multipliers.get(regime, 1.0)
            base_offset = planner_cfg.entry_zone_offset_atr * regime_multiplier
            
            # Apply HTF bias gradient if HTF resistance is nearby
            htf_factor = 1.0
            try:
                if (
                    planner_cfg.htf_bias_enabled
                    and confluence_breakdown is not None
                    and confluence_breakdown.nearest_htf_level_type == 'resistance'
                    and (confluence_breakdown.htf_proximity_atr or 99) <= planner_cfg.htf_bias_max_atr_distance
                ):
                    htf_distance = confluence_breakdown.htf_proximity_atr or 99
                    htf_factor = _calculate_htf_bias_factor(htf_distance, planner_cfg)
            except Exception:
                pass
            
            offset = base_offset * htf_factor * atr
            near_entry = best_ob.low + offset
            far_entry = best_ob.high - offset
            rationale = f"Entry zone based on {best_ob.timeframe} bearish order block"
            used_structure = True
            entry_zone = EntryZone(
                near_entry=near_entry,
                far_entry=far_entry,
                rationale=rationale
            )
            entry_zone.entry_tf_used = entry_tf_used  # type: ignore
            return entry_zone, used_structure
        
        elif fvgs:
            best_fvg = min([fvg for fvg in fvgs if fvg.overlap_with_price < planner_cfg.fvg_overlap_max],
                          key=lambda fvg: abs(fvg.bottom - current_price),
                          default=fvgs[0])
            entry_tf_used = best_fvg.timeframe  # Track for metadata
            
            # Calculate regime-aware base offset
            regime = _classify_atr_regime(atr, current_price, planner_cfg)
            regime_multiplier = planner_cfg.atr_regime_multipliers.get(regime, 1.0)
            base_offset = planner_cfg.entry_zone_offset_atr * regime_multiplier
            
            # Apply HTF bias gradient if HTF resistance is nearby
            htf_factor = 1.0
            try:
                if (
                    planner_cfg.htf_bias_enabled
                    and confluence_breakdown is not None
                    and confluence_breakdown.nearest_htf_level_type == 'resistance'
                    and (confluence_breakdown.htf_proximity_atr or 99) <= planner_cfg.htf_bias_max_atr_distance
                ):
                    htf_distance = confluence_breakdown.htf_proximity_atr or 99
                    htf_factor = _calculate_htf_bias_factor(htf_distance, planner_cfg)
            except Exception:
                pass
            
            offset = base_offset * htf_factor * atr
            # FIX: For shorts, near_entry must be > far_entry (near is closer to price, higher value)
            near_entry = best_fvg.top - offset
            far_entry = best_fvg.bottom + offset
            rationale = f"Entry zone based on {best_fvg.timeframe} bearish FVG"
            used_structure = True
            entry_zone = EntryZone(
                near_entry=near_entry,
                far_entry=far_entry,
                rationale=rationale
            )
            entry_zone.entry_tf_used = entry_tf_used  # type: ignore
            return entry_zone, used_structure
        
        else:
            # Fallback: use ATR-based zone above current price
            # For shorts: near_entry > far_entry (near is farther from price, higher value)
            # SWAP near/far offsets compared to longs to maintain semantic ordering
            regime = _classify_atr_regime(atr, current_price, planner_cfg)
            regime_multiplier = planner_cfg.atr_regime_multipliers.get(regime, 1.0)
            near_entry = current_price + (planner_cfg.fallback_entry_far_atr * regime_multiplier * atr)  # Far offset = higher
            far_entry = current_price + (planner_cfg.fallback_entry_near_atr * regime_multiplier * atr)  # Near offset = lower
            rationale = "Entry zone based on ATR retracement (no clear SMC structure)"
            used_structure = False
            entry_zone = EntryZone(
                near_entry=near_entry,
                far_entry=far_entry,
                rationale=rationale
            )
            entry_zone.entry_tf_used = None  # type: ignore
            return entry_zone, used_structure
    
    # Final sanity: bullish entries must be below price; bearish above
    if is_bullish and near_entry >= current_price:
        logger.warning(f"Bullish entry sanity fail near={near_entry} price={current_price} -> fallback ATR zone")
        regime = _classify_atr_regime(atr, current_price, planner_cfg)
        regime_multiplier = planner_cfg.atr_regime_multipliers.get(regime, 1.0)
        near_entry = current_price - (planner_cfg.fallback_entry_near_atr * regime_multiplier * atr)
        far_entry = current_price - (planner_cfg.fallback_entry_far_atr * regime_multiplier * atr)
        rationale = "Sanity fallback ATR pullback (invalid bullish structure)"
        used_structure = False
        entry_zone = EntryZone(
            near_entry=near_entry,
            far_entry=far_entry,
            rationale=rationale
        )
        entry_zone.entry_tf_used = None  # type: ignore
        return entry_zone, used_structure
    # Bearish sanity: both entries must be strictly above current price
    if (not is_bullish) and (near_entry <= current_price or far_entry <= current_price):
        logger.warning(
            f"Bearish entry sanity fail near={near_entry} far={far_entry} price={current_price} -> fallback ATR zone"
        )
        regime = _classify_atr_regime(atr, current_price, planner_cfg)
        regime_multiplier = planner_cfg.atr_regime_multipliers.get(regime, 1.0)
        # For shorts: swap offsets so near > far (near is higher, farther from price)
        near_entry = current_price + (planner_cfg.fallback_entry_far_atr * regime_multiplier * atr)  # Far offset = higher
        far_entry = current_price + (planner_cfg.fallback_entry_near_atr * regime_multiplier * atr)  # Near offset = lower
        rationale = "Sanity fallback ATR retracement (invalid bearish structure)"
        used_structure = False
        entry_zone = EntryZone(
            near_entry=near_entry,
            far_entry=far_entry,
            rationale=rationale
        )
        entry_zone.entry_tf_used = None  # type: ignore
        return entry_zone, used_structure

    # Return final entry zone (if we didn't hit sanity fallbacks, this was already returned above)
    # This should be unreachable but satisfies type checker
    return EntryZone(
        near_entry=near_entry,
        far_entry=far_entry,
        rationale=rationale
    ), used_structure


def _find_swing_level(
    is_bullish: bool,
    reference_price: float,
    candles_df: pd.DataFrame,
    lookback: int
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
    planner_cfg: PlannerConfig,
    multi_tf_data: Optional[MultiTimeframeData] = None
) -> tuple[StopLoss, bool]:
    """
    Calculate structure-based stop loss.
    
    Never arbitrary - always beyond invalidation point.
    
    Returns:
        Tuple of (StopLoss, used_structure_flag)
    """
    # Direction provided via is_bullish
    allowed_tfs = _get_allowed_structure_tfs(config)
    structure_tf_used = None  # Track which TF provided stop
    
    if is_bullish:
        # Stop below the entry structure
        # Look for recent swing low or OB low
        potential_stops = []
        
        logger.debug(f"Calculating bullish stop: entry_zone.far_entry={entry_zone.far_entry}, entry_zone.near_entry={entry_zone.near_entry}")
        
        # Check for OBs near entry
        for ob in smc_snapshot.order_blocks:
            # Filter to allowed structure timeframes if specified
            if allowed_tfs and ob.timeframe not in allowed_tfs:
                continue
            if ob.direction == "bullish" and ob.low < entry_zone.far_entry:
                potential_stops.append((ob.low, ob.timeframe))
                logger.debug(f"Found bullish OB: low={ob.low}, high={ob.high}, tf={ob.timeframe}")
        
        # Check for FVGs
        for fvg in smc_snapshot.fvgs:
            # Filter to allowed structure timeframes if specified
            if allowed_tfs and fvg.timeframe not in allowed_tfs:
                continue
            if fvg.direction == "bullish" and fvg.bottom < entry_zone.far_entry:
                potential_stops.append((fvg.bottom, fvg.timeframe))
                logger.debug(f"Found bullish FVG: bottom={fvg.bottom}, top={fvg.top}, tf={fvg.timeframe}")
        
        logger.debug(f"Potential stops before filtering: {[s[0] for s in potential_stops]}")
        
        # Filter stops that are actually below entry
        valid_stops = [(level, tf) for level, tf in potential_stops if level < entry_zone.far_entry]
        
        logger.debug(f"Valid stops after filtering: {[s[0] for s in valid_stops]}")
        
        if valid_stops:
            # Use closest structure below entry (highest of the valid stops)
            stop_level, structure_tf_used = max(valid_stops, key=lambda x: x[0])
            stop_level -= (planner_cfg.stop_buffer_atr * atr)  # Buffer beyond structure
            rationale = f"Stop below {structure_tf_used} entry structure invalidation point"
            logger.debug(f"Using structure-based stop: {stop_level} from {structure_tf_used} (before buffer: {max(valid_stops, key=lambda x: x[0])[0]})")
            distance_atr = (entry_zone.far_entry - stop_level) / atr
            used_structure = True
        else:
            # Fallback: swing-based stop from primary timeframe, then HTF if needed
            logger.info(f"No SMC structure for stop - attempting swing-based fallback")
            swing_level = None
            
            # Try primary timeframe first
            if multi_tf_data and primary_tf in multi_tf_data.timeframes:
                candles_df = multi_tf_data.timeframes[primary_tf]
                swing_level = _find_swing_level(
                    is_bullish=True,
                    reference_price=entry_zone.far_entry,
                    candles_df=candles_df,
                    lookback=planner_cfg.stop_lookback_bars
                )
            
            # Try HTF if enabled and primary failed
            if swing_level is None and planner_cfg.stop_use_htf_swings and multi_tf_data:
                htf_candidates = ['4h', '4H', '1d', '1D', '1w', '1W']
                for htf in htf_candidates:
                    if htf in multi_tf_data.timeframes:
                        candles_df = multi_tf_data.timeframes[htf]
                        swing_level = _find_swing_level(
                            is_bullish=True,
                            reference_price=entry_zone.far_entry,
                            candles_df=candles_df,
                            lookback=planner_cfg.stop_htf_lookback_bars
                        )
                        if swing_level:
                            logger.info(f"Found HTF swing on {htf}")
                            break
            
            if swing_level:
                stop_level = swing_level - (planner_cfg.stop_buffer_atr * atr)  # Buffer below swing
                rationale = f"Stop below swing low (no SMC structure)"
                distance_atr = (entry_zone.far_entry - stop_level) / atr
                used_structure = False  # Swing level, not SMC structure
                logger.info(f"Using swing-based stop: {stop_level}")
            else:
                # Last resort: reject trade
                logger.warning(f"No swing level found - rejecting trade")
                raise ValueError("Cannot generate trade plan: no clear structure or swing level for stop loss placement")
    
    else:  # bearish
        # Stop above the entry structure
        potential_stops = []
        
        for ob in smc_snapshot.order_blocks:
            # Filter to allowed structure timeframes if specified
            if allowed_tfs and ob.timeframe not in allowed_tfs:
                continue
            if ob.direction == "bearish" and ob.high > entry_zone.far_entry:
                potential_stops.append((ob.high, ob.timeframe))
        
        for fvg in smc_snapshot.fvgs:
            # Filter to allowed structure timeframes if specified
            if allowed_tfs and fvg.timeframe not in allowed_tfs:
                continue
            if fvg.direction == "bearish" and fvg.top > entry_zone.far_entry:
                potential_stops.append((fvg.top, fvg.timeframe))
        
        # Filter stops that are actually above entry
        valid_stops = [(level, tf) for level, tf in potential_stops if level > entry_zone.far_entry]
        
        if valid_stops:
            # Use closest structure above entry (lowest of the valid stops)
            stop_level, structure_tf_used = min(valid_stops, key=lambda x: x[0])
            stop_level += (planner_cfg.stop_buffer_atr * atr)  # Buffer beyond structure
            rationale = f"Stop above {structure_tf_used} entry structure invalidation point"
            distance_atr = (stop_level - entry_zone.far_entry) / atr
            used_structure = True
        else:
            # Fallback: swing-based stop from primary timeframe, then HTF if needed
            logger.info(f"No SMC structure for stop - attempting swing-based fallback")
            swing_level = None
            
            # Try primary timeframe first
            if multi_tf_data and primary_tf in multi_tf_data.timeframes:
                candles_df = multi_tf_data.timeframes[primary_tf]
                swing_level = _find_swing_level(
                    is_bullish=False,
                    reference_price=entry_zone.far_entry,
                    candles_df=candles_df,
                    lookback=planner_cfg.stop_lookback_bars
                )
            
            # Try HTF if enabled and primary failed
            if swing_level is None and planner_cfg.stop_use_htf_swings and multi_tf_data:
                htf_candidates = ['4h', '4H', '1d', '1D', '1w', '1W']
                for htf in htf_candidates:
                    if htf in multi_tf_data.timeframes:
                        candles_df = multi_tf_data.timeframes[htf]
                        swing_level = _find_swing_level(
                            is_bullish=False,
                            reference_price=entry_zone.far_entry,
                            candles_df=candles_df,
                            lookback=planner_cfg.stop_htf_lookback_bars
                        )
                        if swing_level:
                            logger.info(f"Found HTF swing on {htf}")
                            break
            
            if swing_level:
                stop_level = swing_level + (planner_cfg.stop_buffer_atr * atr)  # Buffer above swing
                rationale = f"Stop above swing high (no SMC structure)"
                distance_atr = (stop_level - entry_zone.far_entry) / atr
                used_structure = False  # Swing level, not SMC structure
                logger.info(f"Using swing-based stop: {stop_level}")
            else:
                # Last resort: reject trade
                logger.warning(f"No swing level found - rejecting trade")
                raise ValueError("Cannot generate trade plan: no clear structure or swing level for stop loss placement")
    
    # CRITICAL DEBUG
    logger.critical(f"STOP CALC: is_bullish={is_bullish}, entry_near={entry_zone.near_entry}, entry_far={entry_zone.far_entry}, stop={stop_level}, atr={atr}")
    
    stop_loss = StopLoss(
        level=stop_level,
        distance_atr=distance_atr,
        rationale=rationale
    )
    # Attach structure_tf_used for metadata tracking
    stop_loss.structure_tf_used = structure_tf_used  # type: ignore
    return stop_loss, used_structure


def _calculate_targets(
    is_bullish: bool,
    entry_zone: EntryZone,
    stop_loss: StopLoss,
    smc_snapshot: SMCSnapshot,
    atr: float,
    config: ScanConfig,
    planner_cfg: PlannerConfig,
    setup_archetype: SetupArchetype,
    regime_label: str,
    rr_scale: float = 1.0,
    confluence_breakdown: Optional[ConfluenceBreakdown] = None
) -> List[Target]:
    """
    Calculate tiered targets based on structure and R:R multiples.
    
    Returns 3 targets: conservative, moderate, aggressive.
    """
    avg_entry = (entry_zone.near_entry + entry_zone.far_entry) / 2
    risk_distance = abs(avg_entry - stop_loss.level)
    allowed_tfs = _get_allowed_structure_tfs(config)
    
    targets = []
    
    # Use configured RR ladder (can be overridden by setup/regime)
    regime_lower = (regime_label or "").lower()
    trending = any(k in regime_lower for k in ["trend", "drive"]) or 'aligned' in regime_lower
    
    # Start with config defaults, adjust for specific setups
    if setup_archetype == "SWEEP_REVERSAL":
        base_rr = [1.2, 2.0, 3.0]
    elif setup_archetype == "RANGE_REVERSION":
        base_rr = [1.2, 2.0, 3.0]
    elif trending and setup_archetype in ["BREAKOUT_RETEST", "TREND_OB_PULLBACK"]:
        base_rr = [2.0, 3.0, 5.0]
    else:
        # Use planner_cfg defaults for most cases
        base_rr = planner_cfg.target_rr_ladder[:3] if len(planner_cfg.target_rr_ladder) >= 3 else [1.5, 2.5, 4.0]
    
    rr_levels = [r * rr_scale for r in base_rr]
    
    if is_bullish:
        # Target 1: Conservative (1.5R or nearest resistance)
        target1_rr = avg_entry + (risk_distance * rr_levels[0])
        
        # Look for FVG or OB resistance
        resistances = []
        for fvg in smc_snapshot.fvgs:
            # Filter to allowed structure timeframes if specified
            if allowed_tfs and fvg.timeframe not in allowed_tfs:
                continue
            if fvg.direction == "bearish" and fvg.bottom > avg_entry:
                resistances.append(fvg.bottom)
        for ob in smc_snapshot.order_blocks:
            # Filter to allowed structure timeframes if specified
            if allowed_tfs and ob.timeframe not in allowed_tfs:
                continue
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
        
        # Target 2: Moderate (with structure clipping if enabled)
        target2_rr = avg_entry + (risk_distance * rr_levels[1])
        target2_level = target2_rr
        target2_rationale = f"Mid target RR≈{rr_levels[1]:.2f}"
        
        if planner_cfg.target_clip_to_structure and resistances:
            # Check if target would extend beyond nearest resistance
            nearest_resist = min([r for r in resistances if r > avg_entry], default=None)
            if nearest_resist and target2_rr > nearest_resist:
                # Calculate R:R if clipped to structure
                clipped_rr = (nearest_resist - avg_entry) / risk_distance
                if clipped_rr >= planner_cfg.target_min_rr_after_clip:
                    target2_level = nearest_resist
                    target2_rationale = f"Clipped to resistance at {nearest_resist:.4f} (RR≈{clipped_rr:.2f})"
        
        targets.append(Target(
            level=target2_level,
            percentage=30.0,
            rationale=target2_rationale
        ))
        
        # Target 3: Aggressive (with structure clipping if enabled)
        target3_rr = avg_entry + (risk_distance * rr_levels[2])
        target3_level = target3_rr
        target3_rationale = f"Aggressive RR≈{rr_levels[2]:.2f}"
        
        if planner_cfg.target_clip_to_structure and resistances:
            # Check if target would extend beyond nearest resistance
            nearest_resist = min([r for r in resistances if r > avg_entry], default=None)
            if nearest_resist and target3_rr > nearest_resist:
                # Calculate R:R if clipped to structure
                clipped_rr = (nearest_resist - avg_entry) / risk_distance
                if clipped_rr >= planner_cfg.target_min_rr_after_clip:
                    target3_level = nearest_resist
                    target3_rationale = f"Clipped to resistance at {nearest_resist:.4f} (RR≈{clipped_rr:.2f})"
        
        targets.append(Target(
            level=target3_level,
            percentage=20.0,
            rationale=target3_rationale
        ))
    
    else:  # bearish
        # Target 1: Conservative
        target1_rr = avg_entry - (risk_distance * rr_levels[0])
        
        # Look for support
        supports = []
        for fvg in smc_snapshot.fvgs:
            # Filter to allowed structure timeframes if specified
            if allowed_tfs and fvg.timeframe not in allowed_tfs:
                continue
            if fvg.direction == "bullish" and fvg.top < avg_entry:
                supports.append(fvg.top)
        for ob in smc_snapshot.order_blocks:
            # Filter to allowed structure timeframes if specified
            if allowed_tfs and ob.timeframe not in allowed_tfs:
                continue
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
        
        # Target 2: Moderate (with structure clipping if enabled)
        target2_rr = avg_entry - (risk_distance * rr_levels[1])
        target2_level = target2_rr
        target2_rationale = f"Mid target RR≈{rr_levels[1]:.2f}"
        
        if planner_cfg.target_clip_to_structure and supports:
            # Check if target would extend beyond nearest support
            nearest_support = max([s for s in supports if s < avg_entry], default=None)
            if nearest_support and target2_rr < nearest_support:
                # Calculate R:R if clipped to structure
                clipped_rr = (avg_entry - nearest_support) / risk_distance
                if clipped_rr >= planner_cfg.target_min_rr_after_clip:
                    target2_level = nearest_support
                    target2_rationale = f"Clipped to support at {nearest_support:.4f} (RR≈{clipped_rr:.2f})"
        
        targets.append(Target(
            level=target2_level,
            percentage=30.0,
            rationale=target2_rationale
        ))
        
        # Target 3: Aggressive (with structure clipping if enabled)
        target3_rr = avg_entry - (risk_distance * rr_levels[2])
        target3_level = target3_rr
        target3_rationale = f"Aggressive RR≈{rr_levels[2]:.2f}"
        
        if planner_cfg.target_clip_to_structure and supports:
            # Check if target would extend beyond nearest support
            nearest_support = max([s for s in supports if s < avg_entry], default=None)
            if nearest_support and target3_rr < nearest_support:
                # Calculate R:R if clipped to structure
                clipped_rr = (avg_entry - nearest_support) / risk_distance
                if clipped_rr >= planner_cfg.target_min_rr_after_clip:
                    target3_level = nearest_support
                    target3_rationale = f"Clipped to support at {nearest_support:.4f} (RR≈{clipped_rr:.2f})"
        
        targets.append(Target(
            level=target3_level,
            percentage=20.0,
            rationale=target3_rationale
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
