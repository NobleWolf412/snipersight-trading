"""
T16 reversal-veto counterfactual — READ-ONLY, ship-nothing.

The question both the root-cause synthesis (workflow wf_73fcbcdc, §4.2) and the adversarial
review agreed must be answered BEFORE any scorer/smc code is written:

    If we had braked ("vetoed") trades that entered into a reversal AGAINST their direction,
    would the clean post-clamp book have improved -- or would the brake have skipped the
    continuation trades that were WORKING?

The exact Option-A+B trigger (`reversal_detector.is_reversal_setup` with a structure-only tier)
was NEVER computed on the live path (cycle-gate => always False), so it cannot be replayed
verbatim. This tool replays the CLOSEST RECORDED PROXY for "entered at a spent counter-extreme":
band-location (bb_percent_b) + RSI 70/30 fade + OBV-against. That proxy IS the T6/T7
exhaustion family the adversarial flagged as FADED below the noise floor -- so this is the
honest first gate: if even the broad proxy fails to separate winners from losers, the narrower
structural veto will not save a no-edge book (ledger T8), and T16's fix is REFUTED-not-built.

PRE-REGISTERED KILL THRESHOLD (decided BEFORE seeing the numbers, per CLAUDE.md threshold
discipline). A trigger is REFUTED unless ALL THREE pass:
  (1) net_book_change > 0          -- removing the vetoed trades actually improves total PnL
  (2) over_veto_rate  < 0.40       -- fewer than 40% of skipped trades were winners
  (3) (keep_exp - veto_exp) 95% bootstrap CI does NOT span zero  -- separation beats noise
Only a trigger that clears all three earns a PROCEED-TO-PLAN on the real (structural) veto.

Usage:
    python -m backend.diagnostics.reversal_veto_counterfactual
    python -m backend.diagnostics.reversal_veto_counterfactual --since 2026-05-31
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
JOURNAL = REPO / "backend" / "cache" / "trade_journal.jsonl"
SESS_DIR = REPO / "logs" / "paper_trading"
CLAMP_DATE = "2026-05-31"  # reachability-clamp ship date = wide-stop-era confound boundary

# --- proxy knobs (documented; band/RSI extremes = "spent counter-extreme at entry") ---
BB_LOW, BB_HIGH = 0.20, 0.80      # short at/below lower band, long at/above upper band
RSI_LOW, RSI_HIGH = 30.0, 70.0    # project standing 70/30 fade thresholds (NOT arbitrary)
# --- pre-registered kill threshold ---
OVER_VETO_KILL = 0.40
BOOT_N = 4000
BOOT_SEED = 1_469_598_103         # fixed => deterministic, reproducible


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _dt(s):
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _boot_mean_diff_ci(keep, veto, n=BOOT_N, seed=BOOT_SEED):
    """Deterministic LCG bootstrap of (mean(keep) - mean(veto)); returns (lo, hi) 95% CI."""
    if len(keep) < 3 or len(veto) < 3:
        return None
    state = seed
    diffs = []
    lk, lv = len(keep), len(veto)
    for _ in range(n):
        sk = 0.0
        for _ in range(lk):
            state = (1103515245 * state + 12345) & 0x7FFFFFFF
            sk += keep[state % lk]
        sv = 0.0
        for _ in range(lv):
            state = (1103515245 * state + 12345) & 0x7FFFFFFF
            sv += veto[state % lv]
        diffs.append(sk / lk - sv / lv)
    diffs.sort()
    lo = diffs[int(0.025 * n)]
    hi = diffs[int(0.975 * n)]
    return lo, hi


def _load_trades(since):
    rows = []
    for line in JOURNAL.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            t = json.loads(line)
        except json.JSONDecodeError:
            continue
        et = t.get("entry_time", "") or ""
        if et < (since or CLAMP_DATE):
            continue
        if t.get("pnl") is None:
            continue
        rows.append(t)
    return rows


def _session_exec_index(sid):
    """symbol -> list of executed signal rows (with entry-time proxies) for a session."""
    p = SESS_DIR / f"session_{sid}" / "signals.jsonl"
    if not p.exists():
        return None
    idx = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            s = json.loads(line)
        except json.JSONDecodeError:
            continue
        if s.get("result") != "executed":
            continue
        idx.setdefault(s.get("symbol"), []).append(s)
    return idx


def _attach_entry_proxies(trades):
    """Join each trade to its session's executed signal nearest entry_time. Returns (matched, n_unmatched)."""
    by_sid = {}
    for t in trades:
        by_sid.setdefault(t["session_id"], []).append(t)
    matched, unmatched = [], 0
    for sid, ts in by_sid.items():
        idx = _session_exec_index(sid)
        for t in ts:
            cands = (idx or {}).get(t["symbol"], [])
            et = _dt(t.get("entry_time", ""))
            best = None
            if cands and et:
                best = min(
                    cands,
                    key=lambda s: abs(((_dt(s.get("timestamp", "")) or et) - et).total_seconds()),
                )
            if not best:
                unmatched += 1
                continue
            t["_bb"] = _f(best.get("bb_percent_b"))
            t["_rsi"] = _f(best.get("rsi"))
            t["_obv"] = best.get("obv_trend")
            matched.append(t)
    return matched, unmatched


