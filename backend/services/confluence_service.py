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
            DIRECTION_MARGIN = 5.0  # Minimum score edge required
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

                    # Bug Fix: In compressed volatility, regime trend tie-breaker is
                    # unreliable — the spring hasn't released yet. Skip instead of
                    # forcing directional bias into a coil market.
                    if volatility == "compressed":
                        # Both fail threshold -> unreliable, skip
                        if not bullish_passes and not bearish_passes:
                            logger.info(
                                "🚧 %s Compressed volatility tie — skipping (scores %.1f vs %.1f failed threshold in coil market)",
                                context.symbol,
                                bullish_breakdown.total_score,
                                bearish_breakdown.total_score
                            )
                            context.metadata["chosen_direction"] = None
                            context.metadata["alt_confluence"] = {
                                "long": bullish_breakdown.total_score,
                                "short": bearish_breakdown.total_score,
                                "tie_break_used": "skipped_compressed_volatility",
                            }
                            raise ConflictingDirectionsException(
                                f"Compressed volatility tie ({bullish_breakdown.total_score:.1f}%): "
                                "no directional edge in coiling market",
                                bullish_breakdown=bullish_breakdown,
                                bearish_breakdown=bearish_breakdown,
                            )
                        
                        # Both pass threshold -> still use regime/structural tiebreaker below
                        # (compressed vol noted in metadata for position sizing reduction)
                        context.metadata["compressed_vol_tiebreak"] = True
                        logger.info(
                            "⚠️ %s Compressed volatility tie but both scores pass threshold (%.1f vs %.1f) "
                            "— proceeding with regime tiebreaker at reduced conviction",
                            context.symbol,
                            bullish_breakdown.total_score,
                            bearish_breakdown.total_score,
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

            # === COUNTER-HTF GATE (Bug Fix) ===
            # If the winning direction is NOT aligned with the HTF trend, require a
            # confirmed Institutional Sequence (Sweep → CHoCH → OB) before allowing
            # the trade through. Without confirmation, the setup has too high a failure
            # probability to trade as a full swing.
            #
            # With confirmation: tag as counter_htf_scalp so the planner downgrades
            # the trade to a single-target scalp to the nearest HTF S/R level.
            if not chosen.htf_aligned:
                smc = context.smc_snapshot
                direction_normalized = chosen_direction.upper()
                is_long = direction_normalized == "LONG"

                # Counter-trend setups must be confirmed on meaningful timeframes (not just 5m noise)
                allowed_tfs = getattr(self._config, "structure_timeframes", ("1d", "4h", "1h"))
                primary_tf = getattr(self._config, "primary_planning_timeframe", "1h")
                if primary_tf not in allowed_tfs:
                    allowed_tfs = tuple(list(allowed_tfs) + [primary_tf])

                # Check sweep of correct liquidity (lows for LONG, highs for SHORT)
                target_sweep_type = "low" if is_long else "high"
                has_confirmed_sweep = any(
                    getattr(s, "confirmation_level", 1 if s.confirmation else 0) >= 1
                    and getattr(s, "timeframe", "1h") in allowed_tfs
                    for s in smc.liquidity_sweeps
                    if s.sweep_type == target_sweep_type
                )

                # Check structural break in trade direction post-sweep
                target_break_dir = "bullish" if is_long else "bearish"
                
                # Keep track of the confirming shifts to determine timeframe
                confirming_shifts = [
                    b for b in smc.structural_breaks
                    if b.break_type in ("CHoCH", "BOS")
                    and getattr(b, "direction", "") == target_break_dir
                    and getattr(b, "timeframe", "1h") in allowed_tfs
                ]
                has_structure_shift = len(confirming_shifts) > 0

                # Check order block with meaningful score
                ob_factor = next((f for f in chosen.factors if f.name == "Order Block"), None)
                has_ob = ob_factor is not None and ob_factor.score >= 50

                inst_seq_confirmed = has_confirmed_sweep and has_structure_shift and has_ob

                if not inst_seq_confirmed:
                    logger.info(
                        "🚫 %s Counter-HTF REJECTED — no Institutional Sequence "
                        "(Sweep=%s, CHoCH/BOS=%s, OB=%s). "
                        "Trade is against HTF trend without reversal confirmation.",
                        context.symbol, has_confirmed_sweep, has_structure_shift, has_ob,
                    )
                    context.metadata["chosen_direction"] = None
                    raise ConflictingDirectionsException(
                        f"{context.symbol}: Counter-HTF trade blocked — "
                        f"no confirmed Sweep→CHoCH/BOS→OB sequence "
                        f"(Sweep={has_confirmed_sweep}, Shift={has_structure_shift}, OB={has_ob})",
                        bullish_breakdown=bullish_breakdown,
                        bearish_breakdown=bearish_breakdown,
                    )
                else:
                    # Institutional sequence confirmed but still counter-HTF.
                    # Determine the strength of the reversal based on the timeframe of the shift.
                    highest_tf = "1h" # Default
                    tf_weights = {"1w": 6, "1d": 5, "4h": 4, "1h": 3, "15m": 2, "5m": 1}
                    
                    if confirming_shifts:
                        # Find the shift with the highest timeframe weight
                        best_shift = max(confirming_shifts, key=lambda x: tf_weights.get(getattr(x, "timeframe", "1h"), 0))
                        highest_tf = getattr(best_shift, "timeframe", "1h")
                    
                    if highest_tf in ("1w", "1d", "4h"):
                        counter_htf_type = "swing"
                        logger.info(
                            "🔀 %s Counter-HTF macro reversal approved — (%s %s). Classifying as SWING.",
                            context.symbol, highest_tf, target_break_dir.upper()
                        )
                    elif highest_tf in ("1h", "15m"):
                        counter_htf_type = "intraday"
                        logger.info(
                            "🔀 %s Counter-HTF intraday reversal approved — (%s %s). Classifying as INTRADAY.",
                            context.symbol, highest_tf, target_break_dir.upper()
                        )
                    else:
                        counter_htf_type = "scalp"
                        logger.info(
                            "🔀 %s Counter-HTF scalp approved — (%s %s). Classifying as SCALP.",
                            context.symbol, highest_tf, target_break_dir.upper()
                        )

                    context.metadata["counter_htf_scalp"] = True # Keep for backwards compat if needed elsewhere
                    context.metadata["counter_htf_type"] = counter_htf_type
                    context.metadata["counter_htf_tf"] = highest_tf

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
