"""
Phase 1 baseline extractor for the TP1 reachability fix
(decisions/2026-05-30__fix-design__tp1-reachability.md).

Read-only. Run AFTER a paper session to produce the baseline table that §15 requires
before any clamp/coherence threshold is set.

Usage (from repo root):
    python -m backend.diagnostics.stop_reachability_baseline            # latest journal session
    python -m backend.diagnostics.stop_reachability_baseline <sid>      # a specific session_id

Reports, for the target session vs the GOOD reference window (journal entries before
2026-05-24), the joint distribution the design doc calls for:
  - outcome: n, win%, expectancy, avg win/loss
  - stop_distance_atr buckets (structural <1.0 / ~1.5 fallback-or-cap / wide >=1.5)
  - targets_hit, exit-reason mix
  - WIDE STOP branch distribution from logs/dev_servers.log (if present)

Output: short summary first, table second, raw buckets last (CLAUDE.md §12).
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
JOURNAL = REPO / "backend" / "cache" / "trade_journal.jsonl"
DEVLOG = REPO / "logs" / "dev_servers.log"
GOOD_CUTOFF = "2026-05-24"  # journal entries before this = healthy reference window


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _load_journal():
    if not JOURNAL.exists():
        return []
    rows = []
    for line in JOURNAL.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def _outcome(rows):
    n = len(rows)
    if not n:
        return None
    wins = [r for r in rows if (_f(r.get("pnl")) or 0) > 0]
    losses = [r for r in rows if (_f(r.get("pnl")) or 0) <= 0]
    aw = sum(_f(r["pnl"]) for r in wins) / len(wins) if wins else 0.0
    al = sum(_f(r["pnl"]) for r in losses) / len(losses) if losses else 0.0
    wr = len(wins) / n
    return {
        "n": n,
        "win_pct": 100 * wr,
        "avg_win": aw,
        "avg_loss": al,
        "expectancy": wr * aw + (1 - wr) * al,
        "payoff": abs(aw / al) if al else float("inf"),
    }


def _stop_buckets(rows):
    b = {"structural<1.0": 0, "~1.5 (fallback/cap)": 0, "wide>=1.5 (other)": 0, "1.0-1.5": 0}
    dists = []
    for r in rows:
        d = _f(r.get("stop_distance_atr"))
        if d is None:
            continue
        dists.append(d)
        if d < 1.0:
            b["structural<1.0"] += 1
        elif abs(d - 1.5) < 0.06:
            b["~1.5 (fallback/cap)"] += 1
        elif d >= 1.5:
            b["wide>=1.5 (other)"] += 1
        else:
            b["1.0-1.5"] += 1
    med = sorted(dists)[len(dists) // 2] if dists else 0.0
    return b, med, dists


def _wide_stop_log_summary():
    if not DEVLOG.exists():
        return None
    branch = Counter()
    dists = []
    pat = re.compile(r"WIDE STOP \[[A-Z]+ [a-z_]+\]: ([a-z-]+) \| dist=([0-9.]+) ATR")
    try:
        for line in DEVLOG.open(encoding="utf-8", errors="ignore"):
            m = pat.search(line)
            if m:
                branch[m.group(1)] += 1
                dists.append(float(m.group(2)))
    except OSError:
        return None
    if not dists:
        return None
    return {"branch": dict(branch.most_common()), "n": len(dists),
            "median": sorted(dists)[len(dists) // 2], "max": max(dists)}


def main():
    rows = _load_journal()
    if not rows:
        print("No trade_journal.jsonl rows found at", JOURNAL)
        return 1

    sid = sys.argv[1] if len(sys.argv) > 1 else rows[-1].get("session_id")
    target = [r for r in rows if r.get("session_id") == sid]
    good = [r for r in rows if (r.get("entry_time", "") or "") < GOOD_CUTOFF]

    to = _outcome(target)
    go = _outcome(good)
    tb, tmed, tdists = _stop_buckets(target)
    gb, gmed, _ = _stop_buckets(good)
    wide = _wide_stop_log_summary()

    print("=== STOP REACHABILITY BASELINE ===")
    print(f"target session: {sid}  (n={len(target)})   |   GOOD reference (<{GOOD_CUTOFF}, n={len(good)})")
    if to and go:
        verdict = "HEALTHY-LIKE" if to["expectancy"] > 0 else "DEGRADED"
        print(f"SUMMARY: target expectancy={to['expectancy']:+.2f}/trade ({verdict}) "
              f"vs good {go['expectancy']:+.2f}; target median stop={tmed:.2f} ATR vs good {gmed:.2f} ATR")
    print()

    print("--- OUTCOME ---")
    print(f"{'':10}{'n':>5}{'win%':>7}{'avg_win':>9}{'avg_loss':>10}{'payoff':>8}{'expectancy':>12}")
    for label, o in (("target", to), ("good", go)):
        if o:
            print(f"{label:10}{o['n']:>5}{o['win_pct']:>6.0f}%{o['avg_win']:>9.2f}"
                  f"{o['avg_loss']:>10.2f}{o['payoff']:>8.2f}{o['expectancy']:>+12.2f}")
    print()

    print("--- STOP DISTANCE BUCKETS (% of trades) ---")
    for label, b, tot in (("target", tb, len(target)), ("good", gb, len(good))):
        if tot:
            parts = "  ".join(f"{k}={100 * v / tot:.0f}%" for k, v in b.items())
            print(f"{label:8} {parts}")
    print()

    print("--- TARGETS_HIT / EXIT MIX (target session) ---")
    th = [len(r.get("targets_hit") or []) for r in target]
    print(f"avg targets_hit: {sum(th) / len(th):.2f}" if th else "no trades")
    print("exit_reasons:", dict(Counter(r.get("exit_reason") for r in target)))
    print()

    print("--- WIDE STOP diagnostic (logs/dev_servers.log; spans ALL recent sessions) ---")
    if wide:
        print(f"n={wide['n']}  median={wide['median']:.2f} ATR  max={wide['max']:.2f} ATR")
        print("branch:", wide["branch"])
        print("(NOTE: log spans all sessions since last rotation, not just this one)")
    else:
        print("no WIDE STOP lines found (session may not have generated wide stops, or log rotated)")
    print()

    print("--- RAW: target stop_distance_atr sorted ---")
    print([round(d, 2) for d in sorted(tdists)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
