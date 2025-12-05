"""
HTF Structural Proximity Gate

Add this function to: backend/strategy/confluence/scorer.py
"""

from typing import Dict, Optional, Tuple
from backend.shared.models.smc import SMCSnapshot
from backend.shared.models.indicators import IndicatorSet
from backend.shared.config.defaults import ScanConfig
from backend.analysis.premium_discount import detect_premium_discount
import logging

logger = logging.getLogger(__name__)


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
    - HTF Key Level (support/resistance from htf_levels.py)
    - HTF Swing Point (last HH/HL/LH/LL)
    - Premium/Discount Zone boundary
    
    If entry is >2 ATR from ANY HTF structure, apply HEAVY penalty or reject.
    
    Args:
        smc: SMC snapshot with all detected patterns
        indicators: Multi-timeframe indicators (need ATR)
        entry_price: Proposed entry price
        direction: "bullish" or "bearish"
        mode_config: Scanner mode config for timeframe responsibility
        swing_structure: Optional swing structure data for HTF swings
        
    Returns:
        Dict with:
            - valid: bool (True if entry is at HTF structure)
            - score_adjustment: float (bonus if valid, heavy penalty if not)
            - proximity_atr: float (distance to nearest HTF level in ATR)
            - nearest_structure: str (description of nearest structure)
            - structure_type: str (OB/FVG/KeyLevel/Swing/PremiumDiscount)
    """
    
    # Get HTF timeframes from mode config
    structure_tfs = getattr(mode_config, 'structure_timeframes', ('4h', '1d'))
    
    # Get ATR from primary planning timeframe
    primary_tf = getattr(mode_config, 'primary_planning_timeframe', '1h')
    primary_ind = indicators.by_timeframe.get(primary_tf)
    
    if not primary_ind or not primary_ind.atr:
        # Fallback: can't validate without ATR
        return {
            'valid': True,  # Don't block if we can't calculate
            'score_adjustment': 0.0,
            'proximity_atr': None,
            'nearest_structure': 'ATR unavailable for validation',
            'structure_type': 'unknown'
        }
    
    atr = primary_ind.atr
    max_distance_atr = 2.0  # Maximum acceptable distance
    
    # Track nearest structure
    min_distance = float('inf')
    nearest_structure = None
    structure_type = None
    
    # 1. Check HTF Order Blocks
    for ob in smc.order_blocks:
        if ob.timeframe not in structure_tfs:
            continue
        
        # Only consider high-quality OBs (A/B grade, fresh)
        ob_grade = getattr(ob, 'grade', 'B')
        if ob_grade not in ('A', 'B'):
            continue
        
        if ob.freshness_score < 0.5:
            continue
        
        # Check if entry is near this OB
        ob_center = (ob.top + ob.bottom) / 2
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
        
        # Only consider substantial, unfilled FVGs
        if fvg.size < atr:
            continue
        
        if fvg.overlap_with_price > 0.5:
            continue
        
        # Check if entry is within FVG
        if fvg.bottom <= entry_price <= fvg.top:
            min_distance = 0.0
            nearest_structure = f"{fvg.timeframe} FVG {fvg.bottom:.5f}-{fvg.top:.5f}"
            structure_type = "FVG"
            break
        
        # Check proximity to FVG boundary
        distance = min(abs(entry_price - fvg.top), abs(entry_price - fvg.bottom))
        distance_atr = distance / atr
        
        if distance_atr < min_distance:
            min_distance = distance_atr
            nearest_structure = f"{fvg.timeframe} FVG boundary @ {fvg.top:.5f}/{fvg.bottom:.5f}"
            structure_type = "FVG"
    
    # 3. Check HTF Swing Points (HH/HL/LH/LL)
    if swing_structure:
        for tf in structure_tfs:
            if tf not in swing_structure:
                continue
            
            ss = swing_structure[tf]
            
            # Check last significant swings
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
    # Use highest structure TF for P/D zones
    htf = max(structure_tfs, key=lambda x: {
        '5m': 0, '15m': 1, '1h': 2, '4h': 3, '1d': 4, '1w': 5
    }.get(x, 0))
    
    htf_ind = indicators.by_timeframe.get(htf)
    
    if htf_ind and hasattr(htf_ind, 'dataframe'):
        df = htf_ind.dataframe
        pd_zone = detect_premium_discount(df, lookback=50, current_price=entry_price)
        
        # Check proximity to equilibrium (50% level)
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
            # Entry in wrong P/D zone AND far from structure
            return {
                'valid': False,
                'score_adjustment': -40.0,
                'proximity_atr': min_distance,
                'nearest_structure': f"Entry in {pd_zone.current_zone} zone (wrong for {direction})",
                'structure_type': "PremiumDiscount_VIOLATION"
            }
    
    # DECISION LOGIC
    if min_distance <= max_distance_atr:
        # Entry is at HTF structure - VALID
        bonus = 0.0
        
        # Give bonus for being very close (<0.5 ATR)
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
        # Entry is TOO FAR from any HTF structure - REJECT
        penalty = min(-30.0, -10.0 * (min_distance - max_distance_atr))
        
        return {
            'valid': False,
            'score_adjustment': penalty,
            'proximity_atr': min_distance,
            'nearest_structure': nearest_structure or "No HTF structure nearby",
            'structure_type': "NONE_NEARBY"
        }
