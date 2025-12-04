"""
Momentum Indicators Module

Implements technical momentum indicators:
- RSI (Relative Strength Index)
- Stochastic RSI
- MFI (Money Flow Index)
- MACD (Moving Average Convergence Divergence)

All functions return pandas Series with proper index alignment.

Uses pandas-ta for optimized computation when available, with fallback
to manual implementations for environments without the library.
"""

from typing import Tuple
import pandas as pd
import numpy as np
import logging

from backend.indicators.validation_utils import validate_ohlcv, DataValidationError

logger = logging.getLogger(__name__)

# Try to import pandas-ta for optimized indicator computation
try:
    import pandas_ta as ta
    PANDAS_TA_AVAILABLE = True
    logger.debug("pandas-ta available - using optimized indicator computation")
except ImportError:
    ta = None  # type: ignore[assignment]
    PANDAS_TA_AVAILABLE = False
    logger.info("pandas-ta not available - using fallback implementations")


def compute_rsi(df: pd.DataFrame, period: int = 14, validate_input: bool = True) -> pd.Series:
    """
    Compute Relative Strength Index (RSI).
    
    RSI measures the magnitude of recent price changes to evaluate
    overbought or oversold conditions.
    
    Args:
        df: DataFrame with 'close' column
        period: RSI period (default 14)
        validate_input: If True, validate input data (default True)
        
    Returns:
        pd.Series: RSI values (0-100)
        
    Raises:
        ValueError: If df is too short or missing required columns
        DataValidationError: If input data has NaN or invalid values
    """
    if len(df) < period + 1:
        raise ValueError(f"DataFrame too short for RSI calculation (need {period + 1} rows, got {len(df)})")
    
    if 'close' not in df.columns:
        raise ValueError("DataFrame must contain 'close' column")
    
    # Validate input data quality
    if validate_input:
        validate_ohlcv(
            df, 
            require_volume=False, 
            min_rows=period + 1,
            raise_on_error=True
        )
    
    # Use pandas-ta if available (faster, C-optimized under the hood)
    if PANDAS_TA_AVAILABLE:
        result = ta.rsi(df['close'], length=period)
        # pandas-ta returns None on error, handle gracefully
        if result is not None:
            return result
        logger.warning("pandas-ta RSI returned None, falling back to manual implementation")
    
    # Fallback: Manual implementation
    delta = df['close'].diff()
    gains = delta.where(delta > 0, 0.0)
    losses = -delta.where(delta < 0, 0.0)
    avg_gains = gains.ewm(span=period, adjust=False).mean()
    avg_losses = losses.ewm(span=period, adjust=False).mean()
    rs = avg_gains / avg_losses
    rsi = 100 - (100 / (1 + rs))
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

    # Use pandas-ta if available
    if PANDAS_TA_AVAILABLE:
        macd_df = ta.macd(df['close'], fast=fast, slow=slow, signal=signal)
        if macd_df is not None and not macd_df.empty:
            # pandas-ta column naming: MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
            macd_col = f'MACD_{fast}_{slow}_{signal}'
            signal_col = f'MACDs_{fast}_{slow}_{signal}'
            hist_col = f'MACDh_{fast}_{slow}_{signal}'
            
            if all(col in macd_df.columns for col in [macd_col, signal_col, hist_col]):
                return macd_df[macd_col], macd_df[signal_col], macd_df[hist_col]
        logger.warning("pandas-ta MACD failed, falling back to manual implementation")

    # Fallback: Manual implementation
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
    
    if 'close' not in df.columns:
        raise ValueError("DataFrame must contain 'close' column")
    
    # Use pandas-ta if available
    if PANDAS_TA_AVAILABLE:
        stoch_df = ta.stochrsi(df['close'], length=rsi_period, rsi_length=stoch_period, k=smooth_k, d=smooth_d)
        if stoch_df is not None and not stoch_df.empty:
            # pandas-ta column naming: STOCHRSIk_14_14_3_3, STOCHRSId_14_14_3_3
            k_col = f'STOCHRSIk_{rsi_period}_{stoch_period}_{smooth_k}_{smooth_d}'
            d_col = f'STOCHRSId_{rsi_period}_{stoch_period}_{smooth_k}_{smooth_d}'
            
            if k_col in stoch_df.columns and d_col in stoch_df.columns:
                # pandas-ta returns 0-100 already
                return stoch_df[k_col], stoch_df[d_col]
        logger.warning("pandas-ta Stoch RSI failed, falling back to manual implementation")
    
    # Fallback: Manual implementation
    rsi = compute_rsi(df, period=rsi_period, validate_input=False)
    rsi_min = rsi.rolling(window=stoch_period).min()
    rsi_max = rsi.rolling(window=stoch_period).max()
    stoch_rsi = ((rsi - rsi_min) / (rsi_max - rsi_min)) * 100
    stoch_rsi = stoch_rsi.fillna(50)
    stoch_k = stoch_rsi.rolling(window=smooth_k).mean()
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
    
    # Use pandas-ta if available
    if PANDAS_TA_AVAILABLE:
        result = ta.mfi(df['high'], df['low'], df['close'], df['volume'], length=period)
        if result is not None:
            return result
        logger.warning("pandas-ta MFI returned None, falling back to manual implementation")
    
    # Fallback: Manual implementation
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    money_flow = typical_price * df['volume']
    price_change = typical_price.diff()
    positive_flow = money_flow.where(price_change > 0, 0.0)
    negative_flow = money_flow.where(price_change < 0, 0.0)
    positive_mf_sum = positive_flow.rolling(window=period).sum()
    negative_mf_sum = negative_flow.rolling(window=period).sum()
    mf_ratio = positive_mf_sum / negative_mf_sum
    mfi = 100 - (100 / (1 + mf_ratio))
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
        'warnings': [],
        'using_pandas_ta': PANDAS_TA_AVAILABLE
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
