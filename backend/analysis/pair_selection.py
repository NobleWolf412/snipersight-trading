"""Centralized pair selection and category filtering.

- Uses adapters' `get_top_symbols` for ranked candidates
- Robust stablecoin-base exclusion
- Leverage-aware perp detection (adapter-first, heuristic fallback)
- Majors, memes, alts bucket selection with curated majors semantics
- Safe fallback behavior when adapter data is unavailable
- Uses SymbolClassifier for accurate category detection (CoinGecko + heuristics)

Selection is direction-agnostic — it runs BEFORE scoring assigns long/short
to a candidate. There is no per-symbol id at this layer; the rollup
(selected vs dropped+reason) is captured per scan cycle in the snapshot
cache below and surfaced via /api/scanner/universe.

────────────────────────────────────────────────────────────────────────
Multi-reason precedence — first-match (waterfall)
────────────────────────────────────────────────────────────────────────
Filters run in this fixed order, and a symbol is recorded with the FIRST
reason it fails on. Subsequent filters never see symbols already dropped
by an earlier filter, so each symbol carries exactly ONE reason.

  1. stable_base       (BASE token is a stablecoin)
  2. non_perp          (leverage>1, non-spot, fails perp heuristic)
  3. bucket_excluded   (in fetched list but bucket toggle is OFF)
  4. limit_exhausted   (passed all filters, did not make the final cut)

Implication: fixing an earlier filter never "moves" drops between
reasons. If you tune `_is_stable_base`, the stable_base count changes
in isolation — non_perp / bucket_excluded / limit_exhausted counts for
the affected symbols stay zero (those symbols were never seen by the
later filters).

────────────────────────────────────────────────────────────────────────
Selection ordering (within selected list)
────────────────────────────────────────────────────────────────────────
`selected` preserves the adapter's ranking, modulated by bucket priority:
  majors bucket first, then meme bucket, then alt bucket
  (only for buckets whose toggle is ON). Backfill draws from `all_symbols`
in adapter order. Stable across cycles iff the adapter's ranking is
stable. The `dropped` list, for limit_exhausted entries, follows the
same adapter order.

────────────────────────────────────────────────────────────────────────
Restart semantics — in-memory only
────────────────────────────────────────────────────────────────────────
Both the latest snapshot and the recent-history ring buffer are
process-local. A restart clears them. Persistent universe history (if
ever needed) would land on disk via session_dir; that is out of scope
for the observability surfaces this module backs today.
"""

import time
from collections import deque
from threading import Lock
from typing import Any, Deque, Dict, List, Optional, Protocol, Tuple
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


# Default fallback — used only when exchange API is unreachable.
# Ordered by approximate 2025 liquidity/volume rank across majors, trending alts, and memes.
DEFAULT_FALLBACK = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "BNB/USDT",
    "ADA/USDT",
    "AVAX/USDT",
    "SUI/USDT",
    "TON/USDT",
    "NEAR/USDT",
    "APT/USDT",
    "ARB/USDT",
    "OP/USDT",
    "INJ/USDT",
    "LINK/USDT",
    "DOT/USDT",
    "DOGE/USDT",
    "SHIB/USDT",
    "PEPE/USDT",
    "WIF/USDT",
    "BONK/USDT",
    "FLOKI/USDT",
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


# ---------------------------------------------------------------------------
# Snapshot ring buffer (consumed by /api/scanner/universe + universe_audit)
# ---------------------------------------------------------------------------
#
# Mirrors the confluence/cache.py pattern: bounded deque keyed by arrival
# order. Latest snapshot is at the right; oldest evicted when full.
#
# Cycle history (last N) lets the audit detect drift across cycles —
# e.g. non_perp rate doubling from cycle to cycle, or fetched_count
# collapsing — instead of only looking at the current cycle in isolation.
#
# Snapshot shape:
#   {
#     "ts": float (epoch seconds),
#     "selected": List[str],
#     "dropped":  List[Dict["symbol", "reason"]],
#     "fetched":  int,
#     "limit":    int,
#     "leverage": int,
#     "market_type": Optional[str],
#     "toggles":  Dict["majors", "altcoins", "meme_mode"],
#     "adapter":  str,
#   }
#
# Threading: written from sync paths inside async scan loops, read from
# FastAPI handlers (which can land on threadpool workers). threading.Lock
# is correct — works from both contexts. Reads return shallow copies so
# the caller can mutate without racing the writer.
#
# Restart semantics: in-memory only. A restart drops history.
_HISTORY_SIZE = 50

_snapshot_lock = Lock()
_snapshot_history: Deque[Dict[str, Any]] = deque(maxlen=_HISTORY_SIZE)


