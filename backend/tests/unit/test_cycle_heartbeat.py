"""
Tests for backend.engine.cycle_heartbeat.

Covers:
  - record / get_latest / recent / clear round-trip
  - Mass conservation assertion fires on breach
  - Mass conservation skipped for failed cycles (partial counts allowed)
  - Failed-cycle path records with failed=True + exception_class
  - Per-mode filtering (overwatch vs surgical separation)
  - Ring buffer eviction at capacity
  - Visibility counters increment correctly
"""

from __future__ import annotations

import pytest

from backend.engine import cycle_heartbeat as hb


def _ok_snapshot(**overrides):
    base = {
        "ts_start": 1_000.0,
        "ts_end": 1_001.5,
        "wall_ms": 1500,
        "run_id": "abcd1234",
        "mode": "stealth",
        "symbols_scanned": 10,
        "plans_emitted": 2,
        "total_rejected": 8,
        "signals_per_stage": {
            "low_confluence": 5,
            "no_data": 2,
            "errors": 1,
        },
        "bottleneck_stage": "low_confluence",
        "direction_stats": {"longs_generated": 1, "shorts_generated": 1},
        "regime": {"composite": "bull_trend", "score": 72.0},
        "next_cycle_eta_ts": 1_061.5,
        "failed": False,
        "exception_class": None,
    }
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def _reset_buffer():
    hb.clear()
    yield
    hb.clear()


def test_record_get_roundtrip():
    snap = _ok_snapshot()
    assert hb.record(snap) is True
    latest = hb.get_latest()
    assert latest is not None
    assert latest["run_id"] == "abcd1234"
    assert latest["plans_emitted"] == 2


def test_record_validation_missing_required_keys():
    bad = _ok_snapshot()
    del bad["run_id"]
    assert hb.record(bad) is False
    assert hb.stats()["record_errors_total"] == 1


def test_record_validation_non_dict_input():
    assert hb.record("not a dict") is False  # type: ignore[arg-type]
    assert hb.record(None) is False  # type: ignore[arg-type]
    assert hb.stats()["record_errors_total"] == 2


def test_mass_conservation_assertion_fires_on_breach():
    """If plans_emitted + per_stage != symbols_scanned, raise loudly."""
    bad = _ok_snapshot(plans_emitted=2, symbols_scanned=10, signals_per_stage={"no_data": 5})
    # 2 + 5 = 7 != 10  -> should raise
    with pytest.raises(AssertionError, match="mass conservation breach"):
        hb.record(bad)


def test_mass_conservation_holds_for_balanced_snapshot():
    snap = _ok_snapshot(
        plans_emitted=3,
        symbols_scanned=10,
        signals_per_stage={"low_confluence": 4, "no_data": 2, "errors": 1},
    )
    assert hb.record(snap) is True


def test_mass_conservation_skipped_for_failed_cycles():
    """Failed cycles emit partial counts; skipping the assertion is intentional."""
    failed_snap = _ok_snapshot(
        plans_emitted=0,
        symbols_scanned=10,
        signals_per_stage={},  # body never built it
        failed=True,
        exception_class="RuntimeError",
        bottleneck_stage=None,
    )
    assert hb.record(failed_snap) is True
    latest = hb.get_latest()
    assert latest["failed"] is True
    assert latest["exception_class"] == "RuntimeError"
    assert hb.stats()["failed_cycles_total"] == 1


def test_filter_by_mode_separates_baselines():
    """overwatch and surgical cycles must be filterable independently."""
    for i in range(3):
        hb.record(_ok_snapshot(run_id=f"ow{i}", mode="overwatch"))
    for i in range(2):
        hb.record(_ok_snapshot(run_id=f"sg{i}", mode="surgical"))

    overwatch_only = hb.filter_by_mode("overwatch")
    surgical_only = hb.filter_by_mode("surgical")
    assert len(overwatch_only) == 3
    assert len(surgical_only) == 2
    assert all(s["mode"] == "overwatch" for s in overwatch_only)
    assert all(s["mode"] == "surgical" for s in surgical_only)


def test_filter_by_mode_with_n_returns_latest():
    for i in range(5):
        hb.record(_ok_snapshot(run_id=f"x{i}", mode="overwatch"))
    last_two = hb.filter_by_mode("overwatch", n=2)
    assert len(last_two) == 2
    assert last_two[0]["run_id"] == "x3"
    assert last_two[1]["run_id"] == "x4"


def test_ring_buffer_eviction_at_capacity():
    cap = hb._HISTORY_SIZE  # type: ignore[attr-defined]
    for i in range(cap + 5):
        hb.record(_ok_snapshot(run_id=f"r{i}"))
    assert hb.history_size() == cap
    latest = hb.get_latest()
    assert latest["run_id"] == f"r{cap + 4}"


def test_recent_returns_shallow_copies():
    hb.record(_ok_snapshot())
    rows = hb.recent()
    rows[0]["mutated"] = "yes"
    rows2 = hb.recent()
    assert "mutated" not in rows2[0]


def test_stats_counters_track_records_and_failures():
    hb.record(_ok_snapshot())
    hb.record(_ok_snapshot(failed=True, plans_emitted=0, signals_per_stage={}))
    s = hb.stats()
    assert s["records_total"] == 2
    assert s["failed_cycles_total"] == 1
    assert s["buffer_size"] == 2
