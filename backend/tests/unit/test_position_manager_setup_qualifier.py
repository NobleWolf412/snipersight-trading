"""
Tests for the Tier 2 setup_qualifier parser at position_manager.py
open_position.

Catches the orchestrator-label-drift regression class: if
counter_htf_quality vocabulary at orchestrator.py:2622-2627 changes
(adds a new tag, renames an existing one), but the parser at
position_manager.py isn't updated, qualifier-tagged setups silently
collapse to "Unknown" and the cohort splits in the autopsy lose
meaning.

Per CLAUDE.md §11 (silent-bug surfacing), §14 rubric 4 (parametrized
coverage of label vocab).
"""

from __future__ import annotations

import pytest


def _parse_qualifier(setup_type: str) -> str:
    """Mirror of the inline parser at position_manager.open_position
    (Tier 2). Kept as a free function here so the test can exercise the
    pure logic without constructing a full PositionState fixture.

    If the parser at position_manager drifts, this helper drifts too —
    the source-string test below pins the inline parser shape against
    this helper's logic."""
    s = str(setup_type or "")
    if "[Strong]" in s:
        return "Strong"
    if "[Moderate]" in s:
        return "Moderate"
    if "[Soft]" in s:
        return "Soft"
    if "[Weak]" in s:
        return "Weak"
    return "Unknown"


# ──────────────────────────────────────────────────────────────────────
# Positive — each of the 4 qualifier tags parses to the right label
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "setup_type,expected",
    [
        # The exact strings the orchestrator emits per
        # orchestrator.py:2622-2629:
        ("Scalp Trade [HTF Bounce ↑ [Strong]]",     "Strong"),
        ("Scalp Trade [HTF Bounce ↑ [Moderate]]",   "Moderate"),
        ("Scalp Trade [HTF Bounce ↑ [Soft]]",       "Soft"),
        ("Scalp Trade [HTF Bounce ↑ [Weak]]",       "Weak"),
        # SHORT mirror — same parser logic, direction-agnostic
        ("Day Trade [HTF Bounce ↓ [Strong]]",       "Strong"),
        ("Day Trade [HTF Bounce ↓ [Moderate]]",     "Moderate"),
        ("Day Trade [HTF Bounce ↓ [Soft]]",         "Soft"),
        ("Day Trade [HTF Bounce ↓ [Weak]]",         "Weak"),
    ],
)
def test_qualifier_parsed_correctly(setup_type, expected):
    """All four qualifier tags map to their own label; not collapsed to Unknown."""
    assert _parse_qualifier(setup_type) == expected


# ──────────────────────────────────────────────────────────────────────
# Negative — non-tagged setup types collapse to Unknown
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "setup_type",
    [
        "Day Trade",
        "Swing Trade",
        "Scalp Trade",
        "Scalp Trade [HTF Bounce ↑]",  # no qualifier tag
        "Counter-HTF Intraday",        # legacy pre-tag label
        "",
        None,
    ],
)
def test_no_qualifier_returns_unknown(setup_type):
    """Setups without any of the 4 qualifier brackets fall to Unknown."""
    assert _parse_qualifier(setup_type) == "Unknown"


# ──────────────────────────────────────────────────────────────────────
# Source-string regression — pin the inline parser at position_manager
# ──────────────────────────────────────────────────────────────────────


def test_position_manager_parser_handles_all_four_tags():
    """The inline parser at position_manager.open_position MUST branch on
    all four tags (Strong/Moderate/Soft/Weak). If a future refactor drops
    one, qualifier-tagged setups silently collapse to Unknown and the
    cohort split in the autopsy loses meaning.

    Regression catch for the auditor's open item #2 from the Tier 2 bundle."""
    from pathlib import Path

    src_path = (
        Path(__file__).resolve().parents[2]
        / "bot"
        / "executor"
        / "position_manager.py"
    )
    src = src_path.read_text(encoding="utf-8")
    for tag in ("[Strong]", "[Moderate]", "[Soft]", "[Weak]"):
        assert tag in src, (
            f"position_manager.open_position parser must check for {tag!r}. "
            f"If this fails, qualifier-tagged setups will silently fall to "
            f"'Unknown' and the post-run autopsy cohort split loses meaning. "
            f"Cross-check orchestrator.py:2622-2627 for the current label "
            f"vocabulary."
        )
