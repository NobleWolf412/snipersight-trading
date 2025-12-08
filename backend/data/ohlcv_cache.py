"""
Smart OHLCV Cache

Caches historical candle data intelligently:
- Closed candles are permanent and can be cached indefinitely
- Only the most recent candles (forming/just-closed) are refreshed
- Cache expiration is based on timeframe duration

This dramatically reduces API calls to exchanges while maintaining
data accuracy for signal generation.
"""

import time
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
import pandas as pd

logger = logging.getLogger(__name__)


# Timeframe to seconds mapping
TIMEFRAME_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "8h": 28800,
    "12h": 43200,
    "1d": 86400,
    "3d": 259200,
    "1w": 604800,
    "1M": 2592000,  # Approximate
}


@dataclass
class CacheEntry:
    """Single cache entry for symbol+timeframe data."""
    df: pd.DataFrame
    fetched_at: float  # Unix timestamp when data was fetched
    timeframe: str
    symbol: str
    
    def is_expired(self, buffer_seconds: float = 5.0) -> bool:
        """
        Check if the cache entry is stale.
        
        A cache entry expires when the current candle's period ends.
        We add a small buffer to account for exchange data lag.
        
        Args:
            buffer_seconds: Extra seconds to wait after candle close
            
        Returns:
            True if cache should be refreshed
        """
        if self.df.empty:
            return True
            
        tf_seconds = TIMEFRAME_SECONDS.get(self.timeframe, 300)  # Default 5m
        
        # Calculate when the current candle closes
        now = time.time()
        time_since_fetch = now - self.fetched_at
        
        # If we've passed the timeframe duration since fetch, the candle has closed
        # and a new one has started - we need fresh data
        if time_since_fetch >= tf_seconds + buffer_seconds:
            return True
            
        return False
    
    def get_age_seconds(self) -> float:
        """Get how old this cache entry is in seconds."""
        return time.time() - self.fetched_at
    
    def get_remaining_seconds(self) -> float:
        """Get seconds until this cache expires."""
        tf_seconds = TIMEFRAME_SECONDS.get(self.timeframe, 300)
        remaining = tf_seconds - self.get_age_seconds()
        return max(0, remaining)


class OHLCVCache:
    """
    Thread-safe OHLCV data cache with smart expiration.
    
    Usage:
        cache = OHLCVCache()
        
        # Check if we have valid cached data
        cached_df = cache.get("BTC/USDT", "1h")
        if cached_df is not None:
            return cached_df
        
        # Fetch from exchange and cache
        df = adapter.fetch_ohlcv(symbol, timeframe)
        cache.set("BTC/USDT", "1h", df)
    """
    
    def __init__(self, max_entries: int = 500):
        """
        Initialize the cache.
        
        Args:
            max_entries: Maximum number of symbol+timeframe entries to cache
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = Lock()
        self._max_entries = max_entries
        self._hits = 0
        self._misses = 0
        
        logger.info(f"OHLCVCache initialized (max_entries={max_entries})")
    
    def _make_key(self, symbol: str, timeframe: str) -> str:
        """Create cache key from symbol and timeframe."""
        return f"{symbol}:{timeframe}"
    
    def get(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Get cached OHLCV data if available and not expired.
        
        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe (e.g., "1h")
            
        Returns:
            Cached DataFrame or None if cache miss/expired
        """
        key = self._make_key(symbol, timeframe)
        
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._misses += 1
                return None
            
            if entry.is_expired():
                # Remove expired entry
                del self._cache[key]
                self._misses += 1
                logger.debug(f"Cache EXPIRED: {key} (age={entry.get_age_seconds():.1f}s)")
                return None
            
            self._hits += 1
            logger.debug(f"Cache HIT: {key} (age={entry.get_age_seconds():.1f}s, remaining={entry.get_remaining_seconds():.1f}s)")
            return entry.df.copy()  # Return copy to prevent mutation
    
    def set(self, symbol: str, timeframe: str, df: pd.DataFrame) -> None:
        """
        Cache OHLCV data.
        
        Args:
            symbol: Trading pair
            timeframe: Candle timeframe
            df: OHLCV DataFrame to cache
        """
        if df is None or df.empty:
            return
            
        key = self._make_key(symbol, timeframe)
        entry = CacheEntry(
            df=df.copy(),  # Store copy
            fetched_at=time.time(),
            timeframe=timeframe,
            symbol=symbol
        )
        
        with self._lock:
            # Evict oldest entries if at capacity
            if len(self._cache) >= self._max_entries and key not in self._cache:
                self._evict_oldest()
            
            self._cache[key] = entry
            logger.debug(f"Cache SET: {key} ({len(df)} candles)")
    
    def _evict_oldest(self) -> None:
        """Evict the oldest cache entries to make room."""
        if not self._cache:
            return
            
        # Sort by fetched_at and remove oldest 10%
        entries = sorted(
            self._cache.items(),
            key=lambda x: x[1].fetched_at
        )
        
        evict_count = max(1, len(entries) // 10)
        for key, _ in entries[:evict_count]:
            del self._cache[key]
            
        logger.debug(f"Evicted {evict_count} oldest cache entries")
    
    def invalidate(self, symbol: str, timeframe: Optional[str] = None) -> int:
        """
        Invalidate cache entries for a symbol.
        
        Args:
            symbol: Trading pair to invalidate
            timeframe: Specific timeframe (None = all timeframes)
            
        Returns:
            Number of entries invalidated
        """
        with self._lock:
            if timeframe:
                key = self._make_key(symbol, timeframe)
                if key in self._cache:
                    del self._cache[key]
                    return 1
                return 0
            else:
                # Invalidate all timeframes for symbol
                keys_to_remove = [k for k in self._cache if k.startswith(f"{symbol}:")]
                for key in keys_to_remove:
                    del self._cache[key]
                return len(keys_to_remove)
    
    def clear(self) -> None:
        """Clear all cached data."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            logger.info(f"Cache cleared ({count} entries)")
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
            
            # Calculate memory usage estimate
            total_rows = sum(len(e.df) for e in self._cache.values())
            
            return {
                "entries": len(self._cache),
                "max_entries": self._max_entries,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_pct": round(hit_rate, 1),
                "total_candles_cached": total_rows,
                "symbols_cached": len(set(e.symbol for e in self._cache.values())),
                "timeframes_cached": len(set(e.timeframe for e in self._cache.values())),
            }
    
    def get_expiration_info(self) -> List[Dict]:
        """Get info about when each cached entry expires."""
        with self._lock:
            info = []
            for key, entry in self._cache.items():
                info.append({
                    "key": key,
                    "symbol": entry.symbol,
                    "timeframe": entry.timeframe,
                    "age_seconds": round(entry.get_age_seconds(), 1),
                    "remaining_seconds": round(entry.get_remaining_seconds(), 1),
                    "expired": entry.is_expired(),
                    "candles": len(entry.df)
                })
            return sorted(info, key=lambda x: x["remaining_seconds"])


# Global cache instance (singleton pattern)
_global_cache: Optional[OHLCVCache] = None
_cache_lock = Lock()


def get_ohlcv_cache() -> OHLCVCache:
    """
    Get the global OHLCV cache instance.
    
    Returns:
        OHLCVCache singleton instance
    """
    global _global_cache
    
    with _cache_lock:
        if _global_cache is None:
            _global_cache = OHLCVCache(max_entries=500)
        return _global_cache


def reset_ohlcv_cache() -> None:
    """Reset the global cache (useful for testing)."""
    global _global_cache
    
    with _cache_lock:
        if _global_cache is not None:
            _global_cache.clear()
            _global_cache = None
