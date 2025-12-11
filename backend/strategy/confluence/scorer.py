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
from backend.analysis.premium_discount import detect_premium_discount
from backend.analysis.pullback_detector import detect_pullback_setup, PullbackSetup

# Conditional imports for type hints
if TYPE_CHECKING:
    from backend.shared.models.smc import CycleContext, ReversalContext

logger = logging.getLogger(__name__)


# ==============================================================================
# HTF CRITICAL GATES - These filter out low-quality signals
# ==============================================================================

def evaluate_htf_structural_proximity(
    smc: SMCSnapshot,
    indicators: IndicatorSet,
    entry_price: float,
    direction: str,
    mode_config: ScanConfig,
    swing_structure: Optional[Dict] = None
) -> Dict:
    """
    MANDATORY HTF Structural Proximity Gate.
    
    Validates that entry occurs at a meaningful HTF structural level:
    - HTF Order Block (4H/1D)
    - HTF FVG (4H/1D)
    - HTF Key Level (support/resistance)
    - HTF Swing Point (last HH/HL/LH/LL)
    - Premium/Discount Zone boundary
    
    If entry is >2 ATR from ANY HTF structure, apply HEAVY penalty or reject.
    """
    # Get HTF timeframes from mode config
    structure_tfs = getattr(mode_config, 'structure_timeframes', ('4h', '1d'))
    
    # Get ATR from primary planning timeframe
    primary_tf = getattr(mode_config, 'primary_planning_timeframe', '1h')
    primary_ind = indicators.by_timeframe.get(primary_tf)
    
    if not primary_ind or not primary_ind.atr:
        return {
            'valid': True,
            'score_adjustment': 0.0,
            'proximity_atr': None,
            'nearest_structure': 'ATR unavailable for validation',
            'structure_type': 'unknown'
        }
    
    atr = primary_ind.atr
    max_distance_atr = 5.0  # Allow entries up to 5 ATR from HTF structure without penalty
    
    min_distance = float('inf')
    nearest_structure = None
    structure_type = None
    
    # 1. Check HTF Order Blocks
    for ob in smc.order_blocks:
        if ob.timeframe not in structure_tfs:
            continue
        ob_grade = getattr(ob, 'grade', 'B')
        if ob_grade not in ('A', 'B'):
            continue
        if ob.freshness_score < 0.5:
            continue
        
        # OrderBlock uses 'high' and 'low', not 'top' and 'bottom'
        ob_center = (ob.high + ob.low) / 2
        distance = abs(entry_price - ob_center)
        distance_atr = distance / atr
        
        if distance_atr < min_distance:
            min_distance = distance_atr
            nearest_structure = f"{ob.timeframe} {ob.direction} OB @ {ob_center:.5f}"
            structure_type = "OrderBlock"
    
    # 2. Check HTF FVGs
    for fvg in smc.fvgs:
        if fvg.timeframe not in structure_tfs:
            continue
        if fvg.size < atr:
            continue
        if fvg.overlap_with_price > 0.5:
            continue
        
        if fvg.bottom <= entry_price <= fvg.top:
            min_distance = 0.0
            nearest_structure = f"{fvg.timeframe} FVG {fvg.bottom:.5f}-{fvg.top:.5f}"
            structure_type = "FVG"
            break
        
        distance = min(abs(entry_price - fvg.top), abs(entry_price - fvg.bottom))
        distance_atr = distance / atr
        
        if distance_atr < min_distance:
            min_distance = distance_atr
            nearest_structure = f"{fvg.timeframe} FVG boundary"
            structure_type = "FVG"
    
    # 3. Check HTF Swing Points
    if swing_structure:
        for tf in structure_tfs:
            if tf not in swing_structure:
                continue
            ss = swing_structure[tf]
            for swing_type in ['last_hh', 'last_hl', 'last_lh', 'last_ll']:
                swing_price = ss.get(swing_type)
                if swing_price:
                    distance = abs(entry_price - swing_price)
                    distance_atr = distance / atr
                    if distance_atr < min_distance:
                        min_distance = distance_atr
                        nearest_structure = f"{tf} {swing_type.upper()} @ {swing_price:.5f}"
                        structure_type = "SwingPoint"
    
    # 4. Check Premium/Discount Zone Boundaries
    htf = max(structure_tfs, key=lambda x: {'5m': 0, '15m': 1, '1h': 2, '4h': 3, '1d': 4, '1w': 5}.get(x, 0))
    htf_ind = indicators.by_timeframe.get(htf)
    
    if htf_ind and hasattr(htf_ind, 'dataframe'):
        try:
            df = htf_ind.dataframe
            pd_zone = detect_premium_discount(df, lookback=50, current_price=entry_price)
            
            eq_distance = abs(entry_price - pd_zone.equilibrium)
            eq_distance_atr = eq_distance / atr
            
            if eq_distance_atr < min_distance:
                min_distance = eq_distance_atr
                nearest_structure = f"{htf} Equilibrium @ {pd_zone.equilibrium:.5f}"
                structure_type = "PremiumDiscount"
            
            # Check if in optimal zone for direction
            in_optimal_zone = (
                (direction == 'bullish' and entry_price <= pd_zone.equilibrium) or
                (direction == 'bearish' and entry_price >= pd_zone.equilibrium)
            )
            
            if not in_optimal_zone and min_distance > 1.0:
                return {
                    'valid': False,
                    'score_adjustment': -40.0,
                    'proximity_atr': min_distance,
                    'nearest_structure': f"Entry in {pd_zone.current_zone} zone (wrong for {direction})",
                    'structure_type': "PremiumDiscount_VIOLATION"
                }
        except Exception:
            pass
    
    # DECISION LOGIC
    if min_distance <= max_distance_atr:
        bonus = 0.0
        if min_distance < 0.5:
            bonus = 15.0
        elif min_distance < 1.0:
            bonus = 10.0
        elif min_distance < 1.5:
            bonus = 5.0
        
        return {
            'valid': True,
            'score_adjustment': bonus,
            'proximity_atr': min_distance,
            'nearest_structure': nearest_structure or "HTF structure present",
            'structure_type': structure_type or "unknown"
        }
    else:
        # Handle case where no HTF structure was found at all
        if min_distance == float('inf'):
            # No structure found - return neutral result, don't penalize harshly
            # This can happen if OBs/FVGs only exist on LTF, not HTF
            return {
                'valid': True,  # Don't block, just don't give bonus
                'score_adjustment': -5.0,  # Small penalty for lack of HTF structure
                'proximity_atr': None,
                'nearest_structure': "No HTF structure detected on structure timeframes",
                'structure_type': "NONE_FOUND"
            }
        
        # Structure exists but is too far away - apply graduated penalty
        # -5 penalty per ATR beyond max_distance, capped at -20
        penalty = max(-20.0, -5.0 * (min_distance - max_distance_atr))
        return {
            'valid': False,
            'score_adjustment': penalty,
            'proximity_atr': min_distance,
            'nearest_structure': nearest_structure or "No HTF structure nearby",
            'structure_type': "NONE_NEARBY"
        }


