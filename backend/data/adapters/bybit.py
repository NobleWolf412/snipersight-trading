"""
Bybit exchange adapter for fetching OHLCV data and market information.
#1 Best overall for bot trading - fast APIs, clean data, no geo-blocking.
"""

import time
from typing import Optional, Dict, Any, List
from functools import wraps
import pandas as pd
import ccxt
from loguru import logger


def _retry_on_rate_limit(max_retries: int = 3, backoff: float = 1.0):
    """Decorator to retry function calls on rate limit errors."""
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


class BybitAdapter:
    """
    Adapter for Bybit exchange using ccxt library.
    Best overall CEX for bot trading - excellent API, no geo-blocking, clean OHLCV.
    """

    def __init__(self, testnet: bool = False):
        """
        Initialize Bybit exchange connection.

        Args:
            testnet: If True, use Bybit testnet instead of production
        """
        self.exchange = ccxt.bybit({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',  # USDT perpetual contracts
            }
        })

        if testnet:
            self.exchange.set_sandbox_mode(True)
            logger.info("Bybit adapter initialized in TESTNET mode")
        else:
            logger.info("Bybit adapter initialized in PRODUCTION mode")

    @_retry_on_rate_limit(max_retries=3)
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
        since: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Fetch OHLCV (candlestick) data from Bybit.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            timeframe: Timeframe string (e.g., '1h', '4h', '1d')
            limit: Number of candles to fetch
            since: Timestamp in milliseconds to fetch candles from

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        try:
            ohlcv = self.exchange.fetch_ohlcv(
                symbol=symbol,
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
            logger.error(f"Bybit exchange error fetching {symbol} {timeframe}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching {symbol} {timeframe}: {e}")
            raise

    @_retry_on_rate_limit(max_retries=3)
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
                    market.get('quote') == quote_currency and
                    market.get('type') == 'swap' and
                    symbol in tickers
                ):
                    valid_symbols.append(symbol)

            # Sort by 24h volume
            sorted_symbols = sorted(
                valid_symbols,
                key=lambda s: tickers[s].get('quoteVolume', 0) or 0,
                reverse=True
            )

            result = sorted_symbols[:n]
            logger.info(f"Retrieved top {len(result)} Bybit symbols")
            return result

        except Exception as e:
            logger.error(f"Error fetching top symbols from Bybit: {e}")
            raise

    def get_exchange_name(self) -> str:
        """Return the exchange name."""
        return "Bybit"
