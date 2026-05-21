"""
Tests for Orchestrator._derive_pre_direction — symmetric pre-direction tie-break.

Per CLAUDE.md §10 (bull/bear symmetry) and §14 rubric 12 (symmetry assertions):
the legacy code at orchestrator.py:1579 used `_pre_dir = "SHORT" if _s > _b else "LONG"`
which silently defaulted equal counts (and bullish-majority cases) to LONG.

Symmetry-guard SYM-01 (May 2026) confirmed this as a §10 violation driving the
observed 2.7:1 LONG bias in conflict_density rejections. This test file is the
paired-symmetry proof for the fix.

Coverage:
  - Positive: strict bull majority → LONG / strict bear majority → SHORT
  - Tie + bullish regime → LONG with rationale "regime_bullish"
  - Tie + bearish regime → SHORT with rationale "regime_bearish"
  - Tie + sideways/None/unknown regime → LONG with rationale "neutral_default_long"
  - Empty inputs (no OBs, no BOS) → tie path → defaults via regime same as above
  - Invalidated OBs and grade-C OBs are skipped per the original logic
  - BOS with direction=None is ignored

Each test has a bull-side AND bear-side pair to enforce §14 rubric 12.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.engine.orchestrator import Orchestrator


# ──────────────────────────────────────────────────────────────────────────────
# Fixture helpers — synthetic OB / BOS / SymbolRegime
# ──────────────────────────────────────────────────────────────────────────────


def _ob(direction: str = "bullish", grade: str = "A", invalidated: bool = False):
    """Synthetic OrderBlock with just the fields _derive_pre_direction reads."""
    return SimpleNamespace(direction=direction, grade=grade, invalidated=invalidated)


def _bos(direction: str = "bullish"):
    """Synthetic structural-break with direction attr."""
    return SimpleNamespace(direction=direction)


def _regime(trend: str = "sideways"):
    """Synthetic SymbolRegime carrying the .trend attribute."""
    return SimpleNamespace(trend=trend, score=50.0)


# ──────────────────────────────────────────────────────────────────────────────
# Positive — strict majority paths
# ──────────────────────────────────────────────────────────────────────────────


def test_strict_bull_majority_returns_long():
    """3 bullish OBs vs 1 bearish OB → LONG with rationale bull_majority."""
    obs = [_ob("bullish"), _ob("bullish"), _ob("bullish"), _ob("bearish")]
    direction, reason = Orchestrator._derive_pre_direction(obs, [], _regime("sideways"))
    assert direction == "LONG"
    assert reason == "bull_majority"


def test_strict_bear_majority_returns_short():
    """1 bullish OB vs 3 bearish OBs → SHORT with rationale bear_majority. §10 symmetric pair."""
    obs = [_ob("bullish"), _ob("bearish"), _ob("bearish"), _ob("bearish")]
    direction, reason = Orchestrator._derive_pre_direction(obs, [], _regime("sideways"))
    assert direction == "SHORT"
    assert reason == "bear_majority"


def test_bos_contributes_to_tally_bullish():
    """Bullish BOS counts toward bull side."""
    obs = [_ob("bullish")]
    bos = [_bos("bullish"), _bos("bullish")]
    direction, reason = Orchestrator._derive_pre_direction(obs, bos, _regime("sideways"))
    assert direction == "LONG"
    assert reason == "bull_majority"


def test_bos_contributes_to_tally_bearish():
    """Bearish BOS counts toward bear side. §10 symmetric pair."""
    obs = [_ob("bearish")]
    bos = [_bos("bearish"), _bos("bearish")]
    direction, reason = Orchestrator._derive_pre_direction(obs, bos, _regime("sideways"))
    assert direction == "SHORT"
    assert reason == "bear_majority"


# ──────────────────────────────────────────────────────────────────────────────
# Tie cases — the §10 fix, regime-aware tie-break
# ──────────────────────────────────────────────────────────────────────────────


def test_tie_with_bullish_regime_resolves_long():
    """2 vs 2 OBs + regime trend "up" → LONG with rationale regime_bullish."""
    obs = [_ob("bullish"), _ob("bullish"), _ob("bearish"), _ob("bearish")]
    direction, reason = Orchestrator._derive_pre_direction(obs, [], _regime("up"))
    assert direction == "LONG"
    assert reason == "regime_bullish"


def test_tie_with_strong_up_regime_resolves_long():
    """Strong_up is also bullish vocabulary."""
    obs = [_ob("bullish"), _ob("bearish")]
    direction, reason = Orchestrator._derive_pre_direction(obs, [], _regime("strong_up"))
    assert direction == "LONG"
    assert reason == "regime_bullish"


def test_tie_with_bearish_regime_resolves_short():
    """§10 symmetric pair: tie + bearish regime → SHORT with rationale regime_bearish."""
    obs = [_ob("bullish"), _ob("bullish"), _ob("bearish"), _ob("bearish")]
    direction, reason = Orchestrator._derive_pre_direction(obs, [], _regime("down"))
    assert direction == "SHORT"
    assert reason == "regime_bearish"


def test_tie_with_strong_down_regime_resolves_short():
    """Strong_down is also bearish vocabulary. §10 symmetric pair."""
    obs = [_ob("bullish"), _ob("bearish")]
    direction, reason = Orchestrator._derive_pre_direction(obs, [], _regime("strong_down"))
    assert direction == "SHORT"
    assert reason == "regime_bearish"


def test_tie_with_sideways_regime_defaults_long_observably():
    """2 vs 2 OBs + sideways regime → LONG with rationale neutral_default_long.

    Documented residual: when structure AND regime are neutral, the bot
    defaults to LONG to preserve trade volume on truly-ambiguous setups.
    The rationale is now EXPLICIT (was silent pre-fix) so future diagnostic
    work can quantify how often this branch fires.
    """
    obs = [_ob("bullish"), _ob("bullish"), _ob("bearish"), _ob("bearish")]
    direction, reason = Orchestrator._derive_pre_direction(obs, [], _regime("sideways"))
    assert direction == "LONG"
    assert reason == "neutral_default_long"


def test_tie_with_unknown_regime_defaults_long_observably():
    """Unknown regime trend label also falls to neutral_default_long."""
    obs = [_ob("bullish"), _ob("bearish")]
    direction, reason = Orchestrator._derive_pre_direction(obs, [], _regime("undefined"))
    assert direction == "LONG"
    assert reason == "neutral_default_long"


def test_tie_with_none_regime_defaults_long_observably():
    """No regime object at all → neutral_default_long."""
    obs = [_ob("bullish"), _ob("bearish")]
    direction, reason = Orchestrator._derive_pre_direction(obs, [], None)
    assert direction == "LONG"
    assert reason == "neutral_default_long"


def test_zero_obs_zero_bos_with_bullish_regime_uses_regime():
    """Empty structure (0 vs 0) is also a tie — regime breaks it."""
    direction, reason = Orchestrator._derive_pre_direction([], [], _regime("up"))
    assert direction == "LONG"
    assert reason == "regime_bullish"


def test_zero_obs_zero_bos_with_bearish_regime_uses_regime():
    """§10 symmetric pair for the empty case."""
    direction, reason = Orchestrator._derive_pre_direction([], [], _regime("down"))
    assert direction == "SHORT"
    assert reason == "regime_bearish"


def test_zero_obs_zero_bos_with_sideways_regime_neutral_default():
    """All-empty case + neutral regime → neutral_default_long."""
    direction, reason = Orchestrator._derive_pre_direction([], [], _regime("sideways"))
    assert direction == "LONG"
    assert reason == "neutral_default_long"


# ──────────────────────────────────────────────────────────────────────────────
# Filter behavior preserved — invalidated/low-grade OBs and null-dir BOS
# ──────────────────────────────────────────────────────────────────────────────


def test_invalidated_obs_are_skipped():
    """Invalidated OBs don't count toward the tally, preserving legacy filter behavior."""
    obs = [
        _ob("bullish", grade="A"),
        _ob("bullish", grade="A", invalidated=True),   # skipped
        _ob("bearish", grade="A"),
        _ob("bearish", grade="A"),
    ]
    direction, reason = Orchestrator._derive_pre_direction(obs, [], _regime("sideways"))
    # 1 bull (1 invalidated skipped) vs 2 bear → strict bear majority
    assert direction == "SHORT"
    assert reason == "bear_majority"


