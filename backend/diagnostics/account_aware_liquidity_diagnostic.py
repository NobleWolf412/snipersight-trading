"""Account-aware liquidity admission — measure-before-ship diagnostic (Gate 1).

§15/§9-A: shows the derived liquidity floor for a given account (balance × leverage) and the
per-symbol admit/drop table, side-by-side against the fixed-$5M baseline, on LIVE Phemex volumes.
This is the baseline-evidence the decisions entry references before the threshold path changes.

Run:
    python -m backend.diagnostics.account_aware_liquidity_diagnostic
    python -m backend.diagnostics.account_aware_liquidity_diagnostic --balance 1000 --leverage 1
    python -m backend.diagnostics.account_aware_liquidity_diagnostic --balance 1000 --leverage 20

Output (CLAUDE.md §12): short summary first, structured table second, raw last.
"""
from __future__ import annotations

import argparse
from typing import Dict, List

from backend.analysis.pair_selection import derive_account_aware_floor, filter_illiquid_symbols

# Representative current STEALTH-ish universe (majors + liquid alts) for the side-by-side.
_UNIVERSE: List[str] = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "BNB/USDT", "DOGE/USDT",
    "ADA/USDT", "NEAR/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT", "INJ/USDT",
    "OP/USDT", "ARB/USDT", "APT/USDT", "TON/USDT", "SUI/USDT", "TRX/USDT",
]

_FIXED_FLOOR = 5_000_000.0


def _fetch_live_volumes_and_book(symbols: List[str]) -> tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
    """Live Phemex 24h perp quote-volume + actual order-book SPREAD (bps) + near-touch DEPTH ($).

    Spread and depth are the quantities that ACTUALLY determine slippage/stop-blowthrough — the thing
    24h volume only proxies (adversarial-review 2026-06-28: volume != instantaneous depth; bulk
    fetch_tickers carries no bid/ask on Phemex). A per-symbol order-book fetch is fine here — this is
    a one-shot diagnostic, NOT the hot scan path. depth = $ resting within 10 bps of mid on the side
    you'd HIT (asks for a buy, but symmetric enough as a thin-book signal). NaN on fetch failure.
    """
    from backend.data.adapters.phemex import PhemexAdapter
    adapter = PhemexAdapter(testnet=False, default_type="swap")
    vols = adapter.get_symbol_volumes(symbols)
    spreads: Dict[str, float] = {}
    depths: Dict[str, float] = {}
    for s in symbols:
        perp = s if ":" in s else f"{s}:USDT"
        try:
            ob = adapter.exchange.fetch_order_book(perp, limit=25)
            bids, asks = ob.get("bids") or [], ob.get("asks") or []
            if not bids or not asks:
                raise ValueError("empty book")
            best_bid, best_ask = bids[0][0], asks[0][0]
            mid = (best_bid + best_ask) / 2.0
            spreads[s] = (best_ask - best_bid) / mid * 10_000.0 if mid > 0 else float("nan")
            band = mid * 0.0010  # 10 bps
            depths[s] = sum(p * q for p, q in asks if p <= best_ask + band)
        except Exception:
            spreads[s] = float("nan")
            depths[s] = float("nan")
    return vols, spreads, depths


def run(balance: float, leverage: float, participation: float, hard_min: float) -> None:
    vols, spreads, depths = _fetch_live_volumes_and_book(_UNIVERSE)
    notional = balance * leverage
    aware_floor = derive_account_aware_floor(balance, leverage, participation, hard_min)
    clamp = "hard_min" if aware_floor <= hard_min else "formula"

    fixed_kept, fixed_dropped = filter_illiquid_symbols(list(_UNIVERSE), vols, _FIXED_FLOOR, context="diag_fixed")
    aware_kept, aware_dropped = filter_illiquid_symbols(list(_UNIVERSE), vols, aware_floor, context="diag_aware")

    newly_admitted = [s for s in aware_kept if s not in fixed_kept]

    # ── Summary ──
    print("ACCOUNT-AWARE LIQUIDITY ADMISSION — Gate 1")
    print("=" * 56)
    print(f"account: balance ${balance:,.0f} x leverage {leverage:g} => position notional ${notional:,.0f}")
    print(f"derived floor: ${aware_floor:,.0f}  (clamp branch: {clamp}; participation {participation:.2%}, hard_min ${hard_min:,.0f})")
    print(f"fixed baseline floor: ${_FIXED_FLOOR:,.0f}")
    print(f"universe {len(_UNIVERSE)}: fixed admits {len(fixed_kept)} | account-aware admits {len(aware_kept)} "
          f"(+{len(newly_admitted)} newly admitted)")
    print()

    # ── Table (spread + near-touch depth = the thin-book signal the volume floor misses) ──
    print(f"{'symbol':12s} {'24h_vol_usd':>14s} {'spread_bps':>10s} {'depth10bp_$':>12s}  {'fixed':>6s}  {'aware':>6s}")
    for s in sorted(_UNIVERSE, key=lambda x: -(vols.get(x, 0.0) or 0.0)):
        v = vols.get(s, 0.0) or 0.0
        sp = spreads.get(s, float("nan"))
        dp = depths.get(s, float("nan"))
        sp_str = (f"{sp:.1f}" + ("*" if sp >= 15.0 else " ")) if sp == sp else "n/a "  # * = wide (>=15bps)
        dp_str = f"{dp:,.0f}" if dp == dp else "n/a"
        f = "ADMIT" if s in fixed_kept else "drop"
        a = "ADMIT" if s in aware_kept else "drop"
        flag = "  <- new" if s in newly_admitted else ""
        print(f"{s:12s} {v:>14,.0f} {sp_str:>10s} {dp_str:>12s}  {f:>6s}  {a:>6s}{flag}")
    print("  (spread * = >=15bps wide; depth10bp_$ = ask liquidity within 10bps of mid — thin-book signal)")
    print()

    # ── Raw ──
    print("raw:")
    print(f"  newly_admitted = {newly_admitted}")
    print(f"  aware_dropped  = {aware_dropped}")
    print(f"  fixed_dropped  = {fixed_dropped}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--balance", type=float, default=1000.0)
    p.add_argument("--leverage", type=float, default=1.0)
    p.add_argument("--participation", type=float, default=0.005)
    p.add_argument("--hard-min", type=float, default=500_000.0)
    a = p.parse_args()
    run(a.balance, a.leverage, a.participation, a.hard_min)


if __name__ == "__main__":
    main()
