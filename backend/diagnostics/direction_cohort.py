"""
Step-0 direction-cohort backtest (read-only). decisions/2026-06-02__direction-authority-map...md

The question that decides "with-trend-only gate" vs "full conviction+abstain rewrite":
  Do counter-trend and neutral-tie trades actually have NEGATIVE expectancy?
If clean structural-majority trades are ~breakeven+ and the tie-break / counter-trend
cohorts bleed, the fix is a with-trend / abstain gate. If counter-trend is fine, a rewrite
removes edge.

Joins closed trades (trade_journal.jsonl: realized pnl + direction + regime + entry) to their
direction-decision telemetry (telemetry.db signal_generated: pre_dir_tie_break +
symbol_regime_trend), matched by symbol+direction+nearest-prior-timestamp. Reports expectancy
per pre_dir_tie_break cohort, per with/counter-trend, and the cross. Surfaces the match rate
(no silent drops).

Usage:  python -m backend.diagnostics.direction_cohort            # all journaled trades
        python -m backend.diagnostics.direction_cohort --since 2026-05-25
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
JOURNAL = REPO / "backend" / "cache" / "trade_journal.jsonl"
TELEM = REPO / "backend" / "cache" / "telemetry.db"
MATCH_WINDOW_S = 3600  # signal must precede the fill by <= 1h to be its decision event


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _dt(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _trend_sign(regime):
    rg = (regime or "")
    if rg.startswith("up"):
        return "up"
    if rg.startswith("down"):
        return "down"
    return "side"


def _cohort(rows):
    n = len(rows)
    if not n:
        return "n=0"
    w = sum(1 for r in rows if (_f(r["t"].get("pnl")) or 0) > 0)
    tot = sum(_f(r["t"].get("pnl")) or 0 for r in rows)
    return f"n={n:3} win={100*w/n:3.0f}% exp={tot/n:+7.2f} total={tot:+9.2f}"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    since = None
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
        trades.append(r)

    # signal_generated events: symbol -> list of (ts, direction, tie_break, regime_trend)
    sig = defaultdict(list)
    c = sqlite3.connect(f"file:{TELEM}?mode=ro", uri=True).cursor()
    for sym, ts, dj in c.execute(
        "SELECT symbol, timestamp, data_json FROM telemetry_events "
        "WHERE event_type='signal_generated' AND data_json LIKE '%pre_dir_tie_break%'"
    ):
        try:
            d = json.loads(dj)
        except Exception:
            continue
        t = _dt(ts)
        if t:
            sig[sym].append((t, d.get("direction"), d.get("pre_dir_tie_break"),
                             d.get("symbol_regime_trend")))
    for s in sig:
        sig[s].sort(key=lambda x: x[0])

    matched, unmatched = [], 0
    for t in trades:
        sym, d, et = t.get("symbol"), t.get("direction"), _dt(t.get("entry_time"))
        tb = None
        if et and sym in sig:
            best = None
            for (sts, sd, stb, strend) in sig[sym]:
                if sd != d:
                    continue
                gap = (et - sts).total_seconds()
                if 0 <= gap <= MATCH_WINDOW_S:
                    if best is None or sts > best[0]:  # latest signal before fill
                        best = (sts, stb)
            if best:
                tb = best[1]
        if tb:
            matched.append({"t": t, "tie_break": tb})
        else:
            unmatched += 1

    print("=== STEP-0 DIRECTION-COHORT BACKTEST ===")
    print(f"trades: {len(trades)} | matched to a decision event: {len(matched)} "
          f"| unmatched: {unmatched} ({100*unmatched/len(trades) if trades else 0:.0f}% — excluded, not silently zeroed)")
    if not matched:
        print("No matched trades — cannot segment. (telemetry window or symbol mismatch)")
        return 1

    # by tie_break
    by_tb = defaultdict(list)
    for m in matched:
        by_tb[m["tie_break"]].append(m)
    print("\n--- by pre_dir_tie_break (how direction was chosen) ---")
    for tb, rs in sorted(by_tb.items(), key=lambda kv: -len(kv[1])):
        print(f"  {str(tb):22} {_cohort(rs)}")

    # with / counter-trend (from journal regime + direction)
    def wc(m):
        d = m["t"].get("direction")
        s = _trend_sign(m["t"].get("regime"))
        if s == "side":
            return "side"
        return "with" if ((s == "up" and d == "LONG") or (s == "down" and d == "SHORT")) else "counter"
    by_wc = defaultdict(list)
    for m in matched:
        by_wc[wc(m)].append(m)
    print("\n--- by with/counter-trend (direction vs journal regime) ---")
    for k in ("with", "counter", "side"):
        if by_wc[k]:
            print(f"  {k:8} {_cohort(by_wc[k])}")

    # tie-break classes grouped: clean-majority vs tiebreak/default
    CLEAN = {"bull_majority", "bear_majority"}
    SOFT = {"regime_bullish", "regime_bearish", "neutral_default_long"}
    clean = [m for m in matched if m["tie_break"] in CLEAN]
    soft = [m for m in matched if m["tie_break"] in SOFT]
    qo = [m for m in matched if m["tie_break"] == "quality_override"]
    print("\n--- grouped (the decisive split) ---")
    print(f"  clean-majority (bull/bear_majority)        {_cohort(clean)}")
    print(f"  soft (regime tie-break + neutral->LONG)    {_cohort(soft)}")
    print(f"  quality_override                           {_cohort(qo)}")

    # verdict
    def exp(rs):
        return (sum(_f(r["t"].get("pnl")) or 0 for r in rs) / len(rs)) if rs else 0.0
    print("\n=== VERDICT (fees NOT included — gross) ===")
    ce, se, cte = exp(clean), exp(soft), exp(by_wc["counter"])
    print(f"  clean-majority expectancy: {ce:+.2f}/trade")
    print(f"  soft tie-break expectancy: {se:+.2f}/trade")
    print(f"  counter-trend expectancy : {cte:+.2f}/trade  (with-trend: {exp(by_wc['with']):+.2f})")
    if cte < 0 and se < 0:
        print("  => counter-trend AND soft-tiebreak BOTH negative -> a with-trend/abstain gate is supported.")
    elif cte >= 0:
        print("  => counter-trend NOT negative -> abstaining/with-trend-only would REMOVE edge. Do NOT gate it out.")
    else:
        print("  => mixed -> inspect the cross below before deciding.")

    print("\n--- RAW: counter-trend x tie_break ---")
    cross = defaultdict(list)
    for m in matched:
        if wc(m) == "counter":
            cross[m["tie_break"]].append(m)
    for tb, rs in sorted(cross.items(), key=lambda kv: -len(kv[1])):
        print(f"  counter/{str(tb):20} {_cohort(rs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
