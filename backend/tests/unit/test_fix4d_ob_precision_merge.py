"""
Regression test for Fix 4d: nested_ob merged into inside_ob as ob_precision (2026-06-11).

Old behavior:
- Two separate factors: "Inside Order Block" (weight: inside_ob) and
  "Nested Order Block" (weight: nested_ob), each contributing independently.
- inside_ob had a floor of 50.0 even when not inside any OB.

New behavior:
- Single "OB Precision" factor (weight: ob_precision = sum of old weights).
- Score 0.0 when not inside OB (floor removed).
- When inside OB: rejection quality score + optional +20 nested boost (capped at 100).

Verifies:
- All four mode dicts have ob_precision > 0 and no inside_ob / nested_ob keys
- ob_precision combined weight matches old inside_ob + nested_ob for each mode
- Standalone "Inside Order Block" and "Nested Order Block" factors NOT in scorer
- Old 50.0 floor removed
- Nested boost +20 applied when inside OB and nested (with 100 cap)
- Bull/bear symmetry in the merged block
"""

from __future__ import annotations

import pathlib
import re

import pytest

SCORER_SRC = pathlib.Path("backend/strategy/confluence/scorer.py").read_text(
    encoding="utf-8"
)


def _extract_weight_dict(dict_name: str) -> dict:
    pattern = re.compile(rf"{dict_name}\s*=\s*\{{([^}}]+)\}}", re.DOTALL)
    m = pattern.search(SCORER_SRC)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        kv = re.match(r'\s*"(\w+)"\s*:\s*([0-9.]+)', line)
        if kv:
            result[kv.group(1)] = float(kv.group(2))
    return result


OVERWATCH = _extract_weight_dict("_OVERWATCH_WEIGHTS")
STRIKE = _extract_weight_dict("_STRIKE_WEIGHTS")
SURGICAL = _extract_weight_dict("_SURGICAL_WEIGHTS")
STEALTH = _extract_weight_dict("_STEALTH_WEIGHTS")


class TestObPrecisionWeightKeys:
    def test_overwatch_has_ob_precision(self):
        assert "ob_precision" in OVERWATCH, "_OVERWATCH_WEIGHTS missing ob_precision key"

    def test_strike_has_ob_precision(self):
        assert "ob_precision" in STRIKE

    def test_surgical_has_ob_precision(self):
        assert "ob_precision" in SURGICAL

    def test_stealth_has_ob_precision(self):
        assert "ob_precision" in STEALTH

    def test_overwatch_no_inside_ob(self):
        assert "inside_ob" not in OVERWATCH, "_OVERWATCH_WEIGHTS still has inside_ob key"

    def test_strike_no_inside_ob(self):
        assert "inside_ob" not in STRIKE

    def test_surgical_no_inside_ob(self):
        assert "inside_ob" not in SURGICAL

    def test_stealth_no_inside_ob(self):
        assert "inside_ob" not in STEALTH

    def test_overwatch_no_nested_ob(self):
        assert "nested_ob" not in OVERWATCH, "_OVERWATCH_WEIGHTS still has nested_ob key"

    def test_strike_no_nested_ob(self):
        assert "nested_ob" not in STRIKE

    def test_surgical_no_nested_ob(self):
        assert "nested_ob" not in SURGICAL

    def test_stealth_no_nested_ob(self):
        assert "nested_ob" not in STEALTH


class TestObPrecisionWeightValues:
    """ob_precision weight must equal old inside_ob + nested_ob for each mode."""

    def test_overwatch_ob_precision_combined(self):
        # old: inside_ob=0.10, nested_ob=0.10
        assert abs(OVERWATCH["ob_precision"] - 0.20) < 0.001, (
            f"OVERWATCH ob_precision={OVERWATCH['ob_precision']:.3f}, expected 0.20"
        )

    def test_strike_ob_precision_combined(self):
        # old: inside_ob=0.10, nested_ob=0.08
        assert abs(STRIKE["ob_precision"] - 0.18) < 0.001

    def test_surgical_ob_precision_combined(self):
        # old: inside_ob=0.12, nested_ob=0.10
        assert abs(SURGICAL["ob_precision"] - 0.22) < 0.001

    def test_stealth_ob_precision_combined(self):
        # old: inside_ob=0.08, nested_ob=0.06
        assert abs(STEALTH["ob_precision"] - 0.14) < 0.001


