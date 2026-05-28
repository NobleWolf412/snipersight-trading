"""
Tests for Orchestrator._apply_quality_override — quality-aware direction selection.

Per CLAUDE.md §10 (bull/bear symmetry), §16 rubric 4 (negative + positive paired),
§16 rubric 12 (bull/bear symmetric pairs on every direction-aware test).

Calibrated on 2026-05-27 DIRECTION-SHORT-CIRCUIT investigation:
  - INJ live data: 10 OBs (8B/2B raw count → LONG via _derive_pre_direction)
  - Per-direction aggregate quality: SHORT=230, LONG=146, delta=84pt
  - Old behavior: takes LONG, loses -$124 (INJ #27, biggest single loss of session 2f35590b)
  - New behavior: quality_delta=84 > threshold=20 AND opposite of count → flip to SHORT

The override block lives at orchestrator.py:1690 and is gated by
ScannerMode.enable_quality_override (STEALTH=True, others=False until calibrated).

Test strategy: mock `_aggregate_direction_quality` to return fixed scalar quality
scores per direction. This isolates the override decision logic from the scoring
helpers (which have their own tests). Each test asserts BOTH the returned
direction AND the tie_break string AND the override_meta dict shape.

Plus a static source-grep regression catch (mirrors test_stale_counter_main_process_accounting):
the orchestrator must contain the override block; if a refactor removes it the
silent bug returns.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Callable

import pytest

from backend.engine.orchestrator import Orchestrator


def _snap_with_quality(quality_long: float, quality_short: float, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Mock _aggregate_direction_quality so the override sees the specified scores.

    Returns a stub SMC snapshot — only used as a non-None sentinel since
    the patched aggregator ignores it."""

    def _mocked(snap, direction: str) -> float:
        if direction == "LONG":
            return quality_long
        if direction == "SHORT":
            return quality_short
        raise ValueError(f"unexpected direction {direction!r}")

    monkeypatch.setattr(Orchestrator, "_aggregate_direction_quality", staticmethod(_mocked))
    return SimpleNamespace()


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 1 — Δ > 20 and opposite → OVERRIDE (positive case, paired)
# ──────────────────────────────────────────────────────────────────────────────


def test_override_fires_when_quality_short_decisively_beats_count_long(monkeypatch):
    """INJ pattern: count picked LONG, quality 230S vs 146L → flip to SHORT."""
    snap = _snap_with_quality(quality_long=146.0, quality_short=230.0, monkeypatch=monkeypatch)
    direction, tie_break, meta = Orchestrator._apply_quality_override(
        snap, pre_dir="LONG", pre_dir_tie_break="bull_majority"
    )
    assert direction == "SHORT"
    assert tie_break == "quality_override"
    assert meta is not None
    assert meta["from"] == "LONG"
    assert meta["to"] == "SHORT"
    assert meta["delta"] == 84.0   # 230 - 146
    assert meta["threshold"] == 20.0
    assert meta["quality_long"] == 146.0
    assert meta["quality_short"] == 230.0


def test_override_fires_when_quality_long_decisively_beats_count_short(monkeypatch):
    """Mirror: count picked SHORT, quality 230L vs 146S → flip to LONG.
    §16 rubric 12 symmetry pair for the test above."""
    snap = _snap_with_quality(quality_long=230.0, quality_short=146.0, monkeypatch=monkeypatch)
    direction, tie_break, meta = Orchestrator._apply_quality_override(
        snap, pre_dir="SHORT", pre_dir_tie_break="bear_majority"
    )
    assert direction == "LONG"
    assert tie_break == "quality_override"
    assert meta is not None
    assert meta["from"] == "SHORT"
    assert meta["to"] == "LONG"
    assert meta["delta"] == -84.0  # 146 - 230 (sign indicates LONG)
    assert meta["quality_long"] == 230.0
    assert meta["quality_short"] == 146.0


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 2 — Δ just above threshold (=25), opposite → OVERRIDE
# ──────────────────────────────────────────────────────────────────────────────


