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
from typing import Dict, List, Optional
from dataclasses import dataclass
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

        A cache entry expires the moment the candle AFTER the latest one in
        the cached df has closed — i.e., when fetching now would return a
        df with a newer "latest closed candle" than the one cached.

        Anchored to the wall-clock candle boundary (using the latest
        candle's open timestamp in the cached df), NOT to elapsed-since-
        fetch. The previous implementation used `now - fetched_at >=
        tf_seconds`, which produced up to ~59 minutes of staleness when a
        candle closed mid-cache-window. That caused production Gate 3
        false-positives in dda4d192 (May 2026) — 84 LONG rejections
        attributed to a stale `btc_velocity_1h` reading.

        Args:
            buffer_seconds: Extra seconds to wait after the new candle's
                close to account for exchange data finalization lag.

        Returns:
            True if cache should be refreshed
        """
        if self.df.empty:
            return True

        tf_seconds = TIMEFRAME_SECONDS.get(self.timeframe, 300)  # Default 5m

        # Read the latest candle's OPEN timestamp from the cached df.
        # The candle CLOSED at latest_open + tf_seconds. The NEXT candle
        # closes at latest_open + 2 * tf_seconds — that is when the cache
        # is unambiguously stale (a fresh fetch would return a newer
        # latest-closed candle). We expire when wall-clock crosses
        # `latest_open + tf_seconds + buffer`, i.e. as soon as the next
        # candle has just closed (the +tf_seconds covers the candle that's
        # CURRENTLY in-progress at fetch time, which has now closed too).
        try:
            latest_open = self.df["timestamp"].iloc[-1]
            ts = pd.Timestamp(latest_open)
            if ts.tz is None:
                # Exchange convention: candle timestamps are UTC even when naive.
                ts = ts.tz_localize("UTC")
            latest_open_epoch = ts.timestamp()
        except Exception as exc:
            # Defensive fallback: if the timestamp column is malformed,
            # use the legacy elapsed-since-fetch formula so we never wedge.
            # WARNING-level + structured telemetry so silent regression to
            # the pre-fix broken behavior is loud (per §11 + §15: silent
            # fallback to known-broken semantics is worse than a halt).
            logger.warning(
                "OHLCVCache.is_expired: timestamp parse failed for %s %s (%s); "
                "falling back to elapsed-since-fetch TTL — silent regression to "
                "pre-fix broken behavior, investigate immediately",
                self.symbol, self.timeframe, exc,
            )
            try:
                from datetime import datetime, timezone as _tz
                from backend.bot.telemetry.events import EventType, TelemetryEvent
                from backend.bot.telemetry.logger import get_telemetry_logger
                get_telemetry_logger().log_event(
                    TelemetryEvent(
                        event_type=EventType.WARNING_ISSUED,
                        timestamp=datetime.now(_tz.utc),
                        symbol=self.symbol,
                        data={
                            "kind": "ohlcv_cache_ttl_fallback_to_elapsed",
                            "timeframe": self.timeframe,
                            "error": str(exc),
                        },
                    )
                )
            except Exception:
                pass  # never block ingestion on telemetry failure
            return (time.time() - self.fetched_at) >= tf_seconds + buffer_seconds

        # Latest cached candle opened at `latest_open_epoch` and closed at
        # `latest_open_epoch + tf_seconds`. Cache becomes stale the moment
        # the FOLLOWING candle has closed (= latest_open + 2 * tf_seconds).
        next_after_close_epoch = latest_open_epoch + 2 * tf_seconds
        return time.time() >= next_after_close_epoch + buffer_seconds

    def is_stale_by_price(self, current_price: float, max_drift_pct: float = 3.0) -> bool:
        """
        Check if cache is stale due to significant price movement.

        Even if time hasn't expired, large price moves can invalidate
        SMC structures detected from cached data.

        Args:
            current_price: Current live market price
            max_drift_pct: Maximum allowed price drift percentage

        Returns:
            True if price has drifted too far from cached close
        """
        if self.df.empty or current_price <= 0:
            return True

        cached_close = self.df["close"].iloc[-1]
        if cached_close <= 0:
            return True

        drift_pct = abs(current_price - cached_close) / cached_close * 100
        return drift_pct > max_drift_pct

    def get_age_seconds(self) -> float:
        """Get how old this cache entry is in seconds."""
        return time.time() - self.fetched_at

    def get_remaining_seconds(self) -> float:
        """Get seconds until this cache expires.

        Mirrors `is_expired()` math so the `/api/cache/*` observability
        endpoints don't drift from actual expiration semantics. Uses the
        latest candle's open timestamp + 2*tf_seconds + 5s buffer, same
        as `is_expired()`. Falls back to the legacy elapsed-since-fetch
        formula on timestamp parse failure (matching the fallback in
        `is_expired()`).
        """
        if self.df.empty:
            return 0.0
        tf_seconds = TIMEFRAME_SECONDS.get(self.timeframe, 300)
        try:
            latest_open = self.df["timestamp"].iloc[-1]
            ts = pd.Timestamp(latest_open)
            if ts.tz is None:
                ts = ts.tz_localize("UTC")
            latest_open_epoch = ts.timestamp()
            next_after_close_epoch = latest_open_epoch + 2 * tf_seconds + 5.0
            remaining = next_after_close_epoch - time.time()
            return max(0.0, remaining)
        except Exception as exc:
            # See is_expired() for the WARNING-vs-DEBUG rationale.
            logger.warning(
                "OHLCVCache.get_remaining_seconds: timestamp parse failed for "
                "%s %s (%s); falling back to elapsed-since-fetch TTL",
                self.symbol, self.timeframe, exc,
            )
            try:
                from datetime import datetime, timezone as _tz
                from backend.bot.telemetry.events import EventType, TelemetryEvent
                from backend.bot.telemetry.logger import get_telemetry_logger
                get_telemetry_logger().log_event(
                    TelemetryEvent(
                        event_type=EventType.WARNING_ISSUED,
                        timestamp=datetime.now(_tz.utc),
                        symbol=self.symbol,
                        data={
                            "kind": "ohlcv_cache_ttl_fallback_to_elapsed",
                            "timeframe": self.timeframe,
                            "source": "get_remaining_seconds",
                            "error": str(exc),
                        },
                    )
                )
            except Exception:
                pass
            remaining = tf_seconds - self.get_age_seconds()
            return max(0.0, remaining)


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

    def get(
        self,
        symbol: str,
        timeframe: str,
        current_price: Optional[float] = None,
        max_price_drift_pct: float = 3.0,
    ) -> Optional[pd.DataFrame]:
        """
        Get cached OHLCV data if available and not expired.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe (e.g., "1h")
            current_price: Optional current price for drift check
            max_price_drift_pct: Max allowed price drift before cache is stale

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
                logger.debug(f"Cache EXPIRED (time): {key} (age={entry.get_age_seconds():.1f}s)")
                return None

            # NEW: Check price drift if current_price provided
            if current_price is not None and entry.is_stale_by_price(
                current_price, max_price_drift_pct
            ):
                del self._cache[key]
                self._misses += 1
                cached_close = entry.df["close"].iloc[-1] if not entry.df.empty else 0
                drift = (
                    abs(current_price - cached_close) / cached_close * 100
                    if cached_close > 0
                    else 0
                )
                logger.debug(
                    f"Cache EXPIRED (price drift): {key} (drift={drift:.1f}% > {max_price_drift_pct}%)"
                )
                return None

            self._hits += 1
            logger.debug(
                f"Cache HIT: {key} (age={entry.get_age_seconds():.1f}s, remaining={entry.get_remaining_seconds():.1f}s)"
            )
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
            df=df.copy(), fetched_at=time.time(), timeframe=timeframe, symbol=symbol  # Store copy
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
        entries = sorted(self._cache.items(), key=lambda x: x[1].fetched_at)

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
                info.append(
                    {
                        "key": key,
                        "symbol": entry.symbol,
                        "timeframe": entry.timeframe,
                        "age_seconds": round(entry.get_age_seconds(), 1),
                        "remaining_seconds": round(entry.get_remaining_seconds(), 1),
                        "expired": entry.is_expired(),
                        "candles": len(entry.df),
                    }
                )
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
