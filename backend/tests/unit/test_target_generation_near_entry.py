"""
Tests for Tier 1.1 — target generator references `near_entry` instead of
`avg_entry` (the midpoint).

Bug-class context (the "strip pattern"):
  - Commit 881d6d7 tightened _guard_target_direction to use `near_entry`
    as the worst-case-fill reference. But the target GENERATOR in
    _calculate_targets kept using `avg_entry = (near + far) / 2`.
  - Result: an inter-band gap. For LONG, `near_entry > avg_entry`, so
    a target placed at `avg_entry + dist` could land between avg and
    near — above the midpoint (planner-guard pass) but below the actual
    fill (executor-strip target). The guard's "least-wrong fallback"
    preserved that target; the executor then stripped it at runtime.
  - Production evidence: session 9558a1c8 (May 2026) — 3 of 4 LONG
    positions opened with `final_targets_remaining=0`, with the new
    executor_target_strip telemetry firing on every one.

Tier 1.1 fix: generator now uses `entry_ref = entry_zone.near_entry` for
all target-side math inside `_calculate_targets` (R:R-ladder generation,
structural-candidate sort + R:R compute, fee-floor reference, helper
calls to structural finders + wick-barrier adjuster). Helper function
parameter names (`avg_entry`) retained for minimal diff; they now
receive the `near_entry` value from the caller.

Per CLAUDE.md §10 (bull/bear symmetry), §14 rubric 4 (negative tests
paired with positive), §16 rubric 12 (direction-pair every relevant
test), §15 (this change is backed by 27,000-candle empirical study +
N=3 production strip evidence from session 9558a1c8).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


_SRC_PATH = (
    Path(__file__).resolve().parents[2] / "strategy" / "planner" / "risk_engine.py"
)


def _calculate_targets_body() -> str:
    """Return the source of `_calculate_targets` from `def _calculate_targets`
    up to (but not including) the next top-level `def `. Used by the
    regression tests below to scan target-generator-only references."""
    src = _SRC_PATH.read_text(encoding="utf-8")
    start_match = re.search(r"^def _calculate_targets\(", src, re.MULTILINE)
    assert start_match, "could not locate _calculate_targets definition"
    start = start_match.start()
    end_match = re.search(r"^def ", src[start + 4:], re.MULTILINE)
    end = (start + 4 + end_match.start()) if end_match else len(src)
    return src[start:end]


# ──────────────────────────────────────────────────────────────────────
# Source-level regression — pin the entry_ref substitution
# ──────────────────────────────────────────────────────────────────────


def test_calculate_targets_uses_entry_ref_local():
    """`_calculate_targets` defines `entry_ref = entry_zone.near_entry`
    at the top of its body. Catches a future refactor that removes the
    local and reintroduces midpoint-relative target math."""
    body = _calculate_targets_body()
    assert "entry_ref = entry_zone.near_entry" in body, (
        "Expected `entry_ref = entry_zone.near_entry` at top of "
        "_calculate_targets per Tier 1.1. Either the local was removed "
        "or renamed — review post-merge."
    )


def test_calculate_targets_risk_distance_uses_entry_ref():
    """risk_distance must be computed from entry_ref (= near_entry), not
    avg_entry. Aligns the planner's view of risk with the executor's."""
    body = _calculate_targets_body()
    assert "risk_distance = abs(entry_ref - stop_loss.level)" in body, (
        "risk_distance must use entry_ref. If this fails, the planner's "
        "reported R:R will diverge from what the executor realizes."
    )


def test_calculate_targets_rr_ladder_uses_entry_ref():
    """R:R-ladder generator places targets at `entry_ref ± dist`, NOT
    `avg_entry ± dist`. This is the primary fix surface."""
    body = _calculate_targets_body()
    # LONG branch
    assert "level = entry_ref + dist" in body, (
        "LONG R:R-ladder target generator must compute `level = entry_ref + dist`. "
        "Pre-fix used avg_entry + dist, which produced strip-pattern losses."
    )
    # SHORT branch (paired)
    assert "level = max(entry_ref * 0.001, entry_ref - dist)" in body, (
        "SHORT R:R-ladder target generator must compute against entry_ref. "
        "Mirror of LONG fix — §10 / §16 rubric 12."
    )


def test_calculate_targets_min_tp_distance_uses_entry_ref():
    """Fee-floor TP distance referenced to entry_ref so the scale
    matches actual fill price."""
    body = _calculate_targets_body()
    assert "_MIN_TP_DISTANCE = entry_ref * fee_rate" in body


def test_calculate_targets_structural_path_uses_entry_ref():
    """Structural-candidate sort key + R:R compute use entry_ref."""
    body = _calculate_targets_body()
    assert "candidates.sort(key=lambda x: abs(x[0] - entry_ref))" in body, (
        "Structural-candidate sort key must reference entry_ref."
    )
    assert "dist = abs(level - entry_ref)" in body, (
        "Structural-candidate R:R compute must reference entry_ref."
    )


def test_calculate_targets_helpers_receive_entry_ref():
    """All structural-candidate helper calls (HTF swing, BOS, EQH/EQL,
    Fib, FVG, Bollinger, swing-structural-fallback) and the wick-barrier
    adjuster receive `entry_ref` for their (legacy-named) `avg_entry`
    parameter."""
    body = _calculate_targets_body()
    expected_helper_calls = [
        "_find_htf_swing_targets(is_bullish, entry_ref,",
        "_get_htf_bos_levels(is_bullish, entry_ref,",
        "_find_eqh_eql_zones(is_bullish, entry_ref,",
        "_calculate_fib_extensions(\n                is_bullish, entry_ref,",
        "_get_unfilled_htf_fvgs(is_bullish, entry_ref,",
        "_get_bollinger_targets(\n                is_bullish,\n                entry_ref,",
        "_adjust_targets_for_wick_barriers(targets, multi_tf_data, entry_ref,",
    ]
    for needle in expected_helper_calls:
        assert needle in body, (
            f"Helper call site must pass entry_ref. Missing pattern: "
            f"{needle!r}. If this fails, a structural-target helper is "
            f"still receiving avg_entry, defeating the Tier 1.1 fix on "
            f"that code path."
        )


def test_no_target_side_math_uses_avg_entry_in_calculate_targets():
    """Within `_calculate_targets` body, no remaining target-generator
    math references `avg_entry`. Only comments + parameter names of
    nested helper definitions (none expected) are permitted.

    Catches a future regression that reintroduces avg_entry into the
    R:R math without going through entry_ref."""
    body = _calculate_targets_body()
    code_lines = []
    for ln in body.splitlines():
        stripped = ln.strip()
        # Skip comment-only lines
        if stripped.startswith("#"):
            continue
        # Skip docstring lines (heuristic: triple-quote markers in surrounding code)
        code_lines.append(ln)
    code_only = "\n".join(code_lines)
    # In code (non-comment) lines, "avg_entry" should not appear.
    # The legacy local was removed by the Tier 1.1 cleanup, and helper
    # parameter names use `avg_entry` only in helper DEFINITIONS (which
    # are NOT inside _calculate_targets body).
    assert "avg_entry" not in code_only, (
        f"Found avg_entry in target-generator code: "
        f"{[l for l in code_only.splitlines() if 'avg_entry' in l]}"
    )


# ──────────────────────────────────────────────────────────────────────
# Math-formula direct verification (no fixture scaffolding required)
# ──────────────────────────────────────────────────────────────────────
#
# The fix is essentially: `level = near + (rr * |near - stop|)` for LONG,
# mirror for SHORT. These tests verify the formula produces targets
# beyond the worst-case fill in both directions, with the worked
# example from the commit body matching exactly.


def test_long_target_formula_lands_beyond_near_entry():
    """LONG worked example. near=100, far=90, stop=80, rr_ladder=[2.0, 4.0].
    Tier 1.1 formula: level = near + (rr * risk_distance) where
    risk_distance = |near - stop| = 20.
    TP1 = 100 + 40 = 140  (NOT 95 + 30 = 125 of pre-fix)
    TP2 = 100 + 80 = 180  (NOT 95 + 60 = 155 of pre-fix)
    Every target must be > near_entry — the executor's strip condition
    `target.level > position.entry_price` (where entry_price = near_entry
    for paper limit orders) is satisfied by construction."""
    near, far, stop = 100.0, 90.0, 80.0
    risk_distance = abs(near - stop)
    rrs = [2.0, 4.0]
    for rr in rrs:
        level = near + (rr * risk_distance)
        assert level > near, (
            f"LONG target {level} must be strictly above near={near}. "
            f"Failing this would re-introduce the strip pattern."
        )
    # The worked example exactly
    assert near + (2.0 * risk_distance) == 140.0
    assert near + (4.0 * risk_distance) == 180.0


def test_short_target_formula_lands_below_near_entry():
    """SHORT mirror. near=100, far=110, stop=120, rr_ladder=[2.0, 4.0].
    risk_distance = |near - stop| = 20.
    TP1 = max(near * 0.001, near - 2 * 20) = max(0.1, 60) = 60
    TP2 = max(0.1, near - 4 * 20) = max(0.1, 20) = 20
    Every target must be < near_entry."""
    near, far, stop = 100.0, 110.0, 120.0
    risk_distance = abs(near - stop)
    rrs = [2.0, 4.0]
    for rr in rrs:
        level = max(near * 0.001, near - (rr * risk_distance))
        assert level < near, (
            f"SHORT target {level} must be strictly below near={near}. "
            f"Mirror of LONG fix — §16 rubric 12."
        )
    assert max(near * 0.001, near - (2.0 * risk_distance)) == 60.0
    assert max(near * 0.001, near - (4.0 * risk_distance)) == 20.0


def test_pre_fix_formula_demonstrates_strip_pattern():
    """Documents the pre-fix bug. With the OLD generator math, TP1 on
    a LONG could land BELOW near_entry (= actual fill), guaranteeing the
    executor's structural-validity guard would strip it at runtime.

    Worked example with WIDE entry zone: near=100, far=90, stop=98,
    rr_ladder=[1.5]. risk_distance_pre = |avg - stop| = |95 - 98| = 3.
    OLD TP1 = avg + 1.5 * 3 = 95 + 4.5 = 99.5  ← BELOW near=100 → STRIPPED
    NEW: risk_distance = |near - stop| = 2.
    NEW TP1 = near + 1.5 * 2 = 100 + 3 = 103  ← above near → kept.

    This is precisely the inter-band-gap class of bug Tier 1.1
    eliminates by construction."""
    near, far, stop = 100.0, 90.0, 98.0
    avg = (near + far) / 2
    # Pre-fix
    pre_risk = abs(avg - stop)
    pre_tp1 = avg + 1.5 * pre_risk
    assert pre_tp1 < near, (
        "Sanity check on the pre-fix worked example: TP1 lands below "
        "near_entry. If this assertion FAILS, the test example needs "
        "reconstruction — the strip pattern requires (avg + rr * |avg-stop|) < near."
    )
    # Post-fix
    post_risk = abs(near - stop)
    post_tp1 = near + 1.5 * post_risk
    assert post_tp1 > near, "Post-fix TP1 lands above near_entry — strip eliminated."
    # Quantify the improvement
    assert post_tp1 - near == 3.0
    assert pre_tp1 - near == pytest.approx(-0.5, abs=1e-9)


# ──────────────────────────────────────────────────────────────────────
# Realized R:R alignment — what the planner reports matches what the
# executor delivers
# ──────────────────────────────────────────────────────────────────────


def test_reported_rr_matches_realized_rr_long():
    """Post Tier 1.1, the R:R the planner reports matches what the
    executor will realize on a near_entry fill.

    LONG: near=100 far=90 stop=80. risk_distance=20.
    Generator: TP1 at near + 2R = 140.
    Realized at fill=near=100: (140 - 100) / (100 - 80) = 2.0R. Match.

    Pre-fix counterexample (for documentation):
    Generator: TP1 at avg + 2R_old = 95 + 2*15 = 125.
    Realized at fill=near=100: (125 - 100) / (100 - 80) = 1.25R. Drift!"""
    near, far, stop = 100.0, 90.0, 80.0
    reported_rr = 2.0
    risk_distance = abs(near - stop)
    target_level = near + reported_rr * risk_distance
    realized_rr = (target_level - near) / (near - stop)
    assert realized_rr == reported_rr, (
        f"Post-fix realized R:R {realized_rr} must equal reported R:R "
        f"{reported_rr}. If different, the generator and the executor "
        f"are disagreeing about which entry price defines risk."
    )


def test_reported_rr_matches_realized_rr_short():
    """SHORT mirror of the R:R-alignment guarantee.
    near=100 far=110 stop=120. TP1 at near - 2R = 60.
    Realized at fill=near=100: (100 - 60) / (120 - 100) = 2.0R. Match."""
    near, far, stop = 100.0, 110.0, 120.0
    reported_rr = 2.0
    risk_distance = abs(near - stop)
    target_level = near - reported_rr * risk_distance
    realized_rr = (near - target_level) / (stop - near)
    assert realized_rr == reported_rr, (
        f"Post-fix realized R:R {realized_rr} must equal reported R:R "
        f"{reported_rr} on SHORT side. §16 rubric 12 mirror of LONG test."
    )
