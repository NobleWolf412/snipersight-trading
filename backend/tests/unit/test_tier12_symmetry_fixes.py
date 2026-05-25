"""
Tests for Tier 1.2 §10 mirror cleanups:

(a) Gate 3 (BTC impulse) — LONG-side divergence bypass mirror.
    Pre-fix: SHORT alts blocked on BTC pump had a bypass for locally-bearish
    alts (BTC.D expansion pattern); LONG alts blocked on BTC dump had NO
    mirror. Tier 1.2 adds the LONG-side bypass for locally-bullish alts
    (BTC.D contraction / alt-divergence-up pattern).

(b) STEALTH position_size_adjustment — strong_down 1.1 → 1.2 to mirror
    strong_up 1.2. Trend clarity drives sizing equally in both directions.

Per CLAUDE.md §10 (bull/bear symmetry), §14 rubric 4 (negative tests
paired with positive), §16 rubric 12 (direction-pair every relevant test).
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest


# ──────────────────────────────────────────────────────────────────────
# (a) Gate 3 LONG-side bypass mirror
# ──────────────────────────────────────────────────────────────────────

_SCORER_SRC = (
    Path(__file__).resolve().parents[2]
    / "strategy"
    / "confluence"
    / "scorer.py"
).read_text(encoding="utf-8")


def test_gate3_long_side_has_alt_local_trend_bypass():
    """Pin that the Gate 3 LONG-side rejection now checks alt_local_trend
    before rejecting (mirror of SHORT-side bypass at L348-360).

    Regression catch: if a future refactor removes the LONG-side bypass
    and reverts to unconditional reject, this fails."""
    # The bypass pattern: `if is_long and btc_strongly_down:` followed by
    # a conditional on `_alt_local_trend not in ("up", "strong_up")`.
    pattern = re.compile(
        r'if is_long and btc_strongly_down:.*?'
        r'if _alt_local_trend not in \("up", "strong_up"\):',
        re.DOTALL,
    )
    assert pattern.search(_SCORER_SRC), (
        "LONG-side Gate 3 must check alt_local_trend before rejecting. "
        "Pre-Tier-1.2 the LONG-side was unconditional — symmetry violation."
    )


def test_gate3_short_side_bypass_preserved():
    """Negative pair — the SHORT-side bypass (pre-existing) must not have
    been damaged by the Tier 1.2 mirror addition."""
    pattern = re.compile(
        r'if not is_long and btc_strongly_up:.*?'
        r'if _alt_local_trend not in \("down", "strong_down"\):',
        re.DOTALL,
    )
    assert pattern.search(_SCORER_SRC), (
        "SHORT-side Gate 3 bypass (pre-existing) must remain intact."
    )


def test_gate3_alt_local_trend_resolved_once():
    """The Tier 1.2 refactor lifts the `_alt_local_trend = getattr(...)`
    resolution to apply to BOTH directions. Verify it's resolved before
    either direction's branch."""
    # Find the position of _alt_local_trend assignment, both is_long branches
    alt_assign = _SCORER_SRC.find('_alt_local_trend = getattr(regime, "trend"')
    long_branch = _SCORER_SRC.find("if is_long and btc_strongly_down:")
    short_branch = _SCORER_SRC.find("if not is_long and btc_strongly_up:")

    assert alt_assign != -1, "_alt_local_trend resolution not found"
    assert long_branch != -1, "LONG branch not found"
    assert short_branch != -1, "SHORT branch not found"
    assert alt_assign < long_branch, (
        "_alt_local_trend must be resolved BEFORE the LONG branch checks it"
    )
    assert alt_assign < short_branch, (
        "_alt_local_trend must be resolved BEFORE the SHORT branch checks it"
    )


def test_orchestrator_forwards_alt_local_trend_to_rejection_info():
    """The Gate 3 rejection metadata's `alt_local_trend` key must be in
    `_FORWARD_KEYS` at orchestrator.py:1698-1705. Without this, the key
    gets dropped before reaching the UI rejection breakdown — the
    operator-visible diagnostic value is lost. §16 Rubric 13 follow-up
    from Tier 1.2 audit."""
    orchestrator_src = (
        Path(__file__).resolve().parents[2] / "engine" / "orchestrator.py"
    ).read_text(encoding="utf-8")
    pattern = re.compile(
        r"_FORWARD_KEYS\s*=\s*\{[^}]*?\"alt_local_trend\"[^}]*?\}",
        re.DOTALL,
    )
    assert pattern.search(orchestrator_src), (
        "_FORWARD_KEYS allowlist at orchestrator.py:1698 must include "
        "\"alt_local_trend\" so the Gate 3 bypass diagnostic surfaces "
        "to rejection_info / UI."
    )


