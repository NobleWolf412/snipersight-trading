"""
Confluence Service - Confluence scoring wrapper extracted from orchestrator.py

Wraps the existing calculate_confluence_score function from scorer.py
and provides a clean service interface for confluence calculations.

This is a lightweight wrapper approach to minimize risk while still
providing the benefits of service-based architecture.
"""

import logging
from typing import Dict, Any, Optional

from backend.analysis.macro_context import MacroContext
from backend.shared.config.sensitivity import passes_confluence_gate
from backend.shared.config.score_policy import (
    DIRECTION_MARGIN, SCORE_MODEL_VERSION, STANDARD_SCORE, STRONG_SCORE,
)


def _btc_dir_to_impulse(macro_context: Optional[MacroContext]) -> Optional[str]:
    """Translate MacroContext.btc_dir vocab to the btc_impulse vocab expected by scorer."""
    if macro_context is None:
        return None
    return {"up": "bullish", "down": "bearish", "flat": "neutral"}.get(
        getattr(macro_context, "btc_dir", "flat"), "neutral"
    )

from backend.engine.context import SniperContext
from backend.strategy.confluence.scorer import (
    calculate_confluence_score, ConfluenceBreakdown, refresh_score_classification,
    _institutional_sequence_evidence,
)

logger = logging.getLogger(__name__)


class ConflictingDirectionsException(Exception):
    """Raised when bullish and bearish scores are too close to call."""

    def __init__(self, message: str, bullish_breakdown: ConfluenceBreakdown, bearish_breakdown: ConfluenceBreakdown,
                 *, selected_direction: Optional[str] = None, gate_name: str = "confluence_tie_break"):
        super().__init__(message)
        self.bullish_breakdown = bullish_breakdown
        self.bearish_breakdown = bearish_breakdown
        self.selected_direction = selected_direction
        self.gate_name = gate_name


