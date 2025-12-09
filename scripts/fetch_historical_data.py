#!/usr/bin/env python3
"""
Fetch Historical Data for Backtesting (YFinance Source)
-----------------------------------------------------
Fetches historical OHLCV data for BTC, ETH, SOL using Yahoo Finance.
Handles 5m/15m (60d limit) and 1h/1d (90d).
Resamples 1h data to create 4h timeframe.

Requires: pip install yfinance
"""

import sys
from pathlib import Path
import time
from datetime import datetime
import pandas as pd
import logging
import yfinance as yf

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

def process_df(df: pd.DataFrame, symbol: str, timeframe: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    
    # Reset index to get 'Date' or 'Datetime' as column
    df = df.reset_index()
    
    # Flatten MultiIndex columns if present (yfinance behavior)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # Identify timestamp column
    ts_col = 'Date' if 'Date' in df.columns else 'Datetime'
    if ts_col not in df.columns:
        # Sometimes yshare returns index name as 'Datetime' but it's not a column until reset
        # Check first column
        ts_col = df.columns[0]
        
    df = df.rename(columns={
        ts_col: 'timestamp',
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Close': 'close',
        'Volume': 'volume'
    })
    
    # Ensure timestamp is datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    
    # Keep only required columns
    cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    df = df[cols]
    
    # Add metadata
    df['symbol'] = symbol
    df['timeframe'] = timeframe
    
    return df

def fetch_data(days_back: int = 90):
    symbol_map = {
        'BTC/USDT': 'BTC-USD',
        'ETH/USDT': 'ETH-USD',
        'SOL/USDT': 'SOL-USD'
    }
    
    all_data_list = []
    
    print(f"🚀 Starting YFINANCE data fetch...")
    
    for target_symbol, yf_symbol in symbol_map.items():
        print(f"\n--- Fetching {target_symbol} ({yf_symbol}) ---")
        
        # 1. Fetch 5m (Limit 60d)
        print("   Fetching 5m (60d)...")
        df_5m = yf.download(yf_symbol, period="59d", interval="5m", progress=False, ignore_tz=False)
        if not df_5m.empty:
            processed_5m = process_df(df_5m, target_symbol, '5m')
            all_data_list.append(processed_5m)
            print(f"   ✅ 5m: {len(processed_5m)} candles")
        else:
            print("   ⚠️ 5m: No data")

        # 2. Fetch 15m (Limit 60d)
        print("   Fetching 15m (60d)...")
        df_15m = yf.download(yf_symbol, period="59d", interval="15m", progress=False, ignore_tz=False)
        if not df_15m.empty:
            processed_15m = process_df(df_15m, target_symbol, '15m')
            all_data_list.append(processed_15m)
            print(f"   ✅ 15m: {len(processed_15m)} candles")
            
        # 3. Fetch 1h (Limit 90d)
        print("   Fetching 1h (90d)...")
        df_1h = yf.download(yf_symbol, period=f"{days_back}d", interval="1h", progress=False, ignore_tz=False)
        if not df_1h.empty:
            processed_1h = process_df(df_1h, target_symbol, '1h')
            all_data_list.append(processed_1h)
            print(f"   ✅ 1h: {len(processed_1h)} candles")
            
            # 4. Resample 1h -> 4h
            print("   Constructing 4h from 1h...")
            # Use processed_1h which has known lowercase columns and clean timestamp
            df_for_resample = processed_1h.set_index('timestamp')
            
            df_4h = df_for_resample.resample('4h').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            
            # process_df handles resetting index and adding metadata
            processed_4h = process_df(df_4h, target_symbol, '4h')
            all_data_list.append(processed_4h)
            print(f"   ✅ 4h: {len(processed_4h)} candles (derived)")

        # 5. Fetch 1d (Limit 90d)
        print("   Fetching 1d (90d)...")
        df_1d = yf.download(yf_symbol, period=f"{days_back}d", interval="1d", progress=False, ignore_tz=False)
        if not df_1d.empty:
            processed_1d = process_df(df_1d, target_symbol, '1d')
            all_data_list.append(processed_1d)
            print(f"   ✅ 1d: {len(processed_1d)} candles")
            
    # Combine
    print("-" * 60)
    print("💾 Saving data...")
    
    if not all_data_list:
        print("❌ No data fetched!")
        return

    full_df = pd.concat(all_data_list, ignore_index=True)
    
    # Sort
    full_df = full_df.sort_values(['symbol', 'timeframe', 'timestamp'])
    
    output_dir = Path("backend/tests/backtest")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "backtest_multitimeframe_real.csv"
    
    full_df.to_csv(output_path, index=False)
    print(f"🎉 Done! Saved {len(full_df)} rows to {output_path}")

if __name__ == "__main__":
    fetch_data()
