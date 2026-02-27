import traceback
from backend.data.ingestion_pipeline import IngestionPipeline
from backend.data.adapters.phemex import PhemexAdapter

adapter = PhemexAdapter(default_type="swap")
pipeline = IngestionPipeline(adapter)

try:
    print("Fetching one timeframe...")
    df = adapter.fetch_ohlcv("BTC/USDT:USDT", "5m")
    print("Datafetched. Columns:", df.columns)
    
    pipeline.normalize_and_validate(df, "BTC/USDT:USDT", "5m")
except Exception as e:
    traceback.print_exc()