def test_override_fires_at_delta_just_above_threshold_long_to_short(monkeypatch):
    """Δ = 25 > 20 → override LONG→SHORT."""
    snap = _snap_with_quality(quality_long=100.0, quality_short=125.0, monkeypatch=monkeypatch)
    direction, tie_break, meta = Orchestrator._apply_quality_override(
        snap, pre_dir="LONG", pre_dir_tie_break="bull_majority"
    )
    assert direction == "SHORT"
    assert tie_break == "quality_override"
    assert meta is not None


def test_override_fires_at_delta_just_above_threshold_short_to_long(monkeypatch):
    """Mirror — Δ = -25, opposite-of-count → override SHORT→LONG."""
    snap = _snap_with_quality(quality_long=125.0, quality_short=100.0, monkeypatch=monkeypatch)
    direction, tie_break, meta = Orchestrator._apply_quality_override(
        snap, pre_dir="SHORT", pre_dir_tie_break="bear_majority"
    )
    assert direction == "LONG"
    assert tie_break == "quality_override"
    assert meta is not None


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 3 — Δ below threshold (=19) → DEFER to count (negative case, paired)
# ──────────────────────────────────────────────────────────────────────────────


def test_no_override_when_delta_below_threshold_keep_long(monkeypatch):
    """Δ = 19 < 20 — quality disagrees but not decisively → defer to count."""
    snap = _snap_with_quality(quality_long=100.0, quality_short=119.0, monkeypatch=monkeypatch)
    direction, tie_break, meta = Orchestrator._apply_quality_override(
        snap, pre_dir="LONG", pre_dir_tie_break="bull_majority"
    )
    assert direction == "LONG"
    assert tie_break == "bull_majority"  # preserved
    assert meta is None


def test_no_override_when_delta_below_threshold_keep_short(monkeypatch):
    """Mirror — Δ = -19 < 20 in absolute → defer to count."""
    snap = _snap_with_quality(quality_long=119.0, quality_short=100.0, monkeypatch=monkeypatch)
    direction, tie_break, meta = Orchestrator._apply_quality_override(
        snap, pre_dir="SHORT", pre_dir_tie_break="bear_majority"
    )
    assert direction == "SHORT"
    assert tie_break == "bear_majority"
    assert meta is None


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 4 — Δ exactly at threshold (=20.0) → DEFER (boundary)
# Strict-greater-than: only Δ > 20 overrides. Δ == 20 falls through.
# ──────────────────────────────────────────────────────────────────────────────


def test_no_override_at_exact_threshold_boundary(monkeypatch):
    """Δ = exactly 20.0 → NO override (predicate is `abs(delta) > threshold`,
    strict greater-than). This boundary protects against floating-point drift
    on exactly-at-threshold cases."""
    snap = _snap_with_quality(quality_long=100.0, quality_short=120.0, monkeypatch=monkeypatch)
    direction, tie_break, meta = Orchestrator._apply_quality_override(
        snap, pre_dir="LONG", pre_dir_tie_break="bull_majority"
    )
    assert direction == "LONG"
    assert tie_break == "bull_majority"
    assert meta is None


def test_no_override_at_exact_threshold_boundary_mirror(monkeypatch):
    """Symmetric mirror — Δ = -20.0 → NO override."""
    snap = _snap_with_quality(quality_long=120.0, quality_short=100.0, monkeypatch=monkeypatch)
    direction, tie_break, meta = Orchestrator._apply_quality_override(
        snap, pre_dir="SHORT", pre_dir_tie_break="bear_majority"
    )
    assert direction == "SHORT"
    assert tie_break == "bear_majority"
    assert meta is None


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 5 — Δ > 20 but SAME direction as count → no-op
# ──────────────────────────────────────────────────────────────────────────────


