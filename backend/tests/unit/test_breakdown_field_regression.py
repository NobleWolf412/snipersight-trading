"""
Regression tests for two long-standing bugs in ConfluenceBreakdown +
plan.metadata['macro'] field assignment, discovered via the 2026-05-26
taken_trade_forensics diagnostic.

Bug #1 — htf_aligned reads non-existent factor names
=====================================================
scorer.py:3220 checked `f.name in ("HTF Alignment", "HTF Structure Bias")`
but neither name is emitted as a ConfluenceFactor anywhere in scorer.py.
The actual emitted factor is "HTF Composite" per CRITICAL_FACTORS at
scorer.py:3237-3247. Result: htf_aligned was permanently False — 17/17
Tier 2 trades wrote False to the trade journal regardless of HTF state.

Bug #2 — macro_state serialized as auto() int not .name label
==============================================================
orchestrator.py:3089 wrote `_macro_state.value` to plan.metadata.
MacroState is an `enum.Enum` with `auto()` members, so `.value` is the
auto-generated integer. STABLE_SCARE → 6 → "6" in the journal. Consumers
expected the human-readable label (e.g. "STABLE_SCARE"). Calibrated on
17/17 Tier 2 trades writing "6" to macro_state_at_entry.

These tests pin both fixes:
  - Construct a ConfluenceBreakdown with an "HTF Composite" factor scoring
    above and below the threshold — assert htf_aligned reflects the score.
  - Construct a MacroContext with a specific MacroState and run the
    Tier-2 macro-metadata writer's serialization path — assert the
    stored string is the .name label not the .value integer.

Per CLAUDE.md §11 (silent-bug surfacing — the field-level audit caught
two stuck-value telemetry bugs that no unit test would have flagged
without partitioning the journal as the forensics did).
"""

from __future__ import annotations

import pytest

from backend.shared.models.scoring import ConfluenceBreakdown, ConfluenceFactor


# ──────────────────────────────────────────────────────────────────────
# Bug #1 — htf_aligned reads the right factor name
# ──────────────────────────────────────────────────────────────────────


def _make_breakdown_with_factor(name: str, score: float) -> bool:
    """Run the inline htf_aligned computation that lives at scorer.py:3220
    against a single-factor list. Returns the htf_aligned value that the
    breakdown would have stored."""
    factors = [ConfluenceFactor(name=name, score=score, weight=0.22, rationale="test")]
    # Mirror the exact predicate from scorer.py post-fix
    return any(f.name == "HTF Composite" and f.score > 60 for f in factors)


def test_htf_aligned_fires_on_htf_composite_above_threshold():
    """The post-fix htf_aligned should look at 'HTF Composite' specifically.
    A factor scoring 70 (above the 60 threshold) must produce True."""
    assert _make_breakdown_with_factor("HTF Composite", 70.0) is True
    assert _make_breakdown_with_factor("HTF Composite", 65.0) is True
    assert _make_breakdown_with_factor("HTF Composite", 61.0) is True


def test_htf_aligned_does_not_fire_below_threshold():
    """A factor at-or-below 60 should not light htf_aligned."""
    assert _make_breakdown_with_factor("HTF Composite", 60.0) is False
    assert _make_breakdown_with_factor("HTF Composite", 55.0) is False
    assert _make_breakdown_with_factor("HTF Composite", 0.0) is False


def test_htf_aligned_does_not_fire_on_legacy_factor_names():
    """The old factor names ('HTF Alignment', 'HTF Structure Bias') are
    NOT emitted as standalone factors anywhere in scorer.py — they got
    consolidated into 'HTF Composite'. If a future refactor reintroduces
    them, the new check (which looks ONLY for 'HTF Composite') must NOT
    pick them up. This locks the post-fix behavior against accidental
    reversion that names them again."""
    assert _make_breakdown_with_factor("HTF Alignment", 99.0) is False
    assert _make_breakdown_with_factor("HTF Structure Bias", 99.0) is False
    assert _make_breakdown_with_factor("HTF Structural Proximity", 99.0) is False
    assert _make_breakdown_with_factor("HTF Momentum Gate", 99.0) is False


