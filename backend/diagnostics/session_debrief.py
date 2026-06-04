"""
Session debrief - one-page post-session scorecard + routing. READ-ONLY.

The big-picture rollup you actually want after a trading session, in ONE command,
so you don't have to choose among /scan-autopsy /trade-autopsy /rejection-survey
/confluence-trace. Consolidates trade_journal.jsonl (closed trades) + the latest
signals.jsonl (rejections / attempts) into the metrics this codebase has repeatedly
shown matter, then flags what's wrong and points at the right drill-down.

Usage (from repo root):
  python -m backend.diagnostics.session_debrief             # latest session (+ recent window for context)
  python -m backend.diagnostics.session_debrief <session_id>
  python -m backend.diagnostics.session_debrief --all       # every journaled trade

Output is §12 paste-friendly: SUMMARY first, SCORECARD second, RAW last.
Tolerant of older trades missing the 2026-06-02 calc-geometry keys (stop_loss_rationale,
tp1_clamped) - they show as 'unrecorded'.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
JOURNAL = REPO / "backend" / "cache" / "trade_journal.jsonl"
SIGNALS_GLOB = str(REPO / "logs" / "paper_trading" / "session_*" / "signals.jsonl")
SCALP_MONOCULTURE_PCT = 80.0
WIDE_STOP_ATR = 1.3  # operator-selected reachability ceiling


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _load_journal():
    if not JOURNAL.exists():
        return []
    out = []
    for line in JOURNAL.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def _trend_sign(regime: str) -> str:
    rg = (regime or "")
    if rg.startswith("up"):
        return "up"
    if rg.startswith("down"):
        return "down"
    return "side"


def _with_trend(r) -> str:
    d, s = r.get("direction"), _trend_sign(r.get("regime"))
    if s == "side":
        return "side"
    if (s == "up" and d == "LONG") or (s == "down" and d == "SHORT"):
        return "with"
    return "counter"


def _stop_branch(rationale: str) -> str:
    t = (rationale or "").lower()
    if not t:
        return "unrecorded"
    if "no swing/structure found" in t:
        return "atr-fallback"
    if "capped:" in t:
        return "max-stop-cap"
    return "structural"


def _stats(rows):
    n = len(rows)
    if not n:
        return None
    wins = [r for r in rows if (_f(r.get("pnl")) or 0) > 0]
    losses = [r for r in rows if (_f(r.get("pnl")) or 0) <= 0]
    tot = sum(_f(r.get("pnl")) or 0 for r in rows)
    aw = sum(_f(r["pnl"]) for r in wins) / len(wins) if wins else 0.0
    al = sum(_f(r["pnl"]) for r in losses) / len(losses) if losses else 0.0
    wr = len(wins) / n
    return {"n": n, "win": 100 * wr, "exp": tot / n, "tot": tot,
            "aw": aw, "al": al, "payoff": abs(aw / al) if al else float("inf")}


def _median(vals):
    s = sorted(v for v in vals if v is not None)
    return s[len(s) // 2] if s else 0.0


def _scorecard(label, rows, flags):
    s = _stats(rows)
    if not s:
        print(f"  {label}: no closed trades")
        return
    verdict = "POSITIVE" if s["exp"] > 0 else "NEGATIVE"
    print(f"  {label}: n={s['n']}  win={s['win']:.0f}%  expectancy={s['exp']:+.2f}/trade ({verdict})  "
          f"payoff={s['payoff']:.2f}  (avgW {s['aw']:+.2f} / avgL {s['al']:+.2f})")
    if s["exp"] <= 0 and s["n"] >= 5:
        flags.append(f"{label}: negative expectancy ({s['exp']:+.2f}/trade over {s['n']} trades)")

    # direction × trend-sign cohort
    by = defaultdict(list)
    for r in rows:
        by[_with_trend(r)].append(r)
    parts = []
    for k in ("with", "counter", "side"):
        st = _stats(by[k])
        if st:
            parts.append(f"{k}-trend n={st['n']} win={st['win']:.0f}% exp={st['exp']:+.2f}")
    if parts:
        print("      cohort: " + "  |  ".join(parts))
    cc = _stats(by["counter"])
    if cc and cc["n"] >= 3 and cc["exp"] < 0:
        flags.append(f"{label}: counter-trend trades bleeding ({cc['exp']:+.2f}/trade, n={cc['n']})")

    # trade-type mix
    tt = Counter((r.get("trade_type") or "?") for r in rows)
    scalp_pct = 100 * tt.get("scalp", 0) / s["n"]
    print(f"      trade-type: " + " ".join(f"{k}={100*v/s['n']:.0f}%" for k, v in tt.most_common()))
    if scalp_pct >= SCALP_MONOCULTURE_PCT:
        flags.append(f"{label}: scalp monoculture ({scalp_pct:.0f}% scalp) - cascade not diversifying")

    # stop-branch + reachability
    branch = Counter(_stop_branch(r.get("stop_loss_rationale", "")) for r in rows)
    sd = [_f(r.get("stop_distance_atr")) for r in rows]
    med_sd = _median(sd)
    clamped = [r for r in rows if r.get("tp1_clamped") is True]
    th = [len(r.get("targets_hit") or []) for r in rows]
    print(f"      stop-branch: " + " ".join(f"{k}={v}" for k, v in branch.most_common())
          + f"  | median stop={med_sd:.2f} ATR | tp1_clamped={len(clamped)}/{s['n']}"
          + f" | avg targets_hit={sum(th)/len(th):.2f}")
    if med_sd >= WIDE_STOP_ATR:
        flags.append(f"{label}: wide stops (median {med_sd:.2f} ATR >= {WIDE_STOP_ATR}) - TP1 reachability risk")
    if branch.get("unrecorded", 0) == s["n"]:
        flags.append(f"{label}: stop_loss_rationale not yet journaled (pre-2026-06-02 trades or bot needs restart)")

    # exits
    print("      exits: " + str(dict(Counter(r.get("exit_reason") for r in rows))))


def _rejection_rollup(flags):
    files = sorted(glob.glob(SIGNALS_GLOB), key=os.path.getmtime)
    if not files:
        print("  (no signals.jsonl found)")
        return
    newest = files[-1]
    sid = os.path.basename(os.path.dirname(newest)).replace("session_", "")
    rows = []
    for l in open(newest, encoding="utf-8", errors="ignore"):
        l = l.strip()
        if l:
            try:
                rows.append(json.loads(l))
            except json.JSONDecodeError:
                pass
    res = Counter(r.get("result") for r in rows)
    dirs = Counter(r.get("direction") for r in rows)
    rej = Counter(r.get("reason_type") or r.get("gate_name") for r in rows if r.get("result") == "filtered")
    regimes = Counter(r.get("regime") for r in rows)
    print(f"  latest scan session {sid}: {len(rows)} signals | results={dict(res)}")
    print(f"      direction attempted: {dict(dirs)} | regime: {dict(regimes.most_common(3))}")
    print("      top reject reasons: " + str(dict(rej.most_common(6))))
    ex = res.get("executed", 0)
    filt = res.get("filtered", 0)
    if filt and ex == 0:
        flags.append(f"latest session executed 0 / {filt} filtered - bot effectively not trading this window")
    longs, shorts = dirs.get("LONG", 0), dirs.get("SHORT", 0)
    up_reg = sum(v for k, v in regimes.items() if (k or "").startswith("up"))
    down_reg = sum(v for k, v in regimes.items() if (k or "").startswith("down"))
    if down_reg > up_reg and longs > shorts:
        flags.append(f"direction-vs-regime mismatch: {longs} LONG vs {shorts} SHORT attempts in a DOWN regime")


def _factor_edge(flags):
    """Corpus-wide factor-edge rollup (all sessions): does any confluence factor
    actually predict outcomes? Surfaces the headline + flags inert/anti factors and
    the no-edge case. Read-only; reuses factor_contribution's computation."""
    print("\n=== FACTOR EDGE (corpus: all sessions) ===")
    try:
        from backend.diagnostics import factor_contribution as fc
    except Exception as e:  # pragma: no cover - import guard
        print(f"  (factor_contribution unavailable: {e})")
        return
    signals, files, trades = fc.load_corpus()
    if not signals:
        print("  (no factor-bearing signals.jsonl yet — run a session first)")
        return
    res = fc.analyze(signals, trades)
    lines, summ = fc.compact_lines(res, files_n=len(files))
    for ln in lines:
        print(ln)
    print("  full table: python -m backend.diagnostics.factor_contribution")

    best, noise = summ["best"], summ["noise"]
    if summ["anti"]:
        flags.append("factor edge: ANTI-signal factor(s) " + ", ".join(summ["anti"])
                     + " score high on LOSERS — likely mis-wired or inverted")
    if best is not None and noise is not None:
        br = abs(res["stats"][best]["r_out"])
        if br < noise:
            flags.append(f"factor edge: NO factor predicts outcome — best |r_out| {br:.2f} "
                         f"below noise floor {noise:.2f}; scoring has no demonstrated edge on taken trades")
    if len(summ["dead"]) >= 4:
        flags.append(f"factor edge: {len(summ['dead'])} inert factors (rare/flat, no "
                     "discrimination) — trim candidates (hygiene, not edge)")


