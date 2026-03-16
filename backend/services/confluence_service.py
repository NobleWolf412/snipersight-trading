"""
Confluence Service - Confluence scoring wrapper extracted from orchestrator.py

Wraps the existing calculate_confluence_score function from scorer.py
and provides a clean service interface for confluence calculations.

This is a lightweight wrapper approach to minimize risk while still
providing the benefits of service-based architecture.
"""

import logging
from typing import Dict, Any, Optional

from backend.engine.context import SniperContext
from backend.strategy.confluence.scorer import calculate_confluence_score, ConfluenceBreakdown

logger = logging.getLogger(__name__)


class ConflictingDirectionsException(Exception):
    """Raised when bullish and bearish scores are too close to call."""
    
    def __init__(self, message: str, bullish_breakdown: ConfluenceBreakdown, bearish_breakdown: ConfluenceBreakdown):
        super().__init__(message)
        self.bullish_breakdown = bullish_breakdown
        self.bearish_breakdown = bearish_breakdown



class ConfluenceService:
    """
    Service for computing confluence scores.

    Wraps the existing scorer.py functionality with a clean service interface.
    The heavy lifting is delegated to calculate_confluence_score.

    Usage:
        service = ConfluenceService(scanner_mode=mode)
        breakdown = service.score(context, current_price, htf_ctx, ...)
    """

    def __init__(
        self,
        scanner_mode: Optional[Any] = None,
        config: Optional[Any] = None,
    ):
        """
        Initialize confluence service.

        Args:
            scanner_mode: Scanner mode for mode-aware scoring
            config: Scan configuration
        """
        self._scanner_mode = scanner_mode
        self._config = config
        self._diagnostics: Dict[str, list] = {"confluence_rejections": []}

    @property
    def diagnostics(self) -> Dict[str, list]:
        """Get diagnostic information from last scoring."""
        return self._diagnostics

    def set_mode(self, scanner_mode):
        """Update scanner mode dynamically."""
        self._scanner_mode = scanner_mode

    def _count_recent_structure(
        self, context: SniperContext, direction: str, lookback: int = 20
    ) -> int:
        """Count recent CHoCH + BOS for a direction to detect structural bias.

        Args:
            context: SniperContext with SMC snapshot
            direction: 'LONG' or 'SHORT'
            lookback: Number of recent breaks to check

        Returns:
            Count of structural breaks in the specified direction
        """
        snap = context.smc_snapshot
        if not snap:
            return 0

        # Map LONG/SHORT to bullish/bearish (StructuralBreak uses bullish/bearish)
        target_direction = "bullish" if direction.upper() == "LONG" else "bearish"

        # Get structural breaks from snapshot (most recent first)
        breaks = getattr(snap, "structural_breaks", []) or []

        # Count breaks in specified direction within lookback
        count = 0
        for brk in breaks[:lookback]:  # Limit to recent breaks
            if hasattr(brk, "direction") and brk.direction.lower() == target_direction:
                count += 1

        return count

    def score(
        self,
        context: SniperContext,
        current_price: float,
        htf_ctx_long: Optional[Dict] = None,
        htf_ctx_short: Optional[Dict] = None,
        cycle_context: Optional[Any] = None,
        reversal_context_long: Optional[Any] = None,
        reversal_context_short: Optional[Any] = None,
    ) -> ConfluenceBreakdown:
        """
        Compute confluence score for both directions.

        Args:
            context: SniperContext with data and indicators
            current_price: Current market price
            htf_ctx_long: HTF context for bullish direction
            htf_ctx_short: HTF context for bearish direction
            cycle_context: Cycle timing context
            reversal_context_long: Reversal context for longs
            reversal_context_short: Reversal context for shorts

        Returns:
            ConfluenceBreakdown with scoring details for the best direction

        Side Effects:
            Sets context.metadata['chosen_direction'] to 'LONG' or 'SHORT'
            Sets context.metadata['alt_confluence'] with both direction scores
        """
        self._diagnostics = {"confluence_rejections": []}

        if not context.smc_snapshot or not context.multi_tf_indicators:
            raise ValueError(
                f"{context.symbol}: Missing SMC snapshot or indicators for confluence scoring"
            )

        try:
            # Score bullish direction
            bullish_breakdown = self._score_direction(
                context=context,
                direction="bullish",
                is_bullish=True,
                htf_context=htf_ctx_long,
                cycle_context=cycle_context,
                reversal_context=reversal_context_long,
                current_price=current_price,
            )

            # Score bearish direction
            bearish_breakdown = self._score_direction(
                context=context,
                direction="bearish",
                is_bullish=False,
                htf_context=htf_ctx_short,
                cycle_context=cycle_context,
                reversal_context=reversal_context_short,
                current_price=current_price,
            )

            # Log comparison for debugging
            logger.info(
                "⚖️  %s Direction eval: LONG=%.1f vs SHORT=%.1f",
                context.symbol,
                bullish_breakdown.total_score,
                bearish_breakdown.total_score,
            )

            # NEW: Require minimum margin for directional confidence
            # Close scores (within margin) are treated as indeterminate
            DIRECTION_MARGIN = 5.0  # Minimum score edge required (was 8.0 — too aggressive, caused excessive compressed vol ties)
            score_diff = bullish_breakdown.total_score - bearish_breakdown.total_score

            # Determine winner - use STRICT greater-than to avoid long bias on ties
            # Ties are broken by regime trend
            tie_break_used = None

            if score_diff >= DIRECTION_MARGIN:
                # Clear bullish edge
                chosen = bullish_breakdown
                chosen_direction = "LONG"
                logger.info(
                    "✅ %s Direction: LONG selected (score %.1f > %.1f by %.1f margin)",
                    context.symbol,
                    bullish_breakdown.total_score,
                    bearish_breakdown.total_score,
                    score_diff,
                )

            elif score_diff <= -DIRECTION_MARGIN:
                # Clear bearish edge
                chosen = bearish_breakdown
                chosen_direction = "SHORT"
                logger.info(
                    "✅ %s Direction: SHORT selected (score %.1f > %.1f by %.1f margin)",
                    context.symbol,
                    bearish_breakdown.total_score,
                    bullish_breakdown.total_score,
                    abs(score_diff),
                )

            else:
                # Gap is within margin — but check THRESHOLD-BASED tiebreaker first
                min_threshold = getattr(self._config, "min_confluence_score", 70.0)
                bullish_passes = bullish_breakdown.total_score >= min_threshold
                bearish_passes = bearish_breakdown.total_score >= min_threshold

                if bullish_passes and not bearish_passes:
                    chosen = bullish_breakdown
                    chosen_direction = "LONG"
                    tie_break_used = "threshold_pass"
                    logger.info(
                        "✅ %s Direction: LONG (threshold tiebreaker - %.1f >= %.1f threshold, %.1f < threshold)",
                        context.symbol,
                        bullish_breakdown.total_score,
                        min_threshold,
                        bearish_breakdown.total_score,
                    )
                elif bearish_passes and not bullish_passes:
                    chosen = bearish_breakdown
                    chosen_direction = "SHORT"
                    tie_break_used = "threshold_pass"
                    logger.info(
                        "✅ %s Direction: SHORT (threshold tiebreaker - %.1f >= %.1f threshold, %.1f < threshold)",
                        context.symbol,
                        bearish_breakdown.total_score,
                        min_threshold,
                        bullish_breakdown.total_score,
                    )
                else:
                    # Both pass or both fail — check volatility before using regime trend
                    symbol_regime = context.metadata.get("symbol_regime")
                    volatility = (
                        getattr(symbol_regime, "volatility", "normal") if symbol_regime else "normal"
                    )
                    regime_trend = (
                        getattr(symbol_regime, "trend", "neutral") if symbol_regime else "neutral"
                    )

                    # In compressed volatility, regime trend tie-breaker can be unreliable
                    # — the spring hasn't released yet.
                    #
                    # OLD behaviour: hard-block ALL compressed-vol ties.
                    # NEW behaviour: only hard-block when BOTH scores fail the minimum threshold
                    # (weak signals in a coiling market → genuinely skip).
                    # When one or both scores still PASS the threshold (e.g. 76% vs 72%),
                    # the stronger direction is still a valid trade; compressed vol means
                    # reduce size, not zero trades.
                    if volatility == "compressed":
                        # NEW behavior: Even if both fail threshold, we still proceed to pick a winner
                        # (usually via regime trend) so that it can be filtered normally by the gate
                        # in the orchestrator/service, rather than throwing an exception.
                        # This provides better diagnostic visibility (Below Gate vs Scoring Failed).
                        context.metadata["compressed_vol_tiebreak"] = True
                        if not bullish_passes and not bearish_passes:
                            logger.info(
                                "🚧 %s Compressed volatility tie (failure) — proceeding for diagnostic clarity (%.1f vs %.1f)",
                                context.symbol,
                                bullish_breakdown.total_score,
                                bearish_breakdown.total_score
                            )
                        else:
                            logger.info(
                                "⚠️ %s Compressed volatility tie (one/both pass) — proceeding (%.1f vs %.1f)",
                                context.symbol,
                                bullish_breakdown.total_score,
                                bearish_breakdown.total_score
                            )


                    if regime_trend == "bearish":
                        chosen = bearish_breakdown
                        chosen_direction = "SHORT"
                        tie_break_used = "regime_bearish"
                        logger.info(
                            "🔄 %s TIE (%.1f) broken by regime: SHORT (bearish regime)",
                            context.symbol,
                            bearish_breakdown.total_score,
                        )
                    elif regime_trend == "bullish":
                        chosen = bullish_breakdown
                        chosen_direction = "LONG"
                        tie_break_used = "regime_bullish"
                        logger.info(
                            "🔄 %s TIE (%.1f) broken by regime: LONG (bullish regime)",
                            context.symbol,
                            bullish_breakdown.total_score,
                        )
                    else:
                        # True neutral with tied scores - MODE-AWARE behavior
                        # Surgical/Precision: Can trade ranges (both directions valid)
                        # Others: Skip (need clear directional edge for swing/intraday)

                        current_profile = (
                            getattr(self._config, "profile", "balanced").lower()
                            if self._config
                            else "balanced"
                        )
                        is_scalp_mode = current_profile in ("precision", "surgical", "intraday_aggressive", "strike")
                        both_scores_high = (
                            bullish_breakdown.total_score >= 70 and bearish_breakdown.total_score >= 70
                        )

                        if is_scalp_mode and both_scores_high:
                            # RANGE_REVERSION: Both directions are valid for scalping
                            # Return the slightly higher one, but store both as valid
                            if bullish_breakdown.total_score >= bearish_breakdown.total_score:
                                chosen = bullish_breakdown
                                chosen_direction = "LONG"
                            else:
                                chosen = bearish_breakdown
                                chosen_direction = "SHORT"

                            tie_break_used = "range_reversion"
                            logger.info(
                                "🔄 %s RANGE_REVERSION: Both directions valid (LONG=%.1f, SHORT=%.1f) - %s mode",
                                context.symbol,
                                bullish_breakdown.total_score,
                                bearish_breakdown.total_score,
                                current_profile,
                            )

                            # Store range context for planner
                            context.metadata["range_reversion"] = {
                                "active": True,
                                "long_score": bullish_breakdown.total_score,
                                "short_score": bearish_breakdown.total_score,
                                "archetype": "RANGE_REVERSION",
                            }
                        else:
                            # Non-scalp mode in neutral regime
                            # NEW: Check if local structure provides directional edge

                            # Only attempt structure override if scores are strong (>70%)
                            if (
                                bullish_breakdown.total_score > 70
                                and bearish_breakdown.total_score > 70
                            ):
                                # Count recent structural breaks for each direction
                                bullish_structure = self._count_recent_structure(
                                    context, "LONG", lookback=20
                                )
                                bearish_structure = self._count_recent_structure(
                                    context, "SHORT", lookback=20
                                )

                                structure_diff = bullish_structure - bearish_structure

                                # Require 2+ structure advantage for override
                                if structure_diff >= 2:
                                    # Clear bullish structural bias overrides neutral regime
                                    chosen = bullish_breakdown
                                    chosen_direction = "LONG"
                                    tie_break_used = "structure_override"
                                    logger.info(
                                        "✅ %s STRUCTURE OVERRIDE: LONG (CHoCH/BOS: %d vs %d, conf=%.1f%%)",
                                        context.symbol,
                                        bullish_structure,
                                        bearish_structure,
                                        bullish_breakdown.total_score,
                                    )

                                elif structure_diff <= -2:
                                    # Clear bearish structural bias overrides neutral regime
                                    chosen = bearish_breakdown
                                    chosen_direction = "SHORT"
                                    tie_break_used = "structure_override"
                                    logger.info(
                                        "✅ %s STRUCTURE OVERRIDE: SHORT (CHoCH/BOS: %d vs %d, conf=%.1f%%)",
                                        context.symbol,
                                        bearish_structure,
                                        bullish_structure,
                                        bearish_breakdown.total_score,
                                    )

                                elif both_scores_high:
                                    # NEW: Elite Score Tiebreaker (>75%)
                                    # If both signals are incredibly strong, don't throw them away due to a tie.
                                    # Pick the winner based on raw score, however small the margin.
                                    if bullish_breakdown.total_score >= bearish_breakdown.total_score:
                                        chosen = bullish_breakdown
                                        chosen_direction = "LONG"
                                        tie_break_used = "elite_score_long"
                                        logger.info(
                                            "✅ %s ELITE TIEBREAKER: LONG selected (%.1f vs %.1f) - forcing trade due to high conviction",
                                            context.symbol,
                                            bullish_breakdown.total_score,
                                            bearish_breakdown.total_score,
                                        )
                                    else:
                                        chosen = bearish_breakdown
                                        chosen_direction = "SHORT"
                                        tie_break_used = "elite_score_short"
                                        logger.info(
                                            "✅ %s ELITE TIEBREAKER: SHORT selected (%.1f vs %.1f) - forcing trade due to high conviction",
                                            context.symbol,
                                            bearish_breakdown.total_score,
                                            bullish_breakdown.total_score,
                                        )

                                else:
                                    # Structure also tied and scores not elite - genuinely no edge
                                    logger.info(
                                        "🔄 %s TIE (%.1f) with neutral regime AND tied structure (%d vs %d): skipping",
                                        context.symbol,
                                        bullish_breakdown.total_score,
                                        bullish_structure,
                                        bearish_structure,
                                    )

                                    context.metadata["chosen_direction"] = None
                                    context.metadata["alt_confluence"] = {
                                        "long": bullish_breakdown.total_score,
                                        "short": bearish_breakdown.total_score,
                                        "tie_break_used": "skipped_no_edge",
                                        "bullish_structure": bullish_structure,
                                        "bearish_structure": bearish_structure,
                                        # FIX: Include factors for UI display (was missing!)
                                        "long_factors": [
                                            {"name": f.name, "score": f.score, "weight": f.weight, "rationale": f.rationale} 
                                            for f in bullish_breakdown.factors
                                        ],
                                        "short_factors": [
                                            {"name": f.name, "score": f.score, "weight": f.weight, "rationale": f.rationale} 
                                            for f in bearish_breakdown.factors
                                        ],
                                    }

                                    raise ConflictingDirectionsException(
                                        f"Conflicting signals ({bullish_breakdown.total_score:.1f}%) - bullish and bearish scores too close to call (<8pt margin) in neutral market",
                                        bullish_breakdown=bullish_breakdown,
                                        bearish_breakdown=bearish_breakdown
                                    )

                            else:
                                # Scores not strong enough for structure override (<=70%)
                                logger.info(
                                    "🔄 %s Conflicting Signals (%.1f%%) - neutral regime, no clear edge",
                                    context.symbol,
                                    bullish_breakdown.total_score,
                                )

                                context.metadata["chosen_direction"] = None
                                context.metadata["alt_confluence"] = {
                                    "long": bullish_breakdown.total_score,
                                    "short": bearish_breakdown.total_score,
                                    "tie_break_used": "skipped_no_edge",
                                    # Bypass Exception Transport Issues by storing factors directly in shared metadata
                                    "long_factors": [
                                        {"name": f.name, "score": f.score, "weight": f.weight, "rationale": f.rationale} 
                                        for f in bullish_breakdown.factors
                                    ],
                                    "short_factors": [
                                        {"name": f.name, "score": f.score, "weight": f.weight, "rationale": f.rationale} 
                                        for f in bearish_breakdown.factors
                                    ],
                                }

                                # --- DEBUG SOURCE ---
                                logger.error(f"DEBUG SOURCE: RAISING CONFLICT! Bull: {bullish_breakdown.total_score}, Bear: {bearish_breakdown.total_score}")
                                try:
                                    logger.error(f"DEBUG SOURCE FACTORS: Bull={len(bullish_breakdown.factors)} Bear={len(bearish_breakdown.factors)}")
                                except: pass
                                # --------------------

                                raise ConflictingDirectionsException(
                                    f"No directional edge ({bullish_breakdown.total_score:.1f}%) - bullish and bearish scores too close to call (<8pt margin) in neutral market",
                                    bullish_breakdown=bullish_breakdown,
                                    bearish_breakdown=bearish_breakdown
                                )

            # CRITICAL: Store chosen direction in context for downstream use
            context.metadata["chosen_direction"] = chosen_direction

            # === HTF ALIGNMENT BONUS ===
            # When global (daily) and local (symbol/4H) regimes both agree with the trade
            # direction, amplify the confluence score to reward high-conviction setups.
            global_regime = context.metadata.get("global_regime")
            symbol_regime = context.metadata.get("symbol_regime")
            if global_regime and symbol_regime:
                global_trend = getattr(global_regime, "trend", "sideways")
                symbol_trend = getattr(symbol_regime, "trend", "sideways")
                direction_lower = chosen_direction.lower()

                macro_aligned = (
                    (direction_lower in ("bullish", "long") and global_trend in ("up", "strong_up"))
                    or (direction_lower in ("bearish", "short") and global_trend in ("down", "strong_down"))
                )
                local_aligned = (
                    (direction_lower in ("bullish", "long") and symbol_trend in ("up", "strong_up"))
                    or (direction_lower in ("bearish", "short") and symbol_trend in ("down", "strong_down"))
                )

                if macro_aligned and local_aligned:
                    alignment_bonus = 5.0
                    chosen.total_score = min(100.0, chosen.total_score + alignment_bonus)
                    context.metadata["htf_alignment_bonus"] = alignment_bonus
                    logger.debug(
                        "%s: Full HTF alignment bonus +%.1f (global=%s, local=%s, dir=%s)",
                        context.symbol, alignment_bonus, global_trend, symbol_trend, chosen_direction,
                    )
                elif local_aligned and not macro_aligned:
                    local_bonus = 2.0
                    chosen.total_score = min(100.0, chosen.total_score + local_bonus)
                    context.metadata["htf_alignment_bonus"] = local_bonus
                    logger.debug(
                        "%s: Local HTF alignment bonus +%.1f (local=%s aligns, global=%s opposes)",
                        context.symbol, local_bonus, symbol_trend, global_trend,
                    )

            # === COUNTER-HTF EVALUATION ===
            # When the trade is NOT aligned with the effective HTF trend (from symbol_regime,
            # which is 4H-based for scalp modes), apply a score penalty instead of a hard block.
            # A hard block is only used as a last resort when there is zero supporting evidence.
            #
            # Penalty tiers (applied to chosen.total_score):
            #   confirmed   (full inst_seq)  → −5
            #   partial     (CHoCH + OB)     → −10
            #   soft        (sweep or diverg) → −15
            #   minimal     (ranging market) → −20
            #
            # The mode's min_confluence_score then acts as the natural gate.
            if not chosen.htf_aligned:
                smc = context.smc_snapshot
                direction_normalized = chosen_direction.upper()
                is_long = direction_normalized == "LONG"

                # Counter-trend setups must be confirmed on meaningful timeframes (not just 5m noise)
                allowed_tfs = getattr(self._config, "structure_timeframes", ("1d", "4h", "1h"))
                primary_tf = getattr(self._config, "primary_planning_timeframe", "1h")
                if primary_tf not in allowed_tfs:
                    allowed_tfs = tuple(list(allowed_tfs) + [primary_tf])

                target_sweep_type = "low" if is_long else "high"

                # Any sweep (confirmation_level >= 0) is a soft condition
                has_any_sweep = any(
                    getattr(s, "timeframe", "1h") in allowed_tfs
                    for s in smc.liquidity_sweeps
                    if s.sweep_type == target_sweep_type
                )
                # Confirmed sweep (confirmation_level >= 1) used for full inst_seq check
                has_confirmed_sweep = any(
                    getattr(s, "confirmation_level", 1 if s.confirmation else 0) >= 1
                    and getattr(s, "timeframe", "1h") in allowed_tfs
                    for s in smc.liquidity_sweeps
                    if s.sweep_type == target_sweep_type
                )

                target_break_dir = "bullish" if is_long else "bearish"
                confirming_shifts = [
                    b for b in smc.structural_breaks
                    if b.break_type in ("CHoCH", "BOS")
                    and getattr(b, "direction", "") == target_break_dir
                    and getattr(b, "timeframe", "1h") in allowed_tfs
                ]
                has_structure_shift = len(confirming_shifts) > 0

                ob_factor = next((f for f in chosen.factors if f.name == "Order Block"), None)
                has_ob = ob_factor is not None and ob_factor.score >= 50

                # Soft conditions from metadata (divergence, pullback patterns)
                has_divergence = bool(
                    context.metadata.get("divergence_direction") == chosen_direction.lower()
                )
                has_pullback = bool(context.metadata.get("pullback_entry"))

                soft_conditions_met = has_any_sweep or has_structure_shift or has_divergence or has_pullback

                inst_seq_confirmed = has_confirmed_sweep and has_structure_shift and has_ob

                # Check global regime volatility — ranging markets require less confirmation
                _global_regime = context.metadata.get("global_regime")
                global_volatility = (
                    getattr(_global_regime, "volatility", "normal") if _global_regime else "normal"
                )
                is_ranging = global_volatility in ("compressed", "coiling", "low", "sideways")

                if not soft_conditions_met and not is_ranging:
                    # Hard block: no evidence whatsoever + actively trending against us
                    logger.info(
                        "🚫 %s Counter-HTF BLOCKED — no supporting evidence "
                        "(sweep=%s, choch=%s, ob=%s, divergence=%s, pullback=%s, ranging=%s)",
                        context.symbol, has_any_sweep, has_structure_shift, has_ob,
                        has_divergence, has_pullback, is_ranging,
                    )
                    context.metadata["chosen_direction"] = None
                    raise ConflictingDirectionsException(
                        f"{context.symbol}: Counter-HTF blocked — "
                        f"no sweep, CHoCH, divergence, or pullback evidence "
                        f"(sweep={has_any_sweep}, choch={has_structure_shift}, ob={has_ob})",
                        bullish_breakdown=bullish_breakdown,
                        bearish_breakdown=bearish_breakdown,
                    )

                # Apply score penalty based on how well-confirmed the counter-HTF setup is
                if inst_seq_confirmed:
                    htf_penalty = -5.0
                    counter_htf_quality = "confirmed"
                elif has_structure_shift and has_ob:
                    htf_penalty = -10.0
                    counter_htf_quality = "partial"
                elif has_any_sweep or has_divergence or has_pullback:
                    htf_penalty = -15.0
                    counter_htf_quality = "soft"
                else:
                    htf_penalty = -20.0
                    counter_htf_quality = "minimal"

                chosen.total_score = max(0.0, chosen.total_score + htf_penalty)
                context.metadata["counter_htf_penalty"] = htf_penalty
                context.metadata["counter_htf_quality"] = counter_htf_quality

                # Determine trade type classification by confirmation timeframe
                highest_tf = "1h"
                tf_weights = {"1w": 6, "1d": 5, "4h": 4, "1h": 3, "15m": 2, "5m": 1}
                if confirming_shifts:
                    best_shift = max(
                        confirming_shifts,
                        key=lambda x: tf_weights.get(getattr(x, "timeframe", "1h"), 0),
                    )
                    highest_tf = getattr(best_shift, "timeframe", "1h")

                if highest_tf in ("1w", "1d", "4h"):
                    counter_htf_type = "swing"
                elif highest_tf in ("1h", "15m"):
                    counter_htf_type = "intraday"
                else:
                    counter_htf_type = "scalp"

                context.metadata["counter_htf_scalp"] = True
                context.metadata["counter_htf_type"] = counter_htf_type
                context.metadata["counter_htf_tf"] = highest_tf

                logger.info(
                    "🔀 %s Counter-HTF allowed — quality=%s, penalty=%.1f, type=%s "
                    "(sweep=%s, choch=%s, ob=%s, divergence=%s, pullback=%s, ranging=%s)",
                    context.symbol, counter_htf_quality, htf_penalty, counter_htf_type,
                    has_any_sweep, has_structure_shift, has_ob,
                    has_divergence, has_pullback, is_ranging,
                )

            # Store alt scores for analytics/debugging
            context.metadata["alt_confluence"] = {
                "long": bullish_breakdown.total_score,
                "short": bearish_breakdown.total_score,
                "tie_break_used": tie_break_used,
            }

            # Store reversal context for chosen direction
            chosen_reversal = (
                reversal_context_long if chosen_direction == "LONG" else reversal_context_short
            )
            if chosen_reversal and getattr(chosen_reversal, "is_reversal_setup", False):
                context.metadata["reversal"] = {
                    "is_reversal_setup": chosen_reversal.is_reversal_setup,
                    "direction": getattr(chosen_reversal, "direction", chosen_direction),
                    "cycle_aligned": getattr(chosen_reversal, "cycle_aligned", False),
                    "htf_bypass_active": getattr(chosen_reversal, "htf_bypass_active", False),
                    "confidence": getattr(chosen_reversal, "confidence", 0.0),
                    "rationale": getattr(chosen_reversal, "rationale", ""),
                }

            return chosen

        except Exception as e:
            logger.error("Confluence scoring failed for %s: %s", context.symbol, e)
            self._diagnostics["confluence_rejections"].append(
                {"symbol": context.symbol, "error": str(e)}
            )
            raise

    def _score_direction(
        self,
        context: SniperContext,
        direction: str,
        is_bullish: bool,
        htf_context: Optional[Dict],
        cycle_context: Optional[Any],
        reversal_context: Optional[Any],
        current_price: float,
    ) -> ConfluenceBreakdown:
        """Score a single direction using the existing scorer."""
        return calculate_confluence_score(
            smc_snapshot=context.smc_snapshot,
            indicators=context.multi_tf_indicators,
            config=self._config,
            direction=direction,
            htf_context=htf_context,
            cycle_context=cycle_context,
            reversal_context=reversal_context,
            volume_profile=context.metadata.get("_volume_profile_obj"),
            current_price=current_price,
            macro_context=context.macro_context,
            is_btc=("BTC" in context.symbol.upper()),
            is_alt=("BTC" not in context.symbol.upper()),
            # Pass symbol-specific regime detected by RegimeDetector
            regime=context.metadata.get("symbol_regime"),
            symbol=context.symbol,
        )


# Singleton
_confluence_service: Optional[ConfluenceService] = None


def get_confluence_service() -> Optional[ConfluenceService]:
    """Get the singleton ConfluenceService instance."""
    return _confluence_service


def configure_confluence_service(scanner_mode=None, config=None) -> ConfluenceService:
    """Configure and return the singleton ConfluenceService."""
    global _confluence_service
    _confluence_service = ConfluenceService(scanner_mode=scanner_mode, config=config)
    return _confluence_service
