"""
Volume Indicators Module

Implements volume-based indicators:
- Volume Spike Detection
- OBV (On-Balance Volume)
- Volume-Weighted Average Price (VWAP)

All functions return pandas Series with proper index alignment.
"""

import pandas as pd
import numpy as np
import logging

from backend.indicators.validation_utils import validate_ohlcv, DataValidationError

logger = logging.getLogger(__name__)


# Anomaly threshold: volumes exceeding this multiple are flagged as potential data errors
VOLUME_ANOMALY_THRESHOLD = 100.0


def detect_volume_spike(
    df: pd.DataFrame, 
    threshold: float = 2.0,
    lookback: int = 20,
    anomaly_threshold: float = VOLUME_ANOMALY_THRESHOLD,
    flag_anomalies: bool = True
) -> pd.Series:
    """
    Detect volume spikes with anomaly detection.
    
    A volume spike occurs when current volume exceeds the rolling average
    by the specified threshold multiplier. Optionally flags extreme outliers
    that may indicate data errors.
    
    Args:
        df: DataFrame with 'volume' column
        threshold: Multiplier for average volume (default 2.0)
        lookback: Rolling window for average calculation (default 20)
        anomaly_threshold: Upper bound multiplier to flag potential data errors (default 100.0)
        flag_anomalies: If True, log warnings for anomalous volumes (default True)
        
    Returns:
        pd.Series: Boolean series indicating volume spikes (excludes anomalies)
        
    Raises:
        ValueError: If df is too short or missing required columns
    """
    if 'volume' not in df.columns:
        raise ValueError("DataFrame must contain 'volume' column")
    
    if len(df) < lookback:
        raise ValueError(f"DataFrame too short for volume spike detection (need {lookback} rows, got {len(df)})")
    
    # Calculate rolling average volume
    avg_volume = df['volume'].rolling(window=lookback).mean()
    
    # Calculate relative volume
    relative_volume = df['volume'] / avg_volume
    
    # Detect anomalies (potential data errors)
    anomalies = relative_volume > anomaly_threshold
    if flag_anomalies and anomalies.any():
        anomaly_count = anomalies.sum()
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"Volume anomaly detected: {anomaly_count} bar(s) with volume >{anomaly_threshold}x average. "
            f"Max ratio: {relative_volume.max():.1f}x. These may be data errors."
        )
    
    # Detect legitimate spikes: above threshold but below anomaly threshold
    volume_spikes = (relative_volume > threshold) & (relative_volume <= anomaly_threshold)
    
    return volume_spikes


def detect_volume_spike_with_metadata(
    df: pd.DataFrame,
    threshold: float = 2.0,
    lookback: int = 20,
    anomaly_threshold: float = VOLUME_ANOMALY_THRESHOLD
) -> dict:
    """
    Detect volume spikes and return detailed metadata.
    
    Args:
        df: DataFrame with 'volume' column
        threshold: Multiplier for average volume (default 2.0)
        lookback: Rolling window for average calculation (default 20)
        anomaly_threshold: Upper bound multiplier for anomaly detection
        
    Returns:
        dict with keys:
            - spikes: Boolean series of legitimate spikes
            - anomalies: Boolean series of potential data errors
            - relative_volume: Series of volume/average ratios
            - avg_volume: Rolling average volume series
    """
    if 'volume' not in df.columns:
        raise ValueError("DataFrame must contain 'volume' column")
    
    if len(df) < lookback:
        raise ValueError(f"DataFrame too short for volume spike detection (need {lookback} rows, got {len(df)})")
    
    avg_volume = df['volume'].rolling(window=lookback).mean()
    relative_volume = df['volume'] / avg_volume
    
    return {
        'spikes': (relative_volume > threshold) & (relative_volume <= anomaly_threshold),
        'anomalies': relative_volume > anomaly_threshold,
        'relative_volume': relative_volume,
        'avg_volume': avg_volume,
    }


def compute_obv(df: pd.DataFrame) -> pd.Series:
    """
    Compute On-Balance Volume (OBV).
    
    OBV is a cumulative indicator that adds volume on up days and
    subtracts volume on down days.
    
    Args:
        df: DataFrame with 'close' and 'volume' columns
        
    Returns:
        pd.Series: Cumulative OBV values
        
    Raises:
        ValueError: If df is missing required columns
    """
    required_cols = ['close', 'volume']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"DataFrame missing required columns: {missing_cols}")
    
    if len(df) < 2:
        raise ValueError(f"DataFrame too short for OBV calculation (need at least 2 rows, got {len(df)})")
    
    # Calculate price direction
    price_change = df['close'].diff()
    
    # Assign volume based on price direction
    # Up day: +volume, Down day: -volume, No change: 0
    signed_volume = df['volume'].copy()
    signed_volume[price_change < 0] = -df['volume']
    signed_volume[price_change == 0] = 0
    
    # Cumulative sum
    obv = signed_volume.cumsum()
    
    return obv


