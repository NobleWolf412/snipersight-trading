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
    
    # Stop loss floor (% of price) - prevents micro-stops
    min_stop_pct: float = 0.2  # NEW: Minimum stop as % of price (0.2% floor)
    
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
    
    # Dynamic stop buffer by ATR regime (TUNED - reduced from original)
    stop_buffer_by_regime: Dict[str, float] = field(default_factory=lambda: {
        "calm": 0.25,      # Tighter stops in calm markets
        "normal": 0.30,    # TUNED: was 0.35 - tighter standard buffer
        "elevated": 0.35,  # TUNED: was 0.45 - reduced volatile buffer
        "explosive": 0.40, # TUNED: was 0.55 - significantly reduced extreme buffer
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
    
    # HTF swing timeframe allowlist per mode profile (NEW - prevents 1w/1d swings for scalp modes)
    htf_swing_allowed: Dict[str, tuple] = field(default_factory=lambda: {
        "precision": ("1h", "15m"),           # surgical: LTF only, no HTF swings
        "intraday_aggressive": ("1h", "15m"), # strike: LTF only, no HTF swings
        "balanced": ("4h", "1h"),             # recon: up to 4h swings
        "macro_surveillance": ("1d", "4h"),   # overwatch: HTF swings allowed
        "stealth_balanced": ("4h", "1h"),     # ghost: up to 4h swings
    })
    
    # Price alignment sanity
    price_alignment_max_rel_diff: float = 0.5  # Max relative diff between mid_entry and current_price
    
    # Structure-aware targets
    target_clip_to_structure: bool = True  # Clip targets to HTF obstacles
    target_min_rr_after_clip: float = 1.2  # Minimum R:R after clipping to structure
    
    # Smart Entry Upgrade (Phase 4)
    pd_compliance_required: bool = False  # Require entry to be in Premium (Short) / Discount (Long)
    pd_compliance_tolerance: float = 0.05  # 5% tolerance buffer to allow near-miss entries
    sweep_backing_boost: float = 1.0  # Boost score if OB is backed by recent sweep (1.0 = no boost)
    sweep_lookback_candles: int = 5  # Candles prior to OB to check for sweep
    
    # Trend Continuation Strategy (Fallback when no fresh OBs/FVGs)
    enable_trend_continuation: bool = False  # Enable consolidation breakout entries
    consolidation_min_touches: int = 5  # Minimum bounces required for valid consolidation
    consolidation_max_height_pct: float = 0.02  # Max range height as % of price (2%)
    consolidation_min_duration_candles: int = 10  # Minimum consolidation duration
    breakout_displacement_atr: float = 1.0  # Min displacement for valid breakout
    retest_tolerance_atr: float = 0.5  # Tolerance for retest detection
    
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
        
        if mode_lower in ("scalp", "precision"):
            return cls(
                min_rr=1.5,  # Quick scalps
                target_rr_ladder=[1.5, 2.5, 4.0],
                entry_zone_offset_atr=0.1,  # Tight entries
                stop_buffer_atr=0.5,   # Tight stops
                stop_lookback_bars=5,
                stop_use_htf_swings=False,  # Don't use HTF stops for scalps
                target_min_rr_after_clip=1.0, # Accept tighter R:R for scalps
                pd_compliance_required=False, # Speed over perfection
                sweep_backing_boost=2.0,      # Prioritize Turtle Soups (High conviction)
                sweep_lookback_candles=3      # Fast reaction
            )
        
        elif mode_lower in ("strike", "intraday_aggressive"):
            # STRIKE: Aggressive Intraday
            # Similar to Scalp but slightly looser stops for volatility
            return cls(
                min_rr=1.8,
                target_rr_ladder=[2.0, 3.5, 5.0],
                entry_zone_offset_atr=0.15,
                stop_buffer_atr=0.75,
                stop_lookback_bars=8,
                stop_use_htf_swings=False,
                pd_compliance_required=False, # Speed/Volume focus
                sweep_backing_boost=2.0,      # Heavy focus on liquidity grabs
                sweep_lookback_candles=5,
                # Trend Continuation for Strike (intraday aggressive)
                enable_trend_continuation=True,  # ENABLED: Strike can hold for swing-sized moves
                consolidation_min_duration_candles=8,  # Shorter for intraday speed
                consolidation_min_touches=4,  # Lower bar for faster detection
            )

        elif mode_lower == "swing" or mode_lower == "overwatch":
            return cls(
                min_rr=2.5,  # Higher standard for swing
                target_rr_ladder=[2.0, 4.0, 8.0], # Big runners
                entry_zone_offset_atr=0.25, # Patient entries (limit orders)
                stop_buffer_atr=1.5,   # Wide stops for noise
                stop_lookback_bars=15,
                stop_use_htf_swings=True,   # Use HTF structure for stops
                pd_compliance_required=True,  # Discipline: Only buy Discount / sell Premium
                pd_compliance_tolerance=0.05, # Allow 5% buffer for near-misses
                sweep_backing_boost=1.2,      # Less boost (Structure > Sweeps)
                sweep_lookback_candles=10,
                # Trend Continuation (NEW)
                enable_trend_continuation=True,  # Enable for swing trading
                consolidation_min_duration_candles=12,  # Longer for HTF consolidations
            )
            
        elif mode_lower in ("stealth", "stealth_balanced"):
            # STEALTH: Smart Money / Institutional Shadowing
            # Balanced but with stricter entry requirements (PD + Structure)
            return cls(
                min_rr=2.0,
                target_rr_ladder=[2.0, 3.0, 6.0],
                entry_zone_offset_atr=0.2,
                stop_buffer_atr=1.0,
                stop_lookback_bars=10,
                stop_use_htf_swings=True,
                pd_compliance_required=True,  # Smart money doesn't chase price
                pd_compliance_tolerance=0.05, # Allow 5% buffer
                sweep_backing_boost=1.5,      # Balanced sweep importance
                sweep_lookback_candles=8,
                # Trend Continuation (NEW)
                enable_trend_continuation=True,  # Enable for balanced/swing
                consolidation_min_duration_candles=10,  # Balanced duration
            )

        else:  # "intraday" or default (balanced)
            return cls(
                min_rr=2.0,
                target_rr_ladder=[2.0, 3.0, 5.0],
                entry_zone_offset_atr=0.2,
                stop_buffer_atr=1.0,
                stop_lookback_bars=10,
                stop_use_htf_swings=True,
                pd_compliance_required=False, # Balance opportunity vs location
                sweep_backing_boost=1.5,      # Standard sweep boost
                sweep_lookback_candles=5
            )

