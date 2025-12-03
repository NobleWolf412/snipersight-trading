"""
Confluence Scorer Module

Implements multi-factor confluence scoring system for trade setups.

Evaluates setups across multiple dimensions:
- SMC patterns (order blocks, FVGs, structural breaks, liquidity sweeps)
- Technical indicators (RSI, Stoch RSI, MFI, volume)
- Higher timeframe alignment
- Market regime detection
- BTC impulse gate (for altcoins)
- Mode-aware MACD evaluation (primary/filter/veto based on scanner mode)
- Cycle-aware synergy bonuses (cycle turns, distribution breaks)

Outputs a comprehensive ConfluenceBreakdown with synergy bonuses and conflict penalties.
"""

from typing import List, Dict, Optional, Tuple, TYPE_CHECKING
from dataclasses import replace
import pandas as pd
import numpy as np
import logging

from backend.shared.models.smc import SMCSnapshot, OrderBlock, FVG, StructuralBreak, LiquiditySweep
from backend.shared.models.indicators import IndicatorSet, IndicatorSnapshot
from backend.shared.models.scoring import ConfluenceFactor, ConfluenceBreakdown
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import MACDModeConfig, get_macd_config
from backend.strategy.smc.volume_profile import VolumeProfile, calculate_volume_confluence_factor

# Conditional imports for type hints
if TYPE_CHECKING:
    from backend.shared.models.smc import CycleContext, ReversalContext

logger = logging.getLogger(__name__)


# --- Mode-Aware MACD Evaluation ---

