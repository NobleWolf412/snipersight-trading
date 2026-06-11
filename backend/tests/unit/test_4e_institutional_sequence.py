"""
Phase 4E: _score_institutional_sequence temporal ordering rewrite.

Tests cover:
1. Full sequence (Sweep → Shift → OB, correctly ordered) → 100
2. Sweep → Shift (ordered) but no OB → 70
3. Shift + OB, no sweep → 50
4. Sweep + Shift + OB but shift BEFORE sweep (wrong order) → 40
5. Sweep only, no shift → 20
6. Nothing → 0
7. confirmed_at used over timestamp for sweep time check when available
8. Bull/bear symmetry for all paths
"""
from datetime import datetime, timedelta

import pytest

from backend.shared.models.smc import LiquiditySweep, StructuralBreak, OrderBlock, SMCSnapshot
from backend.strategy.confluence.scorer import _score_institutional_sequence


# ── Helpers ────────────────────────────────────────────────────────────────


T0 = datetime(2024, 1, 1, 0, 0, 0)


def _sweep(sweep_type: str, ts: datetime, confirmed_at: datetime = None) -> LiquiditySweep:
    return LiquiditySweep(
        level=100.0,
        sweep_type=sweep_type,
        confirmation=True,
        timestamp=ts,
        confirmed_at=confirmed_at,
    )


def _shift(direction: str, ts: datetime) -> StructuralBreak:
    return StructuralBreak(
        timeframe="1h",
        break_type="CHoCH",
        level=100.0,
        timestamp=ts,
        htf_aligned=True,
        direction=direction,
    )


def _ob(direction: str) -> OrderBlock:
    return OrderBlock(
        timeframe="1h",
        direction=direction,
        high=101.0,
        low=99.0,
        timestamp=T0,
        displacement_strength=60.0,
        mitigation_level=0.0,
        freshness_score=80.0,
    )


def _snap(sweeps=(), shifts=(), obs=()) -> SMCSnapshot:
    return SMCSnapshot(
        order_blocks=list(obs),
        fvgs=[],
        structural_breaks=list(shifts),
        liquidity_sweeps=list(sweeps),
    )


# ── 1. Full sequence (all three, correct order) ────────────────────────────


def test_full_sequence_bullish():
    """Sweep(low) at T0 → Shift(bullish) at T0+1h → OB(bullish) → 100."""
    snap = _snap(
        sweeps=[_sweep("low", ts=T0)],
        shifts=[_shift("bullish", ts=T0 + timedelta(hours=1))],
        obs=[_ob("bullish")],
    )
    score, reason = _score_institutional_sequence(snap, "bullish")
    assert score == pytest.approx(100.0)
    assert "Sweep → Shift → OB" in reason


def test_full_sequence_bearish():
    """Sweep(high) at T0 → Shift(bearish) at T0+1h → OB(bearish) → 100."""
    snap = _snap(
        sweeps=[_sweep("high", ts=T0)],
        shifts=[_shift("bearish", ts=T0 + timedelta(hours=1))],
        obs=[_ob("bearish")],
    )
    score, reason = _score_institutional_sequence(snap, "bearish")
    assert score == pytest.approx(100.0)
    assert "Sweep → Shift → OB" in reason


# ── 2. Sweep → Shift (ordered) but no OB → 70 ──────────────────────────────


def test_sweep_shift_no_ob_bullish():
    snap = _snap(
        sweeps=[_sweep("low", ts=T0)],
        shifts=[_shift("bullish", ts=T0 + timedelta(hours=1))],
        obs=[],
    )
    score, reason = _score_institutional_sequence(snap, "bullish")
    assert score == pytest.approx(70.0)
    assert "no OB" in reason


def test_sweep_shift_no_ob_bearish():
    snap = _snap(
        sweeps=[_sweep("high", ts=T0)],
        shifts=[_shift("bearish", ts=T0 + timedelta(hours=1))],
        obs=[],
    )
    score, reason = _score_institutional_sequence(snap, "bearish")
    assert score == pytest.approx(70.0)


# ── 3. Shift + OB, no sweep → 50 ──────────────────────────────────────────


def test_shift_ob_no_sweep_bullish():
    snap = _snap(
        sweeps=[],
        shifts=[_shift("bullish", ts=T0)],
        obs=[_ob("bullish")],
    )
    score, reason = _score_institutional_sequence(snap, "bullish")
    assert score == pytest.approx(50.0)
    assert "no preceding sweep" in reason


def test_shift_ob_no_sweep_bearish():
    snap = _snap(
        sweeps=[],
        shifts=[_shift("bearish", ts=T0)],
        obs=[_ob("bearish")],
    )
    score, reason = _score_institutional_sequence(snap, "bearish")
    assert score == pytest.approx(50.0)


# ── 4. Wrong temporal order (shift before sweep) → 40 ─────────────────────


def test_wrong_order_shift_before_sweep_bullish():
    """Shift at T0, sweep at T0+1h → shift BEFORE sweep → out-of-order (40)."""
    snap = _snap(
        sweeps=[_sweep("low", ts=T0 + timedelta(hours=1))],
        shifts=[_shift("bullish", ts=T0)],  # shift BEFORE sweep
        obs=[_ob("bullish")],
    )
    score, reason = _score_institutional_sequence(snap, "bullish")
    assert score == pytest.approx(40.0)
    assert "temporal order violated" in reason


