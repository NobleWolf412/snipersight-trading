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


@dataclass
class SMCConfig:
    # Order Block parameters
    min_wick_ratio: float = 2.0  # Require significant rejection wick (2x body)
    min_displacement_atr: float = 1.5  # Strong displacement required
    ob_lookback_candles: int = 10  # Wider lookback for OB displacement check
    ob_volume_threshold: float = 1.5  # Require volume spike for valid OB
    ob_max_mitigation: float = 0.75  # Reject heavily mitigated OBs
    ob_min_freshness: float = 0.1  # Require reasonably fresh OBs

    # Fair Value Gap parameters
    fvg_min_gap_atr: float = 0.5  # Only significant FVGs (0.5 ATR minimum)
    fvg_max_overlap: float = 0.10  # Strict overlap tolerance

    # Structural Break parameters
    structure_swing_lookback: int = 15  # Wider lookback catches real swings, not noise
    structure_min_break_distance_atr: float = 1.0  # Only count significant breaks (1 ATR)

    # Liquidity Sweep parameters
    sweep_swing_lookback: int = 20  # Wider search for sweep targets
    sweep_max_sweep_candles: int = 3  # Tight sweep window
    sweep_min_reversal_atr: float = 1.0  # Require meaningful reversal
    sweep_require_volume_spike: bool = False  # Keep flexible for now

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
        
        Expect ~1-2% of candles to have structure labels.
        """
        return SMCConfig(
            # Order Blocks: Only strong rejections with clear displacement
            min_wick_ratio=2.5,           # 2.5x body minimum (strong rejection)
            min_displacement_atr=2.0,      # 2 ATR displacement required
            ob_lookback_candles=15,        # Wider window for displacement verification
            ob_volume_threshold=1.8,       # Require significant volume spike
            ob_max_mitigation=0.5,         # Only 50% mitigated max (very fresh)
            ob_min_freshness=0.2,          # Must be recent
            
            # FVGs: Only large, significant imbalances
            fvg_min_gap_atr=1.0,           # Full ATR gap minimum (rare)
            fvg_max_overlap=0.05,          # Almost no overlap allowed
            
            # Structure: Only major swing breaks
            structure_swing_lookback=25,   # Look for significant swings
            structure_min_break_distance_atr=1.5,  # 1.5 ATR break required
            
            # Sweeps: Clear liquidity grabs only
            sweep_swing_lookback=30,
            sweep_max_sweep_candles=2,     # Tight window
            sweep_min_reversal_atr=1.5,    # Strong reversal required
            sweep_require_volume_spike=True  # Must have volume confirmation
        )
    
    @staticmethod
    def sensitive() -> "SMCConfig":
        """
        Sensitive detection for backtesting and pattern research.
        
        Finds more patterns at the cost of more noise.
        Useful for understanding market structure or backtesting.
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
            sweep_require_volume_spike=False
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
        ]
        for name, value, minimum in numeric_fields:
            if value < minimum:
                raise ValueError(f"{name} must be >= {minimum}, got {value}")
        if not 0 <= self.ob_max_mitigation <= 1:
            raise ValueError(f"ob_max_mitigation must be between 0 and 1, got {self.ob_max_mitigation}")
        if not 0 <= self.fvg_max_overlap <= 1:
            raise ValueError(f"fvg_max_overlap must be between 0 and 1, got {self.fvg_max_overlap}")

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
