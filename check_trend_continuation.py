"""
Diagnostic script to check trend continuation configuration
"""

from backend.shared.config.planner_config import PlannerConfig

# Check what each mode has for trend continuation
modes = ["strike", "surgical", "stealth", "overwatch", "intraday", "swing"]

print("=" * 60)
print("TREND CONTINUATION CONFIGURATION BY MODE")
print("=" * 60)

for mode in modes:
    cfg = PlannerConfig.defaults_for_mode(mode)
    status = "✅ ENABLED" if cfg.enable_trend_continuation else "❌ DISABLED"
    print(f"{mode:15s} → {status:15s} (min_touches={cfg.consolidation_min_touches}, min_duration={cfg.consolidation_min_duration_candles})")

print("=" * 60)
