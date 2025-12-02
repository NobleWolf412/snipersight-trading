"""
Technical Indicators Package

Provides:
- Momentum indicators (RSI, MACD, StochRSI, MFI)
- Volatility indicators (ATR, Bollinger Bands, Keltner Channels)
- Volume indicators (Volume Spike, OBV, VWAP, RVOL)
- Data validation utilities

All indicator functions follow consistent patterns:
- Accept pandas DataFrame with OHLCV columns
- Return pandas Series or tuple of Series
- Raise ValueError for insufficient data or missing columns
"""

from backend.indicators.momentum import (
    compute_rsi,
    compute_macd,
    compute_stoch_rsi,
    compute_mfi,
    validate_momentum_indicators,
)

from backend.indicators.volatility import (
    compute_atr,
    compute_bollinger_bands,
    compute_keltner_channels,
    compute_realized_volatility,
    validate_volatility_indicators,
)

from backend.indicators.volume import (
    detect_volume_spike,
    detect_volume_spike_with_metadata,
    compute_obv,
    compute_vwap,
    compute_volume_profile,
    compute_relative_volume,
    validate_volume_indicators,
    VOLUME_ANOMALY_THRESHOLD,
)

from backend.indicators.validation_utils import (
    validate_ohlcv,
    validate_series,
    clean_ohlcv,
    DataValidationError,
)

__all__ = [
    # Momentum
    'compute_rsi',
    'compute_macd',
    'compute_stoch_rsi',
    'compute_mfi',
    'validate_momentum_indicators',
    # Volatility
    'compute_atr',
    'compute_bollinger_bands',
    'compute_keltner_channels',
    'compute_realized_volatility',
    'validate_volatility_indicators',
    # Volume
    'detect_volume_spike',
    'detect_volume_spike_with_metadata',
    'compute_obv',
    'compute_vwap',
    'compute_volume_profile',
    'compute_relative_volume',
    'validate_volume_indicators',
    'VOLUME_ANOMALY_THRESHOLD',
    # Validation
    'validate_ohlcv',
    'validate_series',
    'clean_ohlcv',
    'DataValidationError',
]
