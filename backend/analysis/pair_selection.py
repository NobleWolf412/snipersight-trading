"""Centralized pair selection and category filtering.

- Uses adapters' `get_top_symbols` for ranked candidates
- Robust stablecoin-base exclusion
- Leverage-aware perp detection (adapter-first, heuristic fallback)
- Majors, memes, alts bucket selection with curated majors semantics
- Safe fallback behavior when adapter data is unavailable
- Uses SymbolClassifier for accurate category detection (CoinGecko + heuristics)
"""

from typing import List, Protocol, Optional
from loguru import logger

from backend.analysis.symbol_classifier import (
    get_classifier,
    HEURISTIC_MAJORS,
)


class SupportsTopSymbols(Protocol):
    def get_top_symbols(self, n: int = 20, quote_currency: str = "USDT") -> List[str]: ...

    # Optional: adapters may expose market type helpers
    def is_perp(self, symbol: str) -> bool:  # type: ignore[override]
        ...


# Default fallback list (mirrors existing api_server behavior)
DEFAULT_FALLBACK = [
    "BTC/USDT",
    "ETH/USDT",
    "BNB/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "AVAX/USDT",
    "MATIC/USDT",
    "DOT/USDT",
    "LINK/USDT",
    "DOGE/USDT",
    "SHIB/USDT",
    "PEPE/USDT",
]

# Curated crypto majors used when present in adapter list; preserves list ranking
# Now uses centralized HEURISTIC_MAJORS from symbol_classifier but keeps pair format
HARDCODED_MAJORS = {f"{base}/USDT" for base in HEURISTIC_MAJORS}


# Get the shared classifier instance (defaults to heuristics, no auto-fetch)
_classifier = get_classifier()


def _is_meme_symbol(symbol: str) -> bool:
    """Classify symbol as meme using SymbolClassifier.

    Uses CoinGecko data when cached, falls back to heuristics.
    """
    return _classifier.is_meme(symbol)


def _is_major_symbol(symbol: str) -> bool:
    """Classify symbol as major using SymbolClassifier."""
    return _classifier.is_major(symbol)


def _normalize_token(token: str) -> str:
    """Normalize token by stripping separators ("-", ":", "_") and uppercasing."""
    return token.replace("-", "").replace(":", "").replace("_", "").upper()


def _is_stable_base(symbol: str) -> bool:
    """Detect if the BASE of a symbol is a stablecoin.

    Handles formats like:
    - BASE/USDT
    - FDUSD:USDT
    - USDCUSDT
    - USDT-USD
    - USTC/USDT

    Strategy: normalize BASE (strip separators, uppercase) and check equality or
    startswith against known crypto stable prefixes.
    """
    parts = symbol.split("/")
    base_raw = parts[0] if parts else symbol
    base_norm = _normalize_token(base_raw)

    STABLE_PREFIXES = {
        "USDT",
        "USDC",
        "BUSD",
        "USD",
        "DAI",
        "TUSD",
        "FDUSD",
        "UST",
        "USTC",
    }

    return any(base_norm == s or base_norm.startswith(s) for s in STABLE_PREFIXES)


def _is_perp_with_fallback(adapter: SupportsTopSymbols, symbol: str) -> bool:
    """Prefer adapter.is_perp; otherwise apply conservative heuristics.

    Heuristics:
    - Prefer ":USDT" swap notation (OKX style) over "/USDT" which is often spot
    - Accept markers "-SWAP" or "PERP" (case-insensitive)
    Emits a debug log when heuristic fallback is used.
    """
    try:
        if hasattr(adapter, "is_perp") and adapter.is_perp(symbol):  # type: ignore[attr-defined]
            return True
    except Exception:
        # Continue to heuristic on adapter failures
        pass

    sym_u = symbol.upper()
    heuristic = (":USDT" in sym_u) or ("-SWAP" in sym_u) or ("PERP" in sym_u)
    if heuristic:
        logger.debug(f"perp heuristic matched for symbol={symbol} (adapter lacks/failed is_perp)")
    return heuristic


