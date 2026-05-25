"""
Tests for filter_stale_symbols() — the helper that gives user-pinned
symbol lists the same auto-drop behavior that select_symbols() already
provides for auto-selected lists.

Background: paper_trading_service / live_trading_service take two paths
to build scan_symbols:
  1. config.symbols set     → list(config.symbols) (no select_symbols call)
  2. config.symbols unset   → select_symbols(...) → applies Stage-0 stale filter

Without filter_stale_symbols, path #1 never sees the stale-drop. Symbols
that have failed _NO_DATA_DROP_THRESHOLD consecutive cycles keep getting
scanned and wasting orchestrator budget. Per CLAUDE.md §11 (silent-bug
surfacing): this test class proves the symmetric behavior between both
paths and proves mass-conservation across the partition.

Calibrated on session 84fd5c96 (May 2026) — BONK/FLOKI scanned 220
times each despite hitting the threshold ~30 minutes into the session.
"""

from __future__ import annotations

from typing import List

import pytest
from loguru import logger as _loguru_logger

from backend.analysis.pair_selection import (
    _NO_DATA_DROP_THRESHOLD,
    clear_stale_counters,
    filter_stale_symbols,
    get_stale_counters_snapshot,
    is_symbol_stale,
    record_no_data_failure,
    record_no_data_success,
)


@pytest.fixture(autouse=True)
def _reset_counters():
    clear_stale_counters()
    yield
    clear_stale_counters()


@pytest.fixture
def loguru_records():
    """Capture loguru log records into a list. pair_selection uses loguru, not
    stdlib logging, so pytest's caplog doesn't see those emits — install a
    direct loguru sink instead."""
    records: List[str] = []
    sink_id = _loguru_logger.add(lambda msg: records.append(str(msg)), level="INFO")
    yield records
    _loguru_logger.remove(sink_id)


# ──────────────────────────────────────────────────────────────────────
# Behavior — kept/dropped partition
# ──────────────────────────────────────────────────────────────────────


def test_no_stale_symbols_returns_input_unchanged():
    """Clean list with no stale counters returns (symbols, [])."""
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    kept, dropped = filter_stale_symbols(symbols)
    assert kept == symbols
    assert dropped == []


def test_single_stale_symbol_is_dropped():
    """A symbol past threshold is moved to dropped, others stay in kept."""
    for _ in range(_NO_DATA_DROP_THRESHOLD):
        record_no_data_failure("BONK/USDT")
    assert is_symbol_stale("BONK/USDT")

    kept, dropped = filter_stale_symbols(["BTC/USDT", "BONK/USDT", "ETH/USDT"])
    assert kept == ["BTC/USDT", "ETH/USDT"]
    assert dropped == ["BONK/USDT"]


def test_multiple_stale_symbols_are_all_dropped():
    """Calibration mirror of the May 2026 BONK/FLOKI session."""
    for _ in range(_NO_DATA_DROP_THRESHOLD):
        record_no_data_failure("BONK/USDT")
        record_no_data_failure("FLOKI/USDT")

    kept, dropped = filter_stale_symbols(
        ["BTC/USDT", "BONK/USDT", "ETH/USDT", "FLOKI/USDT", "SOL/USDT"]
    )
    assert kept == ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    assert dropped == ["BONK/USDT", "FLOKI/USDT"]


def test_symbol_below_threshold_is_kept():
    """Counter at threshold-1 must NOT be considered stale (off-by-one guard)."""
    for _ in range(_NO_DATA_DROP_THRESHOLD - 1):
        record_no_data_failure("BONK/USDT")
    assert not is_symbol_stale("BONK/USDT")

    kept, dropped = filter_stale_symbols(["BONK/USDT", "BTC/USDT"])
    assert "BONK/USDT" in kept
    assert dropped == []


def test_recovered_symbol_returns_to_kept_after_success():
    """Once record_no_data_success fires, the symbol is no longer stale."""
    for _ in range(_NO_DATA_DROP_THRESHOLD):
        record_no_data_failure("BONK/USDT")
    assert is_symbol_stale("BONK/USDT")

    record_no_data_success("BONK/USDT")
    assert not is_symbol_stale("BONK/USDT")

    kept, dropped = filter_stale_symbols(["BONK/USDT"])
    assert kept == ["BONK/USDT"]
    assert dropped == []


def test_empty_input_returns_empty():
    kept, dropped = filter_stale_symbols([])
    assert kept == []
    assert dropped == []


