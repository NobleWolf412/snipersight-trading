"""
Data Router - Market data endpoints extracted from api_server.py

Contains market data endpoints:
- /api/market/price/{symbol} - Get current price
- /api/market/prices - Get multiple prices
- /api/market/candles/{symbol} - Get OHLCV data
- /api/market/regime - Get market regime analysis
- /api/market/cycles - Get cycle timing context

Cache management endpoints:
- /api/cache/stats - OHLCV cache statistics
- /api/cache/entries - Cache entry details
- /api/cache/clear - Clear all cache
- /api/cache/invalidate - Invalidate specific symbol

Dependencies are injected via configure_data_router() to avoid circular imports.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import logging
import asyncio
import time
import pandas as pd

from backend.data.ohlcv_cache import get_ohlcv_cache
from backend.routers.htf_opportunities import _get_adapter as get_htf_phemex_adapter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Market Data"])


# =============================================================================
# Enums (shared with api_server.py)
# =============================================================================

class Timeframe(str, Enum):
    """Supported timeframes."""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


# =============================================================================
# Dependency Injection - Shared state access
# =============================================================================

_shared_state: Dict[str, Any] = {}


def configure_data_router(
    exchange_adapters: Dict,
    price_cache,
    price_cache_ttl: int,
    cycles_cache,
    regime_cache,
    regime_detector,
    orchestrator,
):
    """Configure router with shared dependencies from api_server.py"""
    _shared_state['exchange_adapters'] = exchange_adapters
    _shared_state['price_cache'] = price_cache
    _shared_state['price_cache_ttl'] = price_cache_ttl
    _shared_state['cycles_cache'] = cycles_cache
    _shared_state['regime_cache'] = regime_cache
    _shared_state['regime_detector'] = regime_detector
    _shared_state['orchestrator'] = orchestrator


def get_exchange_adapters():
    return _shared_state.get('exchange_adapters', {})


# Adapter instance cache - singleton pattern for warm adapters
_adapter_instances: Dict[str, Any] = {}


def get_or_create_adapter(exchange_key: str):
    """Get or create a cached adapter instance.
    
    This ensures adapters are reused between requests, keeping them warm
    with loaded markets and proper CCXT state.
    """
    global _adapter_instances
    
    if exchange_key in _adapter_instances:
        return _adapter_instances[exchange_key]
    
    exchange_adapters = get_exchange_adapters()
    if exchange_key not in exchange_adapters:
        return None
    
    # Create new adapter instance and cache it
    adapter = exchange_adapters[exchange_key]()
    _adapter_instances[exchange_key] = adapter
    logger.info(f"Created and cached adapter instance for {exchange_key}")
    return adapter


def get_price_cache():
    return _shared_state.get('price_cache')


def get_price_cache_ttl():
    return _shared_state.get('price_cache_ttl', 5)


# =============================================================================
# Price Endpoints
# =============================================================================

@router.get("/api/market/price/{symbol}")
async def get_price(symbol: str, exchange: str | None = Query(default=None)):
    """Get current price for symbol via selected exchange adapter.

    Falls back to Phemex if no exchange provided. Uses ccxt under the hood.
    """
    exchange_adapters = get_exchange_adapters()
    
    try:
        exchange_key = (exchange or 'phemex').lower()
        if exchange_key not in exchange_adapters:
            raise HTTPException(status_code=400, detail=f"Unsupported exchange: {exchange_key}")

        adapter = exchange_adapters[exchange_key]()

        request_symbol = symbol
        ticker = adapter.fetch_ticker(symbol)
        last_price = ticker.get('last') or ticker.get('close') or 0.0
        ts_ms = ticker.get('timestamp')
        if ts_ms is None:
            dt_iso = datetime.now(timezone.utc).isoformat()
        else:
            try:
                dt_iso = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
            except Exception:
                dt_iso = datetime.now(timezone.utc).isoformat()

        return {
            "symbol": request_symbol,
            "price": float(last_price) if last_price is not None else 0.0,
            "timestamp": dt_iso,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch price for %s on %s: %s", symbol, exchange or 'phemex', e)
        raise HTTPException(status_code=502, detail="Failed to fetch price from exchange") from e


@router.get("/api/market/prices")
async def get_prices(
    symbols: str = Query(..., description="Comma-separated list of symbols (e.g., BTC/USDT,ETH/USDT)"),
    exchange: str | None = Query(default=None)
):
    """Get current prices for multiple symbols in one request.
    
    Reduces N requests to 1 for watchlists. Returns partial results if some symbols fail.
    """
    exchange_adapters = get_exchange_adapters()
    price_cache = get_price_cache()
    price_cache_ttl = get_price_cache_ttl()
    
    try:
        exchange_key = (exchange or 'phemex').lower()
        if exchange_key not in exchange_adapters:
            raise HTTPException(status_code=400, detail=f"Unsupported exchange: {exchange_key}")

        adapter = exchange_adapters[exchange_key]()
        symbol_list = [s.strip() for s in symbols.split(',') if s.strip()]
        
        if not symbol_list:
            raise HTTPException(status_code=400, detail="No symbols provided")
        
        if len(symbol_list) > 50:
            raise HTTPException(status_code=400, detail="Maximum 50 symbols per request")

        results = []
        errors = []
        
        async def fetch_one(symbol: str):
            # Check cache first
            cache_key = f"{exchange_key}:{symbol}"
            if price_cache:
                cached = price_cache.get(cache_key)
                if cached and (time.time() - cached.get('_cached_at', 0)) < price_cache_ttl:
                    logger.debug(f"Cache hit for {cache_key}")
                    return cached.get('data'), None
            
            try:
                loop = asyncio.get_event_loop()
                ticker = await loop.run_in_executor(None, adapter.fetch_ticker, symbol)
                
                last_price = ticker.get('last') or ticker.get('close') or 0.0
                ts_ms = ticker.get('timestamp')
                
                if ts_ms is None:
                    dt_iso = datetime.now(timezone.utc).isoformat()
                else:
                    try:
                        dt_iso = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
                    except Exception:
                        dt_iso = datetime.now(timezone.utc).isoformat()
                
                result = {
                    "symbol": symbol,
                    "price": float(last_price) if last_price is not None else 0.0,
                    "timestamp": dt_iso,
                }
                
                # Store in cache
                if price_cache:
                    price_cache.set(cache_key, {'data': result})
                
                return result, None
            except Exception as e:
                logger.warning("Failed to fetch price for %s: %s", symbol, e)
                return None, {"symbol": symbol, "error": str(e)}
        
        fetch_results = await asyncio.gather(*[fetch_one(sym) for sym in symbol_list])
        
        for result, error in fetch_results:
            if result:
                results.append(result)
            if error:
                errors.append(error)
        
        return {
            "prices": results,
            "total": len(results),
            "errors": errors if errors else None,
            "exchange": exchange_key
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Bulk price fetch failed: %s", e)
        raise HTTPException(status_code=502, detail="Failed to fetch prices from exchange") from e


@router.get("/api/market/candles/{symbol:path}")
async def get_candles(
    symbol: str,
    timeframe: Timeframe = Query(default=Timeframe.H1),
    limit: int = Query(default=100, ge=1, le=1000),
    exchange: str | None = Query(default=None),
    market_type: str = Query(default='swap')
):
    """Get candlestick data via selected exchange adapter or cache.

    Implements multi-tier fallback:
    1. Try OHLCV cache (fastest, from scanner)
    2. Try fresh fetch with requested market type
    3. Try fresh fetch with alternate market type (swap ↔ spot)
    4. Return helpful error with guidance
    """
    try:
        exchange_key = (exchange or 'phemex').lower()
        errors_encountered = []

        # Tier 1: Try to get data from OHLCV cache (scanner's cached data)
        cache = get_ohlcv_cache()
        if cache:
            cached_df = cache.get(symbol, timeframe.value)
            if cached_df is not None and not cached_df.empty:
                logger.info(f"✓ Serving {symbol} {timeframe.value} from OHLCV cache ({len(cached_df)} candles)")
                df = cached_df.tail(limit) if len(cached_df) > limit else cached_df

                candles = []
                for _, row in df.iterrows():
                    candles.append({
                        'timestamp': row['timestamp'].to_pydatetime().isoformat(),
                        'open': float(row['open']),
                        'high': float(row['high']),
                        'low': float(row['low']),
                        'close': float(row['close']),
                        'volume': float(row['volume']),
                    })

                return {
                    "symbol": symbol,
                    "timeframe": timeframe.value,
                    "candles": candles,
                    "source": "cache"
                }
            else:
                errors_encountered.append("cache_miss")
                logger.debug(f"Cache miss for {symbol} {timeframe.value}")
        else:
            errors_encountered.append("cache_unavailable")

        # Tier 2 & 3: Cache miss - try to fetch fresh data with fallback
        logger.info(f"Attempting fresh fetch for {symbol} {timeframe.value}")

        # Use the HTF opportunities singleton adapter for phemex (it's warm and works)
        if exchange_key == 'phemex':
            adapter = get_htf_phemex_adapter()
        else:
            adapter = get_or_create_adapter(exchange_key)
            if adapter is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported exchange: {exchange_key}"
                )

        # Try both market types with detailed error tracking
        df = pd.DataFrame()
        successful_market_type = None

        for attempt_market_type in [market_type, 'spot' if market_type == 'swap' else 'swap']:
            try:
                logger.debug(f"Attempting fetch: {symbol} {timeframe.value} as {attempt_market_type}")
                df = adapter.fetch_ohlcv(symbol, timeframe.value, limit=limit, market_type=attempt_market_type)

                if not df.empty:
                    successful_market_type = attempt_market_type
                    if attempt_market_type != market_type:
                        logger.info(f"✓ Fell back to {attempt_market_type} market for {symbol}")
                    else:
                        logger.info(f"✓ Successfully fetched {len(df)} candles for {symbol} as {attempt_market_type}")
                    break
                else:
                    errors_encountered.append(f"{attempt_market_type}_empty")
                    logger.warning(f"Empty data returned for {symbol} as {attempt_market_type}")

            except Exception as e:
                error_type = type(e).__name__
                errors_encountered.append(f"{attempt_market_type}_{error_type}")
                logger.warning(f"Failed to fetch {symbol} as {attempt_market_type}: {error_type}: {e}")
                continue

        # All attempts failed - return comprehensive error
        if df.empty:
            error_detail = {
                "message": f"Unable to fetch candle data for {symbol}",
                "symbol": symbol,
                "timeframe": timeframe.value,
                "exchange": exchange_key,
                "attempts": errors_encountered,
                "suggestion": (
                    "This symbol may not be available on this exchange, or the market type is incorrect. "
                    "Try: (1) Run a scanner to populate the cache, (2) Check if symbol exists on exchange, "
                    "(3) Try a different exchange or market type."
                ),
                "troubleshooting": {
                    "cache_checked": cache is not None,
                    "market_types_tried": [market_type, 'spot' if market_type == 'swap' else 'swap'],
                    "exchange": exchange_key
                }
            }
            logger.error(f"All fetch attempts failed for {symbol}: {errors_encountered}")
            raise HTTPException(status_code=404, detail=error_detail)

        # Success - convert DataFrame to response
        candles = []
        for _, row in df.iterrows():
            candles.append({
                'timestamp': row['timestamp'].to_pydatetime().isoformat(),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row['volume']),
            })

        return {
            "symbol": symbol,
            "timeframe": timeframe.value,
            "candles": candles,
            "source": "exchange",
            "market_type": successful_market_type
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error fetching candles for %s on %s: %s", symbol, exchange or 'phemex', e)
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Unexpected error fetching candle data",
                "error": str(e),
                "type": type(e).__name__
            }
        ) from e


# =============================================================================
# Cache Management Endpoints
# =============================================================================

@router.get("/api/cache/stats")
async def get_cache_stats():
    """
    Get OHLCV cache statistics.
    
    Returns cache hit rate, entry count, and memory usage estimates.
    Useful for monitoring cache effectiveness.
    """
    try:
        cache = get_ohlcv_cache()
        stats = cache.get_stats()
        return {
            "cache_type": "OHLCVCache",
            "stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error("Failed to get cache stats: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/cache/entries")
async def get_cache_entries():
    """
    Get detailed info about each cached entry and when it expires.
    
    Returns list of cached symbol/timeframe pairs with expiration times.
    """
    try:
        cache = get_ohlcv_cache()
        entries = cache.get_expiration_info()
        return {
            "entries": entries,
            "total": len(entries),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error("Failed to get cache entries: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/api/cache/clear")
async def clear_cache():
    """
    Clear all OHLCV cached data.
    
    Use this to force fresh data fetches on next scan.
    """
    try:
        cache = get_ohlcv_cache()
        stats_before = cache.get_stats()
        cache.clear()
        return {
            "status": "cleared",
            "entries_cleared": stats_before.get("entries", 0),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error("Failed to clear cache: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/api/cache/invalidate")
async def invalidate_symbol_cache(
    symbol: str,
    timeframe: Optional[str] = Query(default=None)
):
    """
    Invalidate cache for a specific symbol.
    
    Args:
        symbol: Symbol to invalidate (e.g., "BTC/USDT")
        timeframe: Optional specific timeframe to invalidate
        
    Use this after a significant price event to ensure fresh data.
    """
    try:
        cache = get_ohlcv_cache()
        invalidated = cache.invalidate(symbol, timeframe)
        return {
            "status": "invalidated",
            "symbol": symbol,
            "timeframe": timeframe or "all",
            "entries_invalidated": invalidated,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error("Failed to invalidate cache for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=str(e)) from e
