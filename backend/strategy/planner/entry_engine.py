"""
Entry Engine Module

Handles entry zone calculation and validation for the Trade Planner, including:
- Dual Entry Calculation (Near/Far)
- Order Block Validation (Mitigation, Breaches)
- Premium/Discount Compliance (Smart Entry)
- Liquidity Sweep Confirmation (Turtle Soup)
"""

import logging
from typing import Optional, List, Literal, cast
import pandas as pd

from backend.shared.models.planner import EntryZone
from backend.shared.models.data import MultiTimeframeData
from backend.shared.models.smc import SMCSnapshot, OrderBlock, FVG, LiquiditySweep
from backend.shared.models.scoring import ConfluenceBreakdown
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.planner_config import PlannerConfig
from backend.strategy.planner.regime_engine import get_atr_regime, _calculate_htf_bias_factor
from backend.shared.models.indicators import IndicatorSet
from backend.strategy.planner.risk_engine import _get_allowed_entry_tfs

logger = logging.getLogger(__name__)

SetupArchetype = Literal[
    "TREND_OB_PULLBACK",
    "RANGE_REVERSION",
    "SWEEP_REVERSAL",
    "BREAKOUT_RETEST",
]


def _calculate_pullback_probability(
    is_bullish: bool,
    current_price: float,
    entry_zone_mid: float,
    atr: float,
    indicators: Optional[IndicatorSet] = None,
    htf_trend: Optional[str] = None
) -> float:
    """
    Calculate probability that price will pull back to reach entry zone.
    
    Evaluates multiple factors:
    - Distance to entry in ATR units (closer = higher probability)
    - Current momentum direction (aligned = higher probability)
    - HTF trend alignment (aligned = higher probability)
    
    Args:
        is_bullish: True for long (pullback down to entry)
        current_price: Current market price
        entry_zone_mid: Midpoint of entry zone
        atr: Average true range
        indicators: Technical indicators for momentum analysis
        htf_trend: Higher timeframe trend direction
        
    Returns:
        Probability score 0.0-1.0 (0 = unlikely, 1 = very likely)
    """
    if atr <= 0:
        return 0.5  # Default to neutral if no ATR
    
    probability = 0.5  # Start neutral
    
    # 1. DISTANCE FACTOR (40% weight)
    # Closer entries are more likely to be reached
    distance_to_entry = abs(current_price - entry_zone_mid)
    distance_atr = distance_to_entry / atr
    
    if distance_atr <= 0.5:
        # Very close - high probability
        distance_score = 0.9
    elif distance_atr <= 1.0:
        # Within 1 ATR - good probability
        distance_score = 0.75
    elif distance_atr <= 2.0:
        # Within 2 ATR - moderate probability
        distance_score = 0.5
    elif distance_atr <= 3.0:
        # Within 3 ATR - low probability
        distance_score = 0.3
    else:
        # Beyond 3 ATR - very unlikely
        distance_score = 0.1
    
    probability = distance_score * 0.4
    
    # 2. MOMENTUM FACTOR (35% weight)
    # Check if momentum supports pullback direction
    if indicators and indicators.by_timeframe:
        try:
            # Get primary timeframe indicators
            # Prefer 15m/1h for pullback momentum validity
            primary_tf = None
            for tf_candidate in ['15m', '1h', '5m', '4h', '1d']:
                if tf_candidate in indicators.by_timeframe:
                    primary_tf = tf_candidate
                    break
            
            if not primary_tf:
                primary_tf = list(indicators.by_timeframe.keys())[0]
                
            ind = indicators.by_timeframe.get(primary_tf)
            
            if ind:
                rsi = getattr(ind, 'rsi', 50)
                stoch_k = getattr(ind, 'stoch_rsi_k', None)
                stoch_d = getattr(ind, 'stoch_rsi_d', None)
                
                momentum_score = 0.5  # Neutral default
                
                if is_bullish:
                    # For longs, we WANT price to pull back (bearish momentum helps)
                    # But if already oversold, pullback is limited
                    if rsi is not None:
                        if rsi < 30:
                            # Already oversold - less room to pull back
                            momentum_score = 0.3
                        elif rsi < 45:
                            # Mildly bearish - good for pullback
                            momentum_score = 0.7
                        elif rsi > 60:
                            # Bullish momentum - pullback less likely
                            momentum_score = 0.4
                        else:
                            momentum_score = 0.5
                else:
                    # For shorts, we WANT price to push up (bullish momentum helps)
                    if rsi is not None:
                        if rsi > 70:
                            # Already overbought - less room to push up
                            momentum_score = 0.3
                        elif rsi > 55:
                            # Mildly bullish - good for push into short zone
                            momentum_score = 0.7
                        elif rsi < 40:
                            # Bearish momentum - push up less likely
                            momentum_score = 0.4
                        else:
                            momentum_score = 0.5
                
                probability += momentum_score * 0.35
        except (IndexError, AttributeError):
            probability += 0.5 * 0.35  # Neutral on error
    else:
        probability += 0.5 * 0.35  # Neutral if no indicators
    
    # 3. HTF TREND FACTOR (25% weight)
    # Pullback against trend is harder to achieve
    htf_score = 0.5  # Neutral default
    if htf_trend:
        trend_lower = htf_trend.lower()
        if is_bullish:
            # For longs, bearish HTF trend makes pullback more likely initially
            # but the bounce back up is harder
            if trend_lower == 'bullish':
                htf_score = 0.65  # Pullback likely to be bought
            elif trend_lower == 'bearish':
                htf_score = 0.45  # Pullback may continue (risky)
        else:
            # For shorts, bullish HTF trend makes push up likely
            if trend_lower == 'bearish':
                htf_score = 0.65  # Push up likely to be sold
            elif trend_lower == 'bullish':
                htf_score = 0.45  # Push up may continue (risky)
    
    probability += htf_score * 0.25
    
    # Clamp to valid range
    return max(0.0, min(1.0, probability))

