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


# ── Price formatting (scale decimals by magnitude) ───────────────────────────
def _fmt_price(p) -> str:
    try:
        v = float(p)
    except (TypeError, ValueError):
        return str(p)
    if v == 0:
        return "0"
    if v >= 1000:
        return f"{v:.2f}"
    if v >= 10:
        return f"{v:.3f}"
    if v >= 1:
        return f"{v:.4f}"
    if v >= 0.01:
        return f"{v:.5f}"
    return f"{v:.8f}"


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

    # Counter-trend flag
    regime_trend = regime.split("_")[0] if "_" in regime else regime
    is_counter_trend = (
        (regime_trend in ("up", "strong") and direction == "SHORT") or
        (regime_trend in ("down",) and direction == "LONG")
    )
    ct_tag = f"  {yellow('⚠ COUNTER-TREND')}" if is_counter_trend else ""

    print()
    print(bold(f"╔══ TRADE #{card_num}  {sym} {dir_colour(arrow + ' ' + direction)}  {conf_str}% conf  [{trade_type.upper()} / {conviction}]{ct_tag}"))
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
    ind_parts = []
    for k in ind_keys:
        if k in signal:
            try:
                ind_parts.append(f"{k}={float(signal[k]):.4f}")
            except (TypeError, ValueError):
                ind_parts.append(f"{k}={signal[k]}")
    if ind_parts:
        print(f"║  {dim('indicators: ' + '  '.join(ind_parts))}")

    # ── Entry plan ────────────────────────────────────────────────────────────
    entry_zone = signal.get("entry_zone", "?")
    stop_loss = signal.get("stop_loss", "?")
    # Stop distance as % of entry — catches micro-stops that sit inside spread noise
    try:
        _e, _s = float(entry_zone), float(stop_loss)
        stop_pct = abs(_e - _s) / _e * 100 if _e > 0 else 0
        stop_pct_str = f"  stop_dist={stop_pct:.3f}%"
        stop_pct_str = f"  {red(stop_pct_str.strip())}" if stop_pct < 0.15 else f"  {dim(stop_pct_str.strip())}"
    except (TypeError, ValueError):
        stop_pct_str = ""
    print(f"║  entry={_fmt_price(entry_zone)}  stop={_fmt_price(stop_loss)}  R:R={rr:.1f}{stop_pct_str}")

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
        print(f"║    entry={entry_time}  exit={exit_time}  exit_price={_fmt_price(exit_price)}")
        # MFE:MAE ratio — if MFE > 0.4% on a loser, the trade was right, management failed
        mfe_mae_note = ""
        if mfe > 0 and mae > 0:
            ratio = mfe / mae
            if pnl < 0 and mfe >= 0.4:
                mfe_mae_note = f"  {yellow('← trade was right, management failed')}"
            elif pnl < 0 and mfe < 0.15:
                mfe_mae_note = f"  {red('← entry was wrong from the start')}"
        realized_rr_note = ""
        if trade and pnl != 0:
            try:
                _ep = float(trade.get("entry_price", 0) or 0)
                _xp = float(trade.get("exit_price", 0) or 0)
                _sl = float(signal.get("stop_loss", 0) or 0)
                if _ep > 0 and _xp > 0 and _sl > 0:
                    _risk = abs(_ep - _sl)
                    _move = (_xp - _ep) if direction == "LONG" else (_ep - _xp)
                    _realized = _move / _risk if _risk > 0 else 0
                    realized_rr_note = f"  realized={_realized:+.2f}R"
            except (TypeError, ValueError):
                pass
        print(f"║    targets_hit={targets_hit or 'none'}  MFE={mfe:+.2f}%  MAE={mae:.2f}%{realized_rr_note}{mfe_mae_note}")

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


# ── Stop geometry helpers ─────────────────────────────────────────────────────
_STOP_PCT_CAPS = {"scalp": 0.03, "intraday": 0.05, "swing": 0.10}


