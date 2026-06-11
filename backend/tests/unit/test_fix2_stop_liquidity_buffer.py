"""
Regression test for Fix 2: Liquidity-aware stop placement (2026-06-11).

Problem: stop losses placed inside EQL/EQH/PWL/PDH clusters get systematically
swept before the trade plays out. Even structurally valid stops lose edge if they
sit inside a known stop-hunt pool.

Fix: _buffer_stop_from_liquidity() in risk_engine.py checks whether the computed
stop is within 0.3 ATR of any EQL/EQH/PWL/PDH pool; if so, pushes it 0.3 ATR
beyond the pool (away from entry), making the stop harder to hunt.

Verifies:
- Function exists and is importable
- Bull/bear symmetry: long pushes stop DOWN, short pushes stop UP
- No-op when stop is clear of all pools
- No-op when ATR is zero/None (safe fallback)
- Pushes stop on EQL hit within 0.3 ATR (long)
- Pushes stop on EQH hit within 0.3 ATR (short)
- Pushes stop on PWL key-level proximity (long)
- Pushes stop on PDH key-level proximity (short)
- 0.3 ATR buffer math is exact
- Boundary: stop exactly at 0.3 ATR triggers (≤ not <)
- Boundary: stop at 0.3 ATR + epsilon does NOT trigger
- Multiple pools: picks the widest adjustment
- Original stop returned unchanged when no trigger
- planner_service imports _buffer_stop_from_liquidity from risk_engine
- planner_service call site uses StopLoss dataclass for the buffered stop
"""

from __future__ import annotations

import pathlib
import re
import types
from unittest.mock import MagicMock, patch

import pytest

from backend.strategy.planner.risk_engine import _buffer_stop_from_liquidity


ATR = 2.0
BUFFER = 0.3 * ATR  # 0.6


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_key_levels(**kwargs) -> object:
    """Minimal object carrying key-level attrs."""
    kl = types.SimpleNamespace(**kwargs)
    return kl


def _no_pools_multi_tf() -> MagicMock:
    """MultiTimeframeData that contains no EQL/EQH matches."""
    mtf = MagicMock()
    # _find_eqh_eql_zones will scan ohlcv_by_timeframe; empty dict = no pools
    mtf.ohlcv_by_timeframe = {}
    mtf.timeframes = {}
    return mtf


# ---------------------------------------------------------------------------
# Import & interface
# ---------------------------------------------------------------------------

class TestFix2Interface:
    def test_importable(self):
        assert callable(_buffer_stop_from_liquidity)

    def test_returns_tuple_of_two(self):
        result = _buffer_stop_from_liquidity(
            stop_level=100.0, entry_ref=105.0, is_bullish=True,
            atr=ATR, multi_tf_data=None, key_levels=None,
        )
        assert isinstance(result, tuple) and len(result) == 2

    def test_planner_service_imports_buffer(self):
        src = pathlib.Path("backend/strategy/planner/planner_service.py").read_text(encoding="utf-8")
        assert "_buffer_stop_from_liquidity" in src, (
            "_buffer_stop_from_liquidity not imported in planner_service.py"
        )

    def test_planner_service_call_site_present(self):
        src = pathlib.Path("backend/strategy/planner/planner_service.py").read_text(encoding="utf-8")
        assert "_buffer_stop_from_liquidity(" in src, (
            "Call site for _buffer_stop_from_liquidity not found in planner_service.py"
        )

    def test_planner_call_site_builds_new_stop_loss(self):
        src = pathlib.Path("backend/strategy/planner/planner_service.py").read_text(encoding="utf-8")
        assert "StopLoss(" in src and "_buffered_stop" in src, (
            "planner_service must reconstruct StopLoss with buffered level"
        )


# ---------------------------------------------------------------------------
# Safe fallback: no ATR / no data
# ---------------------------------------------------------------------------

