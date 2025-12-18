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
from backend.shared.config.smc_config import scale_lookback
from backend.bot.telemetry.logger import get_telemetry_logger
from backend.bot.telemetry.events import create_signal_rejected_event, create_alt_stop_suggested_event
from backend.strategy.smc.reversal_detector import get_reversal_rationale_for_plan

# Fib alignment for confluence boost (HTF only)
from backend.analysis.fibonacci import calculate_fib_levels, FibLevel


def _check_htf_fib_alignment(
    entry_price: float,
    ohlcv_data: dict,
    tolerance_pct: float = 1.0
) -> tuple[bool, Optional[str], float]:
    """
    Check if entry price aligns with HTF Fibonacci levels.
    
    Only checks 4H and 1D timeframes (LTF Fib is noise).
    Only checks 50% and 61.8% levels (statistically meaningful).
    
    Args:
        entry_price: The calculated entry price from SMC structure
        ohlcv_data: Dict of {timeframe: DataFrame} with candle data
        tolerance_pct: How close entry must be to Fib (default 1%)
        
    Returns:
        Tuple of (is_aligned, alignment_note, boost_value)
    """
    if not ohlcv_data:
        return False, None, 0.0
    
    htf_timeframes = ['4h', '1d']
    
    for tf in htf_timeframes:
        df = ohlcv_data.get(tf)
        if df is None or len(df) < 30:
            continue
            
        try:
            # Find major swing range in last 50 candles
            recent = df.tail(50)
            swing_high = recent['high'].max()
            swing_low = recent['low'].min()
            
            if swing_high <= swing_low:
                continue
            
            # Determine trend direction based on price position
            current_price = df.iloc[-1]['close']
            mid_range = (swing_high + swing_low) / 2
            trend_direction = 'bullish' if current_price > mid_range else 'bearish'
            
            # Calculate Fib levels
            fib_levels = calculate_fib_levels(
                swing_high=swing_high,
                swing_low=swing_low,
                trend_direction=trend_direction,
                timeframe=tf
            )
            
            # Check if entry aligns with any Fib level
            for fib in fib_levels:
                distance_pct = abs(entry_price - fib.price) / fib.price * 100
                
                if distance_pct <= tolerance_pct:
                    # Entry aligns with Fib!
                    boost = 7.0 if fib.ratio == 0.618 else 5.0  # 61.8% gets higher boost
                    note = f"Entry aligns with {tf.upper()} Fib {fib.display_ratio} (monitored level)"
                    return True, note, boost
                    
        except Exception as e:
            logger.debug(f"Fib alignment check failed for {tf}: {e}")
            continue
    
    return False, None, 0.0


def _adjust_stop_for_leverage(
    stop_level: float,
    near_entry: float,
    leverage: int,
    is_bullish: bool,
    min_cushion_pct: float = 30.0,
    mmr: float = 0.004,
    margin_type: str = 'isolated_linear'
) -> tuple[float, bool, dict]:
    """
    Adjust stop loss to ensure minimum cushion from liquidation price.
    
    ⚠️ IMPORTANT: This function assumes ISOLATED MARGIN on LINEAR (USDT-margined) contracts.
    
    The liquidation formula used:
    - LONG:  liq_price = entry * (1 + mmr - 1/leverage)
    - SHORT: liq_price = entry * (1 - mmr + 1/leverage)
    
    This is INCORRECT for:
    - Cross Margin: Liquidation depends on total account equity, not just position
    - Inverse/Coin-margined: Different formula involving contract value in coin terms
    
    For high leverage positions, the original structure-based stop may be
    too close to liquidation. This function tightens the stop if needed
    to maintain at least min_cushion_pct distance from liquidation.
    
    Args:
        stop_level: Original stop loss level
        near_entry: Near entry price (used as entry reference)
        leverage: Position leverage (1x = no adjustment)
        is_bullish: True for long, False for short
        min_cushion_pct: Minimum cushion percentage from liquidation (default 30%)
        mmr: Maintenance margin rate (default 0.4%)
        margin_type: 'isolated_linear' (default), 'isolated_inverse', 'cross'
                     Only 'isolated_linear' is currently supported.
        
    Returns:
        Tuple of (adjusted_stop, was_adjusted, adjustment_meta)
    """
    if leverage <= 1:
        return stop_level, False, {}
    
    # Warn if margin type is not supported
    if margin_type != 'isolated_linear':
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            "⚠️ Liquidation calculation assumes ISOLATED LINEAR margin. "
            "For %s margin, the stop adjustment may be INCORRECT. "
            "Manual verification recommended for leverage=%dx positions.",
            margin_type, leverage
        )
    
    entry = near_entry
    
    # Calculate liquidation price
    if is_bullish:
        liq_price = entry * (1 + mmr - (1.0 / leverage))
        # For longs: stop must be above liq_price by at least min_cushion_pct of (entry - liq)
        cushion_distance = (entry - liq_price) * (min_cushion_pct / 100.0)
        min_safe_stop = liq_price + cushion_distance
        
        if stop_level < min_safe_stop:
            # Original stop too close to liquidation - tighten it
            adjustment_meta = {
                'original_stop': stop_level,
                'adjusted_stop': min_safe_stop,
                'liq_price': liq_price,
                'reason': f'Tightened stop to maintain {min_cushion_pct}% cushion from liquidation at {leverage}x leverage'
            }
            return min_safe_stop, True, adjustment_meta
    else:
        liq_price = entry * (1 - mmr + (1.0 / leverage))
        # For shorts: stop must be below liq_price by at least min_cushion_pct of (liq - entry)
        cushion_distance = (liq_price - entry) * (min_cushion_pct / 100.0)
        max_safe_stop = liq_price - cushion_distance
        
        if stop_level > max_safe_stop:
            # Original stop too close to liquidation - tighten it
            adjustment_meta = {
                'original_stop': stop_level,
                'adjusted_stop': max_safe_stop,
                'liq_price': liq_price,
                'reason': f'Tightened stop to maintain {min_cushion_pct}% cushion from liquidation at {leverage}x leverage'
            }
            return max_safe_stop, True, adjustment_meta
    
    return stop_level, False, {}


def _adjust_targets_for_leverage(
    targets: List['Target'],
    leverage: int,
    entry_price: float,
    is_bullish: bool
) -> tuple[List['Target'], dict]:
    """
    Adjust target levels based on leverage tier.
    
    High leverage traders need faster profit capture to avoid liquidation risk.
    Low leverage traders can push for extended targets.
    
    Leverage Tiers:
    - 1x-5x: Extended targets (1.2x multiplier) - can hold for bigger moves
    - 5x-10x: Standard targets (1.0x) - balanced approach
    - 10x-25x: Tighter targets (0.75x) - faster profit capture
    - 25x+: Very tight targets (0.5x) - scalp mentality
    
    Args:
        targets: List of Target objects
        leverage: Position leverage
        entry_price: Entry price for distance calculation
        is_bullish: True for long, False for short
        
    Returns:
        Tuple of (adjusted_targets, adjustment_meta)
    """
    from backend.shared.models.planner import Target
    
    if leverage <= 1 or not targets:
        return targets, {}
    
    # Determine scaling factor based on leverage tier
    if leverage <= 5:
        scale_factor = 1.2  # Extended - can hold for bigger moves
        tier = "extended"
    elif leverage <= 10:
        scale_factor = 1.0  # Standard - no adjustment
        tier = "standard"
    elif leverage <= 25:
        scale_factor = 0.75  # Tighter - faster capture
        tier = "tight"
    else:
        scale_factor = 0.5  # Very tight - scalp mode
        tier = "very_tight"
    
    if scale_factor == 1.0:
        return targets, {"tier": tier, "scale_factor": scale_factor}
    
    adjusted_targets = []
    for target in targets:
        original_distance = abs(target.level - entry_price)
        adjusted_distance = original_distance * scale_factor
        
        if is_bullish:
            new_level = entry_price + adjusted_distance
        else:
            new_level = entry_price - adjusted_distance
        
        # Create new Target with adjusted level
        adjusted_target = Target(
            level=new_level,
            label=target.label,
            rr_ratio=target.rr_ratio * scale_factor if target.rr_ratio else None,
            weight=target.weight,
            rationale=f"{target.rationale} [Adjusted {scale_factor:.0%} for {leverage}x leverage]"
        )
        adjusted_targets.append(adjusted_target)
    
    adjustment_meta = {
        "tier": tier,
        "scale_factor": scale_factor,
        "leverage": leverage,
        "original_targets": [t.level for t in targets],
        "adjusted_targets": [t.level for t in adjusted_targets]
    }
    
    return adjusted_targets, adjustment_meta