def evaluate_htf_momentum_gate(
    indicators: IndicatorSet,
    direction: str,
    mode_config: ScanConfig,
    swing_structure: Optional[Dict] = None
) -> Dict:
    """
    HTF Momentum Gate - blocks counter-trend trades during strong HTF momentum.
    
    If HTF is in strong momentum AGAINST trade direction, apply veto or heavy penalty.
    """
    primary_tf = getattr(mode_config, 'primary_planning_timeframe', '1h')
    structure_tfs = getattr(mode_config, 'structure_timeframes', ('4h', '1d'))
    
    htf = max(structure_tfs, key=lambda x: {'5m': 0, '15m': 1, '1h': 2, '4h': 3, '1d': 4, '1w': 5}.get(x, 0))
    htf_ind = indicators.by_timeframe.get(htf)
    
    if not htf_ind:
        return {
            'allowed': True,
            'score_adjustment': 0.0,
            'htf_momentum': 'unknown',
            'htf_trend': 'unknown',
            'reason': f'No {htf} indicators available'
        }
    
    # Detect HTF trend from swing structure
    htf_trend = 'neutral'
    if swing_structure and htf in swing_structure:
        ss = swing_structure[htf]
        htf_trend = ss.get('trend', 'neutral')
    
    # Detect momentum strength from ATR expansion
    atr = htf_ind.atr
    atr_series = getattr(htf_ind, 'atr_series', [])
    
    momentum_strength = 'normal'
    if atr and len(atr_series) >= 10:
        recent_atr = atr_series[-10:]
        atr_expanding = sum(1 for i in range(1, len(recent_atr)) if recent_atr[i] > recent_atr[i-1])
        
        if atr_expanding >= 7:
            momentum_strength = 'strong'
        elif atr_expanding >= 5:
            momentum_strength = 'building'
        elif atr_expanding <= 3:
            momentum_strength = 'calm'
    
    # Check volume confirmation
    volume_strong = False
    if hasattr(htf_ind, 'relative_volume'):
        rel_vol = htf_ind.relative_volume
        if rel_vol and rel_vol > 1.3:
            volume_strong = True
    
    is_bullish_trade = direction.lower() in ('bullish', 'long')
    htf_is_bullish = htf_trend == 'bullish'
    htf_is_bearish = htf_trend == 'bearish'
    
    # Case 1: Strong momentum AGAINST trade direction
    if momentum_strength in ('strong', 'building'):
        if is_bullish_trade and htf_is_bearish:
            penalty = -50.0 if volume_strong else -35.0
            return {
                'allowed': False,
                'score_adjustment': penalty,
                'htf_momentum': momentum_strength,
                'htf_trend': htf_trend,
                'reason': f"{htf} in strong bearish momentum (blocking LONG)"
            }
        elif not is_bullish_trade and htf_is_bullish:
            penalty = -50.0 if volume_strong else -35.0
            return {
                'allowed': False,
                'score_adjustment': penalty,
                'htf_momentum': momentum_strength,
                'htf_trend': htf_trend,
                'reason': f"{htf} in strong bullish momentum (blocking SHORT)"
            }
    
    # Case 2: Calm/ranging HTF - allow counter-trend
    if momentum_strength == 'calm' or htf_trend == 'neutral':
        return {
            'allowed': True,
            'score_adjustment': 0.0,
            'htf_momentum': momentum_strength,
            'htf_trend': htf_trend,
            'reason': f"{htf} {htf_trend} with {momentum_strength} momentum"
        }
    
    # Case 3: Momentum WITH trade direction - bonus
    if (is_bullish_trade and htf_is_bullish) or (not is_bullish_trade and htf_is_bearish):
        bonus = 10.0 if momentum_strength == 'strong' else 5.0
        return {
            'allowed': True,
            'score_adjustment': bonus,
            'htf_momentum': momentum_strength,
            'htf_trend': htf_trend,
            'reason': f"{htf} momentum supports {direction}"
        }
    
    return {
        'allowed': True,
        'score_adjustment': 0.0,
        'htf_momentum': momentum_strength,
        'htf_trend': htf_trend,
        'reason': f"{htf} {htf_trend} with {momentum_strength} momentum"
    }


def resolve_timeframe_conflicts(
    indicators: IndicatorSet,
    direction: str,
    mode_config: ScanConfig,
    swing_structure: Optional[Dict] = None,
    htf_proximity: Optional[Dict] = None
) -> Dict:
    """
    Resolve timeframe conflicts with explicit hierarchical rules.
    """
    profile = getattr(mode_config, 'profile', 'balanced')
    is_scalp_mode = profile in ('intraday_aggressive', 'precision')
    is_swing_mode = profile in ('macro_surveillance', 'stealth_balanced')
    
    conflicts = []
    resolution_reason_parts = []
    score_adjustment = 0.0
    resolution = 'allowed'
    
    # Get all timeframe trends
    timeframes = ['1w', '1d', '4h', '1h', '15m']
    tf_trends = {}
    
    for tf in timeframes:
        if swing_structure and tf in swing_structure:
            ss = swing_structure[tf]
            tf_trends[tf] = ss.get('trend', 'neutral')
    
    # Define primary bias TF based on mode
    if is_scalp_mode:
        primary_tf = '1h'
        filter_tfs = ['4h']
    elif is_swing_mode:
        primary_tf = '4h'
        filter_tfs = ['1d', '1w']
    else:
        primary_tf = '1h'
        filter_tfs = ['4h', '1d']
    
    primary_trend = tf_trends.get(primary_tf, 'neutral')
    is_bullish_trade = direction.lower() in ('bullish', 'long')
    
    primary_aligned = (
        (is_bullish_trade and primary_trend == 'bullish') or
        (not is_bullish_trade and primary_trend == 'bearish')
    )
    
    if not primary_aligned:
        conflicts.append(f"{primary_tf} {primary_trend} (primary)")
        resolution_reason_parts.append(f"Primary TF ({primary_tf}) not aligned with {direction}")
        score_adjustment -= 10.0  # Reduced from 15 to keep score >= 40 (Weak vs Missing)
        resolution = 'caution'
    
    # Check filter timeframes
    for tf in filter_tfs:
        if tf not in tf_trends:
            continue
        
        htf_trend = tf_trends[tf]
        htf_aligned = (
            (is_bullish_trade and htf_trend == 'bullish') or
            (not is_bullish_trade and htf_trend == 'bearish')
        )
        
        if not htf_aligned and htf_trend != 'neutral':
            conflicts.append(f"{tf} {htf_trend}")
            
            htf_ind = indicators.by_timeframe.get(tf)
            is_strong_momentum = False
            
            if htf_ind and htf_ind.atr:
                atr_series = getattr(htf_ind, 'atr_series', [])
                if len(atr_series) >= 5:
                    recent_atr = atr_series[-5:]
                    expanding_bars = sum(1 for i in range(1, len(recent_atr)) if recent_atr[i] > recent_atr[i-1])
                    is_strong_momentum = (expanding_bars >= 4)
            
            if is_strong_momentum:
                resolution = 'blocked'
                score_adjustment -= 40.0
                resolution_reason_parts.append(f"{tf} in strong {htf_trend} momentum, blocking {direction}")
                break
            else:
                resolution = 'caution'
                score_adjustment -= 10.0
                resolution_reason_parts.append(f"{tf} {htf_trend} but not strong momentum")
    
    # Exception: At major HTF structure, reduce penalty
    proximity_atr = htf_proximity.get('proximity_atr') if htf_proximity else None
    if htf_proximity and htf_proximity.get('valid') and proximity_atr is not None and proximity_atr < 1.0:
        score_adjustment += 15.0
        resolution_reason_parts.append("At major HTF structure (overrides conflict penalty)")
        if resolution == 'blocked' and score_adjustment > -30.0:
            resolution = 'caution'
    
    if not conflicts:
        resolution = 'allowed'
        resolution_reason_parts.append("All timeframes aligned or neutral")
    
    return {
        'resolution': resolution,
        'score_adjustment': score_adjustment,
        'conflicts': conflicts,
        'resolution_reason': '; '.join(resolution_reason_parts) if resolution_reason_parts else 'No conflicts'
    }


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
    score = 50.0  # Start at Neutral (50) instead of 0
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
            # Check for veto conditions - reduced penalty from -15 to -8 for less aggressive filtering
            if is_bullish and bearish_persistent:
                score -= 8.0 * macd_config.weight
                veto_active = True
                role = "VETO"
                reasons.append(f"{timeframe} MACD bearish veto active against bullish setup")
            elif not is_bullish and bullish_persistent:
                score -= 8.0 * macd_config.weight
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
    # Clamp score
    # Scale: -30..50 was raw. Now 50 + adj.
    # Max theoretical with defaults: 50 + 25 + 10 = 85.
    score = max(0.0, min(100.0, score))
    
    return {
        "score": score,
        "reasons": reasons,
        "role": role,
        "veto_active": veto_active,
        "htf_bias": htf_bias,
        "persistent_bars": n_persist if (bullish_persistent or bearish_persistent) else 0
    }


