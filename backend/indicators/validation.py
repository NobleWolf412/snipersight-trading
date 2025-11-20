"""
Indicator Validation Module

Validates custom indicator implementations against TA-Lib industry standards.
Provides fallback mechanisms for production safety.

Usage:
    # In tests/CI:
    from backend.indicators.validation import validate_all_indicators
    results = validate_all_indicators(df)
    assert results['all_passed']
    
    # In production with fallback:
    from backend.indicators.validation import compute_indicator_safe
    rsi = compute_indicator_safe('rsi', df, period=14)
"""

import pandas as pd
import numpy as np
from typing import Dict
import logging

logger = logging.getLogger(__name__)

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    logger.warning("TA-Lib not available - validation and fallback disabled")

from backend.indicators.momentum import compute_rsi, compute_stoch_rsi, compute_mfi
from backend.indicators.volatility import compute_atr, compute_bollinger_bands
from backend.indicators.volume import compute_obv


def validate_rsi(df: pd.DataFrame, tolerance: float = 0.1) -> Dict:
    """
    Validate RSI implementation against TA-Lib.
    
    Args:
        df: OHLCV DataFrame
        tolerance: Maximum acceptable absolute difference
        
    Returns:
        dict: Validation results
    """
    if not TALIB_AVAILABLE:
        return {'indicator': 'RSI', 'skipped': True, 'reason': 'TA-Lib not available'}
    
    try:
        our_rsi = compute_rsi(df, period=14)
        talib_rsi = pd.Series(talib.RSI(df['close'].values, timeperiod=14), index=df.index)
        
        # Compare only valid (non-NaN) values
        valid_mask = ~(our_rsi.isna() | talib_rsi.isna())
        
        if valid_mask.sum() == 0:
            return {
                'indicator': 'RSI',
                'passed': False,
                'error': 'No valid values to compare'
            }
        
        our_valid = our_rsi[valid_mask]
        talib_valid = talib_rsi[valid_mask]
        
        diff = np.abs(our_valid - talib_valid)
        max_diff = diff.max()
        mean_diff = diff.mean()
        
        return {
            'indicator': 'RSI',
            'max_diff': float(max_diff),
            'mean_diff': float(mean_diff),
            'tolerance': tolerance,
            'passed': max_diff < tolerance,
            'samples': int(valid_mask.sum())
        }
        
    except Exception as e:
        return {
            'indicator': 'RSI',
            'passed': False,
            'error': str(e)
        }


def validate_mfi(df: pd.DataFrame, tolerance: float = 0.1) -> Dict:
    """Validate MFI implementation against TA-Lib."""
    if not TALIB_AVAILABLE:
        return {'indicator': 'MFI', 'skipped': True, 'reason': 'TA-Lib not available'}
    
    try:
        our_mfi = compute_mfi(df, period=14)
        talib_mfi = pd.Series(
            talib.MFI(df['high'].values, df['low'].values, df['close'].values, 
                     df['volume'].values, timeperiod=14),
            index=df.index
        )
        
        valid_mask = ~(our_mfi.isna() | talib_mfi.isna())
        
        if valid_mask.sum() == 0:
            return {'indicator': 'MFI', 'passed': False, 'error': 'No valid values'}
        
        diff = np.abs(our_mfi[valid_mask] - talib_mfi[valid_mask])
        
        return {
            'indicator': 'MFI',
            'max_diff': float(diff.max()),
            'mean_diff': float(diff.mean()),
            'tolerance': tolerance,
            'passed': diff.max() < tolerance,
            'samples': int(valid_mask.sum())
        }
        
    except Exception as e:
        return {'indicator': 'MFI', 'passed': False, 'error': str(e)}


def validate_atr(df: pd.DataFrame, tolerance_pct: float = 0.1) -> Dict:
    """
    Validate ATR implementation against TA-Lib.
    
    Uses percentage difference since ATR is price-dependent.
    """
    if not TALIB_AVAILABLE:
        return {'indicator': 'ATR', 'skipped': True, 'reason': 'TA-Lib not available'}
    
    try:
        our_atr = compute_atr(df, period=14)
        talib_atr = pd.Series(
            talib.ATR(df['high'].values, df['low'].values, df['close'].values, timeperiod=14),
            index=df.index
        )
        
        valid_mask = ~(our_atr.isna() | talib_atr.isna())
        
        if valid_mask.sum() == 0:
            return {'indicator': 'ATR', 'passed': False, 'error': 'No valid values'}
        
        our_valid = our_atr[valid_mask]
        talib_valid = talib_atr[valid_mask]
        
        # Percentage difference
        pct_diff = np.abs((our_valid - talib_valid) / talib_valid) * 100
        
        return {
            'indicator': 'ATR',
            'max_pct_diff': float(pct_diff.max()),
            'mean_pct_diff': float(pct_diff.mean()),
            'tolerance_pct': tolerance_pct,
            'passed': pct_diff.max() < tolerance_pct,
            'samples': int(valid_mask.sum())
        }
        
    except Exception as e:
        return {'indicator': 'ATR', 'passed': False, 'error': str(e)}


