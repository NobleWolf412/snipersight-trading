"""
Mock data generators for deterministic testing.
Creates synthetic OHLCV data with different market regimes.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd
from backend.shared.models.data import OHLCV
from loguru import logger


class MockAdapter:
    """
    Mock exchange adapter for testing without network calls.
    Generates deterministic synthetic data that mimics real exchange responses.
    """
    
    def __init__(self, regime: str = 'trending', seed: int = 42):
        """
        Initialize mock adapter.
        
        Args:
            regime: Market regime for data generation ('trending', 'ranging', 'volatile')
            seed: Random seed for reproducibility
        """
        self.regime = regime
        self.seed = seed
        self._markets_loaded = False
        logger.info(f"MockAdapter initialized with regime={regime}, seed={seed}")
    
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
        since: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Generate mock OHLCV data for testing.
        
        Args:
            symbol: Trading pair symbol (ignored, uses same generation)
            timeframe: Timeframe string (affects bar count scaling)
            limit: Number of candles to generate
            since: Ignored in mock
            
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        # Use symbol hash to vary seed slightly per symbol
        symbol_seed = self.seed + hash(symbol) % 1000
        
        ohlcv_list = generate_mock_ohlcv(self.regime, bars=limit, seed=symbol_seed)
        
        # Convert to DataFrame format expected by pipeline
        data = []
        for bar in ohlcv_list:
            data.append({
                'timestamp': bar.timestamp,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            })
        
        df = pd.DataFrame(data)
        return df
    
    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Generate mock ticker data.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Mock ticker dict
        """
        # Generate a single bar to get current price
        ohlcv = generate_mock_ohlcv(self.regime, bars=1, seed=self.seed + hash(symbol) % 1000)
        last_price = ohlcv[0].close if ohlcv else 40000.0
        
        return {
            'symbol': symbol,
            'last': last_price,
            'bid': last_price * 0.9999,
            'ask': last_price * 1.0001,
            'high': last_price * 1.02,
            'low': last_price * 0.98,
            'volume': 10000.0,
            'quoteVolume': last_price * 10000.0,
            'timestamp': datetime.now().timestamp() * 1000
        }
    
    def get_top_symbols(
        self,
        n: int = 50,
        quote_currency: str = 'USDT'
    ) -> List[str]:
        """
        Return mock list of top symbols.
        
        Args:
            n: Number of symbols to return
            quote_currency: Quote currency (ignored)
            
        Returns:
            List of mock symbol strings
        """
        mock_symbols = [
            'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'SOL/USDT',
            'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT', 'DOT/USDT', 'MATIC/USDT',
            'LINK/USDT', 'UNI/USDT', 'ATOM/USDT', 'LTC/USDT', 'ETC/USDT',
            'FIL/USDT', 'APT/USDT', 'ARB/USDT', 'OP/USDT', 'INJ/USDT'
        ]
        return mock_symbols[:n]
    
    def is_perp(self, symbol: str) -> bool:
        """Mock perpetual detection - all mock symbols are perps."""
        return True
    
    def get_exchange_name(self) -> str:
        """Return mock exchange name."""
        return "MockExchange"


def generate_mock_ohlcv(regime: str, bars: int = 100, seed: int = 42) -> List[OHLCV]:
    """
    Generate mock OHLCV data based on market regime.

    Args:
        regime: Market regime - 'trending', 'ranging', or 'volatile'
        bars: Number of bars to generate
        seed: Random seed for reproducibility

    Returns:
        List of OHLCV dataclass instances
    """
    np.random.seed(seed)

    if regime == 'trending':
        return generate_trending_data(bars, seed)
    elif regime == 'ranging':
        return generate_ranging_data(bars, seed)
    elif regime == 'volatile':
        return generate_volatile_data(bars, seed)
    else:
        raise ValueError(f"Unknown regime: {regime}. Use 'trending', 'ranging', or 'volatile'")


def generate_trending_data(bars: int = 100, seed: int = 42) -> List[OHLCV]:
    """
    Generate upward trending OHLCV data with realistic price action.

    Args:
        bars: Number of bars to generate
        seed: Random seed for reproducibility

    Returns:
        List of OHLCV instances with trending pattern
    """
    np.random.seed(seed)
    
    base_price = 40000.0
    trend_strength = 0.001  # 0.1% per bar average
    volatility = 0.02  # 2% volatility
    
    ohlcv_list = []
    current_price = base_price
    start_time = datetime(2024, 1, 1, 0, 0)

    for i in range(bars):
        # Add trend and noise
        price_change = (trend_strength + np.random.normal(0, volatility)) * current_price
        current_price += price_change

        # Generate OHLC with realistic wicks
        open_price = current_price
        close_price = current_price * (1 + np.random.normal(trend_strength, volatility * 0.5))
        
        high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, volatility * 0.3)))
        low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, volatility * 0.3)))

        # Volume with some randomness
        volume = np.random.uniform(100, 1000)

        ohlcv = OHLCV(
            timestamp=start_time + timedelta(hours=i),
            open=round(open_price, 2),
            high=round(high_price, 2),
            low=round(low_price, 2),
            close=round(close_price, 2),
            volume=round(volume, 2)
        )
        ohlcv_list.append(ohlcv)
        current_price = close_price

    return ohlcv_list