def evaluate_macd_for_mode(
    indicators: IndicatorSnapshot,
    direction: str,
    macd_config: MACDModeConfig,
    htf_indicators: Optional[IndicatorSnapshot] = None,
    timeframe: str = "15m"
) -> Dict:
    """
    Evaluate MACD based on scanner mode configuration.
    
    Different modes use MACD differently:
    - HTF/Swing (treat_as_primary=True): MACD drives directional scoring (high weight)
    - Balanced (treat_as_primary=False): MACD is weighted confluence factor
    - Scalp/Surgical (allow_ltf_veto=True): HTF MACD for bias, LTF only vetoes
    
    Args:
        indicators: Current timeframe indicators with MACD data
        direction: Trade direction ("bullish" or "bearish")
        macd_config: Mode-specific MACD configuration
        htf_indicators: Higher timeframe indicators for HTF bias (optional)
        timeframe: Current timeframe string for logging
        
    Returns:
        Dict with score, reasons, role, and veto_active flag
    """
    score = 0.0
    reasons = []
    veto_active = False
    role = "PRIMARY" if macd_config.treat_as_primary else "FILTER"
    
    # Extract MACD values
    macd_line = getattr(indicators, 'macd_line', None)
    macd_signal = getattr(indicators, 'macd_signal', None)
    macd_histogram = getattr(indicators, 'macd_histogram', None)
    macd_line_series = getattr(indicators, 'macd_line_series', None) or []
    macd_signal_series = getattr(indicators, 'macd_signal_series', None) or []
    histogram_series = getattr(indicators, 'macd_histogram_series', None) or []
    
    if macd_line is None or macd_signal is None:
        return {"score": 0.0, "reasons": ["MACD data unavailable"], "role": role, "veto_active": False}
    
    # Check minimum amplitude filter (avoid chop)
    amplitude = abs(macd_line - macd_signal)
    if macd_config.min_amplitude > 0 and amplitude < macd_config.min_amplitude:
        return {"score": 0.0, "reasons": ["MACD in chop zone (below amplitude threshold)"], "role": "NEUTRAL", "veto_active": False}
    
    is_bullish = direction.lower() in ("bullish", "long")
    
    # --- HTF Bias Check (if enabled and HTF indicators available) ---
    htf_bias = "neutral"
    if macd_config.use_htf_bias and htf_indicators:
        htf_macd = getattr(htf_indicators, 'macd_line', None)
        htf_signal = getattr(htf_indicators, 'macd_signal', None)
        
        if htf_macd is not None and htf_signal is not None:
            if htf_macd > htf_signal:
                htf_bias = "bullish"
                if is_bullish:
                    score += 15.0 * macd_config.weight
                    reasons.append(f"HTF MACD bullish bias supports {direction}")
                else:
                    score -= 10.0 * macd_config.weight
                    reasons.append(f"HTF MACD bullish conflicts with {direction}")
            elif htf_macd < htf_signal:
                htf_bias = "bearish"
                if not is_bullish:
                    score += 15.0 * macd_config.weight
                    reasons.append(f"HTF MACD bearish bias supports {direction}")
                else:
                    score -= 10.0 * macd_config.weight
                    reasons.append(f"HTF MACD bearish conflicts with {direction}")
    
    # --- Persistence Check ---
    # Check if MACD/Signal relationship held for min_persistence_bars
    n_persist = min(macd_config.min_persistence_bars, len(macd_line_series), len(macd_signal_series))
    
    bullish_persistent = False
    bearish_persistent = False
    
    if n_persist >= 2 and len(macd_line_series) >= n_persist and len(macd_signal_series) >= n_persist:
        recent_macd = macd_line_series[-n_persist:]
        recent_signal = macd_signal_series[-n_persist:]
        bullish_persistent = all(m > s for m, s in zip(recent_macd, recent_signal))
        bearish_persistent = all(m < s for m, s in zip(recent_macd, recent_signal))
    
    # --- Primary vs Filter Scoring ---
    if macd_config.treat_as_primary:
        # HTF/Swing mode: MACD is a decision-maker with heavy impact
        if is_bullish and bullish_persistent:
            score += 25.0 * macd_config.weight
            reasons.append(f"{timeframe} MACD > Signal with {n_persist}-bar persistence (PRIMARY)")
            if macd_line > 0:
                score += 10.0 * macd_config.weight
                reasons.append(f"{timeframe} MACD above zero line (strong bullish)")
        elif not is_bullish and bearish_persistent:
            score += 25.0 * macd_config.weight
            reasons.append(f"{timeframe} MACD < Signal with {n_persist}-bar persistence (PRIMARY)")
            if macd_line < 0:
                score += 10.0 * macd_config.weight
                reasons.append(f"{timeframe} MACD below zero line (strong bearish)")
        elif (is_bullish and bearish_persistent) or (not is_bullish and bullish_persistent):
            score -= 20.0 * macd_config.weight
            reasons.append(f"{timeframe} MACD opposing direction with persistence (PRIMARY CONFLICT)")
        else:
            # No persistence - current bar only
            if is_bullish and macd_line > macd_signal:
                score += 8.0 * macd_config.weight
                reasons.append(f"{timeframe} MACD > Signal (no persistence)")
            elif not is_bullish and macd_line < macd_signal:
                score += 8.0 * macd_config.weight
                reasons.append(f"{timeframe} MACD < Signal (no persistence)")
    else:
        # Filter/Veto mode: MACD supports but doesn't drive
        if is_bullish and bullish_persistent:
            score += 10.0 * macd_config.weight
            reasons.append(f"{timeframe} MACD supportive bullish (FILTER)")
        elif not is_bullish and bearish_persistent:
            score += 10.0 * macd_config.weight
            reasons.append(f"{timeframe} MACD supportive bearish (FILTER)")
        elif macd_config.allow_ltf_veto:
            # Check for veto conditions
            if is_bullish and bearish_persistent:
                score -= 15.0 * macd_config.weight
                veto_active = True
                role = "VETO"
                reasons.append(f"{timeframe} MACD bearish veto active against bullish setup")
            elif not is_bullish and bullish_persistent:
                score -= 15.0 * macd_config.weight
                veto_active = True
                role = "VETO"
                reasons.append(f"{timeframe} MACD bullish veto active against bearish setup")
    
    # --- Histogram Analysis (if strict mode enabled) ---
    if macd_config.use_histogram_strict and len(histogram_series) >= 2:
        hist_expanding = histogram_series[-1] > histogram_series[-2]
        hist_contracting = histogram_series[-1] < histogram_series[-2]
        
        # Histogram should expand in trend direction
        if is_bullish:
            if macd_histogram and macd_histogram > 0 and hist_expanding:
                score += 8.0 * macd_config.weight
                reasons.append(f"{timeframe} histogram expanding bullish")
            elif macd_histogram and macd_histogram < 0 and hist_contracting:
                score -= 5.0 * macd_config.weight
                reasons.append(f"{timeframe} histogram contracting against bullish")
        else:
            if macd_histogram and macd_histogram < 0 and hist_expanding:
                # For bearish, "expanding" means histogram getting more negative
                score += 8.0 * macd_config.weight
                reasons.append(f"{timeframe} histogram expanding bearish")
            elif macd_histogram and macd_histogram > 0 and hist_contracting:
                score -= 5.0 * macd_config.weight
                reasons.append(f"{timeframe} histogram contracting against bearish")
    
    # Clamp score
    score = max(-30.0, min(50.0, score))
    
    return {
        "score": score,
        "reasons": reasons,
        "role": role,
        "veto_active": veto_active,
        "htf_bias": htf_bias,
        "persistent_bars": n_persist if (bullish_persistent or bearish_persistent) else 0
    }


