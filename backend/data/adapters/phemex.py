"""
Phemex exchange adapter for fetching OHLCV data and market information.
Implements retry logic and rate limit handling.
Works with US IPs - no geo-blocking for public endpoints.
"""

import time
from typing import Optional, Dict, Any, List, cast
from functools import wraps
import pandas as pd
import ccxt
from loguru import logger

from backend.data.adapters.retry import retry_on_rate_limit


class PhemexAdapter:
    """
    Adapter for Phemex exchange using ccxt library.
    Handles data fetching with rate limiting and error recovery.
    Works with US IPs - no geo-blocking for public endpoints.
    """

    def __init__(self, testnet: bool = False):
        """
        Initialize Phemex exchange connection.

        Args:
            testnet: If True, use Phemex testnet instead of production
        """
        self.exchange = ccxt.phemex({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',  # Perpetual contracts
            }
        })

        if testnet:
            self.exchange.set_sandbox_mode(True)
            logger.info("Phemex adapter initialized in TESTNET mode")
        else:
            logger.info("Phemex adapter initialized in PRODUCTION mode")

    @retry_on_rate_limit(max_retries=3)
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
        since: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Fetch OHLCV (candlestick) data from Phemex.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            timeframe: Timeframe string (e.g., '1h', '4h', '1d')
            limit: Number of candles to fetch
            since: Timestamp in milliseconds to fetch data from

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume

        Raises:
            ccxt.ExchangeError: If exchange returns an error
            ccxt.NetworkError: If network/connection fails
        """
        try:
            # Fetch OHLCV data
            ohlcv = self.exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
                since=since
            )

            if not ohlcv:
                logger.warning(f"No OHLCV data returned for {symbol} {timeframe}")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )

            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            logger.debug(f"Fetched {len(df)} candles for {symbol} {timeframe}")
            return df

        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching OHLCV for {symbol}: {e}")
            raise
        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching OHLCV for {symbol}: {e}")
            raise

    @retry_on_rate_limit(max_retries=3)
    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch current ticker data for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')

        Returns:
            Dictionary with ticker data including last price, bid, ask, volume

        Raises:
            ccxt.ExchangeError: If exchange returns an error
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            logger.debug(f"Fetched ticker for {symbol}: {ticker.get('last', 'N/A')}")
            return cast(Dict[str, Any], ticker)

        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching ticker for {symbol}: {e}")
            raise

    @retry_on_rate_limit(max_retries=3)
    def fetch_markets(self) -> list:
        """
        Fetch all available markets/trading pairs.

        Returns:
            List of market dictionaries with symbol info

        Raises:
            ccxt.ExchangeError: If exchange returns an error
        """
        try:
            markets = self.exchange.fetch_markets()
            logger.info(f"Fetched {len(markets)} markets from Phemex")
            return markets
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching markets: {e}")
            raise

    @retry_on_rate_limit(max_retries=3)
    def get_top_symbols(self, n: int = 20, quote_currency: str = 'USDT') -> List[str]:
        """
        Get top N trading pairs by 24h volume from Phemex.

        Uses real-time ticker data sorted by quote volume for accurate rankings.
        Falls back to curated list if API call fails.

        Args:
            n: Number of top symbols to return
            quote_currency: Quote currency to filter by (e.g., 'USDT')

        Returns:
            List of symbol strings sorted by 24h volume
        """
        markets = None
        try:
            markets = self.exchange.load_markets()
            tickers = self.exchange.fetch_tickers()

            # Filter for active USDT perpetual/swap markets
            valid_symbols = []
            for symbol, market in markets.items():
                if (
                    market.get('active', False) and
                    market.get('quote') == quote_currency and
                    market.get('type') == 'swap' and
                    symbol in tickers
                ):
                    valid_symbols.append(symbol)

            # Sort by 24h quote volume (descending)
            sorted_symbols = sorted(
                valid_symbols,
                key=lambda s: tickers[s].get('quoteVolume', 0) or 0,
                reverse=True
            )

            result = sorted_symbols[:n]
            logger.info(f"Retrieved top {len(result)} Phemex symbols by volume")
            return result

        except Exception as e:
            logger.warning(f"Error fetching top symbols dynamically: {e}. Using curated fallback.")
            # Expanded fallback list including meme coins for category support
            fallback_pairs = [
                # Majors
                'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'BNB/USDT',
                'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'LINK/USDT', 'MATIC/USDT',
                # Popular alts (2024-2025)
                'NEAR/USDT', 'ATOM/USDT', 'APT/USDT', 'ARB/USDT', 'OP/USDT',
                'SUI/USDT', 'INJ/USDT', 'SEI/USDT', 'TIA/USDT', 'FIL/USDT',
                'JUP/USDT', 'WLD/USDT', 'STX/USDT', 'IMX/USDT', 'RENDER/USDT',
                # Meme coins
                'DOGE/USDT', 'SHIB/USDT', 'PEPE/USDT', 'BONK/USDT', 'WIF/USDT',
                'FLOKI/USDT', 'MEME/USDT', 'TURBO/USDT',
            ]
            
            # Validate against available markets if possible
            try:
                if not markets:
                    markets = self.exchange.load_markets()
                available = [p for p in fallback_pairs if p in markets]
                if available:
                    logger.info(f"Fallback: {len(available)} pairs available on Phemex")
                    return available[:n]
            except Exception:
                pass
            
            return fallback_pairs[:n]

    def is_perp(self, symbol: str) -> bool:
        """Detect if a symbol is a USDT perpetual swap on Phemex.

        Uses CCXT market metadata when available; falls back to conservative heuristics.
        """
        try:
            if not getattr(self.exchange, 'markets', None):
                self.exchange.load_markets()
            markets_obj = getattr(self.exchange, 'markets', {})
            info = markets_obj.get(symbol) if isinstance(markets_obj, dict) else None
            if info and (info.get('type') == 'swap' or (info.get('contract') and not info.get('spot'))):
                return True
        except Exception:
            pass
        su = symbol.upper()
        return (":USDT" in su) or ("-SWAP" in su) or ("PERP" in su)

    def supports_trading(self) -> bool:
        """
        Check if adapter supports live trading (requires API keys).
        
        Returns:
            False for public data only, True if API keys are configured
        """
        return self.exchange.apiKey is not None and self.exchange.secret is not None
