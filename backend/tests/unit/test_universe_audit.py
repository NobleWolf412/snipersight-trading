"""
Tests for backend.diagnostics.universe_audit.

Confirms the audit:
  - Reports HEALTHY for a normal selection.
  - Surfaces selected ∩ dropped overlap as a failure.
  - Flags qualified=0/fetched>0 as a failure.
  - Flags non_perp > 90% under leverage as a failure.
  - Flags stable_base > 50% as a failure.
  - Flags unknown reasons as out-of-vocabulary.
  - Reports stale snapshots as a note (not a failure).
  - Reports has_snapshot=False cleanly when nothing has run.
"""

from __future__ import annotations

import pytest

from backend.analysis.pair_selection import clear_snapshot
from backend.diagnostics.universe_audit import audit_universe


@pytest.fixture(autouse=True)
def _reset_snapshot():
    clear_snapshot()
    yield
    clear_snapshot()


def _snap(selected, dropped, **overrides):
    base = {
        "ts": 1_700_000_000.0,
        "selected": selected,
        "dropped": dropped,
        "fetched": len(selected) + len(dropped),
        "limit": 50,
        "leverage": 1,
        "market_type": "swap",
        "toggles": {"majors": True, "altcoins": True, "meme_mode": False},
        "adapter": "DummyAdapter",
    }
    base.update(overrides)
    return base


def test_healthy_normal_selection():
    snap = _snap(
        selected=["BTC/USDT", "ETH/USDT"],
        dropped=[
            {"symbol": "USDC/USDT", "reason": "stable_base"},
            {"symbol": "FOO/USDT", "reason": "limit_exhausted"},
        ],
    )
    report = audit_universe(snap, now_ts=1_700_000_005.0)
    assert report.healthy
    assert report.qualified == 2
    assert report.drops_by_reason == {"stable_base": 1, "limit_exhausted": 1}


def test_failure_overlap_between_selected_and_dropped():
    snap = _snap(
        selected=["BTC/USDT", "ETH/USDT"],
        dropped=[{"symbol": "BTC/USDT", "reason": "limit_exhausted"}],
    )
    report = audit_universe(snap, now_ts=1_700_000_005.0)
    assert not report.healthy
    assert any("overlap" in f for f in report.failures)


def test_failure_qualified_zero_with_fetched_positive():
    snap = _snap(
        selected=[],
        dropped=[
            {"symbol": "USDC/USDT", "reason": "stable_base"},
            {"symbol": "USDT/USDT", "reason": "stable_base"},
        ],
        fetched=2,
    )
    report = audit_universe(snap, now_ts=1_700_000_005.0)
    assert not report.healthy
    assert any("qualified=0" in f for f in report.failures)


def test_high_non_perp_rate_surfaces_as_note_not_failure():
    """Until baselined, non_perp rate is a note — it does not fail the audit."""
    snap = _snap(
        selected=["BTC/USDT"],
        dropped=[{"symbol": f"X{i}/USDT", "reason": "non_perp"} for i in range(20)],
        fetched=21,
        leverage=10,
    )
    report = audit_universe(snap, now_ts=1_700_000_005.0)
    assert report.healthy  # NOT a failure — provable invariants are intact
    assert any("non_perp" in n and "provisional" in n for n in report.notes)


def test_high_stable_base_rate_surfaces_as_note_not_failure():
    snap = _snap(
        selected=["BTC/USDT"],
        dropped=[
            {"symbol": "USDC/USDT", "reason": "stable_base"},
            {"symbol": "FDUSD/USDT", "reason": "stable_base"},
            {"symbol": "TUSD/USDT", "reason": "stable_base"},
            {"symbol": "DAI/USDT", "reason": "stable_base"},
            {"symbol": "BUSD/USDT", "reason": "stable_base"},
            {"symbol": "USTC/USDT", "reason": "stable_base"},
        ],
        fetched=7,
    )
    report = audit_universe(snap, now_ts=1_700_000_005.0)
    assert report.healthy  # NOT a failure — needs baseline data first
    assert any("stable_base" in n and "provisional" in n for n in report.notes)


