"""
Tests for Orchestrator._derive_btc_impulse — regime-aware Gate 3 trigger.

Bug context — Adversarial review of cache-TTL fix (a61589c) flagged Gate 3's
unconditional fire on |btc_velocity_1h| >= 1.0% as a more brittle layer than
the cache itself. Historical empirical study (this session):

  - 17,322 BTC 1h candles, 2024-06 → 2026-05 (bull regime)
  - 9,900 BTC 1h candles, 2021-11 → 2022-12 (bear regime)
  - 7-alt cross-tab (ETH/SOL/LINK/DOGE/AVAX/ATOM/DOT) for each window

Findings:
  - Bull market, BTC dump ≤-1.0%, N=421: 7 of 8 alts BOUNCE +0.5 to +1.1%
    over the next 24h (alts mean-revert harder than BTC).
  - Bear market, BTC dump ≤-1.0%, N=514: every alt still BOUNCES (+0.05 to
    +0.63%) even as BTC drifts -0.14%.
  - Bear market strong_down regime, BTC dump, N=225: alts BOUNCE +0.4 to
    +1.1% (the case Gate 3 was specifically designed to protect — alts
    mean-revert harder, not get squeezed).
  - The ONLY regime where alts demonstrably get squeezed instead of
    bouncing: BTC dump in `strong_up` regime (relief rally fade), N=35
    small sample, mixed result.

Fix (Option A): only set _btc_impulse when BTC moves COUNTER to the broader
regime trend. In trend-aligned conditions (dump in down regime, pump in up
regime), the data shows alts mean-revert — Gate 3 should not fire.

Per CLAUDE.md §10 (bull/bear symmetry — the new logic is symmetric across
LONG/SHORT block sides), §14 rubric 4 (negative tests paired with positive),
§16 rubric 12 (bull/bear pairs in every direction-aware test).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.engine.orchestrator import Orchestrator


def _make_orchestrator_stub(regime_trend: str | None = "sideways"):
    """Construct a minimal stub that exposes self.current_regime for the
    helper. Bypasses __init__ since the orchestrator has heavy dependencies
    and we only need attribute access in the helper."""
    orch = Orchestrator.__new__(Orchestrator)
    if regime_trend is None:
        orch.current_regime = None
    else:
        dims = SimpleNamespace(trend=regime_trend)
        orch.current_regime = SimpleNamespace(dimensions=dims)
    return orch


def _macro(btc_vel: float):
    return SimpleNamespace(btc_velocity_1h=btc_vel)


# ──────────────────────────────────────────────────────────────────────
# Positive fires — only in counter-trend conditions
# ──────────────────────────────────────────────────────────────────────


def test_dump_in_strong_up_regime_fires_strong_down():
    """BTC -1.5% in confirmed bull regime → relief rally fade → Gate 3
    fires to block LONG alts. The one case where alts demonstrably get
    squeezed instead of bouncing."""
    orch = _make_orchestrator_stub("strong_up")
    assert orch._derive_btc_impulse(_macro(-1.5), "ETH/USDT") == "strong_down"


def test_pump_in_strong_down_regime_fires_strong_up():
    """BTC +1.5% in confirmed bear regime → dead-cat bounce → Gate 3 fires
    to block SHORT alts. Mirror of the LONG-block trigger."""
    orch = _make_orchestrator_stub("strong_down")
    assert orch._derive_btc_impulse(_macro(1.5), "ETH/USDT") == "strong_up"


# ──────────────────────────────────────────────────────────────────────
# Negative — trend-aligned moves do NOT fire
# ──────────────────────────────────────────────────────────────────────


def test_dump_in_strong_down_regime_does_not_fire():
    """BTC -1.5% in `strong_down` regime — trend-aligned dump.
    Empirical: alts BOUNCE +0.4 to +1.1% over next 24h. Gate 3 firing
    here was the dda4d192 false-positive pattern that wasted 84 LONGs."""
    orch = _make_orchestrator_stub("strong_down")
    assert orch._derive_btc_impulse(_macro(-1.5), "ETH/USDT") is None


def test_dump_in_up_regime_does_not_fire():
    """BTC -1.05% in `up` regime — the EXACT dda4d192 scenario.
    Empirical: bull-market `up` regime mild dumps → alts bounce +0.5 to
    +1.0% over 24h. Gate 3 must NOT fire here."""
    orch = _make_orchestrator_stub("up")
    assert orch._derive_btc_impulse(_macro(-1.05), "ETH/USDT") is None


def test_dump_in_sideways_does_not_fire():
    """Sideways regime: empirical alt response is mean-reverting on
    average. Don't fire."""
    orch = _make_orchestrator_stub("sideways")
    assert orch._derive_btc_impulse(_macro(-1.5), "ETH/USDT") is None