def compute_vwap(df: pd.DataFrame, reset_period: str = None) -> pd.Series:
    """
    Compute Volume-Weighted Average Price (VWAP).
    
    VWAP is the average price weighted by volume. It can be reset
    periodically (e.g., daily for intraday data).
    
    Args:
        df: DataFrame with 'high', 'low', 'close', 'volume' columns
        reset_period: Resampling period for VWAP reset (e.g., 'D' for daily)
                     If None, VWAP is cumulative
        
    Returns:
        pd.Series: VWAP values
        
    Raises:
        ValueError: If df is missing required columns
    """
    required_cols = ['high', 'low', 'close', 'volume']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"DataFrame missing required columns: {missing_cols}")
    
    if len(df) < 1:
        raise ValueError("DataFrame must contain at least 1 row")
    
    # Calculate typical price
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    
    # Calculate price * volume
    pv = typical_price * df['volume']
    
    if reset_period:
        # Reset VWAP at specified period
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame must have DatetimeIndex for period-based VWAP")
        
        # Group by period and calculate VWAP within each group
        grouped = df.groupby(pd.Grouper(freq=reset_period))
        vwap_groups = []
        
        for _, group in grouped:
            if len(group) > 0:
                group_tp = (group['high'] + group['low'] + group['close']) / 3
                group_pv = group_tp * group['volume']
                group_vwap = group_pv.cumsum() / group['volume'].cumsum()
                vwap_groups.append(group_vwap)
        
        vwap = pd.concat(vwap_groups)
    else:
        # Cumulative VWAP
        vwap = pv.cumsum() / df['volume'].cumsum()
    
    return vwap


def compute_volume_profile(
    df: pd.DataFrame,
    price_bins: int = 50,
    lookback: int = None
) -> pd.DataFrame:
    """
    Compute Volume Profile (Volume at Price).
    
    Aggregates volume traded at different price levels.
    
    Args:
        df: DataFrame with 'high', 'low', 'close', 'volume' columns
        price_bins: Number of price bins (default 50)
        lookback: Number of bars to include (None = all bars)
        
    Returns:
        pd.DataFrame: Volume profile with 'price_level' and 'volume' columns
        
    Raises:
        ValueError: If df is missing required columns
    """
    required_cols = ['high', 'low', 'close', 'volume']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"DataFrame missing required columns: {missing_cols}")
    
    # Use lookback window if specified
    data = df.tail(lookback) if lookback else df
    
    if len(data) < 1:
        raise ValueError("DataFrame must contain at least 1 row")
    
    # Determine price range
    min_price = data['low'].min()
    max_price = data['high'].max()
    
    # Create price bins
    price_bins_array = np.linspace(min_price, max_price, price_bins + 1)
    
    # Allocate volume to price levels
    volume_at_price = np.zeros(price_bins)
    
    for _, row in data.iterrows():
        # Find which bins this candle overlaps
        low_bin = np.digitize(row['low'], price_bins_array) - 1
        high_bin = np.digitize(row['high'], price_bins_array) - 1
        
        # Distribute volume across bins (simplified: equal distribution)
        bins_touched = max(1, high_bin - low_bin + 1)
        volume_per_bin = row['volume'] / bins_touched
        
        for bin_idx in range(max(0, low_bin), min(price_bins, high_bin + 1)):
            volume_at_price[bin_idx] += volume_per_bin
    
    # Create result DataFrame
    price_levels = (price_bins_array[:-1] + price_bins_array[1:]) / 2
    volume_profile = pd.DataFrame({
        'price_level': price_levels,
        'volume': volume_at_price
    })
    
    return volume_profile


def compute_relative_volume(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    Compute Relative Volume (RVOL).
    
    RVOL compares current volume to average volume over a period.
    
    Args:
        df: DataFrame with 'volume' column
        period: Rolling window for average volume (default 20)
        
    Returns:
        pd.Series: Relative volume ratio (current / average)
        
    Raises:
        ValueError: If df is too short or missing required columns
    """
    if 'volume' not in df.columns:
        raise ValueError("DataFrame must contain 'volume' column")
    
    if len(df) < period:
        raise ValueError(f"DataFrame too short for RVOL calculation (need {period} rows, got {len(df)})")
    
    # Calculate average volume
    avg_volume = df['volume'].rolling(window=period).mean()
    
    # Relative volume
    rvol = df['volume'] / avg_volume
    
    return rvol


def validate_volume_indicators(df: pd.DataFrame) -> dict:
    """
    Validate volume indicators for debugging purposes.
    
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
        spikes = detect_volume_spike(df)
        spike_count = spikes.sum()
        results['volume_spike_count'] = int(spike_count)
        results['volume_spike_latest'] = bool(spikes.iloc[-1]) if len(spikes) > 0 else None
        
        if spike_count == 0:
            results['warnings'].append("No volume spikes detected in dataset")
            
    except Exception as e:
        results['errors'].append(f"Volume spike detection failed: {str(e)}")
        results['valid'] = False
    
    try:
        obv = compute_obv(df)
        results['obv_latest'] = float(obv.iloc[-1]) if len(obv) > 0 and not pd.isna(obv.iloc[-1]) else None
        
        if obv.isna().all():
            results['errors'].append("OBV returned all NaN values")
            results['valid'] = False
            
    except Exception as e:
        results['errors'].append(f"OBV calculation failed: {str(e)}")
        results['valid'] = False
    
    try:
        rvol = compute_relative_volume(df)
        results['rvol_latest'] = float(rvol.iloc[-1]) if len(rvol) > 0 and not pd.isna(rvol.iloc[-1]) else None
        
        if rvol.isna().all():
            results['errors'].append("RVOL returned all NaN values")
            results['valid'] = False
            
    except Exception as e:
        results['errors'].append(f"RVOL calculation failed: {str(e)}")
        results['valid'] = False
    
    return results
