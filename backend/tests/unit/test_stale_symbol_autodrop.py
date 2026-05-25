"""
Tests for the stale-symbol auto-drop in pair_selection.

Per CLAUDE.md §11 (loud-failure surfacing) and §14 rubric 3 (mass conservation):
calibrated on the May 2026 FLOKI/BONK observability finding — those symbols
failed no_data on 186/187 (99%) of cycles for session e61102fa while still
being included in every universe. The bot wasted ~9% of every cycle's gate
evaluations on symbols that structurally couldn't pass.

The fix exposes a counter API on `pair_selection`:
  - record_no_data_failure(symbol) → increments counter; emits WARNING on first
    cross of _NO_DATA_DROP_THRESHOLD; subsequent failures stay silent.
  - record_no_data_success(symbol) → resets counter; emits INFO if symbol was
    previously dropped (recovery).
  - is_symbol_stale(symbol) → True iff counter >= threshold.
  - clear_stale_counters() → reset all state. For tests.

_select_symbols_impl gets a new Stage 0 filter that drops stale symbols with
reason "stale_no_data" before the existing waterfall (stable_base → non_perp →
bucket_excluded → limit_exhausted).

Coverage:
  - Counter increments correctly; threshold gate at exactly N=10
  - Negative: 9 consecutive failures does NOT mark as stale
  - Success resets counter (recovery path); emits INFO if previously dropped
  - Idempotent: re-calling success on a non-tracked symbol is safe
  - Threshold warning fires exactly once per symbol per session (not per-failure)
  - Stage 0 filter excludes stale symbols from selection with the right reason
  - Mass conservation preserved across the new Stage 0
  - Existing waterfall reasoning unchanged for non-stale symbols
"""

from __future__ import annotations

from typing import List
from unittest.mock import MagicMock

import pytest

from backend.analysis import pair_selection
from backend.analysis.pair_selection import (
    _NO_DATA_DROP_THRESHOLD,
    clear_stale_counters,
    get_stale_counters_snapshot,
    is_symbol_stale,
    record_no_data_failure,
    record_no_data_success,
    _select_symbols_impl,
)


@pytest.fixture(autouse=True)
def _reset_state():
    """Clear all module state before and after each test."""
    pair_selection.clear_snapshot()
    clear_stale_counters()
    yield
    pair_selection.clear_snapshot()
    clear_stale_counters()


# ──────────────────────────────────────────────────────────────────────────────
# Counter API — increment, threshold, recovery
# ──────────────────────────────────────────────────────────────────────────────


def test_threshold_value_is_ten():
    """Calibration constant: 10 consecutive failures ≈ 30min at 3min/cycle."""
    assert _NO_DATA_DROP_THRESHOLD == 10


def test_record_failure_increments_counter():
    """Each call increments by exactly 1; returns the new count."""
    assert record_no_data_failure("FLOKI/USDT") == 1
    assert record_no_data_failure("FLOKI/USDT") == 2
    assert record_no_data_failure("FLOKI/USDT") == 3
    assert get_stale_counters_snapshot()["FLOKI/USDT"] == 3


def test_record_failure_independent_per_symbol():
    """FLOKI failures don't leak into BONK counter."""
    for _ in range(5):
        record_no_data_failure("FLOKI/USDT")
    for _ in range(3):
        record_no_data_failure("BONK/USDT")
    snap = get_stale_counters_snapshot()
    assert snap == {"FLOKI/USDT": 5, "BONK/USDT": 3}


def test_is_symbol_stale_only_true_at_or_above_threshold():
    """Threshold gate is at exactly N=10. 9 = not stale, 10 = stale."""
    sym = "TEST/USDT"
    for i in range(_NO_DATA_DROP_THRESHOLD - 1):
        record_no_data_failure(sym)
    # 9 failures → NOT stale
    assert not is_symbol_stale(sym)
    # 10th failure → stale
    record_no_data_failure(sym)
    assert is_symbol_stale(sym)


def test_record_failure_emits_warning_only_on_first_threshold_cross(caplog):
    """First time a symbol crosses the threshold: one WARNING log. Subsequent
    failures by the same symbol: silent (no log spam)."""
    import logging
    # Loguru routes through std logging when propagation is on; tap stderr-level
    # caplog records since loguru's default sink doesn't go through caplog.
    # The behavior we care about is "exactly one log line per symbol session-wide",
    # so we check via the dropped-set tracking instead of caplog for portability.
    sym = "FLOKI/USDT"
    for _ in range(_NO_DATA_DROP_THRESHOLD - 1):
        record_no_data_failure(sym)
    # Just before the threshold cross — sym should NOT be in the logged set
    assert "FLOKI/USDT" not in pair_selection._stale_dropped_logged
    # The 10th failure crosses the threshold
    record_no_data_failure(sym)
    assert "FLOKI/USDT" in pair_selection._stale_dropped_logged
    # 20 more failures — set membership doesn't change (idempotent)
    for _ in range(20):
        record_no_data_failure(sym)
    assert pair_selection._stale_dropped_logged == {"FLOKI/USDT"}