def test_no_override_when_quality_agrees_with_count_long(monkeypatch):
    """Quality strongly LONG (Δ = -50) AND count was LONG → keep LONG, no override."""
    snap = _snap_with_quality(quality_long=200.0, quality_short=150.0, monkeypatch=monkeypatch)
    direction, tie_break, meta = Orchestrator._apply_quality_override(
        snap, pre_dir="LONG", pre_dir_tie_break="bull_majority"
    )
    assert direction == "LONG"
    assert tie_break == "bull_majority"
    assert meta is None


def test_no_override_when_quality_agrees_with_count_short(monkeypatch):
    """Mirror — quality strongly SHORT AND count was SHORT → keep SHORT."""
    snap = _snap_with_quality(quality_long=150.0, quality_short=200.0, monkeypatch=monkeypatch)
    direction, tie_break, meta = Orchestrator._apply_quality_override(
        snap, pre_dir="SHORT", pre_dir_tie_break="bear_majority"
    )
    assert direction == "SHORT"
    assert tie_break == "bear_majority"
    assert meta is None


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 6 — Zero quality both sides → no-op (defer to count)
# ──────────────────────────────────────────────────────────────────────────────


def test_no_override_when_both_qualities_zero(monkeypatch):
    """Empty structure: quality_long=0, quality_short=0 → Δ=0 < threshold,
    no override. Preserves count-based tie-break."""
    snap = _snap_with_quality(quality_long=0.0, quality_short=0.0, monkeypatch=monkeypatch)
    direction, tie_break, meta = Orchestrator._apply_quality_override(
        snap, pre_dir="LONG", pre_dir_tie_break="neutral_default_long"
    )
    assert direction == "LONG"
    assert tie_break == "neutral_default_long"
    assert meta is None


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 7 — INJ regression fixture (real production data shape)
# ──────────────────────────────────────────────────────────────────────────────


def test_inj_regression_fixture_flips_long_to_short(monkeypatch):
    """INJ live data 2026-05-27: per-direction aggregate quality is 230 SHORT
    vs 146 LONG. Count-based selector picked LONG (8B/2B raw majority).

    Under the override, this MUST flip to SHORT with tie_break=quality_override.
    If this regression test fails the DIRECTION-SHORT-CIRCUIT bug is back and
    the bot will lose -$124 on INJ #27-shaped trades again."""
    snap = _snap_with_quality(quality_long=146.0, quality_short=230.0, monkeypatch=monkeypatch)
    direction, tie_break, meta = Orchestrator._apply_quality_override(
        snap, pre_dir="LONG", pre_dir_tie_break="bull_majority"
    )
    assert direction == "SHORT", (
        "INJ pattern: count majority LONG with quality 230S vs 146L MUST override "
        "to SHORT. If this fails, the count-based DIRECTION-SHORT-CIRCUIT is back."
    )
    assert tie_break == "quality_override"
    assert meta["delta"] == 84.0


# ──────────────────────────────────────────────────────────────────────────────
# Static source-grep — regression catch for accidental removal
# ──────────────────────────────────────────────────────────────────────────────


