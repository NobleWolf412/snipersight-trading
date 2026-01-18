"""
Symbol Classifier with CoinGecko API Integration

Provides accurate symbol categorization (major, meme, defi, etc.) using:
1. CoinGecko API for authoritative category data
2. TTL-cached results for free-tier safety (10-30 calls/min)
3. Heuristic fallback when API unavailable
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import logging

try:
    import requests
except ImportError:
    requests = None  # type: ignore

logger = logging.getLogger(__name__)


class SymbolCategory(Enum):
    """Symbol classification categories."""
    MAJOR = "major"          # BTC, ETH, BNB, SOL - top market cap, high liquidity
    MEME = "meme"            # DOGE, SHIB, PEPE - meme coins
    DEFI = "defi"            # AAVE, UNI, LINK - DeFi protocols
    GAMING = "gaming"        # AXS, SAND, MANA - Gaming/Metaverse
    AI = "ai"                # FET, RNDR, TAO - AI tokens
    LAYER1 = "layer1"        # New L1 chains (SUI, TIA, SEI)
    LAYER2 = "layer2"        # L2 solutions (ARB, OP, MATIC)
    ALT = "alt"              # Default for unclassified


# CoinGecko category mappings
COINGECKO_CATEGORY_MAP: dict[str, SymbolCategory] = {
    # Major
    "layer-1": SymbolCategory.LAYER1,
    "smart-contract-platform": SymbolCategory.LAYER1,
    # Meme
    "meme-token": SymbolCategory.MEME,
    "dog-themed-coins": SymbolCategory.MEME,
    "cat-themed-coins": SymbolCategory.MEME,
    "solana-meme-coins": SymbolCategory.MEME,
    # DeFi
    "decentralized-finance-defi": SymbolCategory.DEFI,
    "decentralized-exchange": SymbolCategory.DEFI,
    "lending-borrowing": SymbolCategory.DEFI,
    "yield-farming": SymbolCategory.DEFI,
    "liquid-staking": SymbolCategory.DEFI,
    "oracle": SymbolCategory.DEFI,
    # Gaming
    "gaming": SymbolCategory.GAMING,
    "play-to-earn": SymbolCategory.GAMING,
    "metaverse": SymbolCategory.GAMING,
    "nft": SymbolCategory.GAMING,
    # AI
    "artificial-intelligence": SymbolCategory.AI,
    "ai-agents": SymbolCategory.AI,
    "gpu": SymbolCategory.AI,
    # L2
    "layer-2": SymbolCategory.LAYER2,
    "ethereum-layer-2": SymbolCategory.LAYER2,
    "optimism-ecosystem": SymbolCategory.LAYER2,
    "arbitrum-ecosystem": SymbolCategory.LAYER2,
    "polygon-ecosystem": SymbolCategory.LAYER2,
}

# Heuristic fallback data
HEURISTIC_MAJORS: set[str] = {
    # Top tier (BTC, ETH, major exchanges)
    "BTC", "ETH", "BNB", "USDT", "USDC",
    # Top L1s
    "SOL", "ADA", "AVAX", "DOT", "ATOM", "TON", "TRX", "XLM",
    # Popular alts with staying power
    "XRP", "LTC", "BCH", "ETC", "XMR", "ALGO", "VET", "FIL",
    # Major L2s (high volume, important infrastructure)
    "MATIC", "ARB", "OP",
    # Major DeFi blue chips
    "LINK", "UNI", "AAVE", "CRV", "MKR", "SNX", "COMP",
    # New L1s with high volume (2024-2025)
    "SUI", "TIA", "INJ", "SEI", "APT", "NEAR", "FTM", "HBAR",
    "WLD", "JUP", "RUNE", "KAVA", "OSMO", "ROSE", "FET"
}

HEURISTIC_MEME_HINTS: tuple[str, ...] = (
    # OG memes (2021-2022)
    "DOGE", "SHIB", "FLOKI", "ELON", "BABYDOGE", "INU",
    # Pepe era (2023)
    "PEPE", "WOJAK", "TURBO", "MEME", "LADYS", "BOBO",
    # Solana memes (2023-2024)
    "BONK", "WIF", "BOME", "MYRO", "SAMO", "SLERF", "PONKE", "COQ",
    "MEW", "POPCAT", "SNEK", "TOSHI", "BOB", "SMOG", "SILLY",
    # Base chain memes (2024)
    "BRETT", "DEGEN", "TOSHI", "NORMIE", "KEYCAT",
    # Political/narrative memes (2024-2025)
    "TRUMP", "BODEN", "TREMP", "MAGA", "KAMA",
    # AI agent memes (2024-2025)
    "GOAT", "ACT", "FARTCOIN", "ZEREBRO", "AI16Z", "VIRTUAL",
    # Recent viral memes (2024-2025)
    "PNUT", "NEIRO", "GIGA", "MOG", "CAT", "GROYPER", "RETARDIO",
    "WEN", "MICHI", "BILLY", "HIGHER", "CHOMP", "FWOG", "MANEKI",
    # Meme indicators (substring matches)
    "PEPE", "INU", "DOGE", "SHIB", "FLOKI", "ELON", "MEME",
)

HEURISTIC_DEFI: set[str] = {
    # Blue chip DeFi
    "AAVE", "UNI", "LINK", "MKR", "SNX", "COMP", "YFI",
    "CRV", "SUSHI", "1INCH", "BAL",
    # Liquid staking
    "LDO", "RPL", "FXS", "RETH", "SFRXETH",
    # Derivatives & perps
    "GMX", "DYDX", "GNS", "KWENTA", "HMX",
    # Yield & farming
    "PENDLE", "JOE", "CAKE", "RAY", "BEEFY",
    # Bridges & infra
    "ACROSS", "SYN", "CELER", "HOP",
    # RWA (Real World Assets)
    "ONDO", "MKR", "TRU", "CFG",
}

HEURISTIC_AI: set[str] = {
    # Infrastructure AI
    "FET", "RNDR", "TAO", "AGIX", "OCEAN", "GRT", "NMR",
    # AI agents & platforms
    "AI16Z", "VIRTUAL", "ARKM", "OLAS", "SPEC", "PRIME",
    # Compute & GPU
    "AIOZ", "ICP", "CTXC", "AKT",
    # Data & oracle AI
    "ROSE", "ORAI", "DYDX",
}

HEURISTIC_GAMING: set[str] = {
    # Metaverse OGs
    "AXS", "SAND", "MANA", "ENJ", "GALA",
    # Gaming infrastructure
    "IMX", "BEAM", "PRIME", "MAGIC", "PORTAL", "RON",
    # Play-to-earn
    "ILV", "PIXELS", "GODS", "ALICE", "TLM", "YGG",
    # NFT gaming
    "FLOW", "WAX", "ULTRA", "JEWEL",
}

HEURISTIC_L2: set[str] = {
    # Major L2s
    "ARB", "OP", "MATIC", "STRK", "ZK",
    # New L2s (2024)
    "MANTA", "BLAST", "SCROLL", "LINEA", "MODE", "METIS",
    # Alt-L1 L2s
    "CELO", "MOVR", "GLMR",
}


@dataclass
class CoinGeckoCache:
    """Cache for CoinGecko API responses with TTL."""
    data: dict[str, SymbolCategory] = field(default_factory=dict)
    last_fetch: float = 0.0
    ttl_seconds: float = 600.0  # 10 minutes
    last_error: float = 0.0
    error_backoff: float = 60.0  # 1 minute backoff on errors
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def is_valid(self) -> bool:
        """Check if cache is still valid."""
        now = time.time()
        return bool(self.data) and (now - self.last_fetch) < self.ttl_seconds

    def is_error_backoff(self) -> bool:
        """Check if we're in error backoff period."""
        if self.last_error == 0:
            return False
        return (time.time() - self.last_error) < self.error_backoff

    def set(self, data: dict[str, SymbolCategory]) -> None:
        """Set cache data with current timestamp."""
        with self._lock:
            self.data = data
            self.last_fetch = time.time()
            self.last_error = 0.0

    def get(self, symbol: str) -> Optional[SymbolCategory]:
        """Get category for symbol if cached."""
        with self._lock:
            return self.data.get(symbol)

    def mark_error(self) -> None:
        """Mark that an error occurred."""
        with self._lock:
            self.last_error = time.time()


