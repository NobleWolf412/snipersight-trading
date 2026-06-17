"""
Regression for the scan_completed regime telemetry gap (decisions/2026-06-16 §11.6 bug #4).

The global market regime was computed in the orchestrator (self.current_regime) but never
passed to create_scan_completed_event, so the scan_completed telemetry `regime_label`
logged None since 2026-06-13 — leaving no independent stream to validate the journal's
entry-regime stamp (bug #1) against. This pins that the event now carries the regime when
present, rounds the score, and OMITS the keys (no spurious value) when regime detection
failed — absence is meaningful for the post-run autopsy.

Per CLAUDE.md §11 (observability), §14 rubric 4 (present + absent pair).
"""
from __future__ import annotations

from backend.bot.telemetry.events import create_scan_completed_event, EventType


def _base() -> dict:
    return dict(
        run_id="R1",
        symbols_scanned=10,
        signals_generated=2,
        signals_rejected=8,
        duration_seconds=1.234,
    )


def test_regime_label_present_and_score_rounded_when_supplied():
    ev = create_scan_completed_event(**_base(), regime_label="down_normal", regime_score=71.42)
    assert ev.event_type == EventType.SCAN_COMPLETED
    assert ev.data["regime_label"] == "down_normal"
    assert ev.data["regime_score"] == 71.4  # rounded to 1dp
    # core counters intact
    assert ev.data["symbols_scanned"] == 10
    assert ev.data["signals_generated"] == 2


def test_regime_keys_omitted_when_detection_failed():
    """current_regime can be None (detection failed) — the event must NOT carry spurious
    regime keys; their ABSENCE distinguishes 'no regime' from a real label downstream."""
    ev = create_scan_completed_event(**_base())  # no regime args, as the None-safe call site sends
    assert "regime_label" not in ev.data
    assert "regime_score" not in ev.data
    assert ev.data["symbols_scanned"] == 10  # counters still present


def test_score_only_or_label_only_are_independent():
    """Each key is gated independently so a partial caller can't smuggle a None in."""
    ev = create_scan_completed_event(**_base(), regime_label="up_elevated")
    assert ev.data["regime_label"] == "up_elevated"
    assert "regime_score" not in ev.data
