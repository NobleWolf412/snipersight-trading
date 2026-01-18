"""
Dominance Service - Real-time crypto dominance metrics from CryptoCompare.

Fetches market cap data to calculate:
- BTC.D (Bitcoin Dominance)
- Stable.D (Stablecoin Dominance: USDT + USDC)
- Alt.D (Altcoin Dominance: everything else)

Uses local file cache (24h TTL) to respect API rate limits.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# CryptoCompare free tier endpoint for market cap
CRYPTOCOMPARE_API_URL = "https://min-api.cryptocompare.com/data/top/mktcapfull"

# Cache settings
CACHE_DIR = Path("backend/cache/dominance")
CACHE_FILE = CACHE_DIR / "dominance_cache.json"
CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours

# Coins to track for stablecoin dominance
STABLECOINS = {"USDT", "USDC", "DAI", "BUSD", "TUSD", "USDP", "FRAX", "GUSD"}


@dataclass
class DominanceSnapshot:
    """Single point-in-time dominance reading."""

    timestamp: float  # Unix timestamp
    btc_dom: float  # 0-100 percentage
    stable_dom: float  # 0-100 percentage
    alt_dom: float  # 0-100 percentage
    total_market_cap: float  # USD
    btc_market_cap: float
    stable_market_cap: float
    alt_market_cap: float


@dataclass
class DominanceContext:
    """Dominance data with historical series for velocity calculation."""

    current: DominanceSnapshot
    history: List[DominanceSnapshot] = field(default_factory=list)

    @property
    def btc_dom(self) -> float:
        return self.current.btc_dom

    @property
    def stable_dom(self) -> float:
        return self.current.stable_dom

    @property
    def alt_dom(self) -> float:
        return self.current.alt_dom

    def get_series(
        self,
    ) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]], List[Tuple[float, float]]]:
        """
        Return (btc_dom_series, alt_dom_series, stable_dom_series) for velocity calculation.
        Each is a list of (timestamp, value) tuples, ascending by time.
        """
        all_points = sorted(self.history + [self.current], key=lambda x: x.timestamp)
        btc_series = [(p.timestamp, p.btc_dom) for p in all_points]
        alt_series = [(p.timestamp, p.alt_dom) for p in all_points]
        stable_series = [(p.timestamp, p.stable_dom) for p in all_points]
        return btc_series, alt_series, stable_series


class DominanceService:
    """
    Service for fetching and caching crypto market dominance metrics.

    Uses CryptoCompare's free tier API (250 calls/day for daily data).
    Implements local file caching to minimize API calls.
    """

    def __init__(self, api_key: Optional[str] = None, cache_dir: Optional[Path] = None):
        """
        Initialize DominanceService.

        Args:
            api_key: Optional CryptoCompare API key (increases rate limits)
            cache_dir: Optional custom cache directory
        """
        self.api_key = api_key
        self.cache_dir = cache_dir or CACHE_DIR
        self.cache_file = self.cache_dir / "dominance_cache.json"
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """Create cache directory if it doesn't exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _load_cache(self) -> Optional[Dict]:
        """Load cached data from disk."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning("Failed to load dominance cache: %s", e)
        return None

    def _save_cache(self, data: Dict) -> None:
        """Save data to disk cache."""
        try:
            with open(self.cache_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug("Dominance cache saved")
        except Exception as e:
            logger.warning("Failed to save dominance cache: %s", e)

    def _is_cache_valid(self, cache: Dict) -> bool:
        """Check if cache is still within TTL."""
        if not cache or "timestamp" not in cache:
            return False
        age = time.time() - cache["timestamp"]
        return age < CACHE_TTL_SECONDS

    def _fetch_market_caps(self, limit: int = 100) -> Optional[List[Dict]]:
        """
        Fetch top coins by market cap from CryptoCompare.

        Args:
            limit: Number of top coins to fetch (max 100 per request)

        Returns:
            List of coin data dicts or None if request fails
        """
        headers = {}
        if self.api_key:
            headers["authorization"] = f"Apikey {self.api_key}"

        try:
            # Fetch top 100 coins by market cap
            params = {"limit": limit, "tsym": "USD", "page": 0}

            response = requests.get(
                CRYPTOCOMPARE_API_URL, params=params, headers=headers, timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if data.get("Response") == "Error":
                logger.error("CryptoCompare API error: %s", data.get("Message", "Unknown"))
                return None

            return data.get("Data", [])

        except requests.Timeout:
            logger.error("CryptoCompare API timeout")
            return None
        except requests.RequestException as e:
            logger.error("CryptoCompare API request failed: %s", e)
            return None
        except Exception as e:
            logger.error("Unexpected error fetching market caps: %s", e)
            return None

    def _fetch_stablecoin_market_caps(self) -> float:
        """
        Fetch market caps for major stablecoins directly.

        Uses CryptoCompare's pricemultifull endpoint to get individual coin data.
        This is needed because stablecoins often don't appear in top-100 by volume.

        Returns:
            Total stablecoin market cap in USD
        """
        headers = {}
        if self.api_key:
            headers["authorization"] = f"Apikey {self.api_key}"

        # Major stablecoins to track
        stables = ["USDT", "USDC", "DAI", "BUSD"]

        try:
            # Use pricemultifull endpoint to get detailed data for specific coins
            params = {"fsyms": ",".join(stables), "tsyms": "USD"}

            response = requests.get(
                "https://min-api.cryptocompare.com/data/pricemultifull",
                params=params,
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("Response") == "Error":
                logger.warning(
                    "CryptoCompare stablecoin API error: %s", data.get("Message", "Unknown")
                )
                return 0.0

            total_stable_cap = 0.0
            raw_data = data.get("RAW", {})

            for symbol in stables:
                if symbol in raw_data and "USD" in raw_data[symbol]:
                    mktcap = raw_data[symbol]["USD"].get("MKTCAP", 0)
                    if mktcap:
                        total_stable_cap += float(mktcap)
                        logger.debug(f"{symbol} market cap: ${mktcap:,.0f}")

            logger.info(f"Total stablecoin market cap: ${total_stable_cap:,.0f}")
            return total_stable_cap

        except requests.Timeout:
            logger.warning("CryptoCompare stablecoin API timeout")
            return 0.0
        except requests.RequestException as e:
            logger.warning("CryptoCompare stablecoin API request failed: %s", e)
            return 0.0
        except Exception as e:
            logger.warning("Unexpected error fetching stablecoin market caps: %s", e)
            return 0.0

    def _calculate_dominance(
        self, coin_data: List[Dict], stablecoin_market_cap: float = 0.0
    ) -> Optional[DominanceSnapshot]:
        """
        Calculate dominance percentages from coin market cap data.

        Args:
            coin_data: List of coin data from CryptoCompare
            stablecoin_market_cap: Pre-fetched stablecoin market cap (since they're not in top-100)

        Returns:
            DominanceSnapshot or None if calculation fails
        """
        if not coin_data:
            return None

        total_market_cap = 0.0
        btc_market_cap = 0.0
        stable_market_cap_from_top100 = 0.0

        for coin in coin_data:
            try:
                coin_info = coin.get("CoinInfo", {})
                raw = coin.get("RAW", {}).get("USD", {})

                symbol = coin_info.get("Name", "").upper()
                mktcap = float(raw.get("MKTCAP", 0) or 0)

                total_market_cap += mktcap

                if symbol == "BTC":
                    btc_market_cap = mktcap
                elif symbol in STABLECOINS:
                    stable_market_cap_from_top100 += mktcap

            except (ValueError, TypeError, KeyError) as e:
                logger.debug("Skipping coin data: %s", e)
                continue

        if total_market_cap <= 0:
            logger.warning("Total market cap is zero or negative")
            return None

        # Use the separately fetched stablecoin market cap if it's higher
        # (top-100 might not include all stablecoins)
        stable_market_cap = max(stablecoin_market_cap, stable_market_cap_from_top100)

        # Add stablecoin market cap to total if it wasn't already counted
        if stablecoin_market_cap > stable_market_cap_from_top100:
            total_market_cap += stablecoin_market_cap - stable_market_cap_from_top100

        alt_market_cap = total_market_cap - btc_market_cap - stable_market_cap

        btc_dom = (btc_market_cap / total_market_cap) * 100
        stable_dom = (stable_market_cap / total_market_cap) * 100
        alt_dom = (alt_market_cap / total_market_cap) * 100

        return DominanceSnapshot(
            timestamp=time.time(),
            btc_dom=round(btc_dom, 2),
            stable_dom=round(stable_dom, 2),
            alt_dom=round(alt_dom, 2),
            total_market_cap=total_market_cap,
            btc_market_cap=btc_market_cap,
            stable_market_cap=stable_market_cap,
            alt_market_cap=alt_market_cap,
        )

    def get_dominance(self, force_refresh: bool = False) -> Optional[DominanceSnapshot]:
        """
        Get current dominance metrics, using cache when valid.

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            DominanceSnapshot or None if fetch fails
        """
        # Check cache first
        if not force_refresh:
            cache = self._load_cache()
            if cache and self._is_cache_valid(cache):
                logger.debug(
                    "Using cached dominance data (age: %.0f min)",
                    (time.time() - cache["timestamp"]) / 60,
                )
                try:
                    return DominanceSnapshot(
                        timestamp=cache["timestamp"],
                        btc_dom=cache["btc_dom"],
                        stable_dom=cache["stable_dom"],
                        alt_dom=cache["alt_dom"],
                        total_market_cap=cache.get("total_market_cap", 0),
                        btc_market_cap=cache.get("btc_market_cap", 0),
                        stable_market_cap=cache.get("stable_market_cap", 0),
                        alt_market_cap=cache.get("alt_market_cap", 0),
                    )
                except Exception as e:
                    logger.warning("Failed to parse cached data: %s", e)

        # Fetch fresh data
        logger.info("Fetching fresh dominance data from CryptoCompare")
        coin_data = self._fetch_market_caps(limit=100)
        if not coin_data:
            # Fallback to stale cache if available
            cache = self._load_cache()
            if cache:
                logger.warning("Using stale cache due to API failure")
                return DominanceSnapshot(
                    timestamp=cache["timestamp"],
                    btc_dom=cache["btc_dom"],
                    stable_dom=cache["stable_dom"],
                    alt_dom=cache["alt_dom"],
                    total_market_cap=cache.get("total_market_cap", 0),
                    btc_market_cap=cache.get("btc_market_cap", 0),
                    stable_market_cap=cache.get("stable_market_cap", 0),
                    alt_market_cap=cache.get("alt_market_cap", 0),
                )
            return None

        # Fetch stablecoin market caps separately (they're not in top-100)
        stablecoin_market_cap = self._fetch_stablecoin_market_caps()

        snapshot = self._calculate_dominance(coin_data, stablecoin_market_cap)
        if snapshot:
            # Save to cache
            self._save_cache(
                {
                    "timestamp": snapshot.timestamp,
                    "btc_dom": snapshot.btc_dom,
                    "stable_dom": snapshot.stable_dom,
                    "alt_dom": snapshot.alt_dom,
                    "total_market_cap": snapshot.total_market_cap,
                    "btc_market_cap": snapshot.btc_market_cap,
                    "stable_market_cap": snapshot.stable_market_cap,
                    "alt_market_cap": snapshot.alt_market_cap,
                }
            )

        return snapshot

    def get_dominance_context(self, lookback_days: int = 7) -> Optional[DominanceContext]:
        """
        Get dominance context with historical data for velocity calculations.

        Note: CryptoCompare free tier only provides current data.
        Historical data requires premium API or alternative sources.
        For now, returns context with current snapshot only.

        Args:
            lookback_days: Days of history to include (not fully implemented)

        Returns:
            DominanceContext with current snapshot and available history
        """
        current = self.get_dominance()
        if not current:
            return None

        # Load historical snapshots from cache history
        history: List[DominanceSnapshot] = []
        try:
            history_file = self.cache_dir / "dominance_history.json"
            if history_file.exists():
                with open(history_file, "r") as f:
                    history_data = json.load(f)
                    cutoff = time.time() - (lookback_days * 24 * 60 * 60)
                    for entry in history_data:
                        if entry.get("timestamp", 0) >= cutoff:
                            history.append(
                                DominanceSnapshot(
                                    timestamp=entry["timestamp"],
                                    btc_dom=entry["btc_dom"],
                                    stable_dom=entry["stable_dom"],
                                    alt_dom=entry["alt_dom"],
                                    total_market_cap=entry.get("total_market_cap", 0),
                                    btc_market_cap=entry.get("btc_market_cap", 0),
                                    stable_market_cap=entry.get("stable_market_cap", 0),
                                    alt_market_cap=entry.get("alt_market_cap", 0),
                                )
                            )
        except Exception as e:
            logger.debug("Could not load dominance history: %s", e)

        # Append current to history file for future lookbacks
        self._append_to_history(current)

        return DominanceContext(current=current, history=history)

    def _append_to_history(self, snapshot: DominanceSnapshot) -> None:
        """Append snapshot to historical data file."""
        try:
            history_file = self.cache_dir / "dominance_history.json"
            history: List[Dict] = []

            if history_file.exists():
                with open(history_file, "r") as f:
                    history = json.load(f)

            # Avoid duplicates (same hour)
            last_ts = history[-1]["timestamp"] if history else 0
            if snapshot.timestamp - last_ts < 3600:  # 1 hour min between entries
                return

            history.append(
                {
                    "timestamp": snapshot.timestamp,
                    "btc_dom": snapshot.btc_dom,
                    "stable_dom": snapshot.stable_dom,
                    "alt_dom": snapshot.alt_dom,
                    "total_market_cap": snapshot.total_market_cap,
                    "btc_market_cap": snapshot.btc_market_cap,
                    "stable_market_cap": snapshot.stable_market_cap,
                    "alt_market_cap": snapshot.alt_market_cap,
                }
            )

            # Keep only last 30 days
            cutoff = time.time() - (30 * 24 * 60 * 60)
            history = [h for h in history if h["timestamp"] >= cutoff]

            with open(history_file, "w") as f:
                json.dump(history, f, indent=2)

        except Exception as e:
            logger.debug("Failed to append to history: %s", e)


# Module-level singleton for convenience
_service: Optional[DominanceService] = None


def get_dominance_service(api_key: Optional[str] = None) -> DominanceService:
    """Get or create the singleton DominanceService instance."""
    global _service
    if _service is None:
        _service = DominanceService(api_key=api_key)
    return _service


def get_current_dominance() -> Optional[DominanceSnapshot]:
    """Convenience function to get current dominance metrics."""
    return get_dominance_service().get_dominance()


def get_dominance_for_macro() -> Tuple[float, float, float]:
    """
    Get dominance values formatted for MacroContext.

    Returns:
        (btc_dom, alt_dom, stable_dom) tuple, defaults to (0, 0, 0) on failure
    """
    snapshot = get_current_dominance()
    if snapshot:
        return (snapshot.btc_dom, snapshot.alt_dom, snapshot.stable_dom)
    return (0.0, 0.0, 0.0)
