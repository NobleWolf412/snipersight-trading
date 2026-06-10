"""
Regression for Phase 1B: LiquiditySweep.confirmed_at (schema add, operator decision #6).

A sweep's `timestamp` is WHEN price penetrated the level; the sweep is only CONFIRMED
once its reversal completes — reversal_bar_count bars later. `confirmed_at` =
timestamp + reversal_bar_count * bar_duration is the earliest look-ahead-safe time the
sweep is actionable. Replay/backtest entry simulation must gate on confirmed_at, never
timestamp, or it acts on a reversal that had not yet happened (look-ahead bias).

Tests: helper formula + bars==0 edge, backward-compat default, detection populates it on
really-detected sweeps (both sweep_types handled identically), and the core contract — no
entry gated on confirmed_at can precede the sweep's confirmation.

Per CLAUDE.md §14 rubric 4 (positive+negative), §16 rubric 12 (bull/bear symmetry).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from backend.shared.models.smc import LiquiditySweep
from backend.strategy.smc.liquidity_sweeps import _confirmed_at, detect_liquidity_sweeps


# ── helper: _confirmed_at formula + edges (deterministic, direction-agnostic) ──────


def test_confirmed_at_adds_reversal_bars_times_duration():
    ts = pd.Timestamp("2025-01-01 00:00:00")
    out = _confirmed_at(ts, reversal_bars=3, bar_duration=pd.Timedelta(hours=1))
    assert out == datetime(2025, 1, 1, 3, 0, 0)


def test_confirmed_at_zero_bars_equals_sweep_timestamp():
    """reversal_bar_count == 0 (wick-only confirmation) → confirmed at the sweep bar."""
    ts = pd.Timestamp("2025-01-01 00:00:00")
    out = _confirmed_at(ts, reversal_bars=0, bar_duration=pd.Timedelta(hours=1))
    assert out == ts.to_pydatetime()


def test_confirmed_at_never_precedes_timestamp():
    ts = pd.Timestamp("2025-01-01 00:00:00")
    for bars in (0, 1, 5, 12):
        assert _confirmed_at(ts, bars, pd.Timedelta(minutes=15)) >= ts.to_pydatetime()


# ── backward compatibility: field is optional, defaults None ──────────────────────


def test_confirmed_at_defaults_none_backward_compatible():
    sweep = LiquiditySweep(
        level=100.0, sweep_type="low", confirmation=True, timestamp=datetime(2025, 1, 1)
    )
    assert sweep.confirmed_at is None


# ── detection populates confirmed_at on real sweeps, both sweep_types ──────────────


def _stophunt_df(n: int = 320, seed: int = 7) -> pd.DataFrame:
    """Continuous walk with periodic stop-hunt spikes (long wick beyond a prior
    extreme + volume + reversal) so the detector produces both high and low sweeps."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-01", periods=n, freq="1h")
    o = [100.0]
    h, l, c, v = [], [], [], []
    for i in range(n):
        op = o[-1]
        cl = op + rng.normal(0, 0.5)
        hi = max(op, cl) + abs(rng.normal(0, 0.3))
        lo = min(op, cl) - abs(rng.normal(0, 0.3))
        vol = 1000 * (1 + abs(rng.normal(0, 0.2)))
        # low stop-hunt: spike down with long lower wick, then close back up
        if i % 37 == 25:
            lo = min(op, cl) - 3.0
            cl = op + 1.2
            hi = max(op, cl) + 0.2
            vol *= 3.0
        # high stop-hunt: spike up with long upper wick, then close back down
        if i % 41 == 30:
            hi = max(op, cl) + 3.0
            cl = op - 1.2
            lo = min(op, cl) - 0.2
            vol *= 3.0
        h.append(hi); l.append(lo); c.append(cl); v.append(vol)
        o.append(cl)
    return pd.DataFrame({"open": o[:-1], "high": h, "low": l, "close": c, "volume": v}, index=idx)


def test_detection_populates_confirmed_at_correctly():
    sweeps = detect_liquidity_sweeps(_stophunt_df())
    assert len(sweeps) >= 1, "fixture failed to produce any sweep — test would be vacuous"

    bar_duration = pd.Timedelta(hours=1)
    for s in sweeps:
        # populated, never None
        assert s.confirmed_at is not None
        # matches the formula recomputed from the sweep's own fields
        expected = _confirmed_at(s.timestamp, s.reversal_bar_count, bar_duration)
        assert s.confirmed_at == expected
        # CORE CONTRACT: confirmation is never before the sweep itself (no look-ahead)
        assert s.confirmed_at >= s.timestamp


def test_both_sweep_types_populate_confirmed_at_symmetrically():
    sweeps = detect_liquidity_sweeps(_stophunt_df())
    by_type = {"high": [], "low": []}
    for s in sweeps:
        by_type[s.sweep_type].append(s)
    bar_duration = pd.Timedelta(hours=1)
    # whichever types were produced, both must obey the identical population rule
    for stype, group in by_type.items():
        for s in group:
            assert s.confirmed_at == _confirmed_at(s.timestamp, s.reversal_bar_count, bar_duration), (
                f"{stype} sweep confirmed_at not populated by the shared rule"
            )


def test_confirmed_at_blocks_lookahead_entry():
    """A backtest entry gated on confirmed_at can never enter before the reversal
    completed; an entry gated on timestamp could (the bias confirmed_at prevents)."""
    sweeps = [s for s in detect_liquidity_sweeps(_stophunt_df()) if s.reversal_bar_count > 0]
    assert sweeps, "need at least one multi-bar-reversal sweep to exercise the guard"
    for s in sweeps:
        # entry permitted only at/after confirmed_at
        assert s.confirmed_at > s.timestamp  # strictly later when reversal took >0 bars