# --- veto triggers: True == "entered at a counter-directional reversal cue -> brake it" ---
def trig_band(t):
    d, bb = t.get("direction"), t.get("_bb")
    if bb is None:
        return False
    return (d == "SHORT" and bb <= BB_LOW) or (d == "LONG" and bb >= BB_HIGH)


def trig_rsi(t):
    d, r = t.get("direction"), t.get("_rsi")
    if r is None:
        return False
    return (d == "SHORT" and r <= RSI_LOW) or (d == "LONG" and r >= RSI_HIGH)


def trig_obv(t):
    d, o = t.get("direction"), t.get("_obv")
    return (d == "SHORT" and o == "rising") or (d == "LONG" and o == "falling")


def trig_combined(t):
    return trig_band(t) or trig_rsi(t)


TRIGGERS = [
    ("band_extreme (bb<=.20 short / >=.80 long)", trig_band),
    ("rsi_fade (rsi<=30 short / >=70 long)", trig_rsi),
    ("obv_against (obv rising vs short / falling vs long)", trig_obv),
    ("combined (band OR rsi)", trig_combined),
]


def _stat(rows):
    n = len(rows)
    if not n:
        return {"n": 0, "win": 0.0, "exp": 0.0, "tot": 0.0}
    pnls = [_f(r.get("pnl")) or 0.0 for r in rows]
    w = sum(1 for p in pnls if p > 0)
    return {"n": n, "win": 100 * w / n, "exp": sum(pnls) / n, "tot": sum(pnls)}