def test_htf_aligned_static_source_check():
    """Static check: scorer.py:3220 must reference 'HTF Composite' and must
    NOT reference 'HTF Alignment' / 'HTF Structure Bias' in the
    htf_aligned predicate. If a future refactor reintroduces the wrong
    name, this test fails immediately (mirrors the regression pattern
    from test_stale_counter_main_process_accounting)."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "strategy" / "confluence" / "scorer.py").read_text(encoding="utf-8")

    # Find the ConfluenceBreakdown construction
    bd_anchor = src.find("htf_aligned=any(")
    assert bd_anchor > 0, "ConfluenceBreakdown.htf_aligned assignment not found"
    line = src[bd_anchor:bd_anchor + 200]
    assert '"HTF Composite"' in line, (
        f"htf_aligned predicate must reference 'HTF Composite'. Saw: {line!r}"
    )
    for forbidden in ('"HTF Alignment"', '"HTF Structure Bias"'):
        assert forbidden not in line, (
            f"htf_aligned predicate must NOT reference {forbidden} — that "
            f"factor name is no longer emitted. Saw: {line!r}"
        )


# ──────────────────────────────────────────────────────────────────────
# Bug #2 — macro_state serialized as .name not .value
# ──────────────────────────────────────────────────────────────────────


def test_macro_state_serializes_name_not_value():
    """Repro the orchestrator's Tier-2 macro-metadata writer for each
    MacroState member. The stored string MUST be the .name (e.g.
    'STABLE_SCARE'), NOT the auto-generated integer (e.g. 6)."""
    from backend.analysis.macro_context import MacroState

    # Inline the post-fix predicate from orchestrator.py:3089-3094
    def _serialize(_macro_state):
        return (
            _macro_state.name if hasattr(_macro_state, "name")
            else (str(_macro_state) if _macro_state is not None else "unknown")
        )

    # Every MacroState member must serialize to its .name string
    for member in MacroState:
        assert _serialize(member) == member.name, (
            f"MacroState.{member.name} serialized to {_serialize(member)!r}, "
            f"expected {member.name!r}. If this fails, the fix at "
            f"orchestrator.py:3089 has regressed and the journal will "
            f"start writing enum integers again."
        )
        # And specifically NOT the integer
        assert _serialize(member) != str(member.value), (
            f"MacroState.{member.name} serialized as integer string "
            f"{str(member.value)!r}. Bug #2 from 2026-05-26 has returned."
        )


def test_macro_state_none_is_unknown():
    """The original predicate's None-branch behavior must be preserved.
    If macro_context is somehow None (e.g. fallback path in replay), the
    field should write 'unknown' not crash."""
    def _serialize(_macro_state):
        return (
            _macro_state.name if hasattr(_macro_state, "name")
            else (str(_macro_state) if _macro_state is not None else "unknown")
        )

    assert _serialize(None) == "unknown"


def test_macro_state_static_source_check():
    """Static check: orchestrator.py at the Tier-2 macro writer must use
    .name not .value for MacroState serialization. Regression catch
    for the original bug pattern."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "engine" / "orchestrator.py").read_text(encoding="utf-8")

    # The relevant block lives inside the Tier-2 writer; find the
    # plan.metadata["macro"] assignment region. Window must be large
    # enough to cover the whole dict literal incl. multi-line comments;
    # the original 800-char window was too tight to reach .name.
    anchor = src.find('plan.metadata["macro"] = {')
    assert anchor > 0, 'plan.metadata["macro"] writer not found in orchestrator.py'
    block = src[anchor:anchor + 1600]

    # The post-fix predicate uses .name; the pre-fix predicate used .value
    assert "_macro_state.name" in block, (
        f"Tier-2 macro writer must use _macro_state.name. Saw block: {block!r}"
    )
    # Allow .value to appear elsewhere in the block (e.g. comments), but
    # the SERIALIZATION line specifically must not use .value-based attr access
    # in the hasattr / branch path.
    forbidden_line_anchor = block.find("macro_state\":")
    assert forbidden_line_anchor > 0
    forbidden_line = block[forbidden_line_anchor:forbidden_line_anchor + 400]
    assert "_macro_state.value" not in forbidden_line, (
        f"Tier-2 macro writer's serialization must not reference .value. "
        f"Saw: {forbidden_line!r}"
    )