class SymbolClassifier:
    """
    Classifies trading symbols using CoinGecko API with heuristic fallback.
    
    Usage:
        classifier = get_classifier()
        category = classifier.classify("BTC/USDT")
        if classifier.is_meme("PEPE/USDT"):
            print("Meme coin detected!")
            
    Note:
        By default, classify() uses heuristics only (fast).
        Call refresh_cache() explicitly to fetch CoinGecko data.
        Set auto_fetch=True to enable automatic API fetching.
    """

    def __init__(
        self,
        cache_ttl_seconds: float = 600.0,
        coingecko_timeout: float = 10.0,
        max_coins: int = 250,
        auto_fetch: bool = False,
    ):
        """
        Initialize classifier.
        
        Args:
            cache_ttl_seconds: How long to cache CoinGecko data
            coingecko_timeout: API request timeout
            max_coins: Number of top coins to fetch from CoinGecko
            auto_fetch: If True, automatically fetch from CoinGecko on classify()
        """
        self._cache = CoinGeckoCache(ttl_seconds=cache_ttl_seconds)
        self._timeout = coingecko_timeout
        self._max_coins = max_coins
        self._coingecko_url = "https://api.coingecko.com/api/v3"
        self._auto_fetch = auto_fetch

    def _extract_base(self, symbol: str) -> str:
        """Extract base currency from symbol (e.g., BTC/USDT -> BTC)."""
        if "/" in symbol:
            return symbol.split("/")[0].upper()
        # Handle formats like BTCUSDT
        for quote in ("USDT", "BUSD", "USD", "USDC"):
            if symbol.upper().endswith(quote):
                return symbol.upper()[:-len(quote)]
        return symbol.upper()

    def _fetch_coingecko_data(self) -> dict[str, SymbolCategory]:
        """Fetch category data from CoinGecko API."""
        if requests is None:
            logger.warning("requests library not available, using heuristics only")
            return {}

        result: dict[str, SymbolCategory] = {}

        try:
            # Fetch top coins by market cap
            url = f"{self._coingecko_url}/coins/markets"
            params = {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": self._max_coins,
                "page": 1,
                "sparkline": "false",
            }

            response = requests.get(url, params=params, timeout=self._timeout)
            response.raise_for_status()
            coins = response.json()

            # Get coin IDs for detailed info
            coin_ids = [coin["id"] for coin in coins[:100]]  # Limit to top 100 for detailed info

            # Map symbols to coin IDs
            symbol_to_id: dict[str, str] = {}
            for coin in coins:
                symbol = coin.get("symbol", "").upper()
                coin_id = coin.get("id", "")
                if symbol and coin_id:
                    symbol_to_id[symbol] = coin_id

            # Fetch detailed info with categories (batch request)
            # Note: CoinGecko free tier limits this, so we use markets endpoint categories
            for coin in coins:
                symbol = coin.get("symbol", "").upper()
                if not symbol:
                    continue

                # Use market cap rank for major classification
                rank = coin.get("market_cap_rank", 999)
                if rank and rank <= 20:
                    result[symbol] = SymbolCategory.MAJOR

            # Fetch categories for top coins (more detailed)
            # This uses the /coins/{id} endpoint for category data
            # Limited calls to stay within free tier
            for coin_id in coin_ids[:50]:  # Only fetch detailed info for top 50
                try:
                    detail_url = f"{self._coingecko_url}/coins/{coin_id}"
                    detail_params = {
                        "localization": "false",
                        "tickers": "false",
                        "market_data": "false",
                        "community_data": "false",
                        "developer_data": "false",
                    }
                    detail_response = requests.get(
                        detail_url, params=detail_params, timeout=self._timeout
                    )

                    if detail_response.status_code == 429:
                        logger.warning("CoinGecko rate limit hit, using partial data")
                        break

                    detail_response.raise_for_status()
                    detail = detail_response.json()

                    symbol = detail.get("symbol", "").upper()
                    categories = detail.get("categories", [])

                    if symbol and categories:
                        for cat in categories:
                            cat_lower = cat.lower().replace(" ", "-")
                            if cat_lower in COINGECKO_CATEGORY_MAP:
                                # Don't override MAJOR classification for top coins
                                if symbol not in result or result[symbol] != SymbolCategory.MAJOR:
                                    result[symbol] = COINGECKO_CATEGORY_MAP[cat_lower]
                                break

                    # Small delay to respect rate limits
                    time.sleep(0.1)

                except requests.exceptions.RequestException:
                    # Continue with other coins on individual failures
                    continue

            logger.info(f"CoinGecko: fetched {len(result)} symbol classifications")
            return result

        except requests.exceptions.RequestException as e:
            logger.warning(f"CoinGecko API error: {e}")
            self._cache.mark_error()
            return {}

    def enable_auto_fetch(self) -> None:
        """Enable automatic CoinGecko fetching."""
        self._auto_fetch = True
        logger.info("SymbolClassifier: Auto-fetch enabled via runtime configuration")

    def _ensure_cache(self) -> None:
        """Ensure cache is populated, fetching if needed (only when auto_fetch=True)."""
        if not self._auto_fetch:
            return
            
        if self._cache.is_valid():
            return

        if self._cache.is_error_backoff():
            logger.debug("CoinGecko in error backoff, using heuristics")
            return

        data = self._fetch_coingecko_data()
        if data:
            self._cache.set(data)

    def _heuristic_classify(self, base: str) -> SymbolCategory:
        """Classify using heuristic rules."""
        base_upper = base.upper()

        if base_upper in HEURISTIC_MAJORS:
            return SymbolCategory.MAJOR

        # Check meme hints (includes substrings)
        for hint in HEURISTIC_MEME_HINTS:
            if hint in base_upper or base_upper == hint:
                return SymbolCategory.MEME

        if base_upper in HEURISTIC_DEFI:
            return SymbolCategory.DEFI

        if base_upper in HEURISTIC_AI:
            return SymbolCategory.AI

        if base_upper in HEURISTIC_GAMING:
            return SymbolCategory.GAMING

        if base_upper in HEURISTIC_L2:
            return SymbolCategory.LAYER2

        return SymbolCategory.ALT

    def classify(self, symbol: str) -> SymbolCategory:
        """
        Classify a trading symbol.
        
        Args:
            symbol: Trading pair (e.g., "BTC/USDT", "BTCUSDT", "BTC")
            
        Returns:
            SymbolCategory classification
        """
        base = self._extract_base(symbol)

        # Try cache first
        self._ensure_cache()
        cached = self._cache.get(base)
        if cached is not None:
            return cached

        # Fallback to heuristics
        return self._heuristic_classify(base)

    def is_meme(self, symbol: str) -> bool:
        """Check if symbol is a meme coin."""
        return self.classify(symbol) == SymbolCategory.MEME

    def is_major(self, symbol: str) -> bool:
        """Check if symbol is a major coin."""
        return self.classify(symbol) == SymbolCategory.MAJOR

    def is_defi(self, symbol: str) -> bool:
        """Check if symbol is a DeFi token."""
        return self.classify(symbol) == SymbolCategory.DEFI

    def is_ai(self, symbol: str) -> bool:
        """Check if symbol is an AI token."""
        return self.classify(symbol) == SymbolCategory.AI

    def is_gaming(self, symbol: str) -> bool:
        """Check if symbol is a gaming/metaverse token."""
        return self.classify(symbol) == SymbolCategory.GAMING

    def is_layer2(self, symbol: str) -> bool:
        """Check if symbol is an L2 token."""
        return self.classify(symbol) == SymbolCategory.LAYER2

    def get_all_cached(self) -> dict[str, SymbolCategory]:
        """Get all cached classifications."""
        return dict(self._cache.data)

    def refresh_cache(self) -> bool:
        """Force refresh the CoinGecko cache."""
        self._cache.data.clear()
        self._cache.last_fetch = 0.0
        self._ensure_cache()
        return self._cache.is_valid()