def evaluate_weekly_stoch_rsi_bonus(
    indicators: IndicatorSet,
    direction: str,
    oversold_threshold: float = 20.0,
    overbought_threshold: float = 80.0,
    max_bonus: float = 15.0,
    max_penalty: float = 10.0
) -> Dict:
    """
    Evaluate Weekly StochRSI as a directional BONUS system (not a hard gate).
    
    This function calculates a score bonus/penalty based on Weekly StochRSI position
    and crossover events. It influences direction selection through scoring, not gating.
    
    Bonus Logic:
    - K line crossing ABOVE 20 (from oversold): +15 bonus for LONG, -10 for SHORT
    - K line crossing BELOW 80 (from overbought): +15 bonus for SHORT, -10 for LONG
    - K in oversold zone (<20): +10 for LONG (anticipation), +5 for SHORT (momentum)
    - K in overbought zone (>80): +10 for SHORT (anticipation), +5 for LONG (momentum)
    - K in neutral zone (20-80): No bonus either direction
    
    The bonus system means BOTH directions can still trade, but the direction aligned
    with Weekly StochRSI gets a meaningful score advantage.
    
    Args:
        indicators: Technical indicators across timeframes (must contain '1W')
        direction: Trade direction ("bullish" or "bearish")
        oversold_threshold: K value below this is oversold (default 20)
        overbought_threshold: K value above this is overbought (default 80)
        max_bonus: Maximum bonus for aligned direction (default 15)
        max_penalty: Maximum penalty for contra direction (default 10)
        
    Returns:
        Dict with:
            - bonus: float - score adjustment for this direction (can be negative)
            - reason: str - explanation of bonus calculation
            - weekly_k: float - current Weekly StochRSI K value
            - weekly_k_prev: float - previous Weekly StochRSI K value
            - crossover_type: str - 'bullish_cross', 'bearish_cross', 'entering_oversold', 
                              'entering_overbought', 'in_oversold', 'in_overbought', 'neutral'
            - aligned: bool - whether this direction is aligned with Weekly StochRSI
    """
    result = {
        "bonus": 0.0,
        "reason": "Weekly StochRSI data unavailable",
        "weekly_k": None,
        "weekly_k_prev": None,
        "crossover_type": "neutral",
        "aligned": True  # Default to aligned if no data
    }
    
    # Get weekly indicators
    weekly_ind = indicators.by_timeframe.get('1W') or indicators.by_timeframe.get('1w')
    if not weekly_ind:
        return result
    
    # Get current and previous K values
    k_current = getattr(weekly_ind, 'stoch_rsi_k', None)
    if k_current is None:
        k_current = getattr(weekly_ind, 'stoch_rsi', None)
    k_prev = getattr(weekly_ind, 'stoch_rsi_k_prev', None)
    
    if k_current is None:
        return result
    
    result["weekly_k"] = k_current
    result["weekly_k_prev"] = k_prev
    
    is_bullish = direction.lower() in ("bullish", "long")
    
    # === CROSSOVER DETECTION (requires previous value) ===
    if k_prev is not None:
        # Bullish crossover: K crosses UP through oversold threshold (20)
        bullish_cross = k_prev < oversold_threshold and k_current >= oversold_threshold
        
        # Bearish crossover: K crosses DOWN through overbought threshold (80)
        bearish_cross = k_prev > overbought_threshold and k_current <= overbought_threshold
        
        # Entering oversold (bearish momentum building)
        entering_oversold = k_prev >= oversold_threshold and k_current < oversold_threshold
        
        # Entering overbought (bullish momentum building)
        entering_overbought = k_prev <= overbought_threshold and k_current > overbought_threshold
        
        if bullish_cross:
            result["crossover_type"] = "bullish_cross"
            if is_bullish:
                result["bonus"] = max_bonus
                result["aligned"] = True
                result["reason"] = f"Weekly StochRSI bullish cross ({k_prev:.1f}→{k_current:.1f}) - LONG strongly favored (+{max_bonus:.0f})"
            else:
                result["bonus"] = -max_penalty
                result["aligned"] = False
                result["reason"] = f"Weekly StochRSI bullish cross conflicts with SHORT (-{max_penalty:.0f})"
                
        elif bearish_cross:
            result["crossover_type"] = "bearish_cross"
            if not is_bullish:
                result["bonus"] = max_bonus
                result["aligned"] = True
                result["reason"] = f"Weekly StochRSI bearish cross ({k_prev:.1f}→{k_current:.1f}) - SHORT strongly favored (+{max_bonus:.0f})"
            else:
                result["bonus"] = -max_penalty
                result["aligned"] = False
                result["reason"] = f"Weekly StochRSI bearish cross conflicts with LONG (-{max_penalty:.0f})"
                
        elif entering_oversold:
            result["crossover_type"] = "entering_oversold"
            if not is_bullish:
                result["bonus"] = 8.0  # Following momentum
                result["aligned"] = True
                result["reason"] = f"Weekly StochRSI entering oversold ({k_current:.1f}) - SHORT momentum bonus (+8)"
            else:
                result["bonus"] = 5.0  # Anticipation (could reverse soon)
                result["aligned"] = True  # Not contra, just waiting
                result["reason"] = f"Weekly StochRSI entering oversold ({k_current:.1f}) - LONG anticipation (+5)"
                
        elif entering_overbought:
            result["crossover_type"] = "entering_overbought"
            if is_bullish:
                result["bonus"] = 8.0  # Following momentum
                result["aligned"] = True
                result["reason"] = f"Weekly StochRSI entering overbought ({k_current:.1f}) - LONG momentum bonus (+8)"
            else:
                result["bonus"] = 5.0  # Anticipation (could reverse soon)
                result["aligned"] = True  # Not contra, just waiting
                result["reason"] = f"Weekly StochRSI entering overbought ({k_current:.1f}) - SHORT anticipation (+5)"
        else:
            # No crossover - use position-based bonuses
            result = _position_based_stoch_bonus(k_current, is_bullish, oversold_threshold, 
                                                  overbought_threshold, result)
    else:
        # No previous value - use position-based bonuses only
        result = _position_based_stoch_bonus(k_current, is_bullish, oversold_threshold,
                                              overbought_threshold, result)
    
    return result


