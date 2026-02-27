"""
Phemex exchange adapter for fetching OHLCV data and market information.
Implements retry logic and rate limit handling.
Works with US IPs - no geo-blocking for public endpoints.
"""

import time
from typing import Optional, Dict, Any, List, cast
import pandas as pd
import ccxt
import random
from loguru import logger

from backend.data.adapters.retry import retry_on_rate_limit


class PhemexAdapter:
    """
    Adapter for Phemex exchange using ccxt library.
    Supports BOTH spot and perpetual swap (futures) markets.
    """

    def __init__(self, testnet: bool = False, default_type: str = "swap"):
        """
        Initialize Phemex exchange connection.

        Args:
            testnet: If True, use Phemex testnet instead of production
            default_type: Default market type ('spot' or 'swap')
        """
        self.exchange = ccxt.phemex(
            {
                "enableRateLimit": True,
                "options": {
                    "defaultType": default_type,  # Allow configuration
                },
                "timeout": 30000,  # 30s timeout explicitly set
            }
        )

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
        since: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data using CCXT (Primary) with Direct REST Fallback.

        Improvements:
        1. Enforces limit >= 500 (Phemex Requirement)
        2. Uses CCXT's built-in rate limiter
        3. Falls back to Direct REST if CCXT fails
        """
        import requests

        # Enforce Phemex minimum limit of 500 to avoid Error 30000
        safe_limit = max(500, limit)

        try:
            # 1. Primary: CCXT Fetch (Handles Rate Limits & Parsing)
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=safe_limit, since=since)

            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            df.reset_index(inplace=True)

            # Simple check to ensure we got data
            if df.empty:
                logger.warning(f"CCXT returned empty data for {symbol}")
                # Don't fallback on empty, it might be valid empty.
                return df

            return df

        except Exception as e:
            logger.warning(f"CCXT fetch failed for {symbol}: {e}. Attempting Direct REST Fallback.")

            # 2. Fallback: Direct REST API
            try:
                # Resolve Symbol
                phemex_symbol = symbol.replace("/", "").replace(":USDT", "")
                if self.is_spot(symbol) and not phemex_symbol.startswith("s"):
                    phemex_symbol = f"s{phemex_symbol}"

                # Resolve Resolution
                tf_map = {
                    "1m": 60,
                    "3m": 180,
                    "5m": 300,
                    "15m": 900,
                    "30m": 1800,
                    "1h": 3600,
                    "2h": 7200,
                    "4h": 14400,
                    "6h": 21600,
                    "12h": 43200,
                    "1d": 86400,
                    "1w": 604800,
                    "1M": 2592000,
                }
                resolution = tf_map.get(timeframe, 60)

                url = "https://api.phemex.com/exchange/public/md/kline"
                end_time = int(time.time())

                params = {
                    "symbol": phemex_symbol,
                    "resolution": resolution,
                    "limit": safe_limit,
                    "to": end_time,
                }
                if since:
                    params["from"] = int(since / 1000)
                else:
                    params["from"] = end_time - (resolution * params["limit"])

                # Polite request
                time.sleep(random.uniform(0.5, 1.0))  # Extra polite on fallback
                response = requests.get(url, params=params, timeout=5)
                data = response.json()

                if data.get("code", -1) != 0:
                    raise ccxt.ExchangeError(f"Phemex API Error: {data.get('msg')}")

                rows = data.get("data", {}).get("rows", [])
                if not rows:
                    return pd.DataFrame()

                # Parse
                # Assume CCXT scaling logic (10^8 for most pairs)
                # But since this is fallback, keep it simple
                scale = 100000000.0 if (rows and rows[0][1] > 1000000) else 1.0

                parsed_data = []
                for r in rows:
                    parsed_data.append(
                        {
                            "timestamp": r[0] * 1000,
                            "open": r[1] / scale,
                            "high": r[2] / scale,
                            "low": r[3] / scale,
                            "close": r[4] / scale,
                            "volume": r[5] / scale if self.is_spot(symbol) else r[5],
                        }
                    )

                df_direct = pd.DataFrame(parsed_data)
                df_direct["timestamp"] = pd.to_datetime(df_direct["timestamp"], unit="ms")
                df_direct.set_index("timestamp", inplace=True)
                df_direct.reset_index(inplace=True)

                logger.info(f"✓ Recovered {symbol} via Direct REST Fallback")
                return df_direct

            except Exception as direct_err:
                logger.error(f"Direct REST Fallback also failed for {symbol}: {direct_err}")
                raise e  # Raise original CCXT error if both fail

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
            params = {"type": mt} if mt else {}

            ticker = self.exchange.fetch_ticker(symbol, params=params)
            logger.debug(f"Fetched ticker for {symbol} ({mt}): {ticker.get('last', 'N/A')}")
            return cast(Dict[str, Any], ticker)

        except ccxt.ExchangeError as e:
            logger.error(
                f"Exchange error fetching ticker for {symbol} ({market_type or self.default_type}): {e}"
            )
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
        self, n: int = 20, quote_currency: str = "USDT", market_type: Optional[str] = None
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
                    market.get("active", False)
                    and market.get("quote") == quote_currency
                    and market.get("type") == mt
                    and symbol in tickers
                ):
                    valid_symbols.append(symbol)

            # Sort by volume * volatility (descending)
            # Volatility = (24h high - low) / close, acts as range expansion multiplier
            def calculate_score(symbol: str) -> float:
                ticker = tickers[symbol]
                volume = ticker.get("quoteVolume", 0) or 0
                high = ticker.get("high", 0) or 0
                low = ticker.get("low", 0) or 0
                close = ticker.get("close", 0) or ticker.get("last", 0) or 1  # Avoid div by zero

                # Volatility as normalized 24h range
                volatility = (high - low) / close if close > 0 else 0

                # Composite score: volume weighted by volatility
                # Higher volatility = more likely to have active setups forming
                return volume * (1 + volatility)

            sorted_symbols = sorted(valid_symbols, key=calculate_score, reverse=True)

            result = sorted_symbols[:n]
            logger.info(f"Retrieved top {len(result)} Phemex {mt} symbols by volume * volatility")
            return result

        except Exception as e:
            logger.warning(f"Error fetching top symbols dynamically: {e}. Using curated fallback.")
            # Expanded fallback list including meme coins for category support
            fallback_pairs = [
                # Majors
                "BTC/USDT",
                "ETH/USDT",
                "SOL/USDT",
                "XRP/USDT",
                "BNB/USDT",
                "ADA/USDT",
                "AVAX/USDT",
                "DOT/USDT",
                "LINK/USDT",
                "MATIC/USDT",
                # Popular alts (2024-2025)
                "NEAR/USDT",
                "ATOM/USDT",
                "APT/USDT",
                "ARB/USDT",
                "OP/USDT",
                "SUI/USDT",
                "INJ/USDT",
                "SEI/USDT",
                "TIA/USDT",
                "FIL/USDT",
                "JUP/USDT",
                "WLD/USDT",
                "STX/USDT",
                "IMX/USDT",
                "RENDER/USDT",
                # Meme coins
                "DOGE/USDT",
                "SHIB/USDT",
                "PEPE/USDT",
                "BONK/USDT",
                "WIF/USDT",
                "FLOKI/USDT",
                "MEME/USDT",
                "TURBO/USDT",
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
            if not getattr(self.exchange, "markets", None):
                self.exchange.load_markets()
            markets_obj = getattr(self.exchange, "markets", {})
            info = markets_obj.get(symbol) if isinstance(markets_obj, dict) else None
            if info and (
                info.get("type") == "swap" or (info.get("contract") and not info.get("spot"))
            ):
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
            if not getattr(self.exchange, "markets", None):
                self.exchange.load_markets()
            markets_obj = getattr(self.exchange, "markets", {})
            info = markets_obj.get(symbol) if isinstance(markets_obj, dict) else None
            if info and info.get("type") == "spot":
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
