"""
Shared retry logic for exchange adapters.

Provides a decorator for handling rate limits and network errors
with exponential backoff and jitter to prevent thundering herd.
"""

import time
import random
from functools import wraps
from typing import Callable, TypeVar, Any
import ccxt
from loguru import logger


# Default configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF = 1.0
DEFAULT_JITTER_PCT = 0.25  # 25% random jitter


F = TypeVar('F', bound=Callable[..., Any])


def retry_on_rate_limit(
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
    jitter_pct: float = DEFAULT_JITTER_PCT
) -> Callable[[F], F]:
    """
    Decorator to retry function calls on rate limit and network errors.
    
    Uses exponential backoff with jitter to prevent thundering herd
    when multiple concurrent requests hit rate limits simultaneously.

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        backoff: Initial backoff time in seconds, doubles each retry (default: 1.0)
        jitter_pct: Random jitter percentage (0-1) to add to backoff (default: 0.25)
    
    Returns:
        Decorated function with retry logic
    
    Example:
        @retry_on_rate_limit(max_retries=5, backoff=2.0, jitter_pct=0.3)
        def fetch_data():
            ...
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
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
                    
                    # Add jitter to prevent thundering herd
                    jitter = current_backoff * jitter_pct * random.random()
                    sleep_time = current_backoff + jitter
                    
                    logger.warning(
                        f"Rate limit hit, retrying in {sleep_time:.2f}s "
                        f"(attempt {retries}/{max_retries})"
                    )
                    time.sleep(sleep_time)
                    current_backoff *= 2
                    
                except ccxt.NetworkError as e:
                    retries += 1
                    if retries >= max_retries:
                        logger.error(f"Network error after {max_retries} retries: {e}")
                        raise
                    
                    # Add jitter for network errors too
                    jitter = current_backoff * jitter_pct * random.random()
                    sleep_time = current_backoff + jitter
                    
                    logger.warning(f"Network error, retrying in {sleep_time:.2f}s: {e}")
                    time.sleep(sleep_time)
                    current_backoff *= 2
            
            # Final attempt without catching
            return func(*args, **kwargs)
        
        return wrapper  # type: ignore
    return decorator


# Backward compatibility alias
_retry_on_rate_limit = retry_on_rate_limit


# ---------------------------------------------------------------------------
# Optional caching layer for expensive ticker fetches
# ---------------------------------------------------------------------------

from threading import Lock
from dataclasses import dataclass, field
from typing import Dict, Optional
import time as time_module


@dataclass
class CachedTickers:
    """
    Simple TTL cache for exchange tickers to reduce API calls.
    
    Usage:
        cache = CachedTickers(ttl_seconds=300)  # 5 minute cache
        
        tickers = cache.get("phemex")
        if tickers is None:
            tickers = exchange.fetch_tickers()
            cache.set("phemex", tickers)
    """
    ttl_seconds: float = 300.0  # 5 minutes default
    _cache: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _timestamps: Dict[str, float] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)
    
    def get(self, exchange_id: str) -> Optional[Dict[str, Any]]:
        """Get cached tickers if not expired."""
        with self._lock:
            if exchange_id not in self._cache:
                return None
            
            cached_time = self._timestamps.get(exchange_id, 0)
            if time_module.time() - cached_time > self.ttl_seconds:
                # Expired - remove from cache
                del self._cache[exchange_id]
                del self._timestamps[exchange_id]
                return None
            
            return self._cache[exchange_id]
    
    def set(self, exchange_id: str, tickers: Dict[str, Any]) -> None:
        """Store tickers in cache with current timestamp."""
        with self._lock:
            self._cache[exchange_id] = tickers
            self._timestamps[exchange_id] = time_module.time()
    
    def invalidate(self, exchange_id: Optional[str] = None) -> None:
        """Clear cache for specific exchange or all exchanges."""
        with self._lock:
            if exchange_id:
                self._cache.pop(exchange_id, None)
                self._timestamps.pop(exchange_id, None)
            else:
                self._cache.clear()
                self._timestamps.clear()


# Global shared cache instance (optional - adapters can use their own)
ticker_cache = CachedTickers(ttl_seconds=300)
