"""
Test script for indicator validation against TA-Lib.

Demonstrates the hybrid validation strategy:
1. Run custom indicator implementations
2. Validate against TA-Lib standards
3. Show fallback mechanisms in action

Usage:
    python -m backend.scripts.test_indicator_validation
"""

import pandas as pd
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.indicators.validation import (
    validate_all_indicators,
    compute_indicator_safe,
    compute_bbands_safe,
    TALIB_AVAILABLE,
)


def load_test_data() -> pd.DataFrame:
    """Generate synthetic test data."""
    import numpy as np

    # Generate 100 candles of synthetic BTCUSDT-like data
    timestamps = pd.date_range(end=pd.Timestamp.now(), periods=100, freq="4H")

    # Start at ~60000, add some realistic price movement
    np.random.seed(42)
    close_prices = 60000 + np.cumsum(np.random.randn(100) * 500)

    df = pd.DataFrame(
        {
            "open": close_prices + np.random.randn(100) * 100,
            "high": close_prices + np.abs(np.random.randn(100) * 200),
            "low": close_prices - np.abs(np.random.randn(100) * 200),
            "close": close_prices,
            "volume": np.random.uniform(100, 1000, 100),
        },
        index=timestamps,
    )

    return df


def test_validation_suite():
    """Run full validation suite."""
    print("=" * 80)
    print("INDICATOR VALIDATION TEST")
    print("=" * 80)
    print()

    # Check TA-Lib availability
    print(f"TA-Lib Available: {TALIB_AVAILABLE}")
    if not TALIB_AVAILABLE:
        print("⚠️  TA-Lib not installed - validation will be skipped")
        print("   Install with: pip install TA-Lib")
        print()

    # Load data
    print("Loading test data...")
    df = load_test_data()
    print(f"✓ Loaded {len(df)} candles")
    print()

    # Run validations
    print("Running validation suite...")
    print("-" * 80)

    results = validate_all_indicators(df)

    print(f"Timestamp: {results['timestamp']}")
    print(f"TA-Lib Available: {results['talib_available']}")

    if not results["talib_available"]:
        print(f"Error: {results.get('error', 'Unknown')}")
        return

    print(f"Data Points: {results['data_points']}")
    print()

    # Display individual validation results
    for validation in results["validations"]:
        indicator = validation["indicator"]

        if validation.get("skipped"):
            print(f"⏭️  {indicator}: SKIPPED - {validation.get('reason', 'Unknown')}")
            continue

        if validation.get("error"):
            print(f"❌ {indicator}: ERROR - {validation['error']}")
            continue

        passed = validation.get("passed", False)
        status = "✓ PASSED" if passed else "✗ FAILED"

        print(f"{status} - {indicator}")

        # Show details based on metric type
        if "max_pct_diff" in validation:
            print(f"    Max % Diff: {validation['max_pct_diff']:.4f}%")
            print(f"    Mean % Diff: {validation.get('mean_pct_diff', 0):.4f}%")
            print(
                f"    Tolerance: {validation.get('tolerance_pct', validation.get('tolerance', 0))}%"
            )
        else:
            print(f"    Max Diff: {validation.get('max_diff', 0):.4f}")
            print(f"    Mean Diff: {validation.get('mean_diff', 0):.4f}")
            print(f"    Tolerance: {validation.get('tolerance', 0)}")

        print(f"    Samples: {validation.get('samples', 0)}")
        print()

    # Summary
    print("-" * 80)
    print(f"SUMMARY: {results['passed_count']}/{results['total_count']} validations passed")

    if results["all_passed"]:
        print("✓ All indicators validated successfully against TA-Lib!")
    else:
        print("⚠️  Some validations failed - review custom implementations")

    print()


def test_safe_computation():
    """Test safe computation with fallback."""
    print("=" * 80)
    print("SAFE COMPUTATION WITH FALLBACK TEST")
    print("=" * 80)
    print()

    df = load_test_data()

    print("Testing compute_indicator_safe() with fallback enabled...")
    print()

    # Test RSI
    try:
        rsi = compute_indicator_safe("rsi", df, period=14, use_fallback=True)
        print(f"✓ RSI computed: {rsi.iloc[-1]:.2f} (latest value)")
    except Exception as e:
        print(f"✗ RSI failed: {e}")

    # Test MFI
    try:
        mfi = compute_indicator_safe("mfi", df, period=14, use_fallback=True)
        print(f"✓ MFI computed: {mfi.iloc[-1]:.2f} (latest value)")
    except Exception as e:
        print(f"✗ MFI failed: {e}")

    # Test ATR
    try:
        atr = compute_indicator_safe("atr", df, period=14, use_fallback=True)
        print(f"✓ ATR computed: {atr.iloc[-1]:.2f} (latest value)")
    except Exception as e:
        print(f"✗ ATR failed: {e}")

    # Test BBands
    try:
        upper, mid, lower = compute_bbands_safe(df, period=20, std_dev=2.0, use_fallback=True)
        print(
            f"✓ BBands computed: Upper={upper.iloc[-1]:.2f}, Mid={mid.iloc[-1]:.2f}, Lower={lower.iloc[-1]:.2f}"
        )
    except Exception as e:
        print(f"✗ BBands failed: {e}")

    print()
    print("All safe computations completed!")
    print()


def main():
    """Run all tests."""
    try:
        test_validation_suite()
        test_safe_computation()

        print("=" * 80)
        print("VALIDATION TESTING COMPLETE")
        print("=" * 80)

    except Exception as e:
        print(f"Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
