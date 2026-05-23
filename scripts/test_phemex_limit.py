import ccxt
print("Initializing Phemex...")
phemex = ccxt.phemex({'enableRateLimit': True, 'options': {'defaultType': 'swap'}})
try:
    print("Fetching OHLCV for BTC/USDT:USDT...")
    ohlcv = phemex.fetch_ohlcv('BTC/USDT:USDT', '15m', limit=750)
    print(f"Success! Got {len(ohlcv)} candles.")
except Exception as e:
    print(f"Failed: {e}")
