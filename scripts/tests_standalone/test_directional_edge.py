"""
Test script to capture directional edge rejection with full payload
"""
import sys
import os
import json

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.engine.orchestrator import Orchestrator
from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode
from backend.data.phemex_adapter import PhemexAdapter

# Create orchestrator
adapter = PhemexAdapter()
orchestrator = Orchestrator(adapter)

# Apply a mode that might trigger the directional edge rejection
mode = get_mode("overwatch")
orchestrator.apply_mode(mode)

# Scan a symbol that's likely to have conflicting directions
# (coins with neutral sentiment often trigger this)
symbols = ["ENSO/USDT:USDT"]

print(f"\n=== Testing scan for {symbols} ===\n")

def progress_cb(completed, total, symbol):
    print(f"  Progress: {completed}/{total} - {symbol}")

try:
    trade_plans, rejection_summary = orchestrator.scan(symbols, progress_callback=progress_cb)
    
    print(f"\n=== Results ===")
    print(f"Trade Plans: {len(trade_plans)}")
    print(f"Rejections: {json.dumps(rejection_summary, indent=2, default=str)}")
    
    # Check the low_confluence details specifically
    if "details" in rejection_summary and "low_confluence" in rejection_summary["details"]:
        low_conf = rejection_summary["details"]["low_confluence"]
        print(f"\n=== Low Confluence Details ({len(low_conf)} rejections) ===")
        for r in low_conf:
            print(f"\nSymbol: {r.get('symbol')}")
            print(f"Reason: {r.get('reason')}")
            print(f"Reason Type: {r.get('reason_type')}")
            print(f"Bullish Score: {r.get('bullish_score')}")
            print(f"Bearish Score: {r.get('bearish_score')}")
            print(f"Bullish Factors: {len(r.get('bullish_factors', []))} factors")
            print(f"Bearish Factors: {len(r.get('bearish_factors', []))} factors")
            if r.get('bullish_factors'):
                print(f"  First Bull Factor: {r['bullish_factors'][0]}")
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
