"""
Edge-significance + edge-after-(modeled)-fees — the viability smoking-gun (read-only).

Answers the T8 question we kept describing but never computing: across clean sessions, is the
bot's per-trade expectancy DISTINGUISHABLE FROM ZERO, and does it survive a realistic fee?

Two corrections that make this runnable on paper data (verified 2026-06-06):
  1. The journal `pnl` is GROSS price-move PnL — `pnl == quantity*(exit-entry)*dir` to the cent
     (the modeled fee_rate=0.001 hits the paper executor BALANCE, not the journal row). So fees
     are NOT already netted; subtracting them here is correct, not double-counting.
  2. Slippage IS already in (the executor slips fill prices, so entry/exit already reflect it).
     Only the per-fill FEE is excluded. Funding on held swings is NOT modeled (extra drag — so
     these net numbers are an OPTIMISTIC ceiling for swing-heavy windows).

What it does, per trade: gross_pnl (journal) and notional legs (qty*entry, qty*exit). For a set
of per-side fee rates it computes net = gross - fee_side*qty*(entry+exit), then BOOTSTRAPS the
mean expectancy (B resamples) for a 95% CI and P(expectancy>0). Also the BREAKEVEN per-side fee
(where mean net hits 0) vs Phemex-real (~0.06%) and the bot's modeled 0.10%.

Real per-fill exchange fees (maker/taker/promos) remain unmeasurable in paper — see
decisions/2026-06-06__fills-fees-ingestion-scope.md. This models them; it does not reconcile them.

Usage:  python -m backend.diagnostics.edge_significance              # post-clamp clean window
        python -m backend.diagnostics.edge_significance --all
        python -m backend.diagnostics.edge_significance --since 2026-06-01
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
JOURNAL = REPO / "backend" / "cache" / "trade_journal.jsonl"
CLAMP_DATE = "2026-05-31"           # wide-stop-era confound boundary (clean window default)
B = 20000                            # bootstrap resamples
# per-SIDE fee scenarios (round-trip = 2x). Phemex perp taker ~0.06%/side; bot models 0.10%/side.
FEE_SIDES = [("gross (0 fee)", 0.0), ("Phemex taker 0.06%/side", 0.0006), ("bot model 0.10%/side", 0.001)]


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# Deterministic LCG bootstrap (no Math.random/seed reliance; reproducible run-to-run).
def _boot_ci(vals, b=B):
    n = len(vals)
    if n < 5:
        return None, None, None
    s = 0x2545F4914F6CDD1D
    means = []
    for _ in range(b):
        tot = 0.0
        for _ in range(n):
            s = (s * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
            tot += vals[(s >> 33) % n]
        means.append(tot / n)
    means.sort()
    lo = means[int(0.025 * b)]
    hi = means[int(0.975 * b)]
    p_gt0 = sum(1 for m in means if m > 0) / b
    return lo, hi, p_gt0


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    since = None if "--all" in sys.argv else CLAMP_DATE
    if "--since" in sys.argv:
        since = sys.argv[sys.argv.index("--since") + 1]

    trades = []
    for line in JOURNAL.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if since and (r.get("entry_time", "") or "") < since:
            continue
        g = _f(r.get("pnl"))
        e, x, q = _f(r.get("entry_price")), _f(r.get("exit_price")), _f(r.get("quantity"))
        if g is None or not all(v is not None for v in (e, x, q)):
            continue
        legs = q * (e + x)            # entry notional + exit notional (per-side fee base)
        trades.append({"gross": g, "legs": legs, "tt": r.get("trade_type")})

    n = len(trades)
    if n < 10:
        print(f"Only {n} trades in window — too few to test significance.")
        return 1

    print("=== EDGE SIGNIFICANCE + EDGE-AFTER-(MODELED)-FEES ===")
    win = sum(1 for t in trades if t["gross"] > 0)
    wins = [t["gross"] for t in trades if t["gross"] > 0]
    losses = [t["gross"] for t in trades if t["gross"] <= 0]
    aw = sum(wins) / len(wins) if wins else 0.0
    al = sum(losses) / len(losses) if losses else 0.0
    print(f"window: {'ALL' if since is None else '>= ' + since}  |  n={n}  win={100*win/n:.0f}%  "
          f"payoff={abs(aw/al) if al else float('inf'):.2f}  (avgW {aw:+.2f} / avgL {al:+.2f})")
    swing_pct = 100 * sum(1 for t in trades if t["tt"] == "swing") / n
    print(f"  (swing {swing_pct:.0f}% — funding on held swings NOT modeled, so net is an OPTIMISTIC ceiling)")

    print(f"\n--- expectancy per fee scenario (95% CI via {B:,}-resample bootstrap) ---")
    print(f"  {'scenario':26}{'exp/trade':>11}{'95% CI':>20}{'P(>0)':>8}")
    for label, side in FEE_SIDES:
        net = [t["gross"] - side * t["legs"] for t in trades]
        mean = sum(net) / n
        lo, hi, p = _boot_ci(net)
        ci = f"[{lo:+.2f}, {hi:+.2f}]" if lo is not None else "n/a"
        print(f"  {label:26}{mean:+11.2f}{ci:>20}{(p if p is not None else 0):>8.0%}")

    # Breakeven per-side fee: mean(gross) = side* * mean(legs)
    mean_gross = sum(t["gross"] for t in trades) / n
    mean_legs = sum(t["legs"] for t in trades) / n
    be_side = (mean_gross / mean_legs) if mean_legs else 0.0
    print(f"\n--- breakeven fee ---")
    print(f"  gross expectancy {mean_gross:+.2f}/trade breaks even at a per-side fee of {100*be_side:.4f}% "
          f"({100*be_side*2:.4f}% round-trip)")
    print(f"  reference: Phemex taker ~0.06%/side (0.12% rt) | bot model 0.10%/side (0.20% rt)")

    # Verdict
    net_real = [t["gross"] - 0.0006 * t["legs"] for t in trades]
    lo_r, hi_r, p_r = _boot_ci(net_real)
    print("\n=== VERDICT ===")
    if lo_r is not None and lo_r <= 0 <= hi_r:
        print(f"  At Phemex-real fees the 95% CI [{lo_r:+.2f}, {hi_r:+.2f}] INCLUDES ZERO "
              f"(P(edge>0)={p_r:.0%}). No statistically demonstrated edge after fees.")
    elif lo_r is not None and lo_r > 0:
        print(f"  At Phemex-real fees the 95% CI [{lo_r:+.2f}, {hi_r:+.2f}] is ABOVE ZERO — a real "
              f"(if modest) net edge. Verify on more sessions + add funding before trusting.")
    else:
        print(f"  At Phemex-real fees expectancy is NEGATIVE (CI [{lo_r:+.2f}, {hi_r:+.2f}]).")
    if be_side < 0.0006:
        print(f"  Breakeven per-side fee {100*be_side:.4f}% is BELOW Phemex taker 0.06% → net-negative at real fees.")
    print("  (modeled fees only — real per-fill fees unmeasurable in paper; funding excluded.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