def _stop_pct_for_signal(sig: Dict) -> Optional[float]:
    try:
        entry = float(sig.get("entry_zone") or 0)
        stop = float(sig.get("stop_loss") or 0)
        if entry > 0 and stop > 0:
            return abs(entry - stop) / entry
    except (TypeError, ValueError):
        pass
    return None


# ── New section renderers ─────────────────────────────────────────────────────

def _print_config_block(config: Dict):
    if not config:
        return
    mode = config.get("mode") or config.get("scanner_mode") or "?"
    score = config.get("min_confluence_score") or config.get("confluence_soft_floor") or "mode default"
    risk = config.get("risk_per_trade_pct") or config.get("risk_percent") or "?"
    lev = config.get("leverage") or 1
    fee = config.get("fee_rate") or "?"
    balance = config.get("initial_balance") or config.get("balance") or "?"
    trailing = config.get("trailing_stop_enabled") or config.get("trailing_stop") or False
    trail_act = config.get("trailing_stop_activation_pct") or "?"
    print()
    print(bold("SESSION CONFIG"))
    print(f"  Mode: {cyan(mode)}  |  Min score: {score}  |  Risk: {risk}%  |  "
          f"Leverage: {lev}x  |  Fee: {fee}  |  Balance: ${balance}")
    if trailing:
        print(f"  Trailing stop: enabled (activation {trail_act}%)")


def _print_equity_curve(all_trades: List[Dict]):
    sorted_trades = sorted(
        [t for t in all_trades if t.get("entry_time")],
        key=lambda t: t.get("entry_time", ""),
    )
    if not sorted_trades:
        return
    print()
    print(bold("EQUITY CURVE  (cumulative P&L per trade)"))
    cumulative = 0.0
    bar_scale = 2.0  # $ per char
    for i, t in enumerate(sorted_trades, 1):
        pnl = t.get("pnl", 0)
        cumulative += pnl
        sym = t.get("symbol", "?")[:8]
        pnl_colour = green if pnl >= 0 else red
        cum_colour = green if cumulative >= 0 else red
        bar_len = max(1, round(abs(pnl) / bar_scale))
        bar = ("+" if pnl >= 0 else "-") * bar_len
        bar_str = green(bar) if pnl >= 0 else red(bar)
        print(f"  #{i:>2}  {sym:<10}  {pnl_colour(f'{pnl:+6.2f}'):>10}  "
              f"cum={cum_colour(f'${cumulative:+7.2f}')}  {bar_str}")


def _print_stop_geometry(all_signals: List[Dict], all_trades: List[Dict]):
    executed = [s for s in all_signals if s.get("result") == "executed"]
    if not executed:
        return

    sig_map: Dict[Tuple, Dict] = {}
    for s in executed:
        sig_map[(s.get("symbol"), s.get("direction"))] = s

    by_sym: Dict[str, List[float]] = defaultdict(list)
    for s in executed:
        pct = _stop_pct_for_signal(s)
        if pct is not None:
            by_sym[s.get("symbol", "?")].append(pct)

    if not by_sym:
        return

    print()
    print(bold("STOP GEOMETRY BY SYMBOL  (stop distance as % of entry)"))
    headers = ["Symbol", "Trades", "Avg Stop%", "Max Stop%", "Cap Breaches"]
    rows = []
    any_breach = False
    for sym, pcts in sorted(by_sym.items()):
        trades_for_sym = [t for t in all_trades if t.get("symbol") == sym]
        tt = (trades_for_sym[0].get("trade_type") or "scalp").lower() if trades_for_sym else "scalp"
        cap = _STOP_PCT_CAPS.get(tt, 0.05)
        breaches = sum(1 for p in pcts if p > cap)
        avg_pct = sum(pcts) / len(pcts) * 100
        max_pct = max(pcts) * 100
        breach_str = red(f"{breaches}  ← geometry issue") if breaches > 0 else green("0")
        if breaches:
            any_breach = True
        rows.append((sym, len(pcts), f"{avg_pct:.2f}%", f"{max_pct:.2f}%", breach_str))

    rows.sort(key=lambda r: float(r[3].rstrip("%")), reverse=True)
    col_widths = [max(len(str(h)), max(len(str(r[i])) for r in rows)) for i, h in enumerate(headers)]
    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
    print(fmt.format(*headers))
    print("  ".join("─" * w for w in col_widths))
    for row in rows:
        print(fmt.format(*row))
    if any_breach:
        print(f"  {yellow('Cap thresholds: scalp 3%, intraday 5%, swing 10%')}")


