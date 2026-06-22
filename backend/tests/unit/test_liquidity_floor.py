"""
Liquidity floor regression — Chunk 1 of the regime-strategy-router rules layer
(decisions/2026-06-16__regime-strategy-router-design.md §9-A).

Promotes the previously SILENT $5M volume drop in PhemexAdapter.get_top_symbols to a loud,
configurable gate. These tests pin the pure partition helper (no live exchange needed):
  - the floor partitions correctly and is INCLUSIVE at the boundary,
  - it is configurable (lower floor admits more, higher admits fewer),
  - a missing/null/zero-volume ticker is fail-safe DROPPED (never admit unknown liquidity),
  - mass-conservation holds (kept + dropped == input).

Per CLAUDE.md §11 (no silent skips) + §16 Rubric 3 (mass-conservation in the function body).
"""
from backend.analysis.pair_selection import filter_illiquid_symbols
from backend.data.adapters.phemex import PhemexAdapter
from backend.shared.config.scanner_modes import MODES


def _tk(vol):
    return {"quoteVolume": vol}


def test_floor_partitions_and_is_boundary_inclusive():
    tickers = {"A": _tk(10_000_000), "B": _tk(1_000_000), "C": _tk(5_000_000), "D": _tk(0)}
    kept, dropped = PhemexAdapter.partition_by_volume_floor(
        ["A", "B", "C", "D"], tickers, 5_000_000
    )
    assert kept == ["A", "C"]          # >= floor; C at exactly 5M is admitted (inclusive)
    assert dropped == ["B", "D"]
    assert len(kept) + len(dropped) == 4   # mass conservation


def test_floor_is_configurable():
    tickers = {"A": _tk(2_000_000), "B": _tk(600_000)}
    kept_low, _ = PhemexAdapter.partition_by_volume_floor(["A", "B"], tickers, 1_000_000)
    assert kept_low == ["A"]           # lower floor admits more
    kept_high, dropped_high = PhemexAdapter.partition_by_volume_floor(["A", "B"], tickers, 5_000_000)
    assert kept_high == []             # higher floor admits fewer
    assert dropped_high == ["A", "B"]


def test_missing_or_null_ticker_is_failsafe_dropped():
    tickers = {"X": _tk(None), "Y": {}}      # null volume; empty ticker
    kept, dropped = PhemexAdapter.partition_by_volume_floor(
        ["X", "Y", "Z"], tickers, 5_000_000   # Z has no ticker at all
    )
    assert kept == []                  # unknown / null / zero liquidity is never admitted
    assert dropped == ["X", "Y", "Z"]


def test_empty_input_is_clean():
    kept, dropped = PhemexAdapter.partition_by_volume_floor([], {}, 5_000_000)
    assert kept == [] and dropped == []


# ---- filter_illiquid_symbols: the scan-stage gate covering auto + pinned paths ----

def test_filter_illiquid_partitions_and_conserves_mass():
    vols = {"BTC/USDT:USDT": 50_000_000, "DEAD/USDT:USDT": 100_000, "ETH/USDT:USDT": 5_000_000}
    kept, dropped = filter_illiquid_symbols(
        ["BTC/USDT:USDT", "DEAD/USDT:USDT", "ETH/USDT:USDT"], vols, 5_000_000.0, context="test"
    )
    assert kept == ["BTC/USDT:USDT", "ETH/USDT:USDT"]   # boundary inclusive (ETH at exactly 5M)
    assert dropped == ["DEAD/USDT:USDT"]
    assert len(kept) + len(dropped) == 3                # mass conservation


def test_filter_illiquid_pinned_unknown_symbol_failsafe_dropped():
    # A user-pinned symbol with no volume entry (couldn't be priced) is dropped, not trusted.
    kept, dropped = filter_illiquid_symbols(["PINNED/USDT:USDT"], {}, 5_000_000.0)
    assert kept == []
    assert dropped == ["PINNED/USDT:USDT"]


def test_every_mode_has_a_liquidity_floor():
    # The config home exists on every scanner mode (default $5M), so Chunk 2b can read it.
    for name, mode in MODES.items():
        assert mode.min_24h_volume_usdt >= 5_000_000.0, f"{name} missing/low liquidity floor"


# ---- perp-vs-spot volume resolution (the 2026-06-22 universe-collapse fix) ----

def test_quote_volume_uses_perp_not_spot():
    # Bot passes spot-style 'BNB/USDT' but trades the perp; must measure PERP liquidity,
    # not the thin spot ticker (the bug that collapsed the universe to majors-only).
    tickers = {
        "BNB/USDT": {"quoteVolume": 1_136_100.0},        # thin spot -> would wrongly fail $5M
        "BNB/USDT:USDT": {"quoteVolume": 28_299_403.0},  # liquid perp -> the real liquidity
    }
    assert PhemexAdapter._quote_volume_for("BNB/USDT", tickers) == 28_299_403.0


def test_quote_volume_perp_symbol_passthrough():
    tickers = {"SOL/USDT:USDT": {"quoteVolume": 55_000_000.0}}
    assert PhemexAdapter._quote_volume_for("SOL/USDT:USDT", tickers) == 55_000_000.0


def test_quote_volume_takes_max_of_spot_and_perp():
    tickers = {"BTC/USDT": {"quoteVolume": 277_000_000.0}, "BTC/USDT:USDT": {"quoteVolume": 276_000_000.0}}
    assert PhemexAdapter._quote_volume_for("BTC/USDT", tickers) == 277_000_000.0


def test_quote_volume_missing_is_zero():
    assert PhemexAdapter._quote_volume_for("NOPE/USDT", {}) == 0.0
