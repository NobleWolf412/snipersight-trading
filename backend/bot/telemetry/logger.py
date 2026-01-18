"""
Telemetry Logger

High-level interface for emitting telemetry events with in-memory caching
for fast access and automatic persistence to SQLite.
"""

from collections import deque
from typing import List, Optional, Dict, Any
import logging
from threading import Lock

from backend.bot.telemetry.events import TelemetryEvent, EventType
from backend.bot.telemetry.storage import TelemetryStorage, get_storage

logger = logging.getLogger(__name__)


class TelemetryLogger:
    """
    Telemetry event logger with in-memory cache and persistent storage.

    Thread-safe event logging with:
    - In-memory cache of last N events for instant API response
    - Automatic persistence to SQLite
    - Graceful fallback if storage fails

    Usage:
        telemetry = get_telemetry_logger()
        telemetry.log_event(scan_started_event)
        recent = telemetry.get_cached_events()
    """

    def __init__(self, storage: Optional[TelemetryStorage] = None, cache_size: int = 100):
        """
        Initialize telemetry logger.

        Args:
            storage: TelemetryStorage instance (uses global if None)
            cache_size: Number of recent events to keep in memory
        """
        self.storage = storage or get_storage()
        self.cache_size = cache_size
        self._cache: deque[Dict[str, Any]] = deque(maxlen=cache_size)
        self._lock = Lock()
        self._next_cache_id = 1

        logger.info(f"Telemetry logger initialized (cache_size={cache_size})")

    def log_event(self, event: TelemetryEvent) -> bool:
        """
        Log telemetry event.

        Persists to storage and adds to in-memory cache.
        Thread-safe: lock covers both database write and cache update.

        Args:
            event: TelemetryEvent to log

        Returns:
            True if successfully logged, False otherwise
        """
        # Acquire lock for entire operation to prevent race conditions
        # between concurrent database writes and cache updates
        with self._lock:
            try:
                # Store in database (now under lock)
                db_id = self.storage.store_event(event)

                # Add to in-memory cache with ID
                event_dict = event.to_dict()
                event_dict["id"] = db_id
                self._cache.append(event_dict)

                logger.debug(f"Logged event: {event.event_type.value} (id={db_id})")
                return True

            except Exception as e:
                logger.error(f"Failed to log telemetry event: {e}")
                # Still add to cache even if DB fails
                try:
                    event_dict = event.to_dict()
                    # Use local cache ID if DB failed
                    event_dict["id"] = self._next_cache_id
                    self._next_cache_id += 1
                    self._cache.append(event_dict)
                except Exception as cache_error:
                    logger.error(f"Failed to cache event: {cache_error}")
                return False

    def get_cached_events(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get recent events from in-memory cache.

        Args:
            limit: Maximum events to return (None = all cached)

        Returns:
            List of event dictionaries (newest first)
        """
        with self._lock:
            events = list(reversed(self._cache))  # Newest first
            if limit:
                events = events[:limit]
            return events

    def get_events(
        self,
        limit: int = 100,
        offset: int = 0,
        event_type: Optional[EventType] = None,
        symbol: Optional[str] = None,
        run_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query events from storage with filters.

        Args:
            limit: Maximum events to return
            offset: Pagination offset
            event_type: Filter by event type
            symbol: Filter by symbol
            run_id: Filter by run_id
            start_time: Filter events after this time (ISO format)
            end_time: Filter events before this time (ISO format)

        Returns:
            List of event dictionaries
        """
        from datetime import datetime

        # Convert ISO strings to datetime if provided
        start_dt = datetime.fromisoformat(start_time) if start_time else None
        end_dt = datetime.fromisoformat(end_time) if end_time else None

        events = self.storage.get_events(
            limit=limit,
            offset=offset,
            event_type=event_type,
            symbol=symbol,
            run_id=run_id,
            start_time=start_dt,
            end_time=end_dt,
        )

        return [event.to_dict() for event in events]

    def get_recent_with_id(
        self, limit: int = 100, since_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent events with ID for polling.

        If since_id provided, returns only events newer than that ID.
        Otherwise returns last N events.

        Args:
            limit: Maximum events to return
            since_id: Only return events with ID > this value

        Returns:
            List of event dictionaries with 'id' field
        """
        if since_id is None:
            # First poll - return from cache for instant response
            return self.get_cached_events(limit)
        else:
            # Subsequent polls - query from DB for new events
            return self.storage.get_recent_events(limit, since_id)

    def get_event_count(
        self,
        event_type: Optional[EventType] = None,
        symbol: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> int:
        """
        Count events matching filters.

        Args:
            event_type: Filter by event type
            symbol: Filter by symbol
            start_time: Count events after this time (ISO format)
            end_time: Count events before this time (ISO format)

        Returns:
            Event count
        """
        from datetime import datetime

        start_dt = datetime.fromisoformat(start_time) if start_time else None
        end_dt = datetime.fromisoformat(end_time) if end_time else None

        return self.storage.get_event_count(
            event_type=event_type, symbol=symbol, start_time=start_dt, end_time=end_dt
        )

    def cleanup_old_events(self, older_than_days: int = 30) -> int:
        """
        Delete events older than specified days.

        Args:
            older_than_days: Delete events older than this many days

        Returns:
            Number of events deleted
        """
        return self.storage.cleanup_old_events(older_than_days)


# Singleton instance
_logger_instance: Optional[TelemetryLogger] = None


def get_telemetry_logger() -> TelemetryLogger:
    """Get global telemetry logger instance."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = TelemetryLogger()
    return _logger_instance
