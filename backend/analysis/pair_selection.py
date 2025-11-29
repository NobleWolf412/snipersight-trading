"""Centralized pair selection and category filtering.

Uses existing exchange adapters' `get_top_symbols` to fetch USDT perp symbols,
then applies category toggles (majors, altcoins, meme_mode). Falls back to a
default list when adapter returns no data or filtering yields nothing.
"""
from typing import List, Protocol


class SupportsTopSymbols(Protocol):
    def get_top_symbols(self, n: int = 20, quote_currency: str = "USDT") -> List[str]:
        ...
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


def _unique_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for s in items:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _is_meme_symbol(symbol: str) -> bool:
    """Heuristic meme classification based on symbol token names.

    Avoids hardcoded full sets while catching common meme tokens.
    """
    name = symbol.split("/")[0].upper()
    MEME_HINTS = (
        "DOGE",
        "SHIB",
        "PEPE",
        "BONK",
        "FLOKI",
        "WIF",
        "TURBO",
        "MEME",
        "SATS",
    )
    return any(hint in name for hint in MEME_HINTS)


def select_symbols(
    adapter: SupportsTopSymbols,
    limit: int,
    majors: bool,
    altcoins: bool,
    meme_mode: bool,
    leverage: int | None = None,
) -> List[str]:
    """Resolve final symbol list based on adapter data and category toggles.

    - Oversamples via adapter (3x limit capped at 50)
    - Applies category filters
    - Falls back to all symbols or default list when needed
    - Truncates to `limit`
    """

    try:
        all_symbols = adapter.get_top_symbols(n=min(limit * 3, 50), quote_currency="USDT")
    except Exception:
        all_symbols = []

    if not all_symbols:
        all_symbols = DEFAULT_FALLBACK.copy()

    # Exclude stablecoin bases from consideration
    STABLES = {"USDT", "USDC", "BUSD", "USD", "DAI", "TUSD", "FDUSD", "UST"}
    def _is_stable(symbol: str) -> bool:
        base = symbol.split("/")[0].upper()
        return base in STABLES

    all_symbols = [s for s in all_symbols if not _is_stable(s)]

    # If leverage is requested (>1), prefer/require perp/marginable symbols
    def _is_perp(symbol: str) -> bool:
        try:
            # Adapters that implement is_perp
            return bool(getattr(adapter, "is_perp")(symbol))  # type: ignore[attr-defined]
        except Exception:
            # Heuristics: OKX uses ":USDT" suffix for swaps; most adapters list perps in top symbols
            return ":USDT" in symbol or symbol.endswith("/USDT")

    if (leverage or 1) > 1:
        perp_symbols = [s for s in all_symbols if _is_perp(s)]
        # Require perp when leverage > 1; if empty, try fallback perp-filter
        if perp_symbols:
            all_symbols = perp_symbols
        else:
            fallback_perps = [s for s in DEFAULT_FALLBACK if _is_perp(s)]
            all_symbols = fallback_perps if fallback_perps else DEFAULT_FALLBACK.copy()

    # Determine majors dynamically by top-by-volume slice (rank order retained)
    # Size majors slice proportionally (≈20% of list), bounded [3..10]
    proportional = max(1, int(len(all_symbols) * 0.2))
    top_k = max(3, min(10, proportional))
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

    return selected[:limit]
