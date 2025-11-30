"""
Default configuration for SniperSight scanner.

Following ARCHITECTURE.md institutional-grade defaults.
"""
from dataclasses import dataclass
from typing import Tuple


@dataclass
class ScanConfig:
    """Core scanning configuration."""
    profile: str = "balanced"
    timeframes: Tuple[str, ...] = ('1W', '1D', '4H', '1H', '15m', '5m')
    min_confluence_score: float = 65.0
    min_rr_ratio: float = 0.8  # Temporarily lowered for testing
    btc_impulse_gate_enabled: bool = True
    max_symbols: int = 20
    max_risk_pct: float = 2.0
    leverage: int = 1  # Added: user-selected leverage to allow planner adaptive buffers/targets
    
    # Planner-specific knobs (wired from scanner mode)
    primary_planning_timeframe: str = "4H"
    max_pullback_atr: float = 3.0
    min_stop_atr: float = 1.0
    max_stop_atr: float = 6.0


@dataclass
class GlobalThresholds:
    """Global indicator and analysis thresholds."""
    # ATR multipliers
    atr_stop_multiplier: float = 1.5
    atr_target_multiplier: float = 3.0
    atr_displacement_threshold: float = 2.0
    
    # RSI levels
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    rsi_extreme_oversold: float = 20.0
    rsi_extreme_overbought: float = 80.0
    
    # Volume spike detection
    volume_spike_threshold: float = 2.0  # 2x average volume
    
    # Order block freshness
    ob_max_age_candles: int = 100
    ob_min_displacement_strength: float = 0.7
    
    # FVG size thresholds
    fvg_min_size_atr: float = 0.5


@dataclass
class WindowSizes:
    """Indicator calculation window sizes."""
    # EMA periods
    ema_fast: int = 20
    ema_medium: int = 50
    ema_slow: int = 200
    
    # RSI/Momentum
    rsi_period: int = 14
    stoch_rsi_period: int = 14
    mfi_period: int = 14
    
    # Volatility
    atr_period: int = 14
    bb_period: int = 20
    bb_std: float = 2.0
    
    # Volume
    volume_ma_period: int = 20
    
    # Lookback windows
    structure_lookback: int = 50
    liquidity_lookback: int = 20


# Default instances
DEFAULT_SCAN_CONFIG = ScanConfig()
DEFAULT_THRESHOLDS = GlobalThresholds()
DEFAULT_WINDOWS = WindowSizes()