def validate_bollinger_bands(df: pd.DataFrame, tolerance: float = 0.01) -> Dict:
    """Validate Bollinger Bands implementation against TA-Lib."""
    if not TALIB_AVAILABLE:
        return {'indicator': 'BBANDS', 'skipped': True, 'reason': 'TA-Lib not available'}
    
    try:
        our_upper, our_mid, our_lower = compute_bollinger_bands(df, period=20, std_dev=2.0)
        talib_upper, talib_mid, talib_lower = talib.BBANDS(
            df['close'].values, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0
        )
        
        talib_upper = pd.Series(talib_upper, index=df.index)
        talib_mid = pd.Series(talib_mid, index=df.index)
        talib_lower = pd.Series(talib_lower, index=df.index)
        
        valid_mask = ~(our_upper.isna() | talib_upper.isna())
        
        if valid_mask.sum() == 0:
            return {'indicator': 'BBANDS', 'passed': False, 'error': 'No valid values'}
        
        # Check all three bands
        upper_diff = np.abs((our_upper[valid_mask] - talib_upper[valid_mask]) / talib_upper[valid_mask]) * 100
        mid_diff = np.abs((our_mid[valid_mask] - talib_mid[valid_mask]) / talib_mid[valid_mask]) * 100
        lower_diff = np.abs((our_lower[valid_mask] - talib_lower[valid_mask]) / talib_lower[valid_mask]) * 100
        
        max_diff = max(upper_diff.max(), mid_diff.max(), lower_diff.max())
        
        return {
            'indicator': 'BBANDS',
            'max_pct_diff': float(max_diff),
            'upper_diff': float(upper_diff.mean()),
            'mid_diff': float(mid_diff.mean()),
            'lower_diff': float(lower_diff.mean()),
            'tolerance_pct': tolerance,
            'passed': max_diff < tolerance,
            'samples': int(valid_mask.sum())
        }
        
    except Exception as e:
        return {'indicator': 'BBANDS', 'passed': False, 'error': str(e)}


def validate_obv(df: pd.DataFrame, tolerance: float = 1.0) -> Dict:
    """Validate OBV implementation against TA-Lib."""
    if not TALIB_AVAILABLE:
        return {'indicator': 'OBV', 'skipped': True, 'reason': 'TA-Lib not available'}
    
    try:
        our_obv = compute_obv(df)
        talib_obv = pd.Series(talib.OBV(df['close'].values, df['volume'].values), index=df.index)
        
        valid_mask = ~(our_obv.isna() | talib_obv.isna())
        
        if valid_mask.sum() == 0:
            return {'indicator': 'OBV', 'passed': False, 'error': 'No valid values'}
        
        # OBV is cumulative, check percentage difference
        pct_diff = np.abs((our_obv[valid_mask] - talib_obv[valid_mask]) / talib_obv[valid_mask]) * 100
        
        return {
            'indicator': 'OBV',
            'max_pct_diff': float(pct_diff.max()),
            'mean_pct_diff': float(pct_diff.mean()),
            'tolerance_pct': tolerance,
            'passed': pct_diff.max() < tolerance,
            'samples': int(valid_mask.sum())
        }
        
    except Exception as e:
        return {'indicator': 'OBV', 'passed': False, 'error': str(e)}


def validate_all_indicators(df: pd.DataFrame) -> Dict:
    """
    Run complete validation suite against TA-Lib.
    
    Args:
        df: OHLCV DataFrame with DatetimeIndex
        
    Returns:
        dict: Complete validation results
    """
    if not TALIB_AVAILABLE:
        return {
            'timestamp': pd.Timestamp.now().isoformat(),
            'talib_available': False,
            'error': 'TA-Lib not installed - validation skipped'
        }
    
    results = {
        'timestamp': pd.Timestamp.now().isoformat(),
        'talib_available': True,
        'data_points': len(df),
        'validations': []
    }
    
    # Run all validations
    validators = [
        validate_rsi,
        validate_mfi,
        validate_atr,
        validate_bollinger_bands,
        validate_obv
    ]
    
    for validator in validators:
        try:
            result = validator(df)
            results['validations'].append(result)
        except Exception as e:
            results['validations'].append({
                'indicator': validator.__name__.replace('validate_', '').upper(),
                'passed': False,
                'error': str(e)
            })
    
    # Overall pass/fail
    passed_validations = [
        v for v in results['validations'] 
        if v.get('passed', False)
    ]
    
    total_validations = [
        v for v in results['validations']
        if not v.get('skipped', False)
    ]
    
    results['passed_count'] = len(passed_validations)
    results['total_count'] = len(total_validations)
    results['all_passed'] = len(passed_validations) == len(total_validations) and len(total_validations) > 0
    
    return results


