#!/usr/bin/env python3
"""Debug script to trace OB/FVG detection and filtering for OVERWATCH mode."""

import sys
import os
sys.path.insert(0, '/home/maccardi4431/snipersight-trading')
os.chdir('/home/maccardi4431/snipersight-trading')

from backend.shared.config.scanner_modes import get_mode
from backend.shared.config.planner_config import PlannerConfig
from backend.data.ingestion_pipeline import IngestionPipeline
from backend.data.adapters.phemex import PhemexAdapter
from backend.services.smc_service import SMCDetectionService
from backend.services.indicator_service import IndicatorService

# Setup
mode = get_mode("overwatch")
planner_cfg = PlannerConfig()
adapter = PhemexAdapter()
data_pipeline = IngestionPipeline(adapter)
smc_service = SMCDetectionService(mode=mode.name)
ind_service = IndicatorService()

symbol = "BTC/USDT"
print(f"\n{'='*60}")
print(f"DEBUGGING: {symbol} in OVERWATCH mode")
print(f"{'='*60}")

# 1. Fetch data
print(f"\n1️⃣ FETCHING DATA for timeframes: {mode.timeframes}")
data = data_pipeline.fetch_multi_timeframe(symbol, list(mode.timeframes))
current_price = data.get_current_price()
print(f"   Current price: ${current_price:,.2f}")

# Get ATR from primary TF
indicators = ind_service.compute(data)
primary_tf = mode.primary_planning_timeframe
atr = indicators.by_timeframe.get(primary_tf).atr if primary_tf in indicators.by_timeframe else 0
print(f"   ATR ({primary_tf}): ${atr:,.2f}")

# 2. Detect SMC patterns
print(f"\n2️⃣ SMC DETECTION (preset: {mode.smc_preset})")
smc = smc_service.detect(data, current_price)

print(f"\n   📦 ORDER BLOCKS DETECTED: {len(smc.order_blocks)}")
for ob in smc.order_blocks:
    distance_atr = max(0, current_price - ob.high) / atr if atr > 0 else 0
    print(f"      [{ob.timeframe}] {ob.direction.upper()} | low=${ob.low:,.2f} high=${ob.high:,.2f} | "
          f"dist={distance_atr:.1f}ATR | mit={ob.mitigation_level:.0%} | grade={getattr(ob, 'grade', '?')}")

print(f"\n   📊 FVGs DETECTED: {len(smc.fvgs)}")
for fvg in smc.fvgs:
    print(f"      [{fvg.timeframe}] {fvg.direction.upper()} | bottom=${fvg.bottom:,.2f} top=${fvg.top:,.2f} | "
          f"overlap={fvg.overlap_with_price:.0%}")

# 3. Apply planner filters
print(f"\n3️⃣ PLANNER FILTER CHAIN (Bullish)")
print(f"   Config: max_pullback_atr={mode.max_pullback_atr}, entry_timeframes={mode.entry_timeframes}")

# Filter 1: Direction
bullish_obs = [ob for ob in smc.order_blocks if ob.direction == "bullish"]
print(f"\n   Filter 1 (direction=bullish): {len(bullish_obs)} OBs remain")

# Filter 2: Below current price
below_price = [ob for ob in bullish_obs if ob.low < current_price]
print(f"   Filter 2 (ob.low < price): {len(below_price)} OBs remain")
for ob in bullish_obs:
    if ob not in below_price:
        print(f"      ❌ DROPPED: {ob.timeframe} OB low=${ob.low:,.2f} >= price=${current_price:,.2f}")

# Filter 3: Entry timeframes
allowed_tfs = [tf.lower() for tf in mode.entry_timeframes]
in_allowed_tfs = [ob for ob in below_price if ob.timeframe.lower() in allowed_tfs]
print(f"   Filter 3 (timeframe in {allowed_tfs}): {len(in_allowed_tfs)} OBs remain")
for ob in below_price:
    if ob not in in_allowed_tfs:
        print(f"      ❌ DROPPED: {ob.timeframe} not in allowed TFs")

# Filter 4: Distance
max_pullback = mode.max_pullback_atr
within_distance = [ob for ob in in_allowed_tfs if (max(0, current_price - ob.high) / atr) <= max_pullback]
print(f"   Filter 4 (distance <= {max_pullback} ATR): {len(within_distance)} OBs remain")
for ob in in_allowed_tfs:
    if ob not in within_distance:
        dist = max(0, current_price - ob.high) / atr
        print(f"      ❌ DROPPED: {ob.timeframe} OB dist={dist:.1f}ATR > {max_pullback}")

# Filter 5: Mitigation
ob_mit_max = planner_cfg.ob_mitigation_max
not_mitigated = [ob for ob in within_distance if ob.mitigation_level <= ob_mit_max]
print(f"   Filter 5 (mitigation <= {ob_mit_max:.0%}): {len(not_mitigated)} OBs remain")
for ob in within_distance:
    if ob not in not_mitigated:
        print(f"      ❌ DROPPED: {ob.timeframe} OB mit={ob.mitigation_level:.0%} > {ob_mit_max:.0%}")

# Final result
print(f"\n4️⃣ FINAL RESULT")
if not_mitigated:
    print(f"   ✅ {len(not_mitigated)} valid bullish OBs for entry:")
    for ob in not_mitigated:
        print(f"      [{ob.timeframe}] ${ob.low:,.2f} - ${ob.high:,.2f}")
else:
    print(f"   ❌ NO VALID BULLISH OBs - Overwatch will reject!")
    
# Check FVGs too
bullish_fvgs = [fvg for fvg in smc.fvgs if fvg.direction == "bullish" and fvg.top < current_price]
if bullish_fvgs:
    print(f"\n   But there are {len(bullish_fvgs)} bullish FVGs below price that could be used")
else:
    print(f"\n   Also NO bullish FVGs below price")