def calculate_confluence_score(
    smc_snapshot: SMCSnapshot,
    indicators: IndicatorSet,
    config: ScanConfig,
    direction: str,
    htf_trend: Optional[str] = None,
    btc_impulse: Optional[str] = None,
    htf_context: Optional[dict] = None,
    cycle_context: Optional["CycleContext"] = None,
    reversal_context: Optional["ReversalContext"] = None,
    volume_profile: Optional[VolumeProfile] = None,
    current_price: Optional[float] = None
) -> ConfluenceBreakdown:
    """
    Calculate comprehensive confluence score for a trade setup.
    
    Args:
        smc_snapshot: SMC patterns detected across timeframes
        indicators: Technical indicators across timeframes
        config: Scan configuration with weights and thresholds
        direction: Trade direction ("bullish" or "bearish")
        htf_trend: Higher timeframe trend ("bullish", "bearish", "neutral")
        btc_impulse: BTC trend for altcoin gate ("bullish", "bearish", "neutral")
        htf_context: HTF level proximity context
        cycle_context: Optional cycle timing context for cycle-aware bonuses
        reversal_context: Optional reversal detection context for synergy bonuses
        volume_profile: Optional volume profile for institutional-grade VAP analysis
        current_price: Optional current price for volume profile entry analysis
        
    Returns:
        ConfluenceBreakdown: Complete scoring breakdown with factors
    """
    factors = []
    
    # --- SMC Pattern Scoring ---
    
    # Order Blocks
    ob_score = _score_order_blocks(smc_snapshot.order_blocks, direction)
    if ob_score > 0:
        factors.append(ConfluenceFactor(
            name="Order Block",
            score=ob_score,
            weight=0.20,
            rationale=_get_ob_rationale(smc_snapshot.order_blocks, direction)
        ))
    
    # Fair Value Gaps
    fvg_score = _score_fvgs(smc_snapshot.fvgs, direction)
    if fvg_score > 0:
        factors.append(ConfluenceFactor(
            name="Fair Value Gap",
            score=fvg_score,
            weight=0.15,
            rationale=_get_fvg_rationale(smc_snapshot.fvgs, direction)
        ))
    
    # Structural Breaks
    structure_score = _score_structural_breaks(smc_snapshot.structural_breaks, direction)
    if structure_score > 0:
        factors.append(ConfluenceFactor(
            name="Market Structure",
            score=structure_score,
            weight=0.25,
            rationale=_get_structure_rationale(smc_snapshot.structural_breaks, direction)
        ))
    
    # Liquidity Sweeps
    sweep_score = _score_liquidity_sweeps(smc_snapshot.liquidity_sweeps, direction)
    if sweep_score > 0:
        factors.append(ConfluenceFactor(
            name="Liquidity Sweep",
            score=sweep_score,
            weight=0.15,
            rationale=_get_sweep_rationale(smc_snapshot.liquidity_sweeps, direction)
        ))
    
    # --- Indicator Scoring ---
    
    # Get primary timeframe indicators (assume first in dict or specified)
    primary_tf = list(indicators.by_timeframe.keys())[0] if indicators.by_timeframe else None
    
    # Get MACD mode config based on profile
    profile = getattr(config, 'profile', 'balanced')
    macd_config = get_macd_config(profile)
    
    # Get HTF indicators for MACD bias (if available)
    htf_tf = macd_config.htf_timeframe
    htf_indicators = indicators.by_timeframe.get(htf_tf) if indicators.by_timeframe else None
    
    macd_analysis = None
    
    if primary_tf:
        primary_indicators = indicators.by_timeframe[primary_tf]
        
        # Momentum indicators (with mode-aware MACD)
        momentum_score, macd_analysis = _score_momentum(
            primary_indicators, 
            direction,
            macd_config=macd_config,
            htf_indicators=htf_indicators,
            timeframe=primary_tf
        )
        if momentum_score > 0:
            # Build momentum rationale including MACD analysis
            momentum_rationale = _get_momentum_rationale(primary_indicators, direction)
            if macd_analysis and macd_analysis.get("reasons"):
                momentum_rationale += f" | MACD [{macd_analysis['role']}]: {'; '.join(macd_analysis['reasons'][:2])}"
            
            factors.append(ConfluenceFactor(
                name="Momentum",
                score=momentum_score,
                weight=0.10,
                rationale=momentum_rationale
            ))
        
        # Volume confirmation
        volume_score = _score_volume(primary_indicators, direction)
        if volume_score > 0:
            factors.append(ConfluenceFactor(
                name="Volume",
                score=volume_score,
                weight=0.10,
                rationale=_get_volume_rationale(primary_indicators)
            ))

        # Volatility normalization (ATR%) - prefer moderate volatility
        volatility_score = _score_volatility(primary_indicators)
        if volatility_score > 0:
            factors.append(ConfluenceFactor(
                name="Volatility",
                score=volatility_score,
                weight=0.08,
                rationale=_get_volatility_rationale(primary_indicators)
            ))
    
    # --- Volume Profile (Institutional VAP Analysis) ---
    # Only if volume profile and current price are available
    if volume_profile and current_price:
        try:
            vp_factor = calculate_volume_confluence_factor(
                entry_price=current_price,
                volume_profile=volume_profile,
                direction=direction
            )
            if vp_factor and vp_factor.get('score', 0) > 0:
                factors.append(ConfluenceFactor(
                    name=vp_factor['name'],
                    score=vp_factor['score'],
                    weight=vp_factor['weight'],
                    rationale=vp_factor['rationale']
                ))
                logger.debug("📊 Volume Profile factor: %.1f (weight=%.2f)",
                            vp_factor['score'], vp_factor['weight'])
        except Exception as e:
            logger.debug("Volume profile scoring skipped: %s", e)
    
    # --- MACD Veto Check (for scalp/surgical modes) ---
    # If MACD veto is active, add a conflict factor
    if macd_analysis and macd_analysis.get("veto_active"):
        factors.append(ConfluenceFactor(
            name="MACD Veto",
            score=0.0,
            weight=0.05,
            rationale=f"MACD opposing direction with veto active: {'; '.join(macd_analysis.get('reasons', []))}"
        ))
    
    # --- HTF Alignment ---
    
    htf_aligned = False
    if htf_trend:
        htf_score = _score_htf_alignment(htf_trend, direction)
        if htf_score > 0:
            htf_aligned = True
            factors.append(ConfluenceFactor(
                name="HTF Alignment",
                score=htf_score,
                weight=0.20,
                rationale=f"Higher timeframe trend is {htf_trend}, aligns with {direction} setup"
            ))
    
    # --- HTF Level Proximity ---
    if getattr(config, 'htf_proximity_enabled', False) and htf_context:
        try:
            within_atr = float(htf_context.get('within_atr', 1e9))
            within_pct = float(htf_context.get('within_pct', 1e9))
            atr_cap = max(1e-6, float(getattr(config, 'htf_proximity_atr_max', 1.0)))
            pct_cap = max(1e-6, float(getattr(config, 'htf_proximity_pct_max', 2.0)))
            if within_atr <= atr_cap and within_pct <= pct_cap:
                # Map proximity to score: closer => higher
                proximity_score = max(0.0, min(100.0, 100.0 * (1.0 - (within_atr / atr_cap))))
                weight = float(getattr(config, 'htf_proximity_weight', 0.12))
                lvl_tf = htf_context.get('timeframe')
                lvl_type = htf_context.get('type')
                factors.append(ConfluenceFactor(
                    name="HTF Level Proximity",
                    score=proximity_score,
                    weight=weight,
                    rationale=f"Within {within_atr:.2f} ATR ({within_pct:.2f}%) of {lvl_tf} {lvl_type}"
                ))
        except Exception:
            pass

    # --- BTC Impulse Gate ---
    
    btc_impulse_gate = True
    if config.btc_impulse_gate_enabled and btc_impulse:
        if btc_impulse != direction and btc_impulse != "neutral":
            btc_impulse_gate = False
            # Add negative factor
            factors.append(ConfluenceFactor(
                name="BTC Impulse Gate",
                score=0.0,
                weight=0.15,
                rationale=f"BTC trend ({btc_impulse}) conflicts with setup direction ({direction})"
            ))
        else:
            btc_impulse_gate = True
            factors.append(ConfluenceFactor(
                name="BTC Impulse Gate",
                score=100.0,
                weight=0.10,
                rationale=f"BTC trend ({btc_impulse}) supports {direction} setup"
            ))
    
    # --- Normalize Weights ---
    
    # If no factors present, return minimal breakdown
    if not factors:
        return ConfluenceBreakdown(
            total_score=0.0,
            factors=[],
            synergy_bonus=0.0,
            conflict_penalty=0.0,
            regime="unknown",
            htf_aligned=False,
            btc_impulse_gate=True
        )
    
    # If not all factors present, weights won't sum to 1.0 - normalize them
    total_weight = sum(f.weight for f in factors)
    if total_weight > 0 and abs(total_weight - 1.0) > 0.01:
        # Normalize weights to sum to 1.0
        for i, factor in enumerate(factors):
            factors[i] = ConfluenceFactor(
                name=factor.name,
                score=factor.score,
                weight=factor.weight / total_weight,
                rationale=factor.rationale
            )
    
    # --- Calculate Weighted Score ---
    
    weighted_score = sum(f.score * f.weight for f in factors)
    
    # --- Synergy Bonuses ---
    
    synergy_bonus = _calculate_synergy_bonus(
        factors, 
        smc_snapshot,
        cycle_context=cycle_context,
        reversal_context=reversal_context,
        direction=direction
    )
    
    # --- Conflict Penalties ---
    
    conflict_penalty = _calculate_conflict_penalty(factors, direction)
    
    # --- Regime Detection ---
    
    regime = _detect_regime(smc_snapshot, indicators)
    
    # --- Final Score ---
    
    final_score = weighted_score + synergy_bonus - conflict_penalty
    final_score = max(0.0, min(100.0, final_score))  # Clamp to 0-100
    
    breakdown = ConfluenceBreakdown(
        total_score=final_score,
        factors=factors,
        synergy_bonus=synergy_bonus,
        conflict_penalty=conflict_penalty,
        regime=regime,
        htf_aligned=htf_aligned,
        btc_impulse_gate=btc_impulse_gate,
        htf_proximity_atr=(htf_context or {}).get('within_atr'),
        htf_proximity_pct=(htf_context or {}).get('within_pct'),
        nearest_htf_level_timeframe=(htf_context or {}).get('timeframe'),
        nearest_htf_level_type=(htf_context or {}).get('type')
    )
    
    return breakdown


