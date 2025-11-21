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
    print("✓ Orchestrator imported")
    
    config = ScanConfig(profile="balanced")
    print(f"✓ Config created: {config}")
    
    orchestrator = Orchestrator(config)
    print("✓ Orchestrator initialized")
    
    print("🎉 All imports successful!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()