def _position_based_stoch_bonus(
    k_current: float,
    is_bullish: bool,
    oversold_threshold: float,
    overbought_threshold: float,
    result: Dict
) -> Dict:
    """
    Calculate position-based Weekly StochRSI bonus when no crossover detected.
    """
    if k_current < oversold_threshold:
        result["crossover_type"] = "in_oversold"
        if is_bullish:
            result["bonus"] = 10.0  # In prime reversal zone
            result["aligned"] = True
            result["reason"] = f"Weekly StochRSI oversold ({k_current:.1f}) - LONG reversal zone (+10)"
        else:
            result["bonus"] = 5.0  # Following momentum, but may reverse
            result["aligned"] = True
            result["reason"] = f"Weekly StochRSI oversold ({k_current:.1f}) - SHORT momentum (+5)"
            
    elif k_current > overbought_threshold:
        result["crossover_type"] = "in_overbought"
        if not is_bullish:
            result["bonus"] = 10.0  # In prime reversal zone
            result["aligned"] = True
            result["reason"] = f"Weekly StochRSI overbought ({k_current:.1f}) - SHORT reversal zone (+10)"
        else:
            result["bonus"] = 5.0  # Following momentum, but may reverse
            result["aligned"] = True
            result["reason"] = f"Weekly StochRSI overbought ({k_current:.1f}) - LONG momentum (+5)"
    else:
        result["crossover_type"] = "neutral"
        result["bonus"] = 0.0
        result["aligned"] = True
        result["reason"] = f"Weekly StochRSI neutral ({k_current:.1f}) - no directional bonus"
    
    return result