class TestFix2SafeFallbacks:
    def test_zero_atr_returns_unchanged(self):
        level, rat = _buffer_stop_from_liquidity(
            stop_level=100.0, entry_ref=105.0, is_bullish=True,
            atr=0.0, multi_tf_data=None, key_levels=None,
        )
        assert level == 100.0 and rat == ""

    def test_none_atr_returns_unchanged(self):
        level, rat = _buffer_stop_from_liquidity(
            stop_level=100.0, entry_ref=105.0, is_bullish=True,
            atr=None, multi_tf_data=None, key_levels=None,
        )
        assert level == 100.0 and rat == ""

    def test_no_data_no_key_levels_noop(self):
        level, rat = _buffer_stop_from_liquidity(
            stop_level=100.0, entry_ref=105.0, is_bullish=True,
            atr=ATR, multi_tf_data=None, key_levels=None,
        )
        assert level == 100.0 and rat == ""

    def test_empty_multi_tf_noop(self):
        level, rat = _buffer_stop_from_liquidity(
            stop_level=100.0, entry_ref=105.0, is_bullish=True,
            atr=ATR, multi_tf_data=_no_pools_multi_tf(), key_levels=None,
        )
        assert level == 100.0 and rat == ""


# ---------------------------------------------------------------------------
# Key-level pool triggering
# ---------------------------------------------------------------------------

class TestFix2KeyLevelTrigger:
    def test_long_stop_near_pwl_gets_pushed_down(self):
        """Long stop at 100.0, PWL at 100.3 (within 0.3 ATR=0.6) → stop pushed to 100.3-0.6=99.7."""
        kl = _fake_key_levels(pwl=100.3, pdl=None, pwh=None, pdh=None)
        level, rat = _buffer_stop_from_liquidity(
            stop_level=100.0, entry_ref=105.0, is_bullish=True,
            atr=ATR, multi_tf_data=None, key_levels=kl,
        )
        assert level < 100.0, f"Stop should be pushed below 100.0, got {level}"
        assert abs(level - (100.3 - BUFFER)) < 1e-9, f"Expected {100.3 - BUFFER}, got {level}"

    def test_long_stop_near_pdl_gets_pushed_down(self):
        """Long stop at 100.0, PDL at 100.4 (within 0.6 ATR) → pushed."""
        kl = _fake_key_levels(pwl=None, pdl=100.4, pwh=None, pdh=None)
        level, rat = _buffer_stop_from_liquidity(
            stop_level=100.0, entry_ref=105.0, is_bullish=True,
            atr=ATR, multi_tf_data=None, key_levels=kl,
        )
        assert level < 100.0

    def test_short_stop_near_pdh_gets_pushed_up(self):
        """Short stop at 110.0, PDH at 109.6 (within 0.6) → pushed to 109.6+0.6=110.2."""
        kl = _fake_key_levels(pwl=None, pdl=None, pwh=None, pdh=109.6)
        level, rat = _buffer_stop_from_liquidity(
            stop_level=110.0, entry_ref=105.0, is_bullish=False,
            atr=ATR, multi_tf_data=None, key_levels=kl,
        )
        assert level > 110.0, f"Stop should be pushed above 110.0, got {level}"
        assert abs(level - (109.6 + BUFFER)) < 1e-9

    def test_short_stop_near_pwh_gets_pushed_up(self):
        """Short stop at 110.0, PWH at 109.8 (within 0.6) → pushed."""
        kl = _fake_key_levels(pwl=None, pdl=None, pwh=109.8, pdh=None)
        level, rat = _buffer_stop_from_liquidity(
            stop_level=110.0, entry_ref=105.0, is_bullish=False,
            atr=ATR, multi_tf_data=None, key_levels=kl,
        )
        assert level > 110.0

    def test_long_stop_clear_of_all_pools_noop(self):
        """Long stop at 100.0, PWL at 98.0 (1.0 ATR away, > 0.3 ATR) → no change."""
        kl = _fake_key_levels(pwl=98.0, pdl=None, pwh=None, pdh=None)
        level, rat = _buffer_stop_from_liquidity(
            stop_level=100.0, entry_ref=105.0, is_bullish=True,
            atr=ATR, multi_tf_data=None, key_levels=kl,
        )
        assert level == 100.0 and rat == ""

    def test_long_pwl_above_entry_is_ignored(self):
        """PWL above entry_ref is not a stop-zone threat for longs — must be filtered."""
        kl = _fake_key_levels(pwl=106.0, pdl=None, pwh=None, pdh=None)
        level, rat = _buffer_stop_from_liquidity(
            stop_level=100.0, entry_ref=105.0, is_bullish=True,
            atr=ATR, multi_tf_data=None, key_levels=kl,
        )
        assert level == 100.0, "PWL above entry_ref should not affect long stop"

    def test_short_pdh_below_entry_is_ignored(self):
        """PDH below entry_ref is not a stop-zone threat for shorts."""
        kl = _fake_key_levels(pwl=None, pdl=None, pwh=None, pdh=103.0)
        level, rat = _buffer_stop_from_liquidity(
            stop_level=110.0, entry_ref=105.0, is_bullish=False,
            atr=ATR, multi_tf_data=None, key_levels=kl,
        )
        assert level == 110.0, "PDH below entry_ref should not affect short stop"


