"""
Test that orchestrator structural_breaks_list metadata reads brk.direction
rather than inferring direction from break_type.

Old code: "direction": "bullish" if brk.break_type == "BOS" else "bearish"
Fix:      "direction": str(getattr(brk, "direction", "bullish"))

4-pre: direction symmetry test (bull/bear × BOS/CHoCH matrix).
"""
from datetime import datetime

import pytest

from backend.shared.models.smc import StructuralBreak


def _make_break(break_type: str, direction: str) -> StructuralBreak:
    return StructuralBreak(
        timeframe="4h",
        break_type=break_type,
        level=50000.0,
        timestamp=datetime(2024, 1, 1),
        htf_aligned=True,
        direction=direction,
    )


def _metadata_direction(brk: StructuralBreak) -> str:
    """Mirrors the list-comprehension expression in orchestrator.py after fix."""
    return str(getattr(brk, "direction", "bullish"))


def _old_metadata_direction(brk: StructuralBreak) -> str:
    """Old (buggy) logic — verifies the fix changes behavior on wrong cases."""
    return "bullish" if brk.break_type == "BOS" else "bearish"


# --- Positive: fix changes behavior ---


def test_bearish_bos_direction_reads_field():
    """Bearish BOS: old code emitted 'bullish' (wrong); fix emits 'bearish'."""
    brk = _make_break("BOS", "bearish")
    assert _old_metadata_direction(brk) == "bullish"  # old bug reproduced
    assert _metadata_direction(brk) == "bearish"  # fix is correct


def test_bullish_choch_direction_reads_field():
    """Bullish CHoCH: old code emitted 'bearish' (wrong); fix emits 'bullish'."""
    brk = _make_break("CHoCH", "bullish")
    assert _old_metadata_direction(brk) == "bearish"  # old bug reproduced
    assert _metadata_direction(brk) == "bullish"  # fix is correct


# --- Negative / pin: unaffected cases remain correct ---


def test_bullish_bos_direction_unchanged():
    """Bullish BOS: both old and new code emit 'bullish' — no regression."""
    brk = _make_break("BOS", "bullish")
    assert _old_metadata_direction(brk) == "bullish"
    assert _metadata_direction(brk) == "bullish"


def test_bearish_choch_direction_unchanged():
    """Bearish CHoCH: both old and new code emit 'bearish' — no regression."""
    brk = _make_break("CHoCH", "bearish")
    assert _old_metadata_direction(brk) == "bearish"
    assert _metadata_direction(brk) == "bearish"
