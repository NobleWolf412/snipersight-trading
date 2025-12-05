"""
HTF Momentum Gate

Add this function to: backend/strategy/confluence/scorer.py
"""

from typing import Dict, Optional
from backend.shared.models.indicators import IndicatorSet
from backend.shared.config.defaults import ScanConfig
import logging

logger = logging.getLogger(__name__)


def evaluate_htf_momentum_gate(
    indicators: IndicatorSet,
    direction: str,
    mode_config: ScanConfig,
    swing_structure: Optional[Dict] = None
) -> Dict:
    """
    HTF Momentum Gate - blocks counter-trend trades during strong HTF momentum.
    
    Checks higher timeframes for:
    - Strong trend (strong_up/strong_down from regime detector)
    - ATR expansion (momentum building)
    - Volume increasing (conviction)
    
    If HTF is in strong momentum AGAINST trade direction, apply veto or heavy penalty.
    
    Args:
        indicators: Multi-timeframe indicators
        direction: "bullish" or "bearish"
        mode_config: Scanner mode config
        swing_structure: Optional swing structure for trend confirmation
        
    Returns:
        Dict with:
            - allowed: bool (False if strong momentum blocks trade)
            - score_adjustment: float (0 if allowed, large penalty if blocked)
            - htf_momentum: str (calm/normal/building/strong)
            - htf_trend: str (bullish/bearish/neutral)
            - reason: str
    """
    
    # Get higher timeframes (one level above primary planning TF)
    primary_tf = getattr(mode_config, 'primary_planning_timeframe', '1h')
    structure_tfs = getattr(mode_config, 'structure_timeframes', ('4h', '1d'))
    
    # Use highest structure TF as HTF reference
    htf = max(structure_tfs, key=lambda x: {
        '5m': 0, '15m': 1, '1h': 2, '4h': 3, '1d': 4, '1w': 5
    }.get(x, 0))
    
    htf_ind = indicators.by_timeframe.get(htf)
    
    if not htf_ind:
        # Can't evaluate without HTF data
        return {
            'allowed': True,
            'score_adjustment': 0.0,
            'htf_momentum': 'unknown',
            'htf_trend': 'unknown',
            'reason': f'No {htf} indicators available'
        }
    
    # 1. Detect HTF trend from swing structure
    htf_trend = 'neutral'
    if swing_structure and htf in swing_structure:
        ss = swing_structure[htf]
        htf_trend = ss.get('trend', 'neutral')  # bullish/bearish/neutral
    
    # 2. Detect momentum strength from ATR expansion
    atr = htf_ind.atr
    atr_series = getattr(htf_ind, 'atr_series', [])
    
    momentum_strength = 'normal'
    if atr and len(atr_series) >= 10:
        recent_atr = atr_series[-10:]
        atr_expanding = sum(
            1 for i in range(1, len(recent_atr))
            if recent_atr[i] > recent_atr[i-1]
        )
        
        if atr_expanding >= 7:
            momentum_strength = 'strong'  # ATR expanding consistently
        elif atr_expanding >= 5:
            momentum_strength = 'building'
        elif atr_expanding <= 3:
            momentum_strength = 'calm'
    
    # 3. Check volume confirmation
    volume_strong = False
    if hasattr(htf_ind, 'relative_volume'):
        rel_vol = htf_ind.relative_volume
        if rel_vol and rel_vol > 1.3:
            volume_strong = True
    
    # 4. Momentum Gate Logic
    # Block counter-trend trades if HTF is in strong momentum
    
    is_bullish_trade = direction.lower() in ('bullish', 'long')
    htf_is_bullish = htf_trend == 'bullish'
    htf_is_bearish = htf_trend == 'bearish'
    
    # Case 1: Strong momentum AGAINST trade direction
    if momentum_strength in ('strong', 'building'):
        if is_bullish_trade and htf_is_bearish:
            # Trying to go long while HTF is in strong bearish momentum
            penalty = -50.0 if volume_strong else -35.0
            
            return {
                'allowed': False,
                'score_adjustment': penalty,
                'htf_momentum': momentum_strength,
                'htf_trend': htf_trend,
                'reason': f"{htf} in strong bearish momentum (ATR expanding, blocking LONG)"
            }
        
        elif not is_bullish_trade and htf_is_bullish:
            # Trying to go short while HTF is in strong bullish momentum
            penalty = -50.0 if volume_strong else -35.0
            
            return {
                'allowed': False,
                'score_adjustment': penalty,
                'htf_momentum': momentum_strength,
                'htf_trend': htf_trend,
                'reason': f"{htf} in strong bullish momentum (ATR expanding, blocking SHORT)"
            }
    
    # Case 2: Calm/ranging HTF - allow counter-trend trades
    if momentum_strength == 'calm' or htf_trend == 'neutral':
        return {
            'allowed': True,
            'score_adjustment': 0.0,
            'htf_momentum': momentum_strength,
            'htf_trend': htf_trend,
            'reason': f"{htf} in {htf_trend} trend with {momentum_strength} momentum (allowing counter-trend)"
        }
    
    # Case 3: Momentum WITH trade direction - bonus
    if (is_bullish_trade and htf_is_bullish) or (not is_bullish_trade and htf_is_bearish):
        bonus = 10.0 if momentum_strength == 'strong' else 5.0
        
        return {
            'allowed': True,
            'score_adjustment': bonus,
            'htf_momentum': momentum_strength,
            'htf_trend': htf_trend,
            'reason': f"{htf} momentum supports {direction} (aligned)"
        }
    
    # Default: allow but no bonus
    return {
        'allowed': True,
        'score_adjustment': 0.0,
        'htf_momentum': momentum_strength,
        'htf_trend': htf_trend,
        'reason': f"{htf} {htf_trend} with {momentum_strength} momentum"
    }
