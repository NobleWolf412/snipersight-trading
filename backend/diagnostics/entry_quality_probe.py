"""
Entry-quality probe (read-only PROTOTYPE). "Does any at-entry signal predict PnL?"

Motivated by the 2026-06-05 A/B (1000FLOKI loser vs APT winner): two indistinguishable
4h SHORT-swing setups (same regime, conviction A, ~81 score, similar/wider stop) had
opposite outcomes purely because of ENTRY LOCATION — one shorted into a 4.5% bounce, the
other into a 3% drop. The 26 confluence factors rated them identically. This probe asks the
empirical follow-up: among signals we can see AT ENTRY, does anything — especially an
entry-location feature the score doesn't use — actually correlate with realised PnL?

Method (same join + Pearson r_out as factor_contribution.py, no leakage):
  - take EXECUTED signals (signals.jsonl: rsi, bb_percent_b, htf_proximity_atr, rr, adx,
    atr_percent, volume_ratio, macro_score, synergy_bonus, conflict_penalty,
    pullback_probability — the at-entry context, semantics per ml/feature_extractor.py),
  - match each to its closed trade's PnL (trade_journal.jsonl),
  - correlate each candidate feature with PnL, plus DIRECTION-ADJUSTED engineered location
    features (loc_bb / loc_rsi / loc_macro: higher = entered at the favourable extreme for
    the trade's direction),
  - report r_out vs the n-based noise floor (±1.96/√n). A feature only matters if |r_out|
    clears the floor AND beats the current best confluence factor (VWAP ~+0.15).

NOTHING is wired into scoring here. This is a measurement to decide whether an entry-quality
input is worth building. Fees not modelled (gross PnL). Outcome fields (max_adverse/favorable)
are deliberately NOT used — they are post-entry leakage.

Usage:  python -m backend.diagnostics.entry_quality_probe
        python -m backend.diagnostics.entry_quality_probe --since 2026-05-31
"""
from __future__ import annotations

import math
import sys

from backend.diagnostics.factor_contribution import (
    _f, _pearson, _match_outcomes, load_corpus,
)

# at-entry raw context fields (semantics: ml/feature_extractor.py). "scored?" = is this
# value already an input the 26 confluence factors consume (loosely — for context only).
_RAW = [
    ("risk_reward_ratio", "rr",                  "no  (planned RR; high=far/unreachable TP)"),
    ("htf_proximity_atr", "htf_proximity_atr",   "part (HTF Composite uses it)"),
    ("bb_percent_b",      "bb_percent_b",        "no  (band position, raw)"),
    ("rsi",               "rsi",                 "part (Momentum/fade)"),
    ("adx",               "adx",                 "no  (trend strength)"),
    ("atr_percent",       "atr_percent",         "no  (volatility; regime input)"),
    ("volume_ratio",      "volume_ratio",        "part (Volume factor)"),
    ("macro_score",       "macro_score",         "part (BTC/macro)"),
    ("synergy_bonus",     "synergy_bonus",       "adj (score bonus)"),
    ("conflict_penalty",  "conflict_penalty",    "adj (score penalty)"),
    ("pullback_probability", "pullback_probability", "no  (pullback state)"),
]


