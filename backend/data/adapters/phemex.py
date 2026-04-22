"""
Phemex exchange adapter for fetching OHLCV data and market information.
Implements retry logic and rate limit handling.
Works with US IPs - no geo-blocking for public endpoints.
"""

import os
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

    def __init__(
        self,
        testnet: bool = False,
        default_type: str = "swap",
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ):
        """
        Initialize Phemex exchange connection.

        Args:
            testnet: If True, use Phemex testnet instead of production
            default_type: Default market type ('spot' or 'swap')
            api_key: Phemex API key (falls back to PHEMEX_API_KEY env var)
            api_secret: Phemex API secret (falls back to PHEMEX_API_SECRET env var)
        """
        _key = api_key or os.getenv("PHEMEX_API_KEY")
        _secret = api_secret or os.getenv("PHEMEX_API_SECRET")

        exchange_config: Dict[str, Any] = {
            "enableRateLimit": True,
            "options": {
                "defaultType": default_type,
            },
            "timeout": 30000,
        }
        if _key:
            exchange_config["apiKey"] = _key
        if _secret:
            exchange_config["secret"] = _secret

        self.exchange = ccxt.phemex(exchange_config)

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

    def get_market_info(self, symbol: str) -> Dict[str, float]:
        """
        Fetch market precision information (tick size and lot size).
        
        Args:
            symbol: Trading pair
            
        Returns:
            Dict with tick_size and lot_size
        """
        try:
            if not self.exchange.markets:
                self.exchange.load_markets()
            
            market = self.exchange.market(symbol)
            # CCXT precision can be standard (e.g. 0.01) or decimal places (e.g. 2)
            # We want the absolute value (tick size)
            tick_size = market["precision"].get("price", 0.0)
            lot_size = market["precision"].get("amount", 0.0)
            
            # If CCXT returns decimal places (int), convert to absolute value
            if isinstance(tick_size, int):
                tick_size = 10 ** -tick_size
            if isinstance(lot_size, int):
                lot_size = 10 ** -lot_size
                
            return {
                "tick_size": float(tick_size),
                "lot_size": float(lot_size),
            }
        except Exception as e:
            logger.warning(f"Failed to fetch market info for {symbol}: {e}")
            return {"tick_size": 0.0, "lot_size": 0.0}

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
        Get top N trading pairs ranked by volume × volatility × momentum from Phemex.

        Scoring: volume * (1 + volatility) * (1 + momentum_factor)
        - volatility = (24h high - low) / close   — range expansion signal
        - momentum_factor = min(abs(24h pct_change) / 20, 1.0) × 0.5  — trending pairs score up to 50% higher
        Minimum volume floor: 500,000 USDT daily — filters out illiquid micro-caps.
        """
        mt = market_type or self.default_type
        markets = None

        try:
            markets = self.exchange.load_markets()

            # fetch_tickers() returns ALL pairs in one call; can time out on Phemex.
            # Try it first; on failure, fall through to the curated fallback.
            tickers = self.exchange.fetch_tickers()

            # Filter: active, correct quote currency, correct market type, has ticker data
            MIN_VOLUME_USDT = 500_000
            valid_symbols = []
            for symbol, market in markets.items():
                if (
                    market.get("active", False)
                    and market.get("quote") == quote_currency
                    and market.get("type") == mt
                    and symbol in tickers
                ):
                    vol = tickers[symbol].get("quoteVolume", 0) or 0
                    if vol >= MIN_VOLUME_USDT:
                        valid_symbols.append(symbol)

            def calculate_score(symbol: str) -> float:
                ticker = tickers[symbol]
                volume = ticker.get("quoteVolume", 0) or 0
                high = ticker.get("high", 0) or 0
                low = ticker.get("low", 0) or 0
                close = ticker.get("close", 0) or ticker.get("last", 0) or 1

                volatility = (high - low) / close if close > 0 else 0

                # Momentum: pairs with a large 24h move (either direction) score higher.
                # A 20% move adds 50% to the base score (momentum_factor caps at 1.0).
                pct_change = abs(ticker.get("percentage", 0) or 0)
                momentum_factor = min(pct_change / 20.0, 1.0)

                return volume * (1 + volatility) * (1 + momentum_factor * 0.5)

            sorted_symbols = sorted(valid_symbols, key=calculate_score, reverse=True)
            result = sorted_symbols[:n]
            logger.info(
                f"Dynamic universe: top {len(result)} Phemex {mt} symbols "
                f"(volume×volatility×momentum) from {len(valid_symbols)} eligible pairs"
            )
            return result

        except Exception as e:
            logger.warning(f"Dynamic symbol fetch failed ({e}). Using curated 2025 fallback.")
            # Updated fallback — 2025-relevant pairs covering majors, trending alts, and memes
            fallback_pairs = [
                # Core majors (always liquid)
                "BTC/USDT",
                "ETH/USDT",
                "SOL/USDT",
                "XRP/USDT",
                "BNB/USDT",
                # Large-cap alts
                "ADA/USDT",
                "AVAX/USDT",
                "SUI/USDT",
                "TON/USDT",
                "NEAR/USDT",
                "APT/USDT",
                "ARB/USDT",
                "OP/USDT",
                "INJ/USDT",
                "SEI/USDT",
                "JUP/USDT",
                "LINK/USDT",
                "DOT/USDT",
                "ATOM/USDT",
                "TIA/USDT",
                # Meme coins
                "DOGE/USDT",
                "SHIB/USDT",
                "PEPE/USDT",
                "WIF/USDT",
                "BONK/USDT",
                "FLOKI/USDT",
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
        """Check if adapter supports live trading (requires API keys)."""
        return bool(self.exchange.apiKey and self.exchange.secret)

    # ------------------------------------------------------------------
    # Authenticated trading methods (require API keys)
    # ------------------------------------------------------------------

    @retry_on_rate_limit(max_retries=3)
    def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Place an order on Phemex via CCXT.

        Args:
            symbol: Trading pair (e.g. 'BTC/USDT')
            order_type: 'market' or 'limit'
            side: 'buy' or 'sell'
            amount: Quantity in base asset
            price: Limit price (required for limit orders)
            params: Extra CCXT params (timeInForce, reduceOnly, etc.)

        Returns:
            CCXT order dict with id, status, filled, remaining, etc.
        """
        if not self.supports_trading():
            raise ccxt.AuthenticationError("API keys required for order placement")
        try:
            order = self.exchange.create_order(
                symbol, order_type, side, amount, price, params or {}
            )
            logger.info(
                f"Order created on Phemex: {side} {amount} {symbol} @ {price} "
                f"(id={order.get('id')})"
            )
            return order
        except ccxt.InsufficientFunds as e:
            logger.error(f"Insufficient funds for {side} {amount} {symbol}: {e}")
            raise
        except ccxt.InvalidOrder as e:
            logger.error(f"Invalid order {side} {amount} {symbol}: {e}")
            raise
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error placing order {side} {amount} {symbol}: {e}")
            raise

    @retry_on_rate_limit(max_retries=3)
    def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Cancel an open order on Phemex."""
        if not self.supports_trading():
            raise ccxt.AuthenticationError("API keys required to cancel orders")
        try:
            result = self.exchange.cancel_order(order_id, symbol)
            logger.info(f"Order cancelled: {order_id} {symbol}")
            return result
        except ccxt.OrderNotFound:
            logger.warning(f"Order not found for cancel: {order_id} {symbol}")
            return {"id": order_id, "status": "not_found"}
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error cancelling {order_id}: {e}")
            raise

    @retry_on_rate_limit(max_retries=3)
    def fetch_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Fetch a single order's current status from Phemex."""
        if not self.supports_trading():
            raise ccxt.AuthenticationError("API keys required to fetch orders")
        return self.exchange.fetch_order(order_id, symbol)

    @retry_on_rate_limit(max_retries=3)
    def fetch_balance(self) -> Dict[str, Any]:
        """
        Fetch account balance from Phemex.

        Returns:
            Dict with 'free', 'used', 'total' keys, each mapping currency → amount.
        """
        if not self.supports_trading():
            raise ccxt.AuthenticationError("API keys required to fetch balance")
        return self.exchange.fetch_balance()

    @retry_on_rate_limit(max_retries=3)
    def fetch_positions(self, symbols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Fetch open positions from Phemex.

        Args:
            symbols: Filter by symbol list (None = all positions)

        Returns:
            List of CCXT position dicts.
        """
        if not self.supports_trading():
            raise ccxt.AuthenticationError("API keys required to fetch positions")
        return self.exchange.fetch_positions(symbols)

    @retry_on_rate_limit(max_retries=3)
    def set_leverage(self, leverage: int, symbol: str) -> None:
        """Set leverage for a symbol on Phemex."""
        if not self.supports_trading():
            raise ccxt.AuthenticationError("API keys required to set leverage")
        try:
            self.exchange.set_leverage(leverage, symbol)
            logger.info(f"Leverage set to {leverage}x for {symbol}")
        except ccxt.ExchangeError as e:
            logger.warning(f"Could not set leverage for {symbol}: {e}")
