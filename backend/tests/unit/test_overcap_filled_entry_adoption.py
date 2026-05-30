"""
Regression for hot-path audit bug #2 (1_BROKEN): an entry limit order that
FILLED while the bot was at max_positions was "cancelled" (a no-op on a filled
order) and dropped from _pending_plans, leaving a real position open on Phemex
with no PositionManager entry, no native stop, and no software monitoring.

Root cause: the cap counter (_get_active_positions) counts only OPEN/PARTIAL
positions, never the in-flight _pending_plans — so the placement gate let the
bot over-subscribe, and the fill handler "resolved" the overage by dropping a
filled order.

Fix (operator-approved: adopt + pending-aware cap):
  - _open_filled_entry ALWAYS adopts a confirmed fill (open_position + native
    stop), even over cap, with a loud over_cap_adopted warning — never drops it.
  - _process_signal counts len(_pending_plans) toward the cap so over-
    subscription stops happening in the first place.

See backend/diagnostics/decisions/2026-05-30__fix-design__overcap-filled-order-stranded.md
and 2026-05-29__hotpath-robustness-audit.md (bug #2).

Per CLAUDE.md §11 (loud-failure surfacing), §14 rubric 4 (negative+positive
pair), §16 rubric 12 (LONG/SHORT symmetry).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from backend.bot.live_trading_service import LiveTradingService


_PLAN_LONG = SimpleNamespace(symbol="BTC/USDT", direction="LONG")
_PLAN_SHORT = SimpleNamespace(symbol="ETH/USDT", direction="SHORT")


def _bare_service(max_positions: int = 2, active_count: int = 0) -> LiveTradingService:
    """A LiveTradingService with only the attributes _open_filled_entry touches
    (bypasses __init__, which connects to the exchange)."""
    svc = object.__new__(LiveTradingService)
    svc.config = SimpleNamespace(max_positions=max_positions)
    svc.stats = SimpleNamespace(signals_taken=0)
    svc.position_manager = MagicMock()
    svc.position_manager.open_position.return_value = "pos-1"
    svc._pending_plans = {}
    svc._pending_placed_at = {}
    svc._pending_placed_price = {}
    svc._get_active_positions = lambda: [object()] * active_count
    svc._place_exchange_stop = AsyncMock()
    svc._activity = []
    svc._log_activity = lambda kind, data: svc._activity.append((kind, data))
    return svc


def _seed_pending(svc, order_id="o1"):
    svc._pending_plans[order_id] = _PLAN_LONG
    svc._pending_placed_at[order_id] = "t"
    svc._pending_placed_price[order_id] = 1.0


# ──────────────────────────────────────────────────────────────────────────────
# Adopt — the bug: an over-cap fill must be OPENED + STOPPED, never dropped
# ──────────────────────────────────────────────────────────────────────────────


def test_open_filled_entry_adopts_over_cap_long():
    svc = _bare_service(max_positions=2, active_count=2)  # at cap
    _seed_pending(svc)
    pos_id = asyncio.run(svc._open_filled_entry("o1", _PLAN_LONG, 100.0, 5.0))

    assert pos_id == "pos-1"  # adopted, NOT dropped (was the stranded-position bug)
    svc.position_manager.open_position.assert_called_once()
    svc._place_exchange_stop.assert_awaited_once()
    assert "o1" not in svc._pending_plans  # pending entry cleared
    assert svc.stats.signals_taken == 1
    # Loud over-cap surfacing (§11)
    assert any(kind == "over_cap_adopted" for kind, _ in svc._activity)


def test_open_filled_entry_adopts_over_cap_short():
    """SHORT mirror (§16 rubric 12)."""
    svc = _bare_service(max_positions=2, active_count=2)
    svc._pending_plans["o1"] = _PLAN_SHORT
    pos_id = asyncio.run(svc._open_filled_entry("o1", _PLAN_SHORT, 100.0, 5.0))
    assert pos_id == "pos-1"
    svc.position_manager.open_position.assert_called_once()
    svc._place_exchange_stop.assert_awaited_once()
    assert any(kind == "over_cap_adopted" for kind, _ in svc._activity)


# ──────────────────────────────────────────────────────────────────────────────
# Positive (no-regression) — under cap opens exactly as before, no over-cap warn
# ──────────────────────────────────────────────────────────────────────────────


def test_open_filled_entry_adopts_even_if_native_stop_throws():
    """If the exchange-native stop call throws, the fill is STILL adopted — the
    position carries a software stop and _sync_exchange_stops retries next cycle.
    The throw must NOT escape the adoption path (Rubric 7 hardening)."""
    svc = _bare_service(max_positions=2, active_count=0)
    _seed_pending(svc)
    svc._place_exchange_stop = AsyncMock(side_effect=RuntimeError("exchange down"))
    pos_id = asyncio.run(svc._open_filled_entry("o1", _PLAN_LONG, 100.0, 5.0))

    assert pos_id == "pos-1"  # adopted despite native-stop failure
    svc.position_manager.open_position.assert_called_once()
    assert "o1" not in svc._pending_plans  # pending cleared, position monitored


def test_open_filled_entry_opens_under_cap_no_warning():
    svc = _bare_service(max_positions=2, active_count=0)
    _seed_pending(svc)
    pos_id = asyncio.run(svc._open_filled_entry("o1", _PLAN_LONG, 100.0, 5.0))

    assert pos_id == "pos-1"
    svc.position_manager.open_position.assert_called_once()
    svc._place_exchange_stop.assert_awaited_once()
    assert svc.stats.signals_taken == 1
    assert not any(kind == "over_cap_adopted" for kind, _ in svc._activity)


# ──────────────────────────────────────────────────────────────────────────────
# Negative — invalid fill price must NOT open and must NOT pop (caller decides)
# ──────────────────────────────────────────────────────────────────────────────


def test_open_filled_entry_rejects_invalid_price():
    svc = _bare_service()
    _seed_pending(svc)
    result = asyncio.run(svc._open_filled_entry("o1", _PLAN_LONG, 0.0, 5.0))

    assert result is None
    svc.position_manager.open_position.assert_not_called()
    svc._place_exchange_stop.assert_not_awaited()
    assert "o1" in svc._pending_plans  # left intact for the caller to handle


# ──────────────────────────────────────────────────────────────────────────────
# Part 2 — pending orders count toward the placement cap (over-subscription fix)
# ──────────────────────────────────────────────────────────────────────────────


def _signal_service(max_positions=2, active_count=0, pending=0, has_position=False):
    svc = object.__new__(LiveTradingService)
    svc.config = SimpleNamespace(max_positions=max_positions)
    svc.executor = MagicMock()
    svc.position_manager = MagicMock()
    svc._get_active_positions = lambda: [object()] * active_count
    svc._pending_plans = {f"o{i}": None for i in range(pending)}
    svc._has_position = lambda s: has_position
    svc._signals = []
    svc._log_signal = lambda plan, status, msg, reason_type=None: svc._signals.append(
        (status, reason_type, msg)
    )
    return svc


def test_pending_orders_count_toward_cap():
    """0 open + 2 pending == cap(2): the placement gate MUST bail. Before the
    fix, pending were uncounted → over-subscription → over-cap fills stranded."""
    svc = _signal_service(max_positions=2, active_count=0, pending=2)
    plan = SimpleNamespace(symbol="BTC/USDT", confidence_score=80.0)
    asyncio.run(svc._process_signal(plan))

    assert svc._signals, "expected a filtered signal"
    assert svc._signals[-1][1] == "max_positions"
    svc.executor.place_order.assert_not_called()


def test_under_cap_with_pending_passes_cap_gate():
    """0 open + 1 pending < cap(2): cap gate must PASS (positive pair). Proven by
    the function reaching the next gate (has_position) instead of max_positions."""
    svc = _signal_service(max_positions=2, active_count=0, pending=1, has_position=True)
    plan = SimpleNamespace(symbol="BTC/USDT", confidence_score=80.0)
    asyncio.run(svc._process_signal(plan))

    assert svc._signals, "expected a filtered signal"
    assert svc._signals[-1][1] == "has_position"  # got past the cap gate
    svc.executor.place_order.assert_not_called()
