"""
Balanced profile configuration.

Moderate thresholds, R:R ≥ 2.5, 4H primary timeframe.
Following ARCHITECTURE.md profile specifications.
"""
from dataclasses import dataclass
from ..defaults import ScanConfig, GlobalThresholds


@dataclass
class BalancedProfile:
    """Balanced trading profile - moderate risk/reward."""
    
    scan_config: ScanConfig = ScanConfig(
        timeframes=('1W', '1D', '4H', '1H', '15m'),
        min_confluence_score=70.0,
        min_rr_ratio=2.5,
        btc_impulse_gate_enabled=True,
        max_symbols=15
    )
    
    thresholds: GlobalThresholds = GlobalThresholds(
        atr_stop_multiplier=1.5,
        atr_target_multiplier=3.5,
        volume_spike_threshold=2.0,
        ob_min_displacement_strength=0.75
    )
    
    primary_timeframe: str = '4H'
    name: str = 'balanced'


BALANCED_PROFILE = BalancedProfile()
