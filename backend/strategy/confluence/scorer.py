"""
Confluence Scorer Module

Implements multi-factor confluence scoring system for trade setups.

Evaluates setups across multiple dimensions:
- SMC patterns (order blocks, FVGs, structural breaks, liquidity sweeps)
- Technical indicators (RSI, Stoch RSI, MFI, volume)
- Higher timeframe alignment
- Market regime detection
- BTC impulse gate (for altcoins)

Outputs a comprehensive ConfluenceBreakdown with synergy bonuses and conflict penalties.
"""

from typing import List, Dict, Optional
from dataclasses import replace
import pandas as pd
import numpy as np

from backend.shared.models.smc import SMCSnapshot, OrderBlock, FVG, StructuralBreak, LiquiditySweep
from backend.shared.models.indicators import IndicatorSet, IndicatorSnapshot
from backend.shared.models.scoring import ConfluenceFactor, ConfluenceBreakdown
from backend.shared.config.defaults import ScanConfig


def calculate_confluence_score(
    smc_snapshot: SMCSnapshot,
    indicators: IndicatorSet,
    config: ScanConfig,
    direction: str,
    htf_trend: Optional[str] = None,
    btc_impulse: Optional[str] = None
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
    
    if primary_tf:
        primary_indicators = indicators.by_timeframe[primary_tf]
        
        # Momentum indicators
        momentum_score = _score_momentum(primary_indicators, direction)
        if momentum_score > 0:
            factors.append(ConfluenceFactor(
                name="Momentum",
                score=momentum_score,
                weight=0.10,
                rationale=_get_momentum_rationale(primary_indicators, direction)
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
    
    synergy_bonus = _calculate_synergy_bonus(factors, smc_snapshot)
    
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
        btc_impulse_gate=btc_impulse_gate
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

def _score_momentum(indicators: IndicatorSnapshot, direction: str) -> float:
    """Score momentum indicators."""
    score = 0.0
    
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
    
    return min(100.0, score)


def _score_volume(indicators: IndicatorSnapshot, direction: str) -> float:
    """Score volume confirmation."""
    if indicators.volume_spike:
        return 100.0
    else:
        return 50.0  # Neutral if no spike


def _score_htf_alignment(htf_trend: str, direction: str) -> float:
    """Score higher timeframe alignment."""
    if htf_trend == direction:
        return 100.0
    elif htf_trend == "neutral":
        return 50.0
    else:
        return 0.0


# --- Synergy and Conflict ---

def _calculate_synergy_bonus(factors: List[ConfluenceFactor], smc: SMCSnapshot) -> float:
    """Calculate synergy bonus when multiple strong factors align."""
    bonus = 0.0
    
    factor_names = [f.name for f in factors]
    
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
    
    if indicators.mfi is not None:
        parts.append(f"MFI {indicators.mfi:.1f}")
    
    status = "oversold" if direction == "bullish" else "overbought"
    return f"Momentum indicators show {status}: {', '.join(parts)}"


def _get_volume_rationale(indicators: IndicatorSnapshot) -> str:
    """Generate rationale for volume factor."""
    if indicators.volume_spike:
        return "Elevated volume confirms price action"
    else:
        return "Normal volume levels"