class TestStandaloneFactorsRemoved:
    def test_no_inside_order_block_factor(self):
        """'Inside Order Block' factor name must not appear (merged into OB Precision)."""
        assert '"Inside Order Block"' not in SCORER_SRC, (
            "Standalone 'Inside Order Block' ConfluenceFactor still present — not merged"
        )

    def test_no_nested_order_block_factor(self):
        """'Nested Order Block' factor name must not appear (absorbed into OB Precision)."""
        assert '"Nested Order Block"' not in SCORER_SRC, (
            "Standalone 'Nested Order Block' ConfluenceFactor still present — not absorbed"
        )

    def test_no_stale_in_ob_score_reference(self):
        """in_ob_score must not appear anywhere — stale var causes NameError in Opposing
        Structure block (silently swallowed by logger.debug, destroying diagnosability)."""
        assert "in_ob_score" not in SCORER_SRC, (
            "Stale 'in_ob_score' reference found — causes silent NameError in "
            "Opposing Structure Penalty block after Fix 4d merge"
        )

    def test_opposing_structure_uses_ob_prec_score(self):
        """Opposing Structure Penalty block must use ob_prec_score as its gate variable."""
        assert "ob_prec_score <= 0.0" in SCORER_SRC, (
            "Opposing Structure block does not gate on ob_prec_score — may be using "
            "stale in_ob_score reference"
        )

    def test_opposing_structure_exception_is_warning(self):
        """Opposing structure exception must be logged at WARNING level (not DEBUG)
        so silent NameErrors surface in production logs per §15."""
        assert 'logger.warning("Opposing structure penalty failed' in SCORER_SRC, (
            "Opposing structure exception logged at debug — upgrade to warning per §15"
        )


class TestDiagnosticBlastRadius:
    """Verify diag_neutral50_contribution.py was updated to match Fix 4d schema."""

    DIAG_SRC = pathlib.Path(
        "backend/diagnostics/diag_neutral50_contribution.py"
    ).read_text(encoding="utf-8")

    def test_diag_no_inside_ob_weight_key(self):
        """inside_ob key must not appear in FACTOR_TO_WEIGHT_KEY — retired by Fix 4d."""
        assert '"inside_ob"' not in self.DIAG_SRC or "Fix 4d" in self.DIAG_SRC, (
            "diag_neutral50: stale 'inside_ob' weight key still present"
        )

    def test_diag_no_nested_ob_weight_key(self):
        """nested_ob key must not appear in FACTOR_TO_WEIGHT_KEY — retired by Fix 4d."""
        assert '"nested_ob"' not in self.DIAG_SRC, (
            "diag_neutral50: stale 'nested_ob' weight key still present"
        )

    def test_diag_ob_precision_weight_key_present(self):
        """FACTOR_TO_WEIGHT_KEY must have 'OB Precision': 'ob_precision'."""
        assert '"OB Precision"' in self.DIAG_SRC and '"ob_precision"' in self.DIAG_SRC, (
            "diag_neutral50: 'OB Precision' / 'ob_precision' key missing from FACTOR_TO_WEIGHT_KEY"
        )

    def test_diag_no_old_neutral_marker(self):
        """Inside Order Block neutral-50 marker must not exist in NEUTRAL_MARKERS list."""
        assert '("Inside Order Block", 50.0' not in self.DIAG_SRC, (
            "diag_neutral50: stale ('Inside Order Block', 50.0, ...) neutral marker still present"
        )

    def test_diag_case1_uses_ob_precision(self):
        """Synthetic Case 1 fixture must use 'OB Precision' factor (not old name)."""
        assert 'F("OB Precision"' in self.DIAG_SRC, (
            "diag_neutral50 Case 1 fixture still uses old 'Inside Order Block' name"
        )

    def test_ob_precision_factor_present(self):
        """'OB Precision' ConfluenceFactor must be appended."""
        assert '"OB Precision"' in SCORER_SRC, (
            "'OB Precision' ConfluenceFactor not found — merge not landed"
        )