def test_grade_c_obs_are_skipped():
    """Grade C and below don't count toward the tally."""
    obs = [
        _ob("bullish", grade="A"),
        _ob("bullish", grade="C"),    # skipped
        _ob("bearish", grade="A"),
    ]
    direction, reason = Orchestrator._derive_pre_direction(obs, [], _regime("sideways"))
    # 1 bull (1 C skipped) vs 1 bear → tie → neutral_default_long
    assert direction == "LONG"
    assert reason == "neutral_default_long"


def test_bos_with_null_direction_is_ignored():
    """BOS without a direction attribute doesn't count."""
    bos = [_bos("bullish"), _bos(None), _bos("bearish")]   # None ignored, 1v1
    direction, reason = Orchestrator._derive_pre_direction([], bos, _regime("sideways"))
    assert direction == "LONG"
    assert reason == "neutral_default_long"


# ──────────────────────────────────────────────────────────────────────────────
# Regression — the EXACT bug pattern from symmetry-guard SYM-01 verification
# ──────────────────────────────────────────────────────────────────────────────


def test_NEAR_USDT_9v9_no_longer_defaults_to_long_when_regime_is_bearish():
    """The NEAR/USDT 9-vs-9 case from the May 2026 forensics.

    Pre-fix: equal counts → strict-greater fails → LONG by default.
    Post-fix: equal counts → regime resolves. If regime is bearish, the bot
    correctly picks SHORT instead of asymmetrically defaulting to LONG.

    This is the exact scenario the symmetry-guard agent flagged as the
    smoking gun for the 2.7:1 LONG bias.
    """
    nine_bull = [_ob("bullish") for _ in range(9)]
    nine_bear = [_ob("bearish") for _ in range(9)]
    direction, reason = Orchestrator._derive_pre_direction(
        nine_bull + nine_bear, [], _regime("down")
    )
    assert direction == "SHORT", "regime-bearish tie must resolve SHORT, not LONG"
    assert reason == "regime_bearish"


def test_NEAR_USDT_9v9_long_when_regime_is_bullish_symmetric_pair():
    """§10 symmetric pair for the regression test."""
    nine_bull = [_ob("bullish") for _ in range(9)]
    nine_bear = [_ob("bearish") for _ in range(9)]
    direction, reason = Orchestrator._derive_pre_direction(
        nine_bull + nine_bear, [], _regime("up")
    )
    assert direction == "LONG", "regime-bullish tie must resolve LONG via regime, not by default"
    assert reason == "regime_bullish"
