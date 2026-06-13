"""
Regression tests for the liquidity-pool stop buffer (risk_engine._buffer_stop_from_liquidity).

Guards the Phase-2 dead-branch fix:
  decisions/2026-06-13__stop-pool-phase2-deadbranch-fix-design.md
  decisions/2026-06-13__stop-in-liquidity-pool-baseline.md

The static PWL/PWH/PDH/PDL branch was dead in production (getattr on the to_dict() dict
returned None for every trade). These tests prove it now fires from BOTH the production dict
form and the KeyLevels dataclass form, on BOTH directions (bull/bear symmetry, §16 Rubric 12),
that the push is bounded to exactly 0.3 ATR beyond the pool, and that it does NOT false-fire
on noise (§16 Rubric 4). multi_tf_data is None throughout to isolate the static branch from the
EQH/EQL scan.
"""

import pytest

from backend.strategy.planner.risk_engine import _buffer_stop_from_liquidity, _pool_price
from backend.analysis.key_levels import KeyLevels, KeyLevel
from datetime import datetime, timezone


ATR = 1.0
BUF = 0.3 * ATR


def _kl_obj(**levels):
    """KeyLevels dataclass with the given attrs set to KeyLevel objects."""
    ts = datetime(2026, 6, 1, tzinfo=timezone.utc)
    kw = {k: KeyLevel(price=v, level_type=k.upper(), timestamp=ts, timeframe="1d")
          for k, v in levels.items()}
    return KeyLevels(symbol="X", **kw)


# ── Bull/bear symmetry: the dict form (production) now fires ───────────────────

def test_long_dict_form_buffers_below_pwl():
    # LONG entry 110, stop 100; PWL @ 99.9 is 0.1 ATR below the stop (inside 0.3-ATR window).
    kl = _kl_obj(pwl=99.9).to_dict()
    new_stop, rat = _buffer_stop_from_liquidity(
        stop_level=100.0, entry_ref=110.0, is_bullish=True, atr=ATR,
        multi_tf_data=None, key_levels=kl,
    )
    assert new_stop == pytest.approx(99.9 - BUF)   # pushed BELOW the pool
    assert "liquidity pool" in rat


def test_short_dict_form_buffers_above_pwh_symmetric():
    # SHORT mirror: entry 90, stop 100; PWH @ 100.1 is 0.1 ATR above the stop.
    kl = _kl_obj(pwh=100.1).to_dict()
    new_stop, rat = _buffer_stop_from_liquidity(
        stop_level=100.0, entry_ref=90.0, is_bullish=False, atr=ATR,
        multi_tf_data=None, key_levels=kl,
    )
    assert new_stop == pytest.approx(100.1 + BUF)  # pushed ABOVE the pool
    assert "liquidity pool" in rat


# ── Object form (KeyLevels dataclass) also fires — representation-robust ───────

def test_long_object_form_buffers_below_pdl():
    kl = _kl_obj(pdl=99.85)
    new_stop, _ = _buffer_stop_from_liquidity(
        stop_level=100.0, entry_ref=110.0, is_bullish=True, atr=ATR,
        multi_tf_data=None, key_levels=kl,
    )
    assert new_stop == pytest.approx(99.85 - BUF)


def test_short_object_form_buffers_above_pdh_symmetric():
    kl = _kl_obj(pdh=100.15)
    new_stop, _ = _buffer_stop_from_liquidity(
        stop_level=100.0, entry_ref=90.0, is_bullish=False, atr=ATR,
        multi_tf_data=None, key_levels=kl,
    )
    assert new_stop == pytest.approx(100.15 + BUF)


# ── Bounded: push is exactly 0.3 ATR beyond the pool (RR cannot blow out) ──────

def test_buffer_push_is_bounded_to_0_3_atr_beyond_pool():
    kl = _kl_obj(pwl=99.95).to_dict()
    new_stop, _ = _buffer_stop_from_liquidity(
        stop_level=100.0, entry_ref=110.0, is_bullish=True, atr=ATR,
        multi_tf_data=None, key_levels=kl,
    )
    # distance from the pool is exactly the buffer, never more
    assert abs(new_stop - 99.95) == pytest.approx(BUF)


# ── Negative tests: no false fire on noise ────────────────────────────────────

def test_no_fire_when_pool_outside_window():
    # PWL @ 99.0 is 1.0 ATR below the stop -> outside the 0.3-ATR window -> unchanged.
    kl = _kl_obj(pwl=99.0).to_dict()
    new_stop, rat = _buffer_stop_from_liquidity(
        stop_level=100.0, entry_ref=110.0, is_bullish=True, atr=ATR,
        multi_tf_data=None, key_levels=kl,
    )
    assert new_stop == 100.0 and rat == ""


def test_no_fire_wrong_side_pool():
    # LONG with a PWL ABOVE entry_ref (wrong side) is ignored.
    kl = _kl_obj(pwl=115.0).to_dict()
    new_stop, rat = _buffer_stop_from_liquidity(
        stop_level=100.0, entry_ref=110.0, is_bullish=True, atr=ATR,
        multi_tf_data=None, key_levels=kl,
    )
    assert new_stop == 100.0 and rat == ""


@pytest.mark.parametrize("kl", [None, {}, {"pwl": None}, {"pwl": {"price": None}}, {"pwl": "x"}])
def test_no_raise_on_missing_or_malformed_key_levels(kl):
    new_stop, rat = _buffer_stop_from_liquidity(
        stop_level=100.0, entry_ref=110.0, is_bullish=True, atr=ATR,
        multi_tf_data=None, key_levels=kl,
    )
    assert new_stop == 100.0 and rat == ""


def test_no_fire_when_atr_nonpositive():
    kl = _kl_obj(pwl=99.9).to_dict()
    new_stop, rat = _buffer_stop_from_liquidity(
        stop_level=100.0, entry_ref=110.0, is_bullish=True, atr=0.0,
        multi_tf_data=None, key_levels=kl,
    )
    assert new_stop == 100.0 and rat == ""


# ── _pool_price helper: both representations + guards ──────────────────────────

def test_pool_price_resolves_dict_and_object_and_rejects_garbage():
    assert _pool_price({"pwl": {"price": 12.5, "swept": False}}, "pwl") == 12.5
    assert _pool_price({"pwl": 12.5}, "pwl") == 12.5                       # flat dict tolerated
    assert _pool_price(_kl_obj(pwl=12.5), "pwl") == 12.5                   # dataclass.price
    assert _pool_price({"pwl": None}, "pwl") is None
    assert _pool_price({"pwl": {"price": 0}}, "pwl") is None               # non-positive rejected
    assert _pool_price(None, "pwl") is None
    assert _pool_price({}, "pdh") is None
