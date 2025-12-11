#!/usr/bin/env python3
"""
Debug script to verify Fibonacci level calculations.

Run: python debug_fib_levels.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

from backend.analysis.fibonacci import calculate_fib_levels, FibLevel, FIB_RATIOS
from backend.analysis.htf_levels import HTFLevelDetector
from backend.data.adapters.phemex import PhemexAdapter


def test_fib_calculation():
    """Test basic Fib calculation with known values."""
    print("\n" + "="*60)
    print("TEST 1: Basic Fibonacci Calculation")
    print("="*60)
    
    # Example: BTC swung from $90,000 to $100,000 (bullish move)
    swing_low = 90000.0
    swing_high = 100000.0
    
    print(f"Swing Low:  ${swing_low:,.2f}")
    print(f"Swing High: ${swing_high:,.2f}")
    print(f"Range:      ${swing_high - swing_low:,.2f}")
    
    # Calculate Fib retracements for bullish trend
    # In bullish trend, price retraces DOWN toward Fib levels = buy zones
    fibs = calculate_fib_levels(
        swing_high=swing_high,
        swing_low=swing_low,
        trend_direction='bullish',
        timeframe='1d'
    )
    
    print("\nFibonacci Retracement Levels (Bullish - Buy Zones):")
    print("-" * 50)
    for fib in fibs:
        golden = "⭐ GOLDEN" if fib.is_golden else ""
        print(f"  {fib.display_ratio:>7} = ${fib.price:,.2f}  {golden}")
    
    # Expected values:
    # 23.6% = 100000 - (10000 * 0.236) = $97,640
    # 38.2% = 100000 - (10000 * 0.382) = $96,180
    # 50.0% = 100000 - (10000 * 0.500) = $95,000
    # 61.8% = 100000 - (10000 * 0.618) = $93,820
    # 78.6% = 100000 - (10000 * 0.786) = $92,140
    
    print("\n✓ Expected values:")
    expected = {
        '23.6%': 97640,
        '38.2%': 96180,
        '50.0%': 95000,
        '61.8%': 93820,
        '78.6%': 92140,
    }
    for label, expected_price in expected.items():
        print(f"  {label} = ${expected_price:,.2f}")
    
    # Validate
    errors = []
    for fib in fibs:
        expected_price = expected.get(fib.display_ratio)
        if expected_price and abs(fib.price - expected_price) > 1:
            errors.append(f"{fib.display_ratio}: got ${fib.price:.2f}, expected ${expected_price:.2f}")
    
    if errors:
        print("\n❌ VALIDATION FAILED:")
        for e in errors:
            print(f"  {e}")
    else:
        print("\n✅ All Fib levels calculated correctly!")


def test_bearish_fib():
    """Test Fib calculation for bearish trend."""
    print("\n" + "="*60)
    print("TEST 2: Bearish Trend Fibonacci (Sell Zones)")
    print("="*60)
    
    # Example: BTC dropped from $100,000 to $90,000 (bearish move)
    swing_high = 100000.0
    swing_low = 90000.0
    
    print(f"Swing High: ${swing_high:,.2f}")
    print(f"Swing Low:  ${swing_low:,.2f}")
    print(f"Range:      ${swing_high - swing_low:,.2f}")
    
    # In bearish trend, price retraces UP toward Fib levels = sell zones
    fibs = calculate_fib_levels(
        swing_high=swing_high,
        swing_low=swing_low,
        trend_direction='bearish',
        timeframe='1d'
    )
    
    print("\nFibonacci Retracement Levels (Bearish - Sell Zones):")
    print("-" * 50)
    for fib in fibs:
        golden = "⭐ GOLDEN" if fib.is_golden else ""
        print(f"  {fib.display_ratio:>7} = ${fib.price:,.2f}  {golden}")
    
    # Expected values (retracement UP from low):
    # 23.6% = 90000 + (10000 * 0.236) = $92,360
    # 38.2% = 90000 + (10000 * 0.382) = $93,820
    # 50.0% = 90000 + (10000 * 0.500) = $95,000
    # 61.8% = 90000 + (10000 * 0.618) = $96,180
    # 78.6% = 90000 + (10000 * 0.786) = $97,860
    print("\n✓ Expected values:")
    expected = {
        '23.6%': 92360,
        '38.2%': 93820,
        '50.0%': 95000,
        '61.8%': 96180,
        '78.6%': 97860,
    }
    for label, expected_price in expected.items():
        print(f"  {label} = ${expected_price:,.2f}")


def test_live_detection():
    """Test live Fib detection with real market data."""
    print("\n" + "="*60)
    print("TEST 3: Live Fib Detection (BTC/USDT)")
    print("="*60)
    
    try:
        adapter = PhemexAdapter()
        detector = HTFLevelDetector(proximity_threshold=3.0)  # 3% threshold
        
        symbol = 'BTC/USDT'
        
        # Fetch data
        ohlcv_data = {}
        for tf in ['4h', '1d']:
            try:
                df = adapter.fetch_ohlcv(symbol, timeframe=tf, limit=100)
                # Adapter returns DataFrame directly
                if df is not None and not df.empty:
                    # Convert timestamp to datetime if needed
                    if 'timestamp' in df.columns and df['timestamp'].dtype != 'datetime64[ns]':
                        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    ohlcv_data[tf] = df
                    print(f"✓ Fetched {len(df)} {tf} candles")
                else:
                    print(f"✗ No data returned for {tf}")
            except Exception as e:
                print(f"✗ Failed to fetch {tf}: {e}")
        
        if not ohlcv_data:
            print("❌ No data available")
            return
        
        # Get current price
        ticker = adapter.fetch_ticker(symbol)
        current_price = ticker.get('last', 0) if ticker else 0
        print(f"\nCurrent Price: ${current_price:,.2f}")
        
        # Detect Fib levels
        fib_levels = detector.detect_fib_levels(symbol, ohlcv_data, current_price)
        
        print(f"\nDetected {len(fib_levels)} Fibonacci Levels:")
        print("-" * 70)
        
        for level in fib_levels[:10]:  # Show top 10
            proximity_indicator = "📍 NEAR" if level.proximity_pct < 2.0 else ""
            golden = "⭐" if level.fib_ratio in [0.382, 0.618] else ""
            print(f"  {level.timeframe:>3} | {level.level_type:>8} | ${level.price:>10,.2f} | {level.proximity_pct:5.2f}% away | {golden} {proximity_indicator}")
        
        # Also show support/resistance levels for comparison
        sr_levels = detector.detect_levels(symbol, ohlcv_data, current_price)
        print(f"\nDetected {len(sr_levels)} Support/Resistance Levels:")
        print("-" * 70)
        for level in sr_levels[:5]:
            print(f"  {level.timeframe:>3} | {level.level_type:>10} | ${level.price:>10,.2f} | {level.proximity_pct:5.2f}% away | Strength: {level.strength:.1f}")
        
        print("\n✅ Live detection completed!")
        
    except Exception as e:
        print(f"❌ Live test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_fib_calculation()
    test_bearish_fib()
    test_live_detection()
    
    print("\n" + "="*60)
    print("DEBUG COMPLETE")
    print("="*60)
