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

  1. stale_no_data     (symbol has failed no_data >= N consecutive cycles)
  2. stable_base       (BASE token is a stablecoin)
  3. non_perp          (leverage>1, non-spot, fails perp heuristic)
  4. bucket_excluded   (in fetched list but bucket toggle is OFF)
  5. limit_exhausted   (passed all filters, did not make the final cut)

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
from typing import Any, Deque, Dict, List, Optional, Protocol, Set, Tuple
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
#
# Phemex ticker convention notes (verified live 2026-05-26):
#   - Most majors are listed at the base/quote name as expected
#   - PEPE/USDT and SHIB/USDT exist as spot tickers (per-coin price tolerable
#     enough that Phemex did not apply the 1000x convention to them)
#   - BONK and FLOKI have NO base-name listing — only listed as 1000BONK/USDT
#     and 1000FLOKI/USDT (memecoin "1000x" convention: per-coin prices
#     ~$0.00000X bundled into 1000-coin contracts for sane notionals)
#   - Using "BONK/USDT" or "FLOKI/USDT" raises BadSymbol from the adapter,
#     which fires no_data every cycle. Calibrated on sessions e5e00ebc +
#     561744bc (May 2026) — 100% no_data failure rate before the rename.
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
    "1000BONK/USDT",
    "1000FLOKI/USDT",
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


# ---------------------------------------------------------------------------
# Stale-symbol auto-drop (no_data persistence guard)
# ---------------------------------------------------------------------------
#
# Calibrated on the May 2026 FLOKI/BONK observability finding: those two
# symbols failed `no_data` on 186/187 (99%) of cycles in session e61102fa
# while still appearing in every universe. The adapter consistently fails
# to return OHLCV for them — likely delisted, illiquid, or symbol-name
# mismatch — and the bot wastes ~9% of every cycle's gate evaluations on
# symbols that structurally cannot pass.
#
# Mechanism: any time the scanner sees a no_data rejection for a symbol,
# it calls `record_no_data_failure(symbol)`. When the counter for a
# symbol crosses `_NO_DATA_DROP_THRESHOLD`, the symbol is excluded from
# future universe selections (added to `dropped` with reason
# `stale_no_data`) until either (a) `record_no_data_success(symbol)` is
# called — meaning the data adapter finally returned OHLCV — or (b) the
# bot process restarts (counters are in-memory only).
#
# Threshold rationale: 10 consecutive failures ≈ 30 minutes at the
# observed ~3-min cycle cadence. Long enough to tolerate transient
# adapter hiccups; short enough that a genuinely-dead symbol gets caught
# quickly. Tune via _NO_DATA_DROP_THRESHOLD if the operator wants a
# different tolerance.
#
# Per CLAUDE.md §11 (loud failures): the FIRST time a symbol crosses the
# threshold, a single WARNING-level log emit surfaces the auto-drop so
# the operator sees it in the bot console. Subsequent failures by the
# same symbol stay silent — no log spam — but the snapshot keeps
# recording `stale_no_data` rejections per cycle for the universe audit.
_NO_DATA_DROP_THRESHOLD = 10

_no_data_counter_lock = Lock()
_consecutive_no_data_failures: Dict[str, int] = {}
_stale_dropped_logged: Set[str] = set()


def record_no_data_failure(symbol: str) -> int:
    """Increment the no_data failure counter for symbol. Returns new count.

    Called by the scanner when a symbol fails data fetch (reason_type
    'no_data'). When the count reaches _NO_DATA_DROP_THRESHOLD, the
    symbol will be auto-excluded from universe selection until success
    (`record_no_data_success`) OR session restart.

    Idempotent and thread-safe. The first time a symbol crosses the
    threshold, emits one WARNING log; subsequent failures stay silent.
    """
    with _no_data_counter_lock:
        new_count = _consecutive_no_data_failures.get(symbol, 0) + 1
        _consecutive_no_data_failures[symbol] = new_count
        if new_count == _NO_DATA_DROP_THRESHOLD and symbol not in _stale_dropped_logged:
            _stale_dropped_logged.add(symbol)
            # loguru uses {}-style format strings; stdlib %s/%d args are NOT
            # interpolated under loguru and would emit literal "%s" / "%d".
            logger.warning(
                "STALE_SYMBOL_AUTO_DROP: {} failed no_data {} consecutive cycles; "
                "excluded from universe selection until success OR session restart",
                symbol, new_count,
            )
        return new_count


def record_no_data_success(symbol: str) -> None:
    """Reset the no_data counter on a successful data fetch.

    Allows a symbol to recover if it transiently failed but data is back.
    If the symbol was previously auto-dropped (counter >= threshold),
    emits one INFO log noting the recovery.
    """
    with _no_data_counter_lock:
        prior = _consecutive_no_data_failures.pop(symbol, 0)
        if prior >= _NO_DATA_DROP_THRESHOLD:
            _stale_dropped_logged.discard(symbol)
            # loguru {}-style — stdlib %s/%d args would emit literal markers.
            logger.info(
                "STALE_SYMBOL_RECOVERED: {} data fetched successfully after {} failures; "
                "re-eligible for selection",
                symbol, prior,
            )