# ──────────────────────────────────────────────────────────────────────────────
# Log-format interpolation — loguru {}-style vs stdlib %s
# ──────────────────────────────────────────────────────────────────────────────
#
# Regression catch for the May 2026 finding: the original emits used stdlib
# %s/%d positional-arg interpolation, which loguru does NOT process. Live
# logs emitted literal "%s failed no_data %d consecutive cycles" instead of
# "FLOKI/USDT failed no_data 10 consecutive cycles", breaking observability
# at the exact moment the auto-drop fires.


@pytest.fixture
def loguru_records():
    """Capture loguru records into a list. caplog bypasses loguru by default."""
    from loguru import logger as _loguru_logger
    records: List[str] = []
    sink_id = _loguru_logger.add(lambda msg: records.append(str(msg)), level="INFO")
    yield records
    _loguru_logger.remove(sink_id)


def test_auto_drop_warning_interpolates_symbol_and_count(loguru_records):
    """The WARNING fired on threshold cross must contain the actual symbol
    name and cycle count — not literal '%s' / '%d' artifacts."""
    for _ in range(_NO_DATA_DROP_THRESHOLD):
        record_no_data_failure("FLOKI/USDT")

    auto_drop_logs = [r for r in loguru_records if "STALE_SYMBOL_AUTO_DROP" in r]
    assert len(auto_drop_logs) == 1, f"expected 1 auto-drop log, saw {len(auto_drop_logs)}"
    msg = auto_drop_logs[0]
    # The fix matters here: loguru must have substituted {} placeholders.
    assert "FLOKI/USDT" in msg, f"symbol not interpolated: {msg!r}"
    assert "10" in msg, f"cycle count not interpolated: {msg!r}"
    # And specifically the un-interpolated markers must NOT appear.
    assert "%s" not in msg, f"stdlib %s leaked into output: {msg!r}"
    assert "%d" not in msg, f"stdlib %d leaked into output: {msg!r}"


def test_recovery_info_interpolates_symbol_and_prior_count(loguru_records):
    """The recovery INFO must contain the symbol name and prior-failure count
    in human-readable form, not literal markers."""
    # Push past threshold so the recovery emit fires
    for _ in range(_NO_DATA_DROP_THRESHOLD + 2):
        record_no_data_failure("BONK/USDT")
    # Clear the recorder of the auto-drop noise
    loguru_records.clear()

    record_no_data_success("BONK/USDT")

    recovery_logs = [r for r in loguru_records if "STALE_SYMBOL_RECOVERED" in r]
    assert len(recovery_logs) == 1, f"expected 1 recovery log, saw {len(recovery_logs)}"
    msg = recovery_logs[0]
    assert "BONK/USDT" in msg, f"symbol not interpolated: {msg!r}"
    assert "12" in msg, f"prior count not interpolated: {msg!r}"
    assert "%s" not in msg, f"stdlib %s leaked into output: {msg!r}"
    assert "%d" not in msg, f"stdlib %d leaked into output: {msg!r}"


def test_record_success_resets_counter():
    """Successful data fetch zeros the counter — symbol re-eligible immediately."""
    sym = "TEST/USDT"
    for _ in range(5):
        record_no_data_failure(sym)
    assert get_stale_counters_snapshot()[sym] == 5

    record_no_data_success(sym)
    assert sym not in get_stale_counters_snapshot()
    assert not is_symbol_stale(sym)


def test_record_success_on_dropped_symbol_clears_log_marker():
    """Recovery removes the symbol from the 'already-logged' set so a future
    drop emits a fresh WARNING."""
    sym = "FLOKI/USDT"
    for _ in range(_NO_DATA_DROP_THRESHOLD):
        record_no_data_failure(sym)
    assert sym in pair_selection._stale_dropped_logged

    record_no_data_success(sym)
    assert sym not in pair_selection._stale_dropped_logged


def test_record_success_idempotent_on_untracked_symbol():
    """Calling success on a symbol that was never failing is a no-op, not a crash."""
    record_no_data_success("NEVER_FAILED/USDT")
    assert get_stale_counters_snapshot() == {}


def test_threshold_recovery_cycle():
    """A symbol can be dropped, recover, get dropped again — full cycle works."""
    sym = "FLAKY/USDT"
    # First drop cycle
    for _ in range(_NO_DATA_DROP_THRESHOLD):
        record_no_data_failure(sym)
    assert is_symbol_stale(sym)

    # Recover
    record_no_data_success(sym)
    assert not is_symbol_stale(sym)

    # Second drop cycle
    for _ in range(_NO_DATA_DROP_THRESHOLD):
        record_no_data_failure(sym)
    assert is_symbol_stale(sym)


# ──────────────────────────────────────────────────────────────────────────────
# Stage 0 filter integration — _select_symbols_impl drops stale symbols
# ──────────────────────────────────────────────────────────────────────────────


def _make_mock_adapter(top_symbols: List[str]):
    """Mock adapter that returns the given symbols on get_top_symbols."""
    adapter = MagicMock()
    adapter.get_top_symbols.return_value = top_symbols
    adapter.is_perp.return_value = True  # default: everything is a perp
    adapter.__class__.__name__ = "MockAdapter"
    return adapter