# Singleton instance
_classifier_instance: Optional[SymbolClassifier] = None
_classifier_lock = threading.Lock()


def get_classifier(
    cache_ttl_seconds: float = 600.0,
    coingecko_timeout: float = 10.0,
    max_coins: int = 250,
    auto_fetch: bool = False,
) -> SymbolClassifier:
    """
    Get the singleton SymbolClassifier instance.
    
    Args:
        cache_ttl_seconds: How long to cache CoinGecko data
        coingecko_timeout: API request timeout
        max_coins: Number of top coins to fetch from CoinGecko
        auto_fetch: If True, automatically fetch from CoinGecko on classify()
        
    Returns:
        Shared SymbolClassifier instance
    """
    global _classifier_instance

    if _classifier_instance is None:
        with _classifier_lock:
            if _classifier_instance is None:
                _classifier_instance = SymbolClassifier(
                    cache_ttl_seconds=cache_ttl_seconds,
                    coingecko_timeout=coingecko_timeout,
                    max_coins=max_coins,
                    auto_fetch=auto_fetch,
                )

    return _classifier_instance


def reset_classifier() -> None:
    """Reset the singleton instance (for testing)."""
    global _classifier_instance
    with _classifier_lock:
        _classifier_instance = None


# Quick test function
def test_classifier() -> None:
    """Quick test of classifier functionality."""
    classifier = get_classifier()

    test_cases = [
        ("BTC/USDT", SymbolCategory.MAJOR),
        ("ETH/USDT", SymbolCategory.MAJOR),
        ("PEPE/USDT", SymbolCategory.MEME),
        ("DOGE/USDT", SymbolCategory.MEME),
        ("AAVE/USDT", SymbolCategory.DEFI),
        ("ARB/USDT", SymbolCategory.LAYER2),
        ("FET/USDT", SymbolCategory.AI),
        ("AXS/USDT", SymbolCategory.GAMING),
    ]

    print("Testing SymbolClassifier...")
    for symbol, expected in test_cases:
        result = classifier.classify(symbol)
        status = "✅" if result == expected else "❌"
        print(f"  {status} {symbol}: {result.value} (expected: {expected.value})")

    print(f"\nCache contains {len(classifier.get_all_cached())} symbols")


if __name__ == "__main__":
    test_classifier()