def is_symbol_stale(symbol: str) -> bool:
    """True if the symbol has failed no_data >= threshold consecutive cycles."""
    with _no_data_counter_lock:
        return _consecutive_no_data_failures.get(symbol, 0) >= _NO_DATA_DROP_THRESHOLD


def filter_stale_symbols(
    symbols: List[str], *, context: str = ""
) -> Tuple[List[str], List[str]]:
    """Partition a symbol list into (kept, dropped) by staleness.

    The auto-drop filter inside `_select_symbols_impl` only runs when the
    user-pinned `config.symbols` list is empty — when symbols are explicitly
    pinned (the common live-bot case), the orchestrator iterates the pinned
    list directly and the Stage-0 stale filter at line 405 never executes.
    Calibrated on session 84fd5c96 (May 2026): BONK and FLOKI failed
    no_data on 220/220 (100%) cycles in an 11-hour user-pinned session even
    though their counters had crossed _NO_DATA_DROP_THRESHOLD ~30 minutes in.

    Both bot services (paper + live) call this helper after building
    `scan_symbols` so the stale-drop applies regardless of which path
    populated the list. Per CLAUDE.md §11 (loud failures): emits one INFO
    log per scan when symbols are dropped; the per-symbol WARNING emit
    inside `record_no_data_failure` still fires on the original cross.

    Args:
        symbols: ordered list of trading pair symbols
        context: optional caller tag (e.g. "paper_trading_service") to make
                 the log line greppable

    Returns:
        (kept, dropped) — both ordered, complementary, no overlap. Mass-
        conservation: `len(kept) + len(dropped) == len(symbols)` always.
    """
    kept: List[str] = []
    dropped: List[str] = []
    for s in symbols:
        if is_symbol_stale(s):
            dropped.append(s)
        else:
            kept.append(s)

    # Mass-conservation runtime assertion (CLAUDE.md §16 Rubric 3).
    assert len(kept) + len(dropped) == len(symbols), (
        f"filter_stale_symbols mass-conservation violated: "
        f"kept={len(kept)} dropped={len(dropped)} input={len(symbols)}"
    )

    if dropped:
        tag = f"[{context}] " if context else ""
        # loguru uses {}-style formatting (NOT stdlib %s). Some other emits in
        # this module pass %s + positional args and produce un-interpolated
        # output under loguru; that's preexisting and out of scope for this commit.
        logger.info(
            "{}STALE_SYMBOL_SKIP: dropping {} symbol(s) this scan: {}",
            tag, len(dropped), dropped,
        )

    return kept, dropped


def filter_illiquid_symbols(
    symbols: List[str],
    volume_by_symbol: Dict[str, float],
    min_volume_usdt: float,
    *,
    context: str = "",
) -> Tuple[List[str], List[str]]:
    """Partition a symbol list into (kept, dropped) by 24h quote-volume floor.

    Companion to `filter_stale_symbols` for the LIQUIDITY rule (regime-strategy-router §9-A, the
    operator's #1 named rule: "don't trade illiquid pairs"). Both bot services call this after
    building `scan_symbols`, so the liquidity gate covers BOTH the auto-selected universe AND
    user-pinned symbols. Operator decision 2026-06-18: pinned symbols ARE liquidity-filtered — a
    pinned illiquid pair is still a capital risk (illiquid fills blow through stops on exit).

    A symbol with no volume entry (or null/zero) is treated as 0 volume -> dropped (fail-safe: never
    trade unknown liquidity). Per CLAUDE.md §11 (loud failures): one INFO log per scan on drop.

    Returns:
        (kept, dropped) — ordered, complementary, no overlap. Mass-conservation:
        len(kept) + len(dropped) == len(symbols) always.
    """
    kept: List[str] = []
    dropped: List[str] = []
    for s in symbols:
        vol = volume_by_symbol.get(s, 0.0) or 0.0
        (kept if vol >= min_volume_usdt else dropped).append(s)

    # Mass-conservation runtime assertion (CLAUDE.md §16 Rubric 3).
    assert len(kept) + len(dropped) == len(symbols), (
        f"filter_illiquid_symbols mass-conservation violated: "
        f"kept={len(kept)} dropped={len(dropped)} input={len(symbols)}"
    )

    if dropped:
        tag = f"[{context}] " if context else ""
        logger.info(
            "{}LOW_LIQUIDITY_SKIP: dropping {} symbol(s) below ${:,.0f} 24h volume this scan: {}",
            tag, len(dropped), min_volume_usdt, dropped,
        )

    return kept, dropped


