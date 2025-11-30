"""
Momentum Indicators Module

Implements technical momentum indicators:
- RSI (Relative Strength Index)
- Stochastic RSI
- MFI (Money Flow Index)
- MACD (Moving Average Convergence Divergence)

All functions return pandas Series with proper index alignment.
"""

from typing import Tuple
import pandas as pd
import numpy as np


def compute_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Compute Relative Strength Index (RSI).
    
    RSI measures the magnitude of recent price changes to evaluate
    overbought or oversold conditions.
    
    Args:
        df: DataFrame with 'close' column
        period: RSI period (default 14)
        
    Returns:
        pd.Series: RSI values (0-100)
        
    Raises:
        ValueError: If df is too short or missing required columns
    """
    if len(df) < period + 1:
        raise ValueError(f"DataFrame too short for RSI calculation (need {period + 1} rows, got {len(df)})")
    
    if 'close' not in df.columns:
        raise ValueError("DataFrame must contain 'close' column")
    
    # Calculate price changes
    delta = df['close'].diff()
    
    # Separate gains and losses
    gains = delta.where(delta > 0, 0.0)
    losses = -delta.where(delta < 0, 0.0)
    
    # Calculate exponential moving averages
    avg_gains = gains.ewm(span=period, adjust=False).mean()
    avg_losses = losses.ewm(span=period, adjust=False).mean()
    
    # Calculate RS and RSI
    rs = avg_gains / avg_losses
    rsi = 100 - (100 / (1 + rs))
    
    # Handle division by zero (when avg_losses is 0)
    rsi = rsi.fillna(100)
    
    return rsi


def compute_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Compute MACD (Moving Average Convergence Divergence).

    Returns MACD line, signal line, and histogram.

    Args:
        df: DataFrame with 'close' column
        fast: Fast EMA period (default 12)
        slow: Slow EMA period (default 26)
        signal: Signal EMA period (default 9)

    Returns:
        Tuple[pd.Series, pd.Series, pd.Series]: (macd_line, signal_line, histogram)

    Raises:
        ValueError: If df is too short or missing required columns
    """
    if 'close' not in df.columns:
        raise ValueError("DataFrame must contain 'close' column")
    min_len = max(fast, slow) + signal + 1
    if len(df) < min_len:
        raise ValueError(f"DataFrame too short for MACD (need {min_len} rows, got {len(df)})")

    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def compute_stoch_rsi(
    df: pd.DataFrame, 
    rsi_period: int = 14,
    stoch_period: int = 14,
    smooth_k: int = 3,
    smooth_d: int = 3
) -> Tuple[pd.Series, pd.Series]:
    """
    Compute Stochastic RSI (K and D lines).
    
    Stochastic RSI applies the Stochastic oscillator formula to RSI values,
    creating a more sensitive momentum indicator.
    
    Args:
        df: DataFrame with 'close' column
        rsi_period: Period for RSI calculation (default 14)
        stoch_period: Period for Stochastic calculation (default 14)
        smooth_k: Smoothing period for %K (default 3)
        smooth_d: Smoothing period for %D (default 3)
        
    Returns:
        Tuple[pd.Series, pd.Series]: (%K, %D) both ranging 0-100
        
    Raises:
        ValueError: If df is too short or missing required columns
    """
    min_length = rsi_period + stoch_period + smooth_k + smooth_d
    if len(df) < min_length:
        raise ValueError(f"DataFrame too short for Stoch RSI (need {min_length} rows, got {len(df)})")
    
    # Calculate RSI first
    rsi = compute_rsi(df, period=rsi_period)
    
    # Calculate Stochastic on RSI values
    rsi_min = rsi.rolling(window=stoch_period).min()
    rsi_max = rsi.rolling(window=stoch_period).max()
    
    # Stochastic formula
    stoch_rsi = ((rsi - rsi_min) / (rsi_max - rsi_min)) * 100
    
    # Handle division by zero (when range is 0)
    stoch_rsi = stoch_rsi.fillna(50)
    
    # Smooth %K
    stoch_k = stoch_rsi.rolling(window=smooth_k).mean()
    
    # %D is moving average of %K
    stoch_d = stoch_k.rolling(window=smooth_d).mean()
    
    return stoch_k, stoch_d