# ---------------------------------------------------------------------------
# Boundary conditions
# ---------------------------------------------------------------------------

class TestFix2BoundaryConditions:
    def test_pool_strictly_inside_buffer_triggers(self):
        """Pool at stop + 0.5 ATR (< buffer 0.6) → pushed to pool - buffer."""
        # stop=100.0, pool=100.5, diff=0.5 < buffer=0.6 → triggers
        # candidate = 100.5 - 0.6 = 99.9 < 100.0 ✓
        kl = _fake_key_levels(pwl=100.5, pdl=None, pwh=None, pdh=None)
        level, rat = _buffer_stop_from_liquidity(
            stop_level=100.0, entry_ref=105.0, is_bullish=True,
            atr=ATR, multi_tf_data=None, key_levels=kl,
        )
        assert level < 100.0, "Pool inside buffer should trigger push"
        assert abs(level - (100.5 - BUFFER)) < 1e-9, f"Expected {100.5 - BUFFER}, got {level}"

    def test_pool_exactly_at_buffer_distance_noop(self):
        """Pool exactly 0.3 ATR from stop → candidate equals current stop, no adjustment.
        The stop is already correctly placed at pool - buffer distance."""
        # stop=100.0, pool=100.6, diff=0.6=buffer, candidate=100.6-0.6=100.0 → unchanged
        kl = _fake_key_levels(pwl=100.6, pdl=None, pwh=None, pdh=None)
        level, rat = _buffer_stop_from_liquidity(
            stop_level=100.0, entry_ref=105.0, is_bullish=True,
            atr=ATR, multi_tf_data=None, key_levels=kl,
        )
        assert level == 100.0, "Pool at exact buffer distance → stop already at safe position"

    def test_pool_outside_buffer_does_not_trigger(self):
        """Pool at 0.3 ATR + epsilon away → no trigger."""
        kl = _fake_key_levels(pwl=100.601, pdl=None, pwh=None, pdh=None)
        level, rat = _buffer_stop_from_liquidity(
            stop_level=100.0, entry_ref=105.0, is_bullish=True,
            atr=ATR, multi_tf_data=None, key_levels=kl,
        )
        assert level == 100.0, "Pool just outside buffer should not trigger"


# ---------------------------------------------------------------------------
# Bull/bear symmetry
# ---------------------------------------------------------------------------

class TestFix2Symmetry:
    """Both LONG and SHORT paths must produce mirror-image adjustments for the same
    relative geometry. Covers Rubric 12: direction-aware code has paired __long/__short
    coverage."""

    def test_long_pushes_stop_lower(self):
        """LONG: buffered stop < original stop."""
        kl = _fake_key_levels(pwl=100.3, pdl=None, pwh=None, pdh=None)
        level, _ = _buffer_stop_from_liquidity(
            stop_level=100.0, entry_ref=105.0, is_bullish=True,
            atr=ATR, multi_tf_data=None, key_levels=kl,
        )
        assert level < 100.0

    def test_short_pushes_stop_higher(self):
        """SHORT: buffered stop > original stop."""
        kl = _fake_key_levels(pwl=None, pdl=None, pwh=None, pdh=109.7)
        level, _ = _buffer_stop_from_liquidity(
            stop_level=110.0, entry_ref=105.0, is_bullish=False,
            atr=ATR, multi_tf_data=None, key_levels=kl,
        )
        assert level > 110.0

    def test_long_rationale_mentions_pool_level(self):
        """Rationale string must name the pool level for LONG trigger."""
        kl = _fake_key_levels(pwl=100.3, pdl=None, pwh=None, pdh=None)
        _, rat = _buffer_stop_from_liquidity(
            stop_level=100.0, entry_ref=105.0, is_bullish=True,
            atr=ATR, multi_tf_data=None, key_levels=kl,
        )
        assert "100.3" in rat or "100." in rat, f"Rationale missing pool level: '{rat}'"

    def test_short_rationale_mentions_pool_level(self):
        """Rationale string must name the pool level for SHORT trigger."""
        kl = _fake_key_levels(pwl=None, pdl=None, pwh=None, pdh=109.7)
        _, rat = _buffer_stop_from_liquidity(
            stop_level=110.0, entry_ref=105.0, is_bullish=False,
            atr=ATR, multi_tf_data=None, key_levels=kl,
        )
        assert "109.7" in rat or "109." in rat, f"Rationale missing pool level: '{rat}'"

    def test_no_trigger_long_returns_empty_rationale(self):
        level, rat = _buffer_stop_from_liquidity(
            stop_level=100.0, entry_ref=105.0, is_bullish=True,
            atr=ATR, multi_tf_data=None, key_levels=None,
        )
        assert rat == ""

    def test_no_trigger_short_returns_empty_rationale(self):
        level, rat = _buffer_stop_from_liquidity(
            stop_level=110.0, entry_ref=105.0, is_bullish=False,
            atr=ATR, multi_tf_data=None, key_levels=None,
        )
        assert rat == ""


