"""
Test script to verify HTF Trend Alignment Fix.

This script tests:
1. Enhanced swing structure trend detection with directional analysis
2. Strict HTF trend alignment enforcement in confluence scoring
3. Proper blocking of counter-trend trades

Expected behavior:
- A LONG signal in a clear 1D/4H downtrend should be heavily penalized or blocked
- A SHORT signal in a clear 1D/4H uptrend should be heavily penalized or blocked
- Aligned trades should receive bonuses
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, '/home/user/snipersight-trading')

from backend.strategy.smc.swing_structure import detect_swing_structure, _determine_trend, SwingPoint
from backend.strategy.confluence.scorer import resolve_timeframe_conflicts
from backend.shared.models.indicators import IndicatorSet, IndicatorSnapshot
from backend.shared.config.defaults import ScanConfig


def create_trending_data(direction='bullish', num_candles=100):
    """
    Create synthetic price data with clear trend.

    Args:
        direction: 'bullish' or 'bearish'
        num_candles: Number of candles to generate

    Returns:
        DataFrame with OHLCV data and clear trend
    """
    dates = pd.date_range(end=datetime.now(), periods=num_candles, freq='1D')

    if direction == 'bullish':
        # Create clear uptrend: rising highs and lows
        base_price = 100
        trend_increment = 0.5  # 0.5% per candle
        noise = 0.02  # 2% noise

        prices = []
        for i in range(num_candles):
            # Uptrend with noise
            trend_price = base_price * (1 + trend_increment * i / 100)
            daily_noise = np.random.uniform(-noise, noise) * trend_price

            open_price = trend_price + daily_noise
            close_price = open_price * (1 + np.random.uniform(-0.01, 0.02))  # Slight bullish bias
            high_price = max(open_price, close_price) * (1 + np.random.uniform(0, 0.01))
            low_price = min(open_price, close_price) * (1 - np.random.uniform(0, 0.01))

            prices.append({
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': np.random.uniform(1000, 2000)
            })
    else:  # bearish
        # Create clear downtrend: falling highs and lows
        base_price = 200
        trend_increment = -0.5  # -0.5% per candle
        noise = 0.02

        prices = []
        for i in range(num_candles):
            # Downtrend with noise
            trend_price = base_price * (1 + trend_increment * i / 100)
            daily_noise = np.random.uniform(-noise, noise) * trend_price

            open_price = trend_price + daily_noise
            close_price = open_price * (1 + np.random.uniform(-0.02, 0.01))  # Slight bearish bias
            high_price = max(open_price, close_price) * (1 + np.random.uniform(0, 0.01))
            low_price = min(open_price, close_price) * (1 - np.random.uniform(0, 0.01))

            prices.append({
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': np.random.uniform(1000, 2000)
            })

    df = pd.DataFrame(prices, index=dates)
    return df


def test_enhanced_trend_detection():
    """Test that enhanced trend detection correctly identifies trends."""
    print("="*80)
    print("TEST 1: Enhanced Swing Structure Trend Detection")
    print("="*80)

    # Test 1: Clear Bullish Trend
    print("\n📈 Test 1a: Clear Bullish Trend (rising highs and lows)")
    bullish_df = create_trending_data(direction='bullish', num_candles=100)
    bullish_structure = detect_swing_structure(bullish_df, lookback=10)

    print(f"   Detected Trend: {bullish_structure.trend}")
    print(f"   Last HH: {bullish_structure.last_hh.price:.2f}" if bullish_structure.last_hh else "   Last HH: None")
    print(f"   Last HL: {bullish_structure.last_hl.price:.2f}" if bullish_structure.last_hl else "   Last HL: None")
    print(f"   Total Swings: {len(bullish_structure.swing_points)}")

    if bullish_structure.trend == 'bullish':
        print("   ✅ PASS: Correctly identified bullish trend")
    else:
        print(f"   ❌ FAIL: Expected 'bullish', got '{bullish_structure.trend}'")

    # Test 2: Clear Bearish Trend
    print("\n📉 Test 1b: Clear Bearish Trend (falling highs and lows)")
    bearish_df = create_trending_data(direction='bearish', num_candles=100)
    bearish_structure = detect_swing_structure(bearish_df, lookback=10)

    print(f"   Detected Trend: {bearish_structure.trend}")
    print(f"   Last LH: {bearish_structure.last_lh.price:.2f}" if bearish_structure.last_lh else "   Last LH: None")
    print(f"   Last LL: {bearish_structure.last_ll.price:.2f}" if bearish_structure.last_ll else "   Last LL: None")
    print(f"   Total Swings: {len(bearish_structure.swing_points)}")

    if bearish_structure.trend == 'bearish':
        print("   ✅ PASS: Correctly identified bearish trend")
    else:
        print(f"   ❌ FAIL: Expected 'bearish', got '{bearish_structure.trend}'")

    return bullish_structure, bearish_structure


def test_htf_alignment_enforcement(bullish_structure, bearish_structure):
    """Test that HTF alignment is strictly enforced."""
    print("\n" + "="*80)
    print("TEST 2: Strict HTF Trend Alignment Enforcement")
    print("="*80)

    # Create mock indicators
    indicators = IndicatorSet(by_timeframe={
        '4h': IndicatorSnapshot(
            timeframe='4h',
            atr=5.0,
            atr_series=[4.5, 4.6, 4.8, 5.0, 5.2]  # Expanding ATR = strong momentum
        ),
        '1d': IndicatorSnapshot(
            timeframe='1d',
            atr=10.0,
            atr_series=[9.0, 9.2, 9.5, 9.8, 10.0]
        )
    })

    config = ScanConfig()

    # Test 2a: LONG signal in bearish HTF (should be blocked/heavily penalized)
    print("\n🔴 Test 2a: Counter-Trend LONG (HTF is bearish)")
    swing_structure_bearish = {
        '4h': {'trend': 'bearish'},
        '1d': {'trend': 'bearish'}
    }

    result_counter_long = resolve_timeframe_conflicts(
        indicators=indicators,
        direction='bullish',
        mode_config=config,
        swing_structure=swing_structure_bearish,
        htf_proximity=None
    )

    print(f"   Resolution: {result_counter_long['resolution']}")
    print(f"   Score Adjustment: {result_counter_long['score_adjustment']:.1f}")
    print(f"   Conflicts: {result_counter_long['conflicts']}")
    print(f"   Reason: {result_counter_long['resolution_reason']}")

    if result_counter_long['resolution'] in ('blocked', 'caution') and result_counter_long['score_adjustment'] < -40:
        print("   ✅ PASS: Counter-trend LONG correctly blocked/heavily penalized")
    else:
        print(f"   ❌ FAIL: Counter-trend LONG should be blocked (got {result_counter_long['resolution']} with {result_counter_long['score_adjustment']:.1f})")

    # Test 2b: SHORT signal in bullish HTF (should be blocked/heavily penalized)
    print("\n🔴 Test 2b: Counter-Trend SHORT (HTF is bullish)")
    swing_structure_bullish = {
        '4h': {'trend': 'bullish'},
        '1d': {'trend': 'bullish'}
    }

    result_counter_short = resolve_timeframe_conflicts(
        indicators=indicators,
        direction='bearish',
        mode_config=config,
        swing_structure=swing_structure_bullish,
        htf_proximity=None
    )

    print(f"   Resolution: {result_counter_short['resolution']}")
    print(f"   Score Adjustment: {result_counter_short['score_adjustment']:.1f}")
    print(f"   Conflicts: {result_counter_short['conflicts']}")
    print(f"   Reason: {result_counter_short['resolution_reason']}")

    if result_counter_short['resolution'] in ('blocked', 'caution') and result_counter_short['score_adjustment'] < -40:
        print("   ✅ PASS: Counter-trend SHORT correctly blocked/heavily penalized")
    else:
        print(f"   ❌ FAIL: Counter-trend SHORT should be blocked (got {result_counter_short['resolution']} with {result_counter_short['score_adjustment']:.1f})")

    # Test 2c: LONG signal in bullish HTF (should be allowed with bonus)
    print("\n🟢 Test 2c: Aligned LONG (HTF is bullish)")
    result_aligned_long = resolve_timeframe_conflicts(
        indicators=indicators,
        direction='bullish',
        mode_config=config,
        swing_structure=swing_structure_bullish,
        htf_proximity=None
    )

    print(f"   Resolution: {result_aligned_long['resolution']}")
    print(f"   Score Adjustment: {result_aligned_long['score_adjustment']:.1f}")
    print(f"   Conflicts: {result_aligned_long['conflicts']}")
    print(f"   Reason: {result_aligned_long['resolution_reason']}")

    if result_aligned_long['resolution'] == 'allowed' and result_aligned_long['score_adjustment'] > 0:
        print("   ✅ PASS: Aligned LONG correctly allowed with bonus")
    else:
        print(f"   ⚠️  WARNING: Aligned LONG should receive bonus (got {result_aligned_long['resolution']} with {result_aligned_long['score_adjustment']:.1f})")

    # Test 2d: SHORT signal in bearish HTF (should be allowed with bonus)
    print("\n🟢 Test 2d: Aligned SHORT (HTF is bearish)")
    result_aligned_short = resolve_timeframe_conflicts(
        indicators=indicators,
        direction='bearish',
        mode_config=config,
        swing_structure=swing_structure_bearish,
        htf_proximity=None
    )

    print(f"   Resolution: {result_aligned_short['resolution']}")
    print(f"   Score Adjustment: {result_aligned_short['score_adjustment']:.1f}")
    print(f"   Conflicts: {result_aligned_short['conflicts']}")
    print(f"   Reason: {result_aligned_short['resolution_reason']}")

    if result_aligned_short['resolution'] == 'allowed' and result_aligned_short['score_adjustment'] > 0:
        print("   ✅ PASS: Aligned SHORT correctly allowed with bonus")
    else:
        print(f"   ⚠️  WARNING: Aligned SHORT should receive bonus (got {result_aligned_short['resolution']} with {result_aligned_short['score_adjustment']:.1f})")

    # Test 2e: Counter-trend with major HTF structure (exception case)
    print("\n🟡 Test 2e: Counter-Trend LONG with HTF Structure Exception")
    htf_proximity_at_structure = {
        'valid': True,
        'proximity_atr': 0.3,  # Within 0.5 ATR threshold
        'nearest_structure': '1d bullish OB'
    }

    result_exception = resolve_timeframe_conflicts(
        indicators=indicators,
        direction='bullish',
        mode_config=config,
        swing_structure=swing_structure_bearish,
        htf_proximity=htf_proximity_at_structure
    )

    print(f"   Resolution: {result_exception['resolution']}")
    print(f"   Score Adjustment: {result_exception['score_adjustment']:.1f}")
    print(f"   Conflicts: {result_exception['conflicts']}")
    print(f"   Reason: {result_exception['resolution_reason']}")

    if result_exception['resolution'] == 'caution' and -50 < result_exception['score_adjustment'] < -10:
        print("   ✅ PASS: HTF structure exception reduces penalty but doesn't fully allow")
    else:
        print(f"   ⚠️  INFO: Exception case adjusted penalty (got {result_exception['resolution']} with {result_exception['score_adjustment']:.1f})")


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("HTF TREND ALIGNMENT FIX - VERIFICATION TESTS")
    print("="*80)
    print("\nThis test suite verifies that the scanner pipeline correctly:")
    print("1. Detects HTF trends with enhanced directional analysis")
    print("2. Strictly enforces HTF trend alignment (analyst-grade)")
    print("3. Blocks/penalizes counter-trend trades appropriately")
    print("4. Rewards trend-aligned trades")
    print("")

    try:
        # Test 1: Trend Detection
        bullish_struct, bearish_struct = test_enhanced_trend_detection()

        # Test 2: HTF Alignment Enforcement
        test_htf_alignment_enforcement(bullish_struct, bearish_struct)

        print("\n" + "="*80)
        print("TEST SUITE COMPLETE")
        print("="*80)
        print("\n✅ All tests completed. Review results above.")
        print("\nExpected behavior:")
        print("  • Clear trends should be correctly identified")
        print("  • Counter-trend trades should get -40 to -60 penalty (blocked or caution)")
        print("  • Aligned trades should get +10 to +20 bonus")
        print("  • HTF structure exceptions should reduce (but not eliminate) penalties")

    except Exception as e:
        print(f"\n❌ TEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
