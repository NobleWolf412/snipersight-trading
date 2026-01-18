"""
Trend-following profile configuration.

Momentum weighted, strict HTF alignment.
Following ARCHITECTURE.md profile specifications.
"""

from dataclasses import dataclass
from ..defaults import ScanConfig, GlobalThresholds


@dataclass
class TrendProfile:
    """Trend-following profile - momentum emphasis."""

    scan_config: ScanConfig = ScanConfig(
        timeframes=("1W", "1D", "4H", "1H"),
        min_confluence_score=75.0,
        min_rr_ratio=3.0,
        btc_impulse_gate_enabled=True,
        max_symbols=10,
    )

    thresholds: GlobalThresholds = GlobalThresholds(
        atr_stop_multiplier=2.0,
        atr_target_multiplier=5.0,
        atr_displacement_threshold=2.5,
        volume_spike_threshold=2.5,
        ob_min_displacement_strength=0.85,
    )

    primary_timeframe: str = "1D"
    htf_alignment_required: bool = True
    name: str = "trend"


TREND_PROFILE = TrendProfile()
