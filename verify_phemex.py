
import sys
import os
import pandas as pd
from datetime import datetime
from loguru import logger

# Ensure backend modules can be imported
sys.path.append(os.getcwd())

from backend.data.adapters.phemex import PhemexAdapter

def verify_phemex_adapter():
    print("--- Phemex Adapter Verification (Direct REST) ---")
    
    # Initialize Adapter
    try:
        adapter = PhemexAdapter()
        print("1. Adapter Initialized")
    except Exception as e:
        print(f"CRITICAL: Failed to init Adapter: {e}")
        return

    symbol = 'BTC/USDT:USDT' 
    
    # Test: Fetch OHLCV
    print(f"\n2. Fetching Candles via Adapter for {symbol}...")
    try:
        # Request a small limit, expecting it to be upgraded to 500
        df = adapter.fetch_ohlcv(symbol, '1m', limit=100)
        
        if df.empty:
            print("   ❌ No data returned (Empty DataFrame)!")
            return
            
        last_candle = df.iloc[-1]
        timestamp = last_candle['timestamp']
        open_price = last_candle['open']
        volume = last_candle['volume']
        
        print(f"   ✓ Data Fetched (Total Rows: {len(df)})")
        print(f"   - Time: {timestamp}")
        print(f"   - Open Price: {open_price}")
        print(f"   - Volume: {volume}")
        
        # Scaling Check
        if open_price > 1_000_000:
            print(f"\n⚠️  CRITICAL WARNING: PRICE UNSCALED (Got {open_price}) - Direct REST parsing failed?")
        else:
            print(f"\n✅ Price looks correct (Scaled to {open_price}).")
            
        print("\nCheck backend logs to confirm 'Fetched ... via Direct REST' message appeared.")
            
    except Exception as e:
        print(f"   ❌ Error fetching OHLCV: {e}")

if __name__ == "__main__":
    verify_phemex_adapter()


    # Test 3: Symbol Format Check
    print("\n4. Checking Top Swap Symbols...")
    try:
        # We need to filter manually if logic relies on it, but here we just check market keys
        markets = phemex.load_markets()
        swaps = [s for s, m in markets.items() if m.get('type') == 'swap' and m.get('quote') == 'USDT']
        print(f"   Found {len(swaps)} USDT Swaps.")
        print(f"   First 3: {swaps[:3]}")
        
        if swaps and ':' in swaps[0]:
            print("   ✅ CCXT uses specific suffix (e.g. :USDT) for Swaps. This prevents Spot collision.")
        else:
            print("   ⚠️  CCXT uses simple symbols for Swaps? Check for collision.")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

def print_candle(candle):
    timestamp = candle[0]
    open_price = candle[1]
    volume = candle[5]
    human_time = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
    
    print(f"   ✓ Data Fetched:")
    print(f"   - Time: {human_time} ({timestamp})")
    print(f"   - Open Price: {open_price}")
    print(f"   - Volume: {volume}")
    
    if open_price > 1_000_000:
        print(f"\n⚠️  CRITICAL WARNING: PRICE APPEARS UNSCALED (Expected ~95k, Got {open_price})")
    else:
        print(f"\n✅ Price looks correct (Scaled automatically by CCXT).")


if __name__ == "__main__":
    verify_phemex_data()
