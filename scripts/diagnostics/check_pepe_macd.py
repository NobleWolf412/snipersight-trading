"""Check PEPE MACD values across timeframes to debug HTF bias detection."""
import ccxt
import pandas as pd
import numpy as np


def calculate_macd(close_prices, fast=12, slow=26, signal=9):
    """Calculate MACD using EMA."""
    ema_fast = close_prices.ewm(span=fast, adjust=False).mean()
    ema_slow = close_prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def main():
    exchange = ccxt.binance({
        "options": {"defaultType": "swap"}
    })
    
    symbol = "1000PEPE/USDT:USDT"
    
    print(f"=== MACD Values for {symbol} ===")
    print(f"=== Fetching from Binance Futures (same as Phemex) ===\n")
    
    for tf in ["4h", "1h", "15m"]:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, tf, limit=100)
            
            if not ohlcv or len(ohlcv) < 50:
                print(f"[{tf}] No data available")
                continue
            
            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            
            # Calculate MACD (12, 26, 9 - standard settings)
            macd_line, signal_line, histogram = calculate_macd(df["close"])
            
            macd_val = float(macd_line.iloc[-1])
            signal_val = float(signal_line.iloc[-1])
            hist_val = float(histogram.iloc[-1])
            hist_prev = float(histogram.iloc[-2])
            
            # Determine bias based on MACD vs Signal
            if macd_val > signal_val:
                bias = "BULLISH (MACD > Signal)"
            elif macd_val < signal_val:
                bias = "BEARISH (MACD < Signal)"
            else:
                bias = "NEUTRAL"
            
            # Position relative to zero
            zero_position = "ABOVE zero" if macd_val > 0 else "BELOW zero"
            
            # Histogram slope
            slope = "Rising" if hist_val > hist_prev else "Falling"
            
            # Close price for reference
            close = float(df["close"].iloc[-1])
            
            # Timestamp of last candle
            from datetime import datetime
            last_ts = datetime.fromtimestamp(ohlcv[-1][0] / 1000)
            
            print(f"[{tf}] Close: {close:.8f} @ {last_ts}")
            print(f"  MACD Line:   {macd_val:.10f}")
            print(f"  Signal Line: {signal_val:.10f}")
            print(f"  Histogram:   {hist_val:.10f}")
            print(f"  Position:    {zero_position}")
            print(f"  Histogram Slope: {slope}")
            print(f"  ──────────────────────────────")
            print(f"  BIAS: {bias}")
            print()
                
        except Exception as e:
            print(f"[{tf}] Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
