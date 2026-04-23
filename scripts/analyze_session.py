#!/usr/bin/env python3
"""
SniperSight Session Analyzer
─────────────────────────────
Reconstructs the full decision chain for every executed trade and produces
aggregate EV breakdowns by trade type, regime, conviction class, and exit reason.

Usage:
    python scripts/analyze_session.py                         # latest session
    python scripts/analyze_session.py <session_dir>           # specific session
    python scripts/analyze_session.py --all                   # all sessions combined
    python scripts/analyze_session.py --all --min-trades 5    # sessions with ≥5 trades
    python scripts/analyze_session.py --card SOL              # decision cards for SOL only
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
SESSIONS_DIR = REPO_ROOT / "logs" / "paper_trading"

# ── Colours (disabled on non-TTY) ─────────────────────────────────────────────
_USE_COLOUR = sys.stdout.isatty()

def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOUR else text

def green(t):  return _c(str(t), "32")
def red(t):    return _c(str(t), "31")
def yellow(t): return _c(str(t), "33")
def cyan(t):   return _c(str(t), "36")
def bold(t):   return _c(str(t), "1")
def dim(t):    return _c(str(t), "2")


# ── Loaders ───────────────────────────────────────────────────────────────────
def _load_jsonl(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _find_sessions(min_trades: int = 0) -> List[Path]:
    if not SESSIONS_DIR.exists():
        return []
    dirs = sorted(
        [d for d in SESSIONS_DIR.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
    )
    if min_trades > 0:
        dirs = [
            d for d in dirs
            if sum(1 for _ in (d / "trades.jsonl").open()) >= min_trades
            if (d / "trades.jsonl").exists()
        ]
    return dirs


# ── Signal ↔ Trade cross-reference ───────────────────────────────────────────
def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _link_signal_to_trade(signal: Dict, trades: List[Dict]) -> Optional[Dict]:
    """Match an executed signal to its completed trade by symbol + direction + nearest timestamp."""
    sym = signal.get("symbol")
    direction = signal.get("direction")
    sig_ts = _parse_dt(signal.get("timestamp"))
    if not sig_ts:
        return None

    candidates = [
        t for t in trades
        if t.get("symbol") == sym and t.get("direction") == direction
    ]
    if not candidates:
        return None

    # Pick the trade whose entry_time is closest to the signal timestamp (within 10 min)
    best = None
    best_delta = float("inf")
    for t in candidates:
        entry_ts = _parse_dt(t.get("entry_time"))
        if not entry_ts:
            continue
        delta = abs((entry_ts - sig_ts).total_seconds())
        if delta < best_delta and delta < 600:
            best_delta = delta
            best = t
    return best


# ── Factor bar renderer ───────────────────────────────────────────────────────
_BAR_WIDTH = 20

def _bar(score: float) -> str:
    filled = round(score / 100 * _BAR_WIDTH)
    bar = "█" * filled + "░" * (_BAR_WIDTH - filled)
    if score >= 70:
        return green(bar)
    if score >= 50:
        return yellow(bar)
    return red(bar)


def _score_colour(score: float) -> str:
    if score >= 70:
        return green(f"{score:.1f}")
    if score >= 50:
        return yellow(f"{score:.1f}")
    return red(f"{score:.1f}")


# ── Decision card ─────────────────────────────────────────────────────────────
def _print_decision_card(signal: Dict, trade: Optional[Dict], card_num: int):
    sym = signal.get("symbol", "?")
    direction = signal.get("direction", "?")
    conf = signal.get("confluence", 0)
    trade_type = signal.get("trade_type", "?")
    regime = signal.get("regime", "unknown")
    conviction = signal.get("conviction_class", "?")
    rr = signal.get("rr", 0)
    sig_ts = signal.get("timestamp", "")[:19].replace("T", " ")
    kill_zone = signal.get("kill_zone", "no_session")
    synergy = signal.get("synergy_bonus", 0)
    conflict = signal.get("conflict_penalty", 0)
    htf_aligned = signal.get("htf_aligned", 0)
    macro_score = signal.get("macro_score", 0)

    arrow = "▲" if direction == "LONG" else "▼"
    dir_colour = green if direction == "LONG" else red
    conf_str = _score_colour(conf)

    print()
    print(bold(f"╔══ TRADE #{card_num}  {sym} {dir_colour(arrow + ' ' + direction)}  {conf_str}% conf  [{trade_type.upper()} / {conviction}]"))
    print(f"║  {dim(sig_ts)}  regime={regime}  kill_zone={kill_zone}  rr={rr:.1f}R  htf_aligned={'✓' if htf_aligned else '✗'}")

    # ── Factor breakdown ──────────────────────────────────────────────────────
    factors = signal.get("factors", [])
    if factors:
        print(f"║")
        print(f"║  {bold('CONFLUENCE FACTORS')}")
        sorted_factors = sorted(factors, key=lambda f: f.get("weighted", 0), reverse=True)
        for f in sorted_factors:
            name = f.get("name", "?")[:28].ljust(28)
            score = f.get("score", 0)
            weighted = f.get("weighted", 0)
            rationale = f.get("rationale", "")[:60]
            print(f"║    {name}  {_bar(score)} {_score_colour(score):>5}  (w={weighted:.2f})  {dim(rationale)}")
        print(f"║  {'─'*72}")
        print(f"║    {'synergy bonus':28}  {green(f'+{synergy:.1f}') if synergy > 0 else dim('0')}   "
              f"{'conflict penalty':20}  {red(f'-{conflict:.1f}') if conflict > 0 else dim('0')}   "
              f"macro={macro_score:+.1f}")
    else:
        print(f"║  {dim('(factor detail not available — run a new session to capture per-factor scores)')}")

    # ── Indicators snapshot ───────────────────────────────────────────────────
    ind_keys = ["rsi", "adx", "bb_percent_b", "volume_ratio", "macd_histogram", "obv_trend"]
    ind_parts = [f"{k}={signal[k]:.2f}" for k in ind_keys if k in signal]
    if ind_parts:
        print(f"║  {dim('indicators: ' + '  '.join(ind_parts))}")

    # ── Entry plan ────────────────────────────────────────────────────────────
    entry_zone = signal.get("entry_zone", "?")
    stop_loss = signal.get("stop_loss", "?")
    print(f"║  entry={entry_zone}  stop={stop_loss}  R:R={rr:.1f}")

    # ── Outcome ───────────────────────────────────────────────────────────────
    print(f"║")
    if trade:
        pnl = trade.get("pnl", 0)
        pnl_pct = trade.get("pnl_pct", 0)
        exit_reason = trade.get("exit_reason", "?")
        targets_hit = trade.get("targets_hit", [])
        mfe = trade.get("max_favorable", 0)
        mae = trade.get("max_adverse", 0)
        exit_price = trade.get("exit_price", "?")
        entry_time = (trade.get("entry_time") or "")[:19].replace("T", " ")
        exit_time = (trade.get("exit_time") or "")[:19].replace("T", " ")

        # Duration
        et = _parse_dt(trade.get("entry_time"))
        xt = _parse_dt(trade.get("exit_time"))
        dur_str = ""
        if et and xt:
            dur = int((xt - et).total_seconds())
            h, m = divmod(dur // 60, 60)
            dur_str = f"{h}h{m:02d}m" if h else f"{m}m"

        pnl_colour = green if pnl >= 0 else red
        outcome_icon = "✅" if pnl >= 0 else "❌"

        print(f"║  {bold('OUTCOME')}  {outcome_icon}  {pnl_colour(f'${pnl:+.2f}')}  ({pnl_pct:+.2f}%)  exit={exit_reason.upper()}  duration={dur_str}")
        print(f"║    entry={entry_time}  exit={exit_time}  exit_price={exit_price}")
        print(f"║    targets_hit={targets_hit or 'none'}  MFE={mfe:+.2f}%  MAE={mae:.2f}%")

        # Assessment
        if exit_reason == "target" and pnl > 0:
            verdict = green("SYSTEM WORKING — target hit, profit taken")
        elif exit_reason == "stop_loss":
            verdict = red(f"STOP OUT — lost {abs(pnl):.2f}")
        elif exit_reason == "stagnation":
            verdict = yellow(f"STAGNATED — closed at {pnl:+.2f} (no progress)")
        elif exit_reason in ("direction_flip", "manual"):
            verdict = yellow(f"EARLY EXIT — {exit_reason}")
        else:
            verdict = dim(f"exit: {exit_reason}")
        print(f"║    {verdict}")
    else:
        print(f"║  {dim('(trade outcome not found — may still be open or session ended early)')}")

    print(bold("╚" + "═" * 78))


# ── Aggregate tables ──────────────────────────────────────────────────────────
def _ev(trades: List[Dict]) -> float:
    if not trades:
        return 0.0
    return sum(t.get("pnl", 0) for t in trades) / len(trades)


def _win_pct(trades: List[Dict]) -> float:
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t.get("pnl", 0) > 1.0)
    return wins / len(trades) * 100


def _scratch_pct(trades: List[Dict]) -> float:
    if not trades:
        return 0.0
    scratches = sum(1 for t in trades if abs(t.get("pnl", 0)) <= 1.0)
    return scratches / len(trades) * 100


def _avg_win(trades: List[Dict]) -> float:
    wins = [t.get("pnl", 0) for t in trades if t.get("pnl", 0) > 1.0]
    return sum(wins) / len(wins) if wins else 0.0


def _avg_loss(trades: List[Dict]) -> float:
    losses = [t.get("pnl", 0) for t in trades if t.get("pnl", 0) < -1.0]
    return sum(losses) / len(losses) if losses else 0.0


def _print_table(title: str, rows: List[Tuple], headers: List[str]):
    col_widths = [max(len(str(h)), max((len(str(r[i])) for r in rows), default=0)) for i, h in enumerate(headers)]
    sep = "  ".join("─" * w for w in col_widths)
    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)

    print()
    print(bold(title))
    print(fmt.format(*headers))
    print(sep)
    for row in rows:
        cells = []
        for i, v in enumerate(row):
            s = str(v)
            # Colour EV/PnL cells
            if headers[i] in ("EV/trade", "Avg Win", "Avg Loss", "Net P&L") and isinstance(v, str):
                if v.startswith("+") or (v.startswith("$") and not v.startswith("$-")):
                    s = green(s)
                elif "-" in v:
                    s = red(s)
            cells.append(s)
        print(fmt.format(*cells))


def _aggregate_report(all_trades: List[Dict], all_signals: List[Dict], session_label: str):
    print()
    print(bold("=" * 80))
    print(bold(f"  SNIPERSIGHT SESSION ANALYSIS  —  {session_label}"))
    print(bold("=" * 80))

    if not all_trades:
        print(red("  No completed trades found."))
        return

    total = len(all_trades)
    net_pnl = sum(t.get("pnl", 0) for t in all_trades)
    ev = net_pnl / total
    wins = sum(1 for t in all_trades if t.get("pnl", 0) > 1.0)
    scratches = sum(1 for t in all_trades if abs(t.get("pnl", 0)) <= 1.0)
    losses = total - wins - scratches
    win_rate = wins / total * 100

    ev_colour = green if ev >= 0 else red
    print(f"\n  Trades: {bold(total)}   Net P&L: {green(f'${net_pnl:+.2f}') if net_pnl >= 0 else red(f'${net_pnl:+.2f}')}"
          f"   EV/trade: {ev_colour(f'${ev:+.2f}')}")
    print(f"  Win/Scratch/Loss: {green(wins)}W / {yellow(scratches)}S / {red(losses)}L"
          f"  ({win_rate:.0f}% win rate)")

    # ── Exit reason breakdown ─────────────────────────────────────────────────
    by_exit: Dict[str, List[Dict]] = defaultdict(list)
    for t in all_trades:
        by_exit[t.get("exit_reason", "unknown")].append(t)

    exit_rows = []
    for reason, trades in sorted(by_exit.items(), key=lambda x: len(x[1]), reverse=True):
        ev_val = _ev(trades)
        exit_rows.append((
            reason,
            len(trades),
            f"{len(trades)/total*100:.0f}%",
            f"${ev_val:+.2f}",
            f"${sum(t['pnl'] for t in trades):+.2f}",
        ))
    _print_table(
        "EXIT REASON BREAKDOWN",
        exit_rows,
        ["Exit Reason", "Count", "% of Trades", "EV/trade", "Net P&L"],
    )

    # ── EV by trade type × regime ─────────────────────────────────────────────
    segments: Dict[str, List[Dict]] = defaultdict(list)
    for t in all_trades:
        regime_raw = t.get("regime", "unknown") or "unknown"
        # regime is stored as "trend_volatility" e.g. "up_compressed"
        parts = regime_raw.split("_")
        vol = parts[-1] if len(parts) >= 2 else regime_raw
        tt = t.get("trade_type", "?") or "?"
        key = f"{tt} / {vol}"
        segments[key].append(t)

    seg_rows = []
    for key, trades in sorted(segments.items(), key=lambda x: _ev(x[1])):
        ev_val = _ev(trades)
        seg_rows.append((
            key,
            len(trades),
            f"{_win_pct(trades):.0f}%",
            f"${_avg_win(trades):+.2f}",
            f"${_avg_loss(trades):+.2f}",
            f"${ev_val:+.2f}",
        ))
    _print_table(
        "EV BY TRADE TYPE × VOLATILITY REGIME",
        seg_rows,
        ["Segment", "Trades", "Win%", "Avg Win", "Avg Loss", "EV/trade"],
    )

    # ── Conviction class breakdown ────────────────────────────────────────────
    by_conviction: Dict[str, List[Dict]] = defaultdict(list)
    for t in all_trades:
        by_conviction[t.get("conviction_class", "?") or "?"].append(t)

    conv_rows = []
    for cls, trades in sorted(by_conviction.items()):
        ev_val = _ev(trades)
        conv_rows.append((cls, len(trades), f"{_win_pct(trades):.0f}%", f"${ev_val:+.2f}"))
    _print_table(
        "EV BY CONVICTION CLASS",
        conv_rows,
        ["Class", "Trades", "Win%", "EV/trade"],
    )

    # ── Confidence bucket analysis ────────────────────────────────────────────
    # Cross-reference with executed signals for confidence scores
    executed_sigs = {
        (s["symbol"], s["direction"]): s
        for s in all_signals
        if s.get("result") == "executed"
    }

    conf_buckets: Dict[str, List[Dict]] = defaultdict(list)
    for t in all_trades:
        sig = executed_sigs.get((t.get("symbol"), t.get("direction")))
        conf = sig.get("confluence", t.get("confidence_score", 0)) if sig else t.get("confidence_score", 0)
        if conf >= 85:
            bucket = "85-100 (APEX)"
        elif conf >= 75:
            bucket = "75-84 (A)"
        elif conf >= 65:
            bucket = "65-74 (B)"
        else:
            bucket = "<65 (C)"
        conf_buckets[bucket].append(t)

    if any(conf_buckets.values()):
        bucket_rows = []
        for bucket in ["85-100 (APEX)", "75-84 (A)", "65-74 (B)", "<65 (C)"]:
            trades = conf_buckets.get(bucket, [])
            if not trades:
                continue
            ev_val = _ev(trades)
            bucket_rows.append((bucket, len(trades), f"{_win_pct(trades):.0f}%", f"${ev_val:+.2f}"))
        _print_table(
            "EV BY CONFIDENCE BUCKET",
            bucket_rows,
            ["Confidence Band", "Trades", "Win%", "EV/trade"],
        )

    # ── Signal gate rejection breakdown ──────────────────────────────────────
    filtered_sigs = [s for s in all_signals if s.get("result") == "filtered"]
    if filtered_sigs:
        gate_counts: Dict[str, int] = defaultdict(int)
        for s in filtered_sigs:
            gate = s.get("reason_type") or "unknown"
            gate_counts[gate] += 1

        total_filtered = len(filtered_sigs)
        total_executed = len([s for s in all_signals if s.get("result") == "executed"])
        pass_rate = total_executed / (total_executed + total_filtered) * 100 if (total_executed + total_filtered) > 0 else 0

        print()
        print(bold("SIGNAL FILTER BREAKDOWN"))
        print(f"  Total signals: {total_executed + total_filtered}   Executed: {green(total_executed)}   Filtered: {red(total_filtered)}   Pass rate: {pass_rate:.1f}%")
        gate_rows = sorted(gate_counts.items(), key=lambda x: x[1], reverse=True)
        for gate, count in gate_rows:
            pct = count / total_filtered * 100
            print(f"    {gate:<30}  {count:>4}  ({pct:.0f}%)")

    # ── Worst trades (biggest losses) ────────────────────────────────────────
    worst = sorted(all_trades, key=lambda t: t.get("pnl", 0))[:5]
    if worst and worst[0].get("pnl", 0) < 0:
        print()
        print(bold("TOP 5 WORST TRADES"))
        for t in worst:
            sym = t.get("symbol", "?")
            direction = t.get("direction", "?")
            pnl = t.get("pnl", 0)
            exit_reason = t.get("exit_reason", "?")
            tt = t.get("trade_type", "?")
            regime = t.get("regime", "?")
            rr = t.get("risk_reward_ratio", 0)
            dur_str = ""
            et = _parse_dt(t.get("entry_time"))
            xt = _parse_dt(t.get("exit_time"))
            if et and xt:
                dur = int((xt - et).total_seconds())
                h, m = divmod(dur // 60, 60)
                dur_str = f"{h}h{m:02d}m" if h else f"{m}m"
            print(f"    {red(f'${pnl:+.2f}'):>12}  {sym:<6} {direction:<5} {tt:<9} {exit_reason:<14} {dur_str:<8} regime={regime} rr={rr:.1f}R")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="SniperSight session analyzer")
    parser.add_argument("session", nargs="?", help="Session directory path (default: latest)")
    parser.add_argument("--all", action="store_true", help="Aggregate all sessions")
    parser.add_argument("--min-trades", type=int, default=0, help="Min trades to include session")
    parser.add_argument("--cards", action="store_true", help="Print per-trade decision cards")
    parser.add_argument("--card", metavar="SYMBOL", help="Print decision cards for a specific symbol")
    parser.add_argument("--no-cards", action="store_true", help="Skip decision cards, show only aggregate")
    args = parser.parse_args()

    # ── Resolve session directories ───────────────────────────────────────────
    if args.all:
        session_dirs = _find_sessions(min_trades=args.min_trades)
        if not session_dirs:
            print(red(f"No sessions found in {SESSIONS_DIR}"))
            sys.exit(1)
        label = f"ALL SESSIONS ({len(session_dirs)} combined)"
    elif args.session:
        session_dirs = [Path(args.session)]
        label = Path(args.session).name
    else:
        all_dirs = _find_sessions()
        if not all_dirs:
            print(red(f"No sessions found in {SESSIONS_DIR}"))
            print(f"Expected location: {SESSIONS_DIR}")
            sys.exit(1)
        session_dirs = [all_dirs[-1]]
        label = all_dirs[-1].name

    # ── Load data ─────────────────────────────────────────────────────────────
    all_trades: List[Dict] = []
    all_signals: List[Dict] = []

    for sd in session_dirs:
        sd = Path(sd)
        all_trades.extend(_load_jsonl(sd / "trades.jsonl"))
        all_signals.extend(_load_jsonl(sd / "signals.jsonl"))

    # ── Decision cards ────────────────────────────────────────────────────────
    show_cards = args.cards or args.card or (not args.no_cards and len(all_trades) <= 30)

    if show_cards:
        executed_signals = [s for s in all_signals if s.get("result") == "executed"]
        if args.card:
            executed_signals = [s for s in executed_signals if s.get("symbol", "").upper() == args.card.upper()]

        if not executed_signals:
            if args.card:
                print(yellow(f"No executed signals found for {args.card}"))
        else:
            print()
            print(bold(f"═══ DECISION CARDS ({len(executed_signals)} trades) ═══"))
            for i, sig in enumerate(executed_signals, 1):
                trade = _link_signal_to_trade(sig, all_trades)
                _print_decision_card(sig, trade, i)

    # ── Aggregate report ──────────────────────────────────────────────────────
    _aggregate_report(all_trades, all_signals, label)

    print()


if __name__ == "__main__":
    main()
