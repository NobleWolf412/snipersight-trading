#!/usr/bin/env python3
"""Comprehensive ETH OB analysis for user verification"""
import sys
sys.path.insert(0, '/home/maccardi4431/snipersight-trading')

from backend.data.ingestion_pipeline import IngestionPipeline
from backend.data.adapters.phemex import PhemexAdapter
from backend.services.smc_service import SMCDetectionService
from backend.services.indicator_service import IndicatorService
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

data = data_pipeline.fetch_multi_timeframe('ETH/USDT', mode.timeframes)
current_price = float(data.timeframes['5m']['close'].iloc[-1])
indicators = ind_service.compute(data)
smc = smc_service.detect(data, current_price)

print(f"""
{'='*80}
📊 ETH/USDT COMPREHENSIVE ANALYSIS
{'='*80}
Current Price: ${current_price:.2f}
""")

# Group OBs by timeframe
tf_order = ['1W', '1D', '4H', '1H', '15m', '5m']
obs_by_tf = {}
for ob in smc.order_blocks:
    tf = getattr(ob, 'timeframe', 'unknown').upper().replace('M', 'm')
    if tf not in obs_by_tf:
        obs_by_tf[tf] = []
    obs_by_tf[tf].append(ob)

for tf in tf_order:
    if tf not in obs_by_tf:
        print(f"\n📦 {tf} ORDER BLOCKS: None detected")
        continue
    
    obs = sorted(obs_by_tf[tf], key=lambda x: getattr(x, 'low', 0), reverse=True)
    print(f"\n📦 {tf} ORDER BLOCKS ({len(obs)} total):")
    print(f"   {'DIR':8} {'RANGE':20} {'FRESHNESS':10} {'MITIGATION':12} {'POSITION':12} {'DATE'}")
    print(f"   {'-'*8} {'-'*20} {'-'*10} {'-'*12} {'-'*12} {'-'*12}")
    
    for ob in obs:
        direction = getattr(ob, 'direction', '')[:4].upper()
        low = getattr(ob, 'low', 0)
        high = getattr(ob, 'high', 0)
        fresh = getattr(ob, 'freshness_score', 0)
        mit = getattr(ob, 'mitigation_level', 0)
        ts = getattr(ob, 'timestamp', None)
        
        # Position relative to price
        if low <= current_price <= high:
            pos = "** INSIDE **"
        elif high < current_price:
            dist = (current_price - high) / current_price * 100
            pos = f"BELOW -{dist:.1f}%"
        else:
            dist = (low - current_price) / current_price * 100
            pos = f"ABOVE +{dist:.1f}%"
        
        date_str = ts.strftime('%Y-%m-%d') if ts else 'N/A'
        range_str = f"${low:.0f} - ${high:.0f}"
        
        # Color indicator
        dir_indicator = "🟢" if direction == "BULL" else "🔴"
        
        print(f"   {dir_indicator} {direction:6} {range_str:20} {fresh:>7.1f}%   {mit:>8.0%}       {pos:12} {date_str}")

# HTF Structure
print(f"\n{'='*80}")
print("📈 HTF SWING STRUCTURE")
print(f"{'='*80}")
if smc.swing_structure:
    for tf, ss in smc.swing_structure.items():
        trend = ss.get('trend', 'unknown') if isinstance(ss, dict) else 'unknown'
        print(f"   {tf}: {trend.upper()}")

# Liquidity Sweeps
print(f"\n{'='*80}")
print("💧 LIQUIDITY SWEEPS")
print(f"{'='*80}")
if smc.liquidity_sweeps:
    for sweep in smc.liquidity_sweeps[:10]:
        tf = getattr(sweep, 'timeframe', 'unknown')
        direction = getattr(sweep, 'direction', 'unknown')
        level = getattr(sweep, 'level', 0)
        ts = getattr(sweep, 'timestamp', None)
        print(f"   [{tf}] {direction.upper():8} @ ${level:.2f} | {ts}")
else:
    print("   No sweeps detected")

# BOS/CHoCH
print(f"\n{'='*80}")
print("🔀 STRUCTURE BREAKS (BOS/CHoCH)")
print(f"{'='*80}")
if smc.structural_breaks:
    bull_count = sum(1 for b in smc.structural_breaks if getattr(b, 'direction', '') == 'bullish')
    bear_count = sum(1 for b in smc.structural_breaks if getattr(b, 'direction', '') == 'bearish')
    print(f"   Total: {len(smc.structural_breaks)} ({bull_count} bullish, {bear_count} bearish)")
    print()
    for brk in smc.structural_breaks[:15]:
        tf = getattr(brk, 'timeframe', 'unknown')
        btype = getattr(brk, 'break_type', 'unknown')
        direction = getattr(brk, 'direction', 'unknown')
        level = getattr(brk, 'level', 0)
        ts = getattr(brk, 'timestamp', None)
        marker = "🟢" if direction == 'bullish' else "🔴"
        print(f"   {marker} [{tf}] {btype:5} {direction:8} @ ${level:.2f} | {ts}")
else:
    print("   No structure breaks detected")

# Premium/Discount
print(f"\n{'='*80}")
print("💰 PREMIUM/DISCOUNT ZONES")
print(f"{'='*80}")
pd_data = getattr(smc, 'premium_discount', None)
if pd_data:
    for tf, pd in pd_data.items():
        zone = pd.get('current_zone', 'unknown') if isinstance(pd, dict) else 'unknown'
        pct = pd.get('zone_percentage', 0) if isinstance(pd, dict) else 0
        indicator = "🟢" if zone == 'discount' else ("🔴" if zone == 'premium' else "⚪")
        print(f"   {indicator} {tf}: {zone.upper()} ({pct:.0f}%)")

# Confluence Scoring
print(f"\n{'='*80}")
print("⚖️ CONFLUENCE SCORING")
print(f"{'='*80}")

scan_config = ScanConfig(profile=mode.name)
scan_config.timeframes = mode.timeframes
scan_config.primary_planning_timeframe = mode.primary_planning_timeframe

long_result = calculate_confluence_score(smc, indicators, scan_config, "LONG", current_price)
short_result = calculate_confluence_score(smc, indicators, scan_config, "SHORT", current_price)

print(f"\n   LONG Score:  {long_result.total_score:.1f}")
print(f"   SHORT Score: {short_result.total_score:.1f}")
print(f"   Winner: {'LONG' if long_result.total_score > short_result.total_score else 'SHORT'} by {abs(long_result.total_score - short_result.total_score):.1f} pts")

print(f"\n   Top LONG factors:")
for f in sorted(long_result.factors, key=lambda x: x.weighted_score, reverse=True)[:8]:
    print(f"      {f.name:25} {f.score:5.1f} × {f.weight:.2f} = {f.weighted_score:5.1f}")

print(f"\n   Top SHORT factors:")
for f in sorted(short_result.factors, key=lambda x: x.weighted_score, reverse=True)[:8]:
    print(f"      {f.name:25} {f.score:5.1f} × {f.weight:.2f} = {f.weighted_score:5.1f}")

print(f"\n{'='*80}")
print("✅ ANALYSIS COMPLETE")
print(f"{'='*80}")
