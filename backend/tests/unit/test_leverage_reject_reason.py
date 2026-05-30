"""
Regression for hot-path audit bug #7 (2_RISKY): in LiveExecutor.place_order, the
leverage-mismatch branch (set_leverage raises because an open position exists) set
order.status = REJECTED but did NOT set order.rejection_reason — unlike every other
reject path in the method. The caller persists `rejection_reason or status.value`,
so the actual cause was destroyed on the JSONL signal record and survived only in a
transient logger.error (CLAUDE.md "never destroy a rejection reason").

Fix: the leverage-mismatch branch now sets order.rejection_reason to the same
message it logs. No execution behavior change — the order is still rejected and
returned; only the reason is now recorded.

See backend/diagnostics/decisions/2026-05-29__hotpath-robustness-audit.md (bug #7).
Per CLAUDE.md §11 (never destroy a rejection reason), §14 rubric 4 (negative+positive).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from backend.bot.executor import live_executor as le_mod
from backend.bot.executor.live_executor import LiveExecutor
from backend.bot.executor.paper_executor import OrderStatus


def _executor():
    """A LiveExecutor with only the attrs place_order reads up to (and through)
    the leverage block (bypasses __init__, which builds a real Phemex adapter)."""
    ex = object.__new__(LiveExecutor)
    ex._orders = {}
    ex.max_position_size_usd = 1e12          # size/exposure checks pass
    ex.max_total_exposure_usd = 1e12
    ex._position_avg_price = {}
    ex._cached_balance = 1e9                  # balance check passes
    ex.min_balance_usd = 0.0
    ex.dry_run = False                        # reach the real leverage block
    ex._leverage_confirmed = set()            # not yet confirmed → enters the block
    ex.target_leverage = 10
    ex._hedge_mode = False
    ex._exchange_order_map = {}
    ex._reverse_order_map = {}
    ex._generate_order_id = lambda: "test-order-1"
    ex._total_exposure_usd = lambda: 0.0
    ex._adapter = MagicMock()
    ex._adapter.set_margin_mode.return_value = None
    return ex


def test_leverage_mismatch_records_rejection_reason():
    """set_leverage raises (open position exists) → order REJECTED WITH a reason
    (was None before the fix → cause lost on the persisted record)."""
    ex = _executor()
    ex._adapter.set_leverage.side_effect = RuntimeError("open position exists")

    order = ex.place_order(
        symbol="BTC/USDT:USDT", side="BUY", order_type="LIMIT", quantity=1.0, price=100.0
    )

    assert order.status == OrderStatus.REJECTED
    assert order.rejection_reason, "leverage-mismatch reject must record a reason (was None)"
    assert "everage" in order.rejection_reason  # mentions leverage mismatch


def test_leverage_success_no_spurious_rejection():
    """Positive pair: set_leverage succeeds and the order sends → NOT rejected, no
    spurious rejection_reason."""
    ex = _executor()
    ex._adapter.set_leverage.side_effect = None
    ex._adapter.create_order.return_value = {"id": "exch-123"}

    order = ex.place_order(
        symbol="BTC/USDT:USDT", side="BUY", order_type="LIMIT", quantity=1.0, price=100.0
    )

    assert order.status != OrderStatus.REJECTED
    assert not order.rejection_reason  # None / empty — no false reason
    assert "BTC/USDT:USDT" in ex._leverage_confirmed  # leverage marked confirmed
