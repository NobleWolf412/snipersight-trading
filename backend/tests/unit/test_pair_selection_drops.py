"""
Drop-tracking tests for backend.analysis.pair_selection.

Each of the 4 documented drop reasons must fire correctly:
  - stable_base
  - non_perp
  - bucket_excluded
  - limit_exhausted

Plus: snapshot cache integrity, reason set is closed, and the legacy
select_symbols entry point continues to behave identically.
"""

from __future__ import annotations

from typing import List, Optional

import pytest

from backend.analysis.pair_selection import (
    DEFAULT_FALLBACK,
    clear_snapshot,
    get_latest_snapshot,
    get_snapshot_history,
    history_size,
    select_symbols,
    select_symbols_with_drops,
)


VALID_REASONS = {"stale_no_data", "stable_base", "non_perp", "bucket_excluded", "limit_exhausted"}


class DummyAdapter:
    """Adapter that returns a fixed symbol list and supports market_type kwarg."""

    def __init__(self, symbols: List[str], perps: Optional[set] = None):
        self._symbols = symbols
        self._perps = perps if perps is not None else set()

    def get_top_symbols(self, n: int = 20, quote_currency: str = "USDT", market_type=None):
        return self._symbols[:n]

    def is_perp(self, symbol: str) -> bool:
        return symbol in self._perps


@pytest.fixture(autouse=True)
def _reset_snapshot():
    clear_snapshot()
    yield
    clear_snapshot()


# ---------------------------------------------------------------------------
# Per-reason tests
# ---------------------------------------------------------------------------


def test_drop_reason_stable_base():
    """Stablecoin bases must be flagged stable_base, not pass through."""
    adapter = DummyAdapter([
        "BTC/USDT",
        "USDC/USDT",  # stable base
        "ETH/USDT",
        "FDUSD/USDT", # stable base
        "SOL/USDT",
    ])
    selected, dropped = select_symbols_with_drops(
        adapter, limit=10, majors=False, altcoins=False, meme_mode=False
    )

    stable_drops = [d for d in dropped if d["reason"] == "stable_base"]
    stable_symbols = {d["symbol"] for d in stable_drops}

    assert "USDC/USDT" in stable_symbols
    assert "FDUSD/USDT" in stable_symbols
    assert "BTC/USDT" not in stable_symbols
    assert "USDC/USDT" not in selected
    assert "FDUSD/USDT" not in selected


def test_drop_reason_non_perp():
    """When leverage>1 and market is not spot, non-perps are dropped as non_perp."""
    adapter = DummyAdapter(
        symbols=["BTC/USDT", "ETH/USDT", "FOO/USDT", "BAR/USDT"],
        perps={"BTC/USDT", "ETH/USDT"},  # only these two are perps
    )
    selected, dropped = select_symbols_with_drops(
        adapter, limit=10, majors=False, altcoins=False, meme_mode=False,
        leverage=10, market_type="swap",
    )

    non_perp_drops = {d["symbol"] for d in dropped if d["reason"] == "non_perp"}
    assert "FOO/USDT" in non_perp_drops
    assert "BAR/USDT" in non_perp_drops
    assert "BTC/USDT" not in non_perp_drops
    # Non-perps must not appear in the survivor list when leverage>1
    assert "FOO/USDT" not in selected
    assert "BAR/USDT" not in selected


def test_drop_reason_non_perp_skipped_when_spot():
    """Spot mode must not drop on non_perp regardless of leverage."""
    adapter = DummyAdapter(
        symbols=["BTC/USDT", "FOO/USDT"],
        perps={"BTC/USDT"},
    )
    _, dropped = select_symbols_with_drops(
        adapter, limit=10, majors=False, altcoins=False, meme_mode=False,
        leverage=10, market_type="spot",  # spot path bypasses perp filter
    )
    assert not any(d["reason"] == "non_perp" for d in dropped)


def test_drop_reason_bucket_excluded():
    """A symbol in a disabled bucket must be flagged bucket_excluded."""
    adapter = DummyAdapter([
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT",
        "DOGE/USDT", "SHIB/USDT", "PEPE/USDT",  # memes
        "FOO/USDT", "BAR/USDT", "BAZ/USDT",   # offline heuristic alts
    ])

    # Majors+memes ON, alts OFF -> alts should be bucket_excluded
    _, dropped = select_symbols_with_drops(
        adapter, limit=20, majors=True, altcoins=False, meme_mode=True,
    )
    excluded = {d["symbol"] for d in dropped if d["reason"] == "bucket_excluded"}
    assert excluded == {"FOO/USDT", "BAR/USDT", "BAZ/USDT"}