def test_stage0_drops_stale_symbol_with_correct_reason():
    """Pre-mark FLOKI as stale; selection drops it with reason 'stale_no_data'."""
    # Force FLOKI into the stale state
    for _ in range(_NO_DATA_DROP_THRESHOLD):
        record_no_data_failure("FLOKI/USDT")
    assert is_symbol_stale("FLOKI/USDT")

    adapter = _make_mock_adapter(["BTC/USDT", "FLOKI/USDT", "ETH/USDT"])
    selected, dropped = _select_symbols_impl(
        adapter, limit=10, majors=True, altcoins=True, meme_mode=True, leverage=1
    )

    assert "FLOKI/USDT" not in selected, "stale symbol must NOT appear in selected"
    floki_drops = [d for d in dropped if d["symbol"] == "FLOKI/USDT"]
    assert len(floki_drops) == 1, f"FLOKI should appear exactly once in dropped, got {floki_drops}"
    assert floki_drops[0]["reason"] == "stale_no_data", (
        f"FLOKI drop reason should be 'stale_no_data', got {floki_drops[0]['reason']}"
    )


def test_stage0_non_stale_symbols_unaffected():
    """Symbols below the threshold (or with no counter) flow through normally."""
    # 9 failures on FLOKI — below threshold
    for _ in range(_NO_DATA_DROP_THRESHOLD - 1):
        record_no_data_failure("FLOKI/USDT")
    assert not is_symbol_stale("FLOKI/USDT")

    adapter = _make_mock_adapter(["BTC/USDT", "FLOKI/USDT", "ETH/USDT"])
    selected, dropped = _select_symbols_impl(
        adapter, limit=10, majors=True, altcoins=True, meme_mode=True, leverage=1
    )

    # FLOKI should NOT be dropped as stale (below threshold)
    stale_drops = [d for d in dropped if d["reason"] == "stale_no_data"]
    assert stale_drops == [], f"no symbols should be stale-dropped, got {stale_drops}"


def test_stage0_first_match_precedence():
    """Stale takes precedence over stable_base etc. — a symbol fails the FIRST
    filter it hits, never the later ones."""
    # USDC/USDT is both stable_base AND stale — should be dropped with 'stale_no_data'
    # (Stage 0) NOT 'stable_base' (Stage 1).
    for _ in range(_NO_DATA_DROP_THRESHOLD):
        record_no_data_failure("USDC/USDT")
    assert is_symbol_stale("USDC/USDT")

    adapter = _make_mock_adapter(["USDC/USDT", "BTC/USDT"])
    selected, dropped = _select_symbols_impl(
        adapter, limit=10, majors=True, altcoins=True, meme_mode=True, leverage=1
    )

    usdc_drops = [d for d in dropped if d["symbol"] == "USDC/USDT"]
    assert len(usdc_drops) == 1
    assert usdc_drops[0]["reason"] == "stale_no_data", (
        "stale_no_data must take first-match precedence over stable_base"
    )


def test_mass_conservation_preserved_across_stage0():
    """Every fetched symbol still accounted for after Stage 0 — the
    mass-conservation assertion at end of _select_symbols_impl must not trip."""
    for _ in range(_NO_DATA_DROP_THRESHOLD):
        record_no_data_failure("FLOKI/USDT")

    adapter = _make_mock_adapter(["BTC/USDT", "FLOKI/USDT", "BONK/USDT", "ETH/USDT", "SOL/USDT"])
    selected, dropped = _select_symbols_impl(
        adapter, limit=3, majors=True, altcoins=True, meme_mode=True, leverage=1
    )

    # Every input must be in selected OR dropped (waterfall)
    accounted = set(selected) | {d["symbol"] for d in dropped}
    fetched = {"BTC/USDT", "FLOKI/USDT", "BONK/USDT", "ETH/USDT", "SOL/USDT"}
    assert accounted >= fetched, (
        f"Mass conservation breach — missing: {fetched - accounted}"
    )


def test_recovery_makes_symbol_eligible_again():
    """After recovery via record_no_data_success, the symbol passes Stage 0."""
    # Drop FLOKI
    for _ in range(_NO_DATA_DROP_THRESHOLD):
        record_no_data_failure("FLOKI/USDT")
    assert is_symbol_stale("FLOKI/USDT")

    # First selection — FLOKI is dropped
    adapter = _make_mock_adapter(["BTC/USDT", "FLOKI/USDT"])
    _, dropped_1 = _select_symbols_impl(
        adapter, limit=10, majors=True, altcoins=True, meme_mode=True, leverage=1
    )
    assert any(d["symbol"] == "FLOKI/USDT" and d["reason"] == "stale_no_data" for d in dropped_1)

    # Recover
    record_no_data_success("FLOKI/USDT")

    # Second selection — FLOKI no longer stale-dropped
    _, dropped_2 = _select_symbols_impl(
        adapter, limit=10, majors=True, altcoins=True, meme_mode=True, leverage=1
    )
    stale_drops_2 = [d for d in dropped_2 if d["reason"] == "stale_no_data"]
    assert stale_drops_2 == [], "after recovery, FLOKI should not be stale-dropped"
