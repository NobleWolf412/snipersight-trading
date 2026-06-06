"""
Factor-contribution diagnostic (read-only). "Do I have too many confluence factors?"

Turns the question from opinion into evidence. For every confluence factor, across all
scored signals in logs/paper_trading/session_*/signals.jsonl, it measures:

  1. FIRE RATE     - how often the factor is even present (score > 0). A factor that is
                     absent 95% of the time carries almost no weight in practice.
  2. DISPERSION    - mean +/- std of its score WHEN present. Near-zero std = no
                     discriminating power (it says the same thing every time).
  3. CONTRIBUTION  - mean of its `weighted` value (score x renormalised weight) = how
                     much it actually moves the final confluence score on average.
  4. REDUNDANCY    - pairwise Pearson correlation of factor scores across signals.
                     Pairs with |r| >= REDUNDANT_R measure overlapping signal (e.g. the
                     HTF/regime/BTC cluster all read the same trend). Effective
                     independent factors << raw count.
  5. OUTCOME EDGE  - for signals that became trades (result=executed, matched to
                     trade_journal.jsonl by symbol+direction+nearest timestamp): Pearson
                     correlation between the factor's score and realised PnL. THE one
                     that matters - a factor whose score does not track whether you win
                     is decoration no matter how clever it sounds. NEGATIVE = the factor
                     scores HIGH on losers (actively misleading).

No factor is deleted here. The output is a ranked verdict per factor; cutting is a
separate, gated decision. Fees are not modelled (PnL is gross).

Usage (from repo root):
  python -m backend.diagnostics.factor_contribution
  python -m backend.diagnostics.factor_contribution --since 2026-05-31
  python -m backend.diagnostics.factor_contribution --session 334fd960

Output is paste-friendly (CLAUDE.md §12): SUMMARY first, per-factor TABLE second,
redundancy clusters + raw matched count last.
"""
from __future__ import annotations

import glob
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SIGNALS_GLOB = str(REPO / "logs" / "paper_trading" / "session_*" / "signals.jsonl")
JOURNAL = REPO / "backend" / "cache" / "trade_journal.jsonl"

REDUNDANT_R = 0.70          # |Pearson| at/above this = overlapping signal
DEAD_FIRE_RATE = 0.10       # fires in <10% of signals = rarely contributes
FLAT_STD = 8.0              # score std (when present) below this = low discrimination
MATCH_WINDOW_S = 3600       # signal must precede the fill by <= 1h to be its decision
CLAMP_DATE = "2026-05-31"   # reachability-clamp ship date = the wide-stop-era confound boundary
MIN_CLEAN_N = 30            # min post-clamp matched trades before a clean verdict is trusted
VETO_FACTORS = {"MACD Veto"}  # gate factors (mirror scorer.py VETO_FACTORS): among taken trades
#                              the score is range-restricted by the gate, so r_out is meaningless


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


