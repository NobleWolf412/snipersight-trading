#!/usr/bin/env python3
"""
Quick test of orchestrator components to identify remaining issues.
"""

import sys
import os
sys.path.append('/workspaces/snipersight-trading')

try:
    from backend.shared.config.defaults import ScanConfig
    print("✓ ScanConfig imported")
    
    from backend.engine.orchestrator import Orchestrator
    from backend.data.adapters.phemex import PhemexAdapter
    print("✓ Orchestrator imported")
    
    config = ScanConfig(profile="recon")
    print(f"✓ Config created: {config}")

    adapter = PhemexAdapter()
    orchestrator = Orchestrator(config, exchange_adapter=adapter)
    print("✓ Orchestrator initialized with PhemexAdapter")
    
    print("🎉 All imports successful!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()