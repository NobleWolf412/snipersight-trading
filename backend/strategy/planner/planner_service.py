"""
Trade Planner Service Module

Generates complete, actionable trade plans based on confluence analysis.
Logic is delegated to specialized engines:
- Entry Engine: Entry zones, validation, archetype mapping
- Risk Engine: Stop loss, targets, leverage adjustments
- Regime Engine: Market regime analysis (volatility, trend)

Following the "No-Null, Actionable Outputs" principle.
"""

from typing import Optional, List, Literal
from datetime import datetime
from loguru import logger

from backend.shared.models.planner import TradePlan, StopLoss
from backend.shared.models.data import MultiTimeframeData
from backend.shared.models.smc import SMCSnapshot
from backend.shared.models.indicators import IndicatorSet
from backend.shared.models.scoring import ConfluenceBreakdown
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.planner_config import PlannerConfig
from backend.bot.telemetry.logger import get_telemetry_logger
from backend.bot.telemetry.events import create_signal_rejected_event, create_alt_stop_suggested_event

# Engine Imports
from backend.strategy.planner.entry_engine import _calculate_entry_zone, _map_setup_to_archetype
from backend.strategy.planner.risk_engine import (
    _calculate_stop_loss,
    _calculate_targets,
    _derive_trade_type,
    _adjust_stop_for_leverage,
    _scale_stop_for_leverage,
    _adjust_targets_for_leverage,
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
    # Stealth = Hybrid Trade (All types, balanced mix)
    "stealth": "Hybrid Trade",
    "stealth_balanced": "Hybrid Trade",
    # Surgical = Scalp Trade (Minutes, extreme precision)
    "surgical": "Scalp Trade",
    "precision": "Scalp Trade",
    # Strike = Day Trade (Hours, aggressive momentum)
    "strike": "Day Trade",
    "intraday_aggressive": "Day Trade",
    # Fallback
    "balanced": "Swing Trade",
}


def get_trade_label_for_mode(mode: str) -> str:
    """Get trader-friendly trade label based on scanner mode or profile."""
    mode_lower = (mode or "stealth").lower()
    return MODE_TO_TRADE_LABEL.get(mode_lower, "Swing Trade")  # Default to Swing