# --- SMC Scoring Functions ---

def _score_order_blocks(order_blocks: List[OrderBlock], direction: str) -> float:
    """Score order blocks based on quality and alignment."""
    if not order_blocks:
        return 0.0
    
    # Filter for direction-aligned OBs
    aligned_obs = [ob for ob in order_blocks if ob.direction == direction]
    
    if not aligned_obs:
        return 0.0
    
    # Find best OB (highest freshness and displacement, lowest mitigation)
    best_ob = max(aligned_obs, key=lambda ob: (
        ob.freshness_score * 0.4 +
        min(ob.displacement_strength / 3.0, 1.0) * 0.4 +
        (1.0 - ob.mitigation_level) * 0.2
    ))
    
    # Score based on OB quality
    score = (
        best_ob.freshness_score * 40 +
        min(best_ob.displacement_strength / 2.0, 1.0) * 40 +
        (1.0 - best_ob.mitigation_level) * 20
    )
    
    return min(100.0, score)


def _score_fvgs(fvgs: List[FVG], direction: str) -> float:
    """Score FVGs based on size and unfilled status."""
    if not fvgs:
        return 0.0
    
    aligned_fvgs = [fvg for fvg in fvgs if fvg.direction == direction]
    
    if not aligned_fvgs:
        return 0.0
    
    # Prefer unfilled FVGs with larger size
    unfilled = [fvg for fvg in aligned_fvgs if fvg.overlap_with_price < 0.5]
    
    if not unfilled:
        return 30.0  # Some credit even if filled
    
    # Score based on size and unfilled status
    best_fvg = max(unfilled, key=lambda fvg: fvg.size * (1.0 - fvg.overlap_with_price))
    
    score = 70 + (1.0 - best_fvg.overlap_with_price) * 30
    
    return min(100.0, score)


