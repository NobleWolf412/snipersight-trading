#!/usr/bin/env python3
"""Full scanner simulation for ETH - shows exactly what the scanner would produce."""

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
from backend.strategy.confluence.scorer import calculate_confluence_score, _score_htf_structure_bias
from backend.strategy.planner.planner_service import _calculate_entry_zone

# Setup - using OVERWATCH mode as you mentioned
mode = get_mode("overwatch")
planner_cfg = PlannerConfig()
adapter = PhemexAdapter()
data_pipeline = IngestionPipeline(adapter)
smc_service = SMCDetectionService(mode=mode.name)
ind_service = IndicatorService()

symbol = "ETH/USDT"
print(f"\n{'='*80}")
print(f"🔍 FULL SCANNER SIMULATION: {symbol} (OVERWATCH MODE)")
print(f"{'='*80}")

# 1. Fetch data
print(f"\n📊 STEP 1: FETCHING DATA ({mode.timeframes})")
data = data_pipeline.fetch_multi_timeframe(symbol, list(mode.timeframes))
current_price = data.get_current_price()
print(f"   Current price: ${current_price:,.2f}")

# 2. Compute indicators
print(f"\n📈 STEP 2: COMPUTING INDICATORS")
indicators = ind_service.compute(data)
primary_tf = mode.primary_planning_timeframe
primary_ind = indicators.by_timeframe.get(primary_tf)
atr = primary_ind.atr if primary_ind else 0
print(f"   ATR ({primary_tf}): ${atr:,.2f}")

# Show RSI across timeframes
print(f"\n   RSI by timeframe:")
for tf, ind in indicators.by_timeframe.items():
    if ind and hasattr(ind, 'rsi') and ind.rsi is not None:
        print(f"      {tf}: RSI = {ind.rsi:.1f}")

# 3. Detect SMC patterns
print(f"\n🎯 STEP 3: SMC DETECTION")
smc = smc_service.detect(data, current_price)

# Group OBs by timeframe and direction
print(f"\n   ORDER BLOCKS DETECTED:")
for tf in ['1w', '1W', '1d', '1D', '4h', '4H', '1h', '1H', '15m', '5m']:
    tf_obs = [ob for ob in smc.order_blocks if ob.timeframe.lower() == tf.lower()]
    if tf_obs:
        for ob in tf_obs:
            dist = (current_price - ob.high) / atr if atr > 0 and ob.direction == "bullish" else 0
            dist = (ob.low - current_price) / atr if atr > 0 and ob.direction == "bearish" else dist
            position = "BELOW" if ob.high < current_price else ("ABOVE" if ob.low > current_price else "INSIDE")
            print(f"      [{tf}] {ob.direction.upper():8} ${ob.low:,.2f} - ${ob.high:,.2f} | {position} price | dist={abs(dist):.1f}ATR")

print(f"\n   FVGs DETECTED: {len(smc.fvgs)}")
for fvg in smc.fvgs[:5]:  # Top 5
    print(f"      [{fvg.timeframe}] {fvg.direction.upper()} ${fvg.bottom:,.2f} - ${fvg.top:,.2f}")

# 4. HTF Structure Analysis
print(f"\n📐 STEP 4: HTF STRUCTURE (Swing HH/HL/LH/LL)")
swing_structure = smc.swing_structure
for tf, ss in swing_structure.items():
    trend = ss.get('trend', 'unknown')
    print(f"      {tf}: {trend.upper()} trend")

# Calculate HTF bias score
htf_bias_long = _score_htf_structure_bias(swing_structure, "LONG")
htf_bias_short = _score_htf_structure_bias(swing_structure, "SHORT")
print(f"\n   HTF Bias Scores:")
print(f"      LONG:  {htf_bias_long['bonus']:+.1f} - {htf_bias_long['reason']}")
print(f"      SHORT: {htf_bias_short['bonus']:+.1f} - {htf_bias_short['reason']}")

# 5. Confluence Scoring
print(f"\n⚖️ STEP 5: CONFLUENCE SCORING")

# Get ScanConfig from the mode
from backend.shared.config.defaults import ScanConfig
scan_config = ScanConfig(profile=mode.name)
# Copy timeframes from mode
scan_config.timeframes = mode.timeframes
scan_config.primary_planning_timeframe = mode.primary_planning_timeframe

long_score = calculate_confluence_score(
    smc_snapshot=smc,
    indicators=indicators,
    config=scan_config,
    direction="LONG",
    current_price=current_price
)

short_score = calculate_confluence_score(
    smc_snapshot=smc,
    indicators=indicators,
    config=scan_config,
    direction="SHORT",
    current_price=current_price
)

print(f"\n   LONG Score:  {long_score.total_score:.1f}")
print(f"   SHORT Score: {short_score.total_score:.1f}")

# Show top factors
print(f"\n   LONG Factors (top 5):")
for f in sorted(long_score.factors, key=lambda x: abs(x.score * x.weight), reverse=True)[:5]:
    print(f"      {f.name}: {f.score:.1f} x {f.weight:.2f} = {f.score * f.weight:.1f}")

print(f"\n   SHORT Factors (top 5):")
for f in sorted(short_score.factors, key=lambda x: abs(x.score * x.weight), reverse=True)[:5]:
    print(f"      {f.name}: {f.score:.1f} x {f.weight:.2f} = {f.score * f.weight:.1f}")

# 6. Direction Decision
print(f"\n🧭 STEP 6: DIRECTION DECISION")
if long_score.total_score > short_score.total_score + 5:
    chosen_direction = "LONG"
    chosen_score = long_score
elif short_score.total_score > long_score.total_score + 5:
    chosen_direction = "SHORT"
    chosen_score = short_score
else:
    chosen_direction = "TIE/SKIP"
    chosen_score = None

print(f"   Chosen Direction: {chosen_direction}")
if chosen_score:
    print(f"   Score: {chosen_score.total_score:.1f}")

# 7. Entry Zone Calculation
print(f"\n📍 STEP 7: ENTRY ZONE CALCULATION")
if chosen_direction in ["LONG", "SHORT"]:
    try:
        is_bullish = chosen_direction == "LONG"
        entry_zone, used_structure = _calculate_entry_zone(
            is_bullish=is_bullish,
            smc_snapshot=smc,
            current_price=current_price,
            atr=atr,
            primary_tf=primary_tf,
            setup_archetype="TREND_OB_PULLBACK",
            config=mode,
            planner_cfg=planner_cfg,
            confluence_breakdown=chosen_score,
            multi_tf_data=data
        )
        
        print(f"   Near Entry: ${entry_zone.near_entry:,.2f}")
        print(f"   Far Entry:  ${entry_zone.far_entry:,.2f}")
        print(f"   Rationale:  {entry_zone.rationale}")
        print(f"   Used Structure: {used_structure}")
        
        # Calculate R:R if we had stop/target
        print(f"\n   Current Price: ${current_price:,.2f}")
        print(f"   Distance to Near: ${abs(current_price - entry_zone.near_entry):,.2f}")
        
    except ValueError as e:
        print(f"   ❌ Entry Zone Failed: {e}")
else:
    print(f"   ⚠️ Skipped - no clear direction")

# 8. Summary
print(f"\n{'='*80}")
print("📋 SUMMARY")
print(f"{'='*80}")
print(f"   Symbol: {symbol}")
print(f"   Price:  ${current_price:,.2f}")
print(f"   HTF Bias: {htf_bias_long['htf_bias']}")
print(f"   Decision: {chosen_direction}")
if chosen_score:
    print(f"   Score: {chosen_score.total_score:.1f}")
print(f"{'='*80}")