def test_drop_reason_limit_exhausted():
    """Symbols that pass all filters but don't make the cut are limit_exhausted."""
    adapter = DummyAdapter([
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT",
        "ADA/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT",
    ])
    selected, dropped = select_symbols_with_drops(
        adapter, limit=3, majors=True, altcoins=True, meme_mode=False,
    )
    # Only 3 should land in selected; the rest should be limit_exhausted.
    assert len(selected) == 3
    exhausted = {d["symbol"] for d in dropped if d["reason"] == "limit_exhausted"}
    assert len(exhausted) >= 1


# ---------------------------------------------------------------------------
# Reason vocabulary is closed
# ---------------------------------------------------------------------------


def test_all_reasons_in_known_set():
    """Every drop reason emitted must be in the documented vocabulary."""
    adapter = DummyAdapter(
        symbols=["BTC/USDT", "USDC/USDT", "FOO/USDT", "BAR/USDT", "DOGE/USDT"],
        perps={"BTC/USDT"},
    )
    _, dropped = select_symbols_with_drops(
        adapter, limit=2, majors=True, altcoins=False, meme_mode=False,
        leverage=5, market_type="swap",
    )
    seen_reasons = {d["reason"] for d in dropped}
    assert seen_reasons.issubset(VALID_REASONS), (
        f"Unknown reasons leaked: {seen_reasons - VALID_REASONS}"
    )


def test_no_symbol_appears_in_both_selected_and_dropped():
    """Selected and dropped sets must be disjoint."""
    adapter = DummyAdapter([
        "BTC/USDT", "ETH/USDT", "SOL/USDT",
        "ADA/USDT", "AVAX/USDT", "DOGE/USDT",
    ])
    selected, dropped = select_symbols_with_drops(
        adapter, limit=4, majors=True, altcoins=True, meme_mode=False,
    )
    selected_set = set(selected)
    dropped_set = {d["symbol"] for d in dropped}
    overlap = selected_set & dropped_set
    assert not overlap, f"Symbols leaked into both buckets: {overlap}"


# ---------------------------------------------------------------------------
# Snapshot cache
# ---------------------------------------------------------------------------


def test_snapshot_populated_by_select_symbols_with_drops():
    adapter = DummyAdapter(["BTC/USDT", "ETH/USDT"])
    select_symbols_with_drops(
        adapter, limit=5, majors=True, altcoins=False, meme_mode=False
    )
    snap = get_latest_snapshot()
    assert snap is not None
    assert snap["selected"] == ["BTC/USDT", "ETH/USDT"]
    assert snap["fetched"] == 2
    assert snap["limit"] == 5
    assert snap["toggles"]["majors"] is True
    assert isinstance(snap["ts"], float)


def test_snapshot_populated_by_legacy_select_symbols():
    """Legacy entrypoint must also populate the snapshot — otherwise existing
    callers (live_trading_service, paper_trading_service, scanner router)
    would never feed the universe endpoint."""
    adapter = DummyAdapter(["BTC/USDT", "ETH/USDT", "SOL/USDT"])
    out = select_symbols(
        adapter, limit=2, majors=True, altcoins=False, meme_mode=False
    )
    assert out  # legacy return shape preserved
    snap = get_latest_snapshot()
    assert snap is not None
    assert snap["selected"] == out
    assert "dropped" in snap


def test_snapshot_overwritten_on_subsequent_call():
    adapter_a = DummyAdapter(["BTC/USDT"])
    adapter_b = DummyAdapter(["ETH/USDT", "SOL/USDT"])
    select_symbols(adapter_a, limit=5, majors=True, altcoins=False, meme_mode=False)
    snap_a = get_latest_snapshot()
    select_symbols(adapter_b, limit=5, majors=True, altcoins=False, meme_mode=False)
    snap_b = get_latest_snapshot()
    assert snap_a is not None and snap_b is not None
    assert snap_b["selected"] != snap_a["selected"]
    assert snap_b["ts"] >= snap_a["ts"]


def test_snapshot_returns_copy_not_reference():
    """Mutating the returned snapshot dict must not pollute the cache."""
    adapter = DummyAdapter(["BTC/USDT"])
    select_symbols(adapter, limit=5, majors=True, altcoins=False, meme_mode=False)
    snap1 = get_latest_snapshot()
    snap1["selected"].append("HACKED/USDT")
    snap2 = get_latest_snapshot()
    assert snap2["selected"] == ["BTC/USDT"]
    # Neither nested nor outer mutations may propagate:
    snap1["new_field"] = "leak"
    assert "new_field" not in (snap2 or {})


# ---------------------------------------------------------------------------
# Legacy backward-compat surface
# ---------------------------------------------------------------------------


def test_legacy_select_symbols_returns_list_only():
    """select_symbols (legacy) returns a List[str], not a tuple."""
    adapter = DummyAdapter(["BTC/USDT", "ETH/USDT"])
    out = select_symbols(adapter, limit=5, majors=True, altcoins=False, meme_mode=False)
    assert isinstance(out, list)
    assert all(isinstance(s, str) for s in out)


