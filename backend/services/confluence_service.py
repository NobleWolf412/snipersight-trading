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
        self._diagnostics: Dict[str, list] = {'confluence_rejections': []}
    
    @property
    def diagnostics(self) -> Dict[str, list]:
        """Get diagnostic information from last scoring."""
        return self._diagnostics
    
    def set_mode(self, scanner_mode):
        """Update scanner mode dynamically."""
        self._scanner_mode = scanner_mode
    
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
        self._diagnostics = {'confluence_rejections': []}
        
        if not context.smc_snapshot or not context.multi_tf_indicators:
            raise ValueError(f"{context.symbol}: Missing SMC snapshot or indicators for confluence scoring")
        
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
            logger.info("⚖️  %s Direction eval: LONG=%.1f vs SHORT=%.1f",
                       context.symbol,
                       bullish_breakdown.total_score,
                       bearish_breakdown.total_score)
            
            # Determine winner - use STRICT greater-than to avoid long bias on ties
            # Ties are broken by regime trend
            tie_break_used = None
            
            if bullish_breakdown.total_score > bearish_breakdown.total_score:
                chosen = bullish_breakdown
                chosen_direction = 'LONG'
                logger.info("✅ %s Direction: LONG selected (score %.1f > %.1f)",
                           context.symbol, bullish_breakdown.total_score, bearish_breakdown.total_score)
                           
            elif bearish_breakdown.total_score > bullish_breakdown.total_score:
                chosen = bearish_breakdown
                chosen_direction = 'SHORT'
                logger.info("✅ %s Direction: SHORT selected (score %.1f > %.1f)",
                           context.symbol, bearish_breakdown.total_score, bullish_breakdown.total_score)
                           
            else:
                # Exact tie - use regime trend as tie-breaker
                symbol_regime = context.metadata.get('symbol_regime')
                regime_trend = getattr(symbol_regime, 'trend', 'neutral') if symbol_regime else 'neutral'
                
                if regime_trend == 'bearish':
                    chosen = bearish_breakdown
                    chosen_direction = 'SHORT'
                    tie_break_used = 'regime_bearish'
                    logger.info("🔄 %s TIE (%.1f) broken by regime: SHORT (bearish regime)",
                               context.symbol, bearish_breakdown.total_score)
                elif regime_trend == 'bullish':
                    chosen = bullish_breakdown
                    chosen_direction = 'LONG'
                    tie_break_used = 'regime_bullish'
                    logger.info("🔄 %s TIE (%.1f) broken by regime: LONG (bullish regime)",
                               context.symbol, bullish_breakdown.total_score)
                else:
                    # True neutral with tied scores - MODE-AWARE behavior
                    # Surgical/Precision: Can trade ranges (both directions valid)
                    # Others: Skip (need clear directional edge for swing/intraday)
                    
                    current_profile = getattr(self._config, 'profile', 'balanced').lower() if self._config else 'balanced'
                    is_scalp_mode = current_profile in ('precision', 'surgical')
                    both_scores_high = bullish_breakdown.total_score >= 70 and bearish_breakdown.total_score >= 70
                    
                    if is_scalp_mode and both_scores_high:
                        # RANGE_REVERSION: Both directions are valid for scalping
                        # Return the slightly higher one, but store both as valid
                        if bullish_breakdown.total_score >= bearish_breakdown.total_score:
                            chosen = bullish_breakdown
                            chosen_direction = 'LONG'
                        else:
                            chosen = bearish_breakdown
                            chosen_direction = 'SHORT'
                        
                        tie_break_used = 'range_reversion'
                        logger.info("🔄 %s RANGE_REVERSION: Both directions valid (LONG=%.1f, SHORT=%.1f) - %s mode",
                                   context.symbol, bullish_breakdown.total_score, bearish_breakdown.total_score, current_profile)
                        
                        # Store range context for planner
                        context.metadata['range_reversion'] = {
                            'active': True,
                            'long_score': bullish_breakdown.total_score,
                            'short_score': bearish_breakdown.total_score,
                            'archetype': 'RANGE_REVERSION'
                        }
                    else:
                        # Non-scalp mode or low scores: Skip (no directional edge)
                        logger.info("🔄 %s TIE (%.1f) with neutral regime: skipping (no directional edge)",
                                   context.symbol, bullish_breakdown.total_score)
                        
                        context.metadata['chosen_direction'] = None
                        context.metadata['alt_confluence'] = {
                            'long': bullish_breakdown.total_score,
                            'short': bearish_breakdown.total_score,
                            'tie_break_used': 'skipped_no_edge'
                        }
                        
                        raise ValueError(f"Confluence tie ({bullish_breakdown.total_score:.1f}) with neutral regime - no directional edge")
            
            # CRITICAL: Store chosen direction in context for downstream use
            context.metadata['chosen_direction'] = chosen_direction
            
            # Store alt scores for analytics/debugging
            context.metadata['alt_confluence'] = {
                'long': bullish_breakdown.total_score,
                'short': bearish_breakdown.total_score,
                'tie_break_used': tie_break_used
            }
            
            # Store reversal context for chosen direction
            chosen_reversal = reversal_context_long if chosen_direction == 'LONG' else reversal_context_short
            if chosen_reversal and getattr(chosen_reversal, 'is_reversal_setup', False):
                context.metadata['reversal'] = {
                    'is_reversal_setup': chosen_reversal.is_reversal_setup,
                    'direction': getattr(chosen_reversal, 'direction', chosen_direction),
                    'cycle_aligned': getattr(chosen_reversal, 'cycle_aligned', False),
                    'htf_bypass_active': getattr(chosen_reversal, 'htf_bypass_active', False),
                    'confidence': getattr(chosen_reversal, 'confidence', 0.0),
                    'rationale': getattr(chosen_reversal, 'rationale', '')
                }
            
            return chosen
            
        except Exception as e:
            logger.error("Confluence scoring failed for %s: %s", context.symbol, e)
            self._diagnostics['confluence_rejections'].append({
                'symbol': context.symbol,
                'error': str(e)
            })
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
            volume_profile=context.metadata.get('_volume_profile_obj'),
            current_price=current_price,
            macro_context=context.macro_context,
            is_btc=("BTC" in context.symbol.upper()),
            is_alt=("BTC" not in context.symbol.upper())
        )


# Singleton
_confluence_service: Optional[ConfluenceService] = None


def get_confluence_service() -> Optional[ConfluenceService]:
    """Get the singleton ConfluenceService instance."""
    return _confluence_service


def configure_confluence_service(
    scanner_mode=None, 
    config=None
) -> ConfluenceService:
    """Configure and return the singleton ConfluenceService."""
    global _confluence_service
    _confluence_service = ConfluenceService(scanner_mode=scanner_mode, config=config)
    return _confluence_service
