"""Fresh source-identified global market shares; no stale or synthetic fallback.

The stable bucket tracks USDT and USDC, not every stablecoin. The remaining
bucket is the rest of the global market. Legacy CryptoCompare basket histories
are retained separately and never spliced into this provider's observations.
"""
from __future__ import annotations

import json
import logging
import math
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)
COINGECKO_API_URL = "https://api.coingecko.com/api/v3/global"
DOMINANCE_VERSION = "coingecko-global-usdt-usdc-v1"
DOMINANCE_SOURCE = "CoinGecko global market cap; stable share = USDT + USDC; remaining share includes all other assets"
CACHE_DIR = Path("backend/cache/dominance")
CACHE_FILE = CACHE_DIR / (DOMINANCE_VERSION + ".json")
CACHE_TTL_SECONDS = 60 * 60


@dataclass
class DominanceSnapshot:
    timestamp: float  # Provider observation time, never the time an old response was read
    btc_dom: float
    stable_dom: float
    alt_dom: float  # Compatibility name for the remaining global market
    total_market_cap: float
    btc_market_cap: float
    stable_market_cap: float
    alt_market_cap: float
    source: str = DOMINANCE_VERSION


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
    """Single-flight public feed with a source-specific cache and bounded retries."""

    def __init__(self, api_key: Optional[str] = None, cache_dir: Optional[Path] = None):
        # An optional Demo key is sent only to the fixed CoinGecko API host.
        self.api_key = api_key or os.getenv("COINGECKO_DEMO_API_KEY")
        self.cache_dir = cache_dir or CACHE_DIR
        self.cache_file = self.cache_dir / (DOMINANCE_VERSION + ".json")
        self.history_file = self.cache_dir / (DOMINANCE_VERSION + "-history.jsonl")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._retry_after = 0.0
        self.last_error: Optional[str] = None

    @staticmethod
    def _is_cache_valid(cache: Dict) -> bool:
        try:
            age = time.time() - float(cache["timestamp"])
            return math.isfinite(age) and 0 <= age < CACHE_TTL_SECONDS
        except (KeyError, TypeError, ValueError, OverflowError):
            return False

    @staticmethod
    def _decode_snapshot(data: Dict, *, fresh: bool = True) -> DominanceSnapshot:
        if not isinstance(data, dict) or data.get("source") != DOMINANCE_VERSION:
            raise ValueError("Market-share source or composition changed")
        snapshot = DominanceSnapshot(**{key: data[key] for key in DominanceSnapshot.__dataclass_fields__})
        values = [snapshot.timestamp, snapshot.btc_dom, snapshot.stable_dom, snapshot.alt_dom,
                  snapshot.total_market_cap, snapshot.btc_market_cap,
                  snapshot.stable_market_cap, snapshot.alt_market_cap]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            raise ValueError("Invalid market-share observation")
        if snapshot.total_market_cap <= 0 or not 0 < snapshot.btc_dom <= 100:
            raise ValueError("Missing market capitalization")
        if not all(0 <= v <= 100 for v in (snapshot.stable_dom, snapshot.alt_dom)):
            raise ValueError("Invalid market-share percentage")
        if not math.isclose(snapshot.btc_dom + snapshot.stable_dom + snapshot.alt_dom, 100., abs_tol=.02):
            raise ValueError("Incomplete market-share partition")
        for cap, share in ((snapshot.btc_market_cap, snapshot.btc_dom),
                           (snapshot.stable_market_cap, snapshot.stable_dom),
                           (snapshot.alt_market_cap, snapshot.alt_dom)):
            if not math.isclose(cap, snapshot.total_market_cap * share / 100., rel_tol=1e-6, abs_tol=.01):
                raise ValueError("Inconsistent market-share capitalization")
        if snapshot.timestamp <= 0 or (fresh and not DominanceService._is_cache_valid(data)):
            raise ValueError("Market-share observation is stale or future-dated")
        return snapshot

    def _load_cache(self) -> Optional[DominanceSnapshot]:
        try:
            return self._decode_snapshot(json.loads(self.cache_file.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def _save_cache(self, snapshot: DominanceSnapshot) -> None:
        try:
            temporary = self.cache_file.with_suffix(".tmp")
            temporary.write_text(json.dumps(asdict(snapshot)), encoding="utf-8")
            temporary.replace(self.cache_file)
        except OSError:
            logger.warning("Could not persist the current dominance cache")

    def _fetch_global(self) -> DominanceSnapshot:
        headers = {"x-cg-demo-api-key": self.api_key} if self.api_key else {}
        response = requests.get(COINGECKO_API_URL, headers=headers, timeout=10)
        # Never include request headers or credential-bearing exception URLs in errors.
        if response.status_code != 200:
            raise ValueError(f"CoinGecko market data returned HTTP {response.status_code}; retry later or configure COINGECKO_DEMO_API_KEY")
        data = response.json()["data"]
        shares = data["market_cap_percentage"]
        raw_values = [data["total_market_cap"]["usd"], data["updated_at"], *(shares[key] for key in ("btc", "usdt", "usdc"))]
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in raw_values):
            raise ValueError("Market share feed contains non-numeric values")
        total = float(data["total_market_cap"]["usd"])
        btc, usdt, usdc = (float(shares[key]) for key in ("btc", "usdt", "usdc"))
        if not all(math.isfinite(v) and 0 < v < 100 for v in (btc, usdt, usdc)):
            raise ValueError("Missing BTC, USDT or USDC market share")
        stable = usdt + usdc
        remaining = 100. - btc - stable
        return self._decode_snapshot(asdict(DominanceSnapshot(
            timestamp=float(data["updated_at"]), btc_dom=btc, stable_dom=stable,
            alt_dom=remaining, total_market_cap=total, btc_market_cap=total * btc / 100.,
            stable_market_cap=total * stable / 100., alt_market_cap=total * remaining / 100.)))

    def get_dominance(self, force_refresh: bool = False) -> Optional[DominanceSnapshot]:
        with self._lock:
            cached = self._load_cache()
            if cached and not force_refresh:
                self.last_error = None
                return cached
            if time.monotonic() < self._retry_after:
                return cached
            try:
                snapshot = self._fetch_global()
            except (requests.RequestException, ValueError, KeyError, TypeError, OverflowError) as exc:
                self.last_error = (str(exc) if isinstance(exc, ValueError) and not isinstance(exc, requests.RequestException)
                                   else "Market data could not be read; check the connection and retry")
                self._retry_after = time.monotonic() + 60.
                logger.warning("Dominance unavailable: %s", self.last_error)
                return cached
            self.last_error = None
            self._retry_after = 0.
            self._save_cache(snapshot)
            self._append_to_history(snapshot)
            return snapshot

    def _append_to_history(self, snapshot: DominanceSnapshot) -> None:
        """Append new source observations; never rewrite legacy history."""
        try:
            previous = None
            if self.history_file.exists():
                with self.history_file.open(encoding="utf-8") as history:
                    for line in history:
                        try:
                            previous = json.loads(line)["timestamp"]
                        except (ValueError, KeyError, TypeError):
                            continue
            if previous is not None and snapshot.timestamp - float(previous) < 3600:
                return
            with self.history_file.open("a", encoding="utf-8") as history:
                history.write(json.dumps(asdict(snapshot)) + "\n")
        except (OSError, ValueError, TypeError):
            logger.warning("Could not append dominance observation history")

    def get_dominance_context(self, lookback_days: int = 7) -> Optional[DominanceContext]:
        with self._lock:
            current = self.get_dominance()
            if current is None:
                return None
            history = []
            cutoff = time.time() - max(0, lookback_days) * 86400
            try:
                with self.history_file.open(encoding="utf-8") as source:
                    for line in source:
                        try:
                            observation = self._decode_snapshot(json.loads(line), fresh=False)
                            if cutoff <= observation.timestamp < current.timestamp:
                                history.append(observation)
                        except (ValueError, TypeError, KeyError):
                            continue
            except OSError:
                pass
            return DominanceContext(current=current, history=history)


_service: Optional[DominanceService] = None
_service_lock = threading.Lock()


def get_dominance_service(api_key: Optional[str] = None) -> DominanceService:
    global _service
    with _service_lock:
        if _service is None:
            _service = DominanceService(api_key=api_key)
        return _service


def get_current_dominance() -> Optional[DominanceSnapshot]:
    return get_dominance_service().get_dominance()


def get_dominance_for_macro() -> Tuple[float, float, float]:
    """Return fresh observed percentages; unavailable evidence is never zero."""
    return dominance_values(get_current_dominance())


def dominance_values(snapshot) -> Tuple[float, float, float]:
    """Validate one captured observation so values and expiry share ownership."""
    try:
        if snapshot is None:
            raise ValueError("missing snapshot")
        age = time.time() - float(snapshot.timestamp)
        values = tuple(float(value) for value in (snapshot.btc_dom, snapshot.alt_dom, snapshot.stable_dom))
        if not math.isfinite(age) or not 0 <= age < CACHE_TTL_SECONDS:
            raise ValueError("stale, future or invalid observation time")
        if not all(math.isfinite(value) and 0 <= value <= 100 for value in values):
            raise ValueError("invalid percentage")
        # Three values rounded to two decimal places can differ by 0.015 in sum.
        if values[0] <= 0 or not math.isclose(sum(values), 100.0, rel_tol=0, abs_tol=0.02):
            raise ValueError("incomplete market-cap partition")
        return values
    except (AttributeError, TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"DOMINANCE_UNAVAILABLE: {error}") from error