def _get_allowed_structure_tfs(config: ScanConfig) -> tuple:
    """Extract structure_timeframes from config, or return empty tuple if unrestricted."""
    return getattr(config, 'structure_timeframes', ())


def _get_allowed_stop_tfs(config: ScanConfig) -> tuple:
    """Extract stop_timeframes from config, or return empty tuple if unrestricted.
    
    Falls back to structure_timeframes if stop_timeframes not specified.
    """
    stop_tfs = getattr(config, 'stop_timeframes', None)
    if stop_tfs:
        return stop_tfs
    # Fallback to structure_timeframes for backward compatibility
    return getattr(config, 'structure_timeframes', ())


def _get_allowed_entry_tfs(config: ScanConfig) -> tuple:
    """Extract entry_timeframes from config, or return empty tuple if unrestricted."""
    return getattr(config, 'entry_timeframes', ())


def _derive_trade_type(
    target_move_pct: float,
    stop_distance_atr: float,
    structure_timeframes: tuple,
    primary_tf: str
) -> Literal['scalp', 'swing', 'intraday']:
    """
    Derive trade type from setup characteristics, not mode.
    
    Trade type is determined by:
    1. Target move % (larger moves = swing)
    2. Stop distance in ATR (wider stops = swing)
    3. Structure timeframes used (HTF structure = swing)
    
    This allows any mode to find any trade type - the mode controls
    which timeframes are scanned (affecting probability), but the 
    actual trade type is derived from the setup itself.
    
    Args:
        target_move_pct: TP1 move as percentage of price
        stop_distance_atr: Stop distance in ATR units
        structure_timeframes: Allowed structure TFs from mode config
        primary_tf: Primary planning timeframe
        
    Returns:
        'scalp', 'swing', or 'intraday'
    """
    HTF = ('1w', '1d', '4h')
    MTF = ('1h',)  # Mid-timeframe - intraday territory
    LTF = ('15m', '5m', '1m')
    
    # Check structure timeframe categories
    htf_structure = any(tf in HTF for tf in structure_timeframes) if structure_timeframes else False
    mtf_structure = any(tf in MTF for tf in structure_timeframes) if structure_timeframes else False
    ltf_only = all(tf in LTF for tf in structure_timeframes) if structure_timeframes else False
    mtf_or_ltf_only = all(tf in MTF + LTF for tf in structure_timeframes) if structure_timeframes else False
    
    # Very large target moves are swing regardless of structure
    if target_move_pct >= 3.5:
        return 'swing'
    
    # Large target moves with HTF structure = swing
    if target_move_pct >= 2.5 and htf_structure:
        return 'swing'
    
    # Wide stops from HTF structure indicate swing trades
    if stop_distance_atr >= 3.5 and htf_structure:
        return 'swing'
    
    # HTF primary timeframe with moderate targets = swing
    if target_move_pct >= 1.5 and primary_tf in ('4h', '1d'):
        return 'swing'
    
    # Tight stops with LTF-only structure = scalp
    if stop_distance_atr <= 1.5 and ltf_only:
        return 'scalp'
    
    # Small moves with LTF context
    if target_move_pct < 0.6 and primary_tf in LTF:
        return 'scalp'
    
    # MTF or LTF structure with moderate moves = intraday (SURGICAL, STRIKE)
    if mtf_or_ltf_only and target_move_pct < 2.5:
        return 'intraday'
    
    # Default: intraday (middle ground)
    return 'intraday'


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
    multi_tf_data: Optional['MultiTimeframeData'] = None,
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
        expected_trade_type: Optional trade type hint (swing, scalp, intraday) - guides
            stop/target calculation. Derived type may differ from expected.
        
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
    # Normalize timeframe to match data keys (handle case mismatches)
    primary_tf_lower = primary_tf.lower()
    if primary_tf not in indicators.by_timeframe and primary_tf_lower in indicators.by_timeframe:
        primary_tf = primary_tf_lower
    
    # Defensive fallback: if configured primary_tf not in indicators, use first available
    if primary_tf not in indicators.by_timeframe:
        available_tfs = list(indicators.by_timeframe.keys())
        if not available_tfs:
            raise ValueError(f"No indicators available - primary_tf '{primary_tf}' not found and no fallback")
        primary_tf = available_tfs[0]
        logger.warning(f"Primary planning TF not in indicators, falling back to {primary_tf}")
    
    primary_indicators = indicators.by_timeframe[primary_tf]
    
    # Get or create PlannerConfig based on expected trade type
    # Trade type (swing/scalp/intraday) determines stop/target parameters
    if getattr(config, 'planner', None):
        # Explicit planner config takes precedence
        planner_cfg = config.planner
    elif expected_trade_type:
        # Use expected trade type from mode
        planner_cfg = PlannerConfig.defaults_for_mode(expected_trade_type)
        logger.debug(f"Using PlannerConfig for expected_trade_type={expected_trade_type}")
    else:
        # Fallback to intraday defaults
        planner_cfg = PlannerConfig.defaults_for_mode("intraday")
    
    # NEW: Apply mode-specific overrides from ScanConfig
    # This allows tuning specific planner parameters (like entry offset) without changing global defaults
    overrides = getattr(config, 'overrides', None) or {}
    if overrides:
        for key, value in overrides.items():
            if hasattr(planner_cfg, key):
                original = getattr(planner_cfg, key)
                setattr(planner_cfg, key, value)
                logger.debug(f"Applied mode override: {key} = {value} (was {original})")
    
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
    
    # --- HTF Fib Alignment Check ---
    # If entry aligns with 4H/1D Fib levels (50% or 61.8%), add confluence boost
    # This is a confirmation signal, not a primary edge
    htf_fib_boost = 0.0
    htf_fib_note = None
    if multi_tf_data and hasattr(multi_tf_data, 'ohlcv_by_timeframe'):
        ohlcv_data = multi_tf_data.ohlcv_by_timeframe
        avg_entry = (entry_zone.near_entry + entry_zone.far_entry) / 2
        fib_aligned, fib_note, fib_boost = _check_htf_fib_alignment(
            entry_price=avg_entry,
            ohlcv_data=ohlcv_data,
            tolerance_pct=1.0  # 1% tolerance
        )
        if fib_aligned:
            htf_fib_boost = fib_boost
            htf_fib_note = fib_note
            logger.info(f"Fib alignment detected for {symbol}: {fib_note} (+{fib_boost} confluence)")
    
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
        multi_tf_data=multi_tf_data,
        current_price=current_price,  # Pass for regime-aware stop buffer
        indicators_by_tf=indicators.by_timeframe  # Pass for structure-TF ATR lookup
    )
    plan_composition['stop_from_structure'] = stop_used_structure
    
    # === STORE ORIGINAL DISTANCE_ATR FOR VALIDATION ===
    # The distance_atr from _calculate_stop_loss uses structure TF ATR (correctly normalized)
    # We'll also compute primary TF distance for validation since modes are calibrated for primary TF
    original_structure_distance_atr = stop_loss.distance_atr
    primary_tf_distance_atr = abs(entry_zone.far_entry - stop_loss.level) / atr
    logger.debug(f"Stop distances: structure_atr={original_structure_distance_atr:.2f}, primary_tf_atr={primary_tf_distance_atr:.2f}")
    
    # --- Leverage-Aware Stop Adjustment ---
    # For high leverage, ensure stop maintains safe distance from liquidation
    if leverage > 1:
        adjusted_stop_level, was_adjusted, leverage_adj_meta = _adjust_stop_for_leverage(
            stop_level=stop_loss.level,
            near_entry=entry_zone.near_entry,
            leverage=leverage,
            is_bullish=is_bullish,
            min_cushion_pct=30.0  # Require 30% cushion from liquidation
        )
        if was_adjusted:
            # Update stop loss with tightened level
            old_stop = stop_loss.level
            # FIXED: Preserve the structure-TF ATR scaling, just recalculate for new distance
            new_distance_raw = abs(entry_zone.far_entry - adjusted_stop_level)
            old_distance_raw = abs(entry_zone.far_entry - old_stop)
            # Scale proportionally to preserve ATR normalization
            if old_distance_raw > 0:
                scale_factor = new_distance_raw / old_distance_raw
                new_distance_atr = original_structure_distance_atr * scale_factor
            else:
                new_distance_atr = new_distance_raw / atr
            stop_loss = StopLoss(
                level=adjusted_stop_level,
                distance_atr=new_distance_atr,
                rationale=f"{stop_loss.rationale} [Adjusted for {leverage}x leverage]"
            )
            # Update primary TF distance for validation
            primary_tf_distance_atr = new_distance_raw / atr
            logger.info(f"Leverage adjustment: stop moved from {old_stop:.6f} to {adjusted_stop_level:.6f} for {leverage}x leverage")
            leverage_adjustments['stop_adjusted'] = True
            leverage_adjustments['adjustment_meta'] = leverage_adj_meta
    
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
    
    # --- Apply Leverage-Based Target Adjustment ---
    # High leverage = tighter targets (faster capture)
    # Low leverage = extended targets (hold for bigger moves)
    if leverage > 1:
        avg_entry_for_targets = (entry_zone.near_entry + entry_zone.far_entry) / 2
        targets, target_adj_meta = _adjust_targets_for_leverage(
            targets=targets,
            leverage=leverage,
            entry_price=avg_entry_for_targets,
            is_bullish=is_bullish
        )
        if target_adj_meta:
            leverage_adjustments['targets_adjusted'] = True
            leverage_adjustments['target_adjustment'] = target_adj_meta
            logger.info(f"Targets adjusted for {leverage}x leverage: tier={target_adj_meta.get('tier')}, scale={target_adj_meta.get('scale_factor')}")
    
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
    
    # Trade-type-aware soft ATR caps
    # These are softer bounds that apply BEFORE mode bounds - trade type hints at expected range
    trade_type_atr_caps = {
        "swing": (0.5, 6.0),    # Swing: allow wide stops (0.5-6 ATR)
        "scalp": (0.15, 2.5),   # Scalp: tight stops (0.15-2.5 ATR)
        "intraday": (0.3, 4.0)  # Intraday: balanced (0.3-4 ATR)
    }
    soft_min, soft_max = trade_type_atr_caps.get(expected_trade_type or "intraday", (0.3, 6.0))
    
    # Use structure-normalized distance_atr for validation (accounts for HTF structure)
    # But also check primary TF distance doesn't exceed a hard ceiling (prevents crazy outliers)
    hard_ceiling_atr = max_stop_atr * 2.0  # Allow 2x for HTF structure
    
    if stop_loss.distance_atr > max_stop_atr:
        # Structure-based stop exceeded normal bounds - check if HTF structure allows it
        if stop_used_structure and stop_loss.distance_atr <= hard_ceiling_atr:
            # HTF structure stop - allow if within hard ceiling
            logger.info(f"Allowing HTF structure stop: {stop_loss.distance_atr:.2f} ATR > {max_stop_atr} but <= hard ceiling {hard_ceiling_atr}")
        else:
            # Calculate what leverage this setup would require
            # At 10x, ~7% max stop. At 5x, ~15% max stop. At 3x, ~25% max stop.
            stop_pct = (stop_loss.distance_atr * atr / current_price) * 100 if current_price > 0 else 0
            
            if stop_pct > 0 and leverage > 1:
                # Calculate max safe leverage allowing for a 30% cushion against liquidation
                # Formula: Max_Lev = 70 / Stop_Pct
                max_safe_lev = max(1, int(70 / stop_pct))
                
                # If our configured leverage is too high for this specific volatility
                if max_safe_lev < leverage:
                    # AUTO-DERATE instead of rejecting
                    new_leverage = max_safe_lev
                    
                    logger.warning(
                        "⚠️ SAFETY DERATING: Stop %.2f%% is too wide for %dx. Derating to %dx.",
                        stop_pct, leverage, new_leverage
                    )
                    
                    # Record this change so the Executor knows to modify the order
                    leverage_adjustments = {
                        'leverage_derated': True,
                        'original_leverage': leverage,
                        'suggested_leverage': new_leverage,
                        'reason': f"Stop distance {stop_pct:.1f}% requires max {new_leverage}x"
                    }
                    
                    # Store in context metadata for downstream use
                    context.metadata['leverage_adjustments'] = leverage_adjustments
                    
                    # Update leverage for this trade
                    leverage = new_leverage
                    
                    # DO NOT REJECT - let the trade pass with lower leverage
                else:
                    # Safe to proceed at configured leverage
                    pass
            else:
                # No leverage or zero stop - reject
                raise ValueError(f"Stop too wide ({stop_loss.distance_atr:.1f} ATR, ~{stop_pct:.1f}% move)")
    if stop_loss.distance_atr < min_stop_atr:
        raise ValueError("Stop too tight relative to ATR")
    
    # Trade-type soft cap check (log warning but don't reject if within mode bounds)
    if stop_loss.distance_atr > soft_max and stop_loss.distance_atr <= max_stop_atr:
        logger.warning(f"Stop {stop_loss.distance_atr:.2f} ATR exceeds {expected_trade_type or 'intraday'} soft cap {soft_max:.2f} (within mode bounds)")
    if stop_loss.distance_atr < soft_min and stop_loss.distance_atr >= min_stop_atr:
        logger.warning(f"Stop {stop_loss.distance_atr:.2f} ATR below {expected_trade_type or 'intraday'} soft floor {soft_min:.2f} (within mode bounds)")

    # Apply R:R threshold appropriate for plan type (mode-aware)
    # Pass EV and confluence to enable intelligent override for borderline R:R
    # Mode's min_rr_ratio override takes priority over trade type defaults
    # 2b. Validate Trade Type Compatibility (Structural Integrity)
    # Ensure the derived trade type matches the mode's intended purpose (e.g., No Scalps in Overwatch)
    # Normalize to expected TradePlan literal types
    _dir_lower = direction.lower()
    trade_direction = "LONG" if is_bullish else "SHORT"
    
    # Derive trade type INITIAL (before full target calc, estimated from TP1)
    # We need this early for mode enforcement validation
    # Use TP1 as proxy for target move if targets not fully validated yet
    # Or better, move target calculation logic UP, or use temporary estimate
    
    # --- Minimum Target Move % Check (needed for derivation) ---
    min_target_move_pct = getattr(config, 'min_target_move_pct', 0.0)
    tp1_move_pct = abs(targets[0].level - current_price) / max(current_price, 1e-12) * 100.0
    
    # Derive trade type from setup characteristics
    structure_tfs = getattr(config, 'structure_timeframes', ())
    trade_setup = _derive_trade_type(
        target_move_pct=tp1_move_pct,
        stop_distance_atr=stop_loss.distance_atr,
        structure_timeframes=structure_tfs,
        primary_tf=primary_tf
    )
    logger.debug(f"Derived trade_type={trade_setup} from target_move={tp1_move_pct:.2f}%, stop_atr={stop_loss.distance_atr:.2f}, structure_tfs={structure_tfs}")

    allowed_types = getattr(config, 'allowed_trade_types', None)
    logger.info("🎯 Trade type check: derived=%s, allowed=%s, profile=%s",
               trade_setup, allowed_types, getattr(config, 'profile', 'unknown'))
    
    # MODE-AWARE TRADE TYPE CLAMPING
    # If derived type isn't allowed, try to downgrade to an allowed type instead of rejecting
    # This handles cases where target move is large but mode is precision-focused
    if allowed_types and trade_setup not in allowed_types:
        # Priority order for downgrade: intraday > scalp > swing
        downgrade_priority = ['intraday', 'scalp', 'swing']
        clamped_type = None
        for fallback in downgrade_priority:
            if fallback in allowed_types:
                clamped_type = fallback
                break
        
        if clamped_type:
            logger.info("⚡ %s: Trade type clamped from '%s' to '%s' (mode %s only allows %s)",
                       symbol, trade_setup, clamped_type, config.profile, allowed_types)
            trade_setup = clamped_type
        else:
            # No valid fallback - this shouldn't happen unless allowed_types is malformed
            logger.info("❌ %s: Plan rejected - Type '%s' not allowed in %s mode (allowed: %s)", 
                       symbol, trade_setup, config.profile, allowed_types)
            raise ValueError(f"Trade type '{trade_setup}' not allowed in {config.profile} mode (allowed: {allowed_types})")

    mode_overrides = getattr(config, 'overrides', None) or {}
    min_rr_override = mode_overrides.get('min_rr_ratio')
    
    # Use derived 'trade_setup' for validation so we validate the PLAN as it actually is,
    # rather than as we hoped it would be. This prevents rejecting valid Swing setups in Intraday mode.
    is_valid_rr, rr_reason = validate_rr(
        plan_type, 
        risk_reward, 
        mode_profile=config.profile,
        expected_value=expected_value,
        confluence_score=confluence_breakdown.total_score,
        trade_type=trade_setup,  # CHANGED: Use derived type
        min_rr_override=min_rr_override
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
    # Derive trade type already done above for validation
    # structure_tfs = getattr(config, 'structure_timeframes', ())
    # trade_setup = _derive_trade_type(...)
    
    # Log telemetry when derived type differs from expected (helps tune mode definitions)
    if expected_trade_type and trade_setup != expected_trade_type:
        logger.info(f"Trade type mismatch: expected={expected_trade_type}, derived={trade_setup} for {symbol}")
        telemetry.log_event({
            "event_type": "trade_type_mismatch",
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": symbol,
            "expected_trade_type": expected_trade_type,
            "derived_trade_type": trade_setup,
            "target_move_pct": tp1_move_pct,
            "stop_distance_atr": stop_loss.distance_atr,
            "structure_timeframes": list(structure_tfs),
            "primary_tf": primary_tf,
            "mode_profile": config.profile
        })

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
    
    # DEBUG: Log entry zone validation details
    logger.info("🔍 ENTRY ZONE VALIDATION: price=%.2f, near=%.2f, far=%.2f, is_bullish=%s",
                current_price, entry_zone.near_entry, entry_zone.far_entry, is_bullish)
    
    # Allow equality (touch) as valid; only reject if strictly above for bullish
    if is_bullish and entry_zone.near_entry > current_price:
        logger.warning("❌ REJECTED: Bullish near_entry (%.2f) > current_price (%.2f) - entry zone is ABOVE price!",
                       entry_zone.near_entry, current_price)
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

    # Apply HTF Fib alignment boost to confidence (capped at 100)
    final_confidence = min(100.0, confluence_breakdown.total_score + htf_fib_boost)
    
    trade_plan = TradePlan(
        symbol=symbol,
        direction=trade_direction,
        setup_type=cast(Literal['scalp', 'swing', 'intraday'], trade_setup),
        entry_zone=entry_zone,
        stop_loss=stop_loss,
        targets=targets,
        risk_reward=risk_reward,
        confidence_score=final_confidence,
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
            "htf_fib_alignment": {
                "aligned": htf_fib_boost > 0,
                "note": htf_fib_note,
                "boost": htf_fib_boost
            } if htf_fib_boost > 0 else None,
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
    # DEBUG: Log all OB details before filtering
    for ob in smc_snapshot.order_blocks:
        logger.critical(f"  OB: dir={ob.direction} tf={ob.timeframe} low={ob.low:.2f} high={ob.high:.2f}")
    
    # Find relevant order block or FVG
    allowed_tfs = _get_allowed_entry_tfs(config)  # CHANGED: Use entry TFs, not structure TFs
    
    if is_bullish:
        # Look for bullish OB or FVG below current price (OR we are inside it)
        # Fix: Allowed if we haven't broken the low. Being inside (high >= price >= low) is GOOD.
        obs = [ob for ob in smc_snapshot.order_blocks if ob.direction == "bullish" and ob.low < current_price]
        # Filter to allowed ENTRY timeframes if specified
        if allowed_tfs:
            # Normalize timeframe case (OBs may have '1H', config has '1h')
            obs = [ob for ob in obs if ob.timeframe.lower() in allowed_tfs]
            logger.debug(f"Filtered bullish OBs to entry_timeframes {allowed_tfs}: {len(obs)} remain")
        # Filter out OBs too far (distance constraint)
        max_pullback_atr = getattr(config, "max_pullback_atr", 3.0)
        # Fix: If inside OB (price <= high), distance is 0.
        obs = [ob for ob in obs if (max(0.0, current_price - ob.high) / atr) <= max_pullback_atr]
        # Filter out heavily mitigated OBs
        obs = [ob for ob in obs if ob.mitigation_level <= planner_cfg.ob_mitigation_max]
        # Validate OB integrity (not broken / not currently tapped)
        if multi_tf_data and primary_tf in getattr(multi_tf_data, 'timeframes', {}):
            df_primary = multi_tf_data.timeframes[primary_tf]
            validated = []
            for ob in obs:
                # Ensure price hasn't broken the OB
                if current_price >= ob.low:
                    validated.append(ob)
                else:
                    logger.debug(f"Filtered invalid bullish OB (broken or tapped): low={ob.low} high={ob.high} ts={ob.timestamp}")
            obs = validated
        
        # NOTE: Removed Grade A/B filter - confluence scoring already penalizes weak OBs.
        # If a symbol passes the confluence gate (70%+), entry zone should be allowed.
        # Double-filtering was blocking valid high-confluence setups with weaker individual OBs.
        logger.debug(f"Bullish OBs for entry zone: {len(obs)} (all grades allowed, confluence handles quality)")

        # NEW: Validate LTF OBs have HTF backing (Top-Down Confirmation)
        # SKIP for Surgical mode - precision entries can use isolated LTF OBs
        # (confluence scoring will still penalize weak setups)
        skip_htf_backing = config.profile in ('precision', 'surgical')
        
        if skip_htf_backing:
            logger.debug("HTF backing filter SKIPPED for bullish OBs (%s mode)", config.profile)
        else:
            # Prevent taking 5m/15m entries in empty space
            validated_backing = []
            ltf_tfs = ('1m', '5m', '15m')
            htf_tfs = ('1h', '4h', '1d', '1w')
            
            for ob in obs:
                if ob.timeframe in ltf_tfs:
                    # Check for overlapping HTF structure (OB or FVG)
                    has_backing = False
                    
                    # Check OBs
                    for htf_ob in smc_snapshot.order_blocks:
                        if htf_ob.timeframe in htf_tfs and htf_ob.direction == "bullish":
                            # Check overlap: LTF OB inside or touching HTF OB
                            if (htf_ob.low <= ob.high and htf_ob.high >= ob.low):
                                has_backing = True
                                break
                                
                    # Check FVGs if no OB backing
                    if not has_backing:
                        for htf_fvg in smc_snapshot.fvgs:
                             if htf_fvg.timeframe in htf_tfs and htf_fvg.direction == "bullish":
                                if (htf_fvg.bottom <= ob.high and htf_fvg.top >= ob.low): # FVG bottom/top are low/high
                                    has_backing = True
                                    break
                    
                    if has_backing:
                        validated_backing.append(ob)
                    else:
                        logger.debug(f"Filtered isolated LTF OB (no HTF backing): {ob.timeframe} at {ob.low}")
                else:
                    # MTF/HTF OBs are self-validating or handled by structure scoring
                    validated_backing.append(ob)
            obs = validated_backing
        
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
            
            # FIX: When price is INSIDE the OB (already pulled back), cap near_entry at current price
            # This allows immediate entry instead of rejecting as "entry above price"
            price_inside_ob = current_price <= best_ob.high and current_price >= best_ob.low
            if near_entry > current_price:
                logger.info("📦 ENTRY ZONE FIX: near_entry (%.2f) > price (%.2f), capping at price (inside OB: %s)",
                            near_entry, current_price, price_inside_ob)
                near_entry = current_price  # Allow entry at current price
                
            logger.info("📦 ENTRY ZONE CALC: OB=[%.2f-%.2f] | offset=%.2f (base=%.2f * htf=%.2f * atr=%.2f) | near=%.2f, far=%.2f | price=%.2f",
                        best_ob.low, best_ob.high, offset, base_offset, htf_factor, atr, near_entry, far_entry, current_price)
            
            rationale = f"Entry zone based on {best_ob.timeframe} bullish order block"
            if price_inside_ob:
                rationale += " (price inside OB - immediate entry)"
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
            
            # FIX: Cap near_entry at current price if calculated above
            if near_entry > current_price:
                logger.info("📦 FVG ENTRY FIX: near_entry (%.2f) > price (%.2f), capping at price",
                            near_entry, current_price)
                near_entry = current_price
                
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
            # NEW: Overwatch Gate with Volatility Exception
            # Swing modes do NOT take random ATR pullbacks - must have structure
            # EXCEPTION: If regime is EXPLOSIVE/ELEVATED, structure lags price.
            # We MUST allow ATR fallback to catch crashes/pumps.
            
            regime = _classify_atr_regime(atr, current_price, planner_cfg)
            
            if config.profile in ('overwatch', 'macro_surveillance'):
                if regime in ('explosive', 'elevated'):
                    # High volatility - structure can't form fast enough
                    logger.info(
                        "⚠️ Overwatch Exception: %s volatility detected. Allowing ATR fallback despite no structure.",
                        regime.upper()
                    )
                else:
                    # Normal/compressed volatility - require structure
                    logger.info("⛔ Overwatch Gate: No valid Bullish OB/FVG structure & low volatility. Rejecting trade.")
                    raise ValueError("Overwatch mode requires valid HTF structure for entry (no ATR fallback)")

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
        # Look for bearish OB or FVG above current price (OR we are inside it)
        # Fix: Allowed if we haven't broken the high. Being inside (low <= price <= high) is GOOD.
        obs = [ob for ob in smc_snapshot.order_blocks if ob.direction == "bearish" and ob.high > current_price]
        # Filter to allowed ENTRY timeframes if specified
        if allowed_tfs:
            # Normalize timeframe case (OBs may have '1H', config has '1h')
            obs = [ob for ob in obs if ob.timeframe.lower() in allowed_tfs]
            logger.debug(f"Filtered bearish OBs to entry_timeframes {allowed_tfs}: {len(obs)} remain")
        max_pullback_atr = getattr(config, "max_pullback_atr", 3.0)
        # Fix: If inside OB (price >= low), distance is 0.
        obs = [ob for ob in obs if (max(0.0, ob.low - current_price) / atr) <= max_pullback_atr]
        # Filter out heavily mitigated OBs
        obs = [ob for ob in obs if ob.mitigation_level <= planner_cfg.ob_mitigation_max]
        if multi_tf_data and primary_tf in getattr(multi_tf_data, 'timeframes', {}):
            df_primary = multi_tf_data.timeframes[primary_tf]
            validated_b = []
            for ob in obs:
                # Ensure price hasn't broken the OB
                if current_price <= ob.high:
                    validated_b.append(ob)
                else:
                    logger.debug(f"Filtered invalid bearish OB (broken or tapped): low={ob.low} high={ob.high} ts={ob.timestamp}")
            obs = validated_b
            
        # NOTE: Removed Grade A/B filter - confluence scoring already penalizes weak OBs.
        # If a symbol passes the confluence gate (70%+), entry zone should be allowed.
        logger.debug(f"Bearish OBs for entry zone: {len(obs)} (all grades allowed, confluence handles quality)")

        # NEW: Validate LTF OBs have HTF backing (Top-Down Confirmation)
        # SKIP for Surgical mode - precision entries can use isolated LTF OBs
        skip_htf_backing = config.profile in ('precision', 'surgical')
        
        if skip_htf_backing:
            logger.debug("HTF backing filter SKIPPED for bearish OBs (%s mode)", config.profile)
        else:
            validated_backing = []
            ltf_tfs = ('1m', '5m', '15m')
            htf_tfs = ('1h', '4h', '1d', '1w')
            
            for ob in obs:
                if ob.timeframe in ltf_tfs:
                    has_backing = False
                    # Check OBs
                    for htf_ob in smc_snapshot.order_blocks:
                        if htf_ob.timeframe in htf_tfs and htf_ob.direction == "bearish":
                            if (htf_ob.low <= ob.high and htf_ob.high >= ob.low):
                                has_backing = True
                                break
                    # Check FVGs
                    if not has_backing:
                        for htf_fvg in smc_snapshot.fvgs:
                             if htf_fvg.timeframe in htf_tfs and htf_fvg.direction == "bearish":
                                if (htf_fvg.bottom <= ob.high and htf_fvg.top >= ob.low):
                                    has_backing = True
                                    break
                    
                    if has_backing:
                        validated_backing.append(ob)
                    else:
                        logger.debug(f"Filtered isolated LTF Bearish OB: {ob.timeframe} at {ob.high}")
                else:
                    validated_backing.append(ob)
            obs = validated_backing
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
            
            # FIX: For shorts, cap near_entry at current price if calculated below
            # (price is inside OB, allow immediate short entry)
            price_inside_ob = current_price >= best_ob.low and current_price <= best_ob.high
            if near_entry < current_price:
                logger.info("📦 BEARISH ENTRY FIX: near_entry (%.2f) < price (%.2f), capping at price (inside OB: %s)",
                            near_entry, current_price, price_inside_ob)
                near_entry = current_price
                
            rationale = f"Entry zone based on {best_ob.timeframe} bearish order block"
            if price_inside_ob:
                rationale += " (price inside OB - immediate entry)"
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
            # NEW: Overwatch Gate with Volatility Exception (Bearish)
            # Swing modes do NOT take random ATR pullbacks - must have structure
            # EXCEPTION: If regime is EXPLOSIVE/ELEVATED, structure lags price.
            
            regime = _classify_atr_regime(atr, current_price, planner_cfg)
            
            if config.profile in ('overwatch', 'macro_surveillance'):
                if regime in ('explosive', 'elevated'):
                    # High volatility - structure can't form fast enough
                    logger.info(
                        "⚠️ Overwatch Exception: %s volatility detected. Allowing ATR fallback despite no structure.",
                        regime.upper()
                    )
                else:
                    # Normal/compressed volatility - require structure
                    logger.info("⛔ Overwatch Gate: No valid Bearish OB/FVG structure & low volatility. Rejecting trade.")
                    raise ValueError("Overwatch mode requires valid HTF structure for entry (no ATR fallback)")

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
    lookback: int,
    timeframe: Optional[str] = None
) -> Optional[float]:
    """
    Find swing high or swing low from price action.
    
    Uses a tiered approach:
    1. Try to find strict swing (2 bars before/after)
    2. Fall back to relaxed swing (1 bar before/after)
    3. Fall back to simple min/max in the lookback period
    
    Args:
        is_bullish: If True, find swing low (for stop). If False, find swing high.
        reference_price: Entry price to anchor search from
        candles_df: OHLCV dataframe for the timeframe
        lookback: Base number of bars to search back (scaled by timeframe)
        timeframe: Timeframe string for lookback scaling (e.g., '5m', '4h', '1d')
        
    Returns:
        Swing level price or None if no valid level found
    """
    if candles_df is None or len(candles_df) < 5:
        return None
    
    # Scale lookback based on timeframe (LTF needs more bars, HTF needs fewer)
    scaled_lookback = scale_lookback(lookback, timeframe) if timeframe else lookback
    
    # Use last N candles
    recent = candles_df.tail(scaled_lookback)
    
    if is_bullish:
        # Find swing lows below reference price
        # Tier 1: Strict swing (2 bars before/after)
        strict_swing_lows = []
        for i in range(2, len(recent) - 2):
            low = recent.iloc[i]['low']
            if (low < recent.iloc[i-1]['low'] and 
                low < recent.iloc[i-2]['low'] and
                low < recent.iloc[i+1]['low'] and 
                low < recent.iloc[i+2]['low'] and
                low < reference_price):
                strict_swing_lows.append(low)
        
        if strict_swing_lows:
            return max(strict_swing_lows)  # Highest swing low (closest to entry)
        
        # Tier 2: Relaxed swing (1 bar before/after)
        relaxed_swing_lows = []
        for i in range(1, len(recent) - 1):
            low = recent.iloc[i]['low']
            if (low < recent.iloc[i-1]['low'] and 
                low < recent.iloc[i+1]['low'] and
                low < reference_price):
                relaxed_swing_lows.append(low)
        
        if relaxed_swing_lows:
            return max(relaxed_swing_lows)  # Highest swing low (closest to entry)
        
        # Tier 3: Simple minimum below reference price
        below_price = recent[recent['low'] < reference_price]['low']
        if len(below_price) > 0:
            return below_price.min()  # Absolute lowest point as stop
        
        return None
    
    else:  # bearish - find swing highs above reference price
        # Tier 1: Strict swing (2 bars before/after)
        strict_swing_highs = []
        for i in range(2, len(recent) - 2):
            high = recent.iloc[i]['high']
            if (high > recent.iloc[i-1]['high'] and 
                high > recent.iloc[i-2]['high'] and
                high > recent.iloc[i+1]['high'] and 
                high > recent.iloc[i+2]['high'] and
                high > reference_price):
                strict_swing_highs.append(high)
        
        if strict_swing_highs:
            return min(strict_swing_highs)  # Lowest swing high (closest to entry)
        
        # Tier 2: Relaxed swing (1 bar before/after)
        relaxed_swing_highs = []
        for i in range(1, len(recent) - 1):
            high = recent.iloc[i]['high']
            if (high > recent.iloc[i-1]['high'] and 
                high > recent.iloc[i+1]['high'] and
                high > reference_price):
                relaxed_swing_highs.append(high)
        
        if relaxed_swing_highs:
            return min(relaxed_swing_highs)  # Lowest swing high (closest to entry)
        
        # Tier 3: Simple maximum above reference price
        above_price = recent[recent['high'] > reference_price]['high']
        if len(above_price) > 0:
            return above_price.max()  # Absolute highest point as stop
        
        return None


def _calculate_stop_loss(
    is_bullish: bool,
    entry_zone: EntryZone,
    smc_snapshot: SMCSnapshot,
    atr: float,
    primary_tf: str,
    setup_archetype: SetupArchetype,
    config: ScanConfig,
    planner_cfg: PlannerConfig,
    multi_tf_data: Optional[MultiTimeframeData] = None,
    current_price: Optional[float] = None,  # NEW: for regime-aware buffer
    indicators_by_tf: Optional[dict] = None  # NEW: for structure-TF ATR lookup
) -> tuple[StopLoss, bool]:
    """
    Calculate structure-based stop loss.
    
    Never arbitrary - always beyond invalidation point.
    NOW with dynamic regime-aware stop buffer (Issue #3 fix).
    NOW with structure-TF ATR normalization (prevents ATR mismatch rejections).
    
    Returns:
        Tuple of (StopLoss, used_structure_flag)
    """
    # Direction provided via is_bullish
    allowed_tfs = _get_allowed_stop_tfs(config)  # CHANGED: Use stop_timeframes, not structure_timeframes
    structure_tf_used = None  # Track which TF provided stop
    
    # === DYNAMIC STOP BUFFER BASED ON ATR REGIME (Issue #3 fix) ===
    # Calculate regime-aware stop buffer instead of static value
    if current_price and current_price > 0:
        regime = _classify_atr_regime(atr, current_price, planner_cfg)
        stop_buffer = planner_cfg.stop_buffer_by_regime.get(regime, planner_cfg.stop_buffer_atr)
        logger.debug(f"Using regime-aware stop buffer: {regime} -> {stop_buffer:.3f} ATR")
    else:
        stop_buffer = planner_cfg.stop_buffer_atr
        regime = "unknown"
    
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
            stop_level -= (stop_buffer * atr)  # Dynamic regime-aware buffer beyond structure
            rationale = f"Stop below {structure_tf_used} entry structure invalidation point"
            logger.debug(f"Using structure-based stop: {stop_level} from {structure_tf_used} (before buffer: {max(valid_stops, key=lambda x: x[0])[0]})")
            
            # === STRUCTURE-TF ATR NORMALIZATION ===
            # Use the structure's TF ATR for distance calculation, not primary TF ATR
            # This prevents "stop too wide" rejections when stop comes from HTF structure
            structure_atr = atr  # Default to primary ATR
            if indicators_by_tf and structure_tf_used:
                # Look up structure TF's ATR (try exact match, then lowercase)
                structure_tf_lower = structure_tf_used.lower()
                if structure_tf_used in indicators_by_tf and indicators_by_tf[structure_tf_used].atr:
                    structure_atr = indicators_by_tf[structure_tf_used].atr
                    logger.debug(f"Using structure TF {structure_tf_used} ATR={structure_atr:.4f} for distance calc")
                elif structure_tf_lower in indicators_by_tf and indicators_by_tf[structure_tf_lower].atr:
                    structure_atr = indicators_by_tf[structure_tf_lower].atr
                    logger.debug(f"Using structure TF {structure_tf_lower} ATR={structure_atr:.4f} for distance calc")
            
            distance_atr = (entry_zone.far_entry - stop_level) / structure_atr
            used_structure = True
        else:
            # === NEW TIER: Entry OB Edge-Based Stop ===
            # If no separate OBs below entry, use an entry OB's low as invalidation
            # CRITICAL: OB low must be BELOW entry, otherwise stop would be above entry!
            entry_obs = [ob for ob in smc_snapshot.order_blocks 
                        if ob.direction == "bullish" and ob.low < entry_zone.far_entry]
            
            if entry_obs:
                # Use the OB with highest low (closest to entry but still below)
                best_entry_ob = max(entry_obs, key=lambda ob: ob.low)
                
                # Stop below the OB's low edge (invalidation point)
                stop_level = best_entry_ob.low - (stop_buffer * atr)
                structure_tf_used = best_entry_ob.timeframe
                rationale = f"Stop below {structure_tf_used} entry OB low (invalidation edge)"
                distance_atr = (entry_zone.far_entry - stop_level) / atr
                used_structure = True
                logger.info(f"Using entry OB edge stop: OB low={best_entry_ob.low}, stop={stop_level}, entry_far={entry_zone.far_entry}")

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
                        lookback=planner_cfg.stop_lookback_bars,
                        timeframe=primary_tf
                    )
                
                # Try HTF if enabled and primary failed (MODE-AWARE HTF FILTERING)
                if swing_level is None and planner_cfg.stop_use_htf_swings and multi_tf_data:
                    # Get mode-specific HTF allowlist from config overrides or planner_cfg
                    mode_profile = getattr(config, 'profile', 'balanced')
                    htf_allowed = planner_cfg.htf_swing_allowed.get(mode_profile, ('4h', '1h', '1d'))
                    # Also check config.overrides for htf_swing_allowed
                    overrides = getattr(config, 'overrides', None) or {}
                    if 'htf_swing_allowed' in overrides:
                        htf_allowed = overrides['htf_swing_allowed']
                    
                    htf_candidates = ['4h', '4H', '1d', '1D', '1w', '1W']
                    for htf in htf_candidates:
                        # Skip HTFs not in allowlist for this mode
                        htf_lower = htf.lower()
                        if htf_lower not in [h.lower() for h in htf_allowed]:
                            logger.debug(f"Skipping HTF {htf} - not in allowlist {htf_allowed} for {mode_profile}")
                            continue
                        if htf in multi_tf_data.timeframes:
                            candles_df = multi_tf_data.timeframes[htf]
                            swing_level = _find_swing_level(
                                is_bullish=True,
                                reference_price=entry_zone.far_entry,
                                candles_df=candles_df,
                                lookback=planner_cfg.stop_lookback_bars,  # Same base, scaled by timeframe
                                timeframe=htf
                            )
                            if swing_level:
                                logger.info(f"Found HTF swing on {htf}")
                                break
                
                if swing_level:
                    stop_level = swing_level - (stop_buffer * atr)  # Dynamic regime-aware buffer below swing
                    rationale = f"Stop below swing low (no SMC structure)"
                    distance_atr = (entry_zone.far_entry - stop_level) / atr
                    used_structure = False  # Swing level, not SMC structure
                    logger.info(f"Using swing-based stop: {stop_level}")
                else:
                    # Emergency ATR fallback for scalp modes (precision/intraday_aggressive)
                    mode_profile = getattr(config, 'profile', 'balanced')
                    overrides = getattr(config, 'overrides', None) or {}
                    emergency_atr_fallback = overrides.get('emergency_atr_fallback', False)
                    
                    if emergency_atr_fallback:
                        # Use ATR-based stop for scalp modes when no structure/swing found
                        fallback_atr_mult = 1.5  # Conservative fallback
                        stop_level = entry_zone.far_entry - (fallback_atr_mult * atr)
                        rationale = f"Emergency ATR fallback ({fallback_atr_mult}x ATR) - no swing structure found"
                        distance_atr = fallback_atr_mult
                        used_structure = False
                        logger.warning(f"Using emergency ATR fallback stop: {stop_level} for {mode_profile} mode")
                    else:
                        # Last resort: reject trade
                        logger.warning(f"No swing level found - rejecting trade")
                        raise ValueError("Cannot generate trade plan: no clear structure or swing level for stop loss placement")
    
    else:  # bearish
        # Stop above the entry structure
        # For SHORT: stop must be ABOVE near_entry (the higher edge where we enter the short)
        potential_stops = []
        
        for ob in smc_snapshot.order_blocks:
            # Filter to allowed structure timeframes if specified
            if allowed_tfs and ob.timeframe not in allowed_tfs:
                continue
            # Look for bearish OBs (supply zones) ABOVE our entry zone
            # These represent invalidation levels - if price breaks above, our short is wrong
            if ob.direction == "bearish" and ob.high > entry_zone.near_entry:
                potential_stops.append((ob.high, ob.timeframe))
        
        for fvg in smc_snapshot.fvgs:
            # Filter to allowed structure timeframes if specified
            if allowed_tfs and fvg.timeframe not in allowed_tfs:
                continue
            if fvg.direction == "bearish" and fvg.top > entry_zone.near_entry:
                potential_stops.append((fvg.top, fvg.timeframe))
        
        # Filter stops that are actually above entry (must be above near_entry for shorts)
        valid_stops = [(level, tf) for level, tf in potential_stops if level > entry_zone.near_entry]
        
        if valid_stops:
            # Use closest structure above entry (lowest of the valid stops)
            stop_level, structure_tf_used = min(valid_stops, key=lambda x: x[0])
            stop_level += (stop_buffer * atr)  # Dynamic regime-aware buffer beyond structure
            rationale = f"Stop above {structure_tf_used} entry structure invalidation point"
            
            # === STRUCTURE-TF ATR NORMALIZATION ===
            # Use the structure's TF ATR for distance calculation, not primary TF ATR
            structure_atr = atr  # Default to primary ATR
            if indicators_by_tf and structure_tf_used:
                structure_tf_lower = structure_tf_used.lower()
                if structure_tf_used in indicators_by_tf and indicators_by_tf[structure_tf_used].atr:
                    structure_atr = indicators_by_tf[structure_tf_used].atr
                    logger.debug(f"Using structure TF {structure_tf_used} ATR={structure_atr:.4f} for distance calc")
                elif structure_tf_lower in indicators_by_tf and indicators_by_tf[structure_tf_lower].atr:
                    structure_atr = indicators_by_tf[structure_tf_lower].atr
                    logger.debug(f"Using structure TF {structure_tf_lower} ATR={structure_atr:.4f} for distance calc")
            
            distance_atr = (stop_level - entry_zone.near_entry) / structure_atr
            used_structure = True
        else:
            # === NEW TIER: Entry OB Edge-Based Stop ===
            # If no separate OBs above entry, use an entry OB's high as invalidation
            # CRITICAL: OB high must be ABOVE entry, otherwise stop would be below entry!
            entry_obs = [ob for ob in smc_snapshot.order_blocks 
                        if ob.direction == "bearish" and ob.high > entry_zone.near_entry]
            
            if entry_obs:
                # Use the OB with lowest high (closest to entry but still above)
                best_entry_ob = min(entry_obs, key=lambda ob: ob.high)
                
                # Stop above the OB's high edge (invalidation point)
                stop_level = best_entry_ob.high + (stop_buffer * atr)
                structure_tf_used = best_entry_ob.timeframe
                rationale = f"Stop above {structure_tf_used} entry OB high (invalidation edge)"
                distance_atr = (stop_level - entry_zone.near_entry) / atr
                used_structure = True
                logger.info(f"Using entry OB edge stop: OB high={best_entry_ob.high}, stop={stop_level}, entry_near={entry_zone.near_entry}")

            else:
                # Fallback: swing-based stop from primary timeframe, then HTF if needed
                logger.info(f"No SMC structure for stop - attempting swing-based fallback")
                swing_level = None
                
                # Try primary timeframe first
                if multi_tf_data and primary_tf in multi_tf_data.timeframes:
                    candles_df = multi_tf_data.timeframes[primary_tf]
                    swing_level = _find_swing_level(
                        is_bullish=False,
                        reference_price=entry_zone.near_entry,  # For shorts, find swing above near_entry
                        candles_df=candles_df,
                        lookback=planner_cfg.stop_lookback_bars,
                        timeframe=primary_tf
                    )
                
                # Try HTF if enabled and primary failed (MODE-AWARE HTF FILTERING)
                if swing_level is None and planner_cfg.stop_use_htf_swings and multi_tf_data:
                    # Get mode-specific HTF allowlist from config overrides or planner_cfg
                    mode_profile = getattr(config, 'profile', 'balanced')
                    htf_allowed = planner_cfg.htf_swing_allowed.get(mode_profile, ('4h', '1h', '1d'))
                    # Also check config.overrides for htf_swing_allowed
                    overrides = getattr(config, 'overrides', None) or {}
                    if 'htf_swing_allowed' in overrides:
                        htf_allowed = overrides['htf_swing_allowed']
                    
                    htf_candidates = ['4h', '4H', '1d', '1D', '1w', '1W']
                    for htf in htf_candidates:
                        # Skip HTFs not in allowlist for this mode
                        htf_lower = htf.lower()
                        if htf_lower not in [h.lower() for h in htf_allowed]:
                            logger.debug(f"Skipping HTF {htf} - not in allowlist {htf_allowed} for {mode_profile}")
                            continue
                        if htf in multi_tf_data.timeframes:
                            candles_df = multi_tf_data.timeframes[htf]
                            swing_level = _find_swing_level(
                                is_bullish=False,
                                reference_price=entry_zone.near_entry,  # For shorts, find swing above near_entry
                                candles_df=candles_df,
                                lookback=planner_cfg.stop_lookback_bars,  # Same base, scaled by timeframe
                                timeframe=htf
                            )
                            if swing_level:
                                logger.info(f"Found HTF swing on {htf}")
                                break
                
                if swing_level:
                    stop_level = swing_level + (stop_buffer * atr)  # Dynamic regime-aware buffer above swing
                    rationale = f"Stop above swing high (no SMC structure)"
                    distance_atr = (stop_level - entry_zone.near_entry) / atr  # Use near_entry for shorts
                    used_structure = False  # Swing level, not SMC structure
                    logger.info(f"Using swing-based stop: {stop_level}")
                else:
                    # Emergency ATR fallback for scalp modes (precision/intraday_aggressive)
                    mode_profile = getattr(config, 'profile', 'balanced')
                    overrides = getattr(config, 'overrides', None) or {}
                    emergency_atr_fallback = overrides.get('emergency_atr_fallback', False)
                    
                    if emergency_atr_fallback:
                        # Use ATR-based stop for scalp modes when no structure/swing found
                        fallback_atr_mult = 1.5  # Conservative fallback
                        stop_level = entry_zone.near_entry + (fallback_atr_mult * atr)  # Use near_entry for shorts
                        rationale = f"Emergency ATR fallback ({fallback_atr_mult}x ATR) - no swing structure found"
                        distance_atr = fallback_atr_mult
                        used_structure = False
                        logger.warning(f"Using emergency ATR fallback stop: {stop_level} for {mode_profile} mode")
                    else:
                        # Last resort: reject trade
                        logger.warning(f"No swing level found - rejecting trade")
                        raise ValueError("Cannot generate trade plan: no clear structure or swing level for stop loss placement")
    
    # CRITICAL DEBUG
    logger.critical(f"STOP CALC: is_bullish={is_bullish}, entry_near={entry_zone.near_entry}, entry_far={entry_zone.far_entry}, stop={stop_level}, atr={atr}")
    
    # === STOP DIRECTION VALIDATION ===
    # Ensure stop is on the correct side of entry for the trade direction
    if is_bullish:
        # For LONG: stop must be BELOW entry
        if stop_level >= entry_zone.far_entry:
            logger.error(f"Invalid LONG stop: stop {stop_level} >= entry {entry_zone.far_entry}")
            raise ValueError(f"LONG: Stop ({stop_level:.6f}) must be < entry ({entry_zone.far_entry:.6f})")
    else:
        # For SHORT: stop must be ABOVE entry
        if stop_level <= entry_zone.far_entry:
            logger.error(f"Invalid SHORT stop: stop {stop_level} <= entry {entry_zone.far_entry}")
            raise ValueError(f"SHORT: Stop ({stop_level:.6f}) must be > entry ({entry_zone.far_entry:.6f})")
    
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
        
        # Add key levels as resistance targets (PWH, PDH)
        if smc_snapshot.key_levels:
            kl = smc_snapshot.key_levels
            if kl.get('pdh') and kl['pdh'].get('price', 0) > avg_entry:
                resistances.append(kl['pdh']['price'])
            if kl.get('pwh') and kl['pwh'].get('price', 0) > avg_entry:
                resistances.append(kl['pwh']['price'])
        
        # Target 1: Clip to resistance only if still meets minimum R:R threshold
        if resistances and min(resistances) < target1_rr:
            nearest_resist = min(resistances)
            clipped_rr = (nearest_resist - avg_entry) / risk_distance if risk_distance > 0 else 0
            # Only clip to resistance if resulting R:R >= minimum threshold
            if clipped_rr >= planner_cfg.target_min_rr_after_clip:
                target1_level = nearest_resist
                target1_rationale = f"Nearest bearish structure (resistance) clipped RR≈{clipped_rr:.2f}"
            else:
                # Resistance too close - use theoretical target instead
                target1_level = target1_rr
                target1_rationale = f"Conservative {rr_levels[0]:.1f}R target (resistance @ {nearest_resist:.2f} too close)"
        else:
            target1_level = target1_rr
            target1_rationale = f"Conservative {rr_levels[0]:.1f}R target"
        
        targets.append(Target(
            level=target1_level,
            percentage=50.0,
            rationale=f"{target1_rationale}"
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
        
        # Add key levels as support targets (PWL, PDL)
        if smc_snapshot.key_levels:
            kl = smc_snapshot.key_levels
            if kl.get('pdl') and kl['pdl'].get('price', 0) < avg_entry:
                supports.append(kl['pdl']['price'])
            if kl.get('pwl') and kl['pwl'].get('price', 0) < avg_entry:
                supports.append(kl['pwl']['price'])
        
        # Target 1: Clip to support only if still meets minimum R:R threshold
        if supports and max(supports) > target1_rr:
            nearest_support = max(supports)
            clipped_rr = (avg_entry - nearest_support) / risk_distance if risk_distance > 0 else 0
            # Only clip to support if resulting R:R >= minimum threshold
            if clipped_rr >= planner_cfg.target_min_rr_after_clip:
                target1_level = nearest_support
                target1_rationale = f"Nearest bullish structure (support) clipped RR≈{clipped_rr:.2f}"
            else:
                # Support too close - use theoretical target instead
                target1_level = target1_rr
                target1_rationale = f"Conservative {rr_levels[0]:.1f}R target (support @ {nearest_support:.2f} too close)"
        else:
            target1_level = target1_rr
            target1_rationale = f"Conservative {rr_levels[0]:.1f}R target"
        
        targets.append(Target(
            level=target1_level,
            percentage=50.0,
            rationale=f"{target1_rationale}"
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
    
    # === PRE-TARGET VALIDATION (NEW - catches negative/invalid targets) ===
    # Validate all targets are positive and in correct direction
    validated_targets = []
    for i, target in enumerate(targets):
        # Check for negative/zero targets
        if target.level <= 0:
            logger.warning(f"Target {i+1} has invalid level {target.level:.6f} - skipping")
            continue
        
        # Check direction validity
        if is_bullish and target.level <= avg_entry:
            logger.warning(f"Bullish target {i+1} at {target.level:.6f} <= avg_entry {avg_entry:.6f} - skipping")
            continue
        if not is_bullish and target.level >= avg_entry:
            logger.warning(f"Bearish target {i+1} at {target.level:.6f} >= avg_entry {avg_entry:.6f} - skipping")
            continue
        
        validated_targets.append(target)
    
    # Must have at least one valid target
    if len(validated_targets) == 0:
        logger.error(f"All targets invalid - entry={avg_entry:.6f}, stop={stop_loss.level:.6f}, risk_dist={risk_distance:.6f}")
        raise ValueError("Cannot generate valid targets: all computed targets failed validation")
    
    # Warn if some targets were filtered
    if len(validated_targets) < len(targets):
        logger.warning(f"Filtered {len(targets) - len(validated_targets)} invalid targets")
    
    return validated_targets


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