def _print_score_histogram(all_signals: List[Dict]):
    executed = [s for s in all_signals if s.get("result") == "executed"]
    if not executed:
        return

    # 1-point buckets from 70 (gate threshold) up — granular enough to see
    # which bands are actually contributing trades.
    buckets: Dict[int, int] = {}
    for lo in range(70, 100):
        buckets[lo] = 0
    below = 0

    for s in executed:
        conf = s.get("confluence", 0) or 0
        lo = int(conf)
        if lo < 70:
            below += 1
        elif lo in buckets:
            buckets[lo] += 1
        else:
            buckets[99] = buckets.get(99, 0) + 1

    total = len(executed)
    print()
    print(bold(f"SCORE DISTRIBUTION  ({total} executed signals)"))
    bar_max = max(max(buckets.values(), default=0), below, 1)
    if below:
        bar = "█" * round(below / bar_max * 20)
        print(f"  {' <70':>6}  {red(bar):<22}  {below:>2} trades  ({below/total*100:.0f}%)")
    for lo, count in sorted(buckets.items()):
        if count == 0:
            continue
        bar = "█" * round(count / bar_max * 20)
        pct = count / total * 100
        colour = green if lo >= 75 else yellow
        label = f"{lo}-{lo+1}"
        print(f"  {label:>6}  {colour(bar):<22}  {count:>2} trades  ({pct:.0f}%)")


def _print_btc_state_analysis(all_signals: List[Dict], all_trades: List[Dict]):
    executed = [s for s in all_signals if s.get("result") == "executed"]
    if not executed:
        return

    trade_map: Dict[Tuple, Dict] = {}
    for t in all_trades:
        trade_map[(t.get("symbol"), t.get("direction"))] = t

    by_btc: Dict[str, List[float]] = defaultdict(list)
    for s in executed:
        btc_state = (
            s.get("btc_impulse")
            or s.get("btc_state")
            or (s.get("btc_factor") or {}).get("status")
            or "unknown"
        )
        t = trade_map.get((s.get("symbol"), s.get("direction")))
        if t:
            by_btc[str(btc_state)].append(t.get("pnl", 0))

    if not by_btc or list(by_btc.keys()) == ["unknown"]:
        return

    print()
    print(bold("WIN RATE BY BTC STATE AT ENTRY"))
    headers = ["BTC State", "Trades", "Win%", "EV/trade"]
    rows = []
    for state, pnls in sorted(by_btc.items()):
        wins = sum(1 for p in pnls if p > 1.0)
        ev = sum(pnls) / len(pnls)
        win_pct = wins / len(pnls) * 100
        ev_str = f"${ev:+.2f}"
        rows.append((state, len(pnls), f"{win_pct:.0f}%", ev_str))

    col_widths = [max(len(str(h)), max(len(str(r[i])) for r in rows)) for i, h in enumerate(headers)]
    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
    print(fmt.format(*headers))
    print("  ".join("─" * w for w in col_widths))
    for row in rows:
        ev_val = float(row[3].replace("$", "").replace("+", ""))
        ev_str = green(row[3]) if ev_val >= 0 else red(row[3])
        print(fmt.format(row[0], row[1], row[2], ev_str))


