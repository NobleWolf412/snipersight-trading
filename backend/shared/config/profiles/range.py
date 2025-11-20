"""
Range/mean-reversion profile configuration.

Tighter entries, oscillator-heavy.
Following ARCHITECTURE.md profile specifications.
"""
from dataclasses import dataclass
from ..defaults import ScanConfig, GlobalThresholds


@dataclass
class RangeProfile:
    """Range-trading profile - mean reversion focus."""
    
    scan_config: ScanConfig = ScanConfig(
        timeframes=('1D', '4H', '1H', '15m', '5m'),
        min_confluence_score=65.0,
        min_rr_ratio=2.0,
        btc_impulse_gate_enabled=False,
        max_symbols=20
    )
    
    thresholds: GlobalThresholds = GlobalThresholds(
        atr_stop_multiplier=1.0,
        atr_target_multiplier=2.0,
        rsi_oversold=25.0,
        rsi_overbought=75.0,
        volume_spike_threshold=1.5,
        ob_min_displacement_strength=0.6
    )
    
    primary_timeframe: str = '1H'
    oscillator_weight: float = 0.4  # Higher weight on RSI/Stoch
    name: str = 'range'


RANGE_PROFILE = RangeProfile()