def _map_setup_to_archetype(setup_type: str) -> SetupArchetype:
    s = (setup_type or "").upper().replace(" ", "_")
    if "SWEEP" in s:
        return cast(SetupArchetype, "SWEEP_REVERSAL")
    if "BREAKOUT" in s or "RETEST" in s:
        return cast(SetupArchetype, "BREAKOUT_RETEST")
    if "RANGE" in s or "MEAN" in s:
        return cast(SetupArchetype, "RANGE_REVERSION")
    return cast(SetupArchetype, "TREND_OB_PULLBACK")

def _is_in_correct_pd_zone(
    price: float,
    is_bullish: bool,
    smc_snapshot: SMCSnapshot,
    timeframe: str,
    tolerance: float = 0.0
) -> bool:
    """Check if price is in the correct Premium/Discount zone with tolerance."""
    if not smc_snapshot.premium_discount:
        return True
    
    # Try specific timeframe, then fallback
    pd_data = smc_snapshot.premium_discount.get(timeframe)
    if not pd_data:
        # Fallback to any HTF PD data
        for tf in ['1w', '1d', '4h']:
            if tf in smc_snapshot.premium_discount:
                pd_data = smc_snapshot.premium_discount[tf]
                break
    
    if not pd_data or 'equilibrium' not in pd_data:
        return True
        
    equilibrium = pd_data['equilibrium']
    
    # Calculate buffer distance based on range size (if available)
    buffer = 0.0
    if tolerance > 0 and 'range_high' in pd_data and 'range_low' in pd_data:
        range_size = pd_data['range_high'] - pd_data['range_low']
        buffer = range_size * tolerance
    
    if is_bullish:
        # Longs should be in Discount (below equilibrium)
        # With tolerance: allow price up to equilibrium + buffer
        return price <= (equilibrium + buffer)
    else:
        # Shorts should be in Premium (above equilibrium)
        # With tolerance: allow price down to equilibrium - buffer
        return price >= (equilibrium - buffer)


