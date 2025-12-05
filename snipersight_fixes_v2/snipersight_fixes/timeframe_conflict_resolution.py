"""
Timeframe Conflict Resolution

Add this function to: backend/strategy/confluence/scorer.py
"""

from typing import Dict, Optional, List
from backend.shared.models.indicators import IndicatorSet
from backend.shared.config.defaults import ScanConfig
import logging

logger = logging.getLogger(__name__)


def resolve_timeframe_conflicts(
    indicators: IndicatorSet,
    direction: str,
    mode_config: ScanConfig,
    swing_structure: Optional[Dict] = None,
    htf_proximity: Optional[Dict] = None
) -> Dict:
    """
    Resolve timeframe conflicts with explicit hierarchical rules.
    
    Rules:
    1. For SCALPS (STRIKE, SURGICAL):
       - Primary bias: 1H
       - Filter: 4H must not be in strong momentum against 1H
       - If 4H is ranging/pullback, allow 1H counter-moves
       - If 4H is accelerating, block 1H counter-moves
    
    2. For SWINGS (OVERWATCH, STEALTH):
       - Primary bias: 1D or 4H
       - Filter: Weekly trend is context, not a hard gate
       - Allow 1D/4H counter-trends if:
         a) Weekly is ranging or showing exhaustion
         b) Entry is at major Weekly structural level
         c) Cycle detector shows DCL/WCL zone
    
    Args:
        indicators: Multi-timeframe indicators
        direction: Trade direction
        mode_config: Scanner mode config
        swing_structure: Swing structure data
        htf_proximity: Result from HTF structural proximity check
        
    Returns:
        Dict with:
            - resolution: str (allowed/blocked/caution)
            - score_adjustment: float
            - conflicts: List[str] (conflicting timeframes)
            - resolution_reason: str
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
    
    # Get primary TF trend
    primary_trend = tf_trends.get(primary_tf, 'neutral')
    is_bullish_trade = direction.lower() in ('bullish', 'long')
    
    # Check if primary TF aligns with trade direction
    primary_aligned = (
        (is_bullish_trade and primary_trend == 'bullish') or
        (not is_bullish_trade and primary_trend == 'bearish')
    )
    
    if not primary_aligned:
        conflicts.append(f"{primary_tf} {primary_trend} (primary)")
        resolution_reason_parts.append(f"Primary TF ({primary_tf}) not aligned with {direction}")
        score_adjustment -= 15.0
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
            
            # Check for strong momentum (from momentum gate)
            htf_ind = indicators.by_timeframe.get(tf)
            is_strong_momentum = False
            
            if htf_ind and htf_ind.atr:
                atr_series = getattr(htf_ind, 'atr_series', [])
                if len(atr_series) >= 5:
                    recent_atr = atr_series[-5:]
                    expanding_bars = sum(
                        1 for i in range(1, len(recent_atr))
                        if recent_atr[i] > recent_atr[i-1]
                    )
                    is_strong_momentum = (expanding_bars >= 4)
            
            if is_strong_momentum:
                # Strong momentum against trade = BLOCK
                resolution = 'blocked'
                score_adjustment -= 40.0
                resolution_reason_parts.append(f"{tf} in strong {htf_trend} momentum, blocking {direction}")
                break
            else:
                # Weak/ranging HTF = ALLOW with caution
                resolution = 'caution'
                score_adjustment -= 10.0
                resolution_reason_parts.append(f"{tf} {htf_trend} but not strong momentum")
    
    # Exception: If at major HTF structure, reduce penalty
    if htf_proximity and htf_proximity.get('valid') and htf_proximity.get('proximity_atr', 999) < 1.0:
        score_adjustment += 15.0
        resolution_reason_parts.append("At major HTF structure (overrides conflict penalty)")
        if resolution == 'blocked' and score_adjustment > -30.0:
            resolution = 'caution'  # Upgrade from blocked to caution
    
    # Exception: If in cycle timing zone (DCL/WCL), reduce penalty
    # TODO: Integrate cycle context here if available from orchestrator
    
    # Final resolution
    if not conflicts:
        resolution = 'allowed'
        resolution_reason_parts.append("All timeframes aligned or neutral")
    
    return {
        'resolution': resolution,
        'score_adjustment': score_adjustment,
        'conflicts': conflicts,
        'resolution_reason': '; '.join(resolution_reason_parts) if resolution_reason_parts else 'No conflicts'
    }