def derive_account_aware_floor(
    balance: float,
    leverage: float,
    participation_rate: float,
    hard_min: float,
) -> float:
    """24h-quote-volume floor scaled to the account's market FOOTPRINT (Gate 1).

    The slippage / stop-blowthrough risk a liquidity floor guards against scales with POSITION
    NOTIONAL, not account capital — and leverage multiplies notional ("$1k at 20× IS a $20k position"
    to the order book). So the safe floor is the volume at which the position is a small slice of
    daily flow:

        floor = max(hard_min, (balance * leverage) / participation_rate)

    A $20 order can't move a $2M book, so a small/unleveraged account clears thinner pairs; a
    leveraged or large account is pinned to deeper books. The `hard_min` clamp ensures NO account
    ever trades a genuinely dead / wash-traded market (where a stop can't fill at any sane price) —
    for small accounts the hard-min governs. Direction-agnostic by design (admission is a universe
    filter, applied identically to long and short theses).

    Inputs are defensive: a non-positive balance/leverage/participation collapses the formula term to
    0 so the result is simply `hard_min` (fail-safe to the floor, never to "trade everything").

    See decisions/2026-06-28__account-aware-liquidity-admission.md (§15/§9-A baseline).
    """
    if balance > 0 and leverage > 0 and participation_rate > 0:
        scaled = (balance * leverage) / participation_rate
    else:
        scaled = 0.0
    return max(hard_min, scaled)


def filter_by_book_quality(
    symbols: List[str],
    book_by_symbol: Dict[str, Dict[str, float]],
    position_notional: float,
    *,
    max_spread_bps: float,
    min_depth_mult: float,
    context: str = "",
) -> Tuple[List[str], List[str]]:
    """Partition symbols into (kept, dropped) by ORDER-BOOK quality, not 24h volume.

    The depth-aware admission gate (decisions/2026-06-28__account-aware-liquidity-admission.md). 24h
    volume is a poor proxy for the depth that actually governs slippage/stop-blowthrough — NEAR ran
    $5M/24h with ~$2 at the touch. A symbol is KEPT iff BOTH hold:
      - spread_bps <= max_spread_bps           (book isn't blown out), AND
      - depth_usd  >= position_notional * min_depth_mult   (your order is a small slice of resting
                                                            near-touch liquidity, so a stop can fill).

    Fail-safe DROP semantics (consistent with §9-A "unknown liquidity -> drop"): a symbol absent from
    `book_by_symbol`, or carrying inf spread / 0 depth (the adapter's fetch-failure sentinel), is
    dropped. Direction-agnostic — `depth_usd` is already the MIN of both book sides.

    Mass-conservation (CLAUDE.md §16 Rubric 3): len(kept)+len(dropped)==len(symbols).
    """
    kept: List[str] = []
    dropped: List[str] = []
    needed_depth = max(0.0, position_notional) * max(0.0, min_depth_mult)
    for s in symbols:
        q = book_by_symbol.get(s)
        if not q:
            dropped.append(s)
            continue
        spread = q.get("spread_bps", float("inf"))
        depth = q.get("depth_usd", 0.0)
        if spread <= max_spread_bps and depth >= needed_depth:
            kept.append(s)
        else:
            dropped.append(s)

    assert len(kept) + len(dropped) == len(symbols), (
        f"filter_by_book_quality mass-conservation violated: "
        f"kept={len(kept)} dropped={len(dropped)} input={len(symbols)}"
    )

    if dropped:
        tag = f"[{context}] " if context else ""
        logger.info(
            "{}BOOK_QUALITY_DROP: {} symbol(s) failed spread<={:.0f}bps or depth>=${:,.0f} "
            "(position ${:,.0f} x {:g}): {}",
            tag, len(dropped), max_spread_bps, needed_depth, position_notional, min_depth_mult, dropped,
        )

    return kept, dropped


def get_stale_counters_snapshot() -> Dict[str, int]:
    """Return a shallow copy of the counter dict — for diagnostics + tests."""
    with _no_data_counter_lock:
        return dict(_consecutive_no_data_failures)


def clear_stale_counters() -> None:
    """Reset all no_data counters and the dropped-log set. Used by tests."""
    with _no_data_counter_lock:
        _consecutive_no_data_failures.clear()
        _stale_dropped_logged.clear()


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

    # Stage 0: stale-symbol auto-drop (no_data persistence guard).
    # Symbols that have failed data fetch >= _NO_DATA_DROP_THRESHOLD consecutive
    # cycles get excluded here — see record_no_data_failure / is_symbol_stale
    # for the counter logic. First-match precedence: a stale symbol is dropped
    # with reason 'stale_no_data' and never seen by stable_base/non_perp/etc.
    # downstream filters, so the rest of the waterfall reasoning is unchanged.
    after_stale: List[str] = []
    for s in all_symbols:
        if is_symbol_stale(s):
            dropped.append({"symbol": s, "reason": "stale_no_data"})
        else:
            after_stale.append(s)
    all_symbols = after_stale

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