def _print_factor_correlation(all_signals: List[Dict], all_trades: List[Dict]):
    executed = [s for s in all_signals if s.get("result") == "executed"]
    if not executed:
        return

    trade_map: Dict[Tuple, Dict] = {}
    for t in all_trades:
        trade_map[(t.get("symbol"), t.get("direction"))] = t

    factor_wins: Dict[str, int] = defaultdict(int)
    factor_losses: Dict[str, int] = defaultdict(int)

    for s in executed:
        t = trade_map.get((s.get("symbol"), s.get("direction")))
        if not t:
            continue
        won = t.get("pnl", 0) > 1.0
        for f in s.get("factors", []):
            name = f.get("name", "?")
            score = f.get("score", 0) or 0
            if score >= 75:
                if won:
                    factor_wins[name] += 1
                else:
                    factor_losses[name] += 1

    all_factors = set(factor_wins) | set(factor_losses)
    if not all_factors:
        return

    print()
    print(bold("FACTOR WIN CORRELATION  (factors scoring ≥75, win% when present)"))
    headers = ["Factor", "W", "L", "Win%", "Signal"]
    rows = []
    for name in sorted(all_factors):
        w = factor_wins.get(name, 0)
        l = factor_losses.get(name, 0)
        total = w + l
        if total < 2:
            continue
        win_pct = w / total * 100
        signal = (green("strong") if win_pct >= 65
                  else yellow("weak") if win_pct >= 45
                  else red("noise"))
        rows.append((name[:32], w, l, f"{win_pct:.0f}%", signal))

    rows.sort(key=lambda r: -int(r[3].rstrip("%")))
    col_widths = [max(len(str(h)), max(len(str(r[i])) for r in rows)) for i, h in enumerate(headers)]
    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
    print(fmt.format(*headers))
    print("  ".join("─" * w for w in col_widths))
    for row in rows:
        print(fmt.format(*row))


