"""
Run an Overwatch scan to test HTF-focused scoring.
"""
import sys
import os
import json

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.engine.orchestrator import Orchestrator
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode
from backend.data.adapters.phemex import PhemexAdapter

# Create config and adapter
config = ScanConfig(profile="overwatch")
adapter = PhemexAdapter()

# Create orchestrator with proper config
orchestrator = Orchestrator(config=config, exchange_adapter=adapter)

# Apply Overwatch mode
mode = get_mode("overwatch")
orchestrator.apply_mode(mode)

print(f"\n=== Running Overwatch Scan ===\n")
print(f"Mode: {mode.name}")
print(f"Min Confluence: {mode.min_confluence_score}")
print(f"Timeframes: {mode.timeframes}\n")

# Get symbols from adapter
symbols = adapter.get_top_symbols(n=10)
print(f"Scanning {len(symbols)} symbols: {symbols}\n")

def progress_cb(completed, total, symbol):
    print(f"  [{completed}/{total}] {symbol}")

try:
    trade_plans, rejection_summary = orchestrator.scan(symbols, progress_callback=progress_cb)
    
    print(f"\n=== RESULTS ===")
    print(f"Signals: {len(trade_plans)}")
    print(f"Total Rejected: {rejection_summary.get('total_rejected', 0)}")
    print(f"\nBy Reason: {json.dumps(rejection_summary.get('by_reason', {}), indent=2)}")
    
    # Check the low_confluence details specifically
    details = rejection_summary.get("details", {})
    
    for reason_type, rejections in details.items():
        if not rejections:
            continue
        print(f"\n=== {reason_type.upper()} ({len(rejections)} rejections) ===")
        for r in rejections[:5]:  # Show first 5
            print(f"\n  Symbol: {r.get('symbol')}")
            
            # Check for directional edge data
            bull_score = r.get('bullish_score')
            bear_score = r.get('bearish_score')
            
            if bull_score is not None or bear_score is not None:
                gap = abs(bull_score - bear_score) if bull_score and bear_score else 0
                print(f"  Bullish: {bull_score:.1f} | Bearish: {bear_score:.1f} | Gap: {gap:.1f}pts")
            else:
                print(f"  Reason: {r.get('reason', '')[:100]}...")
                
except Exception as e:
    import traceback
    print(f"\nError: {e}")
    traceback.print_exc()