def test_orchestrator_source_contains_override_block():
    """Static check: if a future refactor removes the override block from
    orchestrator.py, this test fails before the silent bug returns. Mirrors
    the pattern from test_stale_counter_main_process_accounting and
    test_breakdown_field_regression."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2] / "engine" / "orchestrator.py"
    ).read_text(encoding="utf-8")

    # The method must exist
    assert "def _apply_quality_override(" in src, (
        "_apply_quality_override static method removed from orchestrator.py"
    )
    # The aggregator must exist
    assert "def _aggregate_direction_quality(" in src, (
        "_aggregate_direction_quality static method removed from orchestrator.py"
    )
    # The call site must exist + must be wired through scanner_mode flag
    assert "_apply_quality_override(" in src
    assert "enable_quality_override" in src, (
        "ScannerMode.enable_quality_override gate removed from orchestrator.py"
    )
    # The mass-conservation assertion must remain
    assert "_paths_taken == 1" in src, (
        "Mass-conservation assertion for direction resolution paths is missing — "
        "§16 rubric 3 violation"
    )
    # The new tie_break enum value must be present
    assert '"quality_override"' in src


def test_scanner_mode_stealth_enables_quality_override():
    """The STEALTH ScannerMode config must keep enable_quality_override=True.
    Calibration data lives there; if a future tuner flips it off the
    DIRECTION-SHORT-CIRCUIT bug returns silently."""
    from backend.shared.config.scanner_modes import MODES

    stealth = MODES.get("stealth")  # MODES keys are lowercase
    assert stealth is not None, "stealth mode missing from scanner_modes.MODES"
    assert getattr(stealth, "enable_quality_override", None) is True, (
        "stealth must have enable_quality_override=True per the "
        "2026-05-27 calibration. If this is intentionally flipped off, "
        "update the decisions log and re-baseline."
    )


def test_other_modes_default_to_false():
    """Non-stealth modes must default to False until they have calibration data.
    Per §15: don't change live behavior without baseline data."""
    from backend.shared.config.scanner_modes import MODES

    for mode_name in ("overwatch", "strike", "surgical"):  # lowercase keys
        mode = MODES.get(mode_name)
        if mode is None:
            continue
        assert getattr(mode, "enable_quality_override", False) is False, (
            f"{mode_name}: enable_quality_override should default to False until "
            f"baseline calibration data exists for that mode."
        )


# ──────────────────────────────────────────────────────────────────────────────
# Audit-flagged interaction — flip-retry guard
# Both the §16 audit (Open Item #1) and adversarial review (Risk #3) caught
# this case: the conflict_density flip-retry at orchestrator.py:1765-1819
# would silently undo the quality override. Trace:
#   1. Override: count says LONG, quality says SHORT → tie_break=quality_override
#   2. conflict_density rejects SHORT (the 8 bullish OBs that count favored)
#   3. flip-retry tries LONG (the original count-pick the override rejected)
#   4. LONG passes → chosen_direction = LONG
#   5. Override silently neutralized; pre_dir_tie_break stays "quality_override"
#      in metadata but chosen_direction is the opposite — contradictory state.
# Fix: when tie_break == "quality_override" AND conflict_density rejects, do
# NOT enter flip-retry. The static source-grep test below catches future
# regressions of this guard.
# ──────────────────────────────────────────────────────────────────────────────


def test_orchestrator_skips_flip_retry_on_quality_override():
    """Static source-grep: the flip-retry block at orchestrator.py:1765-1819
    must be guarded so it does NOT execute when the upstream direction came
    via quality_override. Without this guard the override is silently undone.

    Required predicate shape: the conditional entering the flip-retry block
    must check `pre_dir_tie_break != 'quality_override'` (or equivalent).
    """
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2] / "engine" / "orchestrator.py"
    ).read_text(encoding="utf-8")

    # Find the flip-retry block — anchored by the "Conflict-density direction flip"
    # comment header
    anchor = src.find("Conflict-density direction flip")
    assert anchor > 0, "flip-retry block header not found in orchestrator.py"

    # Walk forward to find the `if _gate.gate_name == "conflict_density"` guard
    block = src[anchor:anchor + 3000]

    # The guard predicate must reference quality_override (we expect it to
    # appear in the conditional that enters the flip-retry)
    assert "quality_override" in block, (
        "flip-retry block must guard against quality_override tie_break. "
        "Without this guard, the override is silently undone whenever "
        "conflict_density rejects. Audit Open Item #1 (2026-05-27) caught "
        "this; this test prevents regression."
    )

    # And the guard must be wired via context.metadata.get("pre_dir_tie_break")
    # or equivalent — confirm the literal string reference
    assert '"quality_override"' in block, (
        "expected guard predicate to reference \"quality_override\" literal"
    )
