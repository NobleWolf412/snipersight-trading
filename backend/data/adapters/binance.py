"""
Binance exchange adapter for fetching OHLCV data and market information.
Implements retry logic and rate limit handling.
"""

import time
from typing import Optional, Dict, Any
from functools import wraps
import pandas as pd
import ccxt
from loguru import logger


def _retry_on_rate_limit(max_retries: int = 3, backoff: float = 1.0):
    """
    Decorator to retry function calls on rate limit errors.

    Args:
        max_retries: Maximum number of retry attempts
        backoff: Initial backoff time in seconds (doubles on each retry)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            current_backoff = backoff

            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except ccxt.RateLimitExceeded as e:
                    retries += 1
                    if retries >= max_retries:
                        logger.error(f"Rate limit exceeded after {max_retries} retries")
                        raise
                    
                    logger.warning(
                        f"Rate limit hit, retrying in {current_backoff}s "
                        f"(attempt {retries}/{max_retries})"
                    )
                    time.sleep(current_backoff)
                    current_backoff *= 2
                except ccxt.NetworkError as e:
                    retries += 1
                    if retries >= max_retries:
                        logger.error(f"Network error after {max_retries} retries: {e}")
                        raise
                    
                    logger.warning(f"Network error, retrying in {current_backoff}s: {e}")
                    time.sleep(current_backoff)
                    current_backoff *= 2
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


class BinanceAdapter:
    """
    Adapter for Binance exchange using ccxt library.
    Handles data fetching with rate limiting and error recovery.
    """

    def __init__(self, testnet: bool = False):
        """
        Initialize Binance exchange connection.

        Args:
            testnet: If True, use Binance testnet instead of production
        """
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',  # Use futures market
                'adjustForTimeDifference': True
            }
        })

        if testnet:
            self.exchange.set_sandbox_mode(True)
            logger.info("Binance adapter initialized in TESTNET mode")
        else:
            logger.info("Binance adapter initialized in PRODUCTION mode")

    @_retry_on_rate_limit(max_retries=3)
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
        since: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Fetch OHLCV (candlestick) data from Binance.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            timeframe: Timeframe string (e.g., '1h', '4h', '1d')
            limit: Number of candles to fetch (max 1000 for Binance)
            since: Timestamp in milliseconds to fetch data from

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume

        Raises:
            ccxt.ExchangeError: If the exchange returns an error
            ValueError: If the symbol or timeframe is invalid
        """
        try:
            logger.debug(f"Fetching {limit} {timeframe} candles for {symbol}")
            
            # Fetch raw OHLCV data
            ohlcv = self.exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
                since=since
            )

            if not ohlcv:
                logger.warning(f"No data returned for {symbol} {timeframe}")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )

            # Convert timestamp from milliseconds to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

            # Ensure proper data types
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['close'] = df['close'].astype(float)
            df['volume'] = df['volume'].astype(float)

            # Validate OHLCV relationships
            invalid_rows = (df['high'] < df['low']) | (df['high'] < df['close']) | (df['low'] > df['close'])
            if invalid_rows.any():
                logger.warning(f"Found {invalid_rows.sum()} invalid OHLCV rows for {symbol}")
                df = df[~invalid_rows]

            logger.info(f"✓ Fetched {len(df)} candles for {symbol} {timeframe}")
            return df

        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching {symbol} {timeframe}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching {symbol} {timeframe}: {e}")
            raise

    @_retry_on_rate_limit(max_retries=3)
    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch current ticker information for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')

        Returns:
            Dictionary with ticker data including last price, bid, ask, volume, etc.
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            logger.debug(f"Fetched ticker for {symbol}: {ticker.get('last', 'N/A')}")
            return ticker
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching ticker for {symbol}: {e}")
            raise

    @_retry_on_rate_limit(max_retries=3)
    def fetch_markets(self) -> list:
        """
        Fetch list of all available markets on Binance.

        Returns:
            List of market dictionaries with symbol info
        """
        try:
            markets = self.exchange.fetch_markets()
            logger.info(f"Fetched {len(markets)} markets from Binance")
            return markets
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching markets: {e}")
            raise

    def get_top_symbols(self, n: int = 20, quote_currency: str = 'USDT') -> list:
        """
        Get top N trading pairs by 24h volume.

        Args:
            n: Number of top symbols to return
            quote_currency: Quote currency to filter by (e.g., 'USDT')

        Returns:
            List of symbol strings
        """
        try:
            tickers = self.exchange.fetch_tickers()
            
            # Filter by quote currency
            filtered = {
                symbol: ticker for symbol, ticker in tickers.items()
                if symbol.endswith(f'/{quote_currency}')
            }

            # Sort by 24h volume
            sorted_symbols = sorted(
                filtered.items(),
                key=lambda x: float(x[1].get('quoteVolume', 0)),
                reverse=True
            )

            top_symbols = [symbol for symbol, _ in sorted_symbols[:n]]
            logger.info(f"Top {n} symbols by volume: {', '.join(top_symbols[:5])}...")
            
            return top_symbols

        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching top symbols: {e}")
            raise

    def is_perp(self, symbol: str) -> bool:
        """Detect if a symbol is a perpetual/derivatives market (public data only).

        Prefers exchange market metadata; falls back to conservative heuristics.
        """
        try:
            # Ensure markets are loaded
            if not getattr(self.exchange, 'markets', None):
                self.exchange.load_markets()
            info = self.exchange.markets.get(symbol)
            if info:
                # Binance futures: contract=True and spot=False or type=='future'
                if info.get('type') == 'future' or (info.get('contract') and not info.get('spot')):
                    return True
        except Exception:
            pass
        su = symbol.upper()
        return (":USDT" in su) or ("-SWAP" in su) or ("PERP" in su)