def get_latest_snapshot() -> Optional[Dict[str, Any]]:
    """Return a shallow copy of the most recent snapshot, or None."""
    with _snapshot_lock:
        if not _snapshot_history:
            return None
        return dict(_snapshot_history[-1])


def get_snapshot_history(n: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Return the last `n` snapshots (oldest-first). If `n` is None, returns
    every snapshot in the buffer. Each entry is a shallow copy.
    """
    with _snapshot_lock:
        if not _snapshot_history:
            return []
        if n is None or n >= len(_snapshot_history):
            return [dict(s) for s in _snapshot_history]
        return [dict(s) for s in list(_snapshot_history)[-n:]]


def history_size() -> int:
    """Number of snapshots currently held."""
    with _snapshot_lock:
        return len(_snapshot_history)


def _write_snapshot(snap: Dict[str, Any]) -> None:
    with _snapshot_lock:
        _snapshot_history.append(snap)


def clear_snapshot() -> None:
    """Drop all cached snapshots. Used by tests."""
    with _snapshot_lock:
        _snapshot_history.clear()


def _select_symbols_impl(
    adapter: SupportsTopSymbols,
    limit: int,
    majors: bool,
    altcoins: bool,
    meme_mode: bool,
    leverage: Optional[int] = None,
    market_type: Optional[str] = None,
) -> Tuple[List[str], List[Dict[str, str]]]:
    """Internal: selection with drop tracking.

    Returns (selected, dropped). `dropped` is a list of dicts shaped
    {"symbol": str, "reason": str} where reason is one of:
      - "stable_base"      : base normalized as a stablecoin
      - "non_perp"         : leverage>1 / non-spot market and not a perp
      - "bucket_excluded"  : in fetched list but no enabled bucket would
                             include it (toggles excluded its category)
      - "limit_exhausted"  : passed all filters but selection cap was
                             reached before its turn
    """

    dropped: List[Dict[str, str]] = []

    try:
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

    fetched_count = len(all_symbols)
    # Snapshot the original fetched set up-front so the mass-conservation
    # assertion at the end can prove every input symbol is accounted for
    # — either in `selected` (after possible fallback substitution) or in
    # `dropped` with a reason. Future filters that silently swallow a
    # symbol will trip this assertion in tests instead of vanishing.
    _original_fetched: List[str] = list(all_symbols)

    # Stage 1: stablecoin-base exclusion (track drops)
    after_stable: List[str] = []
    for s in all_symbols:
        if _is_stable_base(s):
            dropped.append({"symbol": s, "reason": "stable_base"})
        else:
            after_stable.append(s)
    all_symbols = after_stable

    # Stage 2: leverage-aware perp filter (track drops)
    if (leverage or 1) > 1 and market_type != "spot":
        perp_symbols: List[str] = []
        for s in all_symbols:
            if _is_perp_with_fallback(adapter, s):
                perp_symbols.append(s)
            else:
                dropped.append({"symbol": s, "reason": "non_perp"})
        if perp_symbols:
            all_symbols = perp_symbols
        else:
            # Fallback perp-filter — these don't count as drops since the
            # filter found zero perps and we're substituting the entire pool.
            fallback_perps = [s for s in DEFAULT_FALLBACK if _is_perp_with_fallback(adapter, s)]
            all_symbols = fallback_perps if fallback_perps else DEFAULT_FALLBACK.copy()
            logger.debug(
                "leverage > 1 but adapter/perp heuristics returned empty; using fallback set"
            )

    # Curated majors when present; preserves ranking order.
    proportional = max(1, int(len(all_symbols) * 0.2))
    top_k = max(3, min(10, proportional))
    majors_present = [s for s in all_symbols[:top_k] if s in HARDCODED_MAJORS]
    if majors_present:
        majors_list = majors_present
    else:
        majors_list = [s for s in all_symbols[:top_k]]

    # Meme and alt derivations
    meme_set = {s for s in all_symbols if _is_meme_symbol(s)}
    memes_list = [s for s in all_symbols if s in meme_set]
    alts_list = [s for s in all_symbols if s not in majors_list and s not in meme_set]

    # Stage 3: bucket inclusion (track drops for symbols whose bucket is OFF)
    buckets: List[List[str]] = []
    enabled_buckets: List[str] = []
    if majors:
        buckets.append(majors_list)
        enabled_buckets.append("majors")
    if meme_mode:
        buckets.append(memes_list)
        enabled_buckets.append("memes")
    if altcoins:
        buckets.append(alts_list)
        enabled_buckets.append("alts")

    if not buckets:
        # No toggles → everything is eligible. No bucket exclusion drops.
        buckets = [all_symbols]
    else:
        # Compute the union of enabled buckets; anything in all_symbols
        # but not in the union is dropped as bucket_excluded.
        union: set = set()
        for b in buckets:
            union.update(b)
        for s in all_symbols:
            if s not in union:
                dropped.append({"symbol": s, "reason": "bucket_excluded"})

    # Stage 4: greedy fill, track limit_exhausted drops
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
        for s in all_symbols:
            if len(selected) >= limit:
                break
            if s not in selected:
                selected.append(s)

    # Anything that survived all filters but didn't make the final cut
    # is recorded as limit_exhausted. Compute by set difference.
    selected_set = set(selected)
    already_dropped = {d["symbol"] for d in dropped}
    for s in all_symbols:
        if s not in selected_set and s not in already_dropped:
            dropped.append({"symbol": s, "reason": "limit_exhausted"})

    selected = selected[:limit]

    # ── Mass-conservation invariant ──────────────────────────────────────
    # Every symbol from the original fetched pool must be accounted for:
    # either it survived to `selected` or it was dropped with a reason.
    # The non-perp-fallback path can substitute the entire pool with
    # DEFAULT_FALLBACK; in that case every original symbol is already
    # in `dropped` as non_perp before substitution, so this still holds.
    #
    # Future filters that silently swallow a symbol will trip this
    # assertion at the source instead of vanishing into a stats mismatch.
    _selected_set = set(selected)
    _dropped_set = {d["symbol"] for d in dropped}
    _unaccounted = [s for s in _original_fetched if s not in _selected_set and s not in _dropped_set]
    if _unaccounted:
        # Loud failure. Aborting selection is preferable to returning a
        # silently-incomplete universe to the scanner.
        raise AssertionError(
            f"pair_selection mass conservation breach: "
            f"{len(_unaccounted)} symbols vanished from fetched={len(_original_fetched)} "
            f"(selected={len(selected)}, dropped={len(dropped)}). "
            f"First few missing: {_unaccounted[:5]}"
        )

    # Selection summary log (unchanged behaviour, plus drop counts)
    try:
        fetched_cnt = fetched_count
        majors_cnt = len(majors_list) if majors else 0
        memes_cnt = len(memes_list) if meme_mode else 0
        alts_cnt = len(alts_list) if altcoins else 0
        # Per-reason breakdown for the log line
        reason_counts: Dict[str, int] = {}
        for d in dropped:
            reason_counts[d["reason"]] = reason_counts.get(d["reason"], 0) + 1
        logger.info(
            "selection adapter=%s limit=%s leverage=%s market=%s toggles majors=%s memes=%s alts=%s fetched=%s final=%s dropped=%s drop_reasons=%s buckets majors=%s memes=%s alts=%s examples majors=%s memes=%s alts=%s",
            adapter.__class__.__name__,
            limit,
            (leverage or 1),
            market_type,
            int(majors),
            int(meme_mode),
            int(altcoins),
            fetched_cnt,
            len(selected),
            len(dropped),
            reason_counts,
            majors_cnt,
            memes_cnt,
            alts_cnt,
            ",".join(majors_list[:3]),
            ",".join(memes_list[:3]),
            ",".join(alts_list[:3]),
        )
    except Exception:
        # Logging must never break selection
        pass

    # Persist the snapshot for /api/scanner/universe
    try:
        _write_snapshot({
            "ts": time.time(),
            "selected": list(selected),
            "dropped":  list(dropped),
            "fetched":  fetched_count,
            "limit":    limit,
            "leverage": int(leverage or 1),
            "market_type": market_type,
            "toggles":  {
                "majors": bool(majors),
                "altcoins": bool(altcoins),
                "meme_mode": bool(meme_mode),
            },
            "adapter":  adapter.__class__.__name__,
        })
    except Exception as e:
        # Snapshot write failure must not block selection.
        logger.warning(f"pair_selection snapshot write failed: {e}")

    return selected, dropped


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

    Backward-compatible signature — returns the selected list only.
    Drop reasons are still captured (and the snapshot cache is populated)
    for /api/scanner/universe; callers wanting the dropped list should
    use `select_symbols_with_drops` directly.
    """
    selected, _ = _select_symbols_impl(
        adapter, limit, majors, altcoins, meme_mode, leverage, market_type
    )
    return selected


def select_symbols_with_drops(
    adapter: SupportsTopSymbols,
    limit: int,
    majors: bool,
    altcoins: bool,
    meme_mode: bool,
    leverage: Optional[int] = None,
    market_type: Optional[str] = None,
) -> Tuple[List[str], List[Dict[str, str]]]:
    """Same selection logic, returns (selected, dropped_with_reasons).

    Used directly by /api/scanner/universe and by the universe audit
    diagnostic. Existing call sites can stay on `select_symbols`.
    """
    return _select_symbols_impl(
        adapter, limit, majors, altcoins, meme_mode, leverage, market_type
    )
