"""
Data models for OHLCV and multi-timeframe market data.

This module defines the core data structures for market data ingestion
and multi-timeframe analysis following the SniperSight architecture.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any
import pandas as pd


@dataclass
class OHLCV:
    """
    Single OHLCV (Open, High, Low, Close, Volume) candlestick data point.
    
    Attributes:
        timestamp: Candle open time
        open: Opening price
        high: Highest price during period
        low: Lowest price during period
        close: Closing price
        volume: Trading volume
    """
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    def __post_init__(self):
        """Validate OHLCV relationships."""
        if self.high < self.low:
            raise ValueError(f"High ({self.high}) cannot be less than Low ({self.low})")
        if self.high < self.close or self.high < self.open:
            raise ValueError(f"High ({self.high}) must be >= Open ({self.open}) and Close ({self.close})")
        if self.low > self.close or self.low > self.open:
            raise ValueError(f"Low ({self.low}) must be <= Open ({self.open}) and Close ({self.close})")


@dataclass
class MultiTimeframeData:
    """
    Multi-timeframe market data for a single symbol.
    
    This is the core data structure passed through the analysis pipeline,
    containing OHLCV data across all relevant timeframes (1W, 1D, 4H, 1H, 15m, 5m).
    
    Attributes:
        symbol: Trading pair symbol (e.g., 'BTC/USDT')
        timeframes: Dictionary mapping timeframe strings to DataFrames
                   Keys: '1W', '1D', '4H', '1H', '15m', '5m'
                   Values: pd.DataFrame with columns [timestamp, open, high, low, close, volume]
        metadata: Additional metadata (exchange, fetch_time, etc.)
    """
    symbol: str
    timeframes: Dict[str, pd.DataFrame]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate timeframe data."""
        if not self.symbol:
            raise ValueError("Symbol cannot be empty")
        if not self.timeframes:
            raise ValueError("Timeframes dictionary cannot be empty")
        
        # Validate DataFrame structure for each timeframe
        required_columns = {'timestamp', 'open', 'high', 'low', 'close', 'volume'}
        for tf, df in self.timeframes.items():
            if not isinstance(df, pd.DataFrame):
                raise TypeError(f"Timeframe '{tf}' data must be a pandas DataFrame")
            missing_cols = required_columns - set(df.columns)
            if missing_cols:
                raise ValueError(f"Timeframe '{tf}' missing required columns: {missing_cols}")
    
    def get_latest_close(self, timeframe: str) -> float:
        """Get the most recent close price for a timeframe."""
        if timeframe not in self.timeframes:
            raise KeyError(f"Timeframe '{timeframe}' not found")
        return float(self.timeframes[timeframe]['close'].iloc[-1])
    
    def get_timeframe_count(self) -> int:
        """Get the number of timeframes available."""
        return len(self.timeframes)

    def get_current_price(self) -> float:
        """
        Get the current market price from the most granular timeframe available.
        
        Returns:
            float: The latest close price from the smallest timeframe found.
            Returns 0.0 if no data is available.
        """
        # Preference order for current price (most granular first)
        preferred_timeframes = ['1m', '5m', '15m', '1h', '4h', '1d', '1w']
        
        # Try to find the most granular timeframe present
        for tf in preferred_timeframes:
            # Check both lowercase and uppercase keys
            if tf in self.timeframes:
                return self.get_latest_close(tf)
            if tf.upper() in self.timeframes:
                return self.get_latest_close(tf.upper())
                
        # Fallback: take any available timeframe if none of the preferred ones match
        if self.timeframes:
            first_tf = next(iter(self.timeframes))
            return self.get_latest_close(first_tf)
            
        return 0.0