def test_all_symbols_stale_returns_empty_kept():
    """Operator pinning a list of only-stale symbols → empty scan_symbols.

    The caller (paper/live trading service) is responsible for deciding what
    to do with an empty list. The helper itself doesn't try to substitute
    fallbacks — that's the caller's prerogative."""
    for _ in range(_NO_DATA_DROP_THRESHOLD):
        record_no_data_failure("BONK/USDT")
        record_no_data_failure("FLOKI/USDT")

    kept, dropped = filter_stale_symbols(["BONK/USDT", "FLOKI/USDT"])
    assert kept == []
    assert set(dropped) == {"BONK/USDT", "FLOKI/USDT"}


# ──────────────────────────────────────────────────────────────────────
# Mass-conservation — Rubric 3 (CLAUDE.md §16)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "stale_pre,input_syms",
    [
        ([], ["BTC/USDT"]),
        (["BONK/USDT"], ["BONK/USDT", "BTC/USDT"]),
        (["BONK/USDT", "FLOKI/USDT"], ["BTC/USDT", "BONK/USDT", "ETH/USDT", "FLOKI/USDT"]),
        # Symbol appears twice in input — both copies should be dropped or kept consistently
        (["BONK/USDT"], ["BONK/USDT", "BTC/USDT", "BONK/USDT"]),
    ],
)
def test_mass_conservation_kept_plus_dropped_equals_input(stale_pre, input_syms):
    for s in stale_pre:
        for _ in range(_NO_DATA_DROP_THRESHOLD):
            record_no_data_failure(s)

    kept, dropped = filter_stale_symbols(input_syms)
    assert len(kept) + len(dropped) == len(input_syms), (
        f"mass-conservation violated: kept={kept} dropped={dropped} input={input_syms}"
    )
    # No symbol appears in both partitions
    assert set(kept).isdisjoint(set(dropped)), "kept/dropped must be disjoint"


# ──────────────────────────────────────────────────────────────────────
# Loud-failure observability — INFO log fires when dropping (CLAUDE.md §11)
# ──────────────────────────────────────────────────────────────────────


def test_drop_emits_info_log_with_context(loguru_records):
    """The drop event must emit one INFO log per scan, tagged with caller context."""
    for _ in range(_NO_DATA_DROP_THRESHOLD):
        record_no_data_failure("BONK/USDT")

    filter_stale_symbols(["BTC/USDT", "BONK/USDT"], context="paper_trading_service")

    drop_logs = [r for r in loguru_records if "STALE_SYMBOL_SKIP" in r]
    assert len(drop_logs) == 1, f"expected 1 drop log, saw {len(drop_logs)}: {loguru_records}"
    assert "[paper_trading_service]" in drop_logs[0]
    assert "BONK/USDT" in drop_logs[0]


def test_no_drop_emits_no_log(loguru_records):
    """Clean lists must not log spam — symmetry to the drop-emits-log test."""
    filter_stale_symbols(["BTC/USDT", "ETH/USDT"], context="paper_trading_service")

    drop_logs = [r for r in loguru_records if "STALE_SYMBOL_SKIP" in r]
    assert drop_logs == []


# ──────────────────────────────────────────────────────────────────────
# Integration — the counter-and-helper round-trip
# ──────────────────────────────────────────────────────────────────────


def test_threshold_crossing_makes_symbol_drop_immediately():
    """The exact cycle that crosses _NO_DATA_DROP_THRESHOLD is when filter
    starts dropping the symbol — no off-by-one window."""
    # Cycles 1..threshold-1 → kept
    for i in range(_NO_DATA_DROP_THRESHOLD - 1):
        record_no_data_failure("BONK/USDT")
        kept, dropped = filter_stale_symbols(["BONK/USDT"])
        assert kept == ["BONK/USDT"], f"cycle {i+1}: dropped too early"
        assert dropped == []

    # Cycle == threshold → starts dropping
    record_no_data_failure("BONK/USDT")
    kept, dropped = filter_stale_symbols(["BONK/USDT"])
    assert kept == []
    assert dropped == ["BONK/USDT"]


def test_idempotent_across_repeated_calls():
    """Calling filter_stale_symbols multiple times in a row returns identical
    partitions — the helper itself does not mutate counter state."""
    for _ in range(_NO_DATA_DROP_THRESHOLD):
        record_no_data_failure("BONK/USDT")
    snap_before = get_stale_counters_snapshot()

    inputs = ["BTC/USDT", "BONK/USDT", "ETH/USDT"]
    res_a = filter_stale_symbols(inputs)
    res_b = filter_stale_symbols(inputs)
    res_c = filter_stale_symbols(inputs)
    assert res_a == res_b == res_c

    # And the counter snapshot is unchanged — filter is read-only on the counter state
    assert get_stale_counters_snapshot() == snap_before
