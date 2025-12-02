"""
Volatility Indicators Module

Implements volatility measurement indicators:
- ATR (Average True Range)
- Realized Volatility

All functions return pandas Series with proper index alignment.
"""

import pandas as pd
import numpy as np

from backend.indicators.validation_utils import validate_ohlcv, DataValidationError


def compute_atr(df: pd.DataFrame, period: int = 14, validate_input: bool = True) -> pd.Series:
    """
    Compute Average True Range (ATR).
    
    ATR measures market volatility by calculating the average of true ranges
    over a specified period. True Range is the greatest of:
    - Current High - Current Low
    - |Current High - Previous Close|
    - |Current Low - Previous Close|
    
    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        period: ATR period (default 14)
        validate_input: If True, validate input data (default True)
        
    Returns:
        pd.Series: ATR values
        
    Raises:
        ValueError: If df is too short or missing required columns
        DataValidationError: If input data has NaN or invalid values
    """
    required_cols = ['high', 'low', 'close']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"DataFrame missing required columns: {missing_cols}")
    
    if len(df) < period + 1:
        raise ValueError(f"DataFrame too short for ATR calculation (need {period + 1} rows, got {len(df)})")
    
    # Validate input data quality
    if validate_input:
        validate_ohlcv(
            df, 
            require_volume=False, 
            min_rows=period + 1,
            raise_on_error=True
        )
    
    # Calculate True Range components
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    
    # True Range is the maximum of the three
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    
    # ATR is the exponential moving average of True Range
    atr = true_range.ewm(span=period, adjust=False).mean()
    
    return atr


def compute_realized_volatility(
    df: pd.DataFrame, 
    window: int = 20,
    annualize: bool = True,
    periods_per_year: int = 365
) -> pd.Series:
    """
    Compute Realized Volatility (Historical Volatility).
    
    Measures the standard deviation of logarithmic returns over a rolling window.
    
    Args:
        df: DataFrame with 'close' column
        window: Rolling window size (default 20)
        annualize: Whether to annualize the volatility (default True)
        periods_per_year: Number of periods per year for annualization (default 365 for daily data)
        
    Returns:
        pd.Series: Realized volatility values (percentage if annualized)
        
    Raises:
        ValueError: If df is too short or missing required columns
    """
    if 'close' not in df.columns:
        raise ValueError("DataFrame must contain 'close' column")
    
    if len(df) < window + 1:
        raise ValueError(f"DataFrame too short for volatility calculation (need {window + 1} rows, got {len(df)})")
    
    # Calculate logarithmic returns
    log_returns = np.log(df['close'] / df['close'].shift())
    
    # Calculate rolling standard deviation
    volatility = log_returns.rolling(window=window).std()
    
    # Annualize if requested
    if annualize:
        volatility = volatility * np.sqrt(periods_per_year) * 100  # Convert to percentage
    
    return volatility


def compute_bollinger_bands(
    df: pd.DataFrame,
    period: int = 20,
    std_dev: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Compute Bollinger Bands.
    
    Bollinger Bands consist of:
    - Middle band: Simple Moving Average (SMA)
    - Upper band: SMA + (standard deviation × multiplier)
    - Lower band: SMA - (standard deviation × multiplier)
    
    Args:
        df: DataFrame with 'close' column
        period: Moving average period (default 20)
        std_dev: Standard deviation multiplier (default 2.0)
        
    Returns:
        Tuple[pd.Series, pd.Series, pd.Series]: (upper_band, middle_band, lower_band)
        
    Raises:
        ValueError: If df is too short or missing required columns
    """
    if 'close' not in df.columns:
        raise ValueError("DataFrame must contain 'close' column")
    
    if len(df) < period:
        raise ValueError(f"DataFrame too short for Bollinger Bands (need {period} rows, got {len(df)})")
    
    # Calculate middle band (SMA)
    middle_band = df['close'].rolling(window=period).mean()
    
    # Calculate standard deviation
    std = df['close'].rolling(window=period).std()
    
    # Calculate upper and lower bands
    upper_band = middle_band + (std * std_dev)
    lower_band = middle_band - (std * std_dev)
    
    return upper_band, middle_band, lower_band


def compute_keltner_channels(
    df: pd.DataFrame,
    ema_period: int = 20,
    atr_period: int = 10,
    atr_multiplier: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Compute Keltner Channels.
    
    Keltner Channels use ATR instead of standard deviation:
    - Middle line: EMA
    - Upper channel: EMA + (ATR × multiplier)
    - Lower channel: EMA - (ATR × multiplier)
    
    Args:
        df: DataFrame with OHLC columns
        ema_period: EMA period for middle line (default 20)
        atr_period: ATR period (default 10)
        atr_multiplier: ATR multiplier (default 2.0)
        
    Returns:
        Tuple[pd.Series, pd.Series, pd.Series]: (upper_channel, middle_line, lower_channel)
        
    Raises:
        ValueError: If df is too short or missing required columns
    """
    if 'close' not in df.columns:
        raise ValueError("DataFrame must contain 'close' column")
    
    min_length = max(ema_period, atr_period) + 1
    if len(df) < min_length:
        raise ValueError(f"DataFrame too short for Keltner Channels (need {min_length} rows, got {len(df)})")
    
    # Calculate middle line (EMA)
    middle_line = df['close'].ewm(span=ema_period, adjust=False).mean()
    
    # Calculate ATR
    atr = compute_atr(df, period=atr_period)
    
    # Calculate upper and lower channels
    upper_channel = middle_line + (atr * atr_multiplier)
    lower_channel = middle_line - (atr * atr_multiplier)
    
    return upper_channel, middle_line, lower_channel


def validate_volatility_indicators(df: pd.DataFrame) -> dict:
    """
    Validate volatility indicators for debugging purposes.
    
    Args:
        df: DataFrame with OHLCV data
        
    Returns:
        dict: Validation results with indicator values and diagnostics
    """
    results = {
        'valid': True,
        'errors': [],
        'warnings': []
    }
    
    try:
        atr = compute_atr(df)
        results['atr_latest'] = float(atr.iloc[-1]) if len(atr) > 0 and not pd.isna(atr.iloc[-1]) else None
        
        if atr.isna().all():
            results['errors'].append("ATR returned all NaN values")
            results['valid'] = False
        elif (atr <= 0).any():
            results['warnings'].append("ATR contains zero or negative values")
            
    except Exception as e:
        results['errors'].append(f"ATR calculation failed: {str(e)}")
        results['valid'] = False
    
    try:
        vol = compute_realized_volatility(df)
        results['volatility_latest'] = float(vol.iloc[-1]) if len(vol) > 0 and not pd.isna(vol.iloc[-1]) else None
        
        if vol.isna().all():
            results['errors'].append("Realized volatility returned all NaN values")
            results['valid'] = False
            
    except Exception as e:
        results['errors'].append(f"Realized volatility calculation failed: {str(e)}")
        results['valid'] = False
    
    try:
        bb_upper, bb_mid, bb_lower = compute_bollinger_bands(df)
        results['bb_width'] = float((bb_upper.iloc[-1] - bb_lower.iloc[-1])) if len(bb_upper) > 0 else None
        
        if bb_upper.isna().all() or bb_lower.isna().all():
            results['errors'].append("Bollinger Bands returned all NaN values")
            results['valid'] = False
            
    except Exception as e:
        results['errors'].append(f"Bollinger Bands calculation failed: {str(e)}")
        results['valid'] = False
    
    return results
