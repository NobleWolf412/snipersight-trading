"""
Tests for the C3 §10 symmetry fix at scorer.py:5021-5057 — LTR+HTF-bearish
multiplicative synergy mirror.

Per CLAUDE.md §10 (bull/bear symmetry) and §14 rubric 12 (symmetry assertions):
symmetry-guard SYM-01-SUSPECT confirmed the LONG RTR+HTF-bullish branch had a
multiplicative synergy `(bonus * 0.25 + 8.0)` while the symmetric SHORT
LTR+HTF-bearish path was missing — only additive bonuses on the SHORT side.

/confluence-trace on WIF/USDT (May 2026) showed the impact: 169 SHORT rejects
vs 0 SHORT passes despite 0.84:1 SHORT-leaning structure. SHORT setups
couldn't clear the 70 floor because they were systematically scoring ~5-15pt
lower than structurally-equivalent LONG setups.

C3 added the symmetric LTR+HTF-bearish multiplicative branch at scorer.py.

These tests isolate the multiplicative synergy by:
  - Zeroing out the other synergy contributions (no Order Block, no FVG,
    no Liquidity Sweep, no Market Structure factor)
  - Constructing matched LONG (RTR + ACCUMULATION) vs SHORT (LTR + DISTRIBUTION)
    cycle contexts
  - Setting HTF Alignment score = 80 (>= 60 threshold)
  - Comparing the resulting synergy bonus between directions
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.shared.models.scoring import ConfluenceFactor
from backend.shared.models.smc import (
    CycleConfirmation,
    CycleContext,
    CyclePhase,
    CycleTranslation,
    SMCSnapshot,
)
from backend.strategy.confluence.scorer import _calculate_synergy_bonus


def _smc() -> SMCSnapshot:
    return SMCSnapshot(
        order_blocks=[], fvgs=[], structural_breaks=[],
        liquidity_sweeps=[],
    )


def _htf_alignment_factor(score: float = 80.0) -> ConfluenceFactor:
    return ConfluenceFactor(
        name="HTF Alignment", score=score, weight=0.22,
        rationale="HTF supports trade direction",
    )


def _cycle_long_rtr(phase: CyclePhase = CyclePhase.MARKUP) -> CycleContext:
    return CycleContext(
        phase=phase, translation=CycleTranslation.RTR,
        dcl_confirmation=CycleConfirmation.UNCONFIRMED,
        in_dcl_zone=False, in_wcl_zone=False,
    )


def _cycle_short_ltr(phase: CyclePhase = CyclePhase.MARKDOWN) -> CycleContext:
    return CycleContext(
        phase=phase, translation=CycleTranslation.LTR,
        dcl_confirmation=CycleConfirmation.UNCONFIRMED,
        in_dcl_zone=False, in_wcl_zone=False,
    )


def _mode_overwatch():
    return SimpleNamespace(profile="overwatch")


def _mode_stealth():
    return SimpleNamespace(profile="stealth_balanced")


# ──────────────────────────────────────────────────────────────────────────────
# C3 — multiplicative synergy mirror on SHORT
# ──────────────────────────────────────────────────────────────────────────────


def test_long_rtr_htf_bullish_multiplicative_fires():
    """LONG with RTR + HTF Alignment >= 60 → multiplicative synergy bonus."""
    bonus = _calculate_synergy_bonus(
        factors=[_htf_alignment_factor(80.0)],
        smc=_smc(),
        cycle_context=_cycle_long_rtr(phase=CyclePhase.MARKUP),
        direction="LONG",
        mode_config=_mode_overwatch(),
    )
    assert bonus > 0.0, f"LONG multiplicative must produce positive bonus, got {bonus}"


def test_short_ltr_htf_bearish_multiplicative_fires_post_C3():
    """§10 mirror: SHORT with LTR + HTF Alignment >= 60 → multiplicative synergy."""
    bonus = _calculate_synergy_bonus(
        factors=[_htf_alignment_factor(80.0)],
        smc=_smc(),
        cycle_context=_cycle_short_ltr(phase=CyclePhase.UNKNOWN),
        direction="SHORT",
        mode_config=_mode_overwatch(),
    )
    assert bonus > 0.0, f"SHORT multiplicative must fire post-C3, got {bonus}"


def test_synergy_bonuses_symmetric_on_mirrored_inputs():
    """§10 invariant: LONG and SHORT with mirrored inputs produce equal bonus.

    Both inputs construct a minimal scenario where ONLY the multiplicative
    synergy fires — no Order Block, no FVG, no Sweep, no Market Structure,
    no DCL/WCL confirmation, no LTR+Distribution/Markdown chain. The only
    bonus that can fire is the multiplicative gate. Bonus computation is
    identical on both sides post-C3 → bonuses must match.
    """
    factors = [_htf_alignment_factor(80.0)]
    long_bonus = _calculate_synergy_bonus(
        factors=factors, smc=_smc(),
        cycle_context=_cycle_long_rtr(phase=CyclePhase.MARKUP),
        direction="LONG", mode_config=_mode_overwatch(),
    )
    short_bonus = _calculate_synergy_bonus(
        factors=factors, smc=_smc(),
        cycle_context=_cycle_short_ltr(phase=CyclePhase.UNKNOWN),
        direction="SHORT", mode_config=_mode_overwatch(),
    )
    assert abs(long_bonus - short_bonus) < 0.01, (
        f"§10 symmetry violation: LONG={long_bonus}, SHORT={short_bonus}, "
        f"diff={abs(long_bonus - short_bonus):.4f}. Pre-C3 the SHORT side got "
        f"only the +5 LTR-alone fallback (5.0) while LONG got the multiplicative "
        f"(~8.0) — a 3pt gap that compounded to ~10pt in DIST+Structure cases."
    )


def test_short_no_multiplicative_when_htf_below_threshold():
    """SHORT with LTR + HTF Alignment score < 60 → multiplicative gate skipped."""
    factors_below = [_htf_alignment_factor(40.0)]
    bonus_below = _calculate_synergy_bonus(
        factors=factors_below, smc=_smc(),
        cycle_context=_cycle_short_ltr(phase=CyclePhase.UNKNOWN),
        direction="SHORT", mode_config=_mode_overwatch(),
    )
    bonus_no_factor = _calculate_synergy_bonus(
        factors=[], smc=_smc(),
        cycle_context=_cycle_short_ltr(phase=CyclePhase.UNKNOWN),
        direction="SHORT", mode_config=_mode_overwatch(),
    )
    assert abs(bonus_below - bonus_no_factor) < 0.01, (
        f"SHORT multiplicative gate fired below threshold: "
        f"with_factor_score_40={bonus_below}, no_factor={bonus_no_factor}"
    )


def test_long_no_multiplicative_when_htf_below_threshold():
    """§10 symmetric pair: LONG also requires HTF >= 60 for multiplicative."""
    factors_below = [_htf_alignment_factor(40.0)]
    bonus_below = _calculate_synergy_bonus(
        factors=factors_below, smc=_smc(),
        cycle_context=_cycle_long_rtr(phase=CyclePhase.MARKUP),
        direction="LONG", mode_config=_mode_overwatch(),
    )
    bonus_no_factor = _calculate_synergy_bonus(
        factors=[], smc=_smc(),
        cycle_context=_cycle_long_rtr(phase=CyclePhase.MARKUP),
        direction="LONG", mode_config=_mode_overwatch(),
    )
    assert abs(bonus_below - bonus_no_factor) < 0.01, (
        f"LONG multiplicative gate fired below threshold: "
        f"with_factor_score_40={bonus_below}, no_factor={bonus_no_factor}"
    )


def test_synergy_cap_applied_symmetrically():
    """MODE_SYNERGY_CAPS clamps LONG and SHORT bonuses equally — no asymmetric clip."""
    factors = [_htf_alignment_factor(95.0)]  # high score, push toward cap
    long_bonus = _calculate_synergy_bonus(
        factors=factors, smc=_smc(),
        cycle_context=_cycle_long_rtr(phase=CyclePhase.MARKUP),
        direction="LONG", mode_config=_mode_stealth(),
    )
    short_bonus = _calculate_synergy_bonus(
        factors=factors, smc=_smc(),
        cycle_context=_cycle_short_ltr(phase=CyclePhase.UNKNOWN),
        direction="SHORT", mode_config=_mode_stealth(),
    )
    STEALTH_CAP = 15.0
    assert long_bonus <= STEALTH_CAP and short_bonus <= STEALTH_CAP
    assert abs(long_bonus - short_bonus) < 0.01, (
        f"Cap clipping asymmetric: LONG={long_bonus}, SHORT={short_bonus}"
    )


def test_no_cycle_context_skips_cycle_bonuses_long():
    """No cycle_context → cycle-bonus block skipped entirely on LONG path."""
    bonus = _calculate_synergy_bonus(
        factors=[_htf_alignment_factor(80.0)],
        smc=_smc(),
        cycle_context=None,
        direction="LONG",
        mode_config=_mode_overwatch(),
    )
    assert bonus == 0.0


def test_no_cycle_context_skips_cycle_bonuses_short():
    """§10 symmetric pair: no cycle_context also skips cycle bonuses on SHORT."""
    bonus = _calculate_synergy_bonus(
        factors=[_htf_alignment_factor(80.0)],
        smc=_smc(),
        cycle_context=None,
        direction="SHORT",
        mode_config=_mode_overwatch(),
    )
    assert bonus == 0.0
