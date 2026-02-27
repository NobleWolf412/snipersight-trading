"""
Debug BNB Risk Validation Failure

Runs a focused scan on BNB/USDT:USDT in Overwatch mode to capture 
the exact reason why it passes confluence (81%) but fails risk validation.
"""

import sys
sys.path.insert(0, ".")

from backend.shared.config.defaults import ScanConfig
from backend.engine.orchestrator import Orchestrator
from backend.data.adapters.phemex import PhemexAdapter
import logging

# Set up detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create Overwatch config
config = ScanConfig(
    profile="overwatch",
    timeframes=("1w", "1d", "4h", "1h", "15m", "5m"),
    min_confluence_score=78.0,
  min_rr_ratio=2.0,
    max_symbols=1,
)

# Initialize orchestrator
adapter = PhemexAdapter()
orch = Orchestrator(config=config, exchange_adapter=adapter, debug_mode=True)

print("\n" + "="*80)
print("DEBUG: BNB Risk Validation Failure Investigation")
print("="*80)
print(f"Mode: Overwatch")
print(f"Min Confluence: {config.min_confluence_score}")
print(f"Min R:R: {config.min_rr_ratio}")
print(f"Allowed Trade Types: {getattr(config, 'allowed_trade_types', 'Not set')}")
print("="*80 + "\n")

# Run scan on BNB only
signals, rejection_summary = orch.scan(["BNB/USDT:USDT"])

print("\n" + "="*80)
print("RESULTS:")
print("="*80)
if signals:
    print(f"✅ Generated {len(signals)} signal(s)")
    for sig in signals:
        print(f"  - {sig.symbol}: {sig.direction} | R:R={sig.risk_reward_ratio:.2f}")
else:
    print("❌ No signals generated")
    print("\nRejection Summary:")
    for reason, items in rejection_summary["details"].items():
        if items:
            print(f"\n  {reason}: {len(items)} rejection(s)")
            for item in items:
                print(f"    - {item.get('symbol', 'Unknown')}: {item.get('reason', 'No reason')}")
print("="*80 + "\n")