def resolve_directional_tie(
    bullish_breakdown: ConfluenceBreakdown,
    bearish_breakdown: ConfluenceBreakdown,
    context_symbol: str,
    branch_label: str,
):
    """Pick higher-scoring breakdown via strict-greater. Raise on exact tie.

    Returns (chosen_breakdown, chosen_direction) where direction is "LONG" / "SHORT".
    Raises ConflictingDirectionsException on exact equality so neither side
    asymmetrically wins.

    §10 standing-fix (C2 symmetry pass, May 2026): symmetry-guard SYM-01
    confirmed three downstream sites in score() — RANGE_REVERSION (line ~340),
    ELITE_TIEBREAKER (line ~420), score_winner_below_gate (line ~460) — were
    using `bullish_score >= bearish_score → LONG` which compounded the
    orchestrator pre-direction LONG bias. This helper centralises the
    strict-greater + raise-on-exact-tie pattern so the three sites share one
    auditable implementation.

    Args:
        bullish_breakdown: scored LONG breakdown
        bearish_breakdown: scored SHORT breakdown
        context_symbol: symbol string for the exception message
        branch_label: human label for which call-site fired the exception
            (e.g. "RANGE_REVERSION", "ELITE_TIEBREAKER", "score_winner_below_gate")
    """
    if bullish_breakdown.total_score > bearish_breakdown.total_score:
        return bullish_breakdown, "LONG"
    if bearish_breakdown.total_score > bullish_breakdown.total_score:
        return bearish_breakdown, "SHORT"
    raise ConflictingDirectionsException(
        f"{context_symbol}: {branch_label} exact-tie "
        f"({bullish_breakdown.total_score:.2f} == {bearish_breakdown.total_score:.2f}); "
        f"cannot symmetrically pick direction",
        bullish_breakdown=bullish_breakdown,
        bearish_breakdown=bearish_breakdown,
    )



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
        selected_direction: Optional[str] = None,
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
            selected_direction: Optional LONG/SHORT thesis; bypasses only legacy selection

        Returns:
            ConfluenceBreakdown for the selected thesis direction, or legacy score winner

        Side Effects:
            Sets context.metadata['chosen_direction'] to 'LONG' or 'SHORT'
            Sets context.metadata['alt_confluence'] with both direction scores
        """
        self._diagnostics = {"confluence_rejections": []}
        if selected_direction is not None and selected_direction not in ("LONG", "SHORT"):
            raise ValueError("selected_direction must be LONG or SHORT")

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
            score_diff = bullish_breakdown.total_score - bearish_breakdown.total_score

            # Determine winner - use STRICT greater-than to avoid long bias on ties
            # Ties are broken by regime trend
            tie_break_used = None

            # When pre-scoring gates found heavy structural opposition (3+ OBs) and
            # flipped direction, honour that structural evidence for close calls.
            _cd_flip = context.metadata.get("conflict_density_flip")
            bullish_eligible = bullish_breakdown.metadata.get("evidence_eligible") is not False
            bearish_eligible = bearish_breakdown.metadata.get("evidence_eligible") is not False
            if selected_direction is not None:
                chosen_direction = selected_direction
                chosen = bullish_breakdown if selected_direction == "LONG" else bearish_breakdown
                tie_break_used = "thesis_direction"
            elif bullish_eligible != bearish_eligible:
                chosen_direction = "LONG" if bullish_eligible else "SHORT"
                chosen = bullish_breakdown if bullish_eligible else bearish_breakdown
                tie_break_used = "evidence_eligibility"
            elif _cd_flip and abs(score_diff) < DIRECTION_MARGIN:
                _flip_to = _cd_flip["to"]
                if _flip_to == "SHORT":
                    chosen = bearish_breakdown
                    chosen_direction = "SHORT"
                else:
                    chosen = bullish_breakdown
                    chosen_direction = "LONG"
                tie_break_used = "conflict_density_structural"
                logger.info(
                    "✅ %s Direction: %s (conflict-density flip — %d opposing OBs forced structural tiebreak, %.1f vs %.1f)",
                    context.symbol, chosen_direction, _cd_flip["conflict_count"],
                    bullish_breakdown.total_score, bearish_breakdown.total_score,
                )

            elif score_diff >= DIRECTION_MARGIN:
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
                min_threshold = getattr(self._config, "min_confluence_score", STANDARD_SCORE)
                bullish_passes = passes_confluence_gate(bullish_breakdown.total_score, min_threshold)
                bearish_passes = passes_confluence_gate(bearish_breakdown.total_score, min_threshold)

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


                    # SymbolRegime.trend uses "strong_up"/"up"/"sideways"/"down"/"strong_down"
                    # — NOT "bearish"/"bullish". Fixed to match actual SymbolRegime vocab.
                    if regime_trend in ("down", "strong_down"):
                        chosen = bearish_breakdown
                        chosen_direction = "SHORT"
                        tie_break_used = "regime_bearish"
                        logger.info(
                            "🔄 %s TIE (%.1f) broken by regime: SHORT (%s regime)",
                            context.symbol,
                            bearish_breakdown.total_score,
                            regime_trend,
                        )
                    elif regime_trend in ("up", "strong_up"):
                        chosen = bullish_breakdown
                        chosen_direction = "LONG"
                        tie_break_used = "regime_bullish"
                        logger.info(
                            "🔄 %s TIE (%.1f) broken by regime: LONG (%s regime)",
                            context.symbol,
                            bullish_breakdown.total_score,
                            regime_trend,
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
                            passes_confluence_gate(bullish_breakdown.total_score, STRONG_SCORE)
                            and passes_confluence_gate(bearish_breakdown.total_score, STRONG_SCORE)
                        )

                        if is_scalp_mode and both_scores_high:
                            # RANGE_REVERSION: Both directions are valid for scalping.
                            # §10 standing-fix — strict-greater + raise on exact tie via
                            # the shared `resolve_directional_tie` helper.
                            chosen, chosen_direction = resolve_directional_tie(
                                bullish_breakdown, bearish_breakdown,
                                context.symbol, "RANGE_REVERSION",
                            )
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

                            # Structure override requires both sides to meet the strong evidence band.
                            if (
                                passes_confluence_gate(bullish_breakdown.total_score, STRONG_SCORE)
                                and passes_confluence_gate(bearish_breakdown.total_score, STRONG_SCORE)
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
                                    # If both signals are incredibly strong, don't throw them away
                                    # due to a near-tie. Pick the winner based on raw score, however
                                    # small the margin.
                                    # §10 standing-fix — strict-greater + raise on exact tie via
                                    # the shared `resolve_directional_tie` helper.
                                    chosen, chosen_direction = resolve_directional_tie(
                                        bullish_breakdown, bearish_breakdown,
                                        context.symbol, "ELITE_TIEBREAKER",
                                    )
                                    tie_break_used = (
                                        "elite_score_long" if chosen_direction == "LONG"
                                        else "elite_score_short"
                                    )
                                    logger.info(
                                        "✅ %s ELITE TIEBREAKER: %s selected (%.1f vs %.1f) - forcing trade due to high conviction",
                                        context.symbol,
                                        chosen_direction,
                                        bullish_breakdown.total_score if chosen_direction == "LONG" else bearish_breakdown.total_score,
                                        bearish_breakdown.total_score if chosen_direction == "LONG" else bullish_breakdown.total_score,
                                    )

                                # NOTE: This else branch is unreachable. We are inside the
                                # both-sides-STRONG_SCORE block, so both_scores_high
                                # is always True here. The elif above always
                                # matches. Dead code removed — ConflictingDirectionsException for
                                # the neutral-regime tied-structure case is raised in the outer
                                # `else` block below (non-scalp, scores below the strong band).

                            else:
                                # Scores not strong enough for structure override (<=70%).
                                # Pick the higher-scoring direction and let the 70% CONF gate
                                # produce a clear rejection.
                                # §10 standing-fix — strict-greater + raise on exact tie via
                                # the shared `resolve_directional_tie` helper. Even though the
                                # conf gate will reject either direction here, the rejection-
                                # payload `direction` field was inflating the LONG telemetry
                                # counter on ties.
                                chosen, chosen_direction = resolve_directional_tie(
                                    bullish_breakdown, bearish_breakdown,
                                    context.symbol, "score_winner_below_gate",
                                )
                                tie_break_used = "score_winner_below_gate"
                                logger.info(
                                    "🔄 %s Both directions below gate (%.1f vs %.1f) — picking %s by score, "
                                    "CONF gate will reject",
                                    context.symbol,
                                    bullish_breakdown.total_score,
                                    bearish_breakdown.total_score,
                                    chosen_direction,
                                )

            # CRITICAL: Store chosen direction in context for downstream use
            context.metadata["chosen_direction"] = chosen_direction

            # The raw diagnostic scores are retained separately from the adjusted winner.
            context.metadata["raw_directional_scores"] = {
                "long": bullish_breakdown.total_score, "short": bearish_breakdown.total_score,
            }
            for key in ("htf_alignment_bonus", "counter_htf_penalty", "counter_htf_scalp",
                        "counter_htf_type", "counter_htf_tf", "reversal"):
                context.metadata.pop(key, None)

            if chosen.metadata.get("evidence_eligible") is False:
                missing = chosen.metadata.get("evidence_missing") or ["required evidence is missing"]
                raise ConflictingDirectionsException(
                    f"{context.symbol}: Evidence requirements failed — {', '.join(map(str, missing))}",
                    bullish_breakdown=bullish_breakdown,
                    bearish_breakdown=bearish_breakdown,
                    selected_direction=chosen_direction,
                    gate_name="evidence_requirements",
                )

            def adjust_score(name: str, delta: float) -> None:
                before = chosen.total_score
                chosen.total_score = max(0.0, min(100.0, before + delta))
                trace = chosen.metadata.setdefault("score_components", {
                    "initial_score": before, "adjustments": [],
                })
                trace["adjustments"].append({"name": name, "delta": chosen.total_score - before,
                                             "requested_delta": delta})
                trace["final_score"] = chosen.total_score

            # Regime Alignment already scores local directional alignment. Do
            # not add another +2/+5 for the same observation after selecting a
            # winner. Keep counter-HTF eligibility/risk policy below explicit.

            # === COUNTER-HTF EVALUATION ===
            # The family model distinguishes opposition from neutral/missing HTF evidence.
            # Only actual opposition invokes counter-HTF eligibility and penalties.
            # Legacy breakdowns retain their prior htf_aligned interpretation.
            # A hard block is only used as a last resort when there is zero supporting evidence.
            #
            # Penalty tiers (applied to chosen.total_score):
            #   confirmed   (full inst_seq)  → −5
            #   partial     (shift + OB/FVG) → −10
            #   soft        (sweep or diverg) → −15
            #   minimal     (ranging market) → −20
            #
            # The mode's min_confluence_score then acts as the natural gate.
            is_family_score = chosen.metadata.get("score_model_version") == SCORE_MODEL_VERSION
            counter_htf = (
                chosen.metadata.get("htf_direction_status") == "opposed"
                if is_family_score else not chosen.htf_aligned
            )
            if counter_htf:
                smc = context.smc_snapshot
                direction_normalized = chosen_direction.upper()
                is_long = direction_normalized == "LONG"

                # Counter-trend setups must be confirmed on meaningful timeframes (not just 5m noise)
                allowed_tfs = getattr(self._config, "structure_timeframes", ("1d", "4h", "1h"))
                primary_tf = getattr(self._config, "primary_planning_timeframe", "1h")
                if primary_tf not in allowed_tfs:
                    allowed_tfs = tuple(list(allowed_tfs) + [primary_tf])
                # Also include the exec TF from the mode's relativity so that reversal signals
                # on the execution timeframe (e.g. 15m CHoCH in Strike mode) aren't excluded.
                try:
                    from backend.shared.config.scanner_modes import RELATIVITY_MAP, map_profile_to_relativity
                    _mode_key = map_profile_to_relativity(getattr(self._config, "profile", "stealth"))
                    _rel = RELATIVITY_MAP.get(_mode_key, RELATIVITY_MAP["intraday"])
                    exec_tf = _rel["exec"]
                    if exec_tf not in allowed_tfs:
                        allowed_tfs = tuple(list(allowed_tfs) + [exec_tf])
                except Exception:
                    pass

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
                fvg_factor = next((f for f in chosen.factors if f.name == "Fair Value Gap"), None)
                has_fvg = fvg_factor is not None and fvg_factor.score >= 50
                has_entry_anchor = has_ob or has_fvg

                # Soft conditions — divergence read directly from chosen breakdown factors.
                # context.metadata["divergence_direction"] was never populated upstream,
                # so we check the "Price-Indicator Divergence" factor score instead.
                # Deduplicated divergence is normalized to 0-100 per event.
                # 60 remains a quality cutoff, not a count of RSI/MACD votes.
                div_factor = next(
                    (f for f in chosen.factors if f.name == "Price-Indicator Divergence"), None
                )
                has_divergence = div_factor is not None and div_factor.score >= 60

                # pullback_entry: check Close Momentum and Multi-Candle Confirmation factors
                # as a proxy for pullback quality (metadata key never populated upstream).
                close_mom = next((f for f in chosen.factors if f.name == "Close Momentum"), None)
                multi_candle = next(
                    (f for f in chosen.factors if f.name == "Multi-Candle Confirmation"), None
                )
                has_pullback = (
                    (close_mom is not None and close_mom.score >= 50)
                    or (multi_candle is not None and multi_candle.score >= 50)
                )

                soft_conditions_met = has_any_sweep or has_structure_shift or has_divergence or has_pullback

                sequence = _institutional_sequence_evidence(smc, chosen_direction, allowed_timeframes=allowed_tfs)
                inst_seq_confirmed = (has_confirmed_sweep and has_structure_shift and has_entry_anchor
                                      and sequence["ordered"] and sequence["sweep_confirmation"] >= 1)

                # Check global regime volatility — ranging markets require less confirmation.
                # MarketRegime stores volatility at .dimensions.volatility, not as a top-level
                # attribute. getattr(_global_regime, "volatility") always returns "normal"
                # (the fallback), so is_ranging was permanently False. Fixed to read from
                # .dimensions first, then fall back to a direct .volatility attr (SymbolRegime).
                _global_regime = context.metadata.get("global_regime")
                if _global_regime:
                    _dims = getattr(_global_regime, "dimensions", None)
                    global_volatility = (
                        getattr(_dims, "volatility", None)
                        or getattr(_global_regime, "volatility", "normal")
                    )
                else:
                    global_volatility = "normal"
                is_ranging = global_volatility in ("compressed", "coiling", "low", "sideways")

                if not soft_conditions_met and not is_ranging:
                    # Hard block: no evidence whatsoever + actively trending against us
                    logger.info(
                        "🚫 %s Counter-HTF BLOCKED — no supporting evidence "
                        "(sweep=%s, choch=%s, anchor=%s, divergence=%s, pullback=%s, ranging=%s)",
                        context.symbol, has_any_sweep, has_structure_shift, has_entry_anchor,
                        has_divergence, has_pullback, is_ranging,
                    )
                    raise ConflictingDirectionsException(
                        f"{context.symbol}: Counter-HTF blocked — "
                        f"no sweep, CHoCH, divergence, or pullback evidence "
                        f"(sweep={has_any_sweep}, choch={has_structure_shift}, ob={has_ob}, fvg={has_fvg})",
                        bullish_breakdown=bullish_breakdown,
                        bearish_breakdown=bearish_breakdown,
                        selected_direction=chosen_direction, gate_name="counter_htf",
                    )

                # Apply score penalty based on how well-confirmed the counter-HTF setup is
                if inst_seq_confirmed:
                    htf_penalty = -5.0
                    counter_htf_quality = "confirmed"
                elif has_structure_shift and has_entry_anchor:
                    htf_penalty = -10.0
                    counter_htf_quality = "partial"
                elif has_any_sweep or has_divergence or has_pullback:
                    htf_penalty = -15.0
                    counter_htf_quality = "soft"
                else:
                    htf_penalty = -20.0
                    counter_htf_quality = "minimal"

                adjust_score("counter_htf", htf_penalty)
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

            refresh_score_classification(chosen, self._config)
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
        # Map symbol/global regime direction into the scorer's context vocabulary.
        # The scorer retains neutral/unknown separately from explicitly opposed.
        htf_trend_str: Optional[str] = None
        symbol_regime = context.metadata.get("symbol_regime")
        if not symbol_regime:
            symbol_regime = context.metadata.get("global_regime")
        if symbol_regime:
            # SymbolRegime exposes .trend directly; MarketRegime exposes .dimensions.trend
            raw_trend = getattr(symbol_regime, "trend", None)
            if raw_trend is None:
                dims = getattr(symbol_regime, "dimensions", None)
                raw_trend = getattr(dims, "trend", "neutral") if dims else "neutral"
            htf_trend_str = {
                "strong_up": "bullish", "up": "bullish",
                "strong_down": "bearish", "down": "bearish",
            }.get(raw_trend)  # None for sideways/neutral → factor not added

        return calculate_confluence_score(
            smc_snapshot=context.smc_snapshot,
            indicators=context.multi_tf_indicators,
            config=self._config,
            direction=direction,
            htf_trend=htf_trend_str,
            htf_context=htf_context,
            cycle_context=cycle_context,
            reversal_context=reversal_context,
            volume_profile=context.metadata.get("_volume_profile_obj"),
            current_price=current_price,
            macro_context=context.macro_context,
            btc_impulse=_btc_dir_to_impulse(context.macro_context) if "BTC" not in context.symbol.upper() else None,
            is_btc=("BTC" in context.symbol.upper()),
            is_alt=("BTC" not in context.symbol.upper()),
            # Pass symbol-specific regime detected by RegimeDetector
            regime=context.metadata.get("symbol_regime"),
            symbol=context.symbol,
            as_of=context.timestamp if context.metadata.get("replay_session_id") else None,
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
