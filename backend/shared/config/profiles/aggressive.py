"""
Aggressive profile configuration.

Lower thresholds, higher leverage, 15m/5m bias.
Following ARCHITECTURE.md profile specifications.
"""
from dataclasses import dataclass
from ..defaults import ScanConfig, GlobalThresholds


@dataclass
class AggressiveProfile:
    """Aggressive trading profile - lower timeframe scalping."""
    
    scan_config: ScanConfig = ScanConfig(
        timeframes=('4H', '1H', '15m', '5m'),
        min_confluence_score=60.0,
        min_rr_ratio=2.0,
        btc_impulse_gate_enabled=False,
        max_symbols=30
    )
    
    thresholds: GlobalThresholds = GlobalThresholds(
        atr_stop_multiplier=1.2,
        atr_target_multiplier=2.5,
        volume_spike_threshold=1.8,
        ob_min_displacement_strength=0.65,
        ob_max_age_candles=50
    )
    
    primary_timeframe: str = '15m'
    max_leverage: float = 10.0
    freshness_weight: float = 0.3  # Higher emphasis on recent signals
    name: str = 'aggressive'


AGGRESSIVE_PROFILE = AggressiveProfile()