def _score_structural_breaks(breaks: List[StructuralBreak], direction: str) -> float:
    """Score structural breaks (BOS/CHoCH)."""
    if not breaks:
        return 0.0
    
    # Get most recent break
    latest_break = max(breaks, key=lambda b: b.timestamp)
    
    # BOS in trend direction is strongest
    if latest_break.break_type == "BOS":
        base_score = 80.0
    else:  # CHoCH
        base_score = 60.0
    
    # Bonus for HTF alignment
    if latest_break.htf_aligned:
        base_score += 20.0
    
    return min(100.0, base_score)


def _score_liquidity_sweeps(sweeps: List[LiquiditySweep], direction: str) -> float:
    """Score liquidity sweeps."""
    if not sweeps:
        return 0.0
    
    # Look for recent sweeps that align with direction
    # Bullish setup benefits from low sweeps, bearish from high sweeps
    target_type = "low" if direction == "bullish" else "high"
    
    aligned_sweeps = [s for s in sweeps if s.sweep_type == target_type]
    
    if not aligned_sweeps:
        return 0.0
    
    # Get most recent
    latest_sweep = max(aligned_sweeps, key=lambda s: s.timestamp)
    
    # Score based on confirmation
    score = 70.0 if latest_sweep.confirmation else 50.0
    
    return score


# --- Indicator Scoring Functions ---

