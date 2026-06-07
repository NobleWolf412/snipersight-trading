"""
Fill-rate + arm comparison for the maker-execution experiment (GATE 1, T14). READ-ONLY.

The make-or-break number for rest_maker: do resting limits at the OB actually FILL, or do they
expire unfilled (especially short-limits above a falling market)? And of those that fill, are they
adversely selected (the reversals = losers)?

Reads signals.jsonl (tagged `execution_mode` as of the Phase-1 commit) + trade_journal.jsonl.
Per execution_mode arm:
  - result distribution (executed / pending / filtered) from signals.jsonl
  - implied FILL RATE — rest_maker places a resting limit (logged result="pending") and the
    monitor loop later logs a second result="executed" when it fills; expired ones never get the
    "executed" row. So fill_rate ≈ executed_rows / pending_rows. (snap_taker fills immediately, so
    its executed rows are ~= placements and pending~0 — shown as a sanity baseline.)
  - closed-trade count + expectancy from the journal (cohort by execution_mode)
  - adverse-selection probe: win% and avg loc_bb of FILLED (closed) trades — to compare against
    snap_taker (maker fills should be at better pullback locations IF the thesis holds).

Caveat: paper OVERSTATES maker fill rate (fills the instant price touches the limit; no queue
position / trade-through). So a healthy paper fill rate is a CEILING. See
decisions/2026-06-06__maker-execution-experiment-design.md.

Usage:  python -m backend.diagnostics.fill_rate            # all sessions, by arm
        python -m backend.diagnostics.fill_rate --since 2026-06-07
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SIGNALS_GLOB = str(REPO / "logs" / "paper_trading" / "session_*" / "signals.jsonl")
JOURNAL = REPO / "backend" / "cache" / "trade_journal.jsonl"


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    since = None
    if "--since" in sys.argv:
        since = sys.argv[sys.argv.index("--since") + 1]

    # signals by arm
    by_arm = defaultdict(Counter)          # execution_mode -> Counter(result)
    for fp in sorted(glob.glob(SIGNALS_GLOB), key=os.path.getmtime):
        for line in open(fp, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if since and (r.get("timestamp", "") or "") < since:
                continue
            arm = r.get("execution_mode", "snap_taker")  # pre-Phase-1 rows default to snap_taker
            by_arm[arm][r.get("result", "?")] += 1

    # closed trades by arm
    trades_by_arm = defaultdict(list)
    if JOURNAL.exists():
        for line in JOURNAL.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                t = json.loads(line)
            except json.JSONDecodeError:
                continue
            if since and (t.get("entry_time", "") or "") < since:
                continue
            trades_by_arm[t.get("execution_mode", "snap_taker")].append(t)

    if not by_arm:
        print("No signals.jsonl rows found.")
        return 1

    print("=== FILL-RATE + ARM COMPARISON (GATE 1) ===")
    print(f"window: {'ALL' if not since else '>= ' + since}")
    if "rest_maker" not in by_arm and "rest_maker" not in trades_by_arm:
        print("\n  No rest_maker data yet. Run a paper session with execution_mode='rest_maker'")
        print("  (POST /api/paper-trading/start with \"execution_mode\":\"rest_maker\"; restart the")
        print("  backend first so it's on Phase-1 code). snap_taker baseline shown below.\n")

    print(f"\n  {'arm':12}{'signals':>9}{'filtered':>9}{'pending':>9}{'executed':>9}{'fill_rate':>10}")
    for arm in sorted(by_arm, key=lambda a: a != "rest_maker"):
        c = by_arm[arm]
        total = sum(c.values())
        pend = c.get("pending", 0)
        exe = c.get("executed", 0)
        # rest_maker: executed rows come from pending fills → executed/pending ≈ fill rate.
        # snap_taker: fills immediately (pending~0) → fill rate ~ n/a (baseline).
        fr = (exe / pend) if pend else None
        fr_s = f"{100*fr:.0f}%" if fr is not None else "n/a(imm)"
        print(f"  {arm:12}{total:>9}{c.get('filtered',0):>9}{pend:>9}{exe:>9}{fr_s:>10}")

    print("\n  --- closed trades by arm (journal) ---")
    for arm in sorted(trades_by_arm, key=lambda a: a != "rest_maker"):
        ts = trades_by_arm[arm]
        n = len(ts)
        if not n:
            continue
        pnls = [_f(t.get("pnl")) or 0 for t in ts]
        win = sum(1 for p in pnls if p > 0)
        exp = sum(pnls) / n
        print(f"  {arm:12} n={n:4}  win={100*win/n:3.0f}%  exp={exp:+.2f}/trade (gross)")

    print("\n=== GATE 1 READ ===")
    rm_pend = by_arm.get("rest_maker", {}).get("pending", 0)
    rm_exe = by_arm.get("rest_maker", {}).get("executed", 0)
    if rm_pend:
        fr = rm_exe / rm_pend
        print(f"  rest_maker fill rate ≈ {100*fr:.0f}% ({rm_exe}/{rm_pend}).")
        if fr < 0.4:
            print("  -> LOW. Resting limits are missing most setups (expected for trend-shorting). If")
            print("     this holds, maker execution is structurally incompatible → strategy verdict #3.")
        else:
            print("  -> survives. Proceed to compare net expectancy vs snap_taker (Phase 2 fee model),")
            print("     but remember paper OVERSTATES maker fills — treat as a ceiling.")
        print("  Also check the closed-trade win%/exp above: if rest_maker fills are reversal-biased")
        print("  (worse win% than snap_taker), that is the adverse-selection failure mode.")
    else:
        print("  (no rest_maker resting orders recorded yet — run the experiment session.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
