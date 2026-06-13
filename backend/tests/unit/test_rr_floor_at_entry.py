"""
Regression tests for the entry realized-RR floor (fill-geometry guard).
decisions/2026-06-13__fill-geometry-distortion.md

Covers the single-source-of-truth helper `_entry_realized_rr` used by BOTH the
entry RR-floor gate and the journal `realized_rr` key. Symmetry (LONG/SHORT) and
negative tests (healthy geometry does NOT trip the floor) per §16 Rubrics 4 & 12.
"""

import pytest

from backend.bot.paper_trading_service import _entry_realized_rr, CompletedTrade
from datetime import datetime, timezone


# ── Helper: symmetry ──────────────────────────────────────────────────────────

def test_realized_rr_long_healthy():
    # LONG entry 100, stop 98 (risk 2), TP1 104 (reward 4) -> RR 2.0
    assert _entry_realized_rr(100.0, 98.0, [104.0, 108.0]) == pytest.approx(2.0)


def test_realized_rr_short_healthy_symmetric():
    # SHORT entry 100, stop 102 (risk 2), TP1 96 (reward 4) -> RR 2.0
    # Mirror image of the LONG case — must yield identical RR (bull/bear symmetry).
    assert _entry_realized_rr(100.0, 102.0, [96.0, 92.0]) == pytest.approx(2.0)


def test_realized_rr_long_collapsed():
    # LONG entry chased up to 103.5, stop 98 (risk 5.5), TP1 104 (reward 0.5) -> RR ~0.09
    rr = _entry_realized_rr(103.5, 98.0, [104.0])
    assert rr < 1.0 and rr == pytest.approx(0.5 / 5.5)


def test_realized_rr_short_collapsed_symmetric():
    # SHORT entry chased down to 96.5, stop 102 (risk 5.5), TP1 96 (reward 0.5) -> RR ~0.09
    rr = _entry_realized_rr(96.5, 102.0, [96.0])
    assert rr < 1.0 and rr == pytest.approx(0.5 / 5.5)


def test_realized_rr_picks_nearest_target():
    # Nearest target to entry is TP1 — reward measured to it, not a far target.
    # entry 100, stop 98 (risk 2), targets [101 (near), 110] -> reward 1 -> RR 0.5
    assert _entry_realized_rr(100.0, 98.0, [110.0, 101.0]) == pytest.approx(0.5)


# ── Helper: guard rails (no false geometry) ──────────────────────────────────

@pytest.mark.parametrize("entry,stop,targets", [
    (0.0, 98.0, [104.0]),      # no entry
    (100.0, 0.0, [104.0]),     # no stop
    (100.0, 98.0, []),         # no targets
    (100.0, 100.0, [104.0]),   # zero risk (entry == stop)
])
def test_realized_rr_unavailable_returns_zero(entry, stop, targets):
    assert _entry_realized_rr(entry, stop, targets) == 0.0


# ── Journal: realized_rr key is emitted and honest ───────────────────────────

def _trade(**kw):
    base = dict(
        trade_id="T", symbol="ADA/USDT", direction="SHORT",
        entry_price=0.169644, exit_price=0.1716, quantity=1.0,
        entry_time=datetime.now(timezone.utc), exit_time=datetime.now(timezone.utc),
        pnl=-1.0, pnl_pct=-1.0, exit_reason="session_stopped",
    )
    base.update(kw)
    return CompletedTrade(**base)


def test_journal_realized_rr_exposes_collapse():
    # The ADA case: recorded RR 2.09 but realized geometry off the fill is ~0.29.
    t = _trade(
        risk_reward_ratio=2.0877,
        stop_loss_level=0.1759,
        target_levels=[0.1678],
    )
    d = t.to_dict()
    assert "realized_rr" in d
    # reward = |0.1678 - 0.169644| = 0.001844 ; risk = |0.169644 - 0.1759| = 0.006256
    assert d["realized_rr"] == pytest.approx(0.001844 / 0.006256, rel=1e-3)
    assert d["realized_rr"] < 0.5           # collapsed
    assert d["risk_reward_ratio"] == pytest.approx(2.0877)  # planned value untouched


def test_journal_realized_rr_zero_when_no_geometry():
    # Older rows without stored levels degrade gracefully to 0.0, never raise.
    t = _trade(risk_reward_ratio=2.0, stop_loss_level=0.0, target_levels=[])
    assert t.to_dict()["realized_rr"] == 0.0
