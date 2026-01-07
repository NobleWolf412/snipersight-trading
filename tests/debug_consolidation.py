
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from backend.strategy.smc.consolidation_detector import detect_consolidations

def create_consolidation_data(length=20, base_price=100.0, range_pct=0.01, breakout_idx=None):
    """
    Creates synthetic OHLCV data with a consolidation.
    """
    dates = [datetime.now() - timedelta(minutes=15 * (length - i)) for i in range(length)]
    
    # Create oscillating price within range
    highs = []
    lows = []
    opens = []
    closes = []
    
    half_range = base_price * range_pct / 2
    
    for i in range(length):
        if breakout_idx and i >= breakout_idx:
            # Bullish breakout
            mid = base_price + (base_price * range_pct * 2) # Jump up
            h = mid + 0.1
            l = mid - 0.1
            o = mid - 0.05
            c = mid + 0.05
        else:
            # Oscillation
            if i % 2 == 0:
                mid = base_price + half_range * 0.9 # Resistance test
            else:
                mid = base_price - half_range * 0.9 # Support test
                
            h = mid + 0.1
            l = mid - 0.1
            o = mid - 0.05
            c = mid + 0.05

        highs.append(h)
        lows.append(l)
        opens.append(o)
        closes.append(c)

    df = pd.DataFrame({
        'timestamp': dates,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': [1000] * length
    })
    return df

print("="*60)
print("TESTING CONSOLIDATION DETECTION")
print("="*60)

# 1. Test Perfect Consolidation (Strike settings: 4 touches, 8 candles)
print("\nTest 1: Perfect Consolidation (12 candles, oscillating)")
df = create_consolidation_data(length=15, range_pct=0.015) # 1.5% range
cons = detect_consolidations(
    df, 
    timeframe="15m", 
    min_touches=4, 
    max_height_pct=0.02, 
    min_duration_candles=8,
    atr=1.0
)
print(f"Detected: {len(cons)}")
if cons:
    c = cons[0]
    print(f"  - Touches: {c.touches}")
    print(f"  - Height: {(c.high - c.low)/c.low:.2%}")
    print(f"  - Strength: {c.strength_score:.2f}")

# 2. Test Breakout
print("\nTest 2: Consolidation with Breakout")
df_breakout = create_consolidation_data(length=20, range_pct=0.015, breakout_idx=15)
# Add FVG at breakout (mocking FVG check inside detector? No, detector takes df)
# The detector checks for breakout displacement

# Let's adjust breakout to have displacement > 1 ATR (ATR passed as 1.0)
# Base price 100, ATR 1.0
# Breakout needs to move > 1.0 from range high
# Range high ~ 100.75
# Breakout close needs ~ 101.8
df_breakout.iloc[15, df_breakout.columns.get_loc('close')] = 102.5 
df_breakout.iloc[15, df_breakout.columns.get_loc('open')] = 100.8
# Breakout hold
df_breakout.iloc[16, df_breakout.columns.get_loc('close')] = 102.6
df_breakout.iloc[16, df_breakout.columns.get_loc('low')] = 102.0 # Hold above range

cons_brk = detect_consolidations(
    df_breakout, 
    timeframe="15m", 
    min_touches=4, 
    max_height_pct=0.02, 
    min_duration_candles=8,
    atr=0.5 # Smaller ATR to ensure displacement check passes easily
)

print(f"Detected: {len(cons_brk)}")
if cons_brk:
    c = cons_brk[0]
    print(f"  - Touches: {c.touches}")
    print(f"  - Breakout Confirmed: {c.breakout_confirmed}")
    print(f"  - Direction: {c.breakout_direction}")

print("="*60)
