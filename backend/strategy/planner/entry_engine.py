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
from backend.shared.models.smc import SMCSnapshot, OrderBlock, LiquiditySweep
from backend.shared.models.scoring import ConfluenceBreakdown
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.planner_config import PlannerConfig
from backend.strategy.planner.regime_engine import get_atr_regime, _calculate_htf_bias_factor
from backend.shared.models.indicators import IndicatorSet
from backend.strategy.planner.risk_engine import _get_allowed_entry_tfs
from backend.shared.config.scanner_modes import RELATIVITY_MAP, map_profile_to_relativity


logger = logging.getLogger(__name__)

SetupArchetype = Literal[
    "TREND_OB_PULLBACK",
    "RANGE_REVERSION",
    "SWEEP_REVERSAL",
    "BREAKOUT_RETEST",
    "TREND_CONTINUATION",  # NEW: Consolidation breakout + retest
]


def _calculate_pullback_probability(
    is_bullish: bool,
    current_price: float,
    entry_zone_mid: float,
    atr: float,
    indicators: Optional[IndicatorSet] = None,
    htf_trend: Optional[str] = None,
    smc_snapshot: Optional[SMCSnapshot] = None,
    confluence_breakdown: Optional[ConfluenceBreakdown] = None,
    config: Optional[ScanConfig] = None,
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
        smc_snapshot: SMC snapshot for liquidity sweep detection
        confluence_breakdown: Confluence results for HTF alignment

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
            # Determine primary timeframe from RELATIVITY_MAP based on mode
            mode_key = map_profile_to_relativity(getattr(config, "profile", "stealth"))
            relativity = RELATIVITY_MAP.get(mode_key, RELATIVITY_MAP["intraday"])
            
            # Prefer 'plan' timeframe for pullback momentum validity
            primary_tf = relativity["plan"]

            if primary_tf not in indicators.by_timeframe:
                primary_tf = list(indicators.by_timeframe.keys())[0]

            if not primary_tf:
                primary_tf = list(indicators.by_timeframe.keys())[0]

            ind = indicators.by_timeframe.get(primary_tf)

            if ind:
                rsi = getattr(ind, "rsi", 50)
                stoch_k = getattr(ind, "stoch_rsi_k", None) or getattr(ind, "stoch_k", None)
                stoch_d = getattr(ind, "stoch_rsi_d", None) or getattr(ind, "stoch_d", None)

                momentum_score = 0.5  # Neutral default

                if is_bullish:
                    # For longs, we WANT price to pull back (bearish momentum helps)
                    # But if already oversold, pullback is limited
                    if rsi is not None:
                        if rsi < 30:
                            # Already oversold - less room to pull back
                            momentum_score = 0.3
                            
                            # BYPASS: If sweeping liquidity OR HTF structure is aligned, soften the penalty
                            sweeps = getattr(smc_snapshot, "liquidity_sweeps", []) if smc_snapshot else []
                            has_sweep = any(s.sweep_type == "low" for s in sweeps)
                            htf_aligned = getattr(confluence_breakdown, "htf_aligned", False) if confluence_breakdown else False
                            
                            # NEW: Check for bullish momentum cross
                            stoch_cross_up = stoch_k is not None and stoch_d is not None and stoch_k > stoch_d
                            
                            if has_sweep or htf_aligned or stoch_cross_up:
                                logger.info(f"🔄 Pullback Bypass (Long): Oversold RSI {rsi:.1f} but sweep/alignment/momentum-cross detected. Neutralizing penalty.")
                                momentum_score = 0.6 # Soften penalty if structure favors the move
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
                            
                            # BYPASS: If sweeping liquidity OR HTF structure is aligned, soften the penalty
                            sweeps = getattr(smc_snapshot, "liquidity_sweeps", []) if smc_snapshot else []
                            has_sweep = any(s.sweep_type == "high" for s in sweeps)
                            htf_aligned = getattr(confluence_breakdown, "htf_aligned", False) if confluence_breakdown else False
                            
                            # NEW: Check for bearish momentum cross
                            stoch_cross_down = stoch_k is not None and stoch_d is not None and stoch_k < stoch_d
                            
                            if has_sweep or htf_aligned or stoch_cross_down:
                                logger.info(f"🔄 Pullback Bypass (Short): Overbought RSI {rsi:.1f} but sweep/alignment/momentum-cross detected. Neutralizing penalty.")
                                momentum_score = 0.6 # Soften penalty if structure favors the move
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
            if trend_lower == "bullish":
                htf_score = 0.65  # Pullback likely to be bought
            elif trend_lower == "bearish":
                htf_score = 0.45  # Pullback may continue (risky)
        else:
            # For shorts, bullish HTF trend makes push up likely
            if trend_lower == "bearish":
                htf_score = 0.65  # Push up likely to be sold
            elif trend_lower == "bullish":
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
    if "CONTINUATION" in s or "CONSOLIDATION" in s:
        return cast(SetupArchetype, "TREND_CONTINUATION")
    return cast(SetupArchetype, "TREND_OB_PULLBACK")


def _is_in_correct_pd_zone(
    price: float,
    is_bullish: bool,
    smc_snapshot: SMCSnapshot,
    timeframe: str,
    tolerance: float = 0.0,
) -> bool:
    """Check if price is in the correct Premium/Discount zone with tolerance."""
    if not smc_snapshot.premium_discount:
        return True

    # Try specific timeframe, then fallback
    pd_data = smc_snapshot.premium_discount.get(timeframe)
    if not pd_data:
        # Fallback to any HTF PD data using dynamic context
        # We don't have config here yet, so we'll check common HTFs or pass it in later if needed
        # For now, stick to structural hierarchy
        # TRY: Find any available PD data in structural order (1w -> 1h)
        # Fixes case-sensitivity issues by checking both layouts if needed
        for tf_opt in ["1w", "1d", "4h", "1h"]:
            # Check lowercase
            if tf_opt in smc_snapshot.premium_discount:
                pd_data = smc_snapshot.premium_discount[tf_opt]
                break
            # Check uppercase fallback
            tf_upper = tf_opt.upper()
            if tf_upper in smc_snapshot.premium_discount:
                pd_data = smc_snapshot.premium_discount[tf_upper]
                break

    if not pd_data or "equilibrium" not in pd_data:
        return True

    equilibrium = pd_data["equilibrium"]

    # Calculate buffer distance based on range size (if available)
    buffer = 0.0
    if tolerance > 0 and "range_high" in pd_data and "range_low" in pd_data:
        range_size = pd_data["range_high"] - pd_data["range_low"]
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
    ob: OrderBlock, sweeps: List[LiquiditySweep], lookback_candles: int = 5
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
    timeframe_minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440, "1w": 10080}
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
    if df is None or df.empty:
        return True

    # CRITICAL: Ensure index is clean before comparison (Deduplication)
    # Fixes "truth value of a Series is ambiguous" errors
    if df.index.duplicated().any():
        df = df[~df.index.duplicated(keep="first")]

    future_index_match = df.index > ob.timestamp
    # Defensive fix for duplicate columns
    if isinstance(future_index_match, pd.DataFrame):
        future_index_match = future_index_match.iloc[:, 0]

    try:
        future_candles = df[future_index_match]
        # Ensure we don't return duplicate columns in future_candles either
        if not future_candles.columns.is_unique:
            future_candles = future_candles.loc[:, ~future_candles.columns.duplicated()]
    except Exception:
        return True

    if future_candles.empty:
        return True

    if ob.direction == "bullish":
        try:
            # Use .min().min() to collapse any multi-element series/dataframe into a single scalar
            # This is the most robust way to ensure we get a single float value even with duplicate columns
            low_data = future_candles["low"]
            lowest = low_data.min()
            if hasattr(lowest, "min"): # Multi-column result
                lowest = lowest.min()

            if float(lowest) < float(ob.low):  # broken through
                return False
            if ob.low <= current_price <= ob.high:  # currently inside zone
                return False
        except (ValueError, TypeError):
            return True

    else:
        try:
            high_data = future_candles["high"]
            highest = high_data.max()
            if hasattr(highest, "max"): # Multi-column result
                highest = highest.max()

            if float(highest) > float(ob.high):
                return False
            if ob.low <= current_price <= ob.high:
                return False
        except (ValueError, TypeError):
            return True

    return True


