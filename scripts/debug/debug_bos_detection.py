#!/usr/bin/env python3
"""Debug BOS detection to find why bearish breaks aren't detected"""
import sys
sys.path.insert(0, '/home/maccardi4431/snipersight-trading')

from backend.data.ingestion_pipeline import IngestionPipeline
from backend.data.adapters.phemex import PhemexAdapter
from backend.strategy.smc.swing_structure import detect_swings_vectorized
from backend.strategy.smc.bos_choch import detect_structural_breaks
from backend.shared.config.smc_config import SMCConfig

adapter = PhemexAdapter()
data_pipeline = IngestionPipeline(adapter)
data = data_pipeline.fetch_multi_timeframe('ETH/USDT', ('4h',))
df = data.timeframes['4h']

print(f"ETH 4H: {len(df)} candles")
print(f"Price: ${df['close'].iloc[-1]:.2f}")
print(f"Recent range: ${df['low'].tail(50).min():.0f} - ${df['high'].tail(50).max():.0f}")

# Get swings
print("\n" + "="*60)
print("SWING DETECTION")
print("="*60)
swings = detect_swings_vectorized(df, swing_length=7)
valid_swings = swings.dropna()

print(f"\nTotal swings: {len(valid_swings)}")
print("\nLast 20 swings:")
last_20 = valid_swings.tail(20)
for idx, row in last_20.iterrows():
    swing_type = "HIGH" if row['HighLow'] == 1 else "LOW "
    price = df.loc[idx, 'high'] if row['HighLow'] == 1 else df.loc[idx, 'low']
    print(f"  {idx}: {swing_type} @ ${price:.2f}")

# Get last 8 swing pattern
pattern = list(valid_swings['HighLow'].tail(8).astype(int).values)
print(f"\nLast 8 swing pattern: {pattern}")
print(f"Bearish pattern needed: [1, -1, 1, -1]")
print(f"Bullish pattern needed: [-1, 1, -1, 1]")

# Check BOS detection
print("\n" + "="*60)
print("BOS/CHoCH DETECTION")
print("="*60)
smc_cfg = SMCConfig.luxalgo_strict()
breaks = detect_structural_breaks(df, smc_cfg)

bull_breaks = [b for b in breaks if getattr(b, 'direction', '') == 'bullish']
bear_breaks = [b for b in breaks if getattr(b, 'direction', '') == 'bearish']

print(f"\nTotal: {len(breaks)} ({len(bull_breaks)} bullish, {len(bear_breaks)} bearish)")

print("\nLast 10 breaks:")
for brk in breaks[-10:]:
    btype = getattr(brk, 'break_type', '?')
    direction = getattr(brk, 'direction', '?')
    level = getattr(brk, 'level', 0)
    ts = getattr(brk, 'timestamp', None)
    marker = "🟢" if direction == 'bullish' else "🔴"
    print(f"  {marker} {btype:5} {direction:8} @ ${level:.2f} | {ts}")

# Manual check - can we find where bearish breaks SHOULD be?
print("\n" + "="*60)
print("MANUAL BEARISH BREAK CHECK")
print("="*60)

# Get recent swing lows
swing_lows_df = valid_swings[valid_swings['HighLow'] == -1].tail(10)
print("\nRecent swing lows:")
for idx, row in swing_lows_df.iterrows():
    low_price = df.loc[idx, 'low']
    # Check if any candle after this closed below
    future_df = df[df.index > idx]
    closes_below = future_df[future_df['close'] < low_price]
    if len(closes_below) > 0:
        first_break = closes_below.index[0]
        print(f"  {idx}: LOW @ ${low_price:.2f} - BROKEN on {first_break}")
    else:
        print(f"  {idx}: LOW @ ${low_price:.2f} - NOT broken")

# Check the pattern sequence at each potential break point
print("\n" + "="*60)
print("PATTERN SEQUENCE ANALYSIS")
print("="*60)

# Get the swing sequence leading up to recent candles
swing_highs_lows = []
swing_levels = []
swing_indices = []

for idx, row in valid_swings.iterrows():
    swing_highs_lows.append(int(row['HighLow']))
    swing_levels.append(row['Level'])
    swing_indices.append(idx)

# Check last few potential break points
print("\nChecking pattern at last 5 swing points:")
for i in range(-5, 0):
    if len(swing_highs_lows) + i >= 4:
        last_4_types = swing_highs_lows[i-3:i+1] if i < -1 else swing_highs_lows[-4:]
        last_4_levels = swing_levels[i-3:i+1] if i < -1 else swing_levels[-4:]
        
        print(f"\n  At swing {i}:")
        print(f"    Pattern: {last_4_types}")
        print(f"    Levels: [{', '.join([f'${l:.0f}' for l in last_4_levels])}]")
        
        # Check for bearish pattern [1, -1, 1, -1]
        if last_4_types == [1, -1, 1, -1]:
            hh, hl, lh, ll = last_4_levels
            print(f"    ✅ BEARISH PATTERN MATCH!")
            print(f"       {hh:.0f} > {lh:.0f} > {hl:.0f} > {ll:.0f}? {hh > lh > hl > ll}")
        elif last_4_types == [-1, 1, -1, 1]:
            ll, lh, hl, hh = last_4_levels
            print(f"    ✅ BULLISH PATTERN MATCH!")
            print(f"       {ll:.0f} < {hl:.0f} < {lh:.0f} < {hh:.0f}? {ll < hl < lh < hh}")
