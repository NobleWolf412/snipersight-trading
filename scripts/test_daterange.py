import traceback
import pandas as pd
from backend.data.ingestion_pipeline import IngestionPipeline
from backend.data.adapters.phemex import PhemexAdapter

adapter = PhemexAdapter(default_type="swap")
pipeline = IngestionPipeline(adapter)

try:
    df = adapter.fetch_ohlcv("BTC/USDT:USDT", "5m")
    
    missing_cols = set(["timestamp", "open", "high", "low", "close", "volume"]) - set(df.columns)
    assert not missing_cols, "missing cols!"
    freq = pipeline._to_pandas_freq("5m")
    print("FREQ:", freq)
    
    df_idx = df.set_index("timestamp", drop=True)
    try:
        idx = pd.date_range(start=df_idx.index.min(), end=df_idx.index.max(), freq=freq)
        print("Date range worked!")
    except Exception as e:
        print("ERROR IN DATE RANGE:", repr(e))
except Exception as e:
    traceback.print_exc()