def _has_sweep_backing(
    ob: OrderBlock,
    sweeps: List[LiquiditySweep],
    lookback_candles: int = 5
) -> bool:
    """Check if Order Block was immediately preceded by a liquidity sweep."""
    if not sweeps:
        return False
        
    ob_ts = ob.timestamp
    
    # Filter sweeps that happened BEFORE the OB
    valid_sweeps = [s for s in sweeps if s.timestamp < ob_ts]
    if not valid_sweeps:
        return False
        
    # Get separate timeframe parsing helper if needed, or estimate duration
    # Simple heuristic: scan recently preceding sweeps
    # Assuming standard candle durations for timestamp delta check would be robust,
    # but for now, we'll check if any sweep constitutes a "setup" for this OB.
    # A Turtle Soup setup implies the OB *formed* from the reversal of the sweep.
    # So the sweep timestamp should be very close to OB timestamp.
    
    # Let's use a robust proximity check based on timeframe
    timeframe_minutes = {
        '1m': 1, '5m': 5, '15m': 15, '1h': 60, '4h': 240, '1d': 1440, '1w': 10080
    }
    tf_min = timeframe_minutes.get(ob.timeframe.lower(), 60)
    max_delta_sec = tf_min * 60 * lookback_candles
    
    nearest_sweep = max(valid_sweeps, key=lambda s: s.timestamp)
    gap = (ob_ts - nearest_sweep.timestamp).total_seconds()
    
    if gap <= max_delta_sec:
         # Also check levels: sweep level should be close to OB
        # For bullish, sweep low should be near/below OB low
        # For bearish, sweep high should be near/above OB high
        if ob.direction == "bullish" and nearest_sweep.sweep_type == "low":
            return True
        elif ob.direction == "bearish" and nearest_sweep.sweep_type == "high":
            return True
            
    return False


def _is_order_block_valid(ob: OrderBlock, df: pd.DataFrame, current_price: float) -> bool:
    """Validate an order block is not broken and not currently being mitigated."""
    if df is None or len(df) == 0:
        return True
    future_index_match = df.index > ob.timestamp
    # Defensive fix for duplicate columns
    if isinstance(future_index_match, pd.DataFrame):
        # If boolean mask is a DataFrame (due to duplicate index?), this is bad data
        # Fallback: take the first column
        future_index_match = future_index_match.iloc[:, 0]
        
    try:
        future_candles = df[future_index_match]
        # Ensure we don't return duplicate columns in future_candles either
        if not future_candles.columns.is_unique:
             future_candles = future_candles.loc[:, ~future_candles.columns.duplicated()]
    except Exception:
        return True
    if len(future_candles) == 0:
        return True
    if ob.direction == "bullish":
        try:
            lows = future_candles['low']
            # Defensive check: if 'low' returns DataFrame (duplicate cols), reduce to min of rows then min of series
            if isinstance(lows, pd.DataFrame):
                 lowest = lows.min(axis=1).min()
            else:
                 lowest = lows.min()
                 
            if lowest < ob.low:  # broken through
                return False
            if ob.low <= current_price <= ob.high:  # currently inside zone
                return False
        except ValueError:
            # Fallback if ambiguity persists
            return True
            
    else:
        try:
            highs = future_candles['high']
            if isinstance(highs, pd.DataFrame):
                 highest = highs.max(axis=1).max()
            else:
                 highest = highs.max()
                 
            if highest > ob.high:
                return False
            if ob.low <= current_price <= ob.high:
                return False
        except ValueError:
            return True
            
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


