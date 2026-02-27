#!/usr/bin/env python3
"""Multi-symbol debug: Test all rejected symbols"""

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

# Symbols that were rejected
symbols = ["ETH/USDT", "BNB/USDT", "XRP/USDT"]

print(f"\n{'='*70}")
print(f"MULTI-SYMBOL DEBUG: Testing rejected symbols in OVERWATCH mode")
print(f"{'='*70}")

for symbol in symbols:
    print(f"\n\n{'='*70}")
    print(f"📊 {symbol}")
    print(f"{'='*70}")
    
    try:
        # Fetch data
        data = data_pipeline.fetch_multi_timeframe(symbol, list(mode.timeframes))
        current_price = data.get_current_price()
        
        # Get indicators
        indicators = ind_service.compute(data)
        primary_tf = mode.primary_planning_timeframe
        primary_ind = indicators.by_timeframe.get(primary_tf)
        atr = primary_ind.atr if primary_ind else 0
        
        print(f"   Price: ${current_price:,.2f} | ATR: ${atr:,.2f}")
        
        # Detect SMC
        smc = smc_service.detect(data, current_price)
        bullish_obs = [ob for ob in smc.order_blocks if ob.direction == "bullish"]
        bearish_obs = [ob for ob in smc.order_blocks if ob.direction == "bearish"]
        
        print(f"   OBs: {len(bullish_obs)} bullish, {len(bearish_obs)} bearish")
        
        # Show bullish OBs below price
        below_price = [ob for ob in bullish_obs if ob.low < current_price]
        print(f"   Bullish OBs below price: {len(below_price)}")
        for ob in below_price[:3]:  # Top 3
            dist = max(0, current_price - ob.high) / atr if atr > 0 else 0
            print(f"      [{ob.timeframe}] ${ob.low:,.2f}-${ob.high:,.2f} dist={dist:.1f}ATR")
        
        # Try entry zone calculation
        try:
            entry_zone, _ = _calculate_entry_zone(
                is_bullish=True,
                smc_snapshot=smc,
                current_price=current_price,
                atr=atr,
                primary_tf=primary_tf,
                setup_archetype="TREND_OB_PULLBACK",
                config=mode,
                planner_cfg=planner_cfg,
                confluence_breakdown=None,
                multi_tf_data=data
            )
            
            if entry_zone.near_entry > current_price:
                print(f"   ❌ REJECTED: near_entry (${entry_zone.near_entry:,.2f}) > price (${current_price:,.2f})")
                print(f"      Reason: 'Invalid bullish entry: entry above current price'")
            else:
                print(f"   ✅ VALID: near=${entry_zone.near_entry:,.2f}, far=${entry_zone.far_entry:,.2f}")
                
        except ValueError as e:
            print(f"   ❌ REJECTED: {e}")
            
    except Exception as e:
        print(f"   ❌ ERROR: {e}")

print(f"\n\n{'='*70}")
print("Done!")