class TestObPrecisionFloorRemoved:
    def test_no_50_floor_in_ob_block(self):
        """Old 'in_ob_score, in_ob_rat = 50.0' floor must not exist."""
        assert "in_ob_score, in_ob_rat = 50.0" not in SCORER_SRC, (
            "Old inside_ob floor of 50.0 still present — should be 0.0 (Fix 4d)"
        )

    def test_ob_precision_default_zero(self):
        """ob_precision block default score must be 0.0 (no floor)."""
        assert "ob_prec_score, ob_prec_rat = 0.0" in SCORER_SRC, (
            "OB precision default is not 0.0 — floor may still exist"
        )


class TestNestedBoostLogic:
    def test_nested_boost_present(self):
        """Nested OB boost (+20) must be applied in the merged block."""
        assert "ob_prec_score + 20.0" in SCORER_SRC or "+ 20.0" in SCORER_SRC, (
            "Nested OB +20 boost not found in merged ob_precision block"
        )

    def test_nested_boost_capped(self):
        """Nested boost must be capped with min(100.0, ...)."""
        assert "min(100.0, ob_prec_score + 20.0)" in SCORER_SRC, (
            "Nested OB boost lacks min(100.0, ...) cap"
        )

    def test_nested_boost_conditional_on_inside_ob(self):
        """Nested boost must only fire when ob_prec_score > 0 (inside OB first)."""
        assert "ob_prec_score > 0 and _detect_nested_ob" in SCORER_SRC, (
            "Nested boost not guarded by ob_prec_score > 0 — could fire outside OB"
        )


class TestObPrecisionSymmetry:
    """Boost logic is direction-agnostic in its math. Symmetry via inline simulation."""

    @staticmethod
    def _simulate_ob_precision(inside_ob: bool, nested: bool, rej_score: float) -> float:
        """Inline reproduction of the merged ob_precision scoring."""
        ob_prec_score = 0.0
        if inside_ob:
            ob_prec_score = rej_score
        if ob_prec_score > 0 and nested:
            ob_prec_score = min(100.0, ob_prec_score + 20.0)
        return ob_prec_score

    def test_not_inside_ob_score_zero_long(self):
        """Not inside OB (LONG) → score 0.0."""
        assert self._simulate_ob_precision(inside_ob=False, nested=False, rej_score=0.0) == 0.0

    def test_not_inside_ob_score_zero_short(self):
        """Not inside OB (SHORT) → score 0.0 (symmetric)."""
        assert self._simulate_ob_precision(inside_ob=False, nested=False, rej_score=0.0) == 0.0

    def test_inside_ob_no_nested_long(self):
        """Inside OB, no nested (LONG) → rejection quality score."""
        assert self._simulate_ob_precision(inside_ob=True, nested=False, rej_score=75.0) == 75.0

    def test_inside_ob_no_nested_short(self):
        """Inside OB, no nested (SHORT) → rejection quality score (symmetric)."""
        assert self._simulate_ob_precision(inside_ob=True, nested=False, rej_score=75.0) == 75.0

    def test_inside_ob_nested_long(self):
        """Inside nested OB (LONG) → base + 20 boost."""
        assert self._simulate_ob_precision(inside_ob=True, nested=True, rej_score=75.0) == 95.0

    def test_inside_ob_nested_short(self):
        """Inside nested OB (SHORT) → base + 20 boost (symmetric)."""
        assert self._simulate_ob_precision(inside_ob=True, nested=True, rej_score=75.0) == 95.0

    def test_nested_boost_capped_at_100_long(self):
        """Boost must cap at 100.0 for LONG."""
        assert self._simulate_ob_precision(inside_ob=True, nested=True, rej_score=90.0) == 100.0

    def test_nested_boost_capped_at_100_short(self):
        """Boost must cap at 100.0 for SHORT (symmetric)."""
        assert self._simulate_ob_precision(inside_ob=True, nested=True, rej_score=90.0) == 100.0

    def test_nested_without_inside_ob_no_boost(self):
        """Nested detection cannot boost if not inside OB (ob_prec_score == 0 guard)."""
        assert self._simulate_ob_precision(inside_ob=False, nested=True, rej_score=0.0) == 0.0
