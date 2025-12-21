import asyncio
import logging
import sys
import pandas as pd
from datetime import datetime, timezone

# Add project root to path
sys.path.append('/home/maccardi4431/snipersight-trading')

# Mock Phemex Adapter to avoid real network calls if needed, but trying real first
try:
    from backend.data.adapters.phemex import PhemexAdapter
except ImportError:
    print("Could not import PhemexAdapter", flush=True)
    sys.exit(1)

from backend.services.smc_service import configure_smc_service
from backend.shared.models.data import MultiTimeframeData
from backend.shared.config.smc_config import SMCConfig

async def check_ltc_order_blocks():
    # Try multiple symbol formats
    symbols_to_try = ["LTC/USDT:USDT", "uLTCUSD", "LTCUSDT", "LTC/USDT"]
    
    adapter = PhemexAdapter()
    timeframes = ['4h', '1h', '15m']
    tf_data = {}
    found_symbol = None

    for sym in symbols_to_try:
        print(f"Trying symbol: {sym}...", flush=True)
        # Try fetching just one timeframe to validate symbol
        try:
            df = await asyncio.to_thread(adapter.fetch_ohlcv, sym, '4h', limit=10)
            if not df.empty:
                print(f"Success with {sym}!", flush=True)
                found_symbol = sym
                break
        except Exception:
            pass
    
    if not found_symbol:
        print("Could not find valid symbol for LTC on Phemex.", flush=True)
        return

    symbol = found_symbol
    print(f"Proceeding with {symbol}...", flush=True)

    # 1. Fetch Data
    adapter = PhemexAdapter()
    timeframes = ['4h', '1h', '15m']
    tf_data = {}
    
    for tf in timeframes:
        print(f"Fetching {tf} data...", flush=True)
        try:
            df = await asyncio.to_thread(adapter.fetch_ohlcv, symbol, tf, limit=200)
            if not df.empty:
                # Ensure DatetimeIndex
                if 'timestamp' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df = df.set_index('timestamp')
                tf_data[tf] = df
                print(f"Fetched {len(df)} candles for {tf}", flush=True)
            else:
                print(f"No data for {tf}", flush=True)
        except Exception as e:
            print(f"Failed to fetch {tf}: {e}", flush=True)

    if not tf_data:
        print("No data fetched. Exiting.", flush=True)
        return

    # 2. Prepare MultiTimeframeData
    print("Preparing MultiTimeframeData...", flush=True)
    multi_tf_data = MultiTimeframeData(
        symbol=symbol,
        timeframes=tf_data,
        timestamp=datetime.now(timezone.utc)
    )

    # 3. Run SMC Detection
    print("Running SMC Detection...", flush=True)
    # Using 'strike' mode as per user logs
    smc_service = configure_smc_service(mode='strike')
    
    # Get current price
    current_price = 0
    if '15m' in tf_data:
        current_price = tf_data['15m']['close'].iloc[-1]
    elif '1h' in tf_data:
        current_price = tf_data['1h']['close'].iloc[-1]
    else:
        current_price = tf_data['4h']['close'].iloc[-1]
    
    print(f"Current Price: {current_price}", flush=True)

    try:
        snapshot = smc_service.detect(multi_tf_data, current_price)
    except Exception as e:
        print(f"SMC Detection crashed: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return
    
    # 4. Report Findings
    print("--- SMC Detection Results ---", flush=True)
    
    obs = snapshot.order_blocks
    
    # Also check raw OBs if available in result dict (SMCService log logic implies filtering)
    # The detect() method returns SMCSnapshot which has .order_blocks
    # It logs debug info about filtering.
    
    print(f"Total Active Order Blocks detected: {len(obs)}", flush=True)
    
    if obs:
        for i, ob in enumerate(obs):
            mitigated_status = "YES" if ob.mitigated else "NO"
            print(f"OB {i+1}: {ob.type.upper()} | TF: {ob.timeframe} | Price: {ob.price:.2f} | Range: {ob.low:.2f}-{ob.high:.2f} | Mitigated: {mitigated_status}", flush=True)
    
    # Check specifically for HTF (4h)
    htf_obs = [ob for ob in obs if ob.timeframe == '4h']
    print(f"HTF (4h) Order Blocks: {len(htf_obs)}", flush=True)
    
    if not htf_obs:
        print("No HTF (4h) Order Blocks found in active set.", flush=True)

if __name__ == "__main__":
    asyncio.run(check_ltc_order_blocks())
