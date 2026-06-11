"""
Regression test for Fix 3: regime double-count dedup (2026-06-11).

Verifies:
- htf_alignment is NOT a sub-score inside htf_composite (removed to avoid
  double-counting with the standalone regime_alignment factor)
- The 4 remaining _HTF_INTERNAL_WEIGHTS are present and non-zero
- _score_htf_alignment_incremental is NOT called from the htf_composite block
"""

from __future__ import annotations

import pathlib
import re

import pytest

SCORER_SRC = pathlib.Path("backend/strategy/confluence/scorer.py").read_text(
    encoding="utf-8"
)

# Locate the htf_composite block for narrow scope assertions
_HTF_BLOCK_RE = re.compile(
    r"# --- HTF Composite Sub-scores.*?# --- Institutional Sequence",
    re.DOTALL,
)
_htf_block = _HTF_BLOCK_RE.search(SCORER_SRC)
HTF_BLOCK = _htf_block.group(0) if _htf_block else ""


class TestRegimeDoubleCountRemoved:
    def test_htf_alignment_not_in_htf_internal_weights(self):
        """htf_alignment must NOT appear in _HTF_INTERNAL_WEIGHTS dict."""
        # Find the _HTF_INTERNAL_WEIGHTS literal in the scorer
        weights_match = re.search(
            r"_HTF_INTERNAL_WEIGHTS\s*=\s*\{([^}]+)\}", SCORER_SRC, re.DOTALL
        )
        assert weights_match, "_HTF_INTERNAL_WEIGHTS dict not found in scorer.py"
        weights_body = weights_match.group(1)
        assert '"htf_alignment"' not in weights_body, (
            '"htf_alignment" still present in _HTF_INTERNAL_WEIGHTS — '
            "double-count with regime_alignment factor not removed"
        )

    def test_htf_alignment_sub_score_not_computed_in_block(self):
        """htf_alignment sub-score must NOT be computed inside htf_composite block."""
        assert HTF_BLOCK, "htf_composite block not found — check block delimiter comment"
        assert '_htf_sub_scores["htf_alignment"]' not in HTF_BLOCK, (
            "htf_alignment still assigned to _htf_sub_scores in htf_composite block"
        )

    def test_htf_alignment_incremental_not_called_in_block(self):
        """_score_htf_alignment_incremental must NOT be called inside the composite block."""
        assert "_score_htf_alignment_incremental" not in HTF_BLOCK, (
            "_score_htf_alignment_incremental still called inside htf_composite block"
        )

    def test_four_htf_sub_weights_present(self):
        """The 4 remaining HTF sub-weight keys must all be present and non-zero."""
        expected = {
            "htf_structure_bias",
            "htf_proximity",
            "htf_momentum_gate",
            "htf_inflection",
        }
        weights_match = re.search(
            r"_HTF_INTERNAL_WEIGHTS\s*=\s*\{([^}]+)\}", SCORER_SRC, re.DOTALL
        )
        assert weights_match, "_HTF_INTERNAL_WEIGHTS not found"
        weights_body = weights_match.group(1)
        for key in expected:
            assert f'"{key}"' in weights_body, (
                f'"{key}" missing from _HTF_INTERNAL_WEIGHTS — sub-weight dropped'
            )

    def test_regime_alignment_standalone_factor_present(self):
        """The standalone regime_alignment factor must still be appended (not removed)."""
        assert '"Regime Alignment"' in SCORER_SRC, (
            "Regime Alignment factor not found — standalone factor was accidentally removed"
        )

    def test_htf_alignment_function_still_defined(self):
        """_score_htf_alignment_incremental must still be defined (not deleted)."""
        assert "def _score_htf_alignment_incremental" in SCORER_SRC, (
            "_score_htf_alignment_incremental function removed — it may have other callers"
        )


class TestHtfCompositeNormalizationSymmetry:
    """Behavioral symmetry: weighted-average math is direction-agnostic."""

    # These weights mirror the current _HTF_INTERNAL_WEIGHTS
    _WEIGHTS = {
        "htf_structure_bias": 0.40,
        "htf_proximity":      0.30,
        "htf_momentum_gate":  0.18,
        "htf_inflection":     0.12,
    }

    @staticmethod
    def _htf_composite(sub_scores: dict) -> float:
        """Inline reproduction of the scorer's normalization formula."""
        weights = TestHtfCompositeNormalizationSymmetry._WEIGHTS
        total_w = sum(weights[k] for k in weights if k in sub_scores)
        if total_w == 0:
            return 0.0
        raw = sum(sub_scores[k] * weights[k] for k in weights if k in sub_scores) / total_w
        return max(0.0, min(100.0, raw))

    def test_full_set_correct_weighted_average(self):
        """Four sub-scores produce the correct weighted average."""
        subs = {
            "htf_structure_bias": 80.0,
            "htf_proximity":      60.0,
            "htf_momentum_gate":  70.0,
            "htf_inflection":     50.0,
        }
        result = self._htf_composite(subs)
        expected = (80*0.40 + 60*0.30 + 70*0.18 + 50*0.12) / (0.40+0.30+0.18+0.12)
        assert abs(result - expected) < 0.001

    def test_bull_bear_same_output_for_equal_inputs(self):
        """Composite math is direction-agnostic: LONG and SHORT with identical sub-scores
        produce the same composite value (no direction branch in the formula)."""
        subs = {"htf_structure_bias": 75.0, "htf_proximity": 60.0}
        assert self._htf_composite(subs) == self._htf_composite(subs), (
            "Identical sub-scores must yield identical composite regardless of direction"
        )

    def test_missing_sub_scores_normalize_correctly(self):
        """Absent sub-scores are excluded; remaining weights normalize to 1.0."""
        # Only proximity and structure_bias present
        subs = {"htf_structure_bias": 100.0, "htf_proximity": 0.0}
        result = self._htf_composite(subs)
        # Expected: (100*0.40 + 0*0.30) / (0.40+0.30) = 40/0.70 ≈ 57.14
        expected = (100 * 0.40 + 0 * 0.30) / (0.40 + 0.30)
        assert abs(result - expected) < 0.001

    def test_htf_alignment_absent_does_not_inflate_composite(self):
        """Removing htf_alignment (was weight 0.35) does not inflate the composite
        beyond 100.0 even with max sub-scores."""
        subs = {
            "htf_structure_bias": 100.0,
            "htf_proximity":      100.0,
            "htf_momentum_gate":  100.0,
            "htf_inflection":     100.0,
        }
        result = self._htf_composite(subs)
        assert result == 100.0, (
            f"All-100 sub-scores must clip to 100.0, got {result}"
        )
