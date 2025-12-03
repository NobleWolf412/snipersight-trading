"""
Planner Configuration Module

Centralizes all trade planner tuning parameters, removing magic numbers from code.
Provides mode-specific defaults (scalp, swing, intraday) for backward compatibility.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class PlannerConfig:
    """Configuration for trade plan generation.
    
    All tuning parameters for entry zones, stops, targets, and structure filtering.
    """
    
    # Risk:Reward targets
    min_rr: float = 1.0
    target_rr_ladder: List[float] = field(default_factory=lambda: [1.5, 2.5, 4.0])
    
    # ATR-based offsets
    entry_zone_offset_atr: float = 0.1  # Base offset for entry zone boundaries
    stop_buffer_atr: float = 0.3  # Buffer beyond structure for stop loss
    fallback_entry_near_atr: float = 0.5  # ATR fallback: near entry offset
    fallback_entry_far_atr: float = 1.5  # ATR fallback: far entry offset
    
    # ATR regime classification (thresholds in ATR% of price)
    atr_regime_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "calm": 0.5,      # ATR < 0.5% of price
        "normal": 1.2,    # ATR < 1.2%
        "elevated": 2.0,  # ATR < 2.0%
        # "explosive" is > 2.0%
    })
    
    # ATR regime multipliers (scale base offsets by regime)
    atr_regime_multipliers: Dict[str, float] = field(default_factory=lambda: {
        "calm": 0.7,
        "normal": 1.0,
        "elevated": 1.2,
        "explosive": 1.5,
    })
    
    # Higher timeframe bias (gradient-based)
    htf_bias_enabled: bool = True
    htf_bias_max_atr_distance: float = 1.0  # Max ATR distance where HTF levels influence offsets
    htf_bias_offset_min_factor: float = 0.3  # Minimum factor when right on HTF level (0.3 = 30% of base offset)
    
    # FVG filtering
    fvg_overlap_max: float = 0.5  # Discard FVGs with overlap >= 50%
    
    # Order Block filtering
    ob_mitigation_max: float = 0.3  # Exclude or deprioritize OBs with mitigation > 30%
    ob_displacement_weight: float = 0.5  # Weight for displacement in scoring
    
    # Swing stop search
    # NOTE: stop_lookback_bars is the BASE value - it gets scaled by timeframe automatically
    # (LTF like 5m scales UP 2.5x, HTF like 1D scales DOWN 0.7x)
    # See scale_lookback() in smc_config.py for details
    stop_lookback_bars: int = 30  # Base swing lookback (calibrated for 4H, auto-scaled per TF)
    stop_htf_lookback_bars: int = 60  # DEPRECATED: no longer used, kept for backward compat
    stop_use_htf_swings: bool = True  # Enable HTF swing searching as fallback
    
    # Price alignment sanity
    price_alignment_max_rel_diff: float = 0.5  # Max relative diff between mid_entry and current_price
    
    # Structure-aware targets
    target_clip_to_structure: bool = True  # Clip targets to HTF obstacles
    target_min_rr_after_clip: float = 1.2  # Minimum R:R after clipping to structure
    
    @classmethod
    def defaults_for_mode(cls, mode: str) -> "PlannerConfig":
        """
        Get mode-specific planner defaults.
        
        Preserves existing behavior for scanner modes (scalp, swing, intraday).
        
        Args:
            mode: Scanner mode ("scalp", "swing", "intraday", etc.)
            
        Returns:
            PlannerConfig with mode-appropriate defaults
        """
        mode_lower = (mode or "intraday").lower()
        
        if mode_lower == "scalp":
            # Scalp: tighter offsets, aggressive targets, conservative structure filtering
            return cls(
                min_rr=1.0,
                target_rr_ladder=[1.2, 2.0, 3.0],
                entry_zone_offset_atr=0.08,  # Tighter entry zones
                stop_buffer_atr=0.25,  # Tighter stops
                fallback_entry_near_atr=0.3,
                fallback_entry_far_atr=1.0,
                atr_regime_multipliers={
                    "calm": 0.6,
                    "normal": 0.9,
                    "elevated": 1.1,
                    "explosive": 1.3,
                },
                htf_bias_offset_min_factor=0.4,  # Less aggressive HTF bias
                fvg_overlap_max=0.4,  # Stricter FVG filtering (40%)
                ob_mitigation_max=0.25,  # Stricter OB filtering
                stop_lookback_bars=15,  # Shorter lookback
                stop_htf_lookback_bars=30,
                target_min_rr_after_clip=1.0,  # Accept tighter R:R for scalps
            )
        
        elif mode_lower == "swing":
            # Swing: wider offsets, patient targets, relaxed structure filtering
            return cls(
                min_rr=1.5,
                target_rr_ladder=[2.0, 3.0, 5.0],
                entry_zone_offset_atr=0.12,  # Wider entry zones
                stop_buffer_atr=0.35,  # Wider stops
                fallback_entry_near_atr=0.7,
                fallback_entry_far_atr=2.0,
                atr_regime_multipliers={
                    "calm": 0.8,
                    "normal": 1.0,
                    "elevated": 1.3,
                    "explosive": 1.7,
                },
                htf_bias_offset_min_factor=0.2,  # More aggressive HTF bias
                fvg_overlap_max=0.6,  # Relaxed FVG filtering (60%)
                ob_mitigation_max=0.35,  # Relaxed OB filtering
                stop_lookback_bars=30,  # Longer lookback
                stop_htf_lookback_bars=60,
                target_min_rr_after_clip=1.5,  # Maintain higher R:R for swings
            )
        
        else:  # intraday or default
            # Intraday: balanced settings (current baseline)
            return cls(
                min_rr=1.2,
                target_rr_ladder=[1.5, 2.5, 4.0],
                entry_zone_offset_atr=0.1,
                stop_buffer_atr=0.3,
                fallback_entry_near_atr=0.5,
                fallback_entry_far_atr=1.5,
                atr_regime_multipliers={
                    "calm": 0.7,
                    "normal": 1.0,
                    "elevated": 1.2,
                    "explosive": 1.5,
                },
                htf_bias_offset_min_factor=0.3,
                fvg_overlap_max=0.5,
                ob_mitigation_max=0.3,
                stop_lookback_bars=20,
                stop_htf_lookback_bars=50,
                target_min_rr_after_clip=1.2,
            )
