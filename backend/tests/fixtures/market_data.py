"""
Reusable market data fixtures for testing.

Provides realistic OHLCV data with various market conditions.
"""

import pandas as pd
import numpy as np
from typing import Dict, List
from backend.shared.models.data import OHLCV


def generate_bullish_trend_ohlcv(periods: int = 100, base_price: float = 100.0) -> List[OHLCV]:
    """
    Generate OHLCV data for a bullish trending market.
    
    Creates realistic candles with:
    - Overall upward price movement
    - Increasing volume on up-moves
    - Realistic wicks and body sizes
    """
    candles = []
    current_price = base_price
    
    for i in range(periods):
        # Bullish bias with some noise
        trend = 0.002  # 0.2% average gain per period
        noise = np.random.normal(0, 0.01)
        price_change = trend + noise
        
        # Generate OHLC
        open_price = current_price
        close_price = current_price * (1 + price_change)
        
        # Wicks
        high = max(open_price, close_price) * (1 + abs(np.random.normal(0, 0.003)))
        low = min(open_price, close_price) * (1 - abs(np.random.normal(0, 0.003)))
        
        # Volume increases on up-moves
        base_volume = 1000000
        if close_price > open_price:
            volume = base_volume * (1 + abs(np.random.normal(0.5, 0.2)))
        else:
            volume = base_volume * (1 + abs(np.random.normal(0, 0.2)))
        
        candles.append(OHLCV(
            timestamp=i * 3600,  # 1-hour candles
            open=round(open_price, 2),
            high=round(high, 2),
            low=round(low, 2),
            close=round(close_price, 2),
            volume=round(volume, 2)
        ))
        
        current_price = close_price
    
    return candles


def generate_bearish_trend_ohlcv(periods: int = 100, base_price: float = 100.0) -> List[OHLCV]:
    """Generate OHLCV data for a bearish trending market."""
    candles = []
    current_price = base_price
    
    for i in range(periods):
        # Bearish bias
        trend = -0.002
        noise = np.random.normal(0, 0.01)
        price_change = trend + noise
        
        open_price = current_price
        close_price = current_price * (1 + price_change)
        
        high = max(open_price, close_price) * (1 + abs(np.random.normal(0, 0.003)))
        low = min(open_price, close_price) * (1 - abs(np.random.normal(0, 0.003)))
        
        base_volume = 1000000
        if close_price < open_price:
            volume = base_volume * (1 + abs(np.random.normal(0.5, 0.2)))
        else:
            volume = base_volume * (1 + abs(np.random.normal(0, 0.2)))
        
        candles.append(OHLCV(
            timestamp=i * 3600,
            open=round(open_price, 2),
            high=round(high, 2),
            low=round(low, 2),
            close=round(close_price, 2),
            volume=round(volume, 2)
        ))
        
        current_price = close_price
    
    return candles


def generate_ranging_ohlcv(periods: int = 100, base_price: float = 100.0, range_pct: float = 0.05) -> List[OHLCV]:
    """
    Generate OHLCV data for a ranging (choppy) market.
    
    Args:
        periods: Number of candles
        base_price: Starting price
        range_pct: Range as percentage (e.g., 0.05 = 5% range)
    """
    candles = []
    current_price = base_price
    upper_bound = base_price * (1 + range_pct / 2)
    lower_bound = base_price * (1 - range_pct / 2)
    
    for i in range(periods):
        # Mean reversion within range
        if current_price > base_price:
            bias = -0.001
        else:
            bias = 0.001
        
        noise = np.random.normal(0, 0.005)
        price_change = bias + noise
        
        open_price = current_price
        close_price = np.clip(
            current_price * (1 + price_change),
            lower_bound,
            upper_bound
        )
        
        high = max(open_price, close_price) * (1 + abs(np.random.normal(0, 0.002)))
        low = min(open_price, close_price) * (1 - abs(np.random.normal(0, 0.002)))
        
        volume = 1000000 * (1 + abs(np.random.normal(0, 0.3)))
        
        candles.append(OHLCV(
            timestamp=i * 3600,
            open=round(open_price, 2),
            high=round(high, 2),
            low=round(low, 2),
            close=round(close_price, 2),
            volume=round(volume, 2)
        ))
        
        current_price = close_price
    
    return candles


