"""
Entry RR-distortion diagnostic.

Proves the fill-geometry distortion (decisions/2026-06-13__fill-geometry-distortion.md)
and catches its return: compares each journal trade's RECORDED risk_reward_ratio
(planned, off entry_zone.midpoint) against its REALIZED RR (reward-to-nearest-target /
risk-to-stop, both measured from the actual fill). A large gap means a fill landed far
from plan and the position opened with inverted geometry.

After the RR-floor gate (rr_floor_at_entry, default 1.0) ships, the realized-RR<floor
share of EXECUTED trades should collapse toward zero — those entries are now rejected
pre-fill with reason_type=rr_collapsed_at_entry.

Usage:
    python -m backend.diagnostics.entry_rr_distortion
    python -m backend.diagnostics.entry_rr_distortion --since 2026-06-13
    python -m backend.diagnostics.entry_rr_distortion --floor 1.0
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

_JOURNAL = Path(__file__).resolve().parent.parent / "cache" / "trade_journal.jsonl"


def _realized_rr(entry: float, stop: float, targets: list[float]) -> float:
    """Mirror of paper_trading_service._entry_realized_rr (canonical). Kept inline so
    the diagnostic stays import-light; the production helper is regression-tested in
    tests/unit/test_rr_floor_at_entry.py."""
    if not entry or not stop or not targets:
        return 0.0
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    nearest = min(targets, key=lambda t: abs(t - entry))
    return abs(nearest - entry) / risk


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since", default=None, help="ISO date/time lower bound on entry_time")
    ap.add_argument("--floor", type=float, default=1.0, help="Realized-RR floor to report against")
    args = ap.parse_args()

    if not _JOURNAL.exists():
        print(f"no journal at {_JOURNAL}")
        return 1

    rows = [json.loads(l) for l in _JOURNAL.open(encoding="utf-8") if l.strip()]
    if args.since:
        rows = [r for r in rows if str(r.get("entry_time", "")) >= args.since]

    recs = []
    for r in rows:
        e, sl, tgts = r.get("entry_price"), r.get("stop_loss_level"), r.get("target_levels") or []
        rr_rec = r.get("risk_reward_ratio")
        rr_real = _realized_rr(e, sl, tgts)
        if rr_real <= 0:
            continue
        recs.append({
            "symbol": r.get("symbol"), "direction": r.get("direction"),
            "recorded": rr_rec, "realized": rr_real,
            "pnl": r.get("pnl"), "trade_type": r.get("trade_type"),
            "exit_reason": r.get("exit_reason"),
        })

    n = len(recs)
    if not n:
        print("no trades with computable geometry")
        return 0

    realized = [x["realized"] for x in recs]
    recorded = [x["recorded"] for x in recs if isinstance(x["recorded"], (int, float))]
    below = [x for x in recs if x["realized"] < args.floor]
    collapse = [x for x in recs if isinstance(x["recorded"], (int, float))
                and x["recorded"] > 0 and x["realized"] < x["recorded"] * 0.5]
    below_pnl = [x["pnl"] for x in below if isinstance(x["pnl"], (int, float))]
    ok_pnl = [x["pnl"] for x in recs if x["realized"] >= args.floor and isinstance(x["pnl"], (int, float))]

    print("=== ENTRY RR-DISTORTION ===")
    print(f"trades with computable realized RR: {n}"
          + (f"  (since {args.since})" if args.since else ""))
    print(f"realized RR: median={statistics.median(realized):.2f} "
          f"min={min(realized):.2f} max={max(realized):.2f}")
    if recorded:
        print(f"recorded RR: median={statistics.median(recorded):.2f} (planned, off midpoint)")
    print(f"realized < floor {args.floor:.2f}: {len(below)}/{n} ({100*len(below)/n:.0f}%)")
    print(f"realized < 50% of recorded (collapsed): {len(collapse)}/{n} ({100*len(collapse)/n:.0f}%)")
    if below_pnl:
        print(f"avg PnL realized<{args.floor:.2f}: {sum(below_pnl)/len(below_pnl):+.2f} (n={len(below_pnl)})")
    if ok_pnl:
        print(f"avg PnL realized>={args.floor:.2f}: {sum(ok_pnl)/len(ok_pnl):+.2f} (n={len(ok_pnl)})")

    print("\n=== worst 10 by realized RR ===")
    for x in sorted(recs, key=lambda r: r["realized"])[:10]:
        rec = x["recorded"] if isinstance(x["recorded"], (int, float)) else 0.0
        pnl = x["pnl"] if isinstance(x["pnl"], (int, float)) else 0.0
        print(f"  {str(x['symbol']):10} {str(x['direction']):5} "
              f"rec={rec:.2f} realized={x['realized']:.2f} pnl={pnl:+.2f} "
              f"{x['trade_type']} {x['exit_reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