def _print_system_diagnostics(
    all_trades: List[Dict],
    all_signals: List[Dict],
    config: Dict,
    session_dirs: Optional[List[Path]] = None,
):
    executed = [s for s in all_signals if s.get("result") == "executed"]
    filtered = [s for s in all_signals if s.get("result") == "filtered"]
    total_trades = len(all_trades)

    print()
    print(bold("SYSTEM DIAGNOSTICS"))

    # ── Stop geometry gate ────────────────────────────────────────────────────
    stop_gate_hits = sum(
        1 for s in filtered
        if (s.get("reason_type") or s.get("reason") or "") in ("stop_pct_too_wide", "no_trade_plan")
        and "stop" in str(s.get("message") or "").lower()
    )
    cap_violations = 0
    for s in executed:
        pct = _stop_pct_for_signal(s)
        tt = (s.get("trade_type") or "scalp").lower()
        cap = _STOP_PCT_CAPS.get(tt, 0.05)
        if pct is not None and pct > cap:
            cap_violations += 1

    if cap_violations == 0:
        print(f"  {green('✅')} Stop geometry gate: no cap violations in executed trades")
    else:
        print(f"  {red('❌')} Stop geometry gate: {cap_violations} executed trades exceeded stop % cap — gate may not be active")

    # ── BTC conflict penalty ──────────────────────────────────────────────────
    neutral_up_shorts = []
    for s in executed:
        regime = s.get("regime") or ""
        direction = s.get("direction") or ""
        btc_state = (
            s.get("btc_impulse")
            or s.get("btc_state")
            or (s.get("btc_factor") or {}).get("status")
            or ""
        )
        if "up" in regime and direction == "SHORT" and "neutral" in str(btc_state).lower():
            neutral_up_shorts.append(s)

    if neutral_up_shorts:
        syms = ", ".join(s.get("symbol", "?") for s in neutral_up_shorts)
        print(f"  {yellow('⚠️ ')} BTC neutral + up-regime SHORTs: {len(neutral_up_shorts)} trades ({syms}) — "
              f"BTC conflict penalty skipped (btc_score=100, block not triggered)")
    else:
        print(f"  {green('✅')} BTC conflict penalty: no neutral-BTC + up-regime SHORT gap detected")

    # ── Stagnation quality ────────────────────────────────────────────────────
    stag_trades = [t for t in all_trades if t.get("exit_reason") == "stagnation"]
    premature_stagnations = [t for t in stag_trades if (t.get("max_favorable") or 0) >= 0.5]
    if premature_stagnations:
        syms = ", ".join(t.get("symbol", "?") for t in premature_stagnations)
        print(f"  {yellow('⚠️ ')} Stagnation cut live trades: {len(premature_stagnations)} exits had MFE ≥0.5% ({syms}) — "
              f"consider MFE guard")
    else:
        clean_stags = len([t for t in stag_trades if (t.get("max_favorable") or 0) < 0.2])
        print(f"  {green('✅')} Stagnation quality: {clean_stags}/{len(stag_trades)} exits had MFE <0.2% (correctly flat)")

    # ── Breakeven stop false positives ───────────────────────────────────────
    be_positives = [
        t for t in all_trades
        if t.get("exit_reason") == "stop_loss" and (t.get("pnl") or 0) > 0
    ]
    if be_positives:
        print(f"  {green('✅')} Breakeven stops: {len(be_positives)} stop_loss exits with positive P&L — "
              f"expected (TP1 hit → breakeven stop)")

    # ── Threshold scrapers ────────────────────────────────────────────────────
    scrapers = [s for s in executed if (s.get("confluence") or 0) < 71.0]
    if scrapers:
        scraper_syms = defaultdict(int)
        for s in scrapers:
            scraper_syms[s.get("symbol", "?")] += 1
        sym_str = ", ".join(f"{sym}×{n}" for sym, n in sorted(scraper_syms.items(), key=lambda x: -x[1]))
        print(f"  {yellow('⚠️ ')} Threshold scrapers (score 70-71): {len(scrapers)} trades — {sym_str}")
    else:
        print(f"  {green('✅')} No threshold scrapers detected (all executed signals scored ≥71)")

    # ── Systematic symbol losers ──────────────────────────────────────────────
    by_sym: Dict[str, List[Dict]] = defaultdict(list)
    for t in all_trades:
        by_sym[t.get("symbol", "?")].append(t)

    flagged_syms = []
    for sym, trades in by_sym.items():
        if len(trades) >= 3:
            wins = sum(1 for t in trades if (t.get("pnl") or 0) > 1.0)
            win_pct = wins / len(trades)
            net = sum(t.get("pnl", 0) for t in trades)
            if win_pct == 0 or (win_pct < 0.30 and net < -10):
                flagged_syms.append((sym, len(trades), win_pct * 100, net))

    if flagged_syms:
        print(f"  {red('❌')} Systematic underperformers (≥3 trades, <30% win):")
        for sym, n, wp, net in flagged_syms:
            print(f"       {sym}: {n} trades, {wp:.0f}% win, ${net:+.2f} net — review exclusion")
    else:
        print(f"  {green('✅')} No systematic symbol losers detected")

    # ── Score band drift vs prior session ────────────────────────────────────
    if session_dirs and len(session_dirs) == 1:
        prior_dirs = _find_sessions()
        idx = next((i for i, d in enumerate(prior_dirs) if d == session_dirs[0]), None)
        if idx is not None and idx > 0:
            prior_signals = _load_jsonl(prior_dirs[idx - 1] / "signals.jsonl")
            prior_exec = [s for s in prior_signals if s.get("result") == "executed"]
            if prior_exec:
                def _b_band_share(sigs):
                    bb = sum(1 for s in sigs if 65 <= (s.get("confluence") or 0) < 75)
                    return bb / len(sigs) * 100 if sigs else 0

                cur_bb = _b_band_share(executed)
                pri_bb = _b_band_share(prior_exec)
                drift = cur_bb - pri_bb
                drift_str = f"{drift:+.0f}pp"
                drift_colour = yellow if abs(drift) >= 10 else green
                print(f"  {'⚠️ ' if abs(drift) >= 10 else '✅'} B-band share: "
                      f"{cur_bb:.0f}% this session vs {pri_bb:.0f}% prior "
                      f"({drift_colour(drift_str)}){'  ← more borderline signals executing' if drift >= 10 else ''}")


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


