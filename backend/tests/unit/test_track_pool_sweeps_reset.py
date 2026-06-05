"""
Regression for SMC routing audit defect F1 (2026-05-31 audit, #2 RISKY):
track_pool_sweeps (liquidity_sweeps.py) only assigned `swept`/`swept_ts`/`swept_idx`
inside `if swept_mask.any()`, but read `if swept:` unconditionally. Loop-scoped, never
reset per iteration → TWO bugs:
  1. NameError the first time an unswept pool reached the `if swept` check.
  2. Stale-value leak: an unswept pool silently inherited a PRIOR pool's swept flag +
     swept_index/swept_timestamp.

Fix: reset swept/swept_ts/swept_idx = False/None/None at the top of each iteration.

Per CLAUDE.md §11 (loud failures), §16 rubric 4 (negative test paired with positive),
rubric 12 (bull/bear symmetry — equal_highs AND equal_lows exercised).
"""
from __future__ import annotations

import pandas as pd

from backend.shared.models.smc import LiquidityPool
from backend.strategy.smc.liquidity_sweeps import track_pool_sweeps


def _df():
    """5-bar 4H frame, closes 100..104, DatetimeIndex."""
    idx = pd.date_range("2026-01-01", periods=5, freq="4h")
    return pd.DataFrame({"close": [100.0, 101.0, 102.0, 103.0, 104.0]}, index=idx)


def _pool(level, pool_type):
    return LiquidityPool(level=level, pool_type=pool_type, touches=2, timeframe="4h")


def test_first_unswept_pool_does_not_raise_nameerror():
    """NEGATIVE: a single unswept pool (level never broken) must return swept=False,
    not raise NameError. This is the original F1 crash path."""
    df = _df()
    # equal_highs level 110 — no close > 110 → never swept
    pools = [_pool(110.0, "equal_highs")]
    out = track_pool_sweeps(df, pools)  # pre-fix: NameError on `if swept:`
    assert len(out) == 1
    assert out[0].swept is False
    assert out[0].swept_index is None
    assert out[0].swept_timestamp is None


def test_no_stale_leak_swept_then_unswept():
    """Swept pool FOLLOWED by an unswept pool: the unswept one must NOT inherit the
    prior pool's swept flag / indices (the silent stale-leak half of F1)."""
    df = _df()
    pools = [
        _pool(101.5, "equal_lows"),   # close < 101.5 at bars 0,1 → SWEPT
        _pool(110.0, "equal_highs"),  # close never > 110 → must stay UNSWEPT
    ]
    out = track_pool_sweeps(df, pools)
    assert len(out) == 2
    assert out[0].swept is True               # first genuinely swept
    assert out[1].swept is False              # second must NOT leak
    assert out[1].swept_index is None
    assert out[1].swept_timestamp is None


def test_symmetry_both_pool_types_detected_when_actually_swept():
    """POSITIVE + symmetry (§16 r12): equal_highs swept upward AND equal_lows swept
    downward are both correctly marked, with the right sweep bar."""
    df = _df()
    pools = [
        _pool(103.5, "equal_highs"),  # close 104 > 103.5 at bar 4 → swept up
        _pool(100.5, "equal_lows"),   # close 100 < 100.5 at bar 0 → swept down
    ]
    out = track_pool_sweeps(df, pools)
    assert len(out) == 2  # mass conservation: pools in == pools out
    highs = next(p for p in out if p.pool_type == "equal_highs")
    lows = next(p for p in out if p.pool_type == "equal_lows")
    assert highs.swept is True and highs.swept_index == 4
    assert lows.swept is True and lows.swept_index == 0