# --- Fallback Functions ---

def talib_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """TA-Lib RSI fallback."""
    if not TALIB_AVAILABLE:
        raise ImportError("TA-Lib not available for fallback")
    return pd.Series(talib.RSI(df['close'].values, timeperiod=period), index=df.index)


def talib_mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """TA-Lib MFI fallback."""
    if not TALIB_AVAILABLE:
        raise ImportError("TA-Lib not available for fallback")
    return pd.Series(
        talib.MFI(df['high'].values, df['low'].values, df['close'].values, 
                 df['volume'].values, timeperiod=period),
        index=df.index
    )


def talib_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """TA-Lib ATR fallback."""
    if not TALIB_AVAILABLE:
        raise ImportError("TA-Lib not available for fallback")
    return pd.Series(
        talib.ATR(df['high'].values, df['low'].values, df['close'].values, timeperiod=period),
        index=df.index
    )


def talib_bbands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> tuple:
    """TA-Lib Bollinger Bands fallback."""
    if not TALIB_AVAILABLE:
        raise ImportError("TA-Lib not available for fallback")
    upper, mid, lower = talib.BBANDS(
        df['close'].values, timeperiod=period, nbdevup=std_dev, nbdevdn=std_dev, matype=0
    )
    return (
        pd.Series(upper, index=df.index),
        pd.Series(mid, index=df.index),
        pd.Series(lower, index=df.index)
    )


def talib_obv(df: pd.DataFrame) -> pd.Series:
    """TA-Lib OBV fallback."""
    if not TALIB_AVAILABLE:
        raise ImportError("TA-Lib not available for fallback")
    return pd.Series(talib.OBV(df['close'].values, df['volume'].values), index=df.index)


def compute_indicator_safe(
    indicator: str,
    df: pd.DataFrame,
    use_fallback: bool = True,
    **kwargs
) -> pd.Series:
    """
    Compute indicator with automatic fallback to TA-Lib on failure.
    
    Args:
        indicator: Indicator name ('rsi', 'mfi', 'atr', 'obv')
        df: OHLCV DataFrame
        use_fallback: Whether to use TA-Lib fallback on error
        **kwargs: Indicator-specific parameters
        
    Returns:
        pd.Series: Indicator values
        
    Raises:
        ValueError: If indicator name unknown
        Exception: If computation fails and fallback disabled/unavailable
    """
    indicator_map = {
        'rsi': (compute_rsi, talib_rsi),
        'mfi': (compute_mfi, talib_mfi),
        'atr': (compute_atr, talib_atr),
        'obv': (compute_obv, talib_obv)
    }
    
    if indicator not in indicator_map:
        raise ValueError(f"Unknown indicator: {indicator}. Available: {list(indicator_map.keys())}")
    
    custom_func, fallback_func = indicator_map[indicator]
    
    try:
        # Try custom implementation
        result = custom_func(df, **kwargs)
        
        # Sanity check
        if result.isna().all():
            raise ValueError(f"{indicator} returned all NaN values")
        
        return result
        
    except Exception as e:
        if use_fallback and TALIB_AVAILABLE:
            logger.warning(f"Custom {indicator} failed: {e}. Using TA-Lib fallback")
            try:
                return fallback_func(df, **kwargs)
            except Exception as fallback_error:
                logger.error(f"TA-Lib fallback also failed: {fallback_error}")
                raise
        else:
            logger.error(f"{indicator} computation failed and fallback unavailable")
            raise


def compute_bbands_safe(
    df: pd.DataFrame,
    period: int = 20,
    std_dev: float = 2.0,
    use_fallback: bool = True
) -> tuple:
    """
    Compute Bollinger Bands with automatic fallback.
    
    Returns:
        tuple: (upper, middle, lower) as pd.Series
    """
    try:
        result = compute_bollinger_bands(df, period=period, std_dev=std_dev)
        
        # Sanity check
        if any(band.isna().all() for band in result):
            raise ValueError("Bollinger Bands returned all NaN values")
        
        return result
        
    except Exception as e:
        if use_fallback and TALIB_AVAILABLE:
            logger.warning(f"Custom Bollinger Bands failed: {e}. Using TA-Lib fallback")
            try:
                return talib_bbands(df, period=period, std_dev=std_dev)
            except Exception as fallback_error:
                logger.error(f"TA-Lib fallback also failed: {fallback_error}")
                raise
        else:
            logger.error("Bollinger Bands computation failed and fallback unavailable")
            raise