def _calculate_liquidation_metadata(
    is_bullish: bool,
    near_entry: float,
    stop_level: float,
    leverage: float,
    mmr: float = 0.004,
) -> dict:
    """
    Estimate approximate liquidation price and cushion from entry.

    Used to identify high-liquidation-risk plans and suggest alternative stops.

    Args:
        is_bullish: Trade direction
        near_entry: Entry price
        stop_level: Planned stop loss level
        leverage: Position leverage (e.g., 5.0 for 5x)
        mmr: Maintenance Margin Rate (default 0.4%)

    Returns:
        dict with approx_liq_price, cushion_pct, risk_band, etc.
    """
    try:
        if leverage <= 0:
            leverage = 1.0
        # Simplified liq price: entry ± (1/leverage - mmr) * entry
        margin_buffer = (1.0 / leverage) - mmr
        if is_bullish:
            liq_price = near_entry * (1.0 - margin_buffer)
            cushion_pct = ((stop_level - liq_price) / near_entry) * 100
        else:
            liq_price = near_entry * (1.0 + margin_buffer)
            cushion_pct = ((liq_price - stop_level) / near_entry) * 100

        if cushion_pct >= 50:
            risk_band = "comfortable"
        elif cushion_pct >= 30:
            risk_band = "moderate"
        else:
            risk_band = "high"

        return {
            "assumed_mmr": mmr,
            "approx_liq_price": round(liq_price, 6),
            "cushion_pct": round(cushion_pct, 2),
            "risk_band": risk_band,
            "direction": "long" if is_bullish else "short",
        }
    except Exception:
        return {
            "assumed_mmr": mmr,
            "approx_liq_price": near_entry * (0.85 if is_bullish else 1.15),
            "cushion_pct": 50.0,
            "risk_band": "comfortable",
            "direction": "long" if is_bullish else "short",
        }


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
    expected_trade_type: Optional[str] = None,
    volume_profile: Optional["VolumeProfile"] = None,  # NEW: For HVN/LVN target filtering
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
    if not hasattr(indicators, "by_timeframe"):
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
            for tf_candidate in ["15m", "1h", "5m", "4h", "1d"]:
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
    if getattr(config, "planner", None):
        planner_cfg = config.planner
    elif expected_trade_type:
        planner_cfg = PlannerConfig.defaults_for_mode(expected_trade_type)
        logger.info(
            f"🔧 Planner Config: mode={expected_trade_type}, trend_continuation={planner_cfg.enable_trend_continuation}"
        )
    else:
        # Fallback to intraday for unknown trade types
        planner_cfg = PlannerConfig.defaults_for_mode("intraday")
        logger.info(
            f"🔧 Planner Config: mode=intraday (fallback), trend_continuation={planner_cfg.enable_trend_continuation}"
        )

    # Apply overlays
    overrides = getattr(config, "overrides", None) or {}
    if overrides:
        for key, value in overrides.items():
            if hasattr(planner_cfg, key):
                setattr(planner_cfg, key, value)

    telemetry = get_telemetry_logger()
    run_id = datetime.utcnow().strftime("run-%Y%m%d")

    if primary_indicators.atr is None or primary_indicators.atr <= 0:
        telemetry.log_event(
            create_signal_rejected_event(
                run_id=run_id,
                symbol=symbol,
                reason="atr_invalid",
                diagnostics={"atr": primary_indicators.atr},
            )
        )
        raise ValueError("ATR required for trade planning and must be positive")
    atr = primary_indicators.atr

    leverage = max(1, int(getattr(config, "leverage", 1) or 1))

    # FIX: Handle both "LONG"/"SHORT" and "bullish"/"bearish" direction formats
    # Confluence service returns "LONG"/"SHORT", but code was checking for "bullish"
    direction_lower = direction.lower()
    is_bullish = direction_lower in ("long", "bullish")

    # DEBUG: Log direction conversion
    logger.info(f"🔍 Direction conversion: '{direction}' -> is_bullish={is_bullish}")

    # Map raw setup string to archetype
    # Now imported from entry_engine
    archetype = _map_setup_to_archetype(setup_type)

    logger.info(
        f"Generating plan for {symbol} ({direction}) | ATR={atr:.2f} | Setup={setup_type} ({archetype})"
    )

    # === 1. Calculate Entry Zone (Delegate to Entry Engine) ===
    try:
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
            indicators=indicators,  # Pass full set for regime detection
        )
    except Exception as e:
        logger.error(f"Entry zone calculation failed for {symbol}: {e}")
        raise ValueError(f"Entry zone calculation failed: {e}") from e

    # === 2. Calculate Stop Loss (Delegate to Risk Engine) ===
    # Extract consolidation source if entry was from Trend Continuation
    consolidation_for_stop = getattr(entry_zone, "consolidation_source", None)

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
            indicators_by_tf=indicators.by_timeframe,  # Pass dict for structure TF lookup
            consolidation_for_stop=consolidation_for_stop,  # NEW: Pass consolidation for stop
        )
    except ValueError as e:
        logger.warning(f"Stop loss calculation failed: {e}")
        telemetry.log_event(
            create_signal_rejected_event(
                run_id=run_id,
                symbol=symbol,
                reason="stop_loss_calc_failed",
                diagnostics={"error": str(e)},
            )
        )
        raise

    # DEBUG: Log entry and stop values BEFORE leverage adjustment
    logger.info(
        "🔍 DEBUG ENTRY/STOP (before leverage adj): Direction=%s | Entry=[%.4f-%.4f] | Stop=%.4f | Current=%.4f",
        "LONG" if is_bullish else "SHORT",
        entry_zone.far_entry,
        entry_zone.near_entry,
        stop_loss.level,
        current_price,
    )

    # === 3. Leverage Adjustment for Stop (Delegate to Risk Engine) ===
    # A. Scale stop for tier-based tolerance (Extended, Standard, Tight)
    # This adjusts the 'room' or 'cushion' based on leverage risk tiers
    scaled_stop_level, scale_meta = _scale_stop_for_leverage(
        stop_level=stop_loss.level,
        entry_price=entry_zone.far_entry,
        leverage=leverage,
        is_bullish=is_bullish
    )

    # B. Check liquidation risk (Safety override)
    adjusted_stop_level, was_liq_adjusted, liq_meta = _adjust_stop_for_leverage(
        stop_level=scaled_stop_level,
        near_entry=entry_zone.near_entry,
        leverage=leverage,
        is_bullish=is_bullish,
    )

    # If scaled or liq-adjusted, create new stop object
    if scaled_stop_level != stop_loss.level or was_liq_adjusted:
        logger.info(
            f"Stop loss adjusted for {leverage}x leverage: "
            f"Original={stop_loss.level:.4f} → Scaled={scaled_stop_level:.4f} "
            f"→ Final={adjusted_stop_level:.4f} (was_liq_adjusted={was_liq_adjusted})"
        )
        
        # Merge rationale
        new_rationale = stop_loss.rationale
        if scale_meta.get("tier") and scale_meta["tier"] != "standard":
            new_rationale += f" [Leverage {scale_meta['tier'].capitalize()} Adjustment]"
        if was_liq_adjusted:
            new_rationale += " [Liquidation Safety Adjusted]"

        stop_loss = StopLoss(
            level=adjusted_stop_level,
            distance_atr=abs(entry_zone.far_entry - adjusted_stop_level) / atr,
            rationale=new_rationale,
            structure_tf_used=stop_loss.structure_tf_used
        )
        # DEBUG: Log after leverage adjustment
        logger.info(
            "🔍 DEBUG ENTRY/STOP (after leverage adj): Direction=%s | Entry=[%.4f-%.4f] | Stop=%.4f (adjusted from %.4f)",
            "LONG" if is_bullish else "SHORT",
            entry_zone.far_entry,
            entry_zone.near_entry,
            adjusted_stop_level,
            stop_loss.level,
        )

    # === 4. Calculate Targets (Delegate to Risk Engine) ===
    # Get regime label for target adjustment
    regime_label = get_atr_regime(indicators, current_price)

    try:
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
            indicators=indicators,
            volume_profile=volume_profile,  # NEW: For HVN/LVN target filtering
        )
    except Exception as e:
        logger.error(f"Target calculation failed for {symbol}: {e}")
        raise ValueError(f"Target calculation failed: {e}") from e

    # === 5. Leverage Adjustment for Targets (Delegate to Risk Engine) ===
    try:
        targets, target_adj_meta = _adjust_targets_for_leverage(
            targets=targets,
            leverage=leverage,
            entry_price=(entry_zone.near_entry + entry_zone.far_entry) / 2,
            is_bullish=is_bullish,
        )
    except Exception as e:
        logger.error(f"Target leverage adjustment failed for {symbol}: {e}")
        raise ValueError(f"Target leverage adjustment failed: {e}") from e

    # === 5b. Distribute Target Percentages ===
    # Targets must sum to 100% for TradePlan validation
    if targets:
        n = len(targets)
        if n == 1:
            targets[0].percentage = 100.0
        elif n == 2:
            targets[0].percentage = 60.0
            targets[1].percentage = 40.0
        elif n == 3:
            targets[0].percentage = 50.0
            targets[1].percentage = 30.0
            targets[2].percentage = 20.0
        else:
            # For 4+ targets, use a decaying distribution
            # TP1: 40%, TP2: 30%, TP3: 20%, others: split remaining 10%
            targets[0].percentage = 40.0
            targets[1].percentage = 30.0
            targets[2].percentage = 20.0
            
            remaining_pct = 10.0
            others_count = n - 3
            pct_per_other = remaining_pct / others_count
            for i in range(3, n):
                targets[i].percentage = round(pct_per_other, 1)

        # Ensure absolute sum is 100.0 by adjusting the last target for floating point residue
        current_sum = sum(t.percentage for t in targets)
        if current_sum != 100.0:
            targets[-1].percentage += (100.0 - current_sum)
            targets[-1].percentage = round(targets[-1].percentage, 1)

        logger.debug(f"Target percentages assigned: {[t.percentage for t in targets]} (Sum: {sum(t.percentage for t in targets)}%)")

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
        tp1_dist = abs(targets[0].level - ((entry_zone.near_entry + entry_zone.far_entry) / 2))
        tp1_move_pct = (tp1_dist / current_price) * 100

    trade_type = _derive_trade_type(
        target_move_pct=tp1_move_pct,
        stop_distance_atr=stop_loss.distance_atr,
        structure_timeframes=structure_tfs_tuple,
        primary_tf=primary_tf,
        expected_trade_type=(getattr(config, "expected_trade_type", None) or expected_trade_type),
    )

    # === DEBUG: Log trade type derivation for BNB failure investigation ===
    logger.info(
        f"🔍 TRADE TYPE DERIVATION | {symbol} | Derived: '{trade_type}' | "
        f"TP1 Move: {tp1_move_pct:.2f}% | Stop: {stop_loss.distance_atr:.2f} ATR | "
        f"Structure TFs: {structure_tfs_tuple} | Primary TF: {primary_tf} | "
        f"Expected Type: {(getattr(config, 'expected_trade_type', None) or expected_trade_type)}"
    )

    # === TRADE TYPE VALIDATION ===
    # Enforce mode-specific trade type restrictions (e.g., Overwatch = swing only)
    allowed_types = getattr(config, "allowed_trade_types", ("swing", "intraday", "scalp"))
    
    # === DEBUG: Log validation check for all symbols ===
    mode_name = getattr(config, "profile", "unknown")
    logger.info(
        f"🔍 TRADE TYPE VALIDATION | {symbol} | Mode: {mode_name} | "
        f"Derived: '{trade_type}' | Allowed: {allowed_types} | "
        f"PASS: {trade_type in allowed_types if allowed_types else True}"
    )
    
    if allowed_types and trade_type not in allowed_types:
        # Build a human-readable, mode-aware rejection message
        geometry_summary = f"TP1 move: {tp1_move_pct:.1f}% · Stop: {stop_loss.distance_atr:.1f} ATR"
        
        mode_messages = {
            "macro_surveillance": (
                f"Setup geometry is {trade_type}-sized ({geometry_summary}), "
                f"but Overwatch only accepts swing trades anchored to 4H/1D structure. "
                f"This setup lacks the HTF alignment required for macro-level positioning."
            ),
            "precision": (
                f"Structure on this pair is {trade_type}-sized ({geometry_summary}). "
                f"Surgical requires intraday or scalp entries — tight stops under 3 ATR and TP1 under ~5%. "
                f"No low-timeframe entry zone with suitable geometry was found. "
                f"Try Overwatch or Stealth for this setup."
            ),
            "strike": (
                f"Derived a {trade_type} setup ({geometry_summary}), "
                f"but Strike mode targets momentum-driven intraday and scalp plays. "
                f"This move is too large for Strike's risk parameters. "
                f"Try Overwatch for swing-sized setups."
            ),
            "tactical": (
                f"Derived trade type '{trade_type}' ({geometry_summary}) "
                f"is not supported in Stealth mode. "
                f"Stealth accepts swing and intraday setups — scalp-only geometry was found."
            ),
        }
        
        rejection_msg = mode_messages.get(
            mode_name,
            (
                f"Trade type mismatch: market structure produced a '{trade_type}' setup "
                f"({geometry_summary}), which is not compatible with {mode_name} mode. "
                f"Allowed types: {', '.join(allowed_types)}."
            )
        )
        
        logger.warning(f"❌ {symbol} REJECTED ({mode_name}) | {trade_type} setup not allowed | {geometry_summary}")
        
        telemetry.log_event(
            create_signal_rejected_event(
                run_id=run_id,
                symbol=symbol,
                reason="trade_type_mismatch",
                diagnostics={
                    "derived_type": trade_type,
                    "allowed_types": allowed_types,
                    "mode": mode_name,
                    "tp1_move_pct": tp1_move_pct,
                    "stop_atr": stop_loss.distance_atr,
                },
            )
        )
        raise ValueError(rejection_msg)


    # DEBUG: Log final values before TradePlan validation
    try:
        targets_levels = [f"{t.level:.4f}" for t in targets[:3]] if targets else []
        logger.info(
            f"🔍 DEBUG FINAL VALUES (before TradePlan): Direction={'LONG' if is_bullish else 'SHORT'} | Entry=[{entry_zone.far_entry:.4f}-{entry_zone.near_entry:.4f}] | Stop={stop_loss.level:.4f} | Targets={targets_levels}"
        )

        plan = TradePlan(
            symbol=symbol,
            direction=direction,
            timestamp=datetime.utcnow(),
            entry_zone=entry_zone,
            stop_loss=stop_loss,
            targets=targets,
            # Use TP1 R:R for display (first realistic exit).
            # Using targets[-1] inflates R:R with extreme extension targets (37R+).
            # TP1 is the conservative, industry-standard reference for R:R evaluation.
            risk_reward_ratio=targets[0].rr_ratio if targets else 0.0,

            setup_type={
                "scalp": "Scalp Trade",
                "intraday": "Day Trade",
                "swing": "Swing Trade",
            }.get(
                trade_type, "Day Trade"
            ),  # Use dynamic geometry-based label
            timeframe=primary_tf,
            status="PENDING",
            trade_type=trade_type,
            confidence_score=confluence_breakdown.total_score,
            confluence_breakdown=confluence_breakdown,
        )

        # === GENERATE MISSION RATIONALE ===
        # Build a rich, price-detail-aware briefing readable as bullet points on the frontend
        rationale_parts = []
        
        # 1. Core Thesis — direction, pair, setup archetype
        rationale_parts.append(
            f"MISSION OBJECTIVE: {direction} {symbol} ({setup_type.replace('_', ' ')})"
        )
        
        # 2. Entry Logic — include the actual price zone
        entry_near = entry_zone.near_entry
        entry_far  = entry_zone.far_entry
        entry_desc = entry_zone.rationale or "structure-based entry zone"
        rationale_parts.append(
            f"ENTRY LOGIC: {entry_desc} | Zone: {entry_far:.4f} → {entry_near:.4f}"
        )
        
        # 3. Risk Mitigation — stop level + distance as % of entry
        stop_lvl = stop_loss.level
        stop_pct = abs(entry_near - stop_lvl) / entry_near * 100
        stop_desc = stop_loss.rationale or "structure-based stop"
        rationale_parts.append(
            f"RISK MITIGATION: {stop_desc} | Stop: {stop_lvl:.4f} ({stop_pct:.2f}% from entry)"
        )
        
        # 4. Target Analysis — first target with R:R and price
        if targets:
            tp1 = targets[0]
            tp1_pct = abs(tp1.level - entry_near) / entry_near * 100
            tp_label = tp1.rationale or "structural target"
            rationale_parts.append(
                f"TARGET ANALYSIS: {tp_label} | TP1: {tp1.level:.4f} "
                f"(+{tp1_pct:.2f}%, {tp1.rr_ratio:.1f}R)"
            )
        
        # 5. Top Confluence Drivers — name + score
        top_factors = sorted(
            confluence_breakdown.factors, key=lambda f: f.score * f.weight, reverse=True
        )[:3]
        if top_factors:
            drivers = ", ".join([f"{f.name.replace('_', ' ')} ({f.score:.0f})" for f in top_factors])
            rationale_parts.append(f"KEY DRIVER CONFLUENCE: {drivers}")
            
        plan.rationale = "\n\n".join(rationale_parts)


        # === DEBUG LOGGING ===
        logger.info(
            f"📋 TRADE PLAN: {symbol} {direction} | "
            f"{len(targets)} targets | "
            f"Final R:R = {plan.risk_reward_ratio:.2f}R (from TP{len(targets)})"
        )

        # === MINIMUM R:R VALIDATION ===
        # Enforce mode-specific R:R requirements (e.g., Overwatch = 2.0R minimum)
        min_rr = getattr(config, "min_rr_ratio", 0.0)
        actual_rr = plan.risk_reward_ratio

        # Use a small epsilon to avoid floating point false rejections.
        # e.g. 1.80R being computed as 1.7999999... and failing a 1.8R threshold.
        RR_EPSILON = 0.001

        # === DEBUG: Log R:R validation for all symbols ===
        logger.info(
            f"🔍 R:R VALIDATION | {symbol} | Actual: {actual_rr:.4f}R | "
            f"Required: {min_rr:.1f}R | Mode: {getattr(config, 'profile', 'unknown')} | "
            f"PASS: {actual_rr >= (min_rr - RR_EPSILON) if min_rr > 0 else True}"
        )

        if min_rr > 0 and actual_rr < (min_rr - RR_EPSILON):
            rejection_msg = (
                f"Insufficient R:R: {actual_rr:.2f}R < {min_rr:.1f}R minimum for "
                f"{getattr(config, 'profile', 'unknown')} mode"
            )
            logger.warning(f"❌ {symbol} REJECTED | {rejection_msg}")

            telemetry.log_event(
                create_signal_rejected_event(
                    run_id=run_id,
                    symbol=symbol,
                    reason="insufficient_rr",
                    diagnostics={
                        "actual_rr": actual_rr,
                        "min_rr": min_rr,
                        "mode": getattr(config, "profile", "unknown"),
                        "trade_type": trade_type,
                        "tp1_level": targets[0].level if targets else None,
                    },
                )
            )
            raise ValueError(rejection_msg)
    except Exception as e:
        logger.error(
            f"❌ TradePlan Constructor Failed: {e} | Values: Entry={entry_zone}, Stop={stop_loss}",
            exc_info=True,
        )
        raise

    try:
        # Attach metadata
        plan.metadata = {
            "archetype": archetype,
            "atr_regime": {"label": regime_label},
            "leverage": leverage,
            "leverage_stop_adjustment": liq_meta if was_liq_adjusted else scale_meta if scale_meta else None,
            "target_adjustment": target_adj_meta,
            "structure_tfs_used": list(structure_tfs_tuple),
            "missing_critical_tfs": missing_critical_timeframes,
            # NEW: R:R best/worst case for transparent risk assessment
            # Best case: Fill at near entry (better R:R), Worst case: Fill at far entry
            "rr_best": None,
            "rr_worst": None,
            # NEW: Pullback probability from entry zone
            "pullback_probability": getattr(entry_zone, "pullback_probability", None),
            # NEW: Entry structure details for frontend display
            "entry_structure": {
                "timeframe": getattr(entry_zone, "entry_tf_used", None) or primary_tf,
                "zone_high": entry_zone.far_entry if is_bullish else entry_zone.near_entry,
                "zone_low": entry_zone.near_entry if is_bullish else entry_zone.far_entry,
                "type": (
                    "OB"
                    if "order block" in (entry_zone.rationale or "").lower()
                    else "FVG" if "fvg" in (entry_zone.rationale or "").lower() else "Zone"
                ),
                "ob_mitigation": getattr(entry_zone, "ob_mitigation", 0.0),  # 0.0-1.0
            },
        }

        # === LIQUIDATION RISK ASSESSMENT ===
        # Check if stop is dangerously close to liquidation price and suggest alternative
        try:
            liq_data = _calculate_liquidation_metadata(
                is_bullish=is_bullish,
                near_entry=entry_zone.near_entry,
                stop_level=stop_loss.level,
                leverage=leverage,
            )
            plan.metadata["liquidation_meta"] = liq_data

            if liq_data.get("risk_band") == "high":
                # Suggest a wider stop that gives more cushion from liquidation
                # Extended by 1x ATR beyond current stop
                if is_bullish:
                    alt_stop_level = stop_loss.level - atr  # Pull stop further below
                else:
                    alt_stop_level = stop_loss.level + atr  # Push stop further above

                alt_stop_data = {
                    "level": alt_stop_level,
                    "reason": "high_liquidation_risk",
                    "cushion_pct": liq_data["cushion_pct"],
                    "risk_band": liq_data["risk_band"],
                    "atr_extension": atr,
                }
                plan.metadata["alt_stop"] = alt_stop_data

                # Log telemetry event
                telemetry.log_event(
                    create_alt_stop_suggested_event(
                        run_id=run_id,
                        symbol=symbol,
                        direction=direction,
                        cushion_pct=liq_data["cushion_pct"],
                        risk_band=liq_data["risk_band"],
                        suggested_level=alt_stop_level,
                        current_stop=stop_loss.level,
                        leverage=int(leverage),
                        regime_label=regime_label,
                        recommended_buffer_atr=atr,
                    )
                )
                logger.warning(
                    f"⚠️ HIGH LIQ RISK | {symbol} | cushion={liq_data['cushion_pct']:.1f}% "
                    f"| Alt stop suggested: {alt_stop_level:.4f} (current: {stop_loss.level:.4f})"
                )
        except Exception as liq_err:
            logger.debug(f"Liquidation risk check failed (non-critical): {liq_err}")

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
    except Exception as e:
        logger.error(f"❌ Metadata Assignment Failed: {e}", exc_info=True)
        # Even if metadata fails, we should iterate return the plan (best effort)
        if plan.metadata is None:
            plan.metadata = {}  # Ensure not None

    return plan
