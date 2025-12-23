import requests

endpoints = [
    "https://api.phemex.com/md/kline",
    "https://api.phemex.com/exchange/public/md/kline"
]
symbols = ["BTCUSD", "sBTCUSDT", "BTCUSDT"]

for url in endpoints:
    for sym in symbols:
        params = {"symbol": sym, "resolution": 60, "limit": 5}
        print(f"\n--- Testing {url} ? symbol={sym} ---")
        try:
            r = requests.get(url, params=params, timeout=5)
            print(f"Status: {r.status_code}")
            print(f"Body: {r.text[:200]}") # Truncate
        except Exception as e:
            print(e)