def _time_since_last_touch(ob: OrderBlock, df: pd.DataFrame) -> float:
    """Hours since OB last touched; infinity if never."""
    if df is None or len(df) == 0:
        return float("inf")
    try:
        if not df.columns.is_unique:
            df = df.loc[:, ~df.columns.duplicated()]
        future_candles = df[df.index > ob.timestamp]
    except Exception:
        return float("inf")
    if future_candles.empty:  # FIX: Use .empty instead of len() == 0
        return float("inf")
    if ob.direction == "bullish":
        touches = future_candles[future_candles["low"] <= ob.high]
    else:
        touches = future_candles[future_candles["high"] >= ob.low]
    if touches.empty:  # FIX: Use .empty instead of len() == 0
        return float("inf")
    last_touch = touches.index[-1]
    return (df.index[-1] - last_touch).total_seconds() / 3600.0


def _find_nested_entry_ob(
    is_bullish: bool,
    zone_obs: List[OrderBlock],
    trigger_obs: List[OrderBlock],
    current_price: float,
    atr: float,
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
            is_nested = trigger_ob.low >= zone_ob.low - (
                0.1 * atr
            ) and trigger_ob.high <= zone_ob.high + (  # Small tolerance
                0.1 * atr
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
            freshness_score = getattr(trigger_ob, "freshness_score", 0.7)
            zone_freshness = getattr(zone_ob, "freshness_score", 0.7)
            mitigation = getattr(trigger_ob, "mitigation_level", 0.0)

            score = (
                freshness_score * 2  # Fresh trigger is key
                + zone_freshness
                + (zone_ob.high - zone_ob.low) / atr  # Larger zone = more significant
                + (1 - mitigation) * 2  # Unmitigated trigger
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
    zone_tfs = getattr(config, "zone_timeframes", None)
    trigger_tfs = getattr(config, "entry_trigger_timeframes", None)

    if zone_tfs and trigger_tfs:
        return zone_tfs, trigger_tfs

    # Fallback: split entry_timeframes into zone (HTF) and trigger (LTF) using RELATIVITY_MAP
    mode_key = map_profile_to_relativity(getattr(config, "profile", "stealth"))
    rel = RELATIVITY_MAP.get(mode_key, RELATIVITY_MAP["intraday"])
    
    # Zone: plan/context | Trigger: exec
    zone_htf = (rel["context"], rel["plan"])
    trigger_ltf = (rel["exec"],)

    entry_tfs = getattr(config, "entry_timeframes", ())
    
    zone_tfs = tuple(tf for tf in entry_tfs if tf.lower() in [h.lower() for h in zone_htf])
    trigger_tfs = tuple(tf for tf in entry_tfs if tf.lower() in [l.lower() for l in trigger_ltf])

    return zone_tfs or (rel["plan"],), trigger_tfs or (rel["exec"],)


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
    indicators: Optional[IndicatorSet] = None,  # NEW: For regime detection
) -> tuple[EntryZone, bool]:
    """
    Calculate dual entry zone based on SMC structure.

    Near entry: Closer to current price, safer but lower R:R
    Far entry: Deeper into structure, riskier but better R:R

    Returns:
        Tuple of (EntryZone, used_structure_flag)
    """
    logger.critical(
        f"_calculate_entry_zone CALLED: is_bullish={is_bullish}, current_price={current_price}, atr={atr}, num_obs={len(smc_snapshot.order_blocks)}, num_fvgs={len(smc_snapshot.fvgs)}"
    )
    # DEBUG: Log all OB details before filtering
    for ob in smc_snapshot.order_blocks:
        logger.critical(
            f"  OB: dir={ob.direction} tf={ob.timeframe} low={ob.low:.2f} high={ob.high:.2f}"
        )

    # Find relevant order block or FVG
    allowed_tfs = _get_allowed_entry_tfs(config)  # CHANGED: Use entry TFs, not structure TFs

    # === SWING MODE: Attempt nested entry (LTF trigger inside HTF zone) ===
    mode_profile = getattr(config, "profile", "balanced").lower()
    is_swing_mode = mode_profile in (
        "macro_surveillance",
        "overwatch",
        "stealth_balanced",
        "stealth",
    )

    if is_swing_mode:
        zone_tfs, trigger_tfs = _get_zone_and_trigger_tfs(config)

        # Separate OBs by timeframe role
        zone_obs = [
            ob
            for ob in smc_snapshot.order_blocks
            if ob.direction == ("bullish" if is_bullish else "bearish")
            and ob.timeframe.lower() in [t.lower() for t in zone_tfs]
        ]
        trigger_obs = [
            ob
            for ob in smc_snapshot.order_blocks
            if ob.direction == ("bullish" if is_bullish else "bearish")
            and ob.timeframe.lower() in [t.lower() for t in trigger_tfs]
        ]

        nested_result = _find_nested_entry_ob(
            is_bullish=is_bullish,
            zone_obs=zone_obs,
            trigger_obs=trigger_obs,
            current_price=current_price,
            atr=atr,
        )

        if nested_result:
            trigger_ob, zone_ob = nested_result
            logger.info(
                f"✅ NESTED ENTRY ACTIVE: Using {trigger_ob.timeframe} trigger inside {zone_ob.timeframe} zone"
            )

            # Use trigger OB for entry zone
            entry_zone = EntryZone(
                near_entry=trigger_ob.high if is_bullish else trigger_ob.low,
                far_entry=trigger_ob.low if is_bullish else trigger_ob.high,
                rationale=f"Nested entry: {trigger_ob.timeframe} OB inside {zone_ob.timeframe} zone OB",
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
            ob
            for ob in smc_snapshot.order_blocks
            if ob.direction == "bullish"
            and ob.low < current_price
            and (ob.high <= current_price or (ob.low <= current_price <= ob.high))
        ]

        # NEW: Premium/Discount Enforcement (Smart Entry)
        if planner_cfg.pd_compliance_required:
            pre_pd_count = len(obs)
            # Check if OB acts as support in Discount zone (with tolerance)
            obs = [
                ob
                for ob in obs
                if _is_in_correct_pd_zone(
                    ob.high, True, smc_snapshot, primary_tf, planner_cfg.pd_compliance_tolerance
                )
            ]
            if len(obs) < pre_pd_count:
                logger.debug(
                    f"PD Gate (Long): Filtered {pre_pd_count - len(obs)} Bullish OBs in Premium"
                )

        # Filter to allowed ENTRY timeframes if specified
        if allowed_tfs:
            # Normalize timeframe case (OBs may have '1H', config has '1h')
            obs = [ob for ob in obs if ob.timeframe.lower() in allowed_tfs]
            logger.debug(
                f"Filtered bullish OBs to entry_timeframes {allowed_tfs}: {len(obs)} remain"
            )
        # Filter out OBs too far (distance constraint)
        max_pullback_atr = getattr(config, "max_pullback_atr", 3.0)
        # Fix: If inside OB (price <= high), distance is 0.
        obs = [ob for ob in obs if (max(0.0, current_price - ob.high) / atr) <= max_pullback_atr]
        # Filter out heavily mitigated OBs
        obs = [ob for ob in obs if ob.mitigation_level <= planner_cfg.ob_mitigation_max]
        # Validate OB integrity: price inside the zone counts as "tapped".
        # Only allow in-zone OBs if mitigation is still low (zone is fresh).
        if multi_tf_data and primary_tf in getattr(multi_tf_data, "timeframes", {}):
            _df_primary = multi_tf_data.timeframes[primary_tf]  # available for future candle-close checks
            tapped_threshold = planner_cfg.ob_mitigation_max * 0.5
            validated = []
            for ob in obs:
                price_inside = ob.low <= current_price <= ob.high
                if price_inside and ob.mitigation_level > tapped_threshold:
                    logger.debug(
                        f"Filtered heavily-mitigated in-zone bullish OB (tapped): "
                        f"low={ob.low} high={ob.high} mitigation={ob.mitigation_level:.2f}"
                    )
                else:
                    validated.append(ob)
            obs = validated

        # NOTE: Removed Grade A/B filter - confluence scoring already penalizes weak OBs.
        # If a symbol passes the confluence gate (70%+), entry zone should be allowed.
        # Double-filtering was blocking valid high-confluence setups with weaker individual OBs.
        logger.debug(
            f"Bullish OBs for entry zone: {len(obs)} (all grades allowed, confluence handles quality)"
        )

        # NEW: Validate LTF OBs have HTF backing (Top-Down Confirmation)
        # SKIP for Surgical mode - precision entries can use isolated LTF OBs
        # (confluence scoring will still penalize weak setups)
        skip_htf_backing = config.profile in ("precision", "surgical")

        if skip_htf_backing:
            logger.debug("HTF backing filter SKIPPED for bullish OBs (%s mode)", config.profile)
        else:
            # Prevent taking LTF entries in empty space (require HTF backing)
            mode_key = map_profile_to_relativity(getattr(config, "profile", "stealth"))
            rel = RELATIVITY_MAP.get(mode_key, RELATIVITY_MAP["intraday"])
            
            validated_backing = []
            ltf_tfs = (rel["exec"],)
            htf_tfs = (rel["plan"], rel["context"], "1d", "1w")

            for ob in obs:
                if ob.timeframe in ltf_tfs:
                    # Check for overlapping HTF structure (OB or FVG)
                    has_backing = False

                    # Check OBs
                    for htf_ob in smc_snapshot.order_blocks:
                        if htf_ob.timeframe in htf_tfs and htf_ob.direction == "bullish":
                            # Check overlap: LTF OB inside or touching HTF OB
                            if htf_ob.low <= ob.high and htf_ob.high >= ob.low:
                                has_backing = True
                                break

                    # Check FVGs if no OB backing
                    if not has_backing:
                        for htf_fvg in smc_snapshot.fvgs:
                            if htf_fvg.timeframe in htf_tfs and htf_fvg.direction == "bullish":
                                if (
                                    htf_fvg.bottom <= ob.high and htf_fvg.top >= ob.low
                                ):  # FVG bottom/top are low/high
                                    has_backing = True
                                    break

                    if has_backing:
                        validated_backing.append(ob)
                    else:
                        logger.debug(
                            f"Filtered isolated LTF OB (no HTF backing): {ob.timeframe} at {ob.low}"
                        )
                else:
                    # MTF/HTF OBs are self-validating or handled by structure scoring
                    validated_backing.append(ob)
            obs = validated_backing

        # Prefer higher timeframe / freshness / displacement / low mitigation
        # Dynamic weights based on relativity tiers
        mode_key = map_profile_to_relativity(getattr(config, "profile", "stealth"))
        rel = RELATIVITY_MAP.get(mode_key, RELATIVITY_MAP["intraday"])
        
        tf_weight = {
            rel["exec"]: 0.8,
            rel["plan"]: 1.2,
            rel["context"]: 1.5,
            "1d": 2.0,
            "1w": 2.5
        }

        def _ob_score(ob: OrderBlock) -> float:
            base_score = ob.freshness_score * tf_weight.get(ob.timeframe, 1.0)
            displacement_factor = 1.0 + (
                ob.displacement_strength * planner_cfg.ob_displacement_weight
            )
            mitigation_penalty = 1.0 - min(ob.mitigation_level, 1.0)

            # Smart Entry: Sweep Boost
            sweep_boost = 1.0
            if _has_sweep_backing(
                ob, smc_snapshot.liquidity_sweeps, planner_cfg.sweep_lookback_candles
            ):
                sweep_boost = planner_cfg.sweep_backing_boost

            return base_score * displacement_factor * mitigation_penalty * sweep_boost

        fvgs = [
            fvg
            for fvg in smc_snapshot.fvgs
            if fvg.direction == "bullish" and fvg.top < current_price
        ]
        # Filter to allowed ENTRY timeframes if specified
        if allowed_tfs:
            fvgs = [fvg for fvg in fvgs if fvg.timeframe in allowed_tfs]
            logger.debug(
                f"Filtered bullish FVGs to entry_timeframes {allowed_tfs}: {len(fvgs)} remain"
            )

        if planner_cfg.pd_compliance_required:
            pre_pd_count = len(fvgs)
            fvgs = [
                f
                for f in fvgs
                if _is_in_correct_pd_zone(
                    f.top, True, smc_snapshot, primary_tf, planner_cfg.pd_compliance_tolerance
                )
            ]
            if len(fvgs) < pre_pd_count:
                logger.debug(
                    f"PD Gate (Long): Filtered {pre_pd_count - len(fvgs)} Bullish FVGs in Premium"
                )

        logger.critical(
            f"Bullish entry zone: found {len(obs)} OBs and {len(fvgs)} FVGs below current price"
        )

        if obs:
            # Use most recent/fresh OB
            best_ob = max(obs, key=_ob_score)

            # Log sweep boost if active
            if _has_sweep_backing(
                best_ob, smc_snapshot.liquidity_sweeps, planner_cfg.sweep_lookback_candles
            ):
                logger.info(
                    f"🐢 TURTLE SOUP: Bullish Entry OB {best_ob.timeframe} backed by liquidity sweep (Score Boosted {planner_cfg.sweep_backing_boost}x)"
                )
            entry_tf_used = best_ob.timeframe  # Track for metadata
            logger.critical(
                f"ENTRY ZONE: Using bullish OB - high={best_ob.high}, low={best_ob.low}, ATR={atr}, TF={entry_tf_used}"
            )

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
                    and confluence_breakdown.nearest_htf_level_type == "support"
                    and (confluence_breakdown.htf_proximity_atr or 99)
                    <= planner_cfg.htf_bias_max_atr_distance
                ):
                    htf_distance = confluence_breakdown.htf_proximity_atr or 99
                    htf_factor = _calculate_htf_bias_factor(htf_distance, planner_cfg)
            except Exception:
                pass

            offset = base_offset * htf_factor * atr
            near_entry = best_ob.high - offset
            offset = base_offset * htf_factor * atr

            # FIX: Clamp offset to prevent entry zone inversion (near crossing far)
            zone_width = best_ob.high - best_ob.low
            max_offset = zone_width / 2.0 * 0.9  # Max 45% of width
            if offset > max_offset:
                offset = max(max_offset, 0.0)

            near_entry = best_ob.high - offset
            far_entry = best_ob.low + offset

            # When price is already inside the OB, apply an aggressive-fill buffer so the
            # marketable limit fills immediately even if price drifts slightly between scan
            # and signal execution. Capped at 0.1% of price on low-ATR assets.
            # Also prevents near==far collision in EntryZone (far is anchored to current_price,
            # near is above it by at least in_zone_buffer).
            price_inside_ob = current_price <= best_ob.high and current_price >= best_ob.low
            if near_entry > current_price:
<<<<<<< HEAD
                # OB DEPTH GATE: Price has fallen deeper into the zone than the planned limit.
                # Entering mid-zone shrinks the actual stop distance (OB.low is still the SL
                # anchor but the entry is lower), so normal wick noise inside the zone will
                # stop us out before the zone can hold.
                #
                # depth_pct = 0.0 → price is at OB top (ideal entry)
                # depth_pct = 1.0 → price is at OB bottom (zone fully tested, bad entry)
                #
                # When depth > ob_max_entry_depth, reject this signal. The cascade will
                # try the next trade type (intraday/scalp) which may have a cleaner OB.
                depth_pct = (best_ob.high - current_price) / zone_width if zone_width > 0 else 0.0
                max_depth = getattr(planner_cfg, "ob_max_entry_depth", 0.5)
                if depth_pct > max_depth:
                    logger.info(
                        "📦 OB DEPTH GATE (LONG): price %.4f is %.0f%% deep in [%.4f-%.4f]"
                        " — exceeds max %.0f%%, rejecting mid-zone entry",
                        current_price, depth_pct * 100, best_ob.low, best_ob.high, max_depth * 100,
                    )
                    return None, False  # Signal dropped; planner_service guards this None

=======
>>>>>>> dceac3bd8a0d4a520e9be7922cc4498cb4fcc3e2
                in_zone_buffer = min(planner_cfg.market_entry_aggression_atr * atr, current_price * 0.001)
                near_entry = current_price + in_zone_buffer
                far_entry = min(far_entry, current_price)  # anchor far to current_price, not near_entry
                logger.info(
<<<<<<< HEAD
                    "📦 IN-ZONE ENTRY (LONG OB): near=%.4f (price=%.4f + buf=%.4f), far=%.4f"
                    " (inside OB: %s, depth=%.0f%%)",
                    near_entry, current_price, in_zone_buffer, far_entry,
                    price_inside_ob, depth_pct * 100,
=======
                    "📦 IN-ZONE ENTRY (LONG OB): near=%.4f (price=%.4f + buf=%.4f), far=%.4f (inside OB: %s)",
                    near_entry, current_price, in_zone_buffer, far_entry, price_inside_ob,
>>>>>>> dceac3bd8a0d4a520e9be7922cc4498cb4fcc3e2
                )

            logger.info(
                "📦 ENTRY ZONE CALC: OB=[%.2f-%.2f] | offset=%.2f (base=%.2f * htf=%.2f * atr=%.2f) | near=%.2f, far=%.2f | price=%.2f",
                best_ob.low,
                best_ob.high,
                offset,
                base_offset,
                htf_factor,
                atr,
                near_entry,
                far_entry,
                current_price,
            )

            rationale = f"Entry zone based on {best_ob.timeframe} bullish order block"
            if price_inside_ob:
                rationale += " (price inside OB - aggressive fill)"
            used_structure = True
            entry_zone = EntryZone(near_entry=near_entry, far_entry=far_entry, rationale=rationale)
            # Attach entry_tf_used for metadata tracking
            entry_zone.entry_tf_used = entry_tf_used  # type: ignore
            entry_zone.ob_mitigation = best_ob.mitigation_level  # type: ignore

            # Calculate pullback probability
            entry_zone.pullback_probability = _calculate_pullback_probability(  # type: ignore
                is_bullish=True,
                current_price=current_price,
                entry_zone_mid=entry_zone.midpoint,
                atr=atr,
                indicators=indicators,
                smc_snapshot=smc_snapshot,
                confluence_breakdown=confluence_breakdown,
            )
            return entry_zone, used_structure

        elif fvgs:
            # Score FVGs by quality (freshness, mitigation, displacement, TF weight)
            # mirrors _ob_score so FVG selection is not purely proximity-based
            def _fvg_score_bullish(fvg) -> float:
                freshness = getattr(fvg, "freshness_score", 0.5)
                mitigation = 1.0 - min(getattr(fvg, "overlap_with_price", 0.0), 1.0)
                displacement = 1.0 + getattr(fvg, "displacement_strength", 0.0) * planner_cfg.ob_displacement_weight
                return freshness * mitigation * displacement * tf_weight.get(fvg.timeframe, 1.0)

            eligible_fvgs = [fvg for fvg in fvgs if fvg.overlap_with_price < planner_cfg.fvg_overlap_max]
            if not eligible_fvgs:
                eligible_fvgs = fvgs
            best_fvg = max(eligible_fvgs, key=_fvg_score_bullish)
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
                    and confluence_breakdown.nearest_htf_level_type == "support"
                    and (confluence_breakdown.htf_proximity_atr or 99)
                    <= planner_cfg.htf_bias_max_atr_distance
                ):
                    htf_distance = confluence_breakdown.htf_proximity_atr or 99
                    htf_factor = _calculate_htf_bias_factor(htf_distance, planner_cfg)
            except Exception:
                pass

            offset = base_offset * htf_factor * atr
            near_entry = best_fvg.top - offset
            offset = base_offset * htf_factor * atr

            # FIX: Clamp offset to prevent inversion
            zone_width = best_fvg.bottom - best_fvg.top
            max_offset = abs(zone_width) / 2.0 * 0.9
            if offset > max_offset:
                offset = max(max_offset, 0.0)

            near_entry = best_fvg.top - offset
            far_entry = best_fvg.bottom + offset

            # When price is already inside the FVG, apply aggressive-fill buffer.
            if near_entry > current_price:
                in_zone_buffer = min(planner_cfg.market_entry_aggression_atr * atr, current_price * 0.001)
                near_entry = current_price + in_zone_buffer
                far_entry = min(far_entry, current_price)  # anchor to current_price to prevent collision
                logger.info(
                    "📦 IN-ZONE ENTRY (LONG FVG): near=%.4f (price=%.4f + buf=%.4f), far=%.4f",
                    near_entry, current_price, in_zone_buffer, far_entry,
                )

            rationale = f"Entry zone based on {best_fvg.timeframe} bullish FVG"
            used_structure = True
            entry_zone = EntryZone(near_entry=near_entry, far_entry=far_entry, rationale=rationale)
            entry_zone.entry_tf_used = entry_tf_used  # type: ignore

            # Calculate pullback probability
            entry_zone.pullback_probability = _calculate_pullback_probability(  # type: ignore
                is_bullish=True,
                current_price=current_price,
                entry_zone_mid=entry_zone.midpoint,
                atr=atr,
                indicators=indicators,
                smc_snapshot=smc_snapshot,
                confluence_breakdown=confluence_breakdown,
            )
            return entry_zone, used_structure

        # NEW: Check for trend continuation entry (consolidation breakout)
        if planner_cfg.enable_trend_continuation:
            continuation_entry = _find_trend_continuation_entry(
                is_bullish=True,
                smc_snapshot=smc_snapshot,
                current_price=current_price,
                atr=atr,
                config=config,
                planner_cfg=planner_cfg,
            )
            if continuation_entry:
                logger.info(
                    "✅ TREND CONTINUATION: Using consolidation breakout entry (no fresh OB/FVG)"
                )
                return continuation_entry, True  # used_structure=True since we have valid pattern

    else:  # Bearish
        # Look for bearish OB or FVG above current price
        # FIXED: Only include OBs where:
        #   1. Price is INSIDE the OB (immediate entry possible), OR
        #   2. OB.low is at or above current price (pullback entry)
        # This prevents selecting OBs where the entry zone is entirely below current price
        obs = [
            ob
            for ob in smc_snapshot.order_blocks
            if ob.direction == "bearish"
            and ob.high > current_price
            and (ob.low >= current_price or (ob.low <= current_price <= ob.high))
        ]

        # NEW: Premium/Discount Enforcement
        if planner_cfg.pd_compliance_required:
            pre_pd_count = len(obs)
            # Check if OB acts as resistance in Premium (with tolerance)
            obs = [
                ob
                for ob in obs
                if _is_in_correct_pd_zone(
                    ob.low, False, smc_snapshot, primary_tf, planner_cfg.pd_compliance_tolerance
                )
            ]
            if len(obs) < pre_pd_count:
                logger.debug(
                    f"PD Gate (Short): Filtered {pre_pd_count - len(obs)} Bearish OBs in Discount"
                )

        # Filter to allowed ENTRY timeframes
        if allowed_tfs:
            obs = [ob for ob in obs if ob.timeframe.lower() in allowed_tfs]
            logger.debug(
                f"Filtered bearish OBs to entry_timeframes {allowed_tfs}: {len(obs)} remain"
            )

        max_pullback_atr = getattr(config, "max_pullback_atr", 3.0)
        # Fix: If inside OB (price >= low), distance is 0.
        obs = [ob for ob in obs if (max(0.0, ob.low - current_price) / atr) <= max_pullback_atr]
        obs = [ob for ob in obs if ob.mitigation_level <= planner_cfg.ob_mitigation_max]
        # Validate OB integrity: price inside the zone counts as "tapped".
        # Only allow in-zone OBs if mitigation is still low (zone is fresh).
        if multi_tf_data and primary_tf in getattr(multi_tf_data, "timeframes", {}):
            _df_primary = multi_tf_data.timeframes[primary_tf]  # available for future candle-close checks
            tapped_threshold = planner_cfg.ob_mitigation_max * 0.5
            validated = []
            for ob in obs:
                price_inside = ob.low <= current_price <= ob.high
                if price_inside and ob.mitigation_level > tapped_threshold:
                    logger.debug(
                        f"Filtered heavily-mitigated in-zone bearish OB (tapped): "
                        f"low={ob.low} high={ob.high} mitigation={ob.mitigation_level:.2f}"
                    )
                else:
                    validated.append(ob)
            obs = validated

        logger.debug(
            f"Bearish OBs for entry zone: {len(obs)} (all grades allowed, confluence handles quality)"
        )

        # NEW: Validate LTF OBs have HTF backing
        skip_htf_backing = config.profile in ("precision", "surgical")
        if skip_htf_backing:
            logger.debug("HTF backing filter SKIPPED for bearish OBs (%s mode)", config.profile)
        if not skip_htf_backing:
            validated_backing = []
            mode_key = map_profile_to_relativity(getattr(config, "profile", "stealth"))
            rel = RELATIVITY_MAP.get(mode_key, RELATIVITY_MAP["intraday"])
            ltf_tfs = (rel["exec"],)
            htf_tfs = (rel["plan"], rel["context"], "1d", "1w")
            for ob in obs:
                if ob.timeframe in ltf_tfs:
                    # Check for overlapping HTF structure (OB or FVG)
                    has_backing = False
                    # Check OBs
                    for htf_ob in smc_snapshot.order_blocks:
                        if htf_ob.timeframe in htf_tfs and htf_ob.direction == "bearish":
                            if htf_ob.low <= ob.high and htf_ob.high >= ob.low:
                                has_backing = True
                                break
                    # Check FVGs
                    if not has_backing:
                        for htf_fvg in smc_snapshot.fvgs:
                            if htf_fvg.timeframe in htf_tfs and htf_fvg.direction == "bearish":
                                if (
                                    htf_fvg.bottom <= ob.high and htf_fvg.top >= ob.low
                                ):  # FVG bottom/top are low/high
                                    has_backing = True
                                    break
                    if has_backing:
                        validated_backing.append(ob)
                else:
                    validated_backing.append(ob)
            obs = validated_backing

        mode_key = map_profile_to_relativity(getattr(config, "profile", "stealth"))
        rel = RELATIVITY_MAP.get(mode_key, RELATIVITY_MAP["intraday"])
        tf_weight = {
            rel["exec"]: 0.8,
            rel["plan"]: 1.2,
            rel["context"]: 1.5,
            "1d": 2.0,
            "1w": 2.5,
        }

        def _ob_score_bearish(ob: OrderBlock) -> float:
            base_score = ob.freshness_score * tf_weight.get(ob.timeframe, 1.0)
            displacement_factor = 1.0 + (
                ob.displacement_strength * planner_cfg.ob_displacement_weight
            )
            mitigation_penalty = 1.0 - min(ob.mitigation_level, 1.0)

            # Smart Entry: Sweep Boost
            sweep_boost = 1.0
            if _has_sweep_backing(
                ob, smc_snapshot.liquidity_sweeps, planner_cfg.sweep_lookback_candles
            ):
                sweep_boost = planner_cfg.sweep_backing_boost

            return base_score * displacement_factor * mitigation_penalty * sweep_boost

        fvgs = [
            fvg
            for fvg in smc_snapshot.fvgs
            if fvg.direction == "bearish" and fvg.bottom > current_price
        ]
        if allowed_tfs:
            fvgs = [fvg for fvg in fvgs if fvg.timeframe in allowed_tfs]
            logger.debug(
                f"Filtered bearish FVGs to entry_timeframes {allowed_tfs}: {len(fvgs)} remain"
            )

        if planner_cfg.pd_compliance_required:
            pre_pd_count = len(fvgs)
            fvgs = [
                f
                for f in fvgs
                if _is_in_correct_pd_zone(
                    f.bottom, False, smc_snapshot, primary_tf, planner_cfg.pd_compliance_tolerance
                )
            ]
            if len(fvgs) < pre_pd_count:
                logger.debug(
                    f"PD Gate (Short): Filtered {pre_pd_count - len(fvgs)} Bearish FVGs in Discount"
                )

        logger.critical(
            f"Bearish entry zone: found {len(obs)} OBs and {len(fvgs)} FVGs above current price"
        )

        if obs:
            best_ob = max(obs, key=_ob_score_bearish)

            # Log sweep boost
            if _has_sweep_backing(
                best_ob, smc_snapshot.liquidity_sweeps, planner_cfg.sweep_lookback_candles
            ):
                logger.info(
                    f"🐢 TURTLE SOUP: Bearish Entry OB {best_ob.timeframe} backed by liquidity sweep (Score Boosted {planner_cfg.sweep_backing_boost}x)"
                )
            entry_tf_used = best_ob.timeframe  # Track for metadata
            logger.critical(
                f"ENTRY ZONE: Using bearish OB - high={best_ob.high}, low={best_ob.low}, ATR={atr}, TF={entry_tf_used}"
            )
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
                    and confluence_breakdown.nearest_htf_level_type == "resistance"
                    and (confluence_breakdown.htf_proximity_atr or 99)
                    <= planner_cfg.htf_bias_max_atr_distance
                ):
                    htf_distance = confluence_breakdown.htf_proximity_atr or 99
                    htf_factor = _calculate_htf_bias_factor(htf_distance, planner_cfg)
            except Exception:
                pass

            offset = base_offset * htf_factor * atr
            near_entry = best_ob.low + offset
            offset = base_offset * htf_factor * atr

            # FIX: Clamp offset to prevent inversion for Shorts (near > far)
            zone_width = best_ob.high - best_ob.low
            max_offset = zone_width / 2.0 * 0.9
            if offset > max_offset:
                offset = max(max_offset, 0.0)

            near_entry = best_ob.low + offset
            far_entry = best_ob.high - offset

            # When price is already inside the OB, apply aggressive-fill buffer for shorts.
            price_inside_ob = current_price <= best_ob.high and current_price >= best_ob.low
            if near_entry < current_price:
                in_zone_buffer = min(planner_cfg.market_entry_aggression_atr * atr, current_price * 0.001)
                near_entry = current_price - in_zone_buffer
                far_entry = max(far_entry, current_price)  # anchor to current_price to prevent collision
                logger.info(
                    "📦 IN-ZONE ENTRY (SHORT OB): near=%.4f (price=%.4f - buf=%.4f), far=%.4f (inside OB: %s)",
                    near_entry, current_price, in_zone_buffer, far_entry, price_inside_ob,
                )

            logger.info(
                "📦 ENTRY ZONE CALC: OB=[%.2f-%.2f] | offset=%.2f (base=%.2f * htf=%.2f * atr=%.2f) | near=%.2f, far=%.2f | price=%.2f",
                best_ob.low,
                best_ob.high,
                offset,
                base_offset,
                htf_factor,
                atr,
                near_entry,
                far_entry,
                current_price,
            )

            rationale = f"Entry zone based on {best_ob.timeframe} bearish order block"
            if price_inside_ob:
                rationale += " (price inside OB - aggressive fill)"
            used_structure = True
            entry_zone = EntryZone(near_entry=near_entry, far_entry=far_entry, rationale=rationale)
            entry_zone.entry_tf_used = entry_tf_used  # type: ignore
            entry_zone.ob_mitigation = best_ob.mitigation_level  # type: ignore

            # Calculate pullback probability
            entry_zone.pullback_probability = _calculate_pullback_probability(  # type: ignore
                is_bullish=False,
                current_price=current_price,
                entry_zone_mid=entry_zone.midpoint,
                atr=atr,
                indicators=indicators,
                smc_snapshot=smc_snapshot,
                confluence_breakdown=confluence_breakdown,
            )
            return entry_zone, used_structure

        elif fvgs:
            # Score FVGs by quality (freshness, mitigation, displacement, TF weight)
            # mirrors _ob_score_bearish so FVG selection is not purely proximity-based
            def _fvg_score_bearish(fvg) -> float:
                freshness = getattr(fvg, "freshness_score", 0.5)
                mitigation = 1.0 - min(getattr(fvg, "overlap_with_price", 0.0), 1.0)
                displacement = 1.0 + getattr(fvg, "displacement_strength", 0.0) * planner_cfg.ob_displacement_weight
                return freshness * mitigation * displacement * tf_weight.get(fvg.timeframe, 1.0)

            eligible_fvgs = [fvg for fvg in fvgs if fvg.overlap_with_price < planner_cfg.fvg_overlap_max]
            if not eligible_fvgs:
                eligible_fvgs = fvgs
            best_fvg = max(eligible_fvgs, key=_fvg_score_bearish)
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
                    and confluence_breakdown.nearest_htf_level_type == "resistance"
                    and (confluence_breakdown.htf_proximity_atr or 99)
                    <= planner_cfg.htf_bias_max_atr_distance
                ):
                    htf_distance = confluence_breakdown.htf_proximity_atr or 99
                    htf_factor = _calculate_htf_bias_factor(htf_distance, planner_cfg)
            except Exception:
                pass

            offset = base_offset * htf_factor * atr

            # FIX: Clamp offset to prevent inversion
            zone_width = best_fvg.top - best_fvg.bottom
            max_offset = abs(zone_width) / 2.0 * 0.9
            if offset > max_offset:
                offset = max(max_offset, 0.0)

            near_entry = best_fvg.top - offset   # Close to FVG top (resistance approach from above)
            far_entry = best_fvg.bottom + offset  # Deeper into FVG

            # When price is already inside the FVG, apply aggressive-fill buffer for shorts.
            if near_entry < current_price:
                in_zone_buffer = min(planner_cfg.market_entry_aggression_atr * atr, current_price * 0.001)
                near_entry = current_price - in_zone_buffer
                far_entry = max(far_entry, current_price)  # anchor to current_price to prevent collision
                logger.info(
                    "📦 IN-ZONE ENTRY (SHORT FVG): near=%.4f (price=%.4f - buf=%.4f), far=%.4f",
                    near_entry, current_price, in_zone_buffer, far_entry,
                )

            rationale = f"Entry zone based on {best_fvg.timeframe} bearish FVG"
            used_structure = True
            entry_zone = EntryZone(near_entry=near_entry, far_entry=far_entry, rationale=rationale)
            entry_zone.entry_tf_used = entry_tf_used  # type: ignore

            # Calculate pullback probability
            entry_zone.pullback_probability = _calculate_pullback_probability(  # type: ignore
                is_bullish=False,
                current_price=current_price,
                entry_zone_mid=entry_zone.midpoint,
                atr=atr,
                indicators=indicators,
                smc_snapshot=smc_snapshot,
                confluence_breakdown=confluence_breakdown,
            )
            return entry_zone, used_structure

        # NEW: Check for trend continuation entry (consolidation breakout)
        if planner_cfg.enable_trend_continuation:
            continuation_entry = _find_trend_continuation_entry(
                is_bullish=False,
                smc_snapshot=smc_snapshot,
                current_price=current_price,
                atr=atr,
                config=config,
                planner_cfg=planner_cfg,
            )
            if continuation_entry:
                logger.info(
                    "✅ TREND CONTINUATION: Using consolidation breakout entry (no fresh OB/FVG)"
                )
                return continuation_entry, True  # used_structure=True since we have valid pattern

    # Final fallback if no OBs, FVGs, or consolidations foundt price with fixed tight stop logic (if no structure found)
    # The caller will handle this case (likely rejecting plan if strict mode)
    used_structure = False

    # Adaptive offset for fallback (dynamic based on ATR)
    fallback_offset = atr * 0.5

    if is_bullish:
        entry_zone = EntryZone(
            near_entry=current_price,
            far_entry=current_price - fallback_offset,
            rationale=f"ATR fallback entry zone (no SMC structure found): offset={fallback_offset:.4f}",
        )
    else:
        # Bearish fallback: price rallies up into the zone.
        # near_entry = first touch (bottom of zone, lower price), far_entry = deeper resistance (higher price).
        entry_zone = EntryZone(
            near_entry=current_price + fallback_offset * 0.5,
            far_entry=current_price + fallback_offset,
            rationale=f"ATR fallback entry zone (no SMC structure found): offset={fallback_offset:.4f}",
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
        htf_trend=None,  # Caller can provide via confluence_breakdown if needed
        smc_snapshot=smc_snapshot,
        confluence_breakdown=confluence_breakdown,
        config=config,
    )
    entry_zone.pullback_probability = pullback_prob  # type: ignore

    return entry_zone, used_structure


