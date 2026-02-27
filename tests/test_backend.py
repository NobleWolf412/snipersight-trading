#!/usr/bin/env python3
"""
Test script for the backend API functionality
"""

import asyncio
import sys
from backend.api_server import get_signals

async def test_signals():
    """Test the signals endpoint directly"""
    try:
        print("Testing signals endpoint...")
        # Pass raw primitives for parameters that have FastAPI Query defaults
        # Use a valid sniper_mode defined in scanner_modes (e.g., 'recon')
        result = await get_signals(limit=3, min_score=70, sniper_mode="recon", exchange="phemex", majors=True, altcoins=True, meme_mode=False, leverage=1)
        print(f"✓ Signals endpoint working: {result['total']} signals generated")
        print(f"  Data source: {result.get('data_source', 'unknown')}")
        
        # Show first signal as example
        if result['signals']:
            signal = result['signals'][0]
            print(f"  Example: {signal['symbol']} {signal['direction']} @ {signal['current_price']}")
        
        return True
    except Exception as e:
        print(f"✗ Signals endpoint failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_signals())
    sys.exit(0 if success else 1)