def _targets_hit_count(trade: Dict) -> int:
    """Return number of TP levels the trade reached."""
    th = trade.get("targets_hit", [])
    if isinstance(th, list):
        return len(th)
    if isinstance(th, int):
        return th
    return 0


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


def _aggregate_report(
    all_trades: List[Dict],
    all_signals: List[Dict],
    session_label: str,
    config: Optional[Dict] = None,
    session_dirs: Optional[List[Path]] = None,
):
    print()
    print(bold("=" * 80))
    print(bold(f"  SNIPERSIGHT SESSION ANALYSIS  —  {session_label}"))
    _print_config_block(config or {})
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

    # ── Best trades ───────────────────────────────────────────────────────────
    best = sorted(all_trades, key=lambda t: t.get("pnl", 0), reverse=True)[:5]
    if best and best[0].get("pnl", 0) > 0:
        print()
        print(bold("TOP 5 BEST TRADES"))
        for t in best:
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
            print(f"    {green(f'${pnl:+.2f}'):>12}  {sym:<6} {direction:<5} {tt:<9} {exit_reason:<14} {dur_str:<8} regime={regime} rr={rr:.1f}R")

    # ── EV by symbol ──────────────────────────────────────────────────────────
    by_sym: Dict[str, List[Dict]] = defaultdict(list)
    for t in all_trades:
        by_sym[t.get("symbol", "?")].append(t)

    if len(by_sym) > 1:
        sym_rows = []
        for sym, trades in sorted(by_sym.items(), key=lambda x: _ev(x[1])):
            ev_val = _ev(trades)
            net = sum(t.get("pnl", 0) for t in trades)
            sym_rows.append((
                sym,
                len(trades),
                f"{_win_pct(trades):.0f}%",
                f"${_avg_win(trades):+.2f}",
                f"${_avg_loss(trades):+.2f}",
                f"${ev_val:+.2f}",
                f"${net:+.2f}",
            ))
        _print_table(
            "EV BY SYMBOL",
            sym_rows,
            ["Symbol", "Trades", "Win%", "Avg Win", "Avg Loss", "EV/trade", "Net P&L"],
        )

    # ── Target ladder hit rates ───────────────────────────────────────────────
    # How many trades reached TP1, TP2, TP3 — tells you if the ladder is
    # sized for this market or if only TP1 is ever reachable.
    tp1_hits = sum(1 for t in all_trades if _targets_hit_count(t) >= 1)
    tp2_hits = sum(1 for t in all_trades if _targets_hit_count(t) >= 2)
    tp3_hits = sum(1 for t in all_trades if _targets_hit_count(t) >= 3)
    # Breakeven trades: hit TP1 (moved stop to entry) but final exit was stop_loss
    be_stops = sum(
        1 for t in all_trades
        if _targets_hit_count(t) >= 1 and t.get("exit_reason") == "stop_loss"
    )
    if tp1_hits > 0 or tp2_hits > 0:
        print()
        print(bold("TARGET LADDER ANALYSIS"))
        print(f"  TP1 reached:  {tp1_hits:>3} / {total}  ({tp1_hits/total*100:.0f}%)")
        print(f"  TP2 reached:  {tp2_hits:>3} / {total}  ({tp2_hits/total*100:.0f}%)"
              + (f"  of TP1 hitters: {tp2_hits/tp1_hits*100:.0f}%" if tp1_hits else ""))
        print(f"  TP3 reached:  {tp3_hits:>3} / {total}  ({tp3_hits/total*100:.0f}%)"
              + (f"  of TP2 hitters: {tp3_hits/tp2_hits*100:.0f}%" if tp2_hits else ""))
        if be_stops > 0:
            print(f"  {yellow(f'Breakeven stops: {be_stops}  (hit TP1 but stopped at entry — runner captured nothing)')}")

    # ── Realized R:R vs planned ───────────────────────────────────────────────
    # The gap between planned R:R and actual win/loss ratio is the single most
    # diagnostic number in the system. Planned 1.8R → actual 0.4:1 = broken targets.
    avg_win_val = _avg_win(all_trades)
    avg_loss_val = abs(_avg_loss(all_trades))
    realized_rr = avg_win_val / avg_loss_val if avg_loss_val > 0 else 0.0
    planned_rrs = [t.get("risk_reward_ratio", 0) for t in all_trades if t.get("risk_reward_ratio", 0) > 0]
    avg_planned_rr = sum(planned_rrs) / len(planned_rrs) if planned_rrs else 0.0
    rr_gap = realized_rr - avg_planned_rr
    if avg_planned_rr > 0:
        print()
        print(bold("REALIZED vs PLANNED R:R"))
        rr_colour = green if realized_rr >= avg_planned_rr * 0.7 else red
        print(f"  Planned avg R:R:   {avg_planned_rr:.2f}R")
        print(f"  Realized R:R:      {rr_colour(f'{realized_rr:.2f}R')}  "
              f"(avg win ${avg_win_val:.2f} ÷ avg loss ${avg_loss_val:.2f})")
        efficiency = realized_rr / avg_planned_rr * 100 if avg_planned_rr > 0 else 0
        eff_colour = green if efficiency >= 70 else (yellow if efficiency >= 40 else red)
        print(f"  R:R efficiency:    {eff_colour(f'{efficiency:.0f}%')}  "
              + ("(targets are reachable)" if efficiency >= 70
                 else ("(targets partially reachable)" if efficiency >= 40
                       else "(targets are structurally out of reach)")))

    # ── MFE / MAE aggregate analysis ─────────────────────────────────────────
    # Peak profit and peak drawdown per trade type. If avg MFE on losers is
    # near 0, the trade was never right — widen confluence or tighten entry.
    # If avg MFE on losers is >0.5%, the trade was right but management failed.
    winner_mfes = [t.get("max_favorable", 0) for t in all_trades if t.get("pnl", 0) > 1.0]
    loser_mfes  = [t.get("max_favorable", 0) for t in all_trades if t.get("pnl", 0) < -1.0]
    winner_maes = [t.get("max_adverse", 0)   for t in all_trades if t.get("pnl", 0) > 1.0]
    loser_maes  = [t.get("max_adverse", 0)   for t in all_trades if t.get("pnl", 0) < -1.0]

    if winner_mfes or loser_mfes:
        avg_w_mfe = sum(winner_mfes) / len(winner_mfes) if winner_mfes else 0
        avg_l_mfe = sum(loser_mfes)  / len(loser_mfes)  if loser_mfes  else 0
        avg_w_mae = sum(winner_maes) / len(winner_maes) if winner_maes else 0
        avg_l_mae = sum(loser_maes)  / len(loser_maes)  if loser_maes  else 0
        print()
        print(bold("MFE / MAE ANALYSIS  (peak profit% and peak drawdown% per trade)"))
        print(f"  {'':8}  {'Avg MFE':>10}  {'Avg MAE':>10}  {'MFE:MAE ratio':>14}  note")
        print(f"  {'─'*8}  {'─'*10}  {'─'*10}  {'─'*14}  {'─'*30}")
        if winner_mfes:
            w_ratio = avg_w_mfe / avg_w_mae if avg_w_mae > 0 else 0
            print(f"  {'Winners':8}  {green(f'+{avg_w_mfe:.2f}%'):>10}  {f'{avg_w_mae:.2f}%':>10}  "
                  f"{green(f'{w_ratio:.1f}x'):>14}  price went right then kept going")
        if loser_mfes:
            l_ratio = avg_l_mfe / avg_l_mae if avg_l_mae > 0 else 0
            note = ("entry was correct, management failed" if avg_l_mfe >= 0.4
                    else "trade was wrong from the start")
            colour = yellow if avg_l_mfe >= 0.4 else red
            print(f"  {'Losers':8}  {colour(f'+{avg_l_mfe:.2f}%'):>10}  {f'{avg_l_mae:.2f}%':>10}  "
                  f"{colour(f'{l_ratio:.1f}x'):>14}  {note}")

    # ── Kill zone EV ─────────────────────────────────────────────────────────
    # Entries outside kill zones (London/NY open) have structurally lower volume
    # and less directional commitment. Quantify the cost.
    by_kz: Dict[str, List[Dict]] = defaultdict(list)
    sig_map = {(s["symbol"], s["direction"]): s for s in all_signals if s.get("result") == "executed"}
    for t in all_trades:
        sig = sig_map.get((t.get("symbol"), t.get("direction")))
        kz = (sig.get("kill_zone") if sig else None) or "no_session"
        by_kz[kz].append(t)

    if len(by_kz) > 1 or (len(by_kz) == 1 and "no_session" not in by_kz):
        kz_rows = []
        for kz, trades in sorted(by_kz.items(), key=lambda x: _ev(x[1])):
            ev_val = _ev(trades)
            kz_rows.append((kz, len(trades), f"{_win_pct(trades):.0f}%", f"${ev_val:+.2f}"))
        _print_table("EV BY KILL ZONE", kz_rows, ["Kill Zone", "Trades", "Win%", "EV/trade"])
    elif "no_session" in by_kz:
        kz_trades = by_kz["no_session"]
        kz_ev = _ev(kz_trades)
        kz_colour = green if kz_ev >= 0 else red
        print()
        print(bold("KILL ZONE NOTE"))
        print(f"  {len(kz_trades)}/{total} trades ({len(kz_trades)/total*100:.0f}%) executed outside kill zones "
              f"| EV: {kz_colour(f'${kz_ev:+.2f}')}")

    # ── Counter-trend vs trend-following ─────────────────────────────────────
    # Identify trades where direction opposes the regime trend. With the new
    # counter-trend gate these should decrease — this section shows the baseline
    # and any that slipped through (e.g. counter-trend scalps at ≥70% conf).
    ct_trades, tf_trades = [], []
    for t in all_trades:
        regime_raw = t.get("regime", "") or ""
        direction = t.get("direction", "")
        is_ct = (
            ("up" in regime_raw and direction == "SHORT") or
            ("down" in regime_raw and direction == "LONG")
        )
        (ct_trades if is_ct else tf_trades).append(t)

    if ct_trades:
        ct_ev = _ev(ct_trades)
        tf_ev = _ev(tf_trades)
        ct_colour = green if ct_ev >= 0 else red
        tf_colour = green if tf_ev >= 0 else red
        print()
        print(bold("COUNTER-TREND vs TREND-FOLLOWING"))
        print(f"  Trend-following:  {len(tf_trades):>3} trades  {_win_pct(tf_trades):.0f}% win  EV {tf_colour(f'${tf_ev:+.2f}')}")
        print(f"  Counter-trend:    {len(ct_trades):>3} trades  {_win_pct(ct_trades):.0f}% win  EV {ct_colour(f'${ct_ev:+.2f}')}"
              + (f"  ← regime gate not blocking these" if ct_ev < 0 else ""))

    # ── New sections ─────────────────────────────────────────────────────────
    _print_equity_curve(all_trades)
    _print_stop_geometry(all_signals, all_trades)
    _print_score_histogram(all_signals)
    _print_btc_state_analysis(all_signals, all_trades)
    _print_factor_correlation(all_signals, all_trades)
    _print_system_diagnostics(all_trades, all_signals, config or {}, session_dirs)


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
    config: Dict = {}

    for sd in session_dirs:
        sd = Path(sd)
        all_trades.extend(_load_jsonl(sd / "trades.jsonl"))
        all_signals.extend(_load_jsonl(sd / "signals.jsonl"))
        if not config:
            config = _load_json(sd / "config.json")

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
    _aggregate_report(all_trades, all_signals, label, config=config, session_dirs=session_dirs)

    print()


if __name__ == "__main__":
    main()