def _find_nested_entry_ob(
    is_bullish: bool,
    zone_obs: List[OrderBlock],
    trigger_obs: List[OrderBlock],
    current_price: float,
    atr: float
) -> Optional[tuple]:
    """
    Find an LTF trigger OB that sits inside an HTF zone OB for precise entry.
    
    This implements TOP-DOWN ENTRY LOGIC:
    1. HTF Zone OB defines the institutional accumulation/distribution zone
    2. LTF Trigger OB inside it provides precise entry timing
    
    Args:
        is_bullish: Trade direction
        zone_obs: HTF zone order blocks (4H/1H)
        trigger_obs: LTF trigger order blocks (15m/5m)
        current_price: Current market price
        atr: ATR for distance validation
        
    Returns:
        Tuple of (trigger_ob, zone_ob) or None if no nested setup found
    """
    if not zone_obs or not trigger_obs:
        return None
    
    best_nested = None
    best_score = -1
    
    for zone_ob in zone_obs:
        # Zone OB must be in correct position relative to price
        if is_bullish:
            # For longs, zone should be below or at current price
            if zone_ob.high > current_price * 1.02:  # 2% tolerance
                continue
        else:
            # For shorts, zone should be above or at current price
            if zone_ob.low < current_price * 0.98:
                continue
        
        for trigger_ob in trigger_obs:
            # Check if trigger is INSIDE the zone (nested)
            is_nested = (
                trigger_ob.low >= zone_ob.low - (0.1 * atr) and  # Small tolerance
                trigger_ob.high <= zone_ob.high + (0.1 * atr)
            )
            
            if not is_nested:
                continue
            
            # Check trigger is in correct position
            if is_bullish:
                if trigger_ob.high > current_price:
                    continue  # Trigger must be below price for longs
            else:
                if trigger_ob.low < current_price:
                    continue  # Trigger must be above price for shorts
            
            # Score the nested setup
            # Prefer: higher freshness, larger zone, less mitigated
            freshness_score = getattr(trigger_ob, 'freshness_score', 0.7)
            zone_freshness = getattr(zone_ob, 'freshness_score', 0.7)
            mitigation = getattr(trigger_ob, 'mitigation_level', 0.0)
            
            score = (
                freshness_score * 2 +  # Fresh trigger is key
                zone_freshness +
                (zone_ob.high - zone_ob.low) / atr +  # Larger zone = more significant
                (1 - mitigation) * 2  # Unmitigated trigger
            )
            
            if score > best_score:
                best_score = score
                best_nested = (trigger_ob, zone_ob)
    
    if best_nested:
        trigger, zone = best_nested
        logger.info(
            f"🎯 NESTED ENTRY: Found {trigger.timeframe} trigger OB inside {zone.timeframe} zone OB | "
            f"Trigger: [{trigger.low:.2f}-{trigger.high:.2f}] Zone: [{zone.low:.2f}-{zone.high:.2f}]"
        )
    
    return best_nested


