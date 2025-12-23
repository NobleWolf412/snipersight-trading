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
    Supports BOTH spot and perpetual swap (futures) markets.
    """

    def __init__(self, testnet: bool = False, default_type: str = 'swap'):
        """
        Initialize Phemex exchange connection.

        Args:
            testnet: If True, use Phemex testnet instead of production
            default_type: Default market type ('spot' or 'swap')
        """
        self.exchange = ccxt.phemex({
            'enableRateLimit': True,
            'options': {
                'defaultType': default_type,  # Allow configuration
            },
            'timeout': 30000,  # 30s timeout explicitly set
        })
        
        self.default_type = default_type

        if testnet:
            self.exchange.set_sandbox_mode(True)
            logger.info(f"Phemex adapter initialized in TESTNET mode (type: {default_type})")
        else:
            logger.info(f"Phemex adapter initialized in PRODUCTION mode (type: {default_type})")
        
        # Load markets to ensure proper symbol resolution and API routing
        try:
            self.exchange.load_markets()
            logger.debug(f"Loaded {len(self.exchange.markets)} markets from Phemex")
        except Exception as e:
            logger.warning(f"Failed to load markets on init: {e}")

    @retry_on_rate_limit(max_retries=3)
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        market_type: Optional[str] = None,
        limit: int = 500,
        since: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Fetch OHLCV (candlestick) data from Phemex.

        Now properly handles market_type by temporarily switching the exchange's
        defaultType setting before fetching.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            timeframe: Timeframe string (e.g., '1h', '4h', '1d')
            market_type: Market type ('spot' or 'swap'). If specified, temporarily
                        switches the exchange's default type for this fetch.
            limit: Number of candles to fetch
            since: Timestamp in milliseconds to fetch data from

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume

        Raises:
            ccxt.ExchangeError: If exchange returns an error
            ccxt.NetworkError: If network/connection fails
        """
        try:
            # Ensure markets are loaded
            if not getattr(self.exchange, 'markets', None):
                logger.debug(f"Markets not loaded, loading now...")
                self.exchange.load_markets()

            # Dynamically set market type if specified
            original_type = self.exchange.options.get('defaultType')
            if market_type and market_type != original_type:
                logger.debug(f"Temporarily switching exchange type from {original_type} to {market_type} for {symbol}")
                self.exchange.options['defaultType'] = market_type

            try:
                # Fetch OHLCV with the correct market type
                ohlcv = self.exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=limit,
                    since=since
                )

                if not ohlcv:
                    logger.warning(f"No OHLCV data returned for {symbol} {timeframe} (market_type: {market_type or original_type})")
                    return pd.DataFrame()

                # Convert to DataFrame
                df = pd.DataFrame(
                    ohlcv,
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                )

                # Convert timestamp to datetime
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)

                # Reset index to make timestamp a column again (standard format for pipeline)
                df.reset_index(inplace=True)

                logger.debug(f"Fetched {len(df)} candles for {symbol} {timeframe} (market_type: {market_type or original_type})")
                return df

            finally:
                # Always restore original type
                if market_type and market_type != original_type and original_type is not None:
                    self.exchange.options['defaultType'] = original_type
                    logger.debug(f"Restored exchange type to {original_type}")

        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching OHLCV for {symbol} {timeframe} (market_type: {market_type or self.exchange.options.get('defaultType')}): {e}")
            raise
        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching OHLCV for {symbol} {timeframe}: {e}")
            raise


    @retry_on_rate_limit(max_retries=3)
    def fetch_ticker(self, symbol: str, market_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch current ticker data for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            market_type: Market type ('spot' or 'swap'). If None, uses default_type

        Returns:
            Dictionary with ticker data including last price, bid, ask, volume

        Raises:
            ccxt.ExchangeError: If exchange returns an error
        """
        try:
            mt = market_type or self.default_type
            params = {'type': mt} if mt else {}
            
            ticker = self.exchange.fetch_ticker(symbol, params=params)
            logger.debug(f"Fetched ticker for {symbol} ({mt}): {ticker.get('last', 'N/A')}")
            return cast(Dict[str, Any], ticker)

        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching ticker for {symbol} ({market_type or self.default_type}): {e}")
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
    def get_top_symbols(
        self, 
        n: int = 20, 
        quote_currency: str = 'USDT',
        market_type: Optional[str] = None
    ) -> List[str]:
        """
        Get top N trading pairs by 24h volume from Phemex.

        Args:
            n: Number of top symbols to return
            quote_currency: Quote currency to filter by (e.g., 'USDT')
            market_type: Market type ('spot' or 'swap'). If None, uses default_type

        Returns:
            List of symbol strings sorted by 24h volume
        """
        mt = market_type or self.default_type
        markets = None
        
        try:
            markets = self.exchange.load_markets()
            tickers = self.exchange.fetch_tickers()

            # Filter for active markets of the specified type
            valid_symbols = []
            for symbol, market in markets.items():
                if (
                    market.get('active', False) and
                    market.get('quote') == quote_currency and
                    market.get('type') == mt and
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
            logger.info(f"Retrieved top {len(result)} Phemex {mt} symbols by volume")
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
        """
        Detect if a symbol is a perpetual swap on Phemex.
        
        Note: This checks if the symbol EXISTS as a swap.
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

    def is_spot(self, symbol: str) -> bool:
        """
        Detect if a symbol is a spot market on Phemex.
        """
        try:
            if not getattr(self.exchange, 'markets', None):
                self.exchange.load_markets()
            markets_obj = getattr(self.exchange, 'markets', {})
            info = markets_obj.get(symbol) if isinstance(markets_obj, dict) else None
            if info and info.get('type') == 'spot':
                return True
        except Exception:
            pass
        return False

    def supports_trading(self) -> bool:
        """
        Check if adapter supports live trading (requires API keys).
        
        Returns:
        """
        return self.exchange.apiKey is not None and self.exchange.secret is not None
