#!/usr/bin/env python3
"""Debug OB detection to find why bearish OBs are missing"""
import sys
sys.path.insert(0, '/home/maccardi4431/snipersight-trading')

from backend.data.ingestion_pipeline import IngestionPipeline
from backend.data.adapters.phemex import PhemexAdapter
from backend.shared.config.smc_config import SMCConfig
from backend.strategy.smc.order_blocks import detect_order_blocks

adapter = PhemexAdapter()
data_pipeline = IngestionPipeline(adapter)
data = data_pipeline.fetch_multi_timeframe('ETH/USDT', ('4h',))
df = data.timeframes['4h']

smc_cfg = SMCConfig.luxalgo_strict()
print(f'Config:')
print(f'  ob_max_mitigation: {smc_cfg.ob_max_mitigation}')
print(f'  ob_min_freshness: {smc_cfg.ob_min_freshness}')
print(f'  min_displacement_atr: {smc_cfg.min_displacement_atr}')
print(f'  min_wick_ratio: {smc_cfg.min_wick_ratio}')

obs = detect_order_blocks(df, smc_cfg)
print(f'\nTotal OBs detected: {len(obs)}')

for ob in obs[:20]:  # Show first 20
    print(f'  {ob.direction.upper():8} ${ob.low:.2f}-${ob.high:.2f} Grade {ob.grade} | fresh={ob.freshness_score:.0f}% mit={ob.mitigation_level:.2f}')

bullish = [ob for ob in obs if ob.direction == 'bullish']
bearish = [ob for ob in obs if ob.direction == 'bearish']
print(f'\n{len(bullish)} bullish, {len(bearish)} bearish')
