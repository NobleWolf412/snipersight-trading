"""
Regression for hot-path audit bug #4 (1_BROKEN): the Phemex Direct-REST fallback
guessed the price scale by magnitude — `scale = 1e8 if rows[0][1] > 1e6 else 1.0`
— which left sub-$0.01 coins (small raw Ep value) at scale 1.0, i.e. 1e8x inflated.
That corrupt price reached sizing/liquidation on the cycle the fallback fired (the
cache drift gate is a get()-time staleness check, not validation of a freshly
fetched frame, so it does NOT protect this path).

Fix (operator-approved Option B): derive the scale from an independent CCXT ticker
(snap to the nearest power of 10 of raw_close/ticker, verify within a factor of 5),
and REJECT the frame (return None → fetch_ohlcv returns empty df) if it can't be
verified — never feed an unverified price downstream.

See backend/diagnostics/decisions/2026-05-30__fix-design__phemex-fallback-scale.md
and 2026-05-29__hotpath-robustness-audit.md (bug #4).

Per CLAUDE.md §11 (loud-failure surfacing), §14 rubric 4 (negative+positive pair).
"""

from __future__ import annotations

from backend.data.adapters.phemex import PhemexAdapter


def _adapter(ticker_last=None, ticker_raises=False):
    """A PhemexAdapter with only fetch_ticker stubbed (bypasses __init__, which
    connects to the exchange). _derive_fallback_scale touches nothing else."""
    a = object.__new__(PhemexAdapter)
    if ticker_raises:
        def _ft(symbol, market_type=None):
            raise RuntimeError("rate limit")
        a.fetch_ticker = _ft
    else:
        a.fetch_ticker = lambda symbol, market_type=None: {"last": ticker_last}
    return a


# ──────────────────────────────────────────────────────────────────────────────
# The bug: sub-$0.01 coin with a small raw Ep value must derive scale 1e8, NOT 1.0
# ──────────────────────────────────────────────────────────────────────────────


def test_sub_cent_coin_derives_1e8_not_one():
    # PEPE real price 0.000012; raw Ep close 1200 (<= 1e6 → old heuristic gave 1.0).
    a = _adapter(ticker_last=0.000012)
    scale = a._derive_fallback_scale("PEPE/USDT:USDT", 1200.0)
    assert scale == 1e8                       # was 1.0 (the bug) → would be 1e8x inflated
    assert abs(1200.0 / scale - 0.000012) < 1e-12  # scaled close == real price


def test_sub_cent_tolerates_market_move_between_bar_and_ticker():
    # Last closed bar raw=1200 (≈0.000012); live ticker moved +30% to 0.0000156.
    # ratio ≈ 7.7e7 → round(log10)=8 → scale 1e8 still chosen (move can't cause a
    # power-of-10 misclassification).
    a = _adapter(ticker_last=0.0000156)
    assert a._derive_fallback_scale("PEPE/USDT:USDT", 1200.0) == 1e8


# ──────────────────────────────────────────────────────────────────────────────
# Positive (no-regression): normally-priced coins still resolve correctly
# ──────────────────────────────────────────────────────────────────────────────


def test_normal_coin_already_unscaled_gives_scale_one():
    a = _adapter(ticker_last=65000.0)
    assert a._derive_fallback_scale("BTC/USDT:USDT", 65000.0) == 1.0


def test_normal_coin_ep8_gives_1e8():
    a = _adapter(ticker_last=65000.0)
    assert a._derive_fallback_scale("BTC/USDT:USDT", 65000.0 * 1e8) == 1e8


# ──────────────────────────────────────────────────────────────────────────────
# Negative: unverifiable → reject (None), never return a guessed scale
# ──────────────────────────────────────────────────────────────────────────────


def test_rejects_when_ticker_fetch_raises():
    a = _adapter(ticker_raises=True)
    assert a._derive_fallback_scale("PEPE/USDT:USDT", 1200.0) is None


def test_rejects_when_ticker_price_zero():
    a = _adapter(ticker_last=0.0)
    assert a._derive_fallback_scale("X/USDT:USDT", 1200.0) is None


def test_rejects_when_raw_close_nonpositive():
    a = _adapter(ticker_last=0.000012)
    assert a._derive_fallback_scale("PEPE/USDT:USDT", 0.0) is None