def generate_ranging_data(bars: int = 100, seed: int = 42) -> List[OHLCV]:
    """
    Generate ranging/sideways OHLCV data oscillating around a mean.

    Args:
        bars: Number of bars to generate
        seed: Random seed for reproducibility

    Returns:
        List of OHLCV instances with ranging pattern
    """
    np.random.seed(seed)
    
    mean_price = 40000.0
    range_width = 0.05  # 5% range around mean
    volatility = 0.015  # 1.5% volatility
    
    ohlcv_list = []
    start_time = datetime(2024, 1, 1, 0, 0)

    for i in range(bars):
        # Oscillate around mean with sine wave + noise
        oscillation = np.sin(i * 0.2) * range_width
        noise = np.random.normal(0, volatility)
        
        current_price = mean_price * (1 + oscillation + noise)

        # Generate OHLC
        open_price = current_price
        close_price = current_price * (1 + np.random.normal(0, volatility * 0.5))
        
        high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, volatility * 0.4)))
        low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, volatility * 0.4)))

        # Lower volume in ranging markets
        volume = np.random.uniform(50, 500)

        ohlcv = OHLCV(
            timestamp=start_time + timedelta(hours=i),
            open=round(open_price, 2),
            high=round(high_price, 2),
            low=round(low_price, 2),
            close=round(close_price, 2),
            volume=round(volume, 2)
        )
        ohlcv_list.append(ohlcv)

    return ohlcv_list


def generate_volatile_data(bars: int = 100, seed: int = 42) -> List[OHLCV]:
    """
    Generate highly volatile OHLCV data with large price swings.

    Args:
        bars: Number of bars to generate
        seed: Random seed for reproducibility

    Returns:
        List of OHLCV instances with volatile pattern
    """
    np.random.seed(seed)
    
    base_price = 40000.0
    volatility = 0.05  # 5% volatility (high)
    
    ohlcv_list = []
    current_price = base_price
    start_time = datetime(2024, 1, 1, 0, 0)

    for i in range(bars):
        # Large random moves
        price_change = np.random.normal(0, volatility) * current_price
        current_price += price_change

        # Generate OHLC with large wicks
        open_price = current_price
        close_price = current_price * (1 + np.random.normal(0, volatility * 0.8))
        
        high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, volatility * 0.6)))
        low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, volatility * 0.6)))

        # High volume during volatile periods
        volume = np.random.uniform(500, 2000)

        ohlcv = OHLCV(
            timestamp=start_time + timedelta(hours=i),
            open=round(open_price, 2),
            high=round(high_price, 2),
            low=round(low_price, 2),
            close=round(close_price, 2),
            volume=round(volume, 2)
        )
        ohlcv_list.append(ohlcv)
        current_price = close_price

    return ohlcv_list


def generate_with_order_blocks(bars: int = 100, seed: int = 42) -> List[OHLCV]:
    """
    Generate OHLCV data with clear order block formations.
    Useful for testing SMC detection algorithms.

    Args:
        bars: Number of bars to generate
        seed: Random seed for reproducibility

    Returns:
        List of OHLCV instances with order block patterns
    """
    np.random.seed(seed)
    
    base_price = 40000.0
    ohlcv_list = []
    current_price = base_price
    start_time = datetime(2024, 1, 1, 0, 0)

    for i in range(bars):
        # Every 20 bars, create a strong rejection candle (potential OB)
        if i % 20 == 10:
            # Bullish order block: strong down candle with long lower wick
            open_price = current_price
            close_price = current_price * 0.97  # 3% down close
            low_price = current_price * 0.95   # 5% down wick
            high_price = open_price * 1.005
            volume = np.random.uniform(800, 1500)  # Higher volume
        elif i % 20 == 15:
            # Strong displacement up after OB
            open_price = current_price
            close_price = current_price * 1.03  # 3% up
            high_price = close_price * 1.005
            low_price = open_price * 0.995
            volume = np.random.uniform(600, 1200)
        else:
            # Normal price action
            open_price = current_price
            close_price = current_price * (1 + np.random.normal(0, 0.01))
            high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, 0.008)))
            low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, 0.008)))
            volume = np.random.uniform(200, 600)

        ohlcv = OHLCV(
            timestamp=start_time + timedelta(hours=i),
            open=round(open_price, 2),
            high=round(high_price, 2),
            low=round(low_price, 2),
            close=round(close_price, 2),
            volume=round(volume, 2)
        )
        ohlcv_list.append(ohlcv)
        current_price = close_price

    return ohlcv_list