def _routing(flags):
    print("\n=== THREADS / DRILL-DOWNS ===")
    if not flags:
        print("  No red flags. Spot-check: /trade-autopsy last-loss")
    routes = {
        "monoculture": "-> cascade/regime: /confluence-trace <SYM>  +  check regime_detector volatility bands",
        "counter-trend": "-> direction logic: /confluence-trace <SYM> ; review pre-direction tally + counter-trend gate",
        "wide stops": "-> stop geometry: grep 'WIDE STOP' logs/backend.err.log ; /trade-autopsy last-loss",
        "negative expectancy": "-> worst trade: /trade-autopsy last-loss ; edge-by-regime cohort",
        "not trading": "-> rejection bottleneck: /rejection-survey 50 ; /scan-autopsy last",
        "mismatch": "-> /scan-autopsy last (why longs in a down regime) ; /confluence-trace <SYM>",
        "rationale not yet journaled": "-> restart the backend so new trades record stop branch + clamp",
        "factor edge": "-> factor analysis: python -m backend.diagnostics.factor_contribution (full per-factor table + redundancy). Trim FLAT/ANTI for hygiene; but if best |r|<noise, re-weighting won't create edge — the strategy needs a new predictive input, not tuning.",
    }
    for i, fl in enumerate(flags, 1):
        hint = next((v for k, v in routes.items() if k in fl.lower()), "-> /trade-autopsy last-loss")
        print(f"  {i}. {fl}\n       {hint}")