def _engineered(sig):
    """Direction-adjusted ENTRY-LOCATION features (the hypothesis). Higher = entered at the
    extreme that favours the trade direction (short into a top / long into a bottom)."""
    is_short = sig.get("direction") == "SHORT"
    bb = _f(sig.get("bb_percent_b"))
    rsi = _f(sig.get("rsi"))
    macro = _f(sig.get("macro_score"))
    out = {}
    if bb is not None:
        out["loc_bb  (dir-adj band: short@top/long@bottom)"] = bb if is_short else (1.0 - bb)
    if rsi is not None:
        out["loc_rsi (dir-adj stretch into the move)"] = (rsi / 100.0) if is_short else (1.0 - rsi / 100.0)
    if macro is not None:
        out["loc_macro (dir-adj macro alignment)"] = (-macro) if is_short else macro
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    since = None
    if "--since" in sys.argv:
        since = sys.argv[sys.argv.index("--since") + 1]

    signals, files, trades = load_corpus(since)
    if not signals:
        print("No signals.jsonl with factors found.")
        return 1
    matched, attempted = _match_outcomes(signals, trades)
    if len(matched) < 10:
        print(f"Only {len(matched)} outcome-matched trades — too few to probe.")
        return 1
    pnl = [m[1] for m in matched]
    n = len(matched)
    noise = 1.96 / math.sqrt(n)
    VWAP_BEST = 0.15  # current best confluence factor, for comparison

    # build aligned vectors per candidate
    rows = []  # (label, scored_note, r_out, cov)
    def _series(getter):
        xs, ys = [], []
        for sig, p in matched:
            v = getter(sig)
            if v is not None:
                xs.append(v); ys.append(p)
        return xs, ys

    for label, key, note in _RAW:
        xs, ys = _series(lambda s, k=key: _f(s.get(k)))
        r, rn = _pearson(xs, ys)
        rows.append((label, note, r, rn, len(xs)))

    for label in ("loc_bb  (dir-adj band: short@top/long@bottom)",
                  "loc_rsi (dir-adj stretch into the move)",
                  "loc_macro (dir-adj macro alignment)"):
        xs, ys = _series(lambda s, L=label: _engineered(s).get(L))
        r, rn = _pearson(xs, ys)
        rows.append((label, "ENGINEERED (not scored)", r, rn, len(xs)))

    rated = [row for row in rows if row[2] is not None]
    rated.sort(key=lambda row: abs(row[2]), reverse=True)

    print("=== ENTRY-QUALITY PROBE (prototype, read-only) ===")
    win = sum(1 for p in pnl if p > 0)
    print(f"outcome-matched trades: {n} (win {100*win/n:.0f}%, gross) across {len(files)} sessions")
    print(f"noise floor for r_out: ±{noise:.2f}  |  must also beat best confluence factor (VWAP +{VWAP_BEST:.2f})")
    print(f"\n  {'feature':46}{'r_out':>7}{'n':>5}{'cov':>5}  signal? / currently scored?")
    for label, note, r, rn, cov in rated:
        flag = ""
        if abs(r) >= noise and abs(r) > VWAP_BEST:
            flag = "  <== beats noise AND best factor"
        elif abs(r) >= noise:
            flag = "  < above noise"
        print(f"  {label[:45]:46}{r:+7.2f}{rn:>5}{cov:>5}  {note}{flag}")

    winners = [row for row in rated if abs(row[2]) >= noise and abs(row[2]) > VWAP_BEST]
    print("\n=== READ ===")
    if winners:
        print(f"  {len(winners)} candidate(s) clear noise AND beat the best current factor:")
        for label, note, r, rn, cov in winners:
            direction = "higher→better" if r > 0 else "higher→WORSE"
            print(f"    - {label.strip()}  r_out={r:+.2f}  ({direction})  [{note.strip()}]")
        print("  -> worth a controlled add: wire ONE into the score behind a flag, re-baseline,")
        print("     symmetry-guard + §16, and re-measure r_out on the next N sessions before keeping.")
    else:
        print("  No at-entry feature (raw or engineered location) clears the noise floor AND beats")
        print("  the best existing factor. The entry-location hypothesis is NOT supported by this")
        print("  data: nothing visible at entry separates winners from losers better than noise.")
        print("  Implication: the edge gap is not a missing KNOWN feature — it needs a genuinely new")
        print("  signal (e.g. liquidity-sweep-before-entry, not currently logged) or a different")
        print("  premise. Do NOT add these to scoring.")
    print("\n(prototype — fees gross, r_out range-restricted to taken trades, n modest)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
