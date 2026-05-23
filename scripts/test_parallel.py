import asyncio
from backend.data.ingestion_pipeline import IngestionPipeline
from backend.data.adapters.phemex import PhemexAdapter

adapter = PhemexAdapter(default_type="swap")
pipeline = IngestionPipeline(adapter)

symbols = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT"
]
timeframes = ["5m", "15m", "1h", "4h"]

results = pipeline.parallel_fetch(symbols, timeframes, limit=500, max_workers=2)

print("\n--- RESULTS ---")
print(results)
