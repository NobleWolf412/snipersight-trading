"""
Telemetry Storage Layer

SQLite-based persistence for telemetry events with efficient querying
and automatic schema management.
"""

import sqlite3
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
import logging

from backend.bot.telemetry.events import TelemetryEvent, EventType

logger = logging.getLogger(__name__)


class TelemetryStorage:
    """
    SQLite storage for telemetry events.

    Provides persistent storage with efficient querying by time range,
    event type, symbol, and run_id.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize storage.

        Args:
            db_path: Path to SQLite database file. If None, uses default location.
        """
        if db_path is None:
            # Default to backend/cache/telemetry.db
            cache_dir = Path(__file__).parent.parent.parent / "cache"
            cache_dir.mkdir(exist_ok=True)
            db_path = str(cache_dir / "telemetry.db")

        self.db_path = db_path
        self._init_db()
        logger.info(f"Telemetry storage initialized: {self.db_path}")

    def _init_db(self):
        """Create database schema if it doesn't exist."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telemetry_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    run_id TEXT,
                    symbol TEXT,
                    data_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indices for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_event_type 
                ON telemetry_events(event_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON telemetry_events(timestamp DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol 
                ON telemetry_events(symbol)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_run_id 
                ON telemetry_events(run_id)
            """)

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
        finally:
            conn.close()

    def store_event(self, event: TelemetryEvent) -> int:
        """
        Store telemetry event.

        Args:
            event: TelemetryEvent to store

        Returns:
            Event ID in database
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO telemetry_events 
                (event_type, timestamp, run_id, symbol, data_json)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    event.event_type.value,
                    event.timestamp.isoformat(),
                    event.run_id,
                    event.symbol,
                    json.dumps(event.data) if event.data else None,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_events(
        self,
        limit: int = 100,
        offset: int = 0,
        event_type: Optional[EventType] = None,
        symbol: Optional[str] = None,
        run_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        since_id: Optional[int] = None,
    ) -> List[TelemetryEvent]:
        """
        Query telemetry events with filters.

        Args:
            limit: Maximum events to return
            offset: Pagination offset
            event_type: Filter by event type
            symbol: Filter by symbol
            run_id: Filter by run_id
            start_time: Filter events after this time
            end_time: Filter events before this time
            since_id: Get events with ID > this value (for polling)

        Returns:
            List of TelemetryEvent objects
        """
        query = "SELECT * FROM telemetry_events WHERE 1=1"
        params = []

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type.value)

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        if run_id:
            query += " AND run_id = ?"
            params.append(run_id)

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat())

        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time.isoformat())

        if since_id is not None:
            query += " AND id > ?"
            params.append(since_id)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        return [self._row_to_event(row) for row in rows]

    def get_recent_events(
        self, limit: int = 100, since_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent events with ID for polling.

        Returns events as dicts with 'id' field included for client tracking.

        Args:
            limit: Maximum events to return
            since_id: Only return events with ID > this value

        Returns:
            List of event dictionaries with 'id' field
        """
        query = "SELECT * FROM telemetry_events"
        params = []

        if since_id is not None:
            query += " WHERE id > ?"
            params.append(since_id)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        events = []
        for row in rows:
            event = self._row_to_event(row)
            event_dict = event.to_dict()
            event_dict["id"] = row["id"]  # Include DB ID for polling
            events.append(event_dict)

        return events

    def get_event_count(
        self,
        event_type: Optional[EventType] = None,
        symbol: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """
        Count events matching filters.

        Args:
            event_type: Filter by event type
            symbol: Filter by symbol
            start_time: Count events after this time
            end_time: Count events before this time

        Returns:
            Event count
        """
        query = "SELECT COUNT(*) as count FROM telemetry_events WHERE 1=1"
        params = []

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type.value)

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat())

        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time.isoformat())

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchone()["count"]

    def cleanup_old_events(self, older_than_days: int = 30) -> int:
        """
        Delete events older than specified days.

        Args:
            older_than_days: Delete events older than this many days

        Returns:
            Number of events deleted
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=older_than_days)

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM telemetry_events 
                WHERE timestamp < ?
            """,
                (cutoff_time.isoformat(),),
            )
            conn.commit()
            deleted = cursor.rowcount

        logger.info(f"Cleaned up {deleted} events older than {older_than_days} days")
        return deleted

    def _row_to_event(self, row: sqlite3.Row) -> TelemetryEvent:
        """Convert database row to TelemetryEvent."""
        data = json.loads(row["data_json"]) if row["data_json"] else {}

        return TelemetryEvent(
            event_type=EventType(row["event_type"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            run_id=row["run_id"],
            symbol=row["symbol"],
            data=data,
        )


# Singleton instance
_storage_instance: Optional[TelemetryStorage] = None


def get_storage() -> TelemetryStorage:
    """Get global telemetry storage instance."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = TelemetryStorage()
    return _storage_instance
