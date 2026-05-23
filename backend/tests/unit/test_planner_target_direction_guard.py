"""
Tests for _guard_target_direction in risk_engine and its three call sites.

Bug context — May 2026 paper-trader R:R display showed `1 : -86.27` on an
open SCALP position. Trace:

  - Entry zone is built with `near_entry = OB.high - offset` for LONG
    (entry_engine.py:822) and `near_entry = OB.low + offset` for SHORT
    (entry_engine.py:1188). For LONG, `near_entry > far_entry`.
  - Paper limit orders fill at `near_entry` exactly (paper_trading_service.py
    :2165 + paper_executor.py:404).
  - Planner computed targets using `avg_entry = (near + far) / 2` for ALL
    operations including the validity guard (_guard_target_direction).
  - For LONG, `near_entry > avg_entry`. A target between avg_entry and
    near_entry PASSED the planner's guard (level > avg_entry) but was BELOW
    the actual fill (level < near_entry == entry_price).
  - The executor's stricter guard (position_manager._check_target_hit) then
    stripped these structurally-invalid targets in-place. If ALL targets
    were on the wrong side of the fill, the position opened with empty
    `targets` and could exit only via SL / stagnation / max_hours_open.
  - Paper serializer emitted tp1/tp2/tp_final = 0.0 (not None); frontend
    modal computed R:R = (0 − entry) / (entry − sl) ≈ −86.

Fix: the three `_guard_target_direction(targets, avg_entry, is_bullish)`
call sites in `_calculate_targets` (risk_engine.py:2266, 2310, 2371) now
pass `entry_zone.near_entry` instead, matching the executor's reference.

These tests cover:
  1. The helper's contract under the new reference (positive/negative pairs
     for both LONG and SHORT — symmetric per CLAUDE.md §10 #3).
  2. The fallback behavior when ALL targets are wrong-side.
  3. A source-level regression assertion that catches a future revert of
     any call site back to `avg_entry`.

Per CLAUDE.md §14 rubric 4 (negative tests paired with positive) and §16
rubric 12 (bull/bear symmetry).
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from backend.shared.models.planner import Target
from backend.strategy.planner.risk_engine import _guard_target_direction


def _t(level: float, label: str = "TP") -> Target:
    return Target(
        level=level,
        rationale="test",
        percentage=50.0,
        label=label,
        rr_ratio=1.5,
        weight=1.0,
    )


# ──────────────────────────────────────────────────────────────────────────────
# LONG — bull path
# ──────────────────────────────────────────────────────────────────────────────
#
# Setup: near_entry = 100.0 (top of OB minus offset, where a LONG fills),
#        avg_entry =  95.0 (midpoint of zone),
#        far_entry =  90.0 (bottom of OB plus offset).
#
# A target at 97.0 sits ABOVE avg_entry (passes the OLD guard) but BELOW
# near_entry (fails the NEW guard — and the executor's runtime check).


def test_long_target_above_near_entry_retained():
    """Positive — LONG TP genuinely above the worst-case fill is kept."""
    targets = [_t(101.0)]
    out = _guard_target_direction(targets, entry_ref=100.0, is_bullish=True)
    assert len(out) == 1
    assert out[0].level == 101.0


def test_long_target_between_avg_and_near_stripped():
    """Negative — LONG TP at 97.0 (above old avg_entry=95, below near=100)
    is stripped. This is the exact regression the fix targets."""
    targets = [_t(97.0), _t(105.0)]
    out = _guard_target_direction(targets, entry_ref=100.0, is_bullish=True)
    assert len(out) == 1
    assert out[0].level == 105.0


def test_long_all_targets_below_near_keeps_nearest_as_fallback():
    """When ALL LONG targets are below near_entry, helper keeps the nearest
    one as a fallback. The executor will strip it post-fill (documented
    residual — see _guard_target_direction docstring)."""
    targets = [_t(91.0), _t(97.0), _t(85.0)]
    out = _guard_target_direction(targets, entry_ref=100.0, is_bullish=True)
    assert len(out) == 1
    assert out[0].level == 97.0  # nearest to 100.0


# ──────────────────────────────────────────────────────────────────────────────
# SHORT — bear path (mirror)
# ──────────────────────────────────────────────────────────────────────────────
#
# Setup: near_entry = 100.0 (bottom of OB plus offset, where a SHORT fills),
#        avg_entry = 105.0,
#        far_entry = 110.0.
#
# A target at 103.0 sits BELOW avg_entry (passes the OLD guard) but ABOVE
# near_entry (fails the NEW guard — symmetric to the LONG case).


def test_short_target_below_near_entry_retained():
    """Positive — SHORT TP genuinely below the worst-case fill is kept."""
    targets = [_t(99.0)]
    out = _guard_target_direction(targets, entry_ref=100.0, is_bullish=False)
    assert len(out) == 1
    assert out[0].level == 99.0


def test_short_target_between_avg_and_near_stripped():
    """Negative mirror — SHORT TP at 103.0 (below old avg_entry=105, above
    near=100) is stripped."""
    targets = [_t(103.0), _t(95.0)]
    out = _guard_target_direction(targets, entry_ref=100.0, is_bullish=False)
    assert len(out) == 1
    assert out[0].level == 95.0


def test_short_all_targets_above_near_keeps_nearest_as_fallback():
    """Mirror of the LONG all-wrong-side fallback case."""
    targets = [_t(109.0), _t(103.0), _t(115.0)]
    out = _guard_target_direction(targets, entry_ref=100.0, is_bullish=False)
    assert len(out) == 1
    assert out[0].level == 103.0  # nearest to 100.0


# ──────────────────────────────────────────────────────────────────────────────
# Empty-input invariant
# ──────────────────────────────────────────────────────────────────────────────


def test_empty_targets_returns_empty():
    """Mass-conservation edge: empty in, empty out — no crash on null plan."""
    assert _guard_target_direction([], entry_ref=100.0, is_bullish=True) == []
    assert _guard_target_direction([], entry_ref=100.0, is_bullish=False) == []


# ──────────────────────────────────────────────────────────────────────────────
# Telemetry — fallback-wrong-side event must fire when residual leak hits
# ──────────────────────────────────────────────────────────────────────────────


def test_fallback_emits_wrong_side_telemetry():
    """When the all-wrong-side fallback fires, the helper must emit a
    structured WARNING_ISSUED telemetry event so the bot HUD activity log
    surfaces the case (the executor will strip the fallback target, and the
    position will exit only via SL/stagnation/max_hours_open).

    Patches the lazy `get_telemetry_logger` import. Verifies log_event was
    called with the correct event_type and key data fields. Regression catch
    for silent loss of observability on the residual fallback re-leak path."""
    mock_logger = MagicMock()
    with patch(
        "backend.bot.telemetry.logger.get_telemetry_logger",
        return_value=mock_logger,
    ):
        targets = [_t(91.0), _t(97.0)]
        out = _guard_target_direction(targets, entry_ref=100.0, is_bullish=True)

    assert len(out) == 1
    assert out[0].level == 97.0
    assert mock_logger.log_event.called, (
        "Fallback path should emit a WARNING_ISSUED telemetry event"
    )
    event = mock_logger.log_event.call_args[0][0]
    assert event.event_type.value == "warning_issued"
    assert event.data["kind"] == "target_direction_guard_fallback_wrong_side"
    assert event.data["direction"] == "LONG"
    assert event.data["entry_ref"] == 100.0
    assert event.data["kept_target_level"] == 97.0
    assert event.data["stripped_count"] == 1


def test_fallback_emits_wrong_side_telemetry_short():
    """SHORT mirror of the LONG telemetry-emit test. The telemetry block
    inside _guard_target_direction is direction-agnostic (it derives
    `direction` once from `is_bullish` and reuses it in both branches), so
    this test exists to satisfy §16 rubric 12 explicit bull/bear pairing
    for direction-aware payload fields."""
    mock_logger = MagicMock()
    with patch(
        "backend.bot.telemetry.logger.get_telemetry_logger",
        return_value=mock_logger,
    ):
        targets = [_t(109.0), _t(103.0)]
        out = _guard_target_direction(targets, entry_ref=100.0, is_bullish=False)

    assert len(out) == 1
    assert out[0].level == 103.0
    assert mock_logger.log_event.called
    event = mock_logger.log_event.call_args[0][0]
    assert event.event_type.value == "warning_issued"
    assert event.data["kind"] == "target_direction_guard_fallback_wrong_side"
    assert event.data["direction"] == "SHORT"
    assert event.data["entry_ref"] == 100.0
    assert event.data["kept_target_level"] == 103.0
    assert event.data["stripped_count"] == 1


def test_no_telemetry_when_targets_are_valid():
    """Negative pair — when targets are correctly on the right side of entry,
    NO telemetry event fires. The fallback-wrong-side event must be
    diagnostic-specific, not blanket-spammy on every guard invocation."""
    mock_logger = MagicMock()
    with patch(
        "backend.bot.telemetry.logger.get_telemetry_logger",
        return_value=mock_logger,
    ):
        targets = [_t(105.0), _t(110.0)]
        out = _guard_target_direction(targets, entry_ref=100.0, is_bullish=True)

    assert len(out) == 2
    assert not mock_logger.log_event.called, (
        "Telemetry should ONLY fire on the wrong-side fallback path"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Regression — catch a future revert of any call site to avg_entry
# ──────────────────────────────────────────────────────────────────────────────


def test_no_call_site_uses_avg_entry_in_risk_engine():
    """
    All three `_guard_target_direction(...)` call sites in risk_engine.py must
    use `entry_zone.near_entry` (or another non-avg_entry reference).

    Catches the exact regression the May 2026 fix introduced: switching the
    reference back to `avg_entry` would let targets between avg and near pass
    the planner but fail the executor's runtime check, producing positions
    with empty `targets`. The helper-level tests above don't catch that
    revert because they're at the wrong granularity; this string match does.
    """
    # __file__ is .../backend/tests/unit/test_...py → parents[2] is .../backend
    src_path = (
        Path(__file__).resolve().parents[2]
        / "strategy" / "planner" / "risk_engine.py"
    )
    assert src_path.exists(), f"risk_engine.py not found at {src_path}"
    src = src_path.read_text(encoding="utf-8")

    # Match `_guard_target_direction(<anything-non-comma>, avg_entry,`
    # across newlines so multi-line call formatting is also caught.
    pattern = re.compile(
        r"_guard_target_direction\(\s*[^,]+,\s*avg_entry\s*,",
        re.DOTALL,
    )
    matches = pattern.findall(src)
    assert not matches, (
        f"_guard_target_direction must use entry_zone.near_entry (worst-case "
        f"fill) as the reference, not avg_entry. Found {len(matches)} call(s) "
        f"still using avg_entry. See test docstring for the bug context."
    )
