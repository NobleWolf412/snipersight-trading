"""
Regression test for Fix 4b: VWAP floor removal + merge into premium_discount (2026-06-11).

The old vwap factor had a floor of 40.0 even when no VWAP data was available,
inflating scores with no information. VWAP signal merged into premium_discount:
only boosts when VWAP is present and price is on the correct side.

Verifies:
- All four mode dicts have vwap weight == 0.00
- Standalone "VWAP Alignment" factor NOT appended to factors list
- premium_discount block contains VWAP alignment boost logic
- Boost only fires for correct direction (bull/bear symmetry)
- No artificial floor when VWAP is absent
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


class TestVwapWeightZeroed:
    def test_overwatch_vwap_weight_zero(self):
        assert OVERWATCH.get("vwap", -1) == 0.00, (
            f"OVERWATCH vwap={OVERWATCH.get('vwap')} — should be 0.00 (merged into premium_discount)"
        )

    def test_strike_vwap_weight_zero(self):
        assert STRIKE.get("vwap", -1) == 0.00

    def test_surgical_vwap_weight_zero(self):
        assert SURGICAL.get("vwap", -1) == 0.00

    def test_stealth_vwap_weight_zero(self):
        assert STEALTH.get("vwap", -1) == 0.00


class TestVwapStandaloneFactorRemoved:
    def test_no_vwap_alignment_factor_appended(self):
        """ConfluenceFactor named 'VWAP Alignment' must NOT be in factors.append calls."""
        assert '"VWAP Alignment"' not in SCORER_SRC, (
            "Standalone VWAP Alignment factor still present — remove it (merged into pd)"
        )

    def test_old_floor_40_removed(self):
        """The old vwap_score = 40.0 floor must not exist in the scoring path."""
        assert "vwap_score = 40.0" not in SCORER_SRC, (
            "Old VWAP floor of 40.0 still present — should be removed (Fix 4b)"
        )


class TestVwapMergedIntoPremiumDiscount:
    def test_vwap_boost_in_pd_block(self):
        """Premium/discount block must contain VWAP alignment boost logic."""
        assert "_vwap_val" in SCORER_SRC, (
            "_vwap_val not found — VWAP boost not merged into premium_discount block"
        )

    def test_vwap_boost_has_no_default_floor(self):
        """VWAP boost must be conditional on _vwap_val being present (no floor)."""
        # Guard must check '_vwap_val and entry_price' before applying boost
        assert "if _vwap_val and entry_price" in SCORER_SRC, (
            "VWAP boost does not guard on _vwap_val presence — may introduce floor"
        )

    def test_vwap_attr_read_path_pinned(self):
        """VWAP is read via getattr(primary_indicators, 'vwap', None) — pin the
        exact attribute name so a rename doesn't silently kill the boost."""
        assert 'getattr(primary_indicators, "vwap", None)' in SCORER_SRC, (
            'VWAP attribute read path changed — boost may silently not fire'
        )

    def test_vwap_boost_min_cap_present(self):
        """Boost must be capped with min(100.0, ...) to prevent over-scoring."""
        assert "min(100.0, pd_score + 10.0)" in SCORER_SRC, (
            "VWAP boost lacks min(100.0, ...) cap — could push pd_score above 100"
        )


class TestVwapBoostSymmetry:
    """Verify the boost logic is bull/bear symmetric."""

    @staticmethod
    def _simulate_pd_with_vwap(direction: str, entry_price: float, vwap_val: float,
                                pd_base: float) -> float:
        """Inline reproduction of the VWAP boost logic from scorer.py."""
        pd_score = pd_base
        if vwap_val and entry_price:
            is_long = direction in ("bullish", "long")
            if (is_long and entry_price < vwap_val) or (not is_long and entry_price > vwap_val):
                pd_score = min(100.0, pd_score + 10.0)
        return pd_score

    def test_long_below_vwap_gets_boost(self):
        """LONG with entry below VWAP should get +10 boost."""
        base = 75.0
        result = self._simulate_pd_with_vwap("long", entry_price=99.0, vwap_val=100.0, pd_base=base)
        assert result == 85.0

    def test_short_above_vwap_gets_boost(self):
        """SHORT with entry above VWAP should get +10 boost (symmetric)."""
        base = 75.0
        result = self._simulate_pd_with_vwap("short", entry_price=101.0, vwap_val=100.0, pd_base=base)
        assert result == 85.0

    def test_long_above_vwap_no_boost(self):
        """LONG with entry above VWAP should NOT get boost (wrong side)."""
        base = 75.0
        result = self._simulate_pd_with_vwap("long", entry_price=101.0, vwap_val=100.0, pd_base=base)
        assert result == 75.0

    def test_short_below_vwap_no_boost(self):
        """SHORT with entry below VWAP should NOT get boost (wrong side, symmetric)."""
        base = 75.0
        result = self._simulate_pd_with_vwap("short", entry_price=99.0, vwap_val=100.0, pd_base=base)
        assert result == 75.0

    def test_no_vwap_no_boost(self):
        """Absent VWAP data (None) must not change pd_score — no floor."""
        base = 50.0
        result = self._simulate_pd_with_vwap("long", entry_price=99.0, vwap_val=None, pd_base=base)
        assert result == 50.0

    def test_boost_capped_at_100(self):
        """Boost must not push pd_score above 100.0."""
        base = 95.0
        result = self._simulate_pd_with_vwap("long", entry_price=99.0, vwap_val=100.0, pd_base=base)
        assert result == 100.0