def _pearson(xs, ys):
    """Pearson r over paired samples; None if undefined (n<3 or zero variance)."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 3:
        return None, n
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    sxx = sum((p[0] - mx) ** 2 for p in pairs)
    syy = sum((p[1] - my) ** 2 for p in pairs)
    if sxx <= 0 or syy <= 0:
        return None, n
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pairs)
    return sxy / math.sqrt(sxx * syy), n


def _load_signals(since, session):
    files = sorted(glob.glob(SIGNALS_GLOB), key=os.path.getmtime)
    if session:
        files = [f for f in files if session in f]
    rows = []
    for fp in files:
        for line in open(fp, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not r.get("factors"):
                continue
            if since and (r.get("timestamp", "") or "") < since:
                continue
            rows.append(r)
    return rows, files


def _load_journal(since):
    if not JOURNAL.exists():
        return []
    out = []
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
        out.append(r)
    return out


def _match_outcomes(signals, trades):
    """Attach realised PnL to each EXECUTED signal by symbol+direction+nearest-prior fill.
    Returns list of (signal_row, pnl). Surfaces match rate so drops are not silent."""
    by_sym = defaultdict(list)
    for t in trades:
        et = _dt(t.get("entry_time"))
        if et is not None:
            by_sym[t.get("symbol")].append((et, t.get("direction"), _f(t.get("pnl"))))
    for s in by_sym:
        by_sym[s].sort(key=lambda x: x[0])

    matched, attempted = [], 0
    for sig in signals:
        if sig.get("result") != "executed":
            continue
        attempted += 1
        sym, d, st = sig.get("symbol"), sig.get("direction"), _dt(sig.get("timestamp"))
        if st is None or sym not in by_sym:
            continue
        best = None
        for (et, td, pnl) in by_sym[sym]:
            if td != d or pnl is None:
                continue
            gap = (et - st).total_seconds()
            if 0 <= gap <= MATCH_WINDOW_S and (best is None or et < best[0]):
                best = (et, pnl)
        if best:
            matched.append((sig, best[1]))
    return matched, attempted


def _verdict(s, name, redundant):
    """Factor verdict. ANTI/KEEP are judged on the CLEAN (post-clamp) window to avoid
    wide-stop-era confounds; gate factors and confounds are labelled explicitly rather
    than mislabelled FLAT/ANTI."""
    # Gate/veto factors: among taken trades the score is range-restricted by the gate
    # (the veto already filtered the other side), so r_out carries no information.
    if name in VETO_FACTORS:
        return "GATE  (veto — r_out range-restricted, not interpretable)"

    r_full, r_clean, n_clean = s["r_out"], s.get("r_out_clean"), s.get("n_out_clean", 0)
    clean_ok = r_clean is not None and n_clean >= MIN_CLEAN_N
    clean_floor = (1.96 / math.sqrt(n_clean)) if n_clean else None

    # Confound: a full-history signal (|r|>=0.15) that vanishes on clean data — i.e. the
    # wide-stop-era artifact that fooled us 5x this session. Flag it, don't trust it.
    if (r_full is not None and abs(r_full) >= 0.15 and clean_ok
            and clean_floor is not None and abs(r_clean) < clean_floor):
        return "CONFOUND (full-history signal gone on clean data)"

    # Window-independent structural verdicts.
    if s["fire"] < DEAD_FIRE_RATE:
        return "RARE  (fires <10%)"
    if s["std"] < FLAT_STD and s["fire"] > 0.5:
        return "FLAT  (no discrimination)"
    if name in redundant:
        return "REDUNDANT (overlaps a stronger factor)"

    # ANTI/KEEP — judged on the clean window only, and only above its own noise floor.
    if clean_ok:
        if abs(r_clean) >= clean_floor and r_clean <= -0.15:
            return "ANTI  (scores high on LOSERS, clean data)"
        if abs(r_clean) >= clean_floor and r_clean >= 0.15:
            return "KEEP  (predicts winners, clean data)"
        return "weak / unproven"
    return "weak / unproven (insufficient clean data)"


def analyze(signals, trades):
    """Compute every per-factor metric + redundancy from signals + journal trades.
    Returns a result dict; pure computation, no I/O. Reused by main() and the
    session_debrief factor-edge block."""
    order = [f["name"] for f in max(signals, key=lambda r: len(r.get("factors", [])))["factors"]]

    scores = {name: [] for name in order}
    weighted = defaultdict(list)
    for sig in signals:
        present = {f["name"]: f for f in sig.get("factors", [])}
        for name in order:
            f = present.get(name)
            scores[name].append(_f(f["score"]) if f else 0.0)
            if f:
                weighted[name].append(_f(f.get("weighted")) or 0.0)

    matched, attempted = _match_outcomes(signals, trades)
    pnl_vec = [m[1] for m in matched]
    out_scores = {name: [] for name in order}
    for sig, _pnl in matched:
        present = {f["name"]: f for f in sig.get("factors", [])}
        for name in order:
            f = present.get(name)
            out_scores[name].append(_f(f["score"]) if f else 0.0)

    # Indices of matched trades in the CLEAN (post-clamp) window — by signal timestamp,
    # which is within MATCH_WINDOW_S of the fill. Used to de-confound ANTI/KEEP verdicts.
    clean_idx = [i for i, (sig, _p) in enumerate(matched)
                 if (sig.get("timestamp", "") or "") >= CLAMP_DATE]

    n = len(signals)
    stats = {}
    for name in order:
        present_vals = [v for v in scores[name] if v and v > 0]
        fire = len(present_vals) / n if n else 0.0
        mean_p = sum(present_vals) / len(present_vals) if present_vals else 0.0
        std_p = (math.sqrt(sum((v - mean_p) ** 2 for v in present_vals) / len(present_vals))
                 if present_vals else 0.0)
        contrib = sum(weighted[name]) / n if n else 0.0
        r_out, n_out = _pearson(out_scores[name], pnl_vec) if matched else (None, 0)
        r_clean, n_clean = (_pearson([out_scores[name][i] for i in clean_idx],
                                     [pnl_vec[i] for i in clean_idx]) if clean_idx else (None, 0))
        stats[name] = {"fire": fire, "mean": mean_p, "std": std_p,
                       "contrib": contrib, "r_out": r_out, "n_out": n_out,
                       "r_out_clean": r_clean, "n_out_clean": n_clean}

    pairs = []
    for i in range(len(order)):
        for j in range(i + 1, len(order)):
            a, b = order[i], order[j]
            r, _ = _pearson(scores[a], scores[b])
            if r is not None and abs(r) >= REDUNDANT_R:
                pairs.append((abs(r), r, a, b))
    pairs.sort(reverse=True)

    # in each correlated cluster the WEAKER outcome predictor is the redundant one
    redundant = set()
    for _ar, _r, a, b in pairs:
        ra = abs(stats[a]["r_out"]) if stats[a]["r_out"] is not None else -1
        rb = abs(stats[b]["r_out"]) if stats[b]["r_out"] is not None else -1
        redundant.add(b if ra >= rb else a)

    for name in order:
        stats[name]["verdict"] = _verdict(stats[name], name, redundant)

    return {"n": n, "order": order, "stats": stats, "redundant": redundant,
            "pairs": pairs, "matched": len(matched), "attempted": attempted,
            "pnl_vec": pnl_vec}


def load_corpus(since=None, session=None):
    """Load all factor-bearing signals + journal trades. Returns (signals, files, trades)."""
    signals, files = _load_signals(since, session)
    trades = _load_journal(since)
    return signals, files, trades


def compact_lines(result, files_n=0, top=3):
    """A few paste-friendly lines summarising factor edge — for embedding in
    session_debrief. Returns list[str]. Mirrors the standalone HEADLINE."""
    order, stats, redundant = result["order"], result["stats"], result["redundant"]
    matched, pnl_vec = result["matched"], result["pnl_vec"]
    dead = [nm for nm in order if stats[nm]["verdict"].startswith(("RARE", "FLAT"))]
    anti = [nm for nm in order if stats[nm]["verdict"].startswith("ANTI")]
    keep = [nm for nm in order if stats[nm]["verdict"].startswith("KEEP")]
    gate = [nm for nm in order if stats[nm]["verdict"].startswith("GATE")]
    confound = [nm for nm in order if stats[nm]["verdict"].startswith("CONFOUND")]
    win = sum(1 for p in pnl_vec if p > 0)
    n_clean = max((stats[nm].get("n_out_clean", 0) for nm in order), default=0)
    # best predictor on the CLEAN window, excluding uninterpretable gate factors
    rated = [nm for nm in order if stats[nm].get("r_out_clean") is not None and nm not in gate]
    best = max(rated, key=lambda nm: abs(stats[nm]["r_out_clean"]), default=None)
    noise = (1.96 / math.sqrt(n_clean)) if n_clean else None

    lines = [
        f"  corpus: {result['n']} signals / {files_n} sessions | {len(order)} factors | "
        f"matched {matched} ({n_clean} post-clamp, win {100*win/len(pnl_vec) if pnl_vec else 0:.0f}% gross)",
        f"  edge (clean): {len(keep)} KEEP | {len(anti)} ANTI | {len(dead)} dead | {len(gate)} gate | "
        f"{len(confound)} confound → effective ≈ {len(order)-len(redundant)-len(dead)}",
    ]
    if best is not None:
        b = stats[best]
        nf = f" (clean noise floor ±{noise:.2f})" if noise else ""
        lines.append(f"  best predictor (clean): {best} r={b['r_out_clean']:+.2f}{nf}")
    if anti:
        lines.append("  ANTI (clean data): "
                     + ", ".join(f"{nm} {stats[nm]['r_out_clean']:+.2f}" for nm in anti))
    if confound:
        lines.append("  confounds IGNORED (full-history artifacts, gone post-clamp): " + ", ".join(confound))
    return lines, {"dead": dead, "anti": anti, "keep": keep, "gate": gate,
                   "confound": confound, "best": best, "noise": noise}


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    since = session = None
    if "--since" in sys.argv:
        since = sys.argv[sys.argv.index("--since") + 1]
    if "--session" in sys.argv:
        session = sys.argv[sys.argv.index("--session") + 1]

    signals, files, trades = load_corpus(since, session)
    if not signals:
        print("No signals.jsonl rows with a factors array found.")
        return 1

    res = analyze(signals, trades)
    order, stats, redundant, pairs = res["order"], res["stats"], res["redundant"], res["pairs"]
    n, matched, attempted, pnl_vec = res["n"], res["matched"], res["attempted"], res["pnl_vec"]

    print("=== FACTOR CONTRIBUTION ===")
    win = sum(1 for p in pnl_vec if p > 0)
    print(f"signals analysed: {n} (across {len(files)} session files)  | factors: {len(order)}")
    print(f"outcome-matched (executed->journal): {matched}/{attempted} executed "
          f"({100*matched/attempted if attempted else 0:.0f}%)  | "
          f"win {100*win/len(pnl_vec) if pnl_vec else 0:.0f}%  | fees NOT modelled")
    if matched < 30:
        print(f"  ⚠ outcome edge is LOW-N ({matched} trades) — treat r_out as directional, not proof")
    elif matched:
        print(f"  (noise floor for r_out at n={matched}: ±{1.96/math.sqrt(matched):.2f} — "
              "|r| inside that is indistinguishable from random)")

    dead = [nm for nm in order if stats[nm]["verdict"].startswith(("RARE", "FLAT"))]
    anti = [nm for nm in order if stats[nm]["verdict"].startswith("ANTI")]
    gate = [nm for nm in order if stats[nm]["verdict"].startswith("GATE")]
    confound = [nm for nm in order if stats[nm]["verdict"].startswith("CONFOUND")]
    n_clean = max((stats[nm].get("n_out_clean", 0) for nm in order), default=0)
    print(f"\nHEADLINE: {len(order)} factors | {len(redundant)} redundant | {len(dead)} dead(rare/flat) "
          f"| {len(anti)} ANTI(clean) | {len(gate)} gate | {len(confound)} confound(full-history artifact)")
    print(f"  → effective independent factors ≈ {len(order) - len(redundant) - len(dead)}")
    print(f"  ANTI/KEEP judged on the CLEAN post-clamp window (since {CLAMP_DATE}, n={n_clean}); "
          f"full-history r shown for reference only.")

    print("\n--- per factor (sorted by |clean outcome edge|) ---")
    print(f"  {'factor':24}{'fire%':>6}{'score(±std)':>13}{'r_full':>8}{'r_clean':>9}{'nC':>4}  verdict")
    def _ck(nm):
        rc = stats[nm].get("r_out_clean")
        return abs(rc) if rc is not None else 0.0
    for name in sorted(order, key=_ck, reverse=True):
        s = stats[name]
        rf = f"{s['r_out']:+.2f}" if s["r_out"] is not None else "  -"
        rc = f"{s['r_out_clean']:+.2f}" if s.get("r_out_clean") is not None else "  -"
        print(f"  {name[:23]:24}{100*s['fire']:5.0f}%{s['mean']:6.0f}±{s['std']:<5.0f}"
              f"{rf:>8}{rc:>9}{s.get('n_out_clean', 0):>4}  {s['verdict']}")

    print(f"\n--- redundancy clusters (|Pearson| >= {REDUNDANT_R}) ---")
    if not pairs:
        print("  none above threshold")
    for _ar, r, a, b in pairs[:20]:
        print(f"  r={r:+.2f}  {a}  <->  {b}")

    print("\n=== READ ===")
    print("  KEEP/ANTI = clean-window score tracks winners/losers above its noise floor.")
    print("  GATE = veto factor, r_out range-restricted (not interpretable — do NOT remove on r alone).")
    print("  CONFOUND = looked like a signal on all data but vanishes post-clamp (wide-stop artifact).")
    print("  RARE/FLAT/REDUNDANT = trim candidates (hygiene). Confirm on more clean trades before cutting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