def test_wrong_order_shift_before_sweep_bearish():
    snap = _snap(
        sweeps=[_sweep("high", ts=T0 + timedelta(hours=1))],
        shifts=[_shift("bearish", ts=T0)],
        obs=[_ob("bearish")],
    )
    score, reason = _score_institutional_sequence(snap, "bearish")
    assert score == pytest.approx(40.0)


# ── 5. Sweep only, no shift → 20 ──────────────────────────────────────────


def test_sweep_only_bullish():
    snap = _snap(sweeps=[_sweep("low", ts=T0)], shifts=[], obs=[])
    score, reason = _score_institutional_sequence(snap, "bullish")
    assert score == pytest.approx(20.0)
    assert "no subsequent structural shift" in reason


def test_sweep_only_bearish():
    snap = _snap(sweeps=[_sweep("high", ts=T0)], shifts=[], obs=[])
    score, reason = _score_institutional_sequence(snap, "bearish")
    assert score == pytest.approx(20.0)


# ── 6. Nothing → 0 ────────────────────────────────────────────────────────


def test_no_sequence_bullish():
    snap = _snap()
    score, reason = _score_institutional_sequence(snap, "bullish")
    assert score == pytest.approx(0.0)
    assert "No institutional sequence detected" in reason


def test_no_sequence_bearish():
    snap = _snap()
    score, reason = _score_institutional_sequence(snap, "bearish")
    assert score == pytest.approx(0.0)


# ── 7. confirmed_at used when available ────────────────────────────────────


def test_confirmed_at_used_for_sweep_time_check():
    """confirmed_at (not timestamp) determines ordering gate for sweep."""
    # Sweep timestamp=T0, but confirmed_at=T0+2h (reversal took 2h to confirm)
    # Shift at T0+1h — AFTER sweep.timestamp but BEFORE confirmed_at
    # Should NOT score 100 (shift is before confirmed_at)
    sweep = _sweep("low", ts=T0, confirmed_at=T0 + timedelta(hours=2))
    snap = _snap(
        sweeps=[sweep],
        shifts=[_shift("bullish", ts=T0 + timedelta(hours=1))],  # between ts and confirmed_at
        obs=[_ob("bullish")],
    )
    score, _ = _score_institutional_sequence(snap, "bullish")
    # Shift at T0+1h is BEFORE confirmed_at=T0+2h → not an ordered shift → should not be 100
    assert score < 100.0


def test_confirmed_at_none_falls_back_to_timestamp():
    """When confirmed_at is None, timestamp is used for ordering check."""
    sweep = _sweep("low", ts=T0, confirmed_at=None)
    snap = _snap(
        sweeps=[sweep],
        shifts=[_shift("bullish", ts=T0 + timedelta(hours=1))],
        obs=[_ob("bullish")],
    )
    score, _ = _score_institutional_sequence(snap, "bullish")
    assert score == pytest.approx(100.0)


# ── 8. Wrong-direction sweep/shift ignored ─────────────────────────────────


def test_wrong_direction_sweep_ignored_bullish():
    """A 'high' sweep does not count for a bullish sequence."""
    snap = _snap(
        sweeps=[_sweep("high", ts=T0)],  # wrong type for bullish
        shifts=[_shift("bullish", ts=T0 + timedelta(hours=1))],
        obs=[_ob("bullish")],
    )
    score, _ = _score_institutional_sequence(snap, "bullish")
    # No aligned sweep → falls through to shift+ob path (50) or worse
    assert score <= 50.0


def test_wrong_direction_shift_ignored_bearish():
    """A 'bullish' shift does not count for a bearish sequence."""
    snap = _snap(
        sweeps=[_sweep("high", ts=T0)],
        shifts=[_shift("bullish", ts=T0 + timedelta(hours=1))],  # wrong direction for bearish
        obs=[_ob("bearish")],
    )
    score, _ = _score_institutional_sequence(snap, "bearish")
    assert score <= 20.0


# ── 9. Same-bar boundary: shift.timestamp == sweep_time → unordered (40) ──────


def test_same_timestamp_shift_and_sweep_bullish():
    """shift.timestamp == sweep_time uses strict > comparison → unordered → 40 (with OB)."""
    snap = _snap(
        sweeps=[_sweep("low", ts=T0)],
        shifts=[_shift("bullish", ts=T0)],  # same timestamp as sweep → not strictly after
        obs=[_ob("bullish")],
    )
    score, reason = _score_institutional_sequence(snap, "bullish")
    # Same-bar BOS+sweep is temporally ambiguous; treated as wrong order
    assert score == pytest.approx(40.0), f"Expected 40 (unordered), got {score}"
    assert "temporal order violated" in reason


def test_same_timestamp_shift_and_sweep_bearish():
    """Symmetric bearish case: same-bar shift+sweep → 40."""
    snap = _snap(
        sweeps=[_sweep("high", ts=T0)],
        shifts=[_shift("bearish", ts=T0)],  # same timestamp
        obs=[_ob("bearish")],
    )
    score, reason = _score_institutional_sequence(snap, "bearish")
    assert score == pytest.approx(40.0)
    assert "temporal order violated" in reason
