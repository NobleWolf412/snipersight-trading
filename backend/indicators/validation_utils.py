"""
OHLCV Data Validation Utilities

Provides centralized input validation for indicator calculations to catch
data quality issues early and prevent NaN propagation through the pipeline.
"""

from typing import Optional
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class DataValidationError(ValueError):
    """Raised when OHLCV data fails validation checks."""


def validate_ohlcv(
    df: pd.DataFrame,
    require_volume: bool = True,
    check_nan: bool = True,
    check_positive_prices: bool = True,
    check_candle_integrity: bool = True,
    check_positive_volume: bool = True,
    min_rows: Optional[int] = None,
    raise_on_error: bool = True,
) -> dict:
    """
    Validate OHLCV DataFrame before indicator calculation.

    Performs comprehensive data quality checks to catch issues early
    rather than letting NaN values propagate through calculations.

    Args:
        df: DataFrame with OHLCV columns
        require_volume: If True, require 'volume' column (default True)
        check_nan: If True, check for NaN values in price columns (default True)
        check_positive_prices: If True, verify H/L/C > 0 (default True)
        check_candle_integrity: If True, verify high >= low (default True)
        check_positive_volume: If True, verify volume >= 0 (default True)
        min_rows: Minimum required rows (None = no minimum)
        raise_on_error: If True, raise DataValidationError; else return dict

    Returns:
        dict with validation results:
            - valid: bool indicating if all checks passed
            - errors: list of error messages
            - warnings: list of warning messages

    Raises:
        DataValidationError: If validation fails and raise_on_error=True
    """
    result = {"valid": True, "errors": [], "warnings": []}

    # Check required columns
    required_price_cols = ["high", "low", "close"]
    if require_volume:
        required_price_cols.append("volume")

    missing_cols = [col for col in required_price_cols if col not in df.columns]
    if missing_cols:
        result["errors"].append(f"Missing required columns: {missing_cols}")
        result["valid"] = False

    # Early exit if missing columns
    if not result["valid"]:
        if raise_on_error:
            raise DataValidationError("; ".join(result["errors"]))
        return result

    # Check minimum rows
    if min_rows is not None and len(df) < min_rows:
        result["errors"].append(f"DataFrame too short: need {min_rows} rows, got {len(df)}")
        result["valid"] = False

    # Check for NaN values in price columns
    if check_nan:
        price_cols = ["high", "low", "close"]
        if "open" in df.columns:
            price_cols.insert(0, "open")

        for col in price_cols:
            if col in df.columns:
                nan_count = df[col].isna().sum()
                if nan_count > 0:
                    nan_pct = (nan_count / len(df)) * 100
                    if nan_pct > 10:
                        result["errors"].append(
                            f"Column '{col}' has {nan_count} NaN values ({nan_pct:.1f}%)"
                        )
                        result["valid"] = False
                    else:
                        result["warnings"].append(
                            f"Column '{col}' has {nan_count} NaN values ({nan_pct:.1f}%)"
                        )

    # Check for positive prices
    if check_positive_prices:
        for col in ["high", "low", "close"]:
            if col in df.columns:
                non_positive = (df[col] <= 0).sum()
                if non_positive > 0:
                    result["errors"].append(
                        f"Column '{col}' has {non_positive} non-positive values"
                    )
                    result["valid"] = False

    # Check candle integrity (high >= low)
    if check_candle_integrity and "high" in df.columns and "low" in df.columns:
        inverted = (df["high"] < df["low"]).sum()
        if inverted > 0:
            result["errors"].append(
                f"Found {inverted} inverted candles (high < low) - data corruption suspected"
            )
            result["valid"] = False

    # Check for positive volume
    if check_positive_volume and "volume" in df.columns:
        negative_volume = (df["volume"] < 0).sum()
        if negative_volume > 0:
            result["errors"].append(f"Found {negative_volume} negative volume values")
            result["valid"] = False

        zero_volume = (df["volume"] == 0).sum()
        if zero_volume > 0:
            zero_pct = (zero_volume / len(df)) * 100
            if zero_pct > 80:
                result["errors"].append(
                    f"Found {zero_volume} zero volume bars ({zero_pct:.1f}%) - possible data issue"
                )
                result["valid"] = False
            elif zero_pct > 10:
                result["warnings"].append(f"Found {zero_volume} zero volume bars ({zero_pct:.1f}%)")

    if raise_on_error and not result["valid"]:
        raise DataValidationError("; ".join(result["errors"]))

    return result


