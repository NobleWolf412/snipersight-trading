#!/usr/bin/env python3
"""Debug ETH simulation with detailed factor breakdown"""

import sys
import os
sys.path.insert(0, '/home/maccardi4431/snipersight-trading')
os.chdir('/home/maccardi4431/snipersight-trading')

from backend.data.ingestion_pipeline import IngestionPipeline
from backend.data.adapters.phemex import PhemexAdapter
from backend.services.indicator_service import IndicatorService
from backend.services.smc_service import SMCDetectionService
from backend.shared.config.scanner_modes import get_mode
from backend.shared.config.smc_config import SMCConfig
from backend.strategy.confluence.scorer import calculate_confluence_score
from backend.shared.config.defaults import ScanConfig

# Setup
adapter = PhemexAdapter()
data_pipeline = IngestionPipeline(adapter)
mode = get_mode('overwatch')
smc_config = SMCConfig.luxalgo_strict()
smc_service = SMCDetectionService(smc_config=smc_config, mode=mode.name)
ind_service = IndicatorService()

symbol = "ETH/USDT"
print(f"\n{'='*80}")
print(f"🔍 DETAILED ETH DEBUG: {symbol} (OVERWATCH)")
print(f"{'='*80}")

# Fetch data
data = data_pipeline.fetch_multi_timeframe(symbol, mode.timeframes)
current_price = float(data.timeframes['5m']['close'].iloc[-1])
print(f"\n📊 Current Price: ${current_price:.2f}")

# Compute indicators
indicators = ind_service.compute(data)

# SMC Detection
smc = smc_service.detect(data, current_price)

# Show mode TF windows
print(f"\n📐 MODE TIMEFRAME WINDOWS:")
print(f"   Bias TFs: {mode.timeframes}")
print(f"   Zone TFs: {mode.zone_timeframes}")
print(f"   Entry TFs: {mode.entry_trigger_timeframes}")

# Show HTF structure
print(f"\n📈 HTF STRUCTURE:")
if smc.swing_structure:
    for tf, ss in smc.swing_structure.items():
        trend = ss.get('trend', 'unknown') if isinstance(ss, dict) else 'unknown'
        print(f"   {tf}: {trend}")

# Show P/D zones
print(f"\n💰 PREMIUM/DISCOUNT ZONES:")
pd_data = getattr(smc, 'premium_discount', None) or getattr(smc, 'premium_discount_zones', None)
if pd_data:
    for tf, pd in pd_data.items() if isinstance(pd_data, dict) else []:
        zone = pd.get('current_zone', 'unknown') if isinstance(pd, dict) else 'unknown'
        pct = pd.get('zone_percentage', 0) if isinstance(pd, dict) else 0
        print(f"   {tf}: {zone} ({pct:.0f}%)")
else:
    print("   (No P/D data available)")

# Show OBs
print(f"\n🟩 ORDER BLOCKS (by zone TFs):")
zone_tfs = set(mode.zone_timeframes)
for ob in smc.order_blocks:
    tf = getattr(ob, 'timeframe', 'unknown')
    if tf.lower() in [t.lower() for t in zone_tfs] or tf.upper() in zone_tfs:
        direction = getattr(ob, 'direction', 'unknown')
        low = getattr(ob, 'low', 0)
        high = getattr(ob, 'high', 0)
        in_price = low <= current_price <= high
        status = "INSIDE" if in_price else ("BELOW" if high < current_price else "ABOVE")
        print(f"   [{tf}] {direction.upper():8} ${low:.2f} - ${high:.2f} | {status}")

print(f"\n🟢 ORDER BLOCKS (by entry TFs):")
entry_tfs = set(mode.entry_trigger_timeframes)
for ob in smc.order_blocks:
    tf = getattr(ob, 'timeframe', 'unknown')
    if tf.lower() in [t.lower() for t in entry_tfs] or tf.upper() in entry_tfs:
        direction = getattr(ob, 'direction', 'unknown')
        low = getattr(ob, 'low', 0)
        high = getattr(ob, 'high', 0)
        in_price = low <= current_price <= high
        status = "INSIDE" if in_price else ("BELOW" if high < current_price else "ABOVE")
        print(f"   [{tf}] {direction.upper():8} ${low:.2f} - ${high:.2f} | {status}")

# Calculate confluence for both directions
scan_config = ScanConfig(profile=mode.name)
scan_config.timeframes = mode.timeframes
scan_config.primary_planning_timeframe = mode.primary_planning_timeframe

print(f"\n⚖️ CONFLUENCE SCORING (LONG):")
long_result = calculate_confluence_score(
    smc_snapshot=smc,
    indicators=indicators,
    config=scan_config,
    direction="LONG",
    current_price=current_price
)

print(f"   Total Score: {long_result.total_score:.1f}")
print(f"   Synergy Bonus: +{long_result.synergy_bonus:.1f}")
print(f"   Conflict Penalty: -{long_result.conflict_penalty:.1f}")
print(f"\n   FACTORS (sorted by contribution):")
sorted_factors = sorted(long_result.factors, key=lambda f: f.weighted_score, reverse=True)
for f in sorted_factors[:10]:
    print(f"      {f.name:25} {f.score:5.1f} x {f.weight:.2f} = {f.weighted_score:5.1f}")
    print(f"         → {f.rationale[:70]}...")

print(f"\n⚖️ CONFLUENCE SCORING (SHORT):")
short_result = calculate_confluence_score(
    smc_snapshot=smc,
    indicators=indicators,
    config=scan_config,
    direction="SHORT",
    current_price=current_price
)

print(f"   Total Score: {short_result.total_score:.1f}")
print(f"   Synergy Bonus: +{short_result.synergy_bonus:.1f}")
print(f"   Conflict Penalty: -{short_result.conflict_penalty:.1f}")
print(f"\n   FACTORS (sorted by contribution):")
sorted_factors = sorted(short_result.factors, key=lambda f: f.weighted_score, reverse=True)
for f in sorted_factors[:10]:
    print(f"      {f.name:25} {f.score:5.1f} x {f.weight:.2f} = {f.weighted_score:5.1f}")
    print(f"         → {f.rationale[:70]}...")

# Decision
print(f"\n🧭 FINAL DECISION:")
winner = "LONG" if long_result.total_score > short_result.total_score else "SHORT"
diff = abs(long_result.total_score - short_result.total_score)
print(f"   Winner: {winner}")
print(f"   Score Difference: {diff:.1f} points")
print(f"   LONG: {long_result.total_score:.1f} vs SHORT: {short_result.total_score:.1f}")

# Key new factors check
print(f"\n🆕 NEW FACTOR CHECK:")
for name in ["HTF Inflection Point", "Multi-TF Reversal", "LTF Structure Shift", 
             "Premium/Discount Zone", "Inside Order Block", "Opposing Structure"]:
    found_long = any(f.name == name for f in long_result.factors)
    found_short = any(f.name == name for f in short_result.factors)
    long_score = next((f.weighted_score for f in long_result.factors if f.name == name), 0)
    short_score = next((f.weighted_score for f in short_result.factors if f.name == name), 0)
    status = "✅" if found_long or found_short else "❌"
    print(f"   {status} {name}: LONG +{long_score:.1f}, SHORT +{short_score:.1f}")

print(f"\n{'='*80}")