def main():
    # Robust against Windows cp1252 consoles — never crash on a stray non-ASCII char.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    rows = _load_journal()
    if not rows:
        print("No trade_journal.jsonl rows.")
        return 1
    by_sess = defaultdict(list)
    for r in rows:
        by_sess[r.get("session_id")].append(r)
    order = sorted(by_sess.items(), key=lambda kv: kv[1][0].get("entry_time", ""))

    arg = sys.argv[1] if len(sys.argv) > 1 else None
    flags: list[str] = []

    print("=== SESSION DEBRIEF ===")
    if arg == "--all":
        target_label, target_rows, window_rows = "ALL", rows, None
    else:
        sid = arg or order[-1][0]
        target_label = f"session {str(sid)[:8]}"
        target_rows = by_sess.get(sid, [])
        # recent window = last 5 sessions for context when the target session is thin
        window_rows = [r for _s, rs in order[-5:] for r in rs]

    print(f"\n--- TARGET: {target_label} ---")
    _scorecard(target_label, target_rows, flags)
    if window_rows is not None and len(target_rows) < 10:
        print("\n--- RECENT WINDOW (last 5 sessions, context - target was thin) ---")
        _scorecard("recent", window_rows, flags)

    print("\n--- LATEST SCAN / REJECTIONS ---")
    _rejection_rollup(flags)

    _factor_edge(flags)

    _routing(flags)

    print("\n=== RAW: per-session ledger (chrono) ===")
    for sid, rs in order[-8:]:
        st = _stats(rs)
        if st:
            sc = 100 * Counter(r.get("trade_type") for r in rs).get("scalp", 0) / st["n"]
            print(f"  {str(sid)[:8]} {rs[0].get('entry_time','')[:10]} n={st['n']:3} "
                  f"win={st['win']:3.0f}% exp={st['exp']:+7.2f} scalp={sc:.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