def validate_series(
    series: pd.Series,
    name: str = "series",
    check_nan: bool = True,
    check_positive: bool = False,
    check_range: Optional[tuple] = None,
    min_length: Optional[int] = None,
    raise_on_error: bool = True,
) -> dict:
    """
    Validate a pandas Series for indicator inputs/outputs.

    Args:
        series: Series to validate
        name: Name for error messages
        check_nan: If True, check for NaN values
        check_positive: If True, verify all values > 0
        check_range: Optional (min, max) tuple to verify range
        min_length: Minimum required length
        raise_on_error: If True, raise DataValidationError; else return dict

    Returns:
        dict with validation results

    Raises:
        DataValidationError: If validation fails and raise_on_error=True
    """
    result = {"valid": True, "errors": [], "warnings": []}

    if min_length is not None and len(series) < min_length:
        result["errors"].append(f"{name}: need {min_length} values, got {len(series)}")
        result["valid"] = False

    if check_nan:
        nan_count = series.isna().sum()
        if nan_count > 0:
            nan_pct = (nan_count / len(series)) * 100
            if nan_pct > 10:
                result["errors"].append(f"{name} has {nan_count} NaN values ({nan_pct:.1f}%)")
                result["valid"] = False
            else:
                result["warnings"].append(f"{name} has {nan_count} NaN values ({nan_pct:.1f}%)")

    if check_positive:
        non_positive = (series <= 0).sum()
        if non_positive > 0:
            result["errors"].append(f"{name} has {non_positive} non-positive values")
            result["valid"] = False

    if check_range is not None:
        min_val, max_val = check_range
        out_of_range = ((series < min_val) | (series > max_val)).sum()
        if out_of_range > 0:
            result["errors"].append(
                f"{name} has {out_of_range} values outside range [{min_val}, {max_val}]"
            )
            result["valid"] = False

    if raise_on_error and not result["valid"]:
        raise DataValidationError("; ".join(result["errors"]))

    return result


def clean_ohlcv(
    df: pd.DataFrame,
    fill_method: str = "ffill",
    remove_zero_volume: bool = False,
    log_changes: bool = True,
) -> pd.DataFrame:
    """
    Clean OHLCV data by handling NaN values and other issues.

    Use this for data preprocessing before indicator calculation
    when you want to attempt recovery rather than fail.

    Args:
        df: DataFrame with OHLCV columns
        fill_method: Method to fill NaN values ('ffill', 'bfill', 'interpolate')
        remove_zero_volume: If True, remove rows with zero volume
        log_changes: If True, log what was cleaned

    Returns:
        Cleaned DataFrame copy
    """
    df_clean = df.copy()
    changes = []

    # Handle NaN in price columns
    price_cols = [col for col in ["open", "high", "low", "close"] if col in df_clean.columns]
    for col in price_cols:
        nan_count = df_clean[col].isna().sum()
        if nan_count > 0:
            if fill_method == "ffill":
                df_clean[col] = df_clean[col].ffill()
            elif fill_method == "bfill":
                df_clean[col] = df_clean[col].bfill()
            elif fill_method == "interpolate":
                df_clean[col] = df_clean[col].interpolate()
            changes.append(f"Filled {nan_count} NaN in '{col}'")

    # Handle NaN in volume
    if "volume" in df_clean.columns:
        nan_count = df_clean["volume"].isna().sum()
        if nan_count > 0:
            df_clean["volume"] = df_clean["volume"].fillna(0)
            changes.append(f"Filled {nan_count} NaN in 'volume' with 0")

    # Remove zero volume rows if requested
    if remove_zero_volume and "volume" in df_clean.columns:
        zero_count = (df_clean["volume"] == 0).sum()
        if zero_count > 0:
            df_clean = df_clean[df_clean["volume"] > 0]
            changes.append(f"Removed {zero_count} zero-volume rows")

    # Fix inverted candles (high < low) by swapping
    if "high" in df_clean.columns and "low" in df_clean.columns:
        inverted = df_clean["high"] < df_clean["low"]
        if inverted.any():
            inverted_count = inverted.sum()
            # Swap high and low for inverted candles
            df_clean.loc[inverted, ["high", "low"]] = df_clean.loc[inverted, ["low", "high"]].values
            changes.append(f"Fixed {inverted_count} inverted candles")

    if log_changes and changes:
        logger.info(f"OHLCV cleanup: {'; '.join(changes)}")

    return df_clean
