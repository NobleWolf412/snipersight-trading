"""
Tests for backend.diagnostics.cycle_heartbeat_audit.

Critical: each drift detector has BOTH a positive test (fires on real
anomaly) AND a negative test (does NOT fire on natural variance below
threshold). Positive-only tests cannot distinguish well-tuned from
trigger-happy; negative tests close that gap.
"""

from __future__ import annotations

import pytest

from backend.diagnostics.cycle_heartbeat_audit import audit_cycles


def _snap(**overrides):
    base = {
        "ts_start": 1_700_000_000.0,
        "ts_end": 1_700_000_001.5,
        "wall_ms": 1500,
        "run_id": "abcd1234",
        "mode": "stealth",
        "symbols_scanned": 10,
        "plans_emitted": 2,
        "total_rejected": 8,
        "signals_per_stage": {"low_confluence": 5, "no_data": 2, "errors": 1},
        "bottleneck_stage": "low_confluence",
        "direction_stats": {},
        "regime": None,
        "next_cycle_eta_ts": 1_700_000_061.5,
        "failed": False,
        "exception_class": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Empty / baseline
# ---------------------------------------------------------------------------


def test_empty_history_returns_clean_state():
    report = audit_cycles(snapshots=[])
    assert not report.has_history
    assert report.healthy
    assert "No cycles recorded" in str(report)


def test_single_healthy_cycle_passes():
    report = audit_cycles(snapshots=[_snap()])
    assert report.has_history
    assert report.healthy
    assert report.failed_cycles == 0
    assert report.healthy_cycles == 1


# ---------------------------------------------------------------------------
# Mass-conservation re-check (catches a regression that bypassed record())
# ---------------------------------------------------------------------------


def test_mass_conservation_breach_in_history_flagged():
    bad = _snap(plans_emitted=3, symbols_scanned=10, signals_per_stage={"no_data": 2})
    # 3 + 2 = 5 != 10
    report = audit_cycles(snapshots=[bad])
    assert not report.healthy
    assert any("mass conservation" in f for f in report.failures)


def test_failed_cycle_skipped_from_mass_conservation():
    failed = _snap(
        plans_emitted=0, symbols_scanned=10,
        signals_per_stage={}, failed=True, exception_class="RuntimeError",
        bottleneck_stage=None,
    )
    report = audit_cycles(snapshots=[failed])
    # Mass-conservation deliberately skipped for failed cycles.
    assert not any("mass conservation" in f for f in report.failures)
    # But the cycle still counts as failed.
    assert report.failed_cycles == 1


def test_failed_cycle_without_exception_class_flagged():
    bad = _snap(
        plans_emitted=0, symbols_scanned=10,
        signals_per_stage={}, failed=True, exception_class=None,
        bottleneck_stage=None,
    )
    report = audit_cycles(snapshots=[bad])
    assert not report.healthy
    assert any("missing exception_class" in f for f in report.failures)


# ---------------------------------------------------------------------------
# Drift detectors — POSITIVE tests
# ---------------------------------------------------------------------------


def test_plans_emitted_collapse_fires_degraded():
    # 5 cycles at 10 plans each; latest at 2 — > 50% drop vs median 10.
    snaps = [_snap(run_id=f"r{i}", plans_emitted=10, symbols_scanned=20,
                   signals_per_stage={"low_confluence": 10})
             for i in range(5)]
    snaps.append(_snap(run_id="r5", plans_emitted=2, symbols_scanned=20,
                       signals_per_stage={"low_confluence": 18}))
    report = audit_cycles(snapshots=snaps)
    assert not report.healthy
    assert any("plans_emitted collapsed" in f for f in report.failures)


def test_wall_ms_latency_regression_fires_degraded():
    # 5 cycles at 1000ms; latest at 3000ms — > 2× median 1000.
    snaps = [_snap(run_id=f"r{i}", wall_ms=1000) for i in range(5)]
    snaps.append(_snap(run_id="r5", wall_ms=3000))
    report = audit_cycles(snapshots=snaps)
    assert not report.healthy
    assert any("wall_ms doubled" in f for f in report.failures)


def test_bottleneck_shift_fires_note_not_failure():
    # 5 cycles bottleneck=low_confluence; latest=regime_alignment.
    snaps = [_snap(run_id=f"r{i}", bottleneck_stage="low_confluence")
             for i in range(5)]
    snaps.append(_snap(run_id="r5", bottleneck_stage="regime_alignment"))
    report = audit_cycles(snapshots=snaps)
    assert report.healthy  # NOTE only, not a failure
    assert any("bottleneck shifted" in n for n in report.notes)


def test_failure_ratio_over_window_flagged():
    # 6 healthy + 9 failed in last 15 = 60% — over 30% threshold.
    snaps = []
    for i in range(6):
        snaps.append(_snap(run_id=f"ok{i}"))
    for i in range(9):
        snaps.append(_snap(
            run_id=f"fail{i}", plans_emitted=0, symbols_scanned=10,
            signals_per_stage={}, failed=True, exception_class="RuntimeError",
            bottleneck_stage=None,
        ))
    report = audit_cycles(snapshots=snaps)
    assert not report.healthy
    assert any("failure ratio" in f for f in report.failures)


# ---------------------------------------------------------------------------
# Drift detectors — NEGATIVE tests (the critical proof of well-tuning)
# ---------------------------------------------------------------------------


def test_plans_emitted_natural_variance_does_not_fire():
    """6 cycles at 10±2 plans should NOT trigger DEGRADED."""
    plans = [10, 12, 8, 11, 9, 10]
    snaps = []
    for i, p in enumerate(plans):
        snaps.append(_snap(
            run_id=f"r{i}",
            plans_emitted=p,
            symbols_scanned=20,
            signals_per_stage={"low_confluence": 20 - p},
        ))
    report = audit_cycles(snapshots=snaps)
    assert report.healthy, f"unexpected failures: {report.failures}"
    assert not any("plans_emitted" in f for f in report.failures)


def test_wall_ms_natural_variance_does_not_fire():
    """6 cycles at 1.0–1.4s (1.4× max, below 2× threshold) should NOT fire."""
    walls = [1000, 1200, 1100, 1400, 1050, 1350]
    snaps = [_snap(run_id=f"r{i}", wall_ms=w) for i, w in enumerate(walls)]
    report = audit_cycles(snapshots=snaps)
    assert report.healthy, f"unexpected failures: {report.failures}"
    assert not any("wall_ms" in f for f in report.failures)


def test_bottleneck_stable_does_not_fire_note():
    """6 cycles all bottleneck=low_confluence should NOT emit a note."""
    snaps = [_snap(run_id=f"r{i}", bottleneck_stage="low_confluence")
             for i in range(6)]
    report = audit_cycles(snapshots=snaps)
    assert not any("bottleneck shifted" in n for n in report.notes)


def test_failure_ratio_below_threshold_does_not_fire():
    """4 failed in 15 = 27% — below 30% threshold, should stay healthy."""
    snaps = []
    for i in range(11):
        snaps.append(_snap(run_id=f"ok{i}"))
    for i in range(4):
        snaps.append(_snap(
            run_id=f"fail{i}", plans_emitted=0, symbols_scanned=10,
            signals_per_stage={}, failed=True, exception_class="RuntimeError",
            bottleneck_stage=None,
        ))
    report = audit_cycles(snapshots=snaps)
    # 27% < 30% threshold → no failure
    assert not any("failure ratio" in f for f in report.failures)


def test_short_history_no_drift_detection():
    """< 6 cycles = no drift detection runs (need baseline)."""
    snaps = [
        _snap(run_id="r0", plans_emitted=10, symbols_scanned=20,
              signals_per_stage={"low_confluence": 10}),
        _snap(run_id="r1", plans_emitted=1, symbols_scanned=20,
              signals_per_stage={"low_confluence": 19}),
    ]
    report = audit_cycles(snapshots=snaps)
    # Even with a 90% drop, history is too short for drift to fire.
    assert report.healthy


# ---------------------------------------------------------------------------
# Per-mode filtering
# ---------------------------------------------------------------------------


def test_per_mode_filter_isolates_baselines():
    """Mixing overwatch (slow) with surgical (fast) cycles in one trend
    invalidates wall_ms drift detection. Per-mode audit must isolate them."""
    # Overwatch cycles run slow but consistently
    overwatch = [_snap(run_id=f"ow{i}", mode="overwatch", wall_ms=5000)
                 for i in range(5)]
    overwatch.append(_snap(run_id="ow5", mode="overwatch", wall_ms=5200))

    # Surgical cycles run fast but consistently
    surgical = [_snap(run_id=f"sg{i}", mode="surgical", wall_ms=800)
                for i in range(5)]
    surgical.append(_snap(run_id="sg5", mode="surgical", wall_ms=900))

    # Filter to overwatch only — should be healthy
    report_ow = audit_cycles(snapshots=overwatch, mode="overwatch")
    assert report_ow.healthy, f"overwatch baselines should not flag: {report_ow.failures}"

    # Filter to surgical only — should be healthy
    report_sg = audit_cycles(snapshots=surgical, mode="surgical")
    assert report_sg.healthy

    # If we accidentally mix them with overwatch latest after surgical history,
    # wall_ms drift would scream. (Mixed mode = caller error; the audit's
    # mode_filter prevents this when used correctly.)


def test_mode_filter_recorded_in_report():
    snaps = [_snap(run_id=f"r{i}") for i in range(2)]
    report = audit_cycles(snapshots=snaps, mode="stealth")
    assert report.mode_filter == "stealth"


# ---------------------------------------------------------------------------
# Trend output rendering
# ---------------------------------------------------------------------------


def test_trend_table_in_string_output():
    snaps = [_snap(run_id="aa"), _snap(run_id="bb")]
    s = str(audit_cycles(snapshots=snaps))
    assert "Cycle trend" in s
    assert "aa" in s
    assert "bb" in s


def test_failed_cycle_marked_with_x():
    failed = _snap(
        run_id="ffff", plans_emitted=0, symbols_scanned=10,
        signals_per_stage={}, failed=True, exception_class="RuntimeError",
        bottleneck_stage=None,
    )
    s = str(audit_cycles(snapshots=[failed]))
    assert "✗" in s


def test_stalled_scan_emits_note():
    stalled = _snap(wall_ms=200_000, plans_emitted=0, symbols_scanned=20,
                    signals_per_stage={"errors": 20})
    report = audit_cycles(snapshots=[stalled])
    # Mass conservation holds (0 + 20 = 20), so the cycle is "valid"
    # but the stall heuristic should fire as a note.
    assert any("stalled" in n for n in report.notes)
