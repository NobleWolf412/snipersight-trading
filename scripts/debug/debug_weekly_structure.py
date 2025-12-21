#!/usr/bin/env python3
"""Debug Weekly structure detection for ETH"""

import sys
import os
sys.path.insert(0, '/home/maccardi4431/snipersight-trading')
os.chdir('/home/maccardi4431/snipersight-trading')

from backend.data.ingestion_pipeline import IngestionPipeline
from backend.data.adapters.phemex import PhemexAdapter
from backend.strategy.smc.swing_structure import detect_swing_structure
from backend.shared.config.smc_config import scale_lookback

adapter = PhemexAdapter()
data_pipeline = IngestionPipeline(adapter)

symbol = "ETH/USDT"
print(f"\n{'='*70}")
print(f"🔍 WEEKLY STRUCTURE DEBUG: {symbol}")
print(f"{'='*70}")

# Fetch weekly data
data = data_pipeline.fetch_multi_timeframe(symbol, ['1w'])
weekly_df = data.timeframes.get('1w')

if weekly_df is None:
    print("❌ No weekly data!")
    exit()

print(f"\n📊 Weekly Data: {len(weekly_df)} candles")
print(f"   Date range: {weekly_df.index[0]} to {weekly_df.index[-1]}")

# Show last 20 weekly candles
print(f"\n📈 Last 20 Weekly Candles:")
last_20 = weekly_df.tail(20)
for idx, row in last_20.iterrows():
    change = ((row['close'] - row['open']) / row['open']) * 100
    direction = "🟢" if row['close'] > row['open'] else "🔴"
    print(f"   {idx.date()} | O:{row['open']:.0f} H:{row['high']:.0f} L:{row['low']:.0f} C:{row['close']:.0f} | {direction} {change:+.1f}%")

# Detect swing structure with different lookbacks
print(f"\n🔄 SWING DETECTION WITH DIFFERENT LOOKBACKS:")

for lookback in [7, 10, 15, 20]:
    swing_result = detect_swing_structure(weekly_df, lookback=lookback)
    print(f"\n   Lookback {lookback}:")
    print(f"      Trend: {swing_result.trend}")
    print(f"      Last HH: {swing_result.last_hh}")
    print(f"      Last HL: {swing_result.last_hl}")
    print(f"      Last LH: {swing_result.last_lh}")
    print(f"      Last LL: {swing_result.last_ll}")
    print(f"      Swing Points: {len(swing_result.swing_points)}")

# Show what the scanner actually uses
scaled = scale_lookback(15, '1w', min_lookback=7, max_lookback=30)
print(f"\n📐 Scanner uses scaled lookback: {scaled}")

swing_result = detect_swing_structure(weekly_df, lookback=scaled)
print(f"   Result: {swing_result.trend}")

# Manually analyze the swings
print(f"\n🔍 SWING POINTS ANALYSIS:")
for i, sp in enumerate(swing_result.swing_points[-10:]):  # Last 10
    print(f"   {i+1}. {sp.type} at ${sp.price:.0f} on {sp.timestamp.date() if sp.timestamp else 'N/A'}")

print(f"\n{'='*70}")
