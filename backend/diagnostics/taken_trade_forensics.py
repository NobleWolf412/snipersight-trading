"""
Taken-Trade Forensics — where is the PnL leak?
================================================
The conflict_density forensics (commit 44994d8) scrutinized 2,200+ BLOCKED
signals to ask whether the gate was over-tight. The bigger PnL question
was never asked: of the trades the bot DID FIRE, which combinations of
entry-context features systematically lost money?

Method:
  1. Read all closed trades from backend/cache/trade_journal.jsonl
  2. Partition by entry-context features:
     - Universal (all trades): direction, trade_type, exit_reason,
       conviction_class, regime, kill_zone, confidence buckets
     - Tier 2 only (post-2026-05-24 sessions): htf_aligned_at_entry,
       setup_qualifier, macro_state_at_entry, btc_velocity × direction,
       alt_velocity × direction
  3. Compute per-partition: count, wins, win_rate, total_pnl, avg_pnl_pct
  4. Rank features by win-rate delta (best bucket vs worst bucket) to
     surface the dominant signal feature
  5. Surface biggest winner / biggest loser / highest-confidence loser

Calibrated as the diagnostic that should have existed from day one. Per
the adversarial-review (2026-05-26 task a62c1e9): "the missing PnL lives
in the trades that fired and lost, not the ones that were blocked."

Sample-size caveat: at N=67 trades total (17 with Tier 2 fields), this
is exploratory. Any single-bucket finding with n<5 is noise. Partitions
with n>=8 and >20pt win-rate delta are worth investigating.

Per CLAUDE.md §11 (silent-bug surfacing — taken trades that LOSE
systematically are themselves a silent bug class), §12 (paste-friendly),
§15 (this script PRODUCES baseline data, doesn't tune anything).

Usage:
    python -X utf8 -m backend.diagnostics.taken_trade_forensics
    python -X utf8 -m backend.diagnostics.taken_trade_forensics --session 561744bc
    python -X utf8 -m backend.diagnostics.taken_trade_forensics --tier2-only

Output: paste-friendly. Summary → feature breakdowns → cross-tabs →
ranked signals → top 5 winners + 5 losers + 5 highest-conf losers.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import mean, median, stdev
from typing import Callable, Dict, List, Optional, Tuple


TIER2_FIELDS = (
    "htf_aligned_at_entry",
    "setup_qualifier",
    "btc_velocity_1h_at_entry",
    "alt_velocity_1h_at_entry",
    "macro_state_at_entry",
    "regime_trend_at_entry",
)


@dataclass
class Stats:
    count: int
    wins: int
    losses: int
    scratch: int
    win_rate: float          # wins / (wins + losses); ignores scratch
    total_pnl: float
    avg_pnl: float
    avg_pnl_pct: float
    total_pnl_pct: float

    @classmethod
    def from_trades(cls, trades: List[Dict]) -> "Stats":
        if not trades:
            return cls(0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0)
        wins = sum(1 for t in trades if (t.get("pnl") or 0) > 0)
        losses = sum(1 for t in trades if (t.get("pnl") or 0) < 0)
        scratch = len(trades) - wins - losses
        decisive = wins + losses
        win_rate = (wins / decisive) if decisive else 0.0
        total_pnl = sum((t.get("pnl") or 0) for t in trades)
        avg_pnl = total_pnl / len(trades)
        pnl_pcts = [(t.get("pnl_pct") or 0) for t in trades]
        return cls(
            count=len(trades),
            wins=wins, losses=losses, scratch=scratch,
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_pnl=avg_pnl,
            avg_pnl_pct=mean(pnl_pcts),
            total_pnl_pct=sum(pnl_pcts),
        )


def _load_trades(session: Optional[str], tier2_only: bool) -> List[Dict]:
    rows = []
    try:
        for line in open("backend/cache/trade_journal.jsonl", encoding="utf-8"):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except FileNotFoundError:
        print("ERROR: backend/cache/trade_journal.jsonl not found", file=sys.stderr)
        return []

    if session:
        rows = [r for r in rows if r.get("session_id") == session]

    if tier2_only:
        rows = [r for r in rows if r.get("htf_aligned_at_entry") is not None]

    return rows


def _bucket_by(trades: List[Dict], key_fn: Callable[[Dict], object]) -> Dict[object, Stats]:
    """Return {bucket_label → Stats(...)}."""
    buckets: Dict[object, List[Dict]] = defaultdict(list)
    for t in trades:
        try:
            buckets[key_fn(t)].append(t)
        except Exception:
            buckets["<error>"].append(t)
    return {k: Stats.from_trades(v) for k, v in buckets.items()}


def _format_bucket_row(label: str, st: Stats, indent: str = "    ") -> str:
    return (
        f"{indent}{str(label):20s}"
        f"n={st.count:>3d}  "
        f"w={st.wins:>2d}/l={st.losses:>2d}/s={st.scratch:>2d}  "
        f"wr={100*st.win_rate:>5.1f}%  "
        f"pnl=${st.total_pnl:>+8.2f}  "
        f"avg=${st.avg_pnl:>+6.2f}  "
        f"avg_pct={st.avg_pnl_pct:>+6.3f}%"
    )


def _print_feature_breakdown(
    title: str,
    trades: List[Dict],
    key_fn: Callable[[Dict], object],
    sort_by: str = "count",
) -> Dict[object, Stats]:
    print(f"\n  {title}")
    print(f"  {'─' * 78}")
    buckets = _bucket_by(trades, key_fn)
    if not buckets:
        print(f"    (no data)")
        return buckets

    items = list(buckets.items())
    if sort_by == "count":
        items.sort(key=lambda kv: -kv[1].count)
    elif sort_by == "win_rate":
        items.sort(key=lambda kv: -kv[1].win_rate)
    elif sort_by == "pnl":
        items.sort(key=lambda kv: -kv[1].total_pnl)

    for label, st in items:
        print(_format_bucket_row(label, st))
    return buckets


def _confidence_bucket(t: Dict) -> str:
    c = t.get("confidence_score")
    if c is None:
        return "—"
    if c < 65:   return "<65"
    if c < 70:   return "65-70"
    if c < 75:   return "70-75"
    if c < 80:   return "75-80"
    if c < 85:   return "80-85"
    return "85+"


def _macro_alignment(t: Dict) -> str:
    """sign(btc_velocity_1h) × direction → aligned / counter / neutral."""
    vel = t.get("btc_velocity_1h_at_entry")
    dir_ = (t.get("direction") or "").upper()
    if vel is None or dir_ not in ("LONG", "SHORT"):
        return "—"
    if abs(vel) < 0.05:
        return "neutral_btc"  # < 0.05% velocity = sideways
    btc_up = vel > 0
    if (btc_up and dir_ == "LONG") or (not btc_up and dir_ == "SHORT"):
        return "aligned"
    return "counter"


def _alt_alignment(t: Dict) -> str:
    vel = t.get("alt_velocity_1h_at_entry")
    dir_ = (t.get("direction") or "").upper()
    if vel is None or dir_ not in ("LONG", "SHORT"):
        return "—"
    if abs(vel) < 0.05:
        return "neutral_alt"
    alt_up = vel > 0
    if (alt_up and dir_ == "LONG") or (not alt_up and dir_ == "SHORT"):
        return "aligned"
    return "counter"


def _signal_rank(features: List[Tuple[str, Dict[object, Stats]]]) -> List[Tuple[str, float, str, str]]:
    """For each feature, compute win-rate delta between best and worst bucket
    (only buckets with n>=3 count). Returns list of
    (feature_name, delta_pct, best_label, worst_label) sorted by delta desc."""
    ranked = []
    for name, buckets in features:
        eligible = [(k, st) for k, st in buckets.items() if st.count >= 3 and (st.wins + st.losses) > 0]
        if len(eligible) < 2:
            continue
        eligible.sort(key=lambda kv: kv[1].win_rate)
        worst_k, worst_st = eligible[0]
        best_k, best_st = eligible[-1]
        delta = (best_st.win_rate - worst_st.win_rate) * 100
        ranked.append((name, delta, str(best_k), str(worst_k)))
    ranked.sort(key=lambda x: -x[1])
    return ranked


def _surprising_trades(trades: List[Dict]) -> None:
    """Top winners + top losers + high-confidence losers."""
    sorted_by_pnl = sorted(trades, key=lambda t: (t.get("pnl") or 0))
    top_losers = sorted_by_pnl[:5]
    top_winners = sorted_by_pnl[-5:][::-1]
    high_conf_losers = sorted(
        [t for t in trades if (t.get("pnl") or 0) < 0 and (t.get("confidence_score") or 0) >= 70],
        key=lambda t: -(t.get("confidence_score") or 0),
    )[:5]

    def _fmt(t: Dict) -> str:
        return (
            f"    {t.get('symbol','?'):14s} {t.get('direction','?'):5s} "
            f"{t.get('trade_type','?'):8s} "
            f"pnl=${(t.get('pnl') or 0):>+7.2f} "
            f"({(t.get('pnl_pct') or 0):>+6.2f}%) "
            f"conf={(t.get('confidence_score') or 0):5.1f} "
            f"htf_aligned={t.get('htf_aligned_at_entry')} "
            f"exit={t.get('exit_reason','?')} "
            f"qualifier={t.get('setup_qualifier','—')}"
        )

    print("\n  Top 5 winners:")
    for t in top_winners: print(_fmt(t))
    print("\n  Top 5 losers:")
    for t in top_losers: print(_fmt(t))
    print("\n  Top 5 high-confidence losers (conf>=70, pnl<0):")
    for t in high_conf_losers: print(_fmt(t))


def main(argv: List[str]) -> int:
    session: Optional[str] = None
    tier2_only = False
    for arg in argv[1:]:
        if arg == "--tier2-only":
            tier2_only = True
        elif arg.startswith("--session"):
            session = arg.split("=", 1)[1] if "=" in arg else None
        elif arg == "--session" and len(argv) > argv.index(arg) + 1:
            session = argv[argv.index(arg) + 1]

    trades = _load_trades(session, tier2_only)
    if not trades:
        print("No trades found matching filter.")
        return 1

    tier2_trades = [t for t in trades if t.get("htf_aligned_at_entry") is not None]
    overall = Stats.from_trades(trades)
    t2_overall = Stats.from_trades(tier2_trades)

    print("=" * 80)
    print("  TAKEN-TRADE FORENSICS")
    print("=" * 80)
    print(f"  Source        : backend/cache/trade_journal.jsonl")
    print(f"  Filters       : session={session or 'ALL'} tier2_only={tier2_only}")
    print(f"  Total trades  : {len(trades)}")
    print(f"  Tier 2 trades : {len(tier2_trades)} (have htf_aligned/macro fields)")
    sessions = sorted(set(t.get("session_id") for t in trades))
    print(f"  Sessions      : {len(sessions)} ({', '.join(sessions[:8])}{'…' if len(sessions) > 8 else ''})")
    print()

    print("  Overall PnL (all trades):")
    print(f"    wins={overall.wins} losses={overall.losses} scratch={overall.scratch}")
    print(f"    win_rate={100*overall.win_rate:.1f}%  total_pnl=${overall.total_pnl:+.2f}  "
          f"avg_pnl=${overall.avg_pnl:+.2f}  total_pnl_pct={overall.total_pnl_pct:+.2f}%")

    if tier2_trades:
        print("\n  Overall PnL (Tier 2 trades only):")
        print(f"    wins={t2_overall.wins} losses={t2_overall.losses} scratch={t2_overall.scratch}")
        print(f"    win_rate={100*t2_overall.win_rate:.1f}%  total_pnl=${t2_overall.total_pnl:+.2f}  "
              f"avg_pnl=${t2_overall.avg_pnl:+.2f}")

    print("\n  " + "═" * 78)
    print("  UNIVERSAL FEATURES (all trades)")
    print("  " + "═" * 78)

    universal_features = []
    universal_features.append(("direction", _print_feature_breakdown(
        "Direction", trades, lambda t: t.get("direction") or "—"
    )))
    universal_features.append(("trade_type", _print_feature_breakdown(
        "Trade type", trades, lambda t: t.get("trade_type") or "—"
    )))
    universal_features.append(("exit_reason", _print_feature_breakdown(
        "Exit reason", trades, lambda t: t.get("exit_reason") or "—"
    )))
    universal_features.append(("conviction_class", _print_feature_breakdown(
        "Conviction class", trades, lambda t: t.get("conviction_class") or "—"
    )))
    universal_features.append(("regime", _print_feature_breakdown(
        "Regime", trades, lambda t: t.get("regime") or "—"
    )))
    universal_features.append(("kill_zone", _print_feature_breakdown(
        "Kill zone", trades, lambda t: t.get("kill_zone") or "—"
    )))
    universal_features.append(("confidence_bucket", _print_feature_breakdown(
        "Confidence bucket", trades, _confidence_bucket
    )))

    # ── Tier 2 ──────────────────────────────────────────────────────
    tier2_features = []
    if tier2_trades:
        print("\n  " + "═" * 78)
        print(f"  TIER 2 FEATURES (only {len(tier2_trades)} trades have these — small-n caveat)")
        print("  " + "═" * 78)

        tier2_features.append(("htf_aligned_at_entry", _print_feature_breakdown(
            "HTF aligned at entry  ← primary hypothesis (adversarial review 2026-05-26)",
            tier2_trades,
            lambda t: t.get("htf_aligned_at_entry"),
        )))
        tier2_features.append(("setup_qualifier", _print_feature_breakdown(
            "Setup qualifier", tier2_trades,
            lambda t: t.get("setup_qualifier") or "—",
        )))
        tier2_features.append(("macro_state_at_entry", _print_feature_breakdown(
            "Macro state at entry", tier2_trades,
            lambda t: t.get("macro_state_at_entry") or "—",
        )))
        tier2_features.append(("macro_alignment (BTC velocity × dir)", _print_feature_breakdown(
            "Macro alignment (sign(BTC velocity) × direction)", tier2_trades,
            _macro_alignment,
        )))
        tier2_features.append(("alt_alignment (alt velocity × dir)", _print_feature_breakdown(
            "Alt-cohort alignment (sign(alt velocity) × direction)", tier2_trades,
            _alt_alignment,
        )))
        tier2_features.append(("regime_trend_at_entry", _print_feature_breakdown(
            "Regime trend at entry", tier2_trades,
            lambda t: t.get("regime_trend_at_entry") or "—",
        )))

        # Cross-tab: htf_aligned × setup_qualifier
        print("\n  Cross-tab: HTF aligned × Setup qualifier")
        print("  " + "─" * 78)
        xtab = defaultdict(list)
        for t in tier2_trades:
            xtab[(t.get("htf_aligned_at_entry"), t.get("setup_qualifier") or "—")].append(t)
        for key in sorted(xtab.keys(), key=lambda k: (str(k[0]), str(k[1]))):
            st = Stats.from_trades(xtab[key])
            label = f"htf={key[0]}, qual={key[1]}"
            print(_format_bucket_row(label, st))

    # ── Signal ranking ─────────────────────────────────────────────
    print("\n  " + "═" * 78)
    print("  TOP SIGNAL FEATURES (ranked by win-rate Δ best-vs-worst bucket)")
    print("  Buckets with n<3 excluded. Δ >= 20pt with n>=5 in each bucket = worth investigating.")
    print("  " + "═" * 78)
    all_features = universal_features + tier2_features
    ranked = _signal_rank(all_features)
    if ranked:
        print(f"  {'feature':40s} {'Δ wr':>8s}  best → worst")
        for name, delta, best, worst in ranked[:12]:
            print(f"  {name:40s} {delta:>+6.1f}pt  {best} → {worst}")
    else:
        print("  (no features had ≥2 eligible buckets)")

    # ── Surprising trades ───────────────────────────────────────────
    print("\n  " + "═" * 78)
    print("  SURPRISING TRADES")
    print("  " + "═" * 78)
    _surprising_trades(trades)

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
