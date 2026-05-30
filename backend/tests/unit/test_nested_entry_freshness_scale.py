"""
Regression for hot-path audit bug #11 (3_CORRECTNESS): _find_nested_entry_ob scored
candidate trigger OBs with `freshness_score * 2 + zone_freshness + width/atr +
(1-mitigation)*2`, but freshness_score is on a 0-100 scale while mitigation/width are
0-1 / ATR-units. So the freshness terms (0-200) swamped mitigation (0-2) and zone-width
(~0-5) by ~100x — selection degenerated into "highest raw freshness," ignoring
mitigation and zone size, and could pick a fresh-but-heavily-mitigated trigger as the
live entry zone. (The `0.7` default gave away the original 0-1 intent.)

Fix: normalize freshness to 0-1 (`/100`, default 70.0) so the weighted terms are
comparable and mitigation/zone size genuinely influence selection.

See backend/diagnostics/decisions/2026-05-29__hotpath-robustness-audit.md (bug #11).
Per CLAUDE.md §14 rubric 4 (negative+positive), §16 rubric 12 (LONG/SHORT symmetry).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from backend.shared.models.smc import OrderBlock
from backend.strategy.planner.entry_engine import _find_nested_entry_ob


def _ob(direction: str, low: float, high: float, freshness: float, mitigation: float) -> OrderBlock:
    return OrderBlock(
        timeframe="4H", direction=direction, high=high, low=low,
        timestamp=datetime.utcnow() - timedelta(days=1),
        displacement_strength=50.0, mitigation_level=mitigation, freshness_score=freshness,
    )


def test_long_prefers_unmitigated_over_max_freshness():
    """LONG: trigger A is max-fresh (95) but heavily mitigated (0.9); trigger B is less
    fresh (60) but unmitigated (0.0). Post-fix, mitigation matters → B wins. Pre-fix,
    freshness*2 (190 vs 120) swamped the mitigation term and A wrongly won."""
    zone = _ob("bullish", low=90.0, high=100.0, freshness=80.0, mitigation=0.0)
    trig_a = _ob("bullish", low=98.0, high=99.0, freshness=95.0, mitigation=0.9)
    trig_b = _ob("bullish", low=95.0, high=97.0, freshness=60.0, mitigation=0.0)

    result = _find_nested_entry_ob(True, [zone], [trig_a, trig_b], current_price=100.0, atr=2.0)
    assert result is not None
    trigger, _ = result
    assert trigger is trig_b  # unmitigated wins (was trig_a pre-fix)


def test_short_prefers_unmitigated_over_max_freshness():
    """SHORT mirror (§16 rubric 12): triggers above price; same freshness/mitigation tradeoff."""
    zone = _ob("bearish", low=100.0, high=110.0, freshness=80.0, mitigation=0.0)
    trig_a = _ob("bearish", low=101.0, high=102.0, freshness=95.0, mitigation=0.9)
    trig_b = _ob("bearish", low=103.0, high=105.0, freshness=60.0, mitigation=0.0)

    result = _find_nested_entry_ob(False, [zone], [trig_a, trig_b], current_price=100.0, atr=2.0)
    assert result is not None
    trigger, _ = result
    assert trigger is trig_b


def test_freshness_still_wins_when_mitigation_equal():
    """Positive pair: when mitigation is equal, the fresher trigger still wins — the fix
    rebalances the terms, it does not stop freshness from mattering."""
    zone = _ob("bullish", low=90.0, high=100.0, freshness=80.0, mitigation=0.0)
    fresher = _ob("bullish", low=98.0, high=99.0, freshness=90.0, mitigation=0.1)
    staler = _ob("bullish", low=95.0, high=97.0, freshness=50.0, mitigation=0.1)

    result = _find_nested_entry_ob(True, [zone], [fresher, staler], current_price=100.0, atr=2.0)
    assert result is not None
    trigger, _ = result
    assert trigger is fresher
