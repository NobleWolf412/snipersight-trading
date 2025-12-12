"""SMC (Smart Money Concepts) configuration module.

Centralizes all tunable parameters for SMC pattern detectors so they can be
externally configured (API / UI) and versioned. This replaces scattered
hardcoded magic numbers inside individual detector modules.

Initial extraction focuses on existing parameters used in:
 - Order Blocks
 - Fair Value Gaps
 - Structural Breaks (BOS / CHoCH)
 - Liquidity Sweeps

Future extensions can add sequence detection, HTF alignment thresholds,
and decay constants. Validation is intentionally light: we ensure values
are non-negative and within simple bounds where applicable.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional


# ============================================================================
# TIMEFRAME-AWARE LOOKBACK SCALING
# ============================================================================
# 
# The core insight: a "7 candle lookback" means very different things:
#   5m chart:  7 candles =  35 minutes (noise!)
#   4H chart:  7 candles =  28 hours   (short-term)
#   1D chart:  7 candles =   1 week    (significant)
#   1W chart:  7 candles =  ~2 months  (major swings)
#
# Solution: Scale lookbacks based on timeframe to ensure we're looking at
# equivalent "significance" of price action regardless of timeframe.

# Timeframe minutes mapping
TIMEFRAME_MINUTES: Dict[str, int] = {
    '1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30,
    '1h': 60, '1H': 60,
    '2h': 120, '2H': 120,
    '4h': 240, '4H': 240,
    '6h': 360, '6H': 360,
    '8h': 480, '8H': 480,
    '12h': 720, '12H': 720,
    '1d': 1440, '1D': 1440,
    '3d': 4320, '3D': 4320,
    '1w': 10080, '1W': 10080,
}

# Lookback multipliers by timeframe category
# LTF (5m-15m): More candles needed to filter noise
# MTF (1H-4H): Balanced lookback
# HTF (1D+): Fewer candles - each one is significant
LOOKBACK_MULTIPLIERS: Dict[str, float] = {
    '1m': 3.0,   # Very noisy - need 3x lookback
    '3m': 2.5,
    '5m': 2.5,   # Noisy - need 2.5x lookback
    '15m': 2.0,  # Still noisy - need 2x lookback
    '30m': 1.5,
    '1h': 1.3, '1H': 1.3,
    '2h': 1.2, '2H': 1.2,
    '4h': 1.0, '4H': 1.0,   # Base reference (multiplier = 1.0)
    '6h': 1.0, '6H': 1.0,
    '8h': 0.9, '8H': 0.9,
    '12h': 0.8, '12H': 0.8,
    '1d': 0.7, '1D': 0.7,   # Each candle is significant
    '3d': 0.6, '3D': 0.6,
    '1w': 0.5, '1W': 0.5,   # Major swings only
}


# ============================================================================
# EQUAL HIGHS/LOWS TIMEFRAME SCALING
# ============================================================================
#
# Lower timeframes have more noise, so we need:
#   - TIGHTER tolerance (to avoid false clusters from noise)
#   - MORE touches required (to filter retail chop)
#
# Higher timeframes have cleaner structure, so we can use:
#   - LOOSER tolerance (swings are more spread out in price terms)
#   - FEWER touches required (each HTF swing is significant)

# Tolerance scaling: LTF = tighter (0.5x), HTF = looser (1.5x)
EQHL_TOLERANCE_SCALING: Dict[str, float] = {
    '1m': 0.4,   # Very tight: 0.08% if base is 0.2%
    '3m': 0.5,
    '5m': 0.5,   # Tight: 0.1%
    '15m': 0.75, # Moderate: 0.15%
    '30m': 0.9,
    '1h': 1.0, '1H': 1.0,   # Base: 0.2%
    '2h': 1.1, '2H': 1.1,
    '4h': 1.25, '4H': 1.25, # Looser: 0.25%
    '6h': 1.3, '6H': 1.3,
    '8h': 1.4, '8H': 1.4,
    '12h': 1.5, '12H': 1.5,
    '1d': 1.5, '1D': 1.5,   # Looser: 0.3%
    '3d': 1.75, '3D': 1.75,
    '1w': 2.0, '1W': 2.0,   # Loosest: 0.4%
}

# Minimum touch requirements by timeframe
# LTF needs MORE touches to filter noise, HTF needs FEWER (each is significant)
EQHL_MIN_TOUCHES: Dict[str, int] = {
    '1m': 5,   # Very noisy - need 5 touches minimum
    '3m': 4,
    '5m': 4,   # Need 4 touches to be meaningful
    '15m': 3,  # 3 touches
    '30m': 3,
    '1h': 3, '1H': 3,
    '2h': 2, '2H': 2,
    '4h': 2, '4H': 2,   # Base: 2 touches
    '6h': 2, '6H': 2,
    '8h': 2, '8H': 2,
    '12h': 2, '12H': 2,
    '1d': 2, '1D': 2,   # Daily: 2 touches (each is significant)
    '3d': 2, '3D': 2,
    '1w': 2, '1W': 2,   # Weekly: 2 touches
}


def get_timeframe_minutes(timeframe: str) -> int:
    """Get minutes for a timeframe string."""
    return TIMEFRAME_MINUTES.get(timeframe, 240)  # Default to 4H


def get_lookback_multiplier(timeframe: str) -> float:
    """
    Get lookback multiplier for a timeframe.
    
    Returns multiplier to scale base lookback values:
    - LTF (5m-15m): 2.0-2.5x (more candles to filter noise)
    - MTF (1H-4H): 1.0-1.3x (balanced)
    - HTF (1D+): 0.5-0.7x (fewer candles, each is significant)
    """
    return LOOKBACK_MULTIPLIERS.get(timeframe, 1.0)


def scale_lookback(base_lookback: int, timeframe: str, min_lookback: int = 3, max_lookback: int = 50) -> int:
    """
    Scale a base lookback value for a specific timeframe.
    
    Args:
        base_lookback: Base lookback (calibrated for 4H)
        timeframe: Timeframe string (e.g., '15m', '4H', '1D')
        min_lookback: Minimum lookback (safety floor)
        max_lookback: Maximum lookback (prevent excessive computation)
        
    Returns:
        Scaled lookback value, clamped to [min, max]
        
    Example:
        scale_lookback(7, '5m')  -> 17  (7 * 2.5 = 17.5 -> 17)
        scale_lookback(7, '4H')  ->  7  (7 * 1.0 = 7)
        scale_lookback(7, '1D')  ->  5  (7 * 0.7 = 4.9 -> 5)
    """
    multiplier = get_lookback_multiplier(timeframe)
    scaled = int(round(base_lookback * multiplier))
    return max(min_lookback, min(max_lookback, scaled))


def get_eqhl_tolerance_scaling(timeframe: str) -> float:
    """
    Get tolerance scaling factor for equal highs/lows detection.
    
    LTF uses tighter tolerance (fewer false clusters from noise).
    HTF uses looser tolerance (swings more spread out).
    
    Args:
        timeframe: Timeframe string
        
    Returns:
        Scaling factor (0.5 = half of base, 2.0 = double base)
    """
    return EQHL_TOLERANCE_SCALING.get(timeframe, 1.0)


def get_eqhl_min_touches(timeframe: str) -> int:
    """
    Get minimum touch requirement for equal highs/lows detection.
    
    LTF needs more touches to filter noise.
    HTF can use fewer touches (each is significant).
    
    Args:
        timeframe: Timeframe string
        
    Returns:
        Minimum number of touches required
    """
    return EQHL_MIN_TOUCHES.get(timeframe, 2)


def scale_eqhl_tolerance(base_tolerance_pct: float, timeframe: str) -> float:
    """
    Scale equal highs/lows tolerance for a specific timeframe.
    
    Args:
        base_tolerance_pct: Base tolerance (e.g., 0.002 = 0.2%)
        timeframe: Timeframe string
        
    Returns:
        Scaled tolerance percentage
        
    Example:
        scale_eqhl_tolerance(0.002, '5m')  -> 0.001  (tighter)
        scale_eqhl_tolerance(0.002, '4H')  -> 0.0025 (base * 1.25)
        scale_eqhl_tolerance(0.002, '1D')  -> 0.003  (looser)
    """
    scaling = get_eqhl_tolerance_scaling(timeframe)
    return base_tolerance_pct * scaling


@dataclass
class SMCConfig:
    # Order Block parameters
    min_wick_ratio: float = 1.5  # Lowered from 2.0 - still requires significant wick
    min_displacement_atr: float = 1.0  # Lowered from 1.5 - more OBs detected
    ob_lookback_candles: int = 7  # Increased from 5 - more time to verify displacement
    ob_volume_threshold: float = 1.3  # Lowered from 1.5 - easier volume confirmation
    ob_max_mitigation: float = 0.85  # Increased from 0.8 - keep slightly more mitigated OBs
    ob_min_freshness: float = 0.05  # Lowered from 0.1 - keep older OBs longer

    # Fair Value Gap parameters
    fvg_min_gap_atr: float = 0.2  # Lowered from 0.3 - detect smaller FVGs
    fvg_max_overlap: float = 0.15  # Increased from 0.1 - allow slightly more overlap

    # Structural Break parameters
    structure_swing_lookback: int = 7  # Increased from 5 - wider search
    structure_min_break_distance_atr: float = 0.4  # Lowered from 0.5 - detect smaller breaks

    # Liquidity Sweep parameters
    sweep_swing_lookback: int = 12  # Increased from 10 - wider search
    sweep_max_sweep_candles: int = 4  # Increased from 3 - more flexible sweep detection
    sweep_min_reversal_atr: float = 0.8  # Lowered from 1.0 - detect smaller reversals
    sweep_require_volume_spike: bool = False

    # Equal Highs/Lows (Liquidity Pool) parameters
    # These identify clustered swing points that represent stop-loss liquidity
    eqhl_base_tolerance_pct: float = 0.002  # Base tolerance (0.2%) - scaled by timeframe
    eqhl_swing_lookback: int = 5  # Base swing detection lookback - scaled by timeframe
    eqhl_min_touches: int = 2  # Base minimum touches - scaled by timeframe
    eqhl_cluster_within_atr: float = 0.3  # Alternative: cluster within 0.3 ATR (more adaptive)
    eqhl_use_atr_tolerance: bool = True  # Use ATR-based tolerance instead of percentage
    eqhl_grade_by_touches: bool = True  # Grade pools by touch count (A=4+, B=3, C=2)

    # Grade thresholds for pattern quality scoring (new grading system)
    # Patterns are graded A/B/C instead of rejected
    grade_a_threshold: float = 1.0   # ATR multiplier for Grade A (excellent)
    grade_b_threshold: float = 0.5   # ATR multiplier for Grade B (good)
    # Below grade_b_threshold = Grade C (marginal but still detected)

    @staticmethod
    def defaults() -> "SMCConfig":
        """Return a fresh default configuration object."""
        return SMCConfig()
    
    @staticmethod
    def luxalgo_strict() -> "SMCConfig":
        """
        LuxAlgo-style strict detection.
        
        Tuned to match the selectivity of LuxAlgo's SMC indicator:
        - Very few BOS/CHoCH (only significant structure breaks)
        - Rare FVGs (only large, unfilled gaps)
        - Only fresh, unmitigated order blocks
        
        Higher grade thresholds mean only the strongest patterns get Grade A.
        """
        return SMCConfig(
            # Order Blocks: Strong rejections, but allow for standard impulse moves
            min_wick_ratio=2.0,           # 2.0x body (was 2.5)
            min_displacement_atr=1.5,      # 1.5 ATR displacement (was 2.0)
            ob_lookback_candles=10,        # Slightly tighter validation (was 15)
            ob_volume_threshold=1.5,       # 1.5x volume (was 1.8)
            ob_max_mitigation=0.75,        # Allow 75% mitigation (was 0.5 - too strict)
            ob_min_freshness=0.1,          # (was 0.2)
            
            # FVGs: Significant gaps, but catch actionable ones
            fvg_min_gap_atr=0.4,           # 0.4 ATR (was 1.0 - filtered everything)
            fvg_max_overlap=0.10,          # Allow small overlap (was 0.05)
            
            # Structure: Major swings
            structure_swing_lookback=20,   # (was 25)
            structure_min_break_distance_atr=1.0,  # 1.0 ATR break (was 1.5)
            
            # Sweeps: Clear liquidity grabs
            sweep_swing_lookback=25,       # (was 30)
            sweep_max_sweep_candles=3,     # (was 2)
            sweep_min_reversal_atr=1.2,    # (was 1.5)
            sweep_require_volume_spike=True,
            
            # Equal Highs/Lows: Strong pools
            eqhl_base_tolerance_pct=0.0015,
            eqhl_swing_lookback=6,           # (was 7)
            eqhl_min_touches=2,              # 2+ touches (was 3 - too rare)
            eqhl_cluster_within_atr=0.25,
            eqhl_use_atr_tolerance=True,
            eqhl_grade_by_touches=True,
            
            # Grade thresholds: High quality
            grade_a_threshold=1.2,         # (was 1.5)
            grade_b_threshold=0.8,         # (was 1.0)
        )
    
    @staticmethod
    def sensitive() -> "SMCConfig":
        """
        Sensitive detection for backtesting and pattern research.
        
        Finds more patterns at the cost of more noise.
        Useful for understanding market structure or backtesting.
        Lower grade thresholds mean more patterns get higher grades.
        """
        return SMCConfig(
            min_wick_ratio=1.5,
            min_displacement_atr=1.0,
            ob_lookback_candles=7,
            ob_volume_threshold=1.2,
            ob_max_mitigation=0.85,
            ob_min_freshness=0.05,
            fvg_min_gap_atr=0.3,
            fvg_max_overlap=0.20,
            structure_swing_lookback=10,
            structure_min_break_distance_atr=0.5,
            sweep_swing_lookback=15,
            sweep_max_sweep_candles=4,
            sweep_min_reversal_atr=0.7,
            sweep_require_volume_spike=False,
            
            # Equal Highs/Lows: Sensitive - detect more pools for research
            eqhl_base_tolerance_pct=0.003,   # Looser base tolerance (0.3%)
            eqhl_swing_lookback=4,           # Shorter swing detection
            eqhl_min_touches=2,              # 2 touches minimum
            eqhl_cluster_within_atr=0.4,     # Looser ATR clustering
            eqhl_use_atr_tolerance=True,
            eqhl_grade_by_touches=True,
            
            # Grade thresholds: Lenient for research
            grade_a_threshold=0.5,         # 0.5x ATR for Grade A
            grade_b_threshold=0.3,         # 0.3x ATR for Grade B
        )

    def validate(self) -> None:
        """Validate configuration values, raising ValueError on invalid entries."""
        numeric_fields = [
            ("min_wick_ratio", self.min_wick_ratio, 0),
            ("min_displacement_atr", self.min_displacement_atr, 0),
            ("ob_lookback_candles", self.ob_lookback_candles, 1),
            ("ob_volume_threshold", self.ob_volume_threshold, 0),
            ("ob_max_mitigation", self.ob_max_mitigation, 0),
            ("ob_min_freshness", self.ob_min_freshness, 0),
            ("fvg_min_gap_atr", self.fvg_min_gap_atr, 0),
            ("fvg_max_overlap", self.fvg_max_overlap, 0),
            ("structure_swing_lookback", self.structure_swing_lookback, 1),
            ("structure_min_break_distance_atr", self.structure_min_break_distance_atr, 0),
            ("sweep_swing_lookback", self.sweep_swing_lookback, 1),
            ("sweep_max_sweep_candles", self.sweep_max_sweep_candles, 1),
            ("sweep_min_reversal_atr", self.sweep_min_reversal_atr, 0),
            ("eqhl_base_tolerance_pct", self.eqhl_base_tolerance_pct, 0),
            ("eqhl_swing_lookback", self.eqhl_swing_lookback, 1),
            ("eqhl_min_touches", self.eqhl_min_touches, 2),
            ("eqhl_cluster_within_atr", self.eqhl_cluster_within_atr, 0),
        ]
        for name, value, minimum in numeric_fields:
            if value < minimum:
                raise ValueError(f"{name} must be >= {minimum}, got {value}")
        if not 0 <= self.ob_max_mitigation <= 1:
            raise ValueError(f"ob_max_mitigation must be between 0 and 1, got {self.ob_max_mitigation}")
        if not 0 <= self.fvg_max_overlap <= 1:
            raise ValueError(f"fvg_max_overlap must be between 0 and 1, got {self.fvg_max_overlap}")
        if not 0 < self.eqhl_base_tolerance_pct < 0.1:
            raise ValueError(f"eqhl_base_tolerance_pct must be between 0 and 0.1 (10%), got {self.eqhl_base_tolerance_pct}")

    def to_dict(self) -> Dict[str, Any]:
        """Return a dict representation suitable for serialization."""
        return asdict(self)

    def get_scaled_lookbacks(self, timeframe: str) -> Dict[str, int]:
        """
        Get all lookback values scaled for a specific timeframe.
        
        Args:
            timeframe: Timeframe string (e.g., '15m', '4H', '1D')
            
        Returns:
            Dict with scaled lookback values for each SMC pattern type
        """
        return {
            'ob_lookback': scale_lookback(self.ob_lookback_candles, timeframe),
            'structure_swing_lookback': scale_lookback(self.structure_swing_lookback, timeframe),
            'sweep_swing_lookback': scale_lookback(self.sweep_swing_lookback, timeframe),
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "SMCConfig":
        """Create configuration from partial dict, applying defaults for missing keys."""
        base = SMCConfig.defaults()
        for key, value in data.items():
            if hasattr(base, key):
                setattr(base, key, value)
        base.validate()
        return base
    
    def calculate_grade(self, atr_ratio: float) -> str:
        """
        Calculate pattern grade based on ATR ratio and this config's thresholds.
        
        Args:
            atr_ratio: The ATR-normalized value (e.g., displacement/ATR)
            
        Returns:
            'A' (excellent), 'B' (good), or 'C' (marginal)
        """
        if atr_ratio >= self.grade_a_threshold:
            return 'A'
        elif atr_ratio >= self.grade_b_threshold:
            return 'B'
        else:
            return 'C'


def get_preset(preset_name: str) -> SMCConfig:
    """
    Get an SMC configuration preset by name.
    
    Args:
        preset_name: One of 'defaults', 'luxalgo_strict', 'sensitive'
        
    Returns:
        SMCConfig instance
    """
    presets = {
        'defaults': SMCConfig.defaults,
        'luxalgo_strict': SMCConfig.luxalgo_strict,
        'sensitive': SMCConfig.sensitive,
    }
    factory = presets.get(preset_name, SMCConfig.defaults)
    return factory()


# ============================================================================
# PRESET-BASED FEATURE CONTROL FOR NEW SMC IMPROVEMENTS
# ============================================================================
# These functions map smc_preset to behavior of Phase 1 refactored features.

def get_swing_dedup_config(preset: str) -> dict:
    """
    Get swing deduplication configuration for a preset.
    
    Args:
        preset: 'luxalgo_strict', 'defaults', or 'sensitive'
        
    Returns:
        dict with:
            - enabled: Whether to use deduplication
            - strict: If True, only keep the most extreme swing
            - lookback_scaling: Multiplier for swing lookback
    """
    configs = {
        'luxalgo_strict': {
            'enabled': True,
            'strict': True,  # Only keep extreme swings
            'lookback_scaling': 1.2,  # Wider lookback for HTF-style patterns
        },
        'defaults': {
            'enabled': True,
            'strict': True,
            'lookback_scaling': 1.0,
        },
        'sensitive': {
            'enabled': True,
            'strict': False,  # Keep more swings for research
            'lookback_scaling': 0.8,  # Shorter lookback
        },
    }
    return configs.get(preset, configs['defaults'])


def get_4swing_pattern_config(preset: str) -> dict:
    """
    Get 4-swing BOS/CHoCH pattern configuration for a preset.
    
    Args:
        preset: 'luxalgo_strict', 'defaults', or 'sensitive'
        
    Returns:
        dict with:
            - require_pattern: If True, BOS/CHoCH MUST have valid 4-swing pattern
            - allow_partial: If True, incomplete patterns can still generate signals
    """
    configs = {
        'luxalgo_strict': {
            'require_pattern': True,    # Must have proper 4-swing pattern
            'allow_partial': False,     # No partial patterns
        },
        'defaults': {
            'require_pattern': True,    # Use pattern validation
            'allow_partial': True,      # Allow partial patterns as lower-grade
        },
        'sensitive': {
            'require_pattern': False,   # Legacy detection (more signals)
            'allow_partial': True,
        },
    }
    return configs.get(preset, configs['defaults'])


def get_structural_ob_config(preset: str) -> dict:
    """
    Get structural OB detection configuration for a preset.
    
    Controls whether to use the "last candle before BOS" method.
    
    Args:
        preset: 'luxalgo_strict', 'defaults', or 'sensitive'
        
    Returns:
        dict with:
            - use_structural: Use structural method
            - use_rejection: Use rejection-wick method
            - prefer_structural: When both detect same zone, use structural grade
            - volume_imbalance_threshold: % threshold for grade boost (lower = stricter)
    """
    configs = {
        'luxalgo_strict': {
            'use_structural': True,
            'use_rejection': True,
            'prefer_structural': True,       # Structural is primary
            'volume_imbalance_threshold': 25.0,  # Stricter threshold
        },
        'defaults': {
            'use_structural': True,
            'use_rejection': True,
            'prefer_structural': False,      # Both weighted equally
            'volume_imbalance_threshold': 35.0,
        },
        'sensitive': {
            'use_structural': True,
            'use_rejection': True,
            'prefer_structural': False,
            'volume_imbalance_threshold': 45.0,  # More lenient
        },
    }
    return configs.get(preset, configs['defaults'])


def get_enhanced_mitigation_config(preset: str) -> dict:
    """
    Get enhanced mitigation tracking configuration for a preset.
    
    Controls how mitigation grading affects OB validity.
    
    Args:
        preset: 'luxalgo_strict', 'defaults', or 'sensitive'
        
    Returns:
        dict with:
            - use_enhanced: Use new check_mitigation_enhanced() function
            - invalidate_on_deep_tap: Invalidate OB on deep (>70%) penetration
            - max_taps_before_invalidate: Max taps before OB considered weak
    """
    configs = {
        'luxalgo_strict': {
            'use_enhanced': True,
            'invalidate_on_deep_tap': True,
            'max_taps_before_invalidate': 2,  # Strict: 2 taps max
        },
        'defaults': {
            'use_enhanced': True,
            'invalidate_on_deep_tap': True,
            'max_taps_before_invalidate': 3,
        },
        'sensitive': {
            'use_enhanced': True,
            'invalidate_on_deep_tap': False,  # Keep more OBs for research
            'max_taps_before_invalidate': 5,
        },
    }
    return configs.get(preset, configs['defaults'])

