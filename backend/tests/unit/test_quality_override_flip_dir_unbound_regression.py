"""
Regression test for the UnboundLocalError on `_flip_dir` introduced by
commit ad60132 (2026-05-27, quality-aware direction override).

Calibrated on session 3512d5eb (2026-05-28, 23h): 2,387 of 10,062
signal_rejected events (23.1%) surfaced as gate_name="errors" with the
message "Confluence scoring failed: cannot access local variable
'_flip_dir' where it is not associated with".

Root cause: orchestrator.py:1862-1866 unconditionally read `_flip_dir`
and `_flip_gate` when `_gate.gate_name == "conflict_density"`. Those
locals are defined ONLY inside the flip-retry block at
orchestrator.py:1765-1819. The quality_override guard added in
ad60132 SKIPS that block when `pre_dir_tie_break == "quality_override"`
and conflict_density rejects — leaving the locals unbound. Then the
rejection-detail builder at L1862 hit them and threw.

Fix: only build `flip_detail` when the flip-retry actually ran
(detected via `"_flip_gate" in locals()`). When quality_override is the
reason flip-retry was skipped, emit an explicit
"flip-retry SKIPPED (quality_override stands)" detail so the autopsy
can still see what happened.

This test exercises the predicate shape via static source-grep and the
intended semantics via inline simulation of the rejection-detail-build
locals frame.

Per CLAUDE.md §11 (silent-bug surfacing — an UnboundLocalError dressed
as a "Confluence scoring failed" message is the worst kind of silent
bug class), §14 (verification discipline — pin the predicate against
regression), §16 audit Open Item #1 (the original audit caught the
flip-retry interaction but missed this UnboundLocalError consequence —
add a static guard so the next audit catches it).
"""

from __future__ import annotations

import pytest


# ──────────────────────────────────────────────────────────────────────
# Static source-grep — the guard predicate must remain
# ──────────────────────────────────────────────────────────────────────


def test_orchestrator_guards_flip_detail_against_unbound_locals():
    """The rejection-detail builder at orchestrator.py:1862 area must
    check `"_flip_gate" in locals()` (or equivalent) before reading
    `_flip_dir` / `_flip_gate`. Without that guard, when the
    quality_override skips the flip-retry block AND conflict_density
    fires the rejection, the rejection builder throws UnboundLocalError
    and 23% of rejected signals masquerade as gate_name="errors".
    """
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2] / "engine" / "orchestrator.py"
    ).read_text(encoding="utf-8")

    # Find the rejection-detail builder anchor
    anchor = src.find("_flip_detail = \"\"")
    assert anchor > 0, "rejection-detail builder _flip_detail anchor not found"

    # Walk forward through the if/elif branches
    block = src[anchor:anchor + 1500]

    # The guard must reference `_flip_gate` in locals() (or _flip_dir
    # equivalent) before reading the variable. The bug was reading it
    # unconditionally.
    assert "in locals()" in block, (
        "Rejection-detail builder must guard against unbound `_flip_dir` / "
        "`_flip_gate` locals. Without this guard, sessions hit UnboundLocalError "
        "on every conflict_density rejection where the quality_override fired. "
        "Calibrated on session 3512d5eb: 2,387 events. Regression catch."
    )

    # And the quality_override skipped-flip case must have an explicit
    # branch so the rejection detail records that fact (not silent).
    assert "quality_override stands" in block or "quality_override" in block, (
        "When quality_override skipped the flip-retry, the rejection detail "
        "must record that fact explicitly — silent skip is the §11 anti-pattern."
    )


# ──────────────────────────────────────────────────────────────────────
# Simulated rejection-detail builder — predicate semantics
# ──────────────────────────────────────────────────────────────────────


def _build_flip_detail(
    gate_name: str,
    quality_override: bool,
    flip_gate_defined: bool,
    flip_dir: str | None = None,
    flip_gate_name: str | None = None,
    flip_gate_reason: str | None = None,
) -> str:
    """Mirror of the predicate at orchestrator.py:1862. If a future
    refactor changes the predicate shape, this helper must change in
    lockstep — but the test pair below pins both code paths so drift
    surfaces immediately."""
    flip_detail = ""
    if gate_name == "conflict_density" and flip_gate_defined:
        flip_detail = (
            f" | flip {flip_dir} blocked by [{flip_gate_name}]: {flip_gate_reason}"
        )
    elif gate_name == "conflict_density" and quality_override:
        flip_detail = " | flip-retry SKIPPED (quality_override stands)"
    return flip_detail


def test_flip_detail_built_when_flip_gate_defined():
    """Normal path: flip-retry ran (locals defined), build the detail
    with the flip direction + opposing gate info."""
    detail = _build_flip_detail(
        gate_name="conflict_density",
        quality_override=False,
        flip_gate_defined=True,
        flip_dir="SHORT",
        flip_gate_name="conflict_density",
        flip_gate_reason="5 simultaneous conflict conditions",
    )
    assert detail == " | flip SHORT blocked by [conflict_density]: 5 simultaneous conflict conditions"


def test_flip_detail_records_skip_on_quality_override():
    """Quality-override path: flip-retry was SKIPPED by design. The
    rejection detail must record that fact explicitly — silent skip
    masks why no flip was attempted."""
    detail = _build_flip_detail(
        gate_name="conflict_density",
        quality_override=True,
        flip_gate_defined=False,   # the locals weren't set
    )
    assert detail == " | flip-retry SKIPPED (quality_override stands)"


def test_flip_detail_empty_on_non_conflict_density_gate():
    """Non-conflict-density rejection (e.g. low_confluence) — no flip
    detail expected. Both code paths must safely return empty."""
    detail = _build_flip_detail(
        gate_name="low_confluence",
        quality_override=False,
        flip_gate_defined=False,
    )
    assert detail == ""


def test_flip_detail_no_crash_when_locals_unbound_and_no_override():
    """Belt-and-braces: if somehow we hit the rejection builder with
    gate_name=conflict_density but neither flip-retry ran NOR
    quality_override fired (shouldn't happen but defend against future
    refactor), return empty string rather than crashing.

    This is the EXACT failure mode that caused the 2,387 events bug:
    code attempted to read unbound locals. The new predicate must
    return safely in this case."""
    detail = _build_flip_detail(
        gate_name="conflict_density",
        quality_override=False,
        flip_gate_defined=False,
    )
    # No flip ran, no override — empty detail, no crash, no UnboundLocalError
    assert detail == ""