def _score_momentum(
    indicators: IndicatorSnapshot, 
    direction: str,
    macd_config: Optional[MACDModeConfig] = None,
    htf_indicators: Optional[IndicatorSnapshot] = None,
    timeframe: str = "15m"
) -> Tuple[float, Optional[Dict]]:
    """
    Score momentum indicators with mode-aware MACD evaluation.
    
    Args:
        indicators: Current timeframe indicators
        direction: Trade direction ("bullish" or "bearish")
        macd_config: Mode-specific MACD configuration (if None, uses legacy scoring)
        htf_indicators: HTF indicators for MACD bias check
        timeframe: Current timeframe string
        
    Returns:
        Tuple of (score, macd_analysis_dict or None)
    """
    score = 0.0
    macd_analysis = None
    
    if direction == "bullish":
        # Bullish momentum: oversold RSI, low Stoch RSI, low MFI
        if indicators.rsi is not None and indicators.rsi < 40:
            score += 40 * ((40 - indicators.rsi) / 40)
        
        if indicators.stoch_rsi is not None and indicators.stoch_rsi < 30:
            score += 30 * ((30 - indicators.stoch_rsi) / 30)
        
        if indicators.mfi is not None and indicators.mfi < 30:
            score += 30 * ((30 - indicators.mfi) / 30)
    
    else:  # bearish
        # Bearish momentum: overbought RSI, high Stoch RSI, high MFI
        if indicators.rsi is not None and indicators.rsi > 60:
            score += 40 * ((indicators.rsi - 60) / 40)
        
        if indicators.stoch_rsi is not None and indicators.stoch_rsi > 70:
            score += 30 * ((indicators.stoch_rsi - 70) / 30)
        
        if indicators.mfi is not None and indicators.mfi > 70:
            score += 30 * ((indicators.mfi - 70) / 30)
    
    # --- Mode-Aware MACD Evaluation ---
    if macd_config:
        # Use new mode-aware MACD scoring
        macd_analysis = evaluate_macd_for_mode(
            indicators=indicators,
            direction=direction,
            macd_config=macd_config,
            htf_indicators=htf_indicators,
            timeframe=timeframe
        )
        score += macd_analysis["score"]
    else:
        # Legacy MACD scoring (fallback for backward compatibility)
        macd_line = getattr(indicators, 'macd_line', None)
        macd_signal = getattr(indicators, 'macd_signal', None)
        if macd_line is not None and macd_signal is not None:
            if direction == "bullish":
                if macd_line > macd_signal and macd_line > 0:
                    score += 20.0
                elif macd_line > macd_signal:
                    score += 12.0
                else:
                    score += 5.0
            else:  # bearish
                if macd_line < macd_signal and macd_line < 0:
                    score += 20.0
                elif macd_line < macd_signal:
                    score += 12.0
                else:
                    score += 5.0

    # Stoch RSI K/D crossover enhancement (debounced by minimum separation)
    k = getattr(indicators, 'stoch_rsi_k', None)
    d = getattr(indicators, 'stoch_rsi_d', None)
    if k is not None and d is not None:
        separation = abs(k - d)
        # Require minimum separation to reduce whipsaws
        if separation >= 2.0:  # simple debounce threshold
            if direction == "bullish" and k > d:
                # Region-sensitive weighting
                if k < 20:
                    score += 25.0  # early oversold bullish cross
                elif k < 50:
                    score += 15.0
                elif k < 80:
                    score += 8.0
                else:
                    score += 5.0  # late/exhaustive
            elif direction == "bearish" and k < d:
                if k > 80:
                    score += 25.0  # overbought bearish cross
                elif k > 50:
                    score += 15.0
                elif k > 20:
                    score += 8.0
                else:
                    score += 5.0
            else:
                # Opposing crossover strong penalty (avoid chasing into momentum shift)
                if separation >= 5.0:
                    score -= 10.0

    # Clamp lower bound after penalties
    if score < 0:
        score = 0.0

    return (min(100.0, score), macd_analysis)


def _score_volume(indicators: IndicatorSnapshot, direction: str) -> float:
    """Score volume confirmation."""
    if indicators.volume_spike:
        return 100.0
    else:
        return 50.0  # Neutral if no spike


def _score_volatility(indicators: IndicatorSnapshot) -> float:
    """Score volatility using ATR% (price-normalized ATR). Prefer moderate volatility.

    Bracket logic (atr_pct in % terms):
    - <0.25%: very low -> 30 (risk of chop)
    - 0.25% - 0.75%: linear ramp to 100 (ideal development range)
    - 0.75% - 1.5%: gentle decline from 95 to 70 (still acceptable)
    - 1.5% - 3.0%: decline from 70 to 40 (moves become erratic)
    - >3.0%: 25 (excessive volatility, unreliable structure)
    """
    atr_pct = getattr(indicators, 'atr_percent', None)
    if atr_pct is None:
        return 0.0

    # Ensure positive
    if atr_pct <= 0:
        return 0.0

    # Convert fraction to percent if given as ratio (heuristic: assume atr_pct already % if > 1.0)
    val = atr_pct

    if val < 0.25:
        return 30.0
    if val < 0.75:
        # Map 0.25 -> 30 up to 0.75 -> 100
        return 30.0 + (val - 0.25) / (0.75 - 0.25) * (100.0 - 30.0)
    if val < 1.5:
        # 0.75 -> 95 down to 1.5 -> 70
        return 95.0 - (val - 0.75) / (1.5 - 0.75) * (95.0 - 70.0)
    if val < 3.0:
        # 1.5 -> 70 down to 3.0 -> 40
        return 70.0 - (val - 1.5) / (3.0 - 1.5) * (70.0 - 40.0)
    # >3.0
    return 25.0


def _score_htf_alignment(htf_trend: str, direction: str) -> float:
    """Score higher timeframe alignment."""
    if htf_trend == direction:
        return 100.0
    elif htf_trend == "neutral":
        return 50.0
    else:
        return 0.0


# --- Synergy and Conflict ---

