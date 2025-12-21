#!/usr/bin/env python3
"""Full end-to-end debug: SMC detection -> Entry Zone Calculation -> Validation"""

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
from backend.strategy.planner.planner_service import _calculate_entry_zone

# Setup
mode = get_mode("overwatch")
planner_cfg = PlannerConfig()
adapter = PhemexAdapter()
data_pipeline = IngestionPipeline(adapter)
smc_service = SMCDetectionService(mode=mode.name)
ind_service = IndicatorService()

symbol = "BTC/USDT"
print(f"\n{'='*70}")
print(f"FULL DEBUG: {symbol} in OVERWATCH mode")
print(f"{'='*70}")

# 1. Fetch data
print(f"\n1️⃣ FETCHING DATA...")
data = data_pipeline.fetch_multi_timeframe(symbol, list(mode.timeframes))
current_price = data.get_current_price()
print(f"   Current price: ${current_price:,.2f}")

# Get indicators
indicators = ind_service.compute(data)
primary_tf = mode.primary_planning_timeframe
primary_ind = indicators.by_timeframe.get(primary_tf)
atr = primary_ind.atr if primary_ind else 0
print(f"   ATR ({primary_tf}): ${atr:,.2f}")

# 2. Detect SMC
print(f"\n2️⃣ SMC DETECTION...")
smc = smc_service.detect(data, current_price)
print(f"   Found {len(smc.order_blocks)} OBs, {len(smc.fvgs)} FVGs")

# Show OBs below price
bullish_obs_below = [ob for ob in smc.order_blocks if ob.direction == "bullish" and ob.low < current_price]
print(f"   Bullish OBs below price: {len(bullish_obs_below)}")
for ob in bullish_obs_below:
    dist = max(0, current_price - ob.high) / atr if atr > 0 else 0
    print(f"      [{ob.timeframe}] ${ob.low:,.2f} - ${ob.high:,.2f} (dist={dist:.1f}ATR)")

# 3. Try entry zone calculation (bullish)
print(f"\n3️⃣ ENTRY ZONE CALCULATION (Bullish)...")
print(f"   Config: entry_timeframes={mode.entry_timeframes}, max_pullback_atr={mode.max_pullback_atr}")

try:
    entry_zone, used_structure = _calculate_entry_zone(
        is_bullish=True,
        smc_snapshot=smc,
        current_price=current_price,
        atr=atr,
        primary_tf=primary_tf,
        setup_archetype="TREND_OB_PULLBACK",  # String literal, not a class
        config=mode,
        planner_cfg=planner_cfg,
        confluence_breakdown=None,
        multi_tf_data=data
    )
    
    print(f"\n   ✅ ENTRY ZONE CALCULATED:")
    print(f"      Near entry: ${entry_zone.near_entry:,.2f}")
    print(f"      Far entry:  ${entry_zone.far_entry:,.2f}")
    print(f"      Current:    ${current_price:,.2f}")
    print(f"      Rationale:  {entry_zone.rationale}")
    
    # Check if it would pass validation
    if entry_zone.near_entry > current_price:
        print(f"\n   ⚠️  WARNING: near_entry ({entry_zone.near_entry:,.2f}) > price ({current_price:,.2f})")
        print(f"       This will be REJECTED as 'Invalid bullish entry: entry above current price'")
    else:
        print(f"\n   ✅ VALID: near_entry ({entry_zone.near_entry:,.2f}) <= price ({current_price:,.2f})")
        
except ValueError as e:
    print(f"\n   ❌ ENTRY ZONE FAILED: {e}")
    
    if "Overwatch mode requires valid HTF structure" in str(e):
        print(f"\n   🔍 DIAGNOSIS: No valid OBs/FVGs passed filters")
        bullish_obs = [ob for ob in smc.order_blocks if ob.direction == "bullish"]
        print(f"       Total bullish OBs: {len(bullish_obs)}")
        for ob in bullish_obs:
            dist = max(0, current_price - ob.high) / atr if atr > 0 else 0
            issues = []
            if ob.low >= current_price:
                issues.append(f"low ({ob.low:,.0f}) >= price")
            if dist > mode.max_pullback_atr:
                issues.append(f"dist ({dist:.1f}) > {mode.max_pullback_atr}")
            if ob.mitigation_level > 0.7:
                issues.append(f"mitigated ({ob.mitigation_level:.0%})")
            if ob.timeframe.lower() not in [tf.lower() for tf in mode.entry_timeframes]:
                issues.append(f"TF ({ob.timeframe}) not in {mode.entry_timeframes}")
            
            status = "❌ " + ", ".join(issues) if issues else "✅ Valid"
            print(f"       [{ob.timeframe}] ${ob.low:,.0f}-${ob.high:,.0f} {status}")

except Exception as e:
    print(f"\n   ❌ UNEXPECTED ERROR: {e}")
    import traceback
    traceback.print_exc()

print(f"\n{'='*70}")