def _get_zone_and_trigger_tfs(config: ScanConfig) -> tuple:
    """
    Get zone and trigger timeframes from config.
    Falls back to entry_timeframes split if not specified.
    """
    zone_tfs = getattr(config, 'zone_timeframes', None)
    trigger_tfs = getattr(config, 'entry_trigger_timeframes', None)
    
    if zone_tfs and trigger_tfs:
        return zone_tfs, trigger_tfs
    
    # Fallback: split entry_timeframes into zone (HTF) and trigger (LTF)
    entry_tfs = getattr(config, 'entry_timeframes', ())
    htf = ('1w', '1d', '4h', '1h')
    ltf = ('15m', '5m', '1m')
    
    zone_tfs = tuple(tf for tf in entry_tfs if tf.lower() in [h.lower() for h in htf])
    trigger_tfs = tuple(tf for tf in entry_tfs if tf.lower() in [l.lower() for l in ltf])
    
    return zone_tfs or ('4h', '1h'), trigger_tfs or ('15m', '5m')

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
    multi_tf_data: Optional[MultiTimeframeData] = None,
    indicators: Optional[IndicatorSet] = None  # NEW: For regime detection
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
    
    # === SWING MODE: Attempt nested entry (LTF trigger inside HTF zone) ===
    mode_profile = getattr(config, 'profile', 'balanced').lower()
    is_swing_mode = mode_profile in ('macro_surveillance', 'overwatch', 'stealth_balanced', 'stealth')
    
    if is_swing_mode:
        zone_tfs, trigger_tfs = _get_zone_and_trigger_tfs(config)
        
        # Separate OBs by timeframe role
        zone_obs = [ob for ob in smc_snapshot.order_blocks 
                   if ob.direction == ("bullish" if is_bullish else "bearish")
                   and ob.timeframe.lower() in [t.lower() for t in zone_tfs]]
        trigger_obs = [ob for ob in smc_snapshot.order_blocks 
                      if ob.direction == ("bullish" if is_bullish else "bearish")
                      and ob.timeframe.lower() in [t.lower() for t in trigger_tfs]]
        
        nested_result = _find_nested_entry_ob(
            is_bullish=is_bullish,
            zone_obs=zone_obs,
            trigger_obs=trigger_obs,
            current_price=current_price,
            atr=atr
        )
        
        if nested_result:
            trigger_ob, zone_ob = nested_result
            logger.info(f"✅ NESTED ENTRY ACTIVE: Using {trigger_ob.timeframe} trigger inside {zone_ob.timeframe} zone")
            
            # Use trigger OB for entry zone
            entry_zone = EntryZone(
                near_entry=trigger_ob.high if is_bullish else trigger_ob.low,
                far_entry=trigger_ob.low if is_bullish else trigger_ob.high,
                rationale=f"Nested entry: {trigger_ob.timeframe} OB inside {zone_ob.timeframe} zone OB"
            )
            # Set additional metadata as attributes (EntryZone model only accepts near_entry, far_entry, rationale)
            entry_zone.entry_tf_used = trigger_ob.timeframe  # type: ignore
            entry_zone.structure_type = "nested_ob"  # type: ignore
            return entry_zone, True  # used_structure = True
    
    if is_bullish:
        # Look for bullish OB or FVG below current price (OR we are inside it)
        # FIXED: Only include OBs where:
        #   1. Price is INSIDE the OB (immediate entry possible), OR
        #   2. OB.high is at or below current price (pullback entry)
        # This prevents selecting OBs where the entry zone is entirely above current price
        obs = [
            ob for ob in smc_snapshot.order_blocks 
            if ob.direction == "bullish" 
            and ob.low < current_price
            and (ob.high <= current_price or (ob.low <= current_price <= ob.high))
        ]
        
        # NEW: Premium/Discount Enforcement (Smart Entry)
        if planner_cfg.pd_compliance_required:
            pre_pd_count = len(obs)
            # Check if OB acts as support in Discount zone (with tolerance)
            obs = [ob for ob in obs if _is_in_correct_pd_zone(
                ob.high, True, smc_snapshot, primary_tf, planner_cfg.pd_compliance_tolerance)]
            if len(obs) < pre_pd_count:
                logger.debug(f"PD Gate (Long): Filtered {pre_pd_count - len(obs)} Bullish OBs in Premium")
        
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
            
            # Smart Entry: Sweep Boost
            sweep_boost = 1.0
            if _has_sweep_backing(ob, smc_snapshot.liquidity_sweeps, planner_cfg.sweep_lookback_candles):
                sweep_boost = planner_cfg.sweep_backing_boost
            
            return base_score * displacement_factor * mitigation_penalty * sweep_boost

        fvgs = [fvg for fvg in smc_snapshot.fvgs if fvg.direction == "bullish" and fvg.top < current_price]
        # Filter to allowed ENTRY timeframes if specified
        if allowed_tfs:
            fvgs = [fvg for fvg in fvgs if fvg.timeframe in allowed_tfs]
            logger.debug(f"Filtered bullish FVGs to entry_timeframes {allowed_tfs}: {len(fvgs)} remain")
        
        if planner_cfg.pd_compliance_required:
            pre_pd_count = len(fvgs)
            fvgs = [f for f in fvgs if _is_in_correct_pd_zone(
                f.top, True, smc_snapshot, primary_tf, planner_cfg.pd_compliance_tolerance)]
            if len(fvgs) < pre_pd_count:
                logger.debug(f"PD Gate (Long): Filtered {pre_pd_count - len(fvgs)} Bullish FVGs in Premium")
        
        logger.critical(f"Bullish entry zone: found {len(obs)} OBs and {len(fvgs)} FVGs below current price")
        if obs:
            # Use most recent/fresh OB
            best_ob = max(obs, key=_ob_score)
            
            # Log sweep boost if active
            if _has_sweep_backing(best_ob, smc_snapshot.liquidity_sweeps, planner_cfg.sweep_lookback_candles):
                 logger.info(f"🐢 TURTLE SOUP: Bullish Entry OB {best_ob.timeframe} backed by liquidity sweep (Score Boosted {planner_cfg.sweep_backing_boost}x)")
            entry_tf_used = best_ob.timeframe  # Track for metadata
            logger.critical(f"ENTRY ZONE: Using bullish OB - high={best_ob.high}, low={best_ob.low}, ATR={atr}, TF={entry_tf_used}")
            
            # Calculate regime-aware base offset
            # Calculate regime-aware base offset
            if indicators:
                 regime = get_atr_regime(indicators, current_price)
            else:
                 regime = "normal"
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
            
            if indicators:
                regime = get_atr_regime(indicators, current_price)
            else:
                regime = "normal"
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
        
    else:  # Bearish
        # Look for bearish OB or FVG above current price
        # FIXED: Only include OBs where:
        #   1. Price is INSIDE the OB (immediate entry possible), OR
        #   2. OB.low is at or above current price (pullback entry)
        # This prevents selecting OBs where the entry zone is entirely below current price
        obs = [
            ob for ob in smc_snapshot.order_blocks 
            if ob.direction == "bearish" 
            and ob.high > current_price
            and (ob.low >= current_price or (ob.low <= current_price <= ob.high))
        ]

        # NEW: Premium/Discount Enforcement
        if planner_cfg.pd_compliance_required:
            pre_pd_count = len(obs)
            # Check if OB acts as resistance in Premium (with tolerance)
            obs = [ob for ob in obs if _is_in_correct_pd_zone(
                ob.low, False, smc_snapshot, primary_tf, planner_cfg.pd_compliance_tolerance)]
            if len(obs) < pre_pd_count:
                logger.debug(f"PD Gate (Short): Filtered {pre_pd_count - len(obs)} Bearish OBs in Discount")
        
        # Filter to allowed ENTRY timeframes
        if allowed_tfs:
            obs = [ob for ob in obs if ob.timeframe.lower() in allowed_tfs]
            logger.debug(f"Filtered bearish OBs to entry_timeframes {allowed_tfs}: {len(obs)} remain")
        
        max_pullback_atr = getattr(config, "max_pullback_atr", 3.0)
        # Fix: If inside OB (price >= low), distance is 0.
        obs = [ob for ob in obs if (max(0.0, ob.low - current_price) / atr) <= max_pullback_atr]
        obs = [ob for ob in obs if ob.mitigation_level <= planner_cfg.ob_mitigation_max]
        if multi_tf_data and primary_tf in getattr(multi_tf_data, 'timeframes', {}):
             df_primary = multi_tf_data.timeframes[primary_tf]
             validated = []
             for ob in obs:
                 # Ensure price hasn't broken the OB
                 if current_price <= ob.high:
                     validated.append(ob)
                 else:
                     logger.debug(f"Filtered invalid bearish OB (broken): low={ob.low} high={ob.high}")
             obs = validated

        logger.debug(f"Bearish OBs for entry zone: {len(obs)} (all grades allowed, confluence handles quality)")

        # NEW: Validate LTF OBs have HTF backing
        skip_htf_backing = config.profile in ('precision', 'surgical')
        if not skip_htf_backing:
             validated_backing = []
             ltf_tfs = ('1m', '5m', '15m')
             htf_tfs = ('1h', '4h', '1d', '1w')
             for ob in obs:
                 if ob.timeframe in ltf_tfs:
                     # Check for overlapping HTF structure (OB or FVG)
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
                                 if (htf_fvg.bottom <= ob.high and htf_fvg.top >= ob.low): # FVG bottom/top are low/high
                                     has_backing = True
                                     break
                     if has_backing:
                         validated_backing.append(ob)
                 else:
                     validated_backing.append(ob)
             obs = validated_backing

        tf_weight = {"1m": 0.5, "5m": 0.8, "15m": 1.0, "1h": 1.2, "4h": 1.5, "1d": 2.0}
        def _ob_score_bearish(ob: OrderBlock) -> float:
            base_score = ob.freshness_score * tf_weight.get(ob.timeframe, 1.0)
            displacement_factor = 1.0 + (ob.displacement_strength * planner_cfg.ob_displacement_weight)
            mitigation_penalty = (1.0 - min(ob.mitigation_level, 1.0))
            
            # Smart Entry: Sweep Boost
            sweep_boost = 1.0
            if _has_sweep_backing(ob, smc_snapshot.liquidity_sweeps, planner_cfg.sweep_lookback_candles):
                sweep_boost = planner_cfg.sweep_backing_boost
            
            return base_score * displacement_factor * mitigation_penalty * sweep_boost

        fvgs = [fvg for fvg in smc_snapshot.fvgs if fvg.direction == "bearish" and fvg.bottom > current_price]
        if allowed_tfs:
            fvgs = [fvg for fvg in fvgs if fvg.timeframe in allowed_tfs]
            logger.debug(f"Filtered bearish FVGs to entry_timeframes {allowed_tfs}: {len(fvgs)} remain")
            
        if planner_cfg.pd_compliance_required:
            pre_pd_count = len(fvgs)
            fvgs = [f for f in fvgs if _is_in_correct_pd_zone(
                f.bottom, False, smc_snapshot, primary_tf, planner_cfg.pd_compliance_tolerance)]
            if len(fvgs) < pre_pd_count:
                logger.debug(f"PD Gate (Short): Filtered {pre_pd_count - len(fvgs)} Bearish FVGs in Discount")

        logger.critical(f"Bearish entry zone: found {len(obs)} OBs and {len(fvgs)} FVGs above current price")
        if obs:
            best_ob = max(obs, key=_ob_score_bearish)

            # Log sweep boost
            if _has_sweep_backing(best_ob, smc_snapshot.liquidity_sweeps, planner_cfg.sweep_lookback_candles):
                 logger.info(f"🐢 TURTLE SOUP: Bearish Entry OB {best_ob.timeframe} backed by liquidity sweep (Score Boosted {planner_cfg.sweep_backing_boost}x)")
            entry_tf_used = best_ob.timeframe  # Track for metadata
            logger.critical(f"ENTRY ZONE: Using bearish OB - high={best_ob.high}, low={best_ob.low}, ATR={atr}, TF={entry_tf_used}")
            # Calculate regime-aware base offset
            if indicators:
                regime = get_atr_regime(indicators, current_price)
            else:
                regime = "normal"
            regime_multiplier = planner_cfg.atr_regime_multipliers.get(regime, 1.0)
            base_offset = planner_cfg.entry_zone_offset_atr * regime_multiplier
            
            # Apply HTF bias gradient
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
            
            # FIX: Cap near_entry at current price if already inside
            price_inside_ob = current_price <= best_ob.high and current_price >= best_ob.low
            if near_entry < current_price:
                logger.info("📦 ENTRY ZONE FIX: near_entry (%.2f) < price (%.2f), capping at price (inside OB: %s)",
                            near_entry, current_price, price_inside_ob)
                near_entry = current_price
            
            logger.info("📦 ENTRY ZONE CALC: OB=[%.2f-%.2f] | offset=%.2f (base=%.2f * htf=%.2f * atr=%.2f) | near=%.2f, far=%.2f | price=%.2f",
                        best_ob.low, best_ob.high, offset, base_offset, htf_factor, atr, near_entry, far_entry, current_price)
                        
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
             
             if indicators:
                 regime = get_atr_regime(indicators, current_price)
             else:
                 regime = "normal"
             regime_multiplier = planner_cfg.atr_regime_multipliers.get(regime, 1.0)
             base_offset = planner_cfg.entry_zone_offset_atr * regime_multiplier
             
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
             near_entry = best_fvg.bottom + offset
             far_entry = best_fvg.top - offset
             
             # FIX
             if near_entry < current_price:
                 logger.info("📦 FVG ENTRY FIX: near_entry (%.2f) < price (%.2f), capping at price",
                             near_entry, current_price)
                 near_entry = current_price
             
             rationale = f"Entry zone based on {best_fvg.timeframe} bearish FVG"
             used_structure = True
             entry_zone = EntryZone(
                 near_entry=near_entry,
                 far_entry=far_entry,
                 rationale=rationale
             )
             entry_zone.entry_tf_used = entry_tf_used  # type: ignore
             return entry_zone, used_structure

    # Fallback to current price with fixed tight stop logic (if no structure found)
    # The caller will handle this case (likely rejecting plan if strict mode)
    used_structure = False
    
    # Adaptive offset for fallback (dynamic based on ATR)
    fallback_offset = atr * 0.5
    
    if is_bullish:
        entry_zone = EntryZone(
            near_entry=current_price,
            far_entry=current_price - fallback_offset,
            rationale="No valid SMC structure found in entry zone (fallback)"
        )
    else:
        entry_zone = EntryZone(
            near_entry=current_price,
            far_entry=current_price + fallback_offset,
            rationale="No valid SMC structure found in entry zone (fallback)"
        )
    entry_zone.entry_tf_used = "N/A"  # type: ignore
    
    # Calculate and store pullback probability
    entry_mid = entry_zone.midpoint
    pullback_prob = _calculate_pullback_probability(
        is_bullish=is_bullish,
        current_price=current_price,
        entry_zone_mid=entry_mid,
        atr=atr,
        indicators=indicators,
        htf_trend=None  # Caller can provide via confluence_breakdown if needed
    )
    entry_zone.pullback_probability = pullback_prob  # type: ignore
    
    return entry_zone, used_structure
