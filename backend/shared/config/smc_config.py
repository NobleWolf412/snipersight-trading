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
from typing import Dict, Any


@dataclass
class SMCConfig:
    # Order Block parameters
    min_wick_ratio: float = 2.0
    min_displacement_atr: float = 1.5
    ob_lookback_candles: int = 5
    ob_volume_threshold: float = 1.5
    ob_max_mitigation: float = 0.8
    ob_min_freshness: float = 0.1

    # Fair Value Gap parameters
    fvg_min_gap_atr: float = 0.3
    fvg_max_overlap: float = 0.1

    # Structural Break parameters
    structure_swing_lookback: int = 5
    structure_min_break_distance_atr: float = 0.5

    # Liquidity Sweep parameters
    sweep_swing_lookback: int = 10
    sweep_max_sweep_candles: int = 3
    sweep_min_reversal_atr: float = 1.0
    sweep_require_volume_spike: bool = False

    @staticmethod
    def defaults() -> "SMCConfig":
        """Return a fresh default configuration object."""
        return SMCConfig()

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

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "SMCConfig":
        """Create configuration from partial dict, applying defaults for missing keys."""
        base = SMCConfig.defaults()
        for key, value in data.items():
            if hasattr(base, key):
                setattr(base, key, value)
        base.validate()
        return base