def test_failure_unknown_reasons_flagged():
    snap = _snap(
        selected=["BTC/USDT"],
        dropped=[{"symbol": "FOO/USDT", "reason": "made_up_reason"}],
    )
    report = audit_universe(snap, now_ts=1_700_000_005.0)
    assert not report.healthy
    assert "made_up_reason" in report.unknown_reasons


def test_stale_snapshot_emits_note_not_failure():
    snap = _snap(
        selected=["BTC/USDT"],
        dropped=[],
    )
    # 15 minutes old -> note threshold is 10 minutes
    report = audit_universe(snap, now_ts=snap["ts"] + 900.0)
    assert report.healthy  # still healthy, just stale
    assert any("stalled" in n or "old" in n for n in report.notes)


def test_no_snapshot_returns_clean_state():
    """Before any selection, audit must report has_snapshot=False without erroring."""
    report = audit_universe(snapshot=None, history=[])
    assert not report.has_snapshot
    assert report.healthy  # nothing to fail against
    assert "No snapshot" in str(report)


# ---------------------------------------------------------------------------
# Cross-cycle drift / trend
# ---------------------------------------------------------------------------


def test_cycle_trend_populated_from_history():
    """Audit report must include per-cycle rows from the history buffer."""
    history = [
        _snap(["BTC/USDT", "ETH/USDT"], [{"symbol": "USDC/USDT", "reason": "stable_base"}], ts=1_000.0),
        _snap(["BTC/USDT"], [{"symbol": "ETH/USDT", "reason": "limit_exhausted"}], ts=1_060.0),
        _snap(["BTC/USDT", "ETH/USDT"], [], ts=1_120.0),
    ]
    report = audit_universe(snapshot=history[-1], history=history, now_ts=1_125.0)
    assert report.history_size == 3
    assert len(report.cycle_trend) == 3
    # Oldest-first ordering
    assert report.cycle_trend[0].ts == 1_000.0
    assert report.cycle_trend[-1].ts == 1_120.0
    assert report.cycle_trend[0].drops_by_reason == {"stable_base": 1}
    assert report.cycle_trend[1].drops_by_reason == {"limit_exhausted": 1}


def test_cycle_trend_flags_fetched_collapse_as_failure():
    """If fetched count craters by >50% relative to prior-5 median, flag it."""
    history = []
    # 5 cycles at fetched ~30
    for i in range(5):
        history.append(_snap(
            ["BTC/USDT"] * 30,
            [],
            ts=1_000.0 + i * 60.0,
            fetched=30,
        ))
    # latest cycle: fetched plummets to 5
    history.append(_snap(["BTC/USDT"] * 5, [], ts=1_300.0, fetched=5))
    report = audit_universe(
        snapshot=history[-1], history=history, now_ts=1_305.0,
    )
    assert not report.healthy
    assert any("collapsed" in f for f in report.failures)


def test_cycle_trend_no_collapse_when_history_too_short():
    """Need >= 6 cycles before drift detection runs."""
    history = [_snap(["BTC/USDT"] * 30, [], ts=1_000.0, fetched=30)]
    history.append(_snap(["BTC/USDT"] * 5, [], ts=1_060.0, fetched=5))
    report = audit_universe(
        snapshot=history[-1], history=history, now_ts=1_065.0,
    )
    # Only 2 cycles in history — collapse heuristic should not fire.
    assert report.healthy
    assert not any("collapsed" in f for f in report.failures)


def test_cycle_trend_in_string_output():
    """The string formatter must render the cycle trend table."""
    history = [
        _snap(["BTC/USDT"], [{"symbol": "USDC/USDT", "reason": "stable_base"}], ts=1_000.0),
        _snap(["BTC/USDT", "ETH/USDT"], [], ts=1_060.0),
    ]
    report = audit_universe(snapshot=history[-1], history=history, now_ts=1_065.0)
    s = str(report)
    assert "Cycle trend" in s
    assert "fetched" in s
