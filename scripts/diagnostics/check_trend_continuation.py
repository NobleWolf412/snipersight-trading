"""
Diagnostic script to check trend continuation configuration
"""
import sys
import os

sys.path.append(os.getcwd())

from backend.shared.config.planner_config import PlannerConfig
from backend.shared.config.scanner_modes import get_mode

target_modes = ["strike", "surgical", "stealth", "overwatch"]

print("=" * 110)
print(f"{'SCANNER MODE':<15} | {'MAPPED TYPE':<15} | {'STATUS':<15} | {'DETAILS'}")
print("=" * 110)

for mode_name in target_modes:
    scanner_mode = get_mode(mode_name)
    if not scanner_mode:
        print(f"{mode_name:15s} | {'NOT FOUND':<15} | {'UNKNOWN':<15}")
        continue
        
    trade_type = scanner_mode.expected_trade_type
    cfg = PlannerConfig.defaults_for_mode(trade_type)
    
    status = "✅ ENABLED" if cfg.enable_trend_continuation else "❌ DISABLED"
    print(f"{mode_name:<15} | {trade_type:<15} | {status:<15} | (touches={cfg.consolidation_min_touches}, dur={cfg.consolidation_min_duration_candles}, height={cfg.consolidation_max_height_pct:.1%})")

print("=" * 110)