def test_pump_in_strong_up_regime_does_not_fire():
    """BTC +1.5% in `strong_up` — trend-aligned pump, no squeeze evidence
    for alt SHORTs. Don't fire."""
    orch = _make_orchestrator_stub("strong_up")
    assert orch._derive_btc_impulse(_macro(1.5), "ETH/USDT") is None


def test_pump_in_up_regime_does_not_fire():
    """Bull market pumps in `up` regime: alts split — some up, some flat.
    Insufficient signal to fire SHORT-block."""
    orch = _make_orchestrator_stub("up")
    assert orch._derive_btc_impulse(_macro(1.5), "ETH/USDT") is None


# ──────────────────────────────────────────────────────────────────────
# Threshold floor — sub-1% moves never fire regardless of regime
# ──────────────────────────────────────────────────────────────────────


def test_subthreshold_dump_never_fires():
    """Moves below the ±1.0% threshold are noise (median abs 1h pct is
    ~0.2%). Never classify as 'strong' impulse regardless of regime."""
    for regime in ("strong_up", "up", "sideways", "down", "strong_down"):
        orch = _make_orchestrator_stub(regime)
        assert orch._derive_btc_impulse(_macro(-0.99), "ETH/USDT") is None
        assert orch._derive_btc_impulse(_macro(-0.5), "ETH/USDT") is None


def test_subthreshold_pump_never_fires():
    for regime in ("strong_up", "up", "sideways", "down", "strong_down"):
        orch = _make_orchestrator_stub(regime)
        assert orch._derive_btc_impulse(_macro(0.99), "ETH/USDT") is None
        assert orch._derive_btc_impulse(_macro(0.5), "ETH/USDT") is None


# ──────────────────────────────────────────────────────────────────────
# Edge cases — symbol exclusion, null context
# ──────────────────────────────────────────────────────────────────────


def test_btc_symbol_never_fires_against_itself():
    """The bot can scan BTC/USDT as a tradeable symbol. Gate 3 must not
    fire when BTC is the symbol being evaluated — it's not an alt."""
    orch = _make_orchestrator_stub("strong_up")
    assert orch._derive_btc_impulse(_macro(-1.5), "BTC/USDT") is None
    assert orch._derive_btc_impulse(_macro(-1.5), "BTCUSDT") is None
    assert orch._derive_btc_impulse(_macro(-1.5), "BTC/USDC") is None


def test_no_macro_context_returns_none():
    """Defensive null check — no macro means no impulse to gate on."""
    orch = _make_orchestrator_stub("strong_up")
    assert orch._derive_btc_impulse(None, "ETH/USDT") is None


def test_missing_regime_defaults_to_no_fire():
    """If global regime hasn't been classified yet (early scan, edge case),
    default to 'sideways' which never fires. Safer to under-fire than to
    over-fire on an unknown-regime guess."""
    orch = _make_orchestrator_stub(None)  # current_regime is None
    assert orch._derive_btc_impulse(_macro(-1.5), "ETH/USDT") is None
    assert orch._derive_btc_impulse(_macro(1.5), "ETH/USDT") is None