def select_symbols(
    adapter: SupportsTopSymbols,
    limit: int,
    majors: bool,
    altcoins: bool,
    meme_mode: bool,
    leverage: Optional[int] = None,
    market_type: Optional[str] = None,
) -> List[str]:
    """Resolve final symbol list based on adapter data and category toggles.

    - Oversamples via adapter (3x limit capped at 50)
    - Excludes stablecoin bases
    - Falls back to all symbols or default list when needed
    - Truncates to `limit`
    """

    try:
        # Pass market_type if adapter supports it (it should based on Protocol but we use kwargs or direct if typed)
        # SupportsTopSymbols protocol doesn't explicitly type market_type in get_top_symbols but PhemexAdapter does.
        # We'll try passing it as a named argument if the adapter accepts it, or rely on adapter state.
        # However, checking signature at runtime is messy. PhemexAdapter has it.
        # Let's assume adapter follows the updated contract or ignores extra kwargs if we were dynamic,
        # but here we know we are usually working with PhemexAdapter.
        # Safest way: check if it takes market_type or just pass it if we are confident.
        # Given the previous context, PhemexAdapter.get_top_symbols *does* take market_type.
        all_symbols = adapter.get_top_symbols(
            n=min(limit * 3, 50), quote_currency="USDT", market_type=market_type
        )
    except TypeError:
        # Fallback for adapters that might not accept market_type yet
        all_symbols = adapter.get_top_symbols(n=min(limit * 3, 50), quote_currency="USDT")
    except Exception:
        all_symbols = []

    if not all_symbols:
        all_symbols = DEFAULT_FALLBACK.copy()

    # Exclude stablecoin bases from consideration (crypto-focused)
    all_symbols = [s for s in all_symbols if not _is_stable_base(s)]

    # If leverage is requested (>1), prefer/require perp/marginable symbols
    # BUT only if we are NOT explicitly in spot mode.
    if (leverage or 1) > 1 and market_type != "spot":
        perp_symbols = [s for s in all_symbols if _is_perp_with_fallback(adapter, s)]
        # Require perp when leverage > 1; if empty, try fallback perp-filter
        if perp_symbols:
            all_symbols = perp_symbols
        else:
            fallback_perps = [s for s in DEFAULT_FALLBACK if _is_perp_with_fallback(adapter, s)]
            all_symbols = fallback_perps if fallback_perps else DEFAULT_FALLBACK.copy()
            logger.debug(
                "leverage > 1 but adapter/perp heuristics returned empty; using fallback set"
            )

    # Curated majors when present; preserves ranking order. Fallback to dynamic slice when none found.
    proportional = max(1, int(len(all_symbols) * 0.2))
    top_k = max(3, min(10, proportional))
    # Use curated majors but only within the dynamic top slice window to preserve UX and leave room for alts
    majors_present = [s for s in all_symbols[:top_k] if s in HARDCODED_MAJORS]
    if majors_present:
        majors_list = majors_present
    else:
        majors_list = [s for s in all_symbols[:top_k]]

    # Meme and alt derivations
    memes_list = [s for s in all_symbols if _is_meme_symbol(s)]
    alts_list = [s for s in all_symbols if s not in majors_list and not _is_meme_symbol(s)]

    # Build target according to toggles, preserving ranking within each bucket
    buckets: List[List[str]] = []
    if majors:
        buckets.append(majors_list)
    if meme_mode:
        buckets.append(memes_list)
    if altcoins:
        buckets.append(alts_list)

    # If no toggles, default to all_symbols
    if not buckets:
        buckets = [all_symbols]

    # Greedy fill from buckets in order, then backfill from remaining pool to reach `limit`
    selected: List[str] = []
    for bucket in buckets:
        for s in bucket:
            if len(selected) >= limit:
                break
            if s not in selected:
                selected.append(s)
        if len(selected) >= limit:
            break

    if len(selected) < limit:
        # Backfill from the union of all symbols respecting original ranking
        for s in all_symbols:
            if len(selected) >= limit:
                break
            if s not in selected:
                selected.append(s)

    # Emit a concise selection summary to enrich scanner console output
    try:
        fetched_cnt = len(all_symbols)
        majors_cnt = len(majors_list) if majors else 0
        memes_cnt = len([s for s in all_symbols if _is_meme_symbol(s)]) if meme_mode else 0
        alts_cnt = (
            len([s for s in all_symbols if s not in majors_list and not _is_meme_symbol(s)])
            if altcoins
            else 0
        )
        logger.info(
            "selection adapter=%s limit=%s leverage=%s market=%s toggles majors=%s memes=%s alts=%s fetched=%s final=%s buckets majors=%s memes=%s alts=%s examples majors=%s memes=%s alts=%s",
            adapter.__class__.__name__,
            limit,
            (leverage or 1),
            market_type,
            int(majors),
            int(meme_mode),
            int(altcoins),
            fetched_cnt,
            len(selected),
            majors_cnt,
            memes_cnt,
            alts_cnt,
            ",".join(majors_list[:3]),
            ",".join([s for s in all_symbols if _is_meme_symbol(s)][:3]),
            ",".join(
                [s for s in all_symbols if s not in majors_list and not _is_meme_symbol(s)][:3]
            ),
        )
    except Exception:
        # Logging must never break selection
        pass

    return selected[:limit]