# Legacy alias for backward compatibility
def evaluate_weekly_stoch_rsi_gate(
    indicators: IndicatorSet,
    direction: str,
    oversold_threshold: float = 20.0,
    overbought_threshold: float = 80.0
) -> Dict:
    """
    Legacy gate function - now wraps the bonus system.
    
    For backward compatibility, converts bonus to gate_passed based on whether
    the bonus is negative (failed gate) or non-negative (passed gate).
    """
    bonus_result = evaluate_weekly_stoch_rsi_bonus(
        indicators, direction, oversold_threshold, overbought_threshold
    )
    
    return {
        "gate_passed": bonus_result["bonus"] >= 0,
        "reason": bonus_result["reason"],
        "weekly_k": bonus_result["weekly_k"],
        "weekly_k_prev": bonus_result["weekly_k_prev"],
        "crossover_type": bonus_result["crossover_type"],
        "bonus": bonus_result["bonus"],
        "aligned": bonus_result["aligned"]
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
    
    # Normalize direction at entry: LONG/SHORT -> bullish/bearish
    # This ensures consistent format throughout all scoring functions
    direction = _normalize_direction(direction)
    
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
            # Add negative factor (softened penalty)
            factors.append(ConfluenceFactor(
                name="BTC Impulse Gate",
                score=40.0,
                weight=0.10,
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
    
    # --- Weekly StochRSI Bonus ---
    # Directional bonus/penalty system based on weekly momentum
    # Replaces the old hard gate - no longer blocks, just influences score
    weekly_stoch_rsi_bonus = 0.0
    weekly_stoch_rsi_analysis = None
    
    if getattr(config, 'weekly_stoch_rsi_gate_enabled', True):  # Config key kept for backward compat
        weekly_stoch_rsi_analysis = evaluate_weekly_stoch_rsi_bonus(
            indicators=indicators,
            direction=direction,
            oversold_threshold=getattr(config, 'weekly_stoch_rsi_oversold', 20.0),
            overbought_threshold=getattr(config, 'weekly_stoch_rsi_overbought', 80.0)
        )
        
        weekly_stoch_rsi_bonus = weekly_stoch_rsi_analysis["bonus"]
        is_aligned = weekly_stoch_rsi_analysis.get("aligned", True)
        
        # Add as a factor that influences but doesn't block
        if weekly_stoch_rsi_bonus > 0:
            # Positive bonus - momentum aligned with direction
            # Convert bonus to 0-100 scale for factor (bonus max is ~15, so scale by 6.67)
            factor_score = min(100.0, 50.0 + weekly_stoch_rsi_bonus * 3.33)
            factors.append(ConfluenceFactor(
                name="Weekly StochRSI Bonus",
                score=factor_score,
                weight=0.10,
                rationale=f"[+{weekly_stoch_rsi_bonus:.1f}] {weekly_stoch_rsi_analysis['reason']}"
            ))
            logger.debug("📈 Weekly StochRSI BONUS +%.1f: %s", weekly_stoch_rsi_bonus, weekly_stoch_rsi_analysis["reason"])
        elif weekly_stoch_rsi_bonus < 0:
            # Negative bonus (penalty) - momentum opposes direction
            # Penalty reduces score but doesn't block (penalty max is -10)
            factor_score = max(0.0, 50.0 + weekly_stoch_rsi_bonus * 5.0)  # -10 penalty = 0 score
            factors.append(ConfluenceFactor(
                name="Weekly StochRSI Bonus",
                score=factor_score,
                weight=0.08,  # Lower weight for penalties
                rationale=f"[{weekly_stoch_rsi_bonus:.1f}] {weekly_stoch_rsi_analysis['reason']}"
            ))
            logger.debug("📉 Weekly StochRSI PENALTY %.1f: %s", weekly_stoch_rsi_bonus, weekly_stoch_rsi_analysis["reason"])
        # For zero bonus (neutral), no factor added - doesn't help or hurt
    
    # --- HTF Structure Bias (HH/HL/LH/LL) ---
    # Score based on swing structure alignment with trade direction
    # This is KEY for pullback trading - HTF trend defines preferred direction
    htf_structure_bonus = 0.0
    htf_structure_analysis = None
    
    if smc_snapshot.swing_structure:
        htf_structure_analysis = _score_htf_structure_bias(
            swing_structure=smc_snapshot.swing_structure,
            direction=direction
        )
        htf_structure_bonus = htf_structure_analysis['bonus']
        
        if htf_structure_bonus != 0:
            # Add as weighted factor
            if htf_structure_bonus > 0:
                # Aligned with HTF structure → bonus
                factor_score = min(100.0, 50.0 + htf_structure_bonus * 3.33)
                factors.append(ConfluenceFactor(
                    name="HTF Structure Bias",
                    score=factor_score,
                    weight=0.12,  # Significant weight for HTF alignment
                    rationale=f"[+{htf_structure_bonus:.1f}] {htf_structure_analysis['reason']}"
                ))
                logger.debug("📊 HTF Structure BONUS +%.1f: %s", htf_structure_bonus, htf_structure_analysis['reason'])
            else:
                # Counter-trend → check if pullback conditions override the penalty
                pullback_override = False
                pullback_bonus = 0.0
                pullback_rationale = ""
                
                # Try to detect pullback setup using 4H data
                try:
                    # Get 4H dataframe from indicators
                    ind_4h = indicators.by_timeframe.get('4h')
                    df_4h = getattr(ind_4h, 'dataframe', None) if ind_4h else None
                    
                    if df_4h is not None and len(df_4h) > 30:
                        # Detect pullback setup
                        pullback_dir = "SHORT" if direction.upper() == "BEARISH" or direction.upper() == "SHORT" else "LONG"
                        pullback_result = detect_pullback_setup(
                            df_4h=df_4h,
                            smc_snapshot=smc_snapshot,
                            requested_direction=pullback_dir,
                            extension_threshold=3.0  # 3% from EMA
                        )
                        
                        if pullback_result.override_counter_trend:
                            pullback_override = True
                            pullback_bonus = 8.0  # Convert penalty to +8 bonus
                            pullback_rationale = f"PULLBACK OVERRIDE: {pullback_result.rationale}"
                            logger.info(f"🔄 Pullback detected, overriding counter-trend penalty: {pullback_rationale}")
                except Exception as e:
                    logger.debug(f"Pullback detection failed: {e}")
                
                if pullback_override:
                    # Pullback conditions met → give bonus instead of penalty!
                    factor_score = min(100.0, 50.0 + pullback_bonus * 3.33)
                    factors.append(ConfluenceFactor(
                        name="HTF Pullback Setup",
                        score=factor_score,
                        weight=0.12,  # Same weight as aligned HTF
                        rationale=f"[+{pullback_bonus:.1f}] {pullback_rationale}"
                    ))
                    logger.debug("🔄 HTF Pullback BONUS +%.1f: %s", pullback_bonus, pullback_rationale)
                else:
                    # No pullback override → apply counter-trend penalty as usual
                    factor_score = max(0.0, 50.0 + htf_structure_bonus * 5.0)
                    factors.append(ConfluenceFactor(
                        name="HTF Structure Bias",
                        score=factor_score,
                        weight=0.08,
                        rationale=f"[{htf_structure_bonus:.1f}] {htf_structure_analysis['reason']}"
                    ))
                    logger.debug("⚠️ HTF Structure PENALTY %.1f: %s", htf_structure_bonus, htf_structure_analysis['reason'])
    
    # ===========================================================================
    # === CRITICAL HTF GATES (New: filters low-quality signals) ===
    # ===========================================================================
    
    # Get current price for proximity calculations
    entry_price = current_price
    if not entry_price and primary_tf:
        # Try to get from indicators
        prim_ind = indicators.by_timeframe.get(primary_tf)
        if prim_ind and hasattr(prim_ind, 'dataframe') and prim_ind.dataframe is not None:
            entry_price = prim_ind.dataframe['close'].iloc[-1] if len(prim_ind.dataframe) > 0 else None
    
    # === Gate 1: HTF STRUCTURAL PROXIMITY GATE ===
    # Entry must be at meaningful HTF structural level
    htf_proximity_result = None
    if getattr(config, 'enable_htf_structural_gate', True) and entry_price:
        htf_proximity_result = evaluate_htf_structural_proximity(
            smc=smc_snapshot,
            indicators=indicators,
            entry_price=entry_price,
            direction=direction,
            mode_config=config,
            swing_structure=smc_snapshot.swing_structure
        )
        
        if htf_proximity_result['score_adjustment'] != 0:
            factor_score = max(0.0, min(100.0, 50.0 + htf_proximity_result['score_adjustment'] * 1.5))
            factors.append(ConfluenceFactor(
                name="HTF_Structural_Proximity",
                score=factor_score,
                weight=0.15,
                rationale=f"{htf_proximity_result['nearest_structure']} ({htf_proximity_result.get('proximity_atr', 'N/A'):.1f} ATR)" if htf_proximity_result.get('proximity_atr') else htf_proximity_result['nearest_structure']
            ))
            
            if not htf_proximity_result['valid']:
                logger.warning("🚫 HTF Structural Gate FAILED: entry %.1f ATR from nearest structure", 
                             htf_proximity_result.get('proximity_atr', 999))
    
    # === Gate 2: HTF MOMENTUM GATE ===
    # Block counter-trend trades during strong HTF momentum
    if getattr(config, 'enable_htf_momentum_gate', True):
        momentum_gate = evaluate_htf_momentum_gate(
            indicators=indicators,
            direction=direction,
            mode_config=config,
            swing_structure=smc_snapshot.swing_structure
        )
        
        if momentum_gate['score_adjustment'] != 0:
            factor_score = max(0.0, min(100.0, 50.0 + momentum_gate['score_adjustment'] * 1.0))
            factors.append(ConfluenceFactor(
                name="HTF_Momentum_Gate",
                score=factor_score,
                weight=0.12,
                rationale=momentum_gate['reason']
            ))
            
            if not momentum_gate['allowed']:
                logger.warning("🚫 HTF Momentum Gate BLOCKED: %s trend with %s momentum",
                             momentum_gate['htf_trend'], momentum_gate['htf_momentum'])
    
    # === Gate 3: TIMEFRAME CONFLICT RESOLUTION ===
    # Explicit rules for handling timeframe conflicts
    if getattr(config, 'enable_conflict_resolution', True):
        conflict_result = resolve_timeframe_conflicts(
            indicators=indicators,
            direction=direction,
            mode_config=config,
            swing_structure=smc_snapshot.swing_structure,
            htf_proximity=htf_proximity_result
        )
        
        if conflict_result['score_adjustment'] != 0:
            factor_score = max(0.0, min(100.0, 50.0 + conflict_result['score_adjustment'] * 1.0))
            factors.append(ConfluenceFactor(
                name="Timeframe_Conflict_Resolution",
                score=factor_score,
                weight=0.10,
                rationale=conflict_result['resolution_reason']
            ))
            
            if conflict_result['resolution'] == 'blocked':
                logger.warning("🚫 Timeframe Conflict BLOCKED: conflicts: %s",
                             ', '.join(conflict_result['conflicts']))
    
    # --- Normalize Weights ---
    
    # If no factors present, return minimal breakdown
    if not factors:
        # Detect regime even if no factors (defaults to 'range' if no data)
        regime = _detect_regime(smc_snapshot, indicators)
        logger.warning("⚠️ No confluence factors generated! Possible data starvation or strict mode. Defaulting regime to %s.", regime)
        
        return ConfluenceBreakdown(
            total_score=0.0,
            factors=[],
            synergy_bonus=0.0,
            conflict_penalty=0.0,
            regime=regime,
            htf_aligned=False,
            btc_impulse_gate=True,
            weekly_stoch_rsi_gate=True
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
        weekly_stoch_rsi_gate=True,  # DEPRECATED - always True (no longer a hard gate)
        weekly_stoch_rsi_bonus=weekly_stoch_rsi_bonus,  # NEW bonus system
        htf_proximity_atr=(htf_context or {}).get('within_atr'),
        htf_proximity_pct=(htf_context or {}).get('within_pct'),
        nearest_htf_level_timeframe=(htf_context or {}).get('timeframe'),
        nearest_htf_level_type=(htf_context or {}).get('type')
    )
    
    return breakdown


# --- HTF Structure Bias Scoring ---

def _score_htf_structure_bias(swing_structure: dict, direction: str) -> dict:
    """
    Score setup based on HTF swing structure (HH/HL/LH/LL).
    
    This is the key function for pullback trading:
    - If Weekly/Daily shows bullish structure (HH/HL), LONG setups get bonus
    - If Weekly/Daily shows bearish structure (LH/LL), SHORT setups get bonus
    - Pullback entries (LTF against HTF → BOS back toward HTF) score highest
    
    Args:
        swing_structure: Dict of {timeframe: SwingStructure.to_dict()}
        direction: "LONG" or "SHORT"
        
    Returns:
        dict with 'bonus' (float), 'reason' (str), 'htf_bias' (str)
    """
    if not swing_structure:
        return {'bonus': 0.0, 'reason': 'No HTF swing structure data', 'htf_bias': 'neutral'}
    
    # Prioritize timeframes: Weekly > Daily > 4H
    # NOTE: Use lowercase to match scanner mode timeframe conventions
    htf_priority = ['1w', '1d', '4h']
    
    bullish_tfs = []
    bearish_tfs = []
    
    for tf in htf_priority:
        # Check both lowercase and uppercase for compatibility
        ss = swing_structure.get(tf) or swing_structure.get(tf.upper())
        if ss:
            trend = ss.get('trend', 'neutral')
            if trend == 'bullish':
                bullish_tfs.append(tf)
            elif trend == 'bearish':
                bearish_tfs.append(tf)
    
    # Calculate bias strength based on HTF alignment
    # Weekly trend = 2 points, Daily = 1.5 points, 4H = 1 point
    tf_weights = {'1w': 2.0, '1d': 1.5, '4h': 1.0}
    
    bullish_strength = sum(tf_weights.get(tf, 0) for tf in bullish_tfs)
    bearish_strength = sum(tf_weights.get(tf, 0) for tf in bearish_tfs)
    
    # Determine overall HTF bias
    if bullish_strength > bearish_strength + 0.5:
        htf_bias = 'bullish'
        bias_strength = bullish_strength
    elif bearish_strength > bullish_strength + 0.5:
        htf_bias = 'bearish'
        bias_strength = bearish_strength
    else:
        htf_bias = 'neutral'
        bias_strength = 0.0
    
    # Calculate directional bonus
    bonus = 0.0
    reason_parts = []
    
    # Direction aligns with HTF bias → strong bonus
    if (direction == 'LONG' and htf_bias == 'bullish'):
        # Bonus scales with strength: max +15 for full Weekly+Daily+4H alignment
        bonus = min(15.0, bias_strength * 3.5)
        reason_parts.append(f"HTF structure bullish ({', '.join(bullish_tfs)})")
        reason_parts.append("LONG aligns with HTF trend")
        
    elif (direction == 'SHORT' and htf_bias == 'bearish'):
        bonus = min(15.0, bias_strength * 3.5)
        reason_parts.append(f"HTF structure bearish ({', '.join(bearish_tfs)})")
        reason_parts.append("SHORT aligns with HTF trend")
        
    # Counter-trend setup → penalty (but not blocking)
    elif (direction == 'LONG' and htf_bias == 'bearish'):
        bonus = max(-8.0, -bias_strength * 2.0)
        reason_parts.append(f"HTF structure bearish ({', '.join(bearish_tfs)})")
        reason_parts.append("LONG is counter-trend (caution)")
        
    elif (direction == 'SHORT' and htf_bias == 'bullish'):
        bonus = max(-8.0, -bias_strength * 2.0)
        reason_parts.append(f"HTF structure bullish ({', '.join(bullish_tfs)})")
        reason_parts.append("SHORT is counter-trend (caution)")
    
    else:
        # Neutral HTF - no bonus or penalty
        reason_parts.append("HTF structure neutral/mixed")
    
    return {
        'bonus': bonus,
        'reason': '; '.join(reason_parts) if reason_parts else 'No HTF bias detected',
        'htf_bias': htf_bias,
        'bullish_tfs': bullish_tfs,
        'bearish_tfs': bearish_tfs
    }


# --- Grade Weighting Constants ---
# Pattern grades affect base score: A = 100%, B = 70%, C = 40%
GRADE_WEIGHTS = {'A': 1.0, 'B': 0.7, 'C': 0.4}

def _get_grade_weight(grade: str) -> float:
    """Get weight multiplier for a pattern grade."""
    return GRADE_WEIGHTS.get(grade, 0.7)  # Default to B weight if unknown


def _normalize_direction(direction: str) -> str:
    """Normalize direction format: LONG/SHORT -> bullish/bearish."""
    d = direction.lower()
    if d in ('long', 'bullish'):
        return 'bullish'
    elif d in ('short', 'bearish'):
        return 'bearish'
    return d


# --- SMC Scoring Functions ---

def _score_order_blocks(order_blocks: List[OrderBlock], direction: str) -> float:
    """Score order blocks based on quality, alignment, and grade."""
    if not order_blocks:
        return 0.0
    
    # Normalize direction: LONG/SHORT -> bullish/bearish
    normalized_dir = _normalize_direction(direction)
    # Filter for direction-aligned OBs
    aligned_obs = [ob for ob in order_blocks if ob.direction == normalized_dir]
    
    if not aligned_obs:
        return 0.0
    
    # Find best OB (highest freshness and displacement, lowest mitigation, best grade)
    best_ob = max(aligned_obs, key=lambda ob: (
        ob.freshness_score * 0.3 +
        min(ob.displacement_strength / 3.0, 1.0) * 0.3 +
        (1.0 - ob.mitigation_level) * 0.2 +
        _get_grade_weight(getattr(ob, 'grade', 'B')) * 0.2  # Grade factor
    ))
    
    # Score based on OB quality
    base_score = (
        best_ob.freshness_score * 40 +
        min(best_ob.displacement_strength / 2.0, 1.0) * 40 +
        (1.0 - best_ob.mitigation_level) * 20
    )
    
    # Apply grade weighting to final score
    grade_weight = _get_grade_weight(getattr(best_ob, 'grade', 'B'))
    score = base_score * grade_weight
    
    return min(100.0, score)


def _score_fvgs(fvgs: List[FVG], direction: str) -> float:
    """Score FVGs based on size, unfilled status, and grade."""
    if not fvgs:
        return 0.0
    
    # Normalize direction: LONG/SHORT -> bullish/bearish
    normalized_dir = _normalize_direction(direction)
    aligned_fvgs = [fvg for fvg in fvgs if fvg.direction == normalized_dir]
    
    if not aligned_fvgs:
        return 0.0
    
    # Prefer unfilled FVGs with larger size
    unfilled = [fvg for fvg in aligned_fvgs if fvg.overlap_with_price < 0.5]
    
    if not unfilled:
        # Still give credit for filled FVGs, weighted by grade
        best_filled = max(aligned_fvgs, key=lambda fvg: fvg.size * _get_grade_weight(getattr(fvg, 'grade', 'B')))
        grade_weight = _get_grade_weight(getattr(best_filled, 'grade', 'B'))
        return 30.0 * grade_weight
    
    # Score based on size, unfilled status, and grade
    best_fvg = max(unfilled, key=lambda fvg: (
        fvg.size * (1.0 - fvg.overlap_with_price) * 
        _get_grade_weight(getattr(fvg, 'grade', 'B'))
    ))
    
    base_score = 70 + (1.0 - best_fvg.overlap_with_price) * 30
    
    # Apply grade weighting
    grade_weight = _get_grade_weight(getattr(best_fvg, 'grade', 'B'))
    score = base_score * grade_weight
    
    return min(100.0, score)


def _score_structural_breaks(breaks: List[StructuralBreak], direction: str) -> float:
    """Score structural breaks (BOS/CHoCH) with grade weighting."""
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
    
    # Apply grade weighting
    grade_weight = _get_grade_weight(getattr(latest_break, 'grade', 'B'))
    score = base_score * grade_weight
    
    return min(100.0, score)


def _score_liquidity_sweeps(sweeps: List[LiquiditySweep], direction: str) -> float:
    """Score liquidity sweeps with grade weighting."""
    if not sweeps:
        return 0.0
    
    # Normalize direction: LONG/SHORT -> bullish/bearish
    normalized_dir = _normalize_direction(direction)
    
    # Look for recent sweeps that align with direction
    # Bullish setup benefits from low sweeps, bearish from high sweeps
    target_type = "low" if normalized_dir == "bullish" else "high"
    
    aligned_sweeps = [s for s in sweeps if s.sweep_type == target_type]
    
    if not aligned_sweeps:
        return 0.0
    
    # Get most recent
    latest_sweep = max(aligned_sweeps, key=lambda s: s.timestamp)
    
    # Score based on confirmation
    base_score = 70.0 if latest_sweep.confirmation else 50.0
    
    # Apply grade weighting
    grade_weight = _get_grade_weight(getattr(latest_sweep, 'grade', 'B'))
    score = base_score * grade_weight
    
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
        direction: Trade direction ("bullish"/"bearish" or "LONG"/"SHORT")
        macd_config: Mode-specific MACD configuration (if None, uses legacy scoring)
        htf_indicators: HTF indicators for MACD bias check
        timeframe: Current timeframe string
        
    Returns:
        Tuple of (score, macd_analysis_dict or None)
    """
    score = 40.0  # Base neutral score (was 0.0)
    macd_analysis = None
    
    # Normalize direction: LONG/SHORT -> bullish/bearish
    normalized_dir = _normalize_direction(direction)
    
    if normalized_dir == "bullish":
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
            direction=normalized_dir,
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
            if normalized_dir == "bullish":
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
            if normalized_dir == "bullish" and k > d:
                # Region-sensitive weighting
                if k < 20:
                    score += 25.0  # early oversold bullish cross
                elif k < 50:
                    score += 15.0
                elif k < 80:
                    score += 8.0
                else:
                    score += 5.0  # late/exhaustive
            elif normalized_dir == "bearish" and k < d:
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
    """
    Score volume confirmation with acceleration bonuses.
    
    Scoring logic:
    - Base: 50 (neutral)
    - Volume spike: +30 (base 80)
    - Acceleration aligned with trade direction: +10-20
    - High consecutive increases (3+): +10-15
    - Volume exhaustion in opposite direction: +10 (reversal confirmation)
    - Acceleration against trade direction: -10-15 (momentum opposition)
    
    Args:
        indicators: Technical indicators including volume acceleration
        direction: Trade direction ('LONG', 'SHORT', 'bullish', 'bearish')
        
    Returns:
        Volume score 0-100
    """
    score = 50.0  # Base neutral score
    
    # Volume spike bonus
    if indicators.volume_spike:
        score += 30.0  # 50 -> 80
    
    # Volume acceleration bonuses
    vol_accel = getattr(indicators, 'volume_acceleration', None)
    vol_accel_dir = getattr(indicators, 'volume_accel_direction', None)
    vol_is_accel = getattr(indicators, 'volume_is_accelerating', False)
    vol_consec = getattr(indicators, 'volume_consecutive_increases', 0)
    vol_exhaust = getattr(indicators, 'volume_exhaustion', False)
    
    # Normalize direction for comparison
    is_bullish_trade = direction.lower() in ('long', 'bullish')
    
    if vol_accel is not None and vol_accel_dir is not None:
        # Direction alignment check
        accel_aligns_with_trade = (
            (is_bullish_trade and vol_accel_dir == 'bullish') or
            (not is_bullish_trade and vol_accel_dir == 'bearish')
        )
        accel_opposes_trade = (
            (is_bullish_trade and vol_accel_dir == 'bearish') or
            (not is_bullish_trade and vol_accel_dir == 'bullish')
        )
        
        if vol_is_accel and accel_aligns_with_trade:
            # Strong acceleration in trade direction - momentum confirmation
            if vol_accel > 0.2:
                score += 20.0  # Strong acceleration bonus
            elif vol_accel > 0.1:
                score += 10.0  # Moderate acceleration bonus
        
        elif accel_opposes_trade and vol_is_accel:
            # Acceleration AGAINST our trade direction - momentum opposition
            # This is a warning for continuation trades, but could be GOOD for reversal trades
            # For now, penalize slightly - reversal_detector handles reversal bonuses separately
            if vol_accel > 0.2:
                score -= 15.0  # Strong opposing momentum
            elif vol_accel > 0.1:
                score -= 10.0  # Moderate opposing momentum
    
    # Consecutive increases bonus (volume building up)
    if vol_consec is not None and vol_consec >= 3:
        if vol_consec >= 4:
            score += 15.0  # Strong sustained volume increase
        else:
            score += 10.0  # Moderate volume buildup
    
    # Volume exhaustion bonus (good for reversals)
    # When volume was spiking but now declining - indicates move may be exhausting
    if vol_exhaust:
        # This is most valuable when paired with reversal detection
        # Adds confidence that the prior move is losing steam
        score += 10.0
    
    return max(0.0, min(100.0, score))


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
        # Default to neutral/weak score if data unavailable (prevent "Missing")
        return 40.0

    # Ensure positive
    if atr_pct <= 0:
        return 0.0

    # Convert fraction to percent if given as ratio (heuristic: assume atr_pct already % if > 1.0)
    val = atr_pct

    if val < 0.25:
        return 40.0  # Weak (Caution) instead of Missing/Fail
    if val < 0.75:
        # Map 0.25 -> 40 up to 0.75 -> 100
        return 40.0 + (val - 0.25) / (0.75 - 0.25) * (100.0 - 40.0)
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
    
    # Clamp synergy bonus to max 10 (validation constraint)
    return min(bonus, 10.0)


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
    
    # === HTF ALIGNMENT PENALTY (NEW) ===
    # If HTF is NOT aligned, apply significant penalty (was just a bonus before)
    htf_factor = next((f for f in factors if f.name == "HTF Alignment"), None)
    if htf_factor and htf_factor.score == 0.0:
        # HTF opposing direction - major penalty
        penalty += 15.0
        logger.debug("HTF opposition penalty applied: +15")
    elif htf_factor and htf_factor.score == 50.0:
        # HTF neutral (ranging) - moderate penalty for counter-trend risk
        penalty += 8.0
        logger.debug("HTF neutral penalty applied: +8")
    
    return penalty


def _detect_regime(smc: SMCSnapshot, indicators: IndicatorSet) -> str:
    """Detect current market regime with enhanced choppy detection.
    
    Returns:
        str: 'trend', 'risk_off', 'range', or 'choppy'
    """
    # Get primary timeframe indicators for volatility analysis
    if not indicators.by_timeframe:
        return "range"
    
    primary_tf = list(indicators.by_timeframe.keys())[0]
    primary_ind = indicators.by_timeframe[primary_tf]
    
    # === ENHANCED CHOPPY DETECTION ===
    # Check ATR% for volatility contraction (choppy market sign)
    atr_pct = getattr(primary_ind, 'atr_percent', None)
    rsi = getattr(primary_ind, 'rsi', 50)
    
    # Choppy indicators:
    # 1. Low ATR% (volatility squeeze)
    # 2. RSI in neutral zone (40-60) - no momentum
    # 3. No clear structural breaks
    is_low_volatility = atr_pct is not None and atr_pct < 0.4
    is_neutral_momentum = rsi is not None and 40 <= rsi <= 60
    
    # Check structural breaks
    recent_bos = [b for b in smc.structural_breaks if b.break_type == "BOS"] if smc.structural_breaks else []
    recent_choch = [b for b in smc.structural_breaks if b.break_type == "CHoCH"] if smc.structural_breaks else []
    
    # CHOPPY: Low volatility + neutral RSI + no structure
    if is_low_volatility and is_neutral_momentum and not recent_bos:
        logger.debug("Market regime: CHOPPY (low ATR, neutral RSI, no BOS)")
        return "choppy"
    
    # Check for clear trend via structural breaks
    if smc.structural_breaks:
        latest_break = max(smc.structural_breaks, key=lambda b: b.timestamp)
        
        if latest_break.break_type == "BOS" and latest_break.htf_aligned:
            return "trend"
        elif latest_break.break_type == "CHoCH":
            return "risk_off"  # Reversal suggests risk-off
        elif latest_break.break_type == "BOS":
            return "trend"  # BOS even without HTF alignment is trend-ish
    
    # Range: moderate volatility, no clear structure
    return "range"


# --- Rationale Generators ---

def _get_ob_rationale(order_blocks: List[OrderBlock], direction: str) -> str:
    """Generate rationale for order block factor."""
    aligned = [ob for ob in order_blocks if ob.direction == direction]
    if not aligned:
        return "No aligned order blocks"
    
    best = max(aligned, key=lambda ob: ob.freshness_score)
    grade = getattr(best, 'grade', 'B')
    return f"Fresh {direction} OB [Grade {grade}] with {best.displacement_strength:.1f}x ATR displacement, {best.mitigation_level*100:.0f}% mitigated"


def _get_fvg_rationale(fvgs: List[FVG], direction: str) -> str:
    """Generate rationale for FVG factor."""
    aligned = [fvg for fvg in fvgs if fvg.direction == direction]
    if not aligned:
        return "No aligned FVGs"
    
    unfilled = [fvg for fvg in aligned if fvg.overlap_with_price < 0.5]
    if unfilled:
        grades = [getattr(fvg, 'grade', 'B') for fvg in unfilled]
        grade_summary = f"[Grades: {', '.join(grades)}]" if len(grades) <= 3 else f"[Best: {min(grades)}]"
        return f"{len(unfilled)} unfilled {direction} FVG(s) {grade_summary}"
    else:
        return f"{len(aligned)} {direction} FVG(s), partially filled"


def _get_structure_rationale(breaks: List[StructuralBreak], direction: str) -> str:
    """Generate rationale for structure factor."""
    if not breaks:
        return "No structural breaks detected"
    
    latest = max(breaks, key=lambda b: b.timestamp)
    htf_status = "HTF aligned" if latest.htf_aligned else "LTF only"
    grade = getattr(latest, 'grade', 'B')
    return f"Recent {latest.break_type} [Grade {grade}] ({htf_status})"


def _get_sweep_rationale(sweeps: List[LiquiditySweep], direction: str) -> str:
    """Generate rationale for liquidity sweep factor."""
    target_type = "low" if direction == "bullish" else "high"
    aligned = [s for s in sweeps if s.sweep_type == target_type]
    
    if not aligned:
        return "No relevant liquidity sweeps"
    
    latest = max(aligned, key=lambda s: s.timestamp)
    conf_status = "volume confirmed" if latest.confirmation else "no volume confirmation"
    grade = getattr(latest, 'grade', 'B')
    return f"Recent {target_type} sweep [Grade {grade}] ({conf_status})"


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