def test_gate3_long_rejection_metadata_includes_alt_local_trend():
    """When Gate 3 LONG rejects, the rejection metadata should include
    alt_local_trend so the operator can verify the bypass logic on
    rejection inspection. Same diagnostic surface as SHORT side."""
    # Find both rejection metadata dicts and assert they include alt_local_trend
    long_rej_pattern = re.compile(
        r'reason=f"LONG alt rejected: BTC in opposing strong impulse.*?'
        r'metadata=\{[^}]*"alt_local_trend"[^}]*\}',
        re.DOTALL,
    )
    short_rej_pattern = re.compile(
        r'reason=f"SHORT alt rejected: BTC in opposing strong impulse.*?'
        r'metadata=\{[^}]*"alt_local_trend"[^}]*\}',
        re.DOTALL,
    )
    assert long_rej_pattern.search(_SCORER_SRC), (
        "LONG-side rejection metadata must include alt_local_trend"
    )
    assert short_rej_pattern.search(_SCORER_SRC), (
        "SHORT-side rejection metadata must include alt_local_trend"
    )


# ──────────────────────────────────────────────────────────────────────
# (b) STEALTH position_size_adjustment mirror
# ──────────────────────────────────────────────────────────────────────


def test_stealth_position_size_strong_pairs_are_symmetric():
    """STEALTH policy's position_size_adjustment must have strong_up ==
    strong_down. Pre-Tier-1.2 was 1.2 vs 1.1 — §10 violation."""
    from backend.analysis.regime_policies import REGIME_POLICIES

    stealth = REGIME_POLICIES["stealth"]
    size_adj = stealth.position_size_adjustment
    assert size_adj["strong_up"] == size_adj["strong_down"], (
        f"§10 violation: strong_up={size_adj['strong_up']} must mirror "
        f"strong_down={size_adj['strong_down']}. Trend clarity drives "
        f"sizing in both directions equally."
    )


def test_stealth_position_size_normal_pairs_are_symmetric():
    """And up == down at the normal level."""
    from backend.analysis.regime_policies import REGIME_POLICIES

    stealth = REGIME_POLICIES["stealth"]
    size_adj = stealth.position_size_adjustment
    assert size_adj["up"] == size_adj["down"], (
        f"§10 violation: up={size_adj['up']} must mirror "
        f"down={size_adj['down']}."
    )


def test_stealth_position_size_sideways_is_lowest():
    """Negative — sideways (the chop / low-quality regime) must score
    less than any directional regime. Pins the directional-clarity-
    drives-sizing framing — prevents the 'set everything equal' anti-fix."""
    from backend.analysis.regime_policies import REGIME_POLICIES

    stealth = REGIME_POLICIES["stealth"]
    size_adj = stealth.position_size_adjustment
    sideways = size_adj["sideways"]
    directional = [
        size_adj["up"],
        size_adj["down"],
        size_adj["strong_up"],
        size_adj["strong_down"],
    ]
    assert sideways < min(directional), (
        f"sideways size {sideways} must be < min directional "
        f"{min(directional)}. Sideways IS the low-quality regime."
    )


def test_stealth_strong_levels_above_normal_levels():
    """strong_up should be ≥ up, and strong_down should be ≥ down.
    Pins the trend-strength gradient."""
    from backend.analysis.regime_policies import REGIME_POLICIES

    stealth = REGIME_POLICIES["stealth"]
    size_adj = stealth.position_size_adjustment
    assert size_adj["strong_up"] >= size_adj["up"], (
        "strong_up sizing must be >= up sizing"
    )
    assert size_adj["strong_down"] >= size_adj["down"], (
        "strong_down sizing must be >= down sizing — §10 mirror of above"
    )


def test_stealth_rr_adjustment_already_symmetric():
    """Sanity check that the pre-existing strong_up == strong_down
    parity in rr_adjustment wasn't disturbed by the Tier 1.2 edit."""
    from backend.analysis.regime_policies import REGIME_POLICIES

    stealth = REGIME_POLICIES["stealth"]
    rr_adj = stealth.rr_adjustment
    assert rr_adj["strong_up"] == rr_adj["strong_down"], (
        "rr_adjustment strong_up/strong_down parity must remain intact"
    )


def test_stealth_confluence_adjustment_already_symmetric():
    """Sanity check — confluence_adjustment bullish_risk_on +3.0 mirrors
    bearish_risk_off +3.0 (pre-existing §10 compliance)."""
    from backend.analysis.regime_policies import REGIME_POLICIES

    stealth = REGIME_POLICIES["stealth"]
    conf_adj = stealth.confluence_adjustment
    assert conf_adj["bullish_risk_on"] == conf_adj["bearish_risk_off"], (
        "confluence_adjustment bullish_risk_on/bearish_risk_off "
        "parity must remain intact (pre-existing §10 compliance)"
    )
