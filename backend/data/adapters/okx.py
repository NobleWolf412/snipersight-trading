"""
OKX exchange adapter for fetching OHLCV data and market information.
Institutional-tier exchange with huge liquidity and excellent API.
"""

import time
from typing import Optional, Dict, Any, List
from functools import wraps
import pandas as pd
import ccxt
from loguru import logger

from backend.data.adapters.retry import retry_on_rate_limit


class OKXAdapter:
    """
    Adapter for OKX exchange using ccxt library.
    Institutional-grade exchange with high liquidity and pro-level API.
    """

    def __init__(self, testnet: bool = False):
        """
        Initialize OKX exchange connection.

        Args:
            testnet: If True, use OKX demo trading instead of production
        """
        self.exchange = ccxt.okx({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',  # USDT perpetual contracts
            }
        })

        if testnet:
            self.exchange.set_sandbox_mode(True)
            logger.info("OKX adapter initialized in TESTNET mode")
        else:
            logger.info("OKX adapter initialized in PRODUCTION mode")

    @retry_on_rate_limit(max_retries=3)
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
        since: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Fetch OHLCV (candlestick) data from OKX.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT:USDT')
            timeframe: Timeframe string (e.g., '1h', '4h', '1d')
            limit: Number of candles to fetch
            since: Timestamp in milliseconds to fetch candles from

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        try:
            # OKX uses different symbol format for swaps
            fetch_symbol = self._normalize_symbol(symbol)
            
            ohlcv = self.exchange.fetch_ohlcv(
                symbol=fetch_symbol,
                timeframe=timeframe,
                limit=limit,
                since=since
            )

            if not ohlcv:
                logger.warning(f"No OHLCV data returned for {symbol} {timeframe}")
                return pd.DataFrame()

            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )

            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df

        except ccxt.ExchangeError as e:
            logger.error(f"OKX exchange error fetching {symbol} {timeframe}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching {symbol} {timeframe}: {e}")
            raise

    def _normalize_symbol(self, symbol: str) -> str:
        """Convert standard symbol format to OKX swap format."""
        if '/USDT' in symbol and ':USDT' not in symbol:
            return symbol.replace('/USDT', '/USDT:USDT')
        return symbol

    @retry_on_rate_limit(max_retries=3)
    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch current ticker data for a symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            
        Returns:
            Ticker data dict with last, bid, ask, volume, etc.
        """
        try:
            fetch_symbol = self._normalize_symbol(symbol)
            return self.exchange.fetch_ticker(fetch_symbol)
        except ccxt.ExchangeError as e:
            logger.error(f"OKX exchange error fetching ticker for {symbol}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching ticker for {symbol}: {e}")
            raise

    @retry_on_rate_limit(max_retries=3)
    def get_top_symbols(
        self,
        n: int = 50,
        quote_currency: str = 'USDT'
    ) -> List[str]:
        """
        Get top N trading pairs by 24h volume.

        Args:
            n: Number of symbols to return
            quote_currency: Quote currency filter (default: USDT)

        Returns:
            List of symbol strings (e.g., ['BTC/USDT', 'ETH/USDT', ...])
        """
        try:
            markets = self.exchange.load_markets()
            tickers = self.exchange.fetch_tickers()

            # Filter for active perpetual USDT markets
            valid_symbols = []
            for symbol, market in markets.items():
                if (
                    market.get('active', False) and
                    market.get('quote') == 'USDT' and
                    market.get('type') == 'swap' and
                    symbol in tickers
                ):
                    # Convert back to standard format
                    clean_symbol = symbol.replace(':USDT', '')
                    valid_symbols.append(clean_symbol)

            # Sort by 24h volume
            sorted_symbols = sorted(
                valid_symbols,
                key=lambda s: tickers.get(s + ':USDT', {}).get('quoteVolume', 0) or 0,
                reverse=True
            )

            result = sorted_symbols[:n]
            logger.info(f"Retrieved top {len(result)} OKX symbols")
            return result

        except Exception as e:
            logger.error(f"Error fetching top symbols from OKX: {e}")
            raise

    def is_perp(self, symbol: str) -> bool:
        """Detect if a symbol is a USDT perpetual swap on OKX.

        OKX swaps typically use the ':USDT' notation in CCXT markets.
        """
        try:
            if not getattr(self.exchange, 'markets', None):
                self.exchange.load_markets()
            # OKX uses ':USDT' for swap markets; convert symbol to market key
            market_key = symbol if ':USDT' in symbol else symbol.replace('/USDT', '/USDT:USDT')
            info = self.exchange.markets.get(market_key)
            if info and info.get('type') == 'swap':
                return True
        except Exception:
            pass
        su = symbol.upper()
        return (":USDT" in su) or ("-SWAP" in su) or ("PERP" in su)

    def get_exchange_name(self) -> str:
        """Return the exchange name."""
        return "OKX"