def compute_mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Compute Money Flow Index (MFI).
    
    MFI is a volume-weighted RSI that measures buying and selling pressure.
    
    Args:
        df: DataFrame with 'high', 'low', 'close', 'volume' columns
        period: MFI period (default 14)
        
    Returns:
        pd.Series: MFI values (0-100)
        
    Raises:
        ValueError: If df is too short or missing required columns
    """
    required_cols = ['high', 'low', 'close', 'volume']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"DataFrame missing required columns: {missing_cols}")
    
    if len(df) < period + 1:
        raise ValueError(f"DataFrame too short for MFI calculation (need {period + 1} rows, got {len(df)})")
    
    # Calculate typical price
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    
    # Calculate raw money flow
    money_flow = typical_price * df['volume']
    
    # Determine positive and negative money flow
    price_change = typical_price.diff()
    positive_flow = money_flow.where(price_change > 0, 0.0)
    negative_flow = money_flow.where(price_change < 0, 0.0)
    
    # Sum over the period
    positive_mf_sum = positive_flow.rolling(window=period).sum()
    negative_mf_sum = negative_flow.rolling(window=period).sum()
    
    # Calculate money flow ratio
    mf_ratio = positive_mf_sum / negative_mf_sum
    
    # Calculate MFI
    mfi = 100 - (100 / (1 + mf_ratio))
    
    # Handle division by zero (when negative_mf_sum is 0)
    mfi = mfi.fillna(100)
    
    return mfi


def validate_momentum_indicators(df: pd.DataFrame) -> dict:
    """
    Validate momentum indicators for debugging purposes.
    
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
        rsi = compute_rsi(df)
        results['rsi_latest'] = rsi.iloc[-1] if len(rsi) > 0 else None
        
        if rsi.isna().all():
            results['errors'].append("RSI returned all NaN values")
            results['valid'] = False
        elif rsi.isna().sum() > len(rsi) * 0.3:
            results['warnings'].append(f"RSI has {rsi.isna().sum()} NaN values ({rsi.isna().sum()/len(rsi)*100:.1f}%)")
            
    except Exception as e:
        results['errors'].append(f"RSI calculation failed: {str(e)}")
        results['valid'] = False
    
    try:
        stoch_k, stoch_d = compute_stoch_rsi(df)
        results['stoch_k_latest'] = stoch_k.iloc[-1] if len(stoch_k) > 0 else None
        results['stoch_d_latest'] = stoch_d.iloc[-1] if len(stoch_d) > 0 else None
        
        if stoch_k.isna().all() or stoch_d.isna().all():
            results['errors'].append("Stoch RSI returned all NaN values")
            results['valid'] = False
            
    except Exception as e:
        results['errors'].append(f"Stoch RSI calculation failed: {str(e)}")
        results['valid'] = False
    
    try:
        mfi = compute_mfi(df)
        results['mfi_latest'] = mfi.iloc[-1] if len(mfi) > 0 else None
        
        if mfi.isna().all():
            results['errors'].append("MFI returned all NaN values")
            results['valid'] = False
            
    except Exception as e:
        results['errors'].append(f"MFI calculation failed: {str(e)}")
        results['valid'] = False
    
    return results


def compute_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Compute MACD (Moving Average Convergence Divergence).

    Returns MACD line, signal line, and histogram.

    Args:
        df: DataFrame with 'close' column
        fast: Fast EMA period (default 12)
        slow: Slow EMA period (default 26)
        signal: Signal EMA period (default 9)

    Returns:
        Tuple[pd.Series, pd.Series, pd.Series]: (macd_line, signal_line, histogram)

    Raises:
        ValueError: If df is too short or missing required columns
    """
    if 'close' not in df.columns:
        raise ValueError("DataFrame must contain 'close' column")
    min_len = max(fast, slow) + signal + 1
    if len(df) < min_len:
        raise ValueError(f"DataFrame too short for MACD (need {min_len} rows, got {len(df)})")

    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram
