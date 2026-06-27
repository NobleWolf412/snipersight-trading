"""Journal-vs-executor reconciliation (2026-06-27). The journal P&L now reads the executor's ACTUAL
realized cash (PaperExecutor._realized_by_symbol via pop_position_realized) instead of the position
manager's modeled gross/planned figure. The invariant that makes the journal trustworthy: the
per-symbol accumulator shadows every balance mutation, so it EQUALS the real account delta — net of
fees, on the actually-filled qty — for any fill sequence (incl. partial fills, the thing that made
the old journal diverge from the account)."""
from backend.bot.executor.paper_executor import PaperExecutor

SYM = "ADA/USDT:USDT"
INIT = 10000.0


def _exec(**kw):
    return PaperExecutor(
        initial_balance=INIT, fee_rate=0.001, slippage_bps=0, major_slippage_bps=0, **kw
    )


def _fill(ex, side, qty, price):
    o = ex.place_order(SYM, side, "MARKET", qty)
    ex.execute_market_order(o.order_id, price)


def test_accumulator_equals_balance_delta_full_fills():
    ex = _exec(enable_partial_fills=False)
    _fill(ex, "SELL", 60000.0, 0.1492)   # open SHORT
    _fill(ex, "BUY", 60000.0, 0.1487)    # close SHORT lower -> profit
    delta = ex.balance - INIT
    acc = ex.pop_position_realized(SYM)
    assert acc is not None
    assert abs(acc - delta) < 1e-6, f"journal {acc} != account delta {delta}"
    # net of fees: gross profit was (0.1492-0.1487)*60000 = 30.0; acc must be LESS (entry+exit fees)
    assert acc < (0.1492 - 0.1487) * 60000.0
    # pop clears it (next position on the symbol starts fresh; double-read falls back)
    assert ex.pop_position_realized(SYM) is None


def test_accumulator_equals_balance_delta_with_partial_fills():
    # the invariant holds REGARDLESS of how the order partially filled — the accumulator shadows the
    # balance, so journal == account even when the old planned-qty journal would have diverged.
    ex = _exec(enable_partial_fills=True, partial_fill_prob=1.0, min_fill_pct=0.3, max_fill_pct=0.7)
    _fill(ex, "SELL", 60000.0, 0.1492)
    _fill(ex, "BUY", 60000.0, 0.1487)
    assert abs(ex.pop_position_realized(SYM) - (ex.balance - INIT)) < 1e-6


def test_long_trade_reconciles_both_outcomes():
    # LONG mirror — the accumulator is direction-blind, so a LONG profit and a LONG loss both
    # reconcile to the account delta exactly (belt-and-suspenders symmetry coverage).
    ex = _exec(enable_partial_fills=False)
    _fill(ex, "BUY", 60000.0, 0.1487)    # open LONG
    _fill(ex, "SELL", 60000.0, 0.1492)   # close higher -> profit
    acc = ex.pop_position_realized(SYM)
    assert abs(acc - (ex.balance - INIT)) < 1e-6 and acc > 0
    ex2 = _exec(enable_partial_fills=False)
    _fill(ex2, "BUY", 60000.0, 0.1492)
    _fill(ex2, "SELL", 60000.0, 0.1487)  # close lower -> loss
    acc2 = ex2.pop_position_realized(SYM)
    assert abs(acc2 - (ex2.balance - INIT)) < 1e-6 and acc2 < 0


def test_loss_trade_also_reconciles():
    # a losing SHORT (buy back higher) — accumulator still == balance delta, and is negative
    ex = _exec(enable_partial_fills=False)
    _fill(ex, "SELL", 60000.0, 0.1487)
    _fill(ex, "BUY", 60000.0, 0.1492)   # close higher -> loss
    acc = ex.pop_position_realized(SYM)
    assert abs(acc - (ex.balance - INIT)) < 1e-6
    assert acc < 0