def _evaluate(trades, name, fn, total_winners):
    veto = [t for t in trades if fn(t)]
    keep = [t for t in trades if not fn(t)]
    sv, sk = _stat(veto), _stat(keep)
    veto_pnls = [_f(t.get("pnl")) or 0.0 for t in veto]
    keep_pnls = [_f(t.get("pnl")) or 0.0 for t in keep]
    winners_skipped = sum(p for p in veto_pnls if p > 0)
    losers_skipped = sum(p for p in veto_pnls if p <= 0)
    net_book_change = -sv["tot"]                       # book PnL delta if vetoed trades removed
    vetoed_winners = sum(1 for p in veto_pnls if p > 0)
    over_veto = vetoed_winners / sv["n"] if sv["n"] else 0.0
    winner_kill = vetoed_winners / total_winners if total_winners else 0.0
    ci = _boot_mean_diff_ci(keep_pnls, veto_pnls)
    # pre-registered gate
    g1 = net_book_change > 0
    g2 = over_veto < OVER_VETO_KILL
    g3 = ci is not None and not (ci[0] <= 0 <= ci[1])
    verdict = "PROCEED-TO-PLAN" if (g1 and g2 and g3) else "REFUTED-as-scoped"
    return {
        "name": name, "veto": sv, "keep": sk,
        "winners_skipped": winners_skipped, "losers_skipped": losers_skipped,
        "net_book_change": net_book_change, "over_veto": over_veto,
        "winner_kill": winner_kill, "ci": ci,
        "g1": g1, "g2": g2, "g3": g3, "verdict": verdict,
    }


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    since = None
    if "--since" in sys.argv:
        since = sys.argv[sys.argv.index("--since") + 1]

    if not JOURNAL.exists():
        print("No trade_journal.jsonl.")
        return 1
    trades = _load_trades(since)
    matched, unmatched = _attach_entry_proxies(trades)
    total = _stat(matched)
    total_winners = sum(1 for t in matched if (_f(t.get("pnl")) or 0) > 0)

    print("=== T16 REVERSAL-VETO COUNTERFACTUAL (read-only, ship-nothing) ===")
    print(f"window: entry_time >= {since or CLAMP_DATE}  | matched {len(matched)} trades "
          f"({unmatched} unmatched, dropped)")
    print(f"baseline book: n={total['n']}  win={total['win']:.0f}%  "
          f"exp={total['exp']:+.2f}/tr  totalPnL={total['tot']:+.1f}")
    print(f"PROXY DISCLAIMER: triggers below are the T6/T7 exhaustion FAMILY (band/RSI/OBV at "
          f"entry), the closest RECORDED stand-in for the structural A+B veto -- NOT the exact "
          f"reversal_detector trigger (never computed live). If the broad proxy can't separate, "
          f"the narrow one won't either.")
    print(f"PRE-REGISTERED KILL: PROCEED only if (1) net_book_change>0 AND (2) over_veto<{OVER_VETO_KILL:.2f} "
          f"AND (3) (keep-veto) 95% CI excludes 0. Else REFUTED-as-scoped.\n")

    results = [_evaluate(matched, name, fn, total_winners) for name, fn in TRIGGERS]

    # --- SUMMARY (short, first) ---
    print(f"  {'trigger':46}{'veto_n':>7}{'veto_exp':>9}{'keep_exp':>9}{'book_chg':>9}"
          f"{'over_veto':>10}  verdict")
    for r in results:
        print(f"  {r['name']:46}{r['veto']['n']:>7}{r['veto']['exp']:>+9.2f}"
              f"{r['keep']['exp']:>+9.2f}{r['net_book_change']:>+9.1f}{r['over_veto']*100:>9.0f}%"
              f"  {r['verdict']}")

    # --- DETAIL ---
    print("\n--- DETAIL (per trigger) ---")
    for r in results:
        ci = r["ci"]
        ci_s = f"[{ci[0]:+.2f}, {ci[1]:+.2f}]" if ci else "n/a (group<3)"
        print(f"\n  {r['name']}")
        print(f"    VETO (would skip):  n={r['veto']['n']:3}  win={r['veto']['win']:3.0f}%  "
              f"exp={r['veto']['exp']:+.2f}  totalPnL={r['veto']['tot']:+.1f}")
        print(f"    KEEP (would trade): n={r['keep']['n']:3}  win={r['keep']['win']:3.0f}%  "
              f"exp={r['keep']['exp']:+.2f}  totalPnL={r['keep']['tot']:+.1f}")
        print(f"    winners_skipped=+{r['winners_skipped']:.1f}  losers_skipped={r['losers_skipped']:.1f}  "
              f"net_book_change={r['net_book_change']:+.1f}")
        print(f"    over_veto_rate={r['over_veto']*100:.0f}% (of skipped were winners)  "
              f"winner_kill={r['winner_kill']*100:.0f}% (of ALL winners skipped)")
        print(f"    (keep_exp - veto_exp) 95% CI = {ci_s}")
        print(f"    gates: net>0={r['g1']}  over_veto<{OVER_VETO_KILL}={r['g2']}  CI_excl_0={r['g3']}"
              f"  -> {r['verdict']}")

    any_proceed = any(r["verdict"] == "PROCEED-TO-PLAN" for r in results)
    print("\n=== READ ===")
    if any_proceed:
        names = [r["name"] for r in results if r["verdict"] == "PROCEED-TO-PLAN"]
        print(f"  At least one proxy CLEARS the pre-registered gate: {names}.")
        print("  -> The reversal-veto hypothesis survives the cheap proxy test. Next gate: compute the")
        print("     EXACT structural trigger (Option B) over these same entries and re-run; only then a §16 plan.")
    else:
        print("  NO proxy clears the gate. The broad exhaustion family (T6/T7) does not separate winners")
        print("  from losers post-clamp -- consistent with the ledger's 'faded below noise' record and the")
        print("  adversarial verdict. T16 fix (Option A+B veto) is REFUTED-as-scoped: braking entries at")
        print("  counter-extremes would not net-improve a no-edge book and risks skipping working continuations.")
        print("  Do NOT write scorer/smc code. Re-open only if a NON-exhaustion reversal signal is proposed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