# ---------------------------------------------------------------------------
# Multiple pools: widest adjustment wins
# ---------------------------------------------------------------------------

class TestFix2Observability:
    """OBS-01/OBS-02 guard: silent failures must log at WARNING level per §15."""

    RE_SRC = pathlib.Path("backend/strategy/planner/risk_engine.py").read_text(encoding="utf-8")
    PS_SRC = pathlib.Path("backend/strategy/planner/planner_service.py").read_text(encoding="utf-8")

    # Extract the _buffer_stop_from_liquidity function body
    _FN_RE = re.compile(
        r"def _buffer_stop_from_liquidity\b.*?(?=\ndef |\Z)",
        re.DOTALL,
    )
    _match = _FN_RE.search(RE_SRC)
    FN_BODY = _match.group(0) if _match else ""

    def test_eql_scan_except_logs_warning_not_pass(self):
        """OBS-01: EQL/EQH scan except clause must log at WARNING, not silently pass."""
        assert "except Exception as _eqh_err" in self.FN_BODY, (
            "EQL scan except clause must capture the exception (_eqh_err) for logging"
        )
        assert "warning" in self.FN_BODY.lower() or "Warning" in self.FN_BODY, (
            "EQL scan except clause must emit a log at WARNING level — bare 'pass' violates §15"
        )

    def test_no_trigger_debug_log_in_planner(self):
        """OBS-02: When no pool is close enough, a debug log must fire to confirm the call ran."""
        assert "STOP BUFFER: no pool within" in self.PS_SRC, (
            "No debug log for the no-trigger path in planner_service — buffer call invisible in logs"
        )

    def test_degenerate_distance_atr_raises(self):
        """R3 guard: planner_service must raise ValueError when buffered stop == near_entry."""
        assert "_buf_dist_atr <= 0" in self.PS_SRC, (
            "No distance_atr <= 0 guard in planner_service — degenerate stop can propagate silently"
        )

    def test_decisions_log_entry_exists(self):
        """R5 baseline: calibration decisions log for 0.3 ATR threshold must exist."""
        log_path = pathlib.Path(
            "backend/diagnostics/decisions/2026-06-11__fix2-stop-liquidity-buffer-baseline.md"
        )
        assert log_path.exists(), (
            f"Decisions log entry missing at {log_path} — §15 requires documented baseline for "
            "the 0.3 ATR buffer threshold"
        )


class TestFix2MultiplePools:
    def test_closest_pool_dominates_for_long(self):
        """Two pools: both within buffer. Stop pushed past the closer/wider one."""
        # pool1=100.3, pool2=100.5. pool1 is closer to stop (100.0), but pool2 is
        # further from stop → pushes stop lower when triggered
        # pool1 at 100.3 → candidate = 100.3 - 0.6 = 99.7
        # pool2 at 100.5 → candidate = 100.5 - 0.6 = 99.9
        # Both within 0.6 ATR. The lower candidate wins (99.7).
        kl = _fake_key_levels(pwl=100.3, pdl=100.5, pwh=None, pdh=None)
        level, _ = _buffer_stop_from_liquidity(
            stop_level=100.0, entry_ref=105.0, is_bullish=True,
            atr=ATR, multi_tf_data=None, key_levels=kl,
        )
        assert abs(level - (100.3 - BUFFER)) < 1e-9, (
            f"Expected widest push {100.3 - BUFFER}, got {level}"
        )