def _find_trend_continuation_entry(
    is_bullish: bool,
    smc_snapshot: SMCSnapshot,
    current_price: float,
    atr: float,
    config: ScanConfig,
    planner_cfg: PlannerConfig,
) -> Optional[EntryZone]:
    """
    Find trend continuation entry via consolidation breakout + retest.

    Only called when no fresh OBs/FVGs are available (fallback strategy).

    Args:
        is_bullish: True for long, False for short
        smc_snapshot: SMC patterns including consolidations
        current_price: Current market price
        atr: Average True Range for validation
        config: Scanner configuration
        planner_cfg: Planner configuration

    Returns:
        EntryZone if valid consolidation breakout found, None otherwise
    """
    if not planner_cfg.enable_trend_continuation:
        logger.debug("Trend continuation DISABLED for this mode")
        return None

    logger.info(
        f"🔄 Checking for trend continuation entry (consolidations available: {len(smc_snapshot.consolidations)})"
    )

    # Get allowed entry timeframes
    allowed_tfs = set(getattr(config, "entry_timeframes", ()))
    if not allowed_tfs:
        mode_key = map_profile_to_relativity(getattr(config, "profile", "stealth"))
        rel = RELATIVITY_MAP.get(mode_key, RELATIVITY_MAP["intraday"])
        allowed_tfs = {rel["exec"], rel["plan"]}  # Default LTF/MTF from mode

    # Filter consolidations by direction and state
    valid_consolidations = []
    for c in smc_snapshot.consolidations:
        reasons = []
        if not c.is_valid_for_entry:
            reasons.append("not_valid_for_entry")
        if c.timeframe.lower() not in [tf.lower() for tf in allowed_tfs]:
            reasons.append(f"tf_mismatch({c.timeframe})")
        if c.breakout_direction != ("bullish" if is_bullish else "bearish"):
            reasons.append(f"wrong_dir({c.breakout_direction})")
        if c.touches < planner_cfg.consolidation_min_touches:
            reasons.append(
                f"insufficient_touches({c.touches}<{planner_cfg.consolidation_min_touches})"
            )

        if not reasons:
            valid_consolidations.append(c)
        else:
            logger.debug(f"⚠️ Filtered consolidation ({c.timeframe}): {', '.join(reasons)}")

    consolidations = valid_consolidations

    if not consolidations:
        logger.info("No valid trend continuation consolidations found after filtering")
        return None

    # Select best consolidation (highest strength score)
    best = max(consolidations, key=lambda c: c.strength_score)

    logger.info(
        f"🔄 Trend Continuation: {best.timeframe} consolidation "
        f"({best.touches} touches, strength={best.strength_score:.2f}, "
        f"breakout={best.breakout_direction})"
    )

    # Build entry zone
    if is_bullish:
        # Bullish breakout retest
        # Near entry: Retest level (support)
        # Far entry: Consolidation low ( failed breakdown fallback)
        near_entry = best.retest_level or best.high
        far_entry = best.low
    else:
        # Bearish breakout retest
        # Near entry: Retest level (resistance)
        # Far entry: Consolidation high (failed breakout fallback)
        near_entry = best.retest_level or best.low
        far_entry = best.high

    # Validate entry zone positioning
    if is_bullish:
        # Long: near_entry should be at or below current price
        if near_entry > current_price:
            logger.warning(
                f"Trend continuation near_entry ({near_entry}) > price ({current_price}), skipping"
            )
            return None
    else:
        # Short: near_entry should be at or above current price
        if near_entry < current_price:
            logger.warning(
                f"Trend continuation near_entry ({near_entry}) < price ({current_price}), skipping"
            )
            return None

    entry_zone = EntryZone(
        near_entry=near_entry,
        far_entry=far_entry,
        rationale=(
            f"Trend continuation: {best.timeframe} consolidation breakout + retest "
            f"({best.touches} touches, strength={best.strength_score:.2f}"
            f"{', FVG confirmed' if best.fvg_at_breakout else ''})"
        ),
    )

    # Add metadata
    entry_zone.entry_tf_used = best.timeframe  # type: ignore
    entry_zone.pullback_probability = 0.7  # type: ignore  # Moderate probability for consolidation retests
    entry_zone.consolidation_source = best  # type: ignore  # Attach for stop calculation

    return entry_zone
