"""
Regression tests for Fix 1: Paper-fidelity package (2026-06-11).

Verifies:
- Phemex taker fee (0.06%) applied to snap_taker sessions
- Phemex maker fee (0.01%) applied to rest_maker sessions
- BTC/ETH use major_slippage_bps (10 bps); alts use slippage_bps (35 bps)
- SIMULATION_MIN_TARGET_HOLD_SECONDS == 0 (no artificial TP hold)
- live_executor.py fee_rate NOT changed (§15 blast-radius guard)

Per CLAUDE.md §14 rubric 4 (negative pair), §16 rubric 12 (bull/bear symmetry),
§15 (live-path isolation).
"""

from __future__ import annotations

import inspect

import pytest

from backend.bot.executor.paper_executor import PaperExecutor, OrderSide
from backend.bot.executor.position_manager import PositionManager
from backend.bot.paper_trading_service import PaperTradingConfig


# ──────────────────────────────────────────────────────────────────────────────
# Fee rates
# ──────────────────────────────────────────────────────────────────────────────


def test_taker_fee_rate_is_phemex_taker():
    """Default fee_rate on PaperExecutor is Phemex taker (0.06%), not old 0.1%."""
    ex = PaperExecutor(initial_balance=10_000)
    assert ex.fee_rate == 0.0006, (
        f"Expected taker fee 0.0006, got {ex.fee_rate} — "
        "paper economics must use real Phemex taker rate"
    )


def test_maker_fee_rate_lower_than_taker():
    """Explicit maker fee session uses 0.01% (6x cheaper than taker)."""
    ex = PaperExecutor(initial_balance=10_000, fee_rate=0.0001)
    assert ex.fee_rate == 0.0001


def test_taker_fee_applied_to_market_order():
    """Market order deducts taker fee = qty * fill_price * 0.0006.
    Partial fills disabled so fill is deterministic (full qty at slipped price)."""
    ex = PaperExecutor(
        initial_balance=10_000,
        fee_rate=0.0006,
        enable_partial_fills=False,  # deterministic full fill
    )
    order = ex.place_order(symbol="SOL/USDT", side="BUY", order_type="MARKET", quantity=100.0)
    starting_balance = ex.balance
    fill = ex.execute_market_order(order.order_id, current_price=50.0)
    assert fill is not None
    # fill_price = 50.0 * (1 + 35/10000) = 50.175 (alt slippage, no partial fill)
    # fee = 100 * 50.175 * 0.0006 = 3.0105
    expected_fee = 100.0 * fill.price * 0.0006
    fee_charged = starting_balance - ex.balance
    assert abs(fee_charged - expected_fee) < 0.001, (
        f"Taker fee {fee_charged:.6f} != expected {expected_fee:.6f}"
    )


