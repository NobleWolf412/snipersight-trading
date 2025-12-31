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
from backend.strategy.smc.sessions import is_kill_zone_active, get_current_kill_zone
from backend.analysis.macro_context import MacroContext, compute_macro_score

# Conditional imports for type hints
if TYPE_CHECKING:
    from backend.shared.models.smc import CycleContext, ReversalContext
    from backend.shared.models.regime import SymbolRegime

logger = logging.getLogger(__name__)


# ==============================================================================
# MODE-SPECIFIC FACTOR WEIGHTS
# ==============================================================================
# Tunes the scoring engine to prioritize factors relevant to each trading style.
#
# OVERWATCH (Swing): Prioritizes HTF alignment, structure, and institutional accumulation.
# STRIKE (Intraday): Prioritizes Momentum, Flow, and Volatility.
# SURGICAL (Scalp): Prioritizes Structure, Precision Timing (Kill Zones), and specific OBs.
# STEALTH (Balanced): Balanced approach across all factors.

MODE_FACTOR_WEIGHTS = {
    'macro_surveillance': {  # OVERWATCH
        'order_block': 0.25,
        'fvg': 0.18,
        'market_structure': 0.20,
        'liquidity_sweep': 0.18,
        'kill_zone': 0.03,
        'momentum': 0.08,
        'volume': 0.10,
        'volatility': 0.08,
        'htf_alignment': 0.25,
        'htf_proximity': 0.15,
        'btc_impulse': 0.12,
        'weekly_stoch_rsi': 0.12,
        'htf_structure_bias': 0.15,
        'premium_discount': 0.12,
        'inside_ob': 0.10,
        'nested_ob': 0.10,
        'opposing_structure': 0.06,
        'htf_inflection': 0.18,
        'multi_tf_reversal': 0.12,
        'ltf_structure_shift': 0.05,
        'institutional_sequence': 0.15,
        'timeframe_conflict': 0.10,
        'macd_veto': 0.05
    },
    'intraday_aggressive': {  # STRIKE
        'order_block': 0.18,
        'fvg': 0.12,
        'market_structure': 0.28,
        'liquidity_sweep': 0.12,
        'kill_zone': 0.08,
        'momentum': 0.15,
        'volume': 0.10,
        'volatility': 0.10,
        'htf_alignment': 0.12,
        'htf_proximity': 0.10,
        'btc_impulse': 0.08,
        'weekly_stoch_rsi': 0.06,
        'htf_structure_bias': 0.10,
        'premium_discount': 0.06,
        'inside_ob': 0.10,
        'nested_ob': 0.08,
        'opposing_structure': 0.10,
        'htf_inflection': 0.10,
        'multi_tf_reversal': 0.12,
        'ltf_structure_shift': 0.10,
        'institutional_sequence': 0.12,
        'timeframe_conflict': 0.12,
        'macd_veto': 0.05
    },
    'precision': {  # SURGICAL
        'order_block': 0.15,
        'fvg': 0.10,
        'market_structure': 0.30,
        'liquidity_sweep': 0.10,
        'kill_zone': 0.10,
        'momentum': 0.12,
        'volume': 0.08,
        'volatility': 0.12,
        'htf_alignment': 0.10,
        'htf_proximity': 0.08,
        'btc_impulse': 0.05,
        'weekly_stoch_rsi': 0.05,
        'htf_structure_bias': 0.08,
        'premium_discount': 0.05,
        'inside_ob': 0.10,
        'nested_ob': 0.05,
        'opposing_structure': 0.12,
        'htf_inflection': 0.08,
        'multi_tf_reversal': 0.10,
        'ltf_structure_shift': 0.12,
        'institutional_sequence': 0.10,
        'timeframe_conflict': 0.15,
        'macd_veto': 0.05
    },
    'stealth_balanced': {  # STEALTH
        'order_block': 0.20,
        'fvg': 0.15,
        'market_structure': 0.25,
        'liquidity_sweep': 0.15,
        'kill_zone': 0.05,
        'momentum': 0.10,
        'volume': 0.10,
        'volatility': 0.08,
        'htf_alignment': 0.18,
        'htf_proximity': 0.12,
        'btc_impulse': 0.10,
        'weekly_stoch_rsi': 0.10,
        'htf_structure_bias': 0.12,
        'premium_discount': 0.08,
        'inside_ob': 0.10,
        'nested_ob': 0.08,
        'opposing_structure': 0.08,
        'htf_inflection': 0.12,
        'multi_tf_reversal': 0.12,
        'ltf_structure_shift': 0.08,
        'institutional_sequence': 0.12,
        'timeframe_conflict': 0.10,
        'macd_veto': 0.05
    },
    # Surgical alias
    'surgical': {  # Maps to precision
        'order_block': 0.15,
        'fvg': 0.10,
        'market_structure': 0.30,
        'liquidity_sweep': 0.10,
        'kill_zone': 0.10,
        'momentum': 0.12,
        'volume': 0.08,
        'volatility': 0.12,
        'htf_alignment': 0.10,
        'htf_proximity': 0.08,
        'btc_impulse': 0.05,
        'weekly_stoch_rsi': 0.05,
        'htf_structure_bias': 0.08,
        'premium_discount': 0.05,
        'inside_ob': 0.10,
        'nested_ob': 0.05,
        'opposing_structure': 0.12,
        'htf_inflection': 0.08,
        'multi_tf_reversal': 0.10,
        'ltf_structure_shift': 0.12,
        'institutional_sequence': 0.10,
        'timeframe_conflict': 0.15,
        'macd_veto': 0.05
    },
    # Overwatch alias
    'overwatch': {  # Maps to macro_surveillance
        'order_block': 0.25,
        'fvg': 0.18,
        'market_structure': 0.20,
        'liquidity_sweep': 0.18,
        'kill_zone': 0.03,
        'momentum': 0.08,
        'volume': 0.10,
        'volatility': 0.08,
        'htf_alignment': 0.25,
        'htf_proximity': 0.15,
        'btc_impulse': 0.12,
        'weekly_stoch_rsi': 0.12,
        'htf_structure_bias': 0.15,
        'premium_discount': 0.12,
        'inside_ob': 0.10,
        'nested_ob': 0.10,
        'opposing_structure': 0.06,
        'htf_inflection': 0.18,
        'multi_tf_reversal': 0.12,
        'ltf_structure_shift': 0.05,
        'institutional_sequence': 0.15,
        'timeframe_conflict': 0.10,
        'macd_veto': 0.05
    },
    # Strike alias
    'strike': {  # Maps to intraday_aggressive
        'order_block': 0.18,
        'fvg': 0.12,
        'market_structure': 0.28,
        'liquidity_sweep': 0.12,
        'kill_zone': 0.08,
        'momentum': 0.15,
        'volume': 0.10,
        'volatility': 0.10,
        'htf_alignment': 0.12,
        'htf_proximity': 0.10,
        'btc_impulse': 0.08,
        'weekly_stoch_rsi': 0.06,
        'htf_structure_bias': 0.10,
        'premium_discount': 0.06,
        'inside_ob': 0.10,
        'nested_ob': 0.08,
        'opposing_structure': 0.10,
        'htf_inflection': 0.10,
        'multi_tf_reversal': 0.12,
        'ltf_structure_shift': 0.10,
        'institutional_sequence': 0.12,
        'timeframe_conflict': 0.12,
        'macd_veto': 0.05
    }
}


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
    # FIXED: Allow per-mode configuration instead of hardcoded 5 ATR
    max_distance_atr = getattr(mode_config, 'htf_proximity_atr', 5.0)
    
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

    # 3. Check Pre-Calculated HTF Levels (HTFLevelDetector) - PRIORITY
    # These are high-quality clustering results
    if hasattr(smc, 'htf_levels') and smc.htf_levels:
        for level in smc.htf_levels:
            if not hasattr(level, 'price') or not hasattr(level, 'level_type'):
                continue
            
            # Filter by timeframe
            if level.timeframe not in structure_tfs:
                continue
                
            distance = abs(entry_price - level.price)
            distance_atr = distance / atr
            
            if distance_atr < min_distance:
                min_distance = distance_atr
                nearest_structure = f"{level.timeframe} {level.level_type.title()} @ {level.price:.5f}"
                structure_type = "HTF_Level"
    
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
    swing_structure: Optional[Dict] = None,
    reversal_context: Optional[dict] = None  # Kept for API compatibility
) -> Dict:
    """
    UNIVERSAL MOMENTUM GATE (FINAL).
    
    A unified gate that handles Scalp, Intraday, and Swing logic correctly.
    
    Improvements over basic version:
    1. "Elastic" Timeframes: Checks the *driver* timeframe (e.g. 15m -> 4H), not just the macro.
    2. Mode-Aware Risk: 
       - Surgical/Strike: Allows fading standard extensions (RSI 70+).
       - Overwatch: Requires EXTREME extensions (RSI 80+) to fade.
    3. Climax Logic: Distinguishes between "Strong Trend" (Block Fades) and "Parabolic" (Allow Fades).
    """
    
    # 1. MODE IDENTIFICATION & SETTINGS
    profile = getattr(mode_config, 'profile', 'balanced')
    mode_name = getattr(mode_config, 'name', 'stealth').lower()
    
    # Defaults
    momentum_tf = '4h'
    fade_threshold_rsi = 75.0  # Standard extension
    
    # Configure per Mode
    if mode_name == 'overwatch' or profile == 'macro_surveillance':
        # SWING: Look at Daily. Hard to turn. Needs extreme evidence.
        momentum_tf = '1d'
        fade_threshold_rsi = 80.0  # RSI > 80 required to fade
    
    elif mode_name == 'stealth' or profile == 'stealth_balanced':
        # BALANCED: Look at 4H.
        momentum_tf = '4h'
        fade_threshold_rsi = 75.0
        
    elif mode_name in ['surgical', 'strike'] or profile in ('precision', 'intraday_aggressive'):
        # SCALP: Look at 1H/4H. Quick turns allowed.
        momentum_tf = '1h'
        fade_threshold_rsi = 70.0  # RSI > 70 is enough for a scalp fade
        
    # 2. GET DATA
    # Elastic fallback if specific TF is missing
    if momentum_tf not in indicators.by_timeframe:
        available = sorted(
            list(indicators.by_timeframe.keys()), 
            key=lambda x: {'1m': 1, '5m': 5, '15m': 15, '1h': 60, '4h': 240, '1d': 1440, '1w': 10080}.get(x, 0)
        )
        momentum_tf = available[-1] if available else None

    ind = indicators.by_timeframe.get(momentum_tf)
    if not ind:
        return {
            'allowed': True, 
            'score_adjustment': 0.0, 
            'htf_momentum': 'unknown',
            'htf_trend': 'unknown',
            'reason': 'No indicator data available'
        }

    # 3. ANALYZE MOMENTUM
    adx = getattr(ind, 'adx', None)
    rsi = getattr(ind, 'rsi', 50.0)
    
    # Determine Trend Strength (0-100)
    momentum_state = "neutral"
    
    if adx is not None:
        if adx > 50: 
            momentum_state = "extreme"
        elif adx > 30: 
            momentum_state = "strong"
        elif adx > 20: 
            momentum_state = "building"
        else: 
            momentum_state = "weak"
    else:
        # Fallback to ATR Slope
        atr_series = getattr(ind, 'atr_series', [])
        if len(atr_series) >= 5:
            slope = (atr_series[-1] - atr_series[0]) / atr_series[0] if atr_series[0] > 0 else 0
            if slope > 0.10: 
                momentum_state = "strong"
            elif slope > 0.02: 
                momentum_state = "building"
            
    # 4. ALIGNMENT CHECK
    htf_trend_dir = "neutral"
    if swing_structure and momentum_tf in swing_structure:
        htf_trend_dir = swing_structure[momentum_tf].get('trend', 'neutral')
    # Also check uppercase version for compatibility
    if htf_trend_dir == "neutral" and swing_structure and momentum_tf.upper() in swing_structure:
        htf_trend_dir = swing_structure[momentum_tf.upper()].get('trend', 'neutral')

    is_long = direction.lower() in ('bullish', 'long')
    
    # Define alignment
    is_aligned = (is_long and htf_trend_dir == 'bullish') or (not is_long and htf_trend_dir == 'bearish')
    is_opposed = (is_long and htf_trend_dir == 'bearish') or (not is_long and htf_trend_dir == 'bullish')

    # === LOGIC BRANCHES ===

    # A. TREND FOLLOWING (Aligned)
    if is_aligned:
        # Overwatch/Trend modes love strong momentum
        if momentum_state in ['strong', 'extreme']:
            bonus = 20.0 if mode_name == 'overwatch' else 15.0
            return {
                'allowed': True,
                'score_adjustment': bonus,
                'htf_momentum': momentum_state,
                'htf_trend': htf_trend_dir,
                'reason': f"Perfect alignment with strong {momentum_tf} momentum"
            }
        elif momentum_state == 'building':
            return {
                'allowed': True,
                'score_adjustment': 10.0,
                'htf_momentum': momentum_state,
                'htf_trend': htf_trend_dir,
                'reason': f"{momentum_tf} momentum building in direction"
            }
        else:
            return {
                'allowed': True, 
                'score_adjustment': 0.0, 
                'htf_momentum': momentum_state, 
                'htf_trend': htf_trend_dir,
                'reason': f"Aligned with {htf_trend_dir} {momentum_tf} trend"
            }

    # B. COUNTER-TREND (Opposed)
    if is_opposed:
        # 1. Check for CLIMAX (The only valid reason to fade a strong trend)
        is_climax = False
        current_rsi = rsi if rsi else 50.0
        
        if is_long:  # Trying to catch a bottom
            # Oversold condition
            threshold = 100.0 - fade_threshold_rsi  # e.g., 30 or 20
            if current_rsi < threshold:
                is_climax = True
        else:  # Trying to catch a top
            # Overbought condition
            if current_rsi > fade_threshold_rsi:
                is_climax = True
        
        # 2. Decision Time
        if is_climax:
            # ALLOW the fade, specifically because it's overextended
            # Bonus usually higher for Scalp modes (they thrive on this)
            climax_bonus = 10.0 if mode_name in ['surgical', 'strike'] else 5.0
            
            return {
                'allowed': True,
                'score_adjustment': climax_bonus,
                'htf_momentum': momentum_state,
                'htf_trend': htf_trend_dir,
                'reason': f"CLIMAX DETECTED: {momentum_tf} RSI {current_rsi:.1f} allows counter-trend fade"
            }
            
        elif momentum_state in ['strong', 'extreme', 'building']:
            # BLOCK the fade. Trend is strong and NOT overextended.
            # This is the "Suicide Prevention" block.
            penalty = -100.0 if mode_name == 'overwatch' else -40.0
            
            return {
                'allowed': False,
                'score_adjustment': penalty,
                'htf_momentum': momentum_state,
                'htf_trend': htf_trend_dir,
                'reason': f"BLOCKED: Fighting strong {momentum_tf} trend without climax (RSI {current_rsi:.1f})"
            }
            
        else:
            # Trend is weak/neutral. Counter-trading allowed but risky.
            return {
                'allowed': True,
                'score_adjustment': -5.0,  # Small penalty for counter-trend
                'htf_momentum': momentum_state,
                'htf_trend': htf_trend_dir,
                'reason': f"Counter-trend allowed (weak {momentum_tf} momentum)"
            }

    # C. NEUTRAL/CHOP
    return {
        'allowed': True,
        'score_adjustment': 0.0,
        'htf_momentum': momentum_state,
        'htf_trend': htf_trend_dir,
        'reason': f"{momentum_tf} context neutral"
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
    
    # Check alignment with tiered scoring
    if primary_trend == 'neutral':
        # Ranging/no data - slight caution, not full conflict
        score_adjustment -= 5.0
        resolution_reason_parts.append(f"Primary TF ({primary_tf}) neutral/ranging")
        resolution = 'caution'
    elif (is_bullish_trade and primary_trend == 'bearish') or \
         (not is_bullish_trade and primary_trend == 'bullish'):
        # Actual conflict - larger penalty
        conflicts.append(f"{primary_tf} {primary_trend} (primary)")
        resolution_reason_parts.append(f"Primary TF ({primary_tf}) {primary_trend} conflicts with {direction}")
        score_adjustment -= 10.0
        resolution = 'caution'
    # else: aligned - no penalty
    
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
        # Check for positive alignment to award bonus
        # If primary is aligned and at least one HTF is aligned (and none conflict)
        is_primary_aligned = (is_bullish_trade and primary_trend == 'bullish') or \
                             (not is_bullish_trade and primary_trend == 'bearish')
        
        has_htf_alignment = False
        for tf in filter_tfs:
            htf_trend = tf_trends.get(tf, 'neutral')
            if (is_bullish_trade and htf_trend == 'bullish') or \
               (not is_bullish_trade and htf_trend == 'bearish'):
                has_htf_alignment = True
                break
        
        if is_primary_aligned:
            score_adjustment += 25.0
            if has_htf_alignment:
                score_adjustment += 25.0  # Total +50 (Score 100)
                resolution_reason_parts.append("Perfect multi-timeframe alignment")
            else:
                resolution_reason_parts.append("Primary timeframe aligned")
        else:
            resolution_reason_parts.append("No conflicts (neutral alignment)")
    
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


def _score_regime_alignment(
    regime,  # SymbolRegime
    direction: str,
    max_bonus: float = 15.0,
    max_penalty: float = 12.0
) -> Dict:
    """
    Calculate regime alignment bonus/penalty for confluence scoring.
    
    Rewards trades aligned with the symbol's local regime (trend + volatility).
    Penalizes trades that fight the regime.
    
    Logic:
    - ALIGNED (strong_up/up + long OR strong_down/down + short): +Bonus scaled by regime.score
    - OPPOSED (strong_up/up + short OR strong_down/down + long): -Penalty scaled by regime.score  
    - SIDEWAYS/NEUTRAL: Small penalty for lack of directional edge
    
    Args:
        regime: SymbolRegime from RegimeDetector (trend, volatility, score)
        direction: Trade direction ("bullish"/"bearish" or "long"/"short")
        max_bonus: Maximum bonus for perfect alignment (default 15)
        max_penalty: Maximum penalty for opposing strong regime (default 12)
        
    Returns:
        Dict with:
            - adjustment: float - score adjustment (positive=bonus, negative=penalty)
            - aligned: bool - whether direction aligns with regime
            - reason: str - explanation
            - factor_score: float - 0-100 scaled score for ConfluenceFactor
    """
    result = {
        "adjustment": 0.0,
        "aligned": True,
        "reason": "No regime data available",
        "factor_score": 50.0  # Neutral
    }
    
    if regime is None:
        return result
    
    trend = getattr(regime, 'trend', 'sideways')
    regime_score = getattr(regime, 'score', 50.0)
    volatility = getattr(regime, 'volatility', 'normal')
    
    # Normalize direction
    is_long = direction.lower() in ('bullish', 'long')
    
    # Score multiplier based on regime confidence (0-100 score -> 0.5-1.0 multiplier)
    confidence_mult = 0.5 + (regime_score / 200.0)  # 50 -> 0.75, 100 -> 1.0
    
    # Alignment logic
    bullish_trends = ('strong_up', 'up')
    bearish_trends = ('strong_down', 'down')
    
    if trend in bullish_trends:
        if is_long:
            # Aligned with bullish regime
            is_strong = trend == 'strong_up'
            base_bonus = max_bonus if is_strong else max_bonus * 0.7
            result["adjustment"] = base_bonus * confidence_mult
            result["aligned"] = True
            result["reason"] = f"LONG aligned with {trend} regime (score={regime_score:.0f})"
            result["factor_score"] = min(100.0, 50.0 + result["adjustment"] * 3.33)
        else:
            # Shorting into bullish regime
            is_strong = trend == 'strong_up'
            base_penalty = max_penalty if is_strong else max_penalty * 0.7
            result["adjustment"] = -base_penalty * confidence_mult
            result["aligned"] = False
            result["reason"] = f"SHORT opposes {trend} regime (score={regime_score:.0f})"
            result["factor_score"] = max(0.0, 50.0 + result["adjustment"] * 5.0)
            
    elif trend in bearish_trends:
        if not is_long:
            # Aligned with bearish regime
            is_strong = trend == 'strong_down'
            base_bonus = max_bonus if is_strong else max_bonus * 0.7
            result["adjustment"] = base_bonus * confidence_mult
            result["aligned"] = True
            result["reason"] = f"SHORT aligned with {trend} regime (score={regime_score:.0f})"
            result["factor_score"] = min(100.0, 50.0 + result["adjustment"] * 3.33)
        else:
            # Longing into bearish regime
            is_strong = trend == 'strong_down'
            base_penalty = max_penalty if is_strong else max_penalty * 0.7
            result["adjustment"] = -base_penalty * confidence_mult
            result["aligned"] = False
            result["reason"] = f"LONG opposes {trend} regime (score={regime_score:.0f})"
            result["factor_score"] = max(0.0, 50.0 + result["adjustment"] * 5.0)
            
    else:  # sideways
        # Ranging market - small penalty for either direction unless volatility suggests opportunity
        if volatility == 'compressed':
            # Compressed volatility in range = good for breakout anticipation (neutral)
            result["adjustment"] = 0.0
            result["aligned"] = True
            result["reason"] = f"Sideways regime with {volatility} volatility (breakout potential)"
            result["factor_score"] = 50.0
        else:
            # Normal/elevated volatility in range = penalize (chop)
            result["adjustment"] = -3.0
            result["aligned"] = True  # Not opposing, just unclear
            result["reason"] = f"Sideways regime - no directional edge"
            result["factor_score"] = 40.0
    
    return result


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
    current_price: Optional[float] = None,
    # Macro context injection
    macro_context: Optional[MacroContext] = None,
    is_btc: bool = False,
    is_alt: bool = True,
    # Symbol-specific regime from RegimeDetector
    regime: Optional["SymbolRegime"] = None
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
        macro_context: Global macro/dominance context (Macro Overlay)
        is_btc: Whether symbol is Bitcoin
        is_alt: Whether symbol is an Altcoin
        
    Returns:
        ConfluenceBreakdown: Complete scoring breakdown with factors
    """
    factors = []
    primary_tf = None
    macd_analysis = None
    
    # Normalize direction at entry: LONG/SHORT -> bullish/bearish
    # This ensures consistent format throughout all scoring functions
    direction = _normalize_direction(direction)
    current_profile = getattr(config, 'profile', 'balanced').lower()

    # Helper to get dynamic weights
    def get_w(key: str, default: float) -> float:
        return MODE_FACTOR_WEIGHTS.get(current_profile, {}).get(key, default)
    
    # --- SMC Pattern Scoring ---
    
    # Order Blocks
    ob_score = _score_order_blocks(smc_snapshot.order_blocks, direction)
    if ob_score > 0:
        factors.append(ConfluenceFactor(
            name="Order Block",
            score=ob_score,
            weight=get_w('order_block', 0.20),
            rationale=_get_ob_rationale(smc_snapshot.order_blocks, direction)
        ))
    
    # Fair Value Gaps
    fvg_score = _score_fvgs(smc_snapshot.fvgs, direction)
    if fvg_score > 0:
        factors.append(ConfluenceFactor(
            name="Fair Value Gap",
            score=fvg_score,
            weight=get_w('fvg', 0.15),
            rationale=_get_fvg_rationale(smc_snapshot.fvgs, direction)
        ))
    
    # Structural Breaks
    structure_score = _score_structural_breaks(smc_snapshot.structural_breaks, direction)
    if structure_score > 0:
        factors.append(ConfluenceFactor(
            name="Market Structure",
            score=structure_score,
            weight=get_w('market_structure', 0.25),
            rationale=_get_structure_rationale(smc_snapshot.structural_breaks, direction)
        ))
    
    # Liquidity Sweeps
    sweep_score = _score_liquidity_sweeps(smc_snapshot.liquidity_sweeps, direction)
    if sweep_score > 0:
        factors.append(ConfluenceFactor(
            name="Liquidity Sweep",
            score=sweep_score,
            weight=get_w('liquidity_sweep', 0.15),
            rationale=_get_sweep_rationale(smc_snapshot.liquidity_sweeps, direction)
        ))
    
    # --- MODE-AWARE STRUCTURAL MINIMUM GATE ---
    # Swing modes (overwatch, stealth, macro_surveillance) require at least ONE
    # structural element (OB, FVG, or sweep) to generate a valid signal.
    # This prevents pure HTF alignment setups with no valid entry structure.
    # Scalp/precision modes are exempt - they can trade isolated setups.
    
    SWING_PROFILES = ('macro_surveillance', 'stealth_balanced', 'overwatch', 'swing')
    is_swing_mode = current_profile in SWING_PROFILES
    
    has_structural_element = (ob_score > 0 or fvg_score > 0 or sweep_score > 0)
    
    if is_swing_mode and not has_structural_element:
        # Apply severe penalty instead of hard rejection (still shows in scan with explanation)
        logger.info("⚠️ STRUCTURAL MINIMUM: %s mode requires OB/FVG/Sweep but none found (%s direction)",
                   current_profile, direction)
        factors.append(ConfluenceFactor(
            name="Structural Minimum",
            score=0.0,  # Zero score
            weight=0.30,  # High weight penalty
            rationale=f"Swing mode requires OB, FVG, or Sweep - none detected for {direction}"
        ))
    
    # Kill Zone Timing (high-probability institutional windows)
    try:
        from datetime import datetime
        now = datetime.now()
        kill_zone = get_current_kill_zone(now)
        if kill_zone:
            # Normalize kill zone name for display
            kz_display = kill_zone.value.replace('_', ' ').title()
            factors.append(ConfluenceFactor(
                name="Kill Zone Timing",
                score=60.0,  # Moderate score (not make-or-break)
                weight=get_w('kill_zone', 0.05),
                rationale=f"In {kz_display} kill zone - high institutional activity"
            ))
            logger.debug("⏰ Kill zone active: %s", kz_display)
    except Exception as e:
        logger.debug("Kill zone check failed: %s", e)
    
    # --- Indicator Scoring ---
    
    # Select primary timeframe (Anchor Chart) for indicator scoring based on mode
    # 1. Try mode-specific planning timeframe (e.g. Strike=15m, Overwatch=4h)
    if config and getattr(config, 'primary_planning_timeframe', None):
        cfg_tf = config.primary_planning_timeframe
        if indicators.has_timeframe(cfg_tf):
            primary_tf = cfg_tf
            # logger.debug(f"Using mode-specific primary timeframe: {primary_tf}")
            
    # 2. Fallback: Try standard anchors if mode TF missing
    if not primary_tf:
        for tf_candidate in ['1h', '15m', '4h', '1d']:
            if indicators.has_timeframe(tf_candidate):
                primary_tf = tf_candidate
                break
                
    # 3. Final Fallback: First available
    if not primary_tf and indicators.by_timeframe:
        primary_tf = list(indicators.by_timeframe.keys())[0]

    # --- PRICE INITIALIZATION (For proximity/alignment checks) ---
    entry_price = current_price
    if not entry_price and primary_tf:
        # Try to get from indicators
        prim_ind = indicators.by_timeframe.get(primary_tf)
        if prim_ind and hasattr(prim_ind, 'dataframe') and prim_ind.dataframe is not None:
            if len(prim_ind.dataframe) > 0:
                 entry_price = float(prim_ind.dataframe['close'].iloc[-1])
            else:
                 entry_price = None
    
    # Get MACD mode config based on profile
    profile = getattr(config, 'profile', 'balanced')
    macd_config = get_macd_config(profile)
    
    # Get HTF indicators for MACD bias (if available)
    htf_tf = macd_config.htf_timeframe
    htf_indicators = indicators.by_timeframe.get(htf_tf) if indicators.by_timeframe else None
    
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
                weight=get_w('momentum', 0.10),
                rationale=momentum_rationale
            ))
        
        # Volume confirmation
        volume_score = _score_volume(primary_indicators, direction)
        if volume_score > 0:
            factors.append(ConfluenceFactor(
                name="Volume",
                score=volume_score,
                weight=get_w('volume', 0.10),
                rationale=_get_volume_rationale(primary_indicators)
            ))
            
        # VWAP Alignment
        vwap = getattr(primary_indicators, 'vwap', None)
        if vwap and entry_price:
            vwap_score = 0.0
            vwap_rationale = ""
            if direction in ('bullish', 'long'):
                if entry_price < vwap:
                    vwap_score = 60.0 # Good entry
                    vwap_rationale = f"Price ({entry_price:.2f}) below VWAP ({vwap:.2f}) - value entry"
                elif entry_price < vwap * 1.01:
                    vwap_score = 50.0 # Neutral
            else: # bearish
                if entry_price > vwap:
                    vwap_score = 60.0
                    vwap_rationale = f"Price ({entry_price:.2f}) above VWAP ({vwap:.2f}) - premium entry"
                elif entry_price > vwap * 0.99:
                    vwap_score = 50.0

            if vwap_score > 50.0:
                 factors.append(ConfluenceFactor(
                    name="VWAP Alignment",
                    score=min(100.0, 50.0 + (vwap_score-50.0)*3.0), # Scale 60->80
                    weight=0.05, # Small weight
                    rationale=vwap_rationale
                ))

        # Volatility normalization (ATR%) - prefer moderate volatility
        volatility_score = _score_volatility(primary_indicators)
        if volatility_score > 0:
            factors.append(ConfluenceFactor(
                name="Volatility",
                score=volatility_score,
                weight=get_w('volatility', 0.08),
                rationale=_get_volatility_rationale(primary_indicators)
            ))

        # MTF Indicator Confluence (New)
        mtf_score, mtf_rationale = _score_mtf_indicator_confluence(indicators, direction)
        if mtf_score != 0:
            # Base 50 +/- bonus. Bonus is 15 -> 15*3.33 = 50. Total 100.
            # Penalty is -10 -> -10*3.33 = -33. Total 17.
            mtf_final_score = 50.0 + (mtf_score * 3.33)
            factors.append(ConfluenceFactor(
                name="MTF Indicator Alignment",
                score=min(100.0, max(0.0, mtf_final_score)),
                weight=get_w('multi_tf_reversal', 0.10),
                rationale=mtf_rationale
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
            weight=get_w('macd_veto', 0.05),
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
                weight=get_w('htf_alignment', 0.20),
                rationale=f"Higher timeframe trend is {htf_trend}, aligns with {direction} setup"
            ))
    
    # --- HTF Level Proximity (Redundant - handled by Gate 1 below) ---
    # Legacy block removed to prefer evaluate_htf_structural_proximity output
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
                weight=get_w('btc_impulse', 0.10),
                rationale=f"BTC trend ({btc_impulse}) conflicts with setup direction ({direction})"
            ))
        else:
            btc_impulse_gate = True
            factors.append(ConfluenceFactor(
                name="BTC Impulse Gate",
                score=100.0,
                weight=get_w('btc_impulse', 0.10),
                rationale=f"BTC trend ({btc_impulse}) supports {direction} setup"
            ))
    
    # --- Weekly StochRSI Bonus ---
    # Directional bonus/penalty system based on weekly momentum
    # Replaces the old hard gate - no longer blocks, just influences score
    # SKIP for LTF-only modes (surgical, precision) - weekly momentum is too slow for scalps
    weekly_stoch_rsi_bonus = 0.0
    weekly_stoch_rsi_analysis = None
    
    # Check if this mode should skip Weekly StochRSI
    skip_weekly_stoch = current_profile in ('precision', 'surgical')
    
    if not skip_weekly_stoch and getattr(config, 'weekly_stoch_rsi_gate_enabled', True):
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
                weight=get_w('weekly_stoch_rsi', 0.10),
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
                weight=get_w('weekly_stoch_rsi', 0.10),
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
                    weight=get_w('htf_structure_bias', 0.12),
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
                        weight=get_w('htf_structure_bias', 0.12),
                        rationale=f"[+{pullback_bonus:.1f}] {pullback_rationale}"
                    ))
                    logger.debug("🔄 HTF Pullback BONUS +%.1f: %s", pullback_bonus, pullback_rationale)
                else:
                    # No pullback override → apply counter-trend penalty as usual
                    factor_score = max(0.0, 50.0 + htf_structure_bonus * 5.0)
                    factors.append(ConfluenceFactor(
                        name="HTF Structure Bias",
                        score=factor_score,
                        weight=get_w('htf_structure_bias', 0.12),
                        rationale=f"[{htf_structure_bonus:.1f}] {htf_structure_analysis['reason']}"
                    ))
                    logger.debug("⚠️ HTF Structure PENALTY %.1f: %s", htf_structure_bonus, htf_structure_analysis['reason'])
    
    # ===========================================================================
    # === CRITICAL HTF GATES (New: filters low-quality signals) ===
    # ===========================================================================
    
    # === Gate 1: HTF STRUCTURAL PROXIMITY GATE ===
    # Entry must be at meaningful HTF structural level
    # SKIP for LTF-only modes (surgical, precision) that don't scan HTF timeframes
    htf_proximity_result = None
    profile = getattr(config, 'profile', 'balanced')
    is_ltf_only_mode = profile in ('precision', 'surgical') or (
        hasattr(config, 'timeframes') and 
        not any(tf.lower() in ('4h', '1d', '1w') for tf in getattr(config, 'timeframes', ()))
    )
    
    if getattr(config, 'enable_htf_structural_gate', True) and entry_price and not is_ltf_only_mode:
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
                weight=get_w('htf_proximity', 0.15),
                rationale=f"{htf_proximity_result['nearest_structure']} ({htf_proximity_result.get('proximity_atr', 'N/A'):.1f} ATR)" if htf_proximity_result.get('proximity_atr') else htf_proximity_result['nearest_structure']
            ))
            
            if not htf_proximity_result['valid']:
                logger.warning("🚫 HTF Structural Gate FAILED: entry %.1f ATR from nearest structure", 
                             htf_proximity_result.get('proximity_atr', 999))
    elif is_ltf_only_mode:
        # For LTF modes, give neutral score - don't penalize missing HTF
        logger.debug("⏭️ HTF Structural Gate SKIPPED for %s mode (LTF-only)", profile)

    
    # === Gate 2: HTF MOMENTUM GATE ===
    # Block counter-trend trades during strong HTF momentum
    # SKIP for LTF-only modes (surgical, precision) that don't scan HTF timeframes
    if getattr(config, 'enable_htf_momentum_gate', True) and not is_ltf_only_mode:
        momentum_gate = evaluate_htf_momentum_gate(
            indicators=indicators,
            direction=direction,
            mode_config=config,
            swing_structure=smc_snapshot.swing_structure,
            reversal_context=reversal_context
        )
        
        if momentum_gate['score_adjustment'] != 0:
            factor_score = max(0.0, min(100.0, 50.0 + momentum_gate['score_adjustment'] * 1.0))
            factors.append(ConfluenceFactor(
                name="HTF_Momentum_Gate",
                score=factor_score,
                weight=get_w('htf_alignment', 0.12),
                rationale=momentum_gate['reason']
            ))
            
            if not momentum_gate['allowed']:
                logger.warning("🚫 HTF Momentum Gate BLOCKED: %s trend with %s momentum",
                             momentum_gate['htf_trend'], momentum_gate['htf_momentum'])
    elif is_ltf_only_mode:
        logger.debug("⏭️ HTF Momentum Gate SKIPPED for %s mode (LTF-only)", profile)

    
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
                weight=get_w('timeframe_conflict', 0.10),
                rationale=conflict_result['resolution_reason']
            ))
            
            if conflict_result['resolution'] == 'blocked':
                logger.warning("🚫 Timeframe Conflict BLOCKED: conflicts: %s",
                             ', '.join(conflict_result['conflicts']))
    
    # --- NEW: Premium/Discount Zone Scoring ---
    # Bonus for trading in the optimal zone for direction
    try:
        if current_price is not None and smc_snapshot.premium_discount_zones:
            # Get the zone from the primary planning timeframe
            primary_tf = getattr(config, 'primary_planning_timeframe', '4h')
            pd_zone = smc_snapshot.premium_discount_zones.get(primary_tf) or smc_snapshot.premium_discount_zones.get(primary_tf.upper())
            
            if pd_zone:
                current_zone = pd_zone.get('current_zone', 'neutral')
                zone_pct = pd_zone.get('zone_percentage', 50)
                
                pd_score = 50.0  # Neutral baseline
                pd_rationale = "Price at equilibrium"
                
                # For LONG: discount zone is preferred
                if direction in ('bullish', 'long'):
                    if current_zone == 'discount':
                        if zone_pct < 30:  # Deep discount
                            pd_score = 100.0
                            pd_rationale = f"Deep discount zone ({zone_pct:.0f}%) - ideal for longs"
                        else:
                            pd_score = 75.0
                            pd_rationale = f"Discount zone ({zone_pct:.0f}%) - good for longs"
                    elif current_zone == 'premium':
                        if zone_pct > 70:  # Deep premium
                            pd_score = 20.0
                            pd_rationale = f"Deep premium zone ({zone_pct:.0f}%) - risky for longs"
                        else:
                            pd_score = 35.0
                            pd_rationale = f"Premium zone ({zone_pct:.0f}%) - caution for longs"
                
                # For SHORT: premium zone is preferred
                elif direction in ('bearish', 'short'):
                    if current_zone == 'premium':
                        if zone_pct > 70:  # Deep premium
                            pd_score = 100.0
                            pd_rationale = f"Deep premium zone ({zone_pct:.0f}%) - ideal for shorts"
                        else:
                            pd_score = 75.0
                            pd_rationale = f"Premium zone ({zone_pct:.0f}%) - good for shorts"
                    elif current_zone == 'discount':
                        if zone_pct < 30:  # Deep discount
                            pd_score = 20.0
                            pd_rationale = f"Deep discount zone ({zone_pct:.0f}%) - risky for shorts"
                        else:
                            pd_score = 35.0
                            pd_rationale = f"Discount zone ({zone_pct:.0f}%) - caution for shorts"
                
                factors.append(ConfluenceFactor(
                    name="Premium/Discount Zone",
                    score=pd_score,
                    weight=get_w('premium_discount', 0.08),
                    rationale=pd_rationale
                ))
    except Exception as e:
        logger.debug("P/D zone scoring failed: %s", e)
    
    # --- NEW: Symbol Regime Alignment Scoring ---
    # Rewards trades aligned with the local symbol regime (from RegimeDetector)
    # Penalizes trades that fight the regime
    if regime is not None:
        try:
            regime_result = _score_regime_alignment(
                regime=regime,
                direction=direction,
                max_bonus=15.0,
                max_penalty=12.0
            )
            
            # Add as weighted factor (regime alignment is important for timing)
            factor_score = regime_result['factor_score']
            factors.append(ConfluenceFactor(
                name="Regime Alignment",
                score=factor_score,
                weight=get_w('htf_alignment', 0.12),  # Use htf_alignment weight as proxy
                rationale=regime_result['reason']
            ))
            
            if regime_result['aligned']:
                logger.debug("📊 Regime ALIGNED: %s (adj=%.1f)", 
                           regime_result['reason'], regime_result['adjustment'])
            else:
                logger.debug("⚠️ Regime OPPOSED: %s (adj=%.1f)", 
                           regime_result['reason'], regime_result['adjustment'])
        except Exception as e:
            logger.debug("Regime alignment scoring failed: %s", e)
    
    # --- NEW: Inside Order Block Bonus ---
    # Extra confluence when price is inside a valid aligned OB
    try:
        if current_price is not None:
            for ob in smc_snapshot.order_blocks:
                ob_direction = getattr(ob, 'direction', None)
                ob_low = getattr(ob, 'low', 0)
                ob_high = getattr(ob, 'high', 0)
                
                # Check if price is inside this OB
                if ob_low <= current_price <= ob_high:
                    # Check if OB direction aligns with trade direction
                    if (direction in ('bullish', 'long') and ob_direction == 'bullish') or \
                       (direction in ('bearish', 'short') and ob_direction == 'bearish'):
                        tf = getattr(ob, 'timeframe', 'unknown')
                        factors.append(ConfluenceFactor(
                            name="Inside Order Block",
                            score=100.0,  # Very bullish signal
                            weight=get_w('inside_ob', 0.10),
                            rationale=f"Price inside {tf} {ob_direction} OB (${ob_low:.2f}-${ob_high:.2f}) - immediate entry zone"
                        ))
                        break  # Only count once
    except Exception as e:
        logger.debug("Inside OB bonus failed: %s", e)
    
    # --- NEW: Nested Order Block Bonus ---
    # Extra confluence when LTF OB is nested inside HTF OB (same direction)
    # This indicates stacked institutional demand/supply zones
    try:
        ltf_timeframes = {'5m', '15m'}
        htf_timeframes = {'1h', '1H', '4h', '4H', '1d', '1D'}
        
        # Separate OBs by timeframe category
        ltf_obs = [ob for ob in smc_snapshot.order_blocks if ob.timeframe.lower() in ltf_timeframes]
        htf_obs = [ob for ob in smc_snapshot.order_blocks if ob.timeframe.lower().replace('h', 'h').replace('d', 'd') in htf_timeframes or ob.timeframe in htf_timeframes]
        
        nested_found = False
        for ltf_ob in ltf_obs:
            ltf_dir = getattr(ltf_ob, 'direction', None)
            ltf_low = getattr(ltf_ob, 'low', 0)
            ltf_high = getattr(ltf_ob, 'high', 0)
            ltf_tf = getattr(ltf_ob, 'timeframe', 'unknown')
            
            # Check if this LTF OB aligns with trade direction
            if not ((direction in ('bullish', 'long') and ltf_dir == 'bullish') or \
                    (direction in ('bearish', 'short') and ltf_dir == 'bearish')):
                continue
            
            # Find an HTF OB that contains/overlaps this LTF OB (same direction)
            for htf_ob in htf_obs:
                htf_dir = getattr(htf_ob, 'direction', None)
                htf_low = getattr(htf_ob, 'low', 0)
                htf_high = getattr(htf_ob, 'high', 0)
                htf_tf = getattr(htf_ob, 'timeframe', 'unknown')
                
                # Same direction required
                if htf_dir != ltf_dir:
                    continue
                
                # Check overlap: LTF OB must be at least partially inside HTF OB
                # Overlap = (LTF low <= HTF high) AND (LTF high >= HTF low)
                if ltf_low <= htf_high and ltf_high >= htf_low:
                    factors.append(ConfluenceFactor(
                        name="Nested Order Block",
                        score=100.0,
                        weight=get_w('nested_ob', 0.08),
                        rationale=f"{ltf_tf} {ltf_dir} OB nested inside {htf_tf} OB - stacked institutional structure"
                    ))
                    nested_found = True
                    break
            
            if nested_found:
                break  # Only count once
    except Exception as e:
        logger.debug("Nested OB bonus failed: %s", e)
    
    # --- NEW: Opposing Structure Penalty ---
    # Penalty when opposing OB/FVG is near the entry (immediate resistance/support)
    try:
        if current_price is not None:
            atr = indicators.by_timeframe.get(getattr(config, 'primary_planning_timeframe', '4h'))
            atr_val = getattr(atr, 'atr', 0) if atr else 0
            
            if atr_val > 0:
                opposing_atr_threshold = 2.0  # Within 2 ATR
                
                for ob in smc_snapshot.order_blocks:
                    ob_direction = getattr(ob, 'direction', None)
                    ob_low = getattr(ob, 'low', 0)
                    ob_high = getattr(ob, 'high', 0)
                    
                    # For LONG, check for bearish OBs above price (resistance)
                    if direction in ('bullish', 'long') and ob_direction == 'bearish':
                        if ob_low > current_price:
                            dist = (ob_low - current_price) / atr_val
                            if dist <= opposing_atr_threshold:
                                tf = getattr(ob, 'timeframe', 'unknown')
                                penalty_score = max(20.0, 50.0 - (dist * 15))  # Closer = worse
                                factors.append(ConfluenceFactor(
                                    name="Opposing Structure",
                                    score=penalty_score,
                                    weight=get_w('opposing_structure', 0.08),
                                    rationale=f"Bearish {tf} OB {dist:.1f} ATR above - resistance threat"
                                ))
                                break  # Only count nearest opposing
                    
                    # For SHORT, check for bullish OBs below price (support)
                    elif direction in ('bearish', 'short') and ob_direction == 'bullish':
                        if ob_high < current_price:
                            dist = (current_price - ob_high) / atr_val
                            if dist <= opposing_atr_threshold:
                                tf = getattr(ob, 'timeframe', 'unknown')
                                penalty_score = max(20.0, 50.0 - (dist * 15))  # Closer = worse
                                factors.append(ConfluenceFactor(
                                    name="Opposing Structure",
                                    score=penalty_score,
                                    weight=get_w('opposing_structure', 0.08),
                                    rationale=f"Bullish {tf} OB {dist:.1f} ATR below - support threat"
                                ))
                                break  # Only count nearest opposing
    except Exception as e:
        logger.debug("Opposing structure penalty failed: %s", e)
    
    # --- NEW: HTF Inflection Point Bonus ---
    # Big bonus when at HTF support (for LONG) or HTF resistance (for SHORT)
    # This can tip direction organically when at major reversal zones
    try:
        if current_price is not None:
            htf_tfs = ('1w', '1W', '1d', '1D', '4h', '4H')
            for ob in smc_snapshot.order_blocks:
                ob_tf = getattr(ob, 'timeframe', '')
                if ob_tf not in htf_tfs:
                    continue
                    
                ob_direction = getattr(ob, 'direction', None)
                ob_low = getattr(ob, 'low', 0)
                ob_high = getattr(ob, 'high', 0)
                
                # Check if price is near HTF support (bullish OB below)
                if direction in ('bullish', 'long') and ob_direction == 'bullish':
                    if ob_low < current_price:
                        atr_obj = indicators.by_timeframe.get(getattr(config, 'primary_planning_timeframe', '4h'))
                        atr_val = getattr(atr_obj, 'atr', 1) if atr_obj else 1
                        dist = (current_price - ob_high) / atr_val
                        if dist <= 2.0:  # Within 2 ATR of support
                            factors.append(ConfluenceFactor(
                                name="HTF Inflection Point",
                                score=100.0,
                                weight=get_w('htf_inflection', 0.15),
                                rationale=f"At {ob_tf} support OB ({dist:.1f} ATR) - strong reversal zone for longs"
                            ))
                            break
                
                # Check if price is near HTF resistance (bearish OB above)
                elif direction in ('bearish', 'short') and ob_direction == 'bearish':
                    if ob_high > current_price:
                        atr_obj = indicators.by_timeframe.get(getattr(config, 'primary_planning_timeframe', '4h'))
                        atr_val = getattr(atr_obj, 'atr', 1) if atr_obj else 1
                        dist = (ob_low - current_price) / atr_val
                        if dist <= 2.0:  # Within 2 ATR of resistance
                            factors.append(ConfluenceFactor(
                                name="HTF Inflection Point",
                                score=100.0,
                                weight=get_w('htf_inflection', 0.15),
                                rationale=f"At {ob_tf} resistance OB ({dist:.1f} ATR) - strong reversal zone for shorts"
                            ))
                            break
    except Exception as e:
        logger.debug("HTF Inflection bonus failed: %s", e)
    
    # --- NEW: Multi-TF Reversal Confluence ---
    # Bonus when multiple reversal signals align (divergence + sweep + BOS)
    try:
        reversal_signals = 0
        reversal_reasons = []
        
        # Check for liquidity sweeps in direction
        if smc_snapshot.liquidity_sweeps:
            for sweep in smc_snapshot.liquidity_sweeps:
                sweep_dir = getattr(sweep, 'direction', None)
                if (direction in ('bullish', 'long') and sweep_dir == 'bullish') or \
                   (direction in ('bearish', 'short') and sweep_dir == 'bearish'):
                    reversal_signals += 1
                    reversal_reasons.append(f"{getattr(sweep, 'timeframe', 'unknown')} sweep")
                    break
        
        # Check for structural breaks in direction
        if smc_snapshot.structural_breaks:
            for brk in smc_snapshot.structural_breaks:
                brk_dir = getattr(brk, 'direction', None)
                brk_type = getattr(brk, 'break_type', '')
                if (direction in ('bullish', 'long') and brk_dir == 'bullish') or \
                   (direction in ('bearish', 'short') and brk_dir == 'bearish'):
                    if brk_type in ('bos', 'choch', 'BOS', 'CHoCH'):
                        reversal_signals += 1
                        reversal_reasons.append(f"{getattr(brk, 'timeframe', 'unknown')} {brk_type}")
                        break
        
        # Check swing structure for bias alignment
        if smc_snapshot.swing_structure:
            for tf, ss in smc_snapshot.swing_structure.items():
                trend = ss.get('trend', 'neutral') if isinstance(ss, dict) else getattr(ss, 'trend', 'neutral')
                if (direction in ('bullish', 'long') and trend == 'bullish') or \
                   (direction in ('bearish', 'short') and trend == 'bearish'):
                    reversal_signals += 1
                    reversal_reasons.append(f"{tf} trend={trend}")
                    break
        
        if reversal_signals >= 2:
            score = min(100.0, 50.0 + (reversal_signals * 15))
            factors.append(ConfluenceFactor(
                name="Multi-TF Reversal",
                score=score,
                weight=get_w('multi_tf_reversal', 0.12),
                rationale=f"{reversal_signals} reversal signals: {', '.join(reversal_reasons[:3])}"
            ))
    except Exception as e:
        logger.debug("Multi-TF reversal failed: %s", e)
    
    # --- NEW: LTF Structure Shift (Micro-Reversal) ---
    # Partial bonus when LTF (5m/15m) shows CHoCH/BOS even if HTF is against
    try:
        ltf_tfs = ('5m', '15m', '1m')
        for brk in smc_snapshot.structural_breaks:
            brk_tf = getattr(brk, 'timeframe', '')
            if brk_tf not in ltf_tfs:
                continue
                
            brk_dir = getattr(brk, 'direction', None)
            brk_type = getattr(brk, 'break_type', '')
            
            if brk_type in ('choch', 'CHoCH', 'bos', 'BOS'):
                if (direction in ('bullish', 'long') and brk_dir == 'bullish') or \
                   (direction in ('bearish', 'short') and brk_dir == 'bearish'):
                    factors.append(ConfluenceFactor(
                        name="LTF Structure Shift",
                        score=75.0,
                        weight=get_w('ltf_structure_shift', 0.08),
                        rationale=f"{brk_tf} {brk_type} {brk_dir} - micro-reversal forming"
                    ))
                    break
    except Exception as e:
        logger.debug("LTF structure shift failed: %s", e)
    
    # --- NEW: Institutional Sequence Factor ---
    # Detects Sweep → OB → BOS pattern (institutional footprint)
    # Sweep before OB: 3-7 candles (same TF as OB)
    # BOS after OB: 3-10 candles
    try:
        best_sequence_score = 0
        best_sequence_rationale = ""
        
        for ob in smc_snapshot.order_blocks:
            ob_direction = getattr(ob, 'direction', None)
            ob_timestamp = getattr(ob, 'timestamp', None)
            ob_tf = getattr(ob, 'timeframe', '')
            
            # Skip OBs that don't align with trade direction
            if direction in ('bullish', 'long') and ob_direction != 'bullish':
                continue
            if direction in ('bearish', 'short') and ob_direction != 'bearish':
                continue
            
            if not ob_timestamp:
                continue
            
            has_sweep_before = False
            has_bos_after = False
            sweep_detail = ""
            bos_detail = ""
            
            # Check for liquidity sweep BEFORE this OB (within 7 candles = ~hours on 4H)
            for sweep in smc_snapshot.liquidity_sweeps:
                sweep_ts = getattr(sweep, 'timestamp', None)
                sweep_dir = getattr(sweep, 'direction', None)
                sweep_tf = getattr(sweep, 'timeframe', '')
                
                if not sweep_ts or sweep_tf.lower() != ob_tf.lower():
                    continue
                
                # Sweep should be before OB and align with direction
                if sweep_ts < ob_timestamp:
                    time_diff = (ob_timestamp - sweep_ts).total_seconds()
                    # 7 candles on 4H = 28 hours
                    max_lookback = 7 * 4 * 3600 if '4' in ob_tf else 7 * 3600
                    
                    if time_diff <= max_lookback:
                        if (direction in ('bullish', 'long') and sweep_dir == 'bullish') or \
                           (direction in ('bearish', 'short') and sweep_dir == 'bearish'):
                            has_sweep_before = True
                            sweep_detail = f"{sweep_tf} sweep"
                            break
            
            # Check for BOS/CHoCH AFTER this OB (within 10 candles)
            for brk in smc_snapshot.structural_breaks:
                brk_ts = getattr(brk, 'timestamp', None)
                brk_dir = getattr(brk, 'direction', None)
                brk_type = getattr(brk, 'break_type', '')
                brk_tf = getattr(brk, 'timeframe', '')
                
                if not brk_ts:
                    continue
                
                # BOS should be after OB
                if brk_ts > ob_timestamp:
                    time_diff = (brk_ts - ob_timestamp).total_seconds()
                    # 10 candles on 4H = 40 hours
                    max_forward = 10 * 4 * 3600 if '4' in ob_tf else 10 * 3600
                    
                    if time_diff <= max_forward:
                        if (direction in ('bullish', 'long') and brk_dir == 'bullish') or \
                           (direction in ('bearish', 'short') and brk_dir == 'bearish'):
                            has_bos_after = True
                            bos_detail = f"{brk_tf} {brk_type}"
                            break
            
            # Score the sequence
            sequence_score = 0
            if has_sweep_before and has_bos_after:
                sequence_score = 100  # Full sequence
                rationale = f"Full institutional sequence: {sweep_detail} → {ob_tf} OB → {bos_detail}"
            elif has_sweep_before:
                sequence_score = 60  # Sweep + OB
                rationale = f"Sweep + OB: {sweep_detail} → {ob_tf} OB (awaiting BOS)"
            elif has_bos_after:
                sequence_score = 50  # OB + BOS
                rationale = f"OB + BOS: {ob_tf} OB → {bos_detail} (no sweep detected)"
            else:
                continue  # No sequence worth mentioning
            
            if sequence_score > best_sequence_score:
                best_sequence_score = sequence_score
                best_sequence_rationale = rationale
        
        if best_sequence_score > 0:
            # Weight based on sequence completeness
            # Sweep+OB+BOS=20pts (100*0.20), Sweep+OB=12pts, OB+BOS=10pts
            weight = 0.20 if best_sequence_score == 100 else (0.12 if best_sequence_score == 60 else 0.10)
            factors.append(ConfluenceFactor(
                name="Institutional Sequence",
                score=best_sequence_score,
                weight=weight,
                rationale=best_sequence_rationale
            ))
    except Exception as e:
        logger.debug("Institutional sequence failed: %s", e)
    
    # ===========================================================================
    # === PRIMARY FAILURE DAMPENING ===
    # ===========================================================================
    # If a "hard gate" fires (MACD veto, HTF Momentum blocked), we should NOT
    # quadruple-punish the same underlying issue. Reduce overlapping soft 
    # penalties by 50% to prevent score obliteration.
    
    # Identify hard gate failures
    hard_gate_fired = False
    hard_gate_reason = None
    
    # Check for MACD veto (factor with score=0, name contains "MACD")
    for f in factors:
        if 'MACD Veto' in f.name and f.score == 0:
            hard_gate_fired = True
            hard_gate_reason = "MACD Veto"
            break
        if 'HTF_Momentum_Gate' in f.name and f.score < 30:  # Blocked or severely penalized
            hard_gate_fired = True
            hard_gate_reason = "HTF Momentum Gate"
            break
    
    # Dampen overlapping soft penalties if hard gate fired
    if hard_gate_fired:
        dampened_factors = {
            'Timeframe_Conflict_Resolution',
            'HTF Structure Bias',
            'HTF Pullback Setup',
            'Opposing Structure',
            'Weekly StochRSI Bonus'
        }
        
        dampened_count = 0
        for i, f in enumerate(factors):
            if f.name in dampened_factors and f.score < 50:  # Only dampen penalties, not bonuses
                # Reduce penalty weight by 50% (move score toward neutral)
                original_weight = f.weight
                new_weight = f.weight * 0.5
                factors[i] = ConfluenceFactor(
                    name=f.name,
                    score=f.score,
                    weight=new_weight,
                    rationale=f.rationale + f" [dampened: {hard_gate_reason}]"
                )
                dampened_count += 1
        
        if dampened_count > 0:
            logger.debug("🔇 Primary failure dampening: %d factors reduced (cause: %s)", 
                        dampened_count, hard_gate_reason)
    
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
    
    # --- Macro Overlay (if enabled) ---
    macro_score_val = 0.0
    if config and getattr(config, 'macro_overlay_enabled', False) and macro_context:
        # Use boolean flags if available, otherwise heuristics based on symbol being passed down?
        # Scorer doesn't have 'symbol', relying on flags 'is_btc', 'is_alt' passed in
        raw_macro = compute_macro_score(macro_context, direction, is_btc, is_alt)
        
        # Scale impact: +/- 1 raw point = +/- 5% adjustment
        # Max impact: +/- 4 * 5 = +/- 20%
        macro_score_val = raw_macro * 5.0
        
        if macro_score_val != 0:
            logger.info("🌍 Macro Overlay Applied: Raw=%d -> Adj=%.1f", raw_macro, macro_score_val)
            
            # Add explicit factor for visibility in "Details" modal
            rationale_prefix = "MACRO " + ("BONUS" if macro_score_val > 0 else "PENALTY")
            macro_notes = "; ".join(macro_context.notes[-2:]) # Last few notes
            factors.append(ConfluenceFactor(
                name="Macro Overlay",
                score=50.0 + macro_score_val, # Center around 50 for display
                weight=0.0, # Information only, score applied via multiplier/adjustment below
                rationale=f"{rationale_prefix}: {macro_notes} ({macro_score_val:+.1f})"
            ))
            
            # Apply to bonuses/penalties to affect final score without breaking weight normalization
            if macro_score_val > 0:
                synergy_bonus += macro_score_val
            else:
                conflict_penalty += abs(macro_score_val)

    # --- LTF-Only Penalty ---
    # Penalize setups that have NO HTF pattern backing (all patterns are 15m/5m)
    htf_timeframes = {'1w', '1W', '1d', '1D', '4h', '4H', '1h', '1H'}
    htf_pattern_count = 0
    htf_pattern_count += sum(1 for ob in smc_snapshot.order_blocks 
                              if getattr(ob, 'timeframe', '1h') in htf_timeframes)
    htf_pattern_count += sum(1 for fvg in smc_snapshot.fvgs 
                              if getattr(fvg, 'timeframe', '1h') in htf_timeframes)
    htf_pattern_count += sum(1 for brk in smc_snapshot.structural_breaks 
                              if getattr(brk, 'timeframe', '1h') in htf_timeframes)
    
    if htf_pattern_count == 0:
        # LTF-only setup - apply penalty
        ltf_penalty = 15.0
        conflict_penalty += ltf_penalty
        logger.debug("⚠️ LTF-only setup penalty: +%.1f (no HTF pattern backing)", ltf_penalty)
    
    # --- Regime Detection ---
    
    regime = _detect_regime(smc_snapshot, indicators)
    
    # --- Final Score ---
    
    raw_score = weighted_score + synergy_bonus - conflict_penalty
    
    # ===========================================================================
    # === DIMINISHING RETURNS CURVE (Mode-Aware) ===
    # ===========================================================================
    # Prevent score inflation where "everything aligned" = 95%+
    # After threshold, additional points contribute at 50% strength.
    # 
    # Mode-aware thresholds:
    # - Overwatch/Swing: 80 (more selective, allow higher scores)
    # - Surgical/Scalp: 70 (stricter, cap scores earlier)
    # - Strike/Intraday: 75 (balanced)
    
    MODE_DIMINISHING_THRESHOLDS = {
        'macro_surveillance': 80.0,  # Overwatch
        'overwatch': 80.0,
        'precision': 70.0,  # Surgical
        'surgical': 70.0,
        'intraday_aggressive': 75.0,  # Strike
        'strike': 75.0,
        'stealth_balanced': 75.0,  # Stealth
    }
    
    DIMINISHING_THRESHOLD = MODE_DIMINISHING_THRESHOLDS.get(current_profile, 75.0)
    DIMINISHING_RATE = 0.5  # 50% credit above threshold
    
    if raw_score > DIMINISHING_THRESHOLD:
        excess = raw_score - DIMINISHING_THRESHOLD
        final_score = DIMINISHING_THRESHOLD + (excess * DIMINISHING_RATE)
        logger.debug("📉 Diminishing returns applied: %.1f → %.1f (threshold: %.0f, mode: %s)", 
                    raw_score, final_score, DIMINISHING_THRESHOLD, current_profile)
    else:
        final_score = raw_score

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
        # Prefer internal calculation result, fallback to htf_context for legacy safety
        htf_proximity_atr=htf_proximity_result.get('proximity_atr') if htf_proximity_result else (htf_context or {}).get('within_atr'),
        htf_proximity_pct=(htf_context or {}).get('within_pct'),  # Not calculated internally yet
        nearest_htf_level_timeframe=(htf_context or {}).get('timeframe'), # TODO: Extract from result
        nearest_htf_level_type=htf_proximity_result.get('structure_type') if htf_proximity_result else (htf_context or {}).get('type'),
        macro_score=macro_score_val
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
    # NOTE: direction is normalized to 'bullish' or 'bearish' (lowercase)
    bonus = 0.0
    reason_parts = []
    
    # Direction aligns with HTF bias → strong bonus
    if (direction in ('long', 'bullish') and htf_bias == 'bullish'):
        # Bonus scales with strength: max +15 for full Weekly+Daily+4H alignment
        bonus = min(15.0, bias_strength * 3.5)
        reason_parts.append(f"HTF structure bullish ({', '.join(bullish_tfs)})")
        reason_parts.append("LONG aligns with HTF trend")
        
    elif (direction in ('short', 'bearish') and htf_bias == 'bearish'):
        bonus = min(15.0, bias_strength * 3.5)
        reason_parts.append(f"HTF structure bearish ({', '.join(bearish_tfs)})")
        reason_parts.append("SHORT aligns with HTF trend")
        
    # Counter-trend setup → penalty (but not blocking)
    elif (direction in ('long', 'bullish') and htf_bias == 'bearish'):
        bonus = max(-8.0, -bias_strength * 2.0)
        reason_parts.append(f"HTF structure bearish ({', '.join(bearish_tfs)})")
        reason_parts.append("LONG is counter-trend (caution)")
        
    elif (direction in ('short', 'bearish') and htf_bias == 'bullish'):
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


# --- Timeframe Weighting Constants ---
# HTF patterns (institutional) should score higher than LTF patterns (noise)
# 4H is the reference baseline (1.0), weekly patterns most significant
TIMEFRAME_WEIGHTS = {
    '1w': 1.5,   # Weekly patterns are most significant
    '1W': 1.5,
    '1d': 1.3,   # Daily
    '1D': 1.3,
    '4h': 1.0,   # Base reference
    '4H': 1.0,
    '1h': 0.85,  # Intraday
    '1H': 0.85,
    '15m': 0.6,  # LTF patterns worth less
    '5m': 0.3,   # Minimal weight - mostly noise
}

def _get_timeframe_weight(timeframe: str) -> float:
    """Get weight multiplier for pattern timeframe."""
    if not timeframe:
        return 0.7  # Default if unknown
    return TIMEFRAME_WEIGHTS.get(timeframe, 0.7)


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
        logger.debug("📦 OB Score: No order blocks detected")
        return 0.0
    
    # Normalize direction: LONG/SHORT -> bullish/bearish
    normalized_dir = _normalize_direction(direction)
    # Filter for direction-aligned OBs
    aligned_obs = [ob for ob in order_blocks if ob.direction == normalized_dir]
    
    # Debug: Show why OBs don't score
    if not aligned_obs:
        opposite_dir = 'bearish' if normalized_dir == 'bullish' else 'bullish'
        opposite_count = len([ob for ob in order_blocks if ob.direction == opposite_dir])
        logger.info("📦 OB Score: 0 aligned (looking for %s) | %d total | %d %s OBs exist",
                   normalized_dir, len(order_blocks), opposite_count, opposite_dir)
        return 0.0
    
    logger.debug("📦 OB Score: %d aligned %s OBs out of %d total", 
                len(aligned_obs), normalized_dir, len(order_blocks))
    
    # Find best OB (highest freshness and displacement, lowest mitigation, best grade, best TF)
    best_ob = max(aligned_obs, key=lambda ob: (
        ob.freshness_score * 0.25 +
        min(ob.displacement_strength / 3.0, 1.0) * 0.25 +
        (1.0 - ob.mitigation_level) * 0.2 +
        _get_grade_weight(getattr(ob, 'grade', 'B')) * 0.15 +
        _get_timeframe_weight(getattr(ob, 'timeframe', '1h')) * 0.15  # Prefer HTF OBs
    ))
    
    # Score based on OB quality
    base_score = (
        best_ob.freshness_score * 40 +
        min(best_ob.displacement_strength / 2.0, 1.0) * 40 +
        (1.0 - best_ob.mitigation_level) * 20
    )
    
    # Apply grade weighting and timeframe weighting to final score
    grade_weight = _get_grade_weight(getattr(best_ob, 'grade', 'B'))
    tf_weight = _get_timeframe_weight(getattr(best_ob, 'timeframe', '1h'))
    score = base_score * grade_weight * tf_weight
    
    logger.debug("📦 OB Score: %.1f (base=%.1f, grade=%s[%.1f], tf=%s[%.1f])",
                score, base_score, getattr(best_ob, 'grade', 'B'), grade_weight,
                getattr(best_ob, 'timeframe', '?'), tf_weight)
    
    return min(100.0, score)



def _score_fvgs(fvgs: List[FVG], direction: str) -> float:
    """Score FVGs based on size, unfilled status, and grade."""
    if not fvgs:
        logger.debug("🔲 FVG Score: No FVGs detected")
        return 0.0
    
    # Normalize direction: LONG/SHORT -> bullish/bearish
    normalized_dir = _normalize_direction(direction)
    aligned_fvgs = [fvg for fvg in fvgs if fvg.direction == normalized_dir]
    
    if not aligned_fvgs:
        opposite_dir = 'bearish' if normalized_dir == 'bullish' else 'bullish'
        opposite_count = len([fvg for fvg in fvgs if fvg.direction == opposite_dir])
        logger.info("🔲 FVG Score: 0 aligned (looking for %s) | %d total | %d %s FVGs exist",
                   normalized_dir, len(fvgs), opposite_count, opposite_dir)
        return 0.0
    
    logger.debug("🔲 FVG Score: %d aligned %s FVGs out of %d total",
                len(aligned_fvgs), normalized_dir, len(fvgs))
    
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
        _get_grade_weight(getattr(fvg, 'grade', 'B')) *
        _get_timeframe_weight(getattr(fvg, 'timeframe', '1h'))  # Prefer HTF FVGs
    ))
    
    base_score = 70 + (1.0 - best_fvg.overlap_with_price) * 30
    
    # Apply grade weighting and timeframe weighting
    grade_weight = _get_grade_weight(getattr(best_fvg, 'grade', 'B'))
    tf_weight = _get_timeframe_weight(getattr(best_fvg, 'timeframe', '1h'))
    score = base_score * grade_weight * tf_weight
    
    return min(100.0, score)


def _score_structural_breaks(breaks: List[StructuralBreak], direction: str) -> float:
    """Score structural breaks (BOS/CHoCH) with grade and TF weighting.
    
    Note: Filters to direction-aligned breaks and meaningful HTF breaks (1H+). 
    LTF breaks are heavily penalized to prevent 5m BOS from driving the structure score.
    """
    if not breaks:
        return 0.0
    
    # Normalize direction: LONG/SHORT -> bullish/bearish
    normalized_dir = _normalize_direction(direction)
    
    # Filter to direction-aligned breaks FIRST
    aligned_breaks = [b for b in breaks if getattr(b, 'direction', 'bullish') == normalized_dir]
    
    if not aligned_breaks:
        # No aligned breaks - log and return 0
        opposite_dir = 'bearish' if normalized_dir == 'bullish' else 'bullish'
        opposite_count = len([b for b in breaks if getattr(b, 'direction', 'bullish') == opposite_dir])
        logger.debug("📊 Structure Score: 0 aligned (looking for %s) | %d total | %d %s breaks exist",
                    normalized_dir, len(breaks), opposite_count, opposite_dir)
        return 0.0
    
    # Filter to meaningful timeframes (1H+) - LTF breaks are noise
    meaningful_tfs = {'1w', '1W', '1d', '1D', '4h', '4H', '1h', '1H'}
    meaningful_breaks = [b for b in aligned_breaks if getattr(b, 'timeframe', '1h') in meaningful_tfs]
    
    if not meaningful_breaks:
        # Fallback to any aligned break but heavily penalized (LTF-only)
        latest_break = max(aligned_breaks, key=lambda b: b.timestamp)
        base_score = 30.0  # Much lower base for LTF-only
        tf_weight = 0.3  # Additional penalty
    else:
        # Use most recent meaningful break
        latest_break = max(meaningful_breaks, key=lambda b: b.timestamp)
        # BOS in trend direction is strongest
        if latest_break.break_type == "BOS":
            base_score = 80.0
        else:  # CHoCH
            base_score = 60.0
        # Bonus for HTF alignment
        if latest_break.htf_aligned:
            base_score += 20.0
        tf_weight = _get_timeframe_weight(getattr(latest_break, 'timeframe', '1h'))
    
    # Apply grade weighting and timeframe weighting
    grade_weight = _get_grade_weight(getattr(latest_break, 'grade', 'B'))
    score = base_score * grade_weight * tf_weight
    
    logger.debug("📊 Structure Score: %.1f (%s %s | base=%.1f, grade=%s, tf=%s)",
                score, latest_break.break_type, normalized_dir, base_score,
                getattr(latest_break, 'grade', 'B'), getattr(latest_break, 'timeframe', '?'))
    
    return min(100.0, score)


def _score_liquidity_sweeps(sweeps: List[LiquiditySweep], direction: str) -> float:
    """Score liquidity sweeps with grade and TF weighting."""
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
    
    # Prefer HTF sweeps (they're institutional), then confirmation level, then timestamp
    best_sweep = max(aligned_sweeps, key=lambda s: (
        _get_timeframe_weight(getattr(s, 'timeframe', '1h')),
        getattr(s, 'confirmation_level', 1 if s.confirmation else 0),
        s.timestamp
    ))
    
    # Phase 4: Score based on confirmation level (0-3)
    conf_level = getattr(best_sweep, 'confirmation_level', 1 if best_sweep.confirmation else 0)
    
    if conf_level >= 3:
        base_score = 85.0  # Structure-validated = strongest
    elif conf_level == 2:
        base_score = 75.0  # Volume + pattern
    elif conf_level == 1:
        base_score = 60.0  # Volume or pattern only
    else:
        base_score = 45.0  # Unconfirmed sweep
    
    # Apply grade weighting and timeframe weighting
    grade_weight = _get_grade_weight(getattr(best_sweep, 'grade', 'B'))
    tf_weight = _get_timeframe_weight(getattr(best_sweep, 'timeframe', '1h'))
    score = base_score * grade_weight * tf_weight
    
    logger.debug("💧 Sweep Score: %.1f (conf_lvl=%d, base=%.1f, grade=%s, tf=%s)",
                score, conf_level, base_score, 
                getattr(best_sweep, 'grade', 'B'),
                getattr(best_sweep, 'timeframe', '?'))
    
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
    score = 0.0  # FIXED: Was 40.0 which inflated momentum even with no signals
    macd_analysis = None
    
    # Normalize direction: LONG/SHORT -> bullish/bearish
    normalized_dir = _normalize_direction(direction)
    
    if normalized_dir == "bullish":
        # Bullish momentum: oversold RSI, low Stoch RSI, low MFI
        if indicators.rsi is not None:
            if indicators.rsi < 40:
                score += 40 * ((40 - indicators.rsi) / 40)
            elif 40 <= indicators.rsi <= 60:
                score += 20.0  # Trend-following neutral bonus
        
        if indicators.stoch_rsi is not None and indicators.stoch_rsi < 30:
            score += 30 * ((30 - indicators.stoch_rsi) / 30)
        
        if indicators.mfi is not None and indicators.mfi < 30:
            score += 30 * ((30 - indicators.mfi) / 30)
    
    else:  # bearish
        # Bearish momentum: overbought RSI, high Stoch RSI, high MFI
        if indicators.rsi is not None:
            if indicators.rsi > 60:
                score += 40 * ((indicators.rsi - 60) / 40)
            elif 40 <= indicators.rsi <= 60:
                score += 20.0  # Trend-following neutral bonus
        
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
                # Neutral MACD (opposing) gives 0 points - removed legacy +5 fallback
            else:  # bearish
                if macd_line < macd_signal and macd_line < 0:
                    score += 20.0
                elif macd_line < macd_signal:
                    score += 12.0
                # Neutral MACD (opposing) gives 0 points - removed legacy +5 fallback

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
                    score += 15.0  # moderate bullish cross
                elif k < 80:
                    score += 8.0
                else:
                    score += 5.0  # late/exhaustive
                
                # Check previous values for FRESH crossover (just happened)
                k_prev = getattr(indicators, 'stoch_rsi_k_prev', None)
                d_prev = getattr(indicators, 'stoch_rsi_d_prev', None)
                if k_prev is not None and d_prev is not None and k_prev <= d_prev:
                    score += 10.0  # Just crossed over!
                    
            elif normalized_dir == "bearish" and k < d:
                if k > 80:
                    score += 25.0  # overbought bearish cross
                elif k > 50:
                    score += 15.0  # moderate bearish cross
                elif k > 20:
                    score += 8.0
                else:
                    score += 5.0
                
                # Check previous values for FRESH crossover (just happened)
                k_prev = getattr(indicators, 'stoch_rsi_k_prev', None)
                d_prev = getattr(indicators, 'stoch_rsi_d_prev', None)
                if k_prev is not None and d_prev is not None and k_prev >= d_prev:
                    score += 10.0  # Just crossed under!
            else:
                # Opposing crossover strong penalty (avoid chasing into momentum shift)
                if separation >= 5.0:
                    score -= 10.0

    # ADX Trend Strength & DI Confirmation
    adx = getattr(indicators, 'adx', None)
    plus_di = getattr(indicators, 'adx_plus_di', None)
    minus_di = getattr(indicators, 'adx_minus_di', None)
    
    if adx is not None and plus_di is not None and minus_di is not None:
        di_bullish = plus_di > minus_di
        di_aligned = (normalized_dir == "bullish" and di_bullish) or \
                     (normalized_dir == "bearish" and not di_bullish)
        
        if adx > 25:
            if di_aligned:
                score += 20.0  # Strong trend confirmed
                if adx > 40: score += 5.0 # Very strong trend
            else:
                score -= 15.0  # Counter-trend warning

        elif adx < 20:
            score -= 10.0  # Ranging/Weak trend

    # EMA Trend Alignment (EMA stacking)
    ema_9 = getattr(indicators, 'ema_9', None)
    ema_21 = getattr(indicators, 'ema_21', None)
    ema_50 = getattr(indicators, 'ema_50', None)
    
    if ema_9 and ema_21 and ema_50:
        if normalized_dir == "bullish":
            if ema_9 > ema_21 > ema_50:
                score += 15.0 # Strong trend alignment
            elif ema_9 > ema_21:
                score += 5.0 # Moderate trend
        elif normalized_dir == "bearish":
            if ema_9 < ema_21 < ema_50:
                score += 15.0 # Strong trend alignment
            elif ema_9 < ema_21:
                score += 5.0 # Moderate trend

    # Bollinger Band %B - Mean Reversion / Breakout
    # %B > 1.0 = Above Upper Band (Strong Momentum or Overbought)
    # %B < 0.0 = Below Lower Band (Strong Momentum or Oversold)
    # In trend-following, riding the bands is good. In mean-reversion, it's an entry signal.
    pct_b = getattr(indicators, 'bb_percent_b', None)
    if pct_b is not None:
        if normalized_dir == "bullish":
            # For bullish trend, we want price supported, not necessarily blown out
            # But if we are catching a dip, pct_b < 0 is great (oversold)
            if pct_b < 0.05: 
                score += 20.0 # Deep discount / Oversold
            elif 0.4 <= pct_b <= 0.6:
                score += 5.0 # Supported at mid-band (continuation)
        elif normalized_dir == "bearish":
            if pct_b > 0.95:
                score += 20.0 # Premium / Overbought
            elif 0.4 <= pct_b <= 0.6:
                score += 5.0 # Resisting at mid-band

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
    score = 40.0  # Base neutral score (lowered from 50 to penalize lack of signals)
    
    # Volume spike bonus
    if indicators.volume_spike:
        score += 35.0  # 40 -> 75 with spike
        
    # OBV trend confirmation
    obv_trend = getattr(indicators, 'obv_trend', None)
    if obv_trend:
        is_bullish_trade = direction.lower() in ('long', 'bullish')
        if (is_bullish_trade and obv_trend == 'rising'):
            score += 15.0  # Accumulation confirms bullish
        elif (not is_bullish_trade and obv_trend == 'falling'):
            score += 15.0  # Distribution confirms bearish
        elif obv_trend != 'flat' and obv_trend != 'neutral' and obv_trend != ('rising' if is_bullish_trade else 'falling'):
            score -= 10.0  # OBV divergence warning
    
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
    # >3.0
    score = 25.0
    
    # Apply TTM Squeeze Modifiers
    if getattr(indicators, 'ttm_squeeze_firing', False):
        score += 15.0  # Expansion likely - volatility developing
    elif getattr(indicators, 'ttm_squeeze_on', False):
        score -= 5.0   # Compression - low volatility warning
        
    return max(0.0, min(100.0, score))


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
    
    # --- HTF SWEEP → LTF ENTRY SYNERGY ---
    # When HTF sweep detected, LTF entries in expected direction get bonus
    htf_context = getattr(smc, 'htf_sweep_context', None)
    if htf_context and htf_context.get('has_recent_htf_sweep'):
        expected_dir = htf_context.get('expected_ltf_direction', '')
        direction_lower = direction.lower() if direction else ''
        
        # Check alignment: HTF swept low → expect bullish → LONG gets bonus
        # HTF swept high → expect bearish → SHORT gets bonus
        if (expected_dir == 'bullish' and direction_lower in ('long', 'bullish')):
            bonus += 12.0
            logger.debug("📊 HTF sweep → LTF long alignment (+12): %s sweep signaled bullish",
                        htf_context.get('sweep_timeframe', '?'))
        elif (expected_dir == 'bearish' and direction_lower in ('short', 'bearish')):
            bonus += 12.0
            logger.debug("📊 HTF sweep → LTF short alignment (+12): %s sweep signaled bearish",
                        htf_context.get('sweep_timeframe', '?'))
    
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
    
    # Apply diminishing returns after 15 points
    # This prevents "lucky" factor stacking from inflating scores excessively
    if bonus > 15.0:
        excess = bonus - 15.0
        bonus = 15.0 + (excess * 0.5)
        logger.debug("📊 Synergy diminishing applied: excess %.1f → %.1f", excess, excess * 0.5)
    
    # Clamp synergy bonus to max 25 (allow strong multi-factor synergies)
    return min(bonus, 25.0)


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
    
    # === HTF ALIGNMENT PENALTY ===
    # FIXED: Only penalize if HTF Alignment wasn't already scored as a factor
    # (otherwise we double-penalize: score 0 AND conflict penalty)
    htf_factor = next((f for f in factors if f.name == "HTF Alignment"), None)
    htf_already_scored_negative = htf_factor and htf_factor.score < 30  # Already penalized via low score
    
    if htf_factor and not htf_already_scored_negative:
        if htf_factor.score == 0.0:
            # HTF opposing direction - major penalty (only if not already scored low)
            penalty += 15.0
            logger.debug("HTF opposition penalty applied: +15")
        elif htf_factor.score == 50.0:
            # HTF neutral (ranging) - moderate penalty for counter-trend risk
            penalty += 8.0
            logger.debug("HTF neutral penalty applied: +8")
    
    # Cap penalty to 35 (limit downside impact)
    return min(penalty, 35.0)


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
    if atr_pct:
        val = atr_pct
        if val < 0.25: return f"Very low volatility ({val:.2f}%) - chop risk"
        if val < 0.75: return f"Healthy volatility expansion ({val:.2f}%)"
        if val < 1.5: return f"Moderate volatility ({val:.2f}%)"
        if val < 3.0: return f"High volatility ({val:.2f}%)"
        return f"Excessive volatility ({val:.2f}%) - unpredictable"
    return "Volatility data unavailable"


def _score_mtf_indicator_confluence(indicators: IndicatorSet, direction: str) -> Tuple[float, str]:
    """Check if indicators align across timeframes."""
    norm_dir = _normalize_direction(direction)
    is_bullish = norm_dir == 'bullish'
    aligned_count = 0
    opposed_count = 0
    
    for tf, ind in indicators.by_timeframe.items():
        rsi = getattr(ind, 'rsi', None)
        if rsi is None: continue
            
        if is_bullish:
            # Bullish alignment: RSI < 45 (oversold/reversal) or > 50 (trend) depending on logic
            # Using simple threshold for alignment
            if rsi < 45 or (getattr(ind, 'macd_line', 0) > getattr(ind, 'macd_signal', 0)):
                aligned_count += 1
            elif rsi > 65:
                # Bearish indication in bullish trade
                opposed_count += 1
        else: # Bearish
            if rsi > 55 or (getattr(ind, 'macd_line', 0) < getattr(ind, 'macd_signal', 0)):
                aligned_count += 1
            elif rsi < 35:
                # Bullish indication in bearish trade
                opposed_count += 1
    
    if aligned_count >= 3 and opposed_count == 0:
        return 15.0, "Strong MTF alignment"
    elif opposed_count >= 2:
        return -10.0, "MTF divergence warning"
    
    return 0.0, ""
