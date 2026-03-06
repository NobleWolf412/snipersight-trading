"""
Cooldown Manager

Handles persistent storage of trade cooldowns (lockouts after stop-outs).
Ensures that risk management state survives backend restarts.
"""

import json
import os
import threading
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class CooldownManager:
    """
    Manages trade cooldowns with JSON persistence.

    A cooldown prevents re-entry into a symbol/direction for a set duration
    (typically 24h) after a stop-loss event.
    """

    def __init__(self, storage_path: str = "data/cooldowns.json"):
        """
        Initialize manager.

        Args:
            storage_path: Path to JSON storage file
        """
        self.storage_path = storage_path
        self._lock = threading.Lock()
        self._cooldowns: Dict[str, Dict[str, Any]] = {}  # {symbol: {direction: {expires_at: ...}}}

        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

        self._load()

    def _load(self):
        """Load cooldowns from disk."""
        with self._lock:
            if not os.path.exists(self.storage_path):
                self._cooldowns = {}
                return

            try:
                with open(self.storage_path, "r") as f:
                    data = json.load(f)

                # Parse timestamps (stored as ISO strings)
                self._cooldowns = {}
                now = datetime.now(timezone.utc)

                for symbol, directions in data.items():
                    self._cooldowns[symbol] = {}
                    for direction, info in directions.items():
                        try:
                            expires_at = datetime.fromisoformat(info["expires_at"])
                            # Only keep active cooldowns
                            if expires_at > now:
                                self._cooldowns[symbol][direction] = {
                                    "expires_at": expires_at,
                                    "price": info.get("price", 0.0),
                                    "reason": info.get("reason", "stop_loss"),
                                }
                        except (ValueError, KeyError):
                            continue

                logger.info(
                    "Loaded %d active cooldowns from %s",
                    sum(len(d) for d in self._cooldowns.values()),
                    self.storage_path,
                )

            except Exception as e:
                logger.error("Failed to load cooldowns: %s", e)
                self._cooldowns = {}

    def _save(self):
        """Save active cooldowns to disk."""
        try:
            # Prepare serializable data
            data = {}
            now = datetime.now(timezone.utc)

            for symbol, directions in self._cooldowns.items():
                symbol_data = {}
                for direction, info in directions.items():
                    # Only save future expirations
                    if info["expires_at"] > now:
                        symbol_data[direction] = {
                            "expires_at": info["expires_at"].isoformat(),
                            "price": info.get("price", 0.0),
                            "reason": info.get("reason", "stop_loss"),
                        }
                if symbol_data:
                    data[symbol] = symbol_data

            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error("Failed to save cooldowns: %s", e)

    def is_active(
        self,
        symbol: str,
        direction: str,
        current_price: float = 0.0,
        price_move_pct_threshold: float = 0.08,
    ) -> Optional[Dict[str, Any]]:
        """
        Check if cooldown is active.

        Supports early release when price has moved far enough from the stop-out price
        to represent a genuinely new setup. A cooldown is lifted early if current price
        has moved more than `price_move_pct_threshold` (default 8%) away from the stop price
        in the favorable direction (i.e., price dropped 8%+ for a LONG cooldown after a stop,
        indicating a structurally different entry level now exists).

        Returns:
            Dict with cooldown info if still active, None if expired or early-released.
        """
        with self._lock:
            if symbol not in self._cooldowns:
                return None

            info = self._cooldowns[symbol].get(direction)
            if not info:
                return None

            if info["expires_at"] <= datetime.now(timezone.utc):
                # Time-expired - clean up immediately
                del self._cooldowns[symbol][direction]
                if not self._cooldowns[symbol]:
                    del self._cooldowns[symbol]
                return None

            # Price-distance early release check
            stop_price = info.get("price", 0.0)
            if current_price > 0 and stop_price > 0 and price_move_pct_threshold > 0:
                pct_move = abs(current_price - stop_price) / stop_price
                if pct_move >= price_move_pct_threshold:
                    # Price has moved far enough — the setup is structurally different now
                    logger.info(
                        "🔓 Cooldown EARLY RELEASE: %s %s | Price moved %.1f%% from stop %.4f (threshold %.0f%%)",
                        symbol,
                        direction,
                        pct_move * 100,
                        stop_price,
                        price_move_pct_threshold * 100,
                    )
                    del self._cooldowns[symbol][direction]
                    if not self._cooldowns[symbol]:
                        del self._cooldowns[symbol]
                    return None

            return info

    def add_cooldown(
        self,
        symbol: str,
        direction: str,
        price: float,
        reason: str = "stop_loss",
        duration_hours: int = 24,
    ):
        """
        Add a new cooldown.

        Args:
            symbol: Trading pair
            direction: 'LONG' or 'SHORT'
            price: Price at validiation failure/stop-out
            reason: Reason for cooldown
            duration_hours: Lockout duration
        """
        with self._lock:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=duration_hours)

            if symbol not in self._cooldowns:
                self._cooldowns[symbol] = {}

            self._cooldowns[symbol][direction] = {
                "expires_at": expires_at,
                "price": price,
                "reason": reason,
            }

            logger.info(
                "❄️ Cooldown added: %s %s for %dh (until %s)",
                symbol,
                direction,
                duration_hours,
                expires_at.strftime("%Y-%m-%d %H:%M"),
            )

            self._save()

    def clear_cooldown(self, symbol: str, direction: Optional[str] = None):
        """Manually clear a cooldown."""
        with self._lock:
            if symbol in self._cooldowns:
                if direction:
                    if direction in self._cooldowns[symbol]:
                        del self._cooldowns[symbol][direction]
                        logger.info("Cleared cooldown for %s %s", symbol, direction)
                else:
                    del self._cooldowns[symbol]
                    logger.info("Cleared all cooldowns for %s", symbol)
                self._save()
