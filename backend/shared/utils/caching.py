"""
Cache manager for storing and retrieving data with TTL support.
Implements file-based caching with expiration logic.
"""

import os
import pickle
import time
from typing import Any, Optional
from pathlib import Path
from loguru import logger


class CacheManager:
    """
    File-based cache manager with TTL (time-to-live) support.
    Stores data as pickled files with expiration metadata.
    """

    def __init__(self, cache_dir: str = "./backend/cache"):
        """
        Initialize cache manager.

        Args:
            cache_dir: Directory path for storing cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Cache manager initialized at: {self.cache_dir.absolute()}")

    def _get_cache_path(self, key: str) -> Path:
        """
        Get file path for a cache key.

        Args:
            key: Cache key string

        Returns:
            Path object for cache file
        """
        # Sanitize key for filesystem
        safe_key = key.replace("/", "_").replace(":", "_").replace(" ", "_")
        return self.cache_dir / f"{safe_key}.cache"

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve value from cache if it exists and hasn't expired.

        Args:
            key: Cache key

        Returns:
            Cached value if valid, None if expired or doesn't exist
        """
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            logger.debug(f"Cache miss: {key}")
            return None

        try:
            with open(cache_path, 'rb') as f:
                cache_data = pickle.load(f)

            # Check expiration
            if 'expiry' in cache_data and cache_data['expiry'] < time.time():
                logger.debug(f"Cache expired: {key}")
                self.invalidate(key)
                return None

            logger.debug(f"Cache hit: {key}")
            return cache_data.get('value')

        except (pickle.PickleError, EOFError, KeyError) as e:
            logger.warning(f"Error reading cache for {key}: {e}")
            self.invalidate(key)
            return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """
        Store value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache (must be picklable)
            ttl: Time-to-live in seconds (default: 1 hour)
        """
        cache_path = self._get_cache_path(key)

        cache_data = {
            'value': value,
            'expiry': time.time() + ttl,
            'created': time.time()
        }

        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(cache_data, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            logger.debug(f"Cached {key} with TTL={ttl}s")

        except pickle.PickleError as e:
            logger.error(f"Error caching {key}: {e}")

    def invalidate(self, key: str) -> None:
        """
        Remove a specific cache entry.

        Args:
            key: Cache key to invalidate
        """
        cache_path = self._get_cache_path(key)

        if cache_path.exists():
            try:
                cache_path.unlink()
                logger.debug(f"Invalidated cache: {key}")
            except OSError as e:
                logger.warning(f"Error deleting cache file {key}: {e}")
        else:
            logger.debug(f"Cache key not found for invalidation: {key}")

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Remove all cache entries matching a pattern.

        Args:
            pattern: String pattern to match (uses simple string contains)

        Returns:
            Number of cache entries invalidated
        """
        count = 0
        
        for cache_file in self.cache_dir.glob("*.cache"):
            if pattern in cache_file.stem:
                try:
                    cache_file.unlink()
                    count += 1
                except OSError as e:
                    logger.warning(f"Error deleting {cache_file}: {e}")

        logger.info(f"Invalidated {count} cache entries matching '{pattern}'")
        return count

    def clear_all(self) -> int:
        """
        Remove all cache entries.

        Returns:
            Number of cache entries cleared
        """
        count = 0
        
        for cache_file in self.cache_dir.glob("*.cache"):
            try:
                cache_file.unlink()
                count += 1
            except OSError as e:
                logger.warning(f"Error deleting {cache_file}: {e}")

        logger.info(f"Cleared {count} cache entries")
        return count

    def cleanup_expired(self) -> int:
        """
        Remove all expired cache entries.

        Returns:
            Number of expired entries removed
        """
        count = 0
        current_time = time.time()

        for cache_file in self.cache_dir.glob("*.cache"):
            try:
                with open(cache_file, 'rb') as f:
                    cache_data = pickle.load(f)

                if 'expiry' in cache_data and cache_data['expiry'] < current_time:
                    cache_file.unlink()
                    count += 1

            except (pickle.PickleError, EOFError, OSError) as e:
                logger.warning(f"Error processing {cache_file} during cleanup: {e}")

        logger.info(f"Cleaned up {count} expired cache entries")
        return count

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats (total entries, size, etc.)
        """
        total_entries = 0
        total_size = 0
        expired_entries = 0
        current_time = time.time()

        for cache_file in self.cache_dir.glob("*.cache"):
            total_entries += 1
            total_size += cache_file.stat().st_size

            try:
                with open(cache_file, 'rb') as f:
                    cache_data = pickle.load(f)

                if 'expiry' in cache_data and cache_data['expiry'] < current_time:
                    expired_entries += 1

            except (pickle.PickleError, EOFError, OSError):
                pass

        return {
            'total_entries': total_entries,
            'expired_entries': expired_entries,
            'valid_entries': total_entries - expired_entries,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'cache_dir': str(self.cache_dir.absolute())
        }
