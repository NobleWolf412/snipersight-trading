"""
Regression test for Fix 4a: kill_zone weight zeroed for OVERWATCH mode (2026-06-11).

OVERWATCH/macro_surveillance is a 4h swing mode. Kill zones (London/NY open etc.)
are intraday session timing signals irrelevant to multi-hour swing entries.
Setting weight=0.00 removes kill_zone from OVERWATCH scoring entirely.

Verifies:
- OVERWATCH kill_zone weight == 0.00
- Other modes (STRIKE, SURGICAL, STEALTH) still have non-zero kill_zone weight
- Negative: kill_zone weight NOT zeroed in intraday modes
"""

from __future__ import annotations

import pathlib
import re

import pytest

SCORER_SRC = pathlib.Path("backend/strategy/confluence/scorer.py").read_text(
    encoding="utf-8"
)

# Extract weight dicts by parsing their literal bodies
def _extract_weight_dict(dict_name: str) -> dict:
    """Parse a simple single-line-per-entry weight dict from scorer.py."""
    pattern = re.compile(
        rf"{dict_name}\s*=\s*\{{([^}}]+)\}}", re.DOTALL
    )
    m = pattern.search(SCORER_SRC)
    if not m:
        return {}
    body = m.group(1)
    result = {}
    for line in body.splitlines():
        line = line.strip()
        kv = re.match(r'"(\w+)"\s*:\s*([0-9.]+)', line)
        if kv:
            result[kv.group(1)] = float(kv.group(2))
    return result


OVERWATCH = _extract_weight_dict("_OVERWATCH_WEIGHTS")
STRIKE = _extract_weight_dict("_STRIKE_WEIGHTS")
SURGICAL = _extract_weight_dict("_SURGICAL_WEIGHTS")
STEALTH = _extract_weight_dict("_STEALTH_WEIGHTS")


class TestKillZoneOverwatchZeroed:
    def test_overwatch_kill_zone_is_zero(self):
        """_OVERWATCH_WEIGHTS must have kill_zone == 0.00."""
        assert "kill_zone" in OVERWATCH, "_OVERWATCH_WEIGHTS missing kill_zone key"
        assert OVERWATCH["kill_zone"] == 0.00, (
            f"OVERWATCH kill_zone = {OVERWATCH['kill_zone']} but must be 0.00 "
            "(intraday session timing irrelevant for 4h swing mode)"
        )

    def test_strike_kill_zone_nonzero(self):
        """STRIKE (intraday) must retain non-zero kill_zone weight."""
        assert STRIKE.get("kill_zone", 0) > 0, (
            "STRIKE kill_zone weight is 0 — intraday mode should value session timing"
        )

    def test_surgical_kill_zone_nonzero(self):
        """SURGICAL must retain non-zero kill_zone weight."""
        assert SURGICAL.get("kill_zone", 0) > 0, (
            "SURGICAL kill_zone weight is 0 — precision intraday mode should value session timing"
        )

    def test_stealth_kill_zone_nonzero(self):
        """STEALTH must retain non-zero kill_zone weight."""
        assert STEALTH.get("kill_zone", 0) > 0, (
            "STEALTH kill_zone weight is 0 — intraday-balanced mode should value session timing"
        )
