"""
Unified Cache Manager

Consolidates all caching functionality into a single, consistent interface:
- Price cache (TTL: 5s) - for real-time price data
- OHLCV cache (TTL: timeframe-aware) - for candlestick data
- Regime cache (TTL: 60s) - for market regime data
- Cycles cache (TTL: 300s) - for cycle timing data

Features:
- Thread-safe with per-namespace locks
- LRU eviction when capacity exceeded
- Configurable TTL per cache type
- Stats tracking (hits, misses, evictions)
- Unified interface for all cache operations
"""

import time
import threading
from typing import Dict, Any, Optional, List
from collections import OrderedDict
from dataclasses import dataclass
import logging

import pandas as pd

logger = logging.getLogger(__name__)


# Timeframe to seconds mapping (for OHLCV expiration)
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
    "1M": 2592000,
}


@dataclass
class CacheStats:
    """Cache statistics for monitoring."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    current_entries: int = 0
    max_entries: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "current_entries": self.current_entries,
            "max_entries": self.max_entries,
            "hit_rate_pct": round(self.hit_rate, 2),
        }


class CacheNamespace:
    """
    A single cache namespace with TTL and LRU eviction.

    This is the core building block - each cache type (price, regime, etc.)
    gets its own namespace with independent settings.
    """

    def __init__(self, name: str, max_entries: int = 1000, default_ttl: int = 60):
        self.name = name
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._max_entries = max_entries
        self._default_ttl = default_ttl
        self._stats = CacheStats(max_entries=max_entries)

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache, returns None if expired or missing."""
        with self._lock:
            if key not in self._cache:
                self._stats.misses += 1
                return None

            entry = self._cache[key]
            ttl = entry.get("_ttl", self._default_ttl)

            if time.time() - entry.get("_cached_at", 0) > ttl:
                # Expired
                del self._cache[key]
                self._stats.current_entries = len(self._cache)
                self._stats.misses += 1
                return None

            # Move to end (LRU)
            self._cache.move_to_end(key)
            self._stats.hits += 1
            return entry.get("_value")

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with optional custom TTL."""
        with self._lock:
            self._cache[key] = {
                "_value": value,
                "_cached_at": time.time(),
                "_ttl": ttl if ttl is not None else self._default_ttl,
            }
            self._cache.move_to_end(key)

            # Evict oldest if over capacity
            while len(self._cache) > self._max_entries:
                self._cache.popitem(last=False)
                self._stats.evictions += 1

            self._stats.current_entries = len(self._cache)

    def delete(self, key: str) -> bool:
        """Delete a specific key. Returns True if key existed."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._stats.current_entries = len(self._cache)
                return True
            return False

    def clear(self) -> int:
        """Clear all entries. Returns count of entries cleared."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._stats.current_entries = 0
            return count

    def get_stats(self) -> CacheStats:
        """Get current cache statistics."""
        with self._lock:
            self._stats.current_entries = len(self._cache)
            return CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                evictions=self._stats.evictions,
                current_entries=self._stats.current_entries,
                max_entries=self._stats.max_entries,
            )

    def get_entries_info(self) -> List[Dict[str, Any]]:
        """Get info about all cached entries (for debugging)."""
        with self._lock:
            entries = []
            now = time.time()
            for key, entry in self._cache.items():
                ttl = entry.get("_ttl", self._default_ttl)
                cached_at = entry.get("_cached_at", 0)
                age = now - cached_at
                entries.append(
                    {
                        "key": key,
                        "age_seconds": round(age, 1),
                        "ttl_seconds": ttl,
                        "expires_in_seconds": round(max(0, ttl - age), 1),
                        "expired": age > ttl,
                    }
                )
            return entries


class CacheManager:
    """
    Unified cache manager with typed accessors for different cache domains.

    Usage:
        cache = get_cache_manager()  # Singleton

        # Price cache
        cache.set_price("phemex:BTC/USDT", {"price": 90000, "timestamp": "..."})
        price_data = cache.get_price("phemex:BTC/USDT")

        # Regime cache
        cache.set_regime("global", {"composite": "bullish", "score": 75})
        regime = cache.get_regime("global")

        # Stats
        stats = cache.get_all_stats()
    """

    def __init__(self):
        # Initialize namespaces with appropriate settings
        self._namespaces: Dict[str, CacheNamespace] = {
            "price": CacheNamespace("price", max_entries=1000, default_ttl=5),
            "regime": CacheNamespace("regime", max_entries=50, default_ttl=60),
            "cycles": CacheNamespace("cycles", max_entries=100, default_ttl=300),
            "ohlcv": CacheNamespace("ohlcv", max_entries=500, default_ttl=300),
            "generic": CacheNamespace("generic", max_entries=500, default_ttl=60),
        }
        logger.info("CacheManager initialized with namespaces: %s", list(self._namespaces.keys()))

    # =========================================================================
    # Price Cache (TTL: 5s)
    # =========================================================================

    def get_price(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached price data."""
        return self._namespaces["price"].get(key)

    def set_price(self, key: str, data: Dict[str, Any]) -> None:
        """Cache price data (5s TTL)."""
        self._namespaces["price"].set(key, data)

    # =========================================================================
    # Regime Cache (TTL: 60s)
    # =========================================================================

    def get_regime(self, key: str = "global") -> Optional[Dict[str, Any]]:
        """Get cached regime data."""
        return self._namespaces["regime"].get(key)

    def set_regime(self, key: str, data: Dict[str, Any], ttl: int = 60) -> None:
        """Cache regime data (default 60s TTL)."""
        self._namespaces["regime"].set(key, data, ttl=ttl)

    # =========================================================================
    # Cycles Cache (TTL: 300s)
    # =========================================================================

    def get_cycles(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached cycle data."""
        return self._namespaces["cycles"].get(key)

    def set_cycles(self, key: str, data: Dict[str, Any], ttl: int = 300) -> None:
        """Cache cycle data (default 5min TTL)."""
        self._namespaces["cycles"].set(key, data, ttl=ttl)

    # =========================================================================
    # OHLCV Cache (Timeframe-aware TTL)
    # =========================================================================

    def get_ohlcv(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Get cached OHLCV DataFrame."""
        key = f"{symbol}:{timeframe}"
        return self._namespaces["ohlcv"].get(key)

    def set_ohlcv(self, symbol: str, timeframe: str, df: pd.DataFrame) -> None:
        """Cache OHLCV DataFrame with timeframe-aware TTL."""
        key = f"{symbol}:{timeframe}"
        # TTL based on timeframe duration + small buffer
        ttl = TIMEFRAME_SECONDS.get(timeframe, 300) + 5
        self._namespaces["ohlcv"].set(key, df, ttl=ttl)

    def invalidate_ohlcv(self, symbol: str, timeframe: Optional[str] = None) -> int:
        """Invalidate OHLCV cache for a symbol (optionally specific timeframe)."""
        ns = self._namespaces["ohlcv"]
        if timeframe:
            key = f"{symbol}:{timeframe}"
            return 1 if ns.delete(key) else 0
        else:
            # Invalidate all timeframes for this symbol
            count = 0
            with ns._lock:
                keys_to_delete = [k for k in ns._cache.keys() if k.startswith(f"{symbol}:")]
            for key in keys_to_delete:
                if ns.delete(key):
                    count += 1
            return count

    # =========================================================================
    # Generic Cache
    # =========================================================================

    def get(self, namespace: str, key: str) -> Optional[Any]:
        """Get from any namespace."""
        ns = self._namespaces.get(namespace, self._namespaces["generic"])
        return ns.get(key)

    def set(self, namespace: str, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set in any namespace."""
        ns = self._namespaces.get(namespace, self._namespaces["generic"])
        ns.set(key, value, ttl=ttl)

    # =========================================================================
    # Management
    # =========================================================================

    def clear_namespace(self, namespace: str) -> int:
        """Clear all entries in a namespace."""
        ns = self._namespaces.get(namespace)
        if ns:
            return ns.clear()
        return 0

    def clear_all(self) -> Dict[str, int]:
        """Clear all caches. Returns count by namespace."""
        result = {}
        for name, ns in self._namespaces.items():
            result[name] = ns.clear()
        return result

    def get_stats(self, namespace: str) -> Optional[Dict[str, Any]]:
        """Get stats for a specific namespace."""
        ns = self._namespaces.get(namespace)
        if ns:
            return ns.get_stats().to_dict()
        return None

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get stats for all namespaces."""
        return {name: ns.get_stats().to_dict() for name, ns in self._namespaces.items()}

    def get_entries_info(self, namespace: str) -> List[Dict[str, Any]]:
        """Get info about entries in a namespace."""
        ns = self._namespaces.get(namespace)
        if ns:
            return ns.get_entries_info()
        return []


# Singleton instance
_cache_manager: Optional[CacheManager] = None
_cache_lock = threading.Lock()


def get_cache_manager() -> CacheManager:
    """Get or create the singleton CacheManager instance."""
    global _cache_manager
    if _cache_manager is None:
        with _cache_lock:
            if _cache_manager is None:
                _cache_manager = CacheManager()
    return _cache_manager