def test_fallback_used_when_adapter_empty_does_not_blow_up_drops():
    adapter = DummyAdapter([])
    selected, dropped = select_symbols_with_drops(
        adapter, limit=5, majors=True, altcoins=False, meme_mode=False
    )
    assert selected
    # All survivors must be from the fallback set.
    assert all(s in DEFAULT_FALLBACK for s in selected)
    # Drops are allowed (limit_exhausted from fallback overflow), but reasons must be closed.
    assert {d["reason"] for d in dropped}.issubset(VALID_REASONS)


# ---------------------------------------------------------------------------
# Mass conservation
# ---------------------------------------------------------------------------


def test_mass_conservation_invariant_holds_normal_path():
    """Every original symbol must appear in selected ∪ dropped."""
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "USDC/USDT", "DOGE/USDT"]
    adapter = DummyAdapter(symbols)
    selected, dropped = select_symbols_with_drops(
        adapter, limit=2, majors=True, altcoins=True, meme_mode=False,
    )
    selected_set = set(selected)
    dropped_set = {d["symbol"] for d in dropped}
    for s in symbols:
        assert s in selected_set or s in dropped_set, f"{s} vanished"


def test_mass_conservation_invariant_holds_when_no_perps_survive():
    """Every original candidate remains a non_perp drop, with no substitution."""
    adapter = DummyAdapter(
        symbols=["FOO/USDT", "BAR/USDT", "BAZ/USDT"],  # none are perps
        perps=set(),
    )
    selected, dropped = select_symbols_with_drops(
        adapter, limit=3, majors=False, altcoins=True, meme_mode=False,
        leverage=10, market_type="swap",
    )
    dropped_set = {d["symbol"] for d in dropped}
    assert selected == []
    for s in ["FOO/USDT", "BAR/USDT", "BAZ/USDT"]:
        assert s in dropped_set


def test_mass_conservation_accounts_for_all_eligible_symbols():
    from backend.analysis.pair_selection import _select_symbols_impl as real_impl

    adapter = DummyAdapter(["BTC/USDT", "ETH/USDT"])
    selected, dropped = real_impl(adapter, 5, True, True, False)
    seen = set(selected) | {d["symbol"] for d in dropped}
    assert "ETH/USDT" in seen, "real impl should have accounted for ETH/USDT"


# ---------------------------------------------------------------------------
# Ring buffer / cycle history
# ---------------------------------------------------------------------------


def test_history_starts_empty():
    assert history_size() == 0
    assert get_snapshot_history() == []


def test_history_accumulates_across_cycles():
    adapter = DummyAdapter(["BTC/USDT"])
    for _ in range(3):
        select_symbols(adapter, limit=5, majors=True, altcoins=False, meme_mode=False)
    assert history_size() == 3
    history = get_snapshot_history()
    assert len(history) == 3
    # ts should be non-decreasing
    timestamps = [h["ts"] for h in history]
    assert timestamps == sorted(timestamps)


def test_history_evicts_oldest_at_capacity():
    from backend.analysis.pair_selection import _HISTORY_SIZE

    adapter = DummyAdapter(["BTC/USDT"])
    for i in range(_HISTORY_SIZE + 5):
        select_symbols(adapter, limit=1, majors=True, altcoins=False, meme_mode=False)
    assert history_size() == _HISTORY_SIZE


def test_history_returns_detached_copies():
    adapter = DummyAdapter(["BTC/USDT"])
    select_symbols(adapter, limit=5, majors=True, altcoins=False, meme_mode=False)
    history1 = get_snapshot_history()
    history1[0]["selected"].append("HACKED/USDT")
    history2 = get_snapshot_history()
    assert history2[0]["selected"] == ["BTC/USDT"]
    # Outer dict mutation should not propagate
    history1[0]["new_field"] = "leak"
    assert "new_field" not in history2[0]


def test_get_snapshot_history_with_n():
    adapter = DummyAdapter(["BTC/USDT"])
    for _ in range(5):
        select_symbols(adapter, limit=1, majors=True, altcoins=False, meme_mode=False)
    last_two = get_snapshot_history(n=2)
    assert len(last_two) == 2
    last_ten_capped = get_snapshot_history(n=10)
    assert len(last_ten_capped) == 5  # all available


def test_latest_snapshot_returns_last_element_of_history():
    adapter_a = DummyAdapter(["BTC/USDT"])
    adapter_b = DummyAdapter(["ETH/USDT", "SOL/USDT"])
    select_symbols(adapter_a, limit=1, majors=True, altcoins=False, meme_mode=False)
    select_symbols(adapter_b, limit=2, majors=True, altcoins=False, meme_mode=False)
    latest = get_latest_snapshot()
    assert latest is not None
    assert latest["adapter"] == "DummyAdapter"
    assert set(latest["selected"]) == {"ETH/USDT", "SOL/USDT"}