def generate_with_order_block(
    periods: int = 100,
    ob_position: int = 70,
    direction: str = "bullish"
) -> List[OHLCV]:
    """
    Generate OHLCV with a clear order block pattern.
    
    Order block = last opposing candle before strong directional move
    
    Args:
        periods: Total candles
        ob_position: Where to place the order block
        direction: "bullish" or "bearish"
    """
    candles = generate_bullish_trend_ohlcv(periods - 20) if direction == "bullish" else generate_bearish_trend_ohlcv(periods - 20)
    
    # Insert order block at specified position
    if ob_position < len(candles):
        ob_candle = candles[ob_position]
        
        if direction == "bullish":
            # Last red candle before green surge
            candles[ob_position] = OHLCV(
                timestamp=ob_candle.timestamp,
                open=ob_candle.close,
                high=ob_candle.close * 1.002,
                low=ob_candle.close * 0.995,  # Deeper low
                close=ob_candle.close * 0.996,  # Close below open
                volume=ob_candle.volume * 1.5
            )
            
            # Strong green candles after
            for i in range(ob_position + 1, min(ob_position + 5, len(candles))):
                prev = candles[i - 1]
                candles[i] = OHLCV(
                    timestamp=prev.timestamp + 3600,
                    open=prev.close,
                    high=prev.close * 1.02,
                    low=prev.close * 0.998,
                    close=prev.close * 1.015,
                    volume=prev.volume * 1.8
                )
        else:
            # Last green candle before red dump
            candles[ob_position] = OHLCV(
                timestamp=ob_candle.timestamp,
                open=ob_candle.close,
                high=ob_candle.close * 1.005,
                low=ob_candle.close * 0.998,
                close=ob_candle.close * 1.004,
                volume=ob_candle.volume * 1.5
            )
            
            # Strong red candles after
            for i in range(ob_position + 1, min(ob_position + 5, len(candles))):
                prev = candles[i - 1]
                candles[i] = OHLCV(
                    timestamp=prev.timestamp + 3600,
                    open=prev.close,
                    high=prev.close * 1.002,
                    low=prev.close * 0.98,
                    close=prev.close * 0.985,
                    volume=prev.volume * 1.8
                )
    
    return candles


def generate_with_fvg(
    periods: int = 100,
    fvg_position: int = 50,
    direction: str = "bullish"
) -> List[OHLCV]:
    """
    Generate OHLCV with Fair Value Gap (imbalance).
    
    FVG = Gap between candle 1 high and candle 3 low (bullish)
          or candle 1 low and candle 3 high (bearish)
    """
    candles = generate_bullish_trend_ohlcv(periods) if direction == "bullish" else generate_bearish_trend_ohlcv(periods)
    
    if fvg_position + 2 < len(candles):
        if direction == "bullish":
            # Create gap between candle 1 high and candle 3 low
            candles[fvg_position] = OHLCV(
                timestamp=candles[fvg_position].timestamp,
                open=100.0,
                high=100.5,
                low=99.8,
                close=100.3,
                volume=1000000
            )
            candles[fvg_position + 1] = OHLCV(
                timestamp=candles[fvg_position + 1].timestamp,
                open=100.3,
                high=103.0,  # Big move
                low=100.2,
                close=102.8,
                volume=2000000
            )
            candles[fvg_position + 2] = OHLCV(
                timestamp=candles[fvg_position + 2].timestamp,
                open=102.8,
                high=103.5,
                low=101.0,  # Gap: 101.0 > 100.5
                close=103.2,
                volume=1500000
            )
        else:
            # Bearish FVG
            candles[fvg_position] = OHLCV(
                timestamp=candles[fvg_position].timestamp,
                open=100.0,
                high=100.2,
                low=99.5,
                close=99.7,
                volume=1000000
            )
            candles[fvg_position + 1] = OHLCV(
                timestamp=candles[fvg_position + 1].timestamp,
                open=99.7,
                high=99.8,
                low=97.0,  # Big drop
                close=97.2,
                volume=2000000
            )
            candles[fvg_position + 2] = OHLCV(
                timestamp=candles[fvg_position + 2].timestamp,
                open=97.2,
                high=99.0,  # Gap: 99.0 < 99.5
                low=96.5,
                close=96.8,
                volume=1500000
            )
    
    return candles


def generate_multi_timeframe_data(symbol: str = "BTC/USDT") -> Dict[str, List[OHLCV]]:
    """
    Generate multi-timeframe OHLCV data for testing orchestrator.
    
    Returns dict with keys: '1W', '1D', '4H', '1H', '15m', '5m'
    """
    return {
        "1W": generate_bullish_trend_ohlcv(52, base_price=30000),    # 1 year weekly
        "1D": generate_bullish_trend_ohlcv(365, base_price=35000),   # 1 year daily
        "4H": generate_bullish_trend_ohlcv(180, base_price=40000),   # 30 days 4H
        "1H": generate_with_order_block(720, ob_position=680, direction="bullish"),  # 30 days hourly with OB
        "15m": generate_with_fvg(672, fvg_position=650, direction="bullish"),  # 7 days 15m with FVG
        "5m": generate_bullish_trend_ohlcv(2016, base_price=45000),  # 7 days 5m
    }