def _calculate_synergy_bonus(
    factors: List[ConfluenceFactor], 
    smc: SMCSnapshot,
    cycle_context: Optional["CycleContext"] = None,
    reversal_context: Optional["ReversalContext"] = None,
    direction: str = ""
) -> float:
    """
    Calculate synergy bonus when multiple strong factors align.
    
    Includes cycle-aware bonuses when cycle/reversal context provided:
    - Cycle Turn Bonus (+15): CHoCH + cycle extreme + volume
    - Distribution Break Bonus (+15): CHoCH + LTR + distribution phase
    - Accumulation Zone Bonus (+12): Liquidity sweep + DCL/WCL + bullish OB
    
    Args:
        factors: List of confluence factors
        smc: SMC snapshot with patterns
        cycle_context: Optional cycle timing context
        reversal_context: Optional reversal detection context
        direction: Trade direction ("LONG" or "SHORT")
        
    Returns:
        Total synergy bonus
    """
    bonus = 0.0
    
    factor_names = [f.name for f in factors]
    
    # --- EXISTING SYNERGIES ---
    
    # Order Block + FVG + Structure = strong setup
    if "Order Block" in factor_names and "Fair Value Gap" in factor_names and "Market Structure" in factor_names:
        bonus += 10.0
    
    # Liquidity Sweep + Structure = institutional trap reversal
    if "Liquidity Sweep" in factor_names and "Market Structure" in factor_names:
        bonus += 8.0
    
    # HTF Alignment + strong momentum
    if "HTF Alignment" in factor_names and "Momentum" in factor_names:
        momentum_factor = next((f for f in factors if f.name == "Momentum"), None)
        if momentum_factor and momentum_factor.score > 70:
            bonus += 5.0
    
    # --- CYCLE-AWARE SYNERGIES ---
    
    # Use reversal_context if available (combines cycle + SMC)
    if reversal_context and reversal_context.is_reversal_setup:
        # Import here to avoid circular import
        try:
            from backend.strategy.smc.reversal_detector import combine_reversal_with_cycle_bonus
            if cycle_context:
                cycle_bonus = combine_reversal_with_cycle_bonus(reversal_context, cycle_context)
                bonus += cycle_bonus
                if cycle_bonus > 0:
                    logger.debug("📊 Cycle synergy bonus: +%.1f", cycle_bonus)
        except ImportError:
            pass  # Module not available, skip cycle bonus
    
    # Direct cycle context bonuses (when reversal_context not available)
    elif cycle_context:
        try:
            from backend.shared.models.smc import CyclePhase, CycleTranslation, CycleConfirmation
            
            direction_upper = direction.upper() if direction else ""
            
            # === CYCLE TURN BONUS (Long at cycle low) ===
            if direction_upper == "LONG":
                # At confirmed DCL/WCL with structure alignment
                if (cycle_context.phase == CyclePhase.ACCUMULATION and 
                    "Market Structure" in factor_names):
                    bonus += 10.0
                    logger.debug("📈 Accumulation + Structure bonus (+10)")
                
                # DCL/WCL zone with confirmed cycle low
                if ((cycle_context.in_dcl_zone or cycle_context.in_wcl_zone) and
                    cycle_context.dcl_confirmation == CycleConfirmation.CONFIRMED):
                    bonus += 8.0
                    logger.debug("📈 Confirmed cycle low bonus (+8)")
                
                # RTR translation supports longs
                if cycle_context.translation == CycleTranslation.RTR:
                    bonus += 5.0
                    logger.debug("📈 RTR translation bonus (+5)")
            
            # === DISTRIBUTION BREAK BONUS (Short at distribution) ===
            elif direction_upper == "SHORT":
                # LTR translation + distribution/markdown phase
                if (cycle_context.translation == CycleTranslation.LTR and
                    cycle_context.phase in [CyclePhase.DISTRIBUTION, CyclePhase.MARKDOWN]):
                    bonus += 12.0
                    logger.debug("📉 LTR Distribution bonus (+12)")
                
                # Distribution phase with structure break
                if (cycle_context.phase == CyclePhase.DISTRIBUTION and
                    "Market Structure" in factor_names):
                    bonus += 8.0
                    logger.debug("📉 Distribution + Structure bonus (+8)")
                
                # LTR translation alone (moderate bonus)
                elif cycle_context.translation == CycleTranslation.LTR:
                    bonus += 5.0
                    logger.debug("📉 LTR translation bonus (+5)")
        
        except ImportError:
            pass  # Cycle models not available
    
    return bonus


def _calculate_conflict_penalty(factors: List[ConfluenceFactor], direction: str) -> float:
    """Calculate penalty for conflicting signals."""
    penalty = 0.0
    
    # BTC impulse gate failure is major conflict
    btc_factor = next((f for f in factors if f.name == "BTC Impulse Gate"), None)
    if btc_factor and btc_factor.score == 0.0:
        penalty += 20.0
    
    # Weak momentum in strong setup
    momentum_factor = next((f for f in factors if f.name == "Momentum"), None)
    structure_factor = next((f for f in factors if f.name == "Market Structure"), None)
    
    if momentum_factor and structure_factor:
        if momentum_factor.score < 30 and structure_factor.score > 70:
            penalty += 10.0  # Structure says go, momentum says no
    
    return penalty