def test_maker_fee_cheaper_than_taker_on_identical_order():
    """Maker session charges less fee than taker session for identical order."""
    def _fee_for_session(fee_rate: float) -> float:
        ex = PaperExecutor(initial_balance=10_000, fee_rate=fee_rate, enable_partial_fills=False)
        order = ex.place_order(symbol="SOL/USDT", side="BUY", order_type="MARKET", quantity=100.0)
        b_before = ex.balance
        ex.execute_market_order(order.order_id, current_price=50.0)
        return b_before - ex.balance

    taker_cost = _fee_for_session(0.0006)
    maker_cost = _fee_for_session(0.0001)
    assert maker_cost < taker_cost, (
        f"Maker fee {maker_cost:.4f} should be less than taker {taker_cost:.4f}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Slippage tiers
# ──────────────────────────────────────────────────────────────────────────────


def test_btc_uses_major_slippage():
    """BTC/USDT market order uses major_slippage_bps (10 bps), not alt (35 bps)."""
    ex = PaperExecutor(
        initial_balance=10_000,
        slippage_bps=35.0,
        major_slippage_bps=10.0,
    )
    price = 100_000.0
    slipped = ex._calculate_slippage(price, OrderSide.BUY, "BTC/USDT")
    expected = price * (1 + 10.0 / 10_000)
    assert abs(slipped - expected) < 0.01, (
        f"BTC slippage {slipped:.2f} should use major tier {expected:.2f}"
    )


def test_eth_uses_major_slippage():
    """ETH/USDT also classified as major."""
    ex = PaperExecutor(slippage_bps=35.0, major_slippage_bps=10.0, initial_balance=10_000)
    price = 4_000.0
    slipped = ex._calculate_slippage(price, OrderSide.BUY, "ETH/USDT")
    expected = price * (1 + 10.0 / 10_000)
    assert abs(slipped - expected) < 0.01


def test_alt_uses_alt_slippage():
    """SOL/USDT uses the higher alt slippage tier (35 bps)."""
    ex = PaperExecutor(
        initial_balance=10_000,
        slippage_bps=35.0,
        major_slippage_bps=10.0,
    )
    price = 200.0
    slipped = ex._calculate_slippage(price, OrderSide.BUY, "SOL/USDT")
    expected = price * (1 + 35.0 / 10_000)
    assert abs(slipped - expected) < 0.001


def test_alt_slippage_higher_than_major_slippage():
    """Alt slippage > major slippage for the same price direction."""
    ex = PaperExecutor(
        initial_balance=10_000, slippage_bps=35.0, major_slippage_bps=10.0
    )
    major_fill = ex._calculate_slippage(100.0, OrderSide.BUY, "BTC/USDT")
    alt_fill = ex._calculate_slippage(100.0, OrderSide.BUY, "SOL/USDT")
    assert alt_fill > major_fill


def test_slippage_works_against_seller():
    """Sell-side slippage moves price DOWN (adverse for seller) for both tiers."""
    ex = PaperExecutor(
        initial_balance=10_000, slippage_bps=35.0, major_slippage_bps=10.0
    )
    assert ex._calculate_slippage(100.0, OrderSide.SELL, "BTC/USDT") < 100.0
    assert ex._calculate_slippage(100.0, OrderSide.SELL, "SOL/USDT") < 100.0


def test_empty_symbol_falls_back_to_alt_slippage():
    """No symbol provided → conservative alt slippage (not major)."""
    ex = PaperExecutor(
        initial_balance=10_000, slippage_bps=35.0, major_slippage_bps=10.0
    )
    slipped = ex._calculate_slippage(100.0, OrderSide.BUY, "")
    expected_alt = 100.0 * (1 + 35.0 / 10_000)
    assert abs(slipped - expected_alt) < 0.001


# ──────────────────────────────────────────────────────────────────────────────
# TP hold removed
# ──────────────────────────────────────────────────────────────────────────────


def test_simulation_min_target_hold_is_zero():
    """SIMULATION_MIN_TARGET_HOLD_SECONDS must be 0 — no artificial TP hold."""
    assert PositionManager.SIMULATION_MIN_TARGET_HOLD_SECONDS == 0, (
        "Artificial TP hold removed to match live exchange behavior "
        "(limit orders fill immediately when price touches the level)"
    )


# ──────────────────────────────────────────────────────────────────────────────
# BotConfig fee fields
# ──────────────────────────────────────────────────────────────────────────────


def test_bot_config_taker_fee_default():
    cfg = PaperTradingConfig()
    assert cfg.taker_fee_rate == 0.0006


def test_bot_config_maker_fee_default():
    cfg = PaperTradingConfig()
    assert cfg.maker_fee_rate == 0.0001


def test_bot_config_major_slippage_default():
    cfg = PaperTradingConfig()
    assert cfg.major_slippage_bps == 10.0


def test_bot_config_alt_slippage_default():
    cfg = PaperTradingConfig()
    assert cfg.alt_slippage_bps == 35.0


# ──────────────────────────────────────────────────────────────────────────────
# §15 blast-radius guard: live_executor.py fee_rate NOT changed
# ──────────────────────────────────────────────────────────────────────────────


def test_live_executor_fee_rate_not_changed():
    """Negative: live_executor.py must NOT reference 0.0006 or taker_fee_rate.
    The live path is §15 protected — fee changes there require explicit approval."""
    import pathlib
    live_src = pathlib.Path("backend/bot/executor/live_executor.py").read_text(encoding="utf-8")
    assert "taker_fee_rate" not in live_src, (
        "live_executor.py references taker_fee_rate — §15 violation, live path not approved"
    )
    assert "0.0006" not in live_src, (
        "live_executor.py hardcodes 0.0006 — §15 violation, live fee change not approved"
    )