def _detect_regime(smc: SMCSnapshot, indicators: IndicatorSet) -> str:
    """Detect current market regime."""
    # Simplified regime detection
    # Would typically use more sophisticated analysis
    
    if smc.structural_breaks:
        latest_break = max(smc.structural_breaks, key=lambda b: b.timestamp)
        
        if latest_break.break_type == "BOS":
            return "trend"
        elif latest_break.break_type == "CHoCH":
            return "risk_off"  # Reversal suggests risk-off
    
    # Check volatility from indicators
    if indicators.by_timeframe:
        primary_tf = list(indicators.by_timeframe.keys())[0]
        primary_ind = indicators.by_timeframe[primary_tf]
        
        # High ATR suggests volatile/trending, low ATR suggests ranging
        if primary_ind.atr is not None:
            # This is simplified - would need historical context
            return "range"  # Default
    
    return "range"  # Default to range if unclear


# --- Rationale Generators ---

def _get_ob_rationale(order_blocks: List[OrderBlock], direction: str) -> str:
    """Generate rationale for order block factor."""
    aligned = [ob for ob in order_blocks if ob.direction == direction]
    if not aligned:
        return "No aligned order blocks"
    
    best = max(aligned, key=lambda ob: ob.freshness_score)
    return f"Fresh {direction} OB with {best.displacement_strength:.1f}x ATR displacement, {best.mitigation_level*100:.0f}% mitigated"


def _get_fvg_rationale(fvgs: List[FVG], direction: str) -> str:
    """Generate rationale for FVG factor."""
    aligned = [fvg for fvg in fvgs if fvg.direction == direction]
    if not aligned:
        return "No aligned FVGs"
    
    unfilled = [fvg for fvg in aligned if fvg.overlap_with_price < 0.5]
    if unfilled:
        return f"{len(unfilled)} unfilled {direction} FVG(s) present"
    else:
        return f"{len(aligned)} {direction} FVG(s), partially filled"


def _get_structure_rationale(breaks: List[StructuralBreak], direction: str) -> str:
    """Generate rationale for structure factor."""
    if not breaks:
        return "No structural breaks detected"
    
    latest = max(breaks, key=lambda b: b.timestamp)
    htf_status = "HTF aligned" if latest.htf_aligned else "LTF only"
    return f"Recent {latest.break_type} ({htf_status})"


def _get_sweep_rationale(sweeps: List[LiquiditySweep], direction: str) -> str:
    """Generate rationale for liquidity sweep factor."""
    target_type = "low" if direction == "bullish" else "high"
    aligned = [s for s in sweeps if s.sweep_type == target_type]
    
    if not aligned:
        return "No relevant liquidity sweeps"
    
    latest = max(aligned, key=lambda s: s.timestamp)
    conf_status = "volume confirmed" if latest.confirmation else "no volume confirmation"
    return f"Recent {target_type} sweep ({conf_status})"


def _get_momentum_rationale(indicators: IndicatorSnapshot, direction: str) -> str:
    """Generate rationale for momentum factor."""
    parts = []
    
    if indicators.rsi is not None:
        parts.append(f"RSI {indicators.rsi:.1f}")
    
    if indicators.stoch_rsi is not None:
        parts.append(f"Stoch {indicators.stoch_rsi:.1f}")
    # Include K/D relationship if available
    k = getattr(indicators, 'stoch_rsi_k', None)
    d = getattr(indicators, 'stoch_rsi_d', None)
    if k is not None and d is not None:
        relation = "above" if k > d else "below" if k < d else "equal"
        parts.append(f"K {k:.1f} {relation} D {d:.1f}")
        sep = abs(k - d)
        if sep >= 2.0:
            if direction == "bullish" and k > d and k < 20:
                parts.append("bullish oversold K/D crossover")
            elif direction == "bearish" and k < d and k > 80:
                parts.append("bearish overbought K/D crossover")
    
    if indicators.mfi is not None:
        parts.append(f"MFI {indicators.mfi:.1f}")
    if getattr(indicators, 'macd_line', None) is not None and getattr(indicators, 'macd_signal', None) is not None:
        parts.append(f"MACD {indicators.macd_line:.3f} vs signal {indicators.macd_signal:.3f}")
    
    status = "oversold" if direction == "bullish" else "overbought"
    return f"Momentum indicators show {status}: {', '.join(parts)}"


def _get_volume_rationale(indicators: IndicatorSnapshot) -> str:
    """Generate rationale for volume factor."""
    if indicators.volume_spike:
        return "Elevated volume confirms price action"
    else:
        return "Normal volume levels"


def _get_volatility_rationale(indicators: IndicatorSnapshot) -> str:
    """Generate rationale for volatility factor."""
    atr_pct = getattr(indicators, 'atr_percent', None)
    if atr_pct is None:
        return "ATR% unavailable"
    val = atr_pct
    if val < 0.25:
        zone = "very low volatility (range risk)"
    elif val < 0.75:
        zone = "healthy development volatility"
    elif val < 1.5:
        zone = "elevated but acceptable volatility"
    elif val < 3.0:
        zone = "high volatility (structure reliability reduced)"
    else:
        zone = "extreme volatility (erratic price action)"
    return f"ATR% {val:.2f}% - {zone}"
