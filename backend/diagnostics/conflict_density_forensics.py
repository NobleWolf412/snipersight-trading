"""
Conflict-Density Forensics — counterfactual analysis of blocked scalps
=======================================================================
Answers the strategic question raised in the session 84fd5c96 audit:
the `conflict_density` pre-scoring gate caught 46% of all rejections
this session — 10 majors hit it on 220/220 cycles each. Was the gate
correctly identifying multi-TF chop, or was it over-blocking winners?

Method:
  1. Read session signals.jsonl, filter to rows where gate_name="conflict_density"
  2. For each (symbol, timestamp, direction) triple, fetch live 5m OHLCV
     around the rejection point and compute 15m-ATR-anchored scalp geometry
  3. Walk forward N minutes from the rejection moment and classify outcome:
     - target  : price hit +target_atr × ATR before -stop_atr × ATR (for LONG; mirrored for SHORT)
     - stop    : price hit stop before target
     - timeout : neither — position would have closed at max_hours
  4. Aggregate per-symbol and overall. Net R is the EV proxy.

Verdict logic (net-R-centric, NOT win-rate-centric — at 1:2 RR a 33%
win rate is still positive EV; win-rate-only verdicts mislead):
  net_R         = target_count × (target_atr/stop_atr) - stop_count × 1.0
  R_per_signal  = net_R / total_blocked    # EV per evaluation if gate removed
  - OVER-BLOCKING   : R_per_signal > +0.05  (positive EV after typical scalp costs)
  - CORRECT-BLOCKING: R_per_signal < -0.05  (negative EV — gate is right to block)
  - AMBIGUOUS       : -0.05 ≤ R_per_signal ≤ +0.05  (near break-even after costs)
The ±0.05R band is calibrated to typical perp scalp transaction costs
(slippage + fees combined).

Per CLAUDE.md §12 (paste-friendly), §15 (no threshold tuning without baseline
data — this script PRODUCES the baseline data for any future decision on the
conflict_density threshold).

Usage:
    python -X utf8 -m backend.diagnostics.conflict_density_forensics              # latest session
    python -X utf8 -m backend.diagnostics.conflict_density_forensics 84fd5c96     # specific session

Output: paste-friendly summary first, per-symbol table second, raw outcome
counts last. Exit code 0 always — this is observational, not pass/fail.
"""

from __future__ import annotations

import glob
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import pandas as pd

# Default scalp geometry — calibrated against the bot's planner defaults for
# STEALTH-mode scalps (1.0 ATR stop, 2.0 ATR target → 1:2 RR). Tweakable via
# CLI args; the script reports the geometry it ran with so the operator can
# re-run with alternates and see whether the verdict is geometry-sensitive.
DEFAULT_STOP_ATR = 1.0
DEFAULT_TARGET_ATR = 2.0
DEFAULT_HORIZON_MIN = 60
ATR_PERIOD = 14
ATR_TIMEFRAME = "15m"
EXEC_TIMEFRAME = "5m"

# Forward-look window — how many 5m candles to walk after the rejection
# timestamp. 60 minutes = 12 candles. Stops the simulation if neither
# target nor stop hits in this window (counts as "timeout").
HORIZON_5M_CANDLES = DEFAULT_HORIZON_MIN // 5


@dataclass
class Outcome:
    """Outcome of one counterfactual scalp simulation."""
    symbol: str
    direction: str  # LONG / SHORT
    ts: datetime
    entry_price: float
    stop_price: float
    target_price: float
    atr: float
    result: str  # target | stop | timeout | no_data
    minutes_to_hit: Optional[int] = None
    exit_price: Optional[float] = None


def _resolve_session_path(session_id: Optional[str]) -> Tuple[str, str]:
    """Find the signals.jsonl for the session. Returns (path, session_id).
    If session_id is None, use the latest by mtime."""
    candidates = sorted(glob.glob("logs/paper_trading/session_*/signals.jsonl"))
    if not candidates:
        raise FileNotFoundError("No session signals.jsonl files found under logs/paper_trading/")

    if session_id:
        matches = [c for c in candidates if f"session_{session_id}" in c]
        if not matches:
            raise FileNotFoundError(f"Session {session_id} not found among {len(candidates)} sessions")
        return matches[0], session_id

    # Latest by mtime
    candidates.sort(key=os.path.getmtime)
    latest = candidates[-1]
    sid = os.path.basename(os.path.dirname(latest)).replace("session_", "")
    return latest, sid


def _load_blocked_rows(path: str) -> List[Dict]:
    """Return all signals.jsonl rows where gate_name == 'conflict_density'."""
    blocked = []
    for line in open(path, encoding="utf-8"):
        try:
            r = json.loads(line)
            if r.get("gate_name") == "conflict_density":
                blocked.append(r)
        except Exception:
            continue
    return blocked


def _compute_atr(df_15m: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    """Standard ATR(14) on 15m candles. Uses Wilder smoothing (EMA-like)."""
    h, l, c = df_15m["high"], df_15m["low"], df_15m["close"]
    prev_c = c.shift(1)
    tr = pd.concat([
        h - l,
        (h - prev_c).abs(),
        (l - prev_c).abs(),
    ], axis=1).max(axis=1)
    # Wilder smoothing
    atr = tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    return atr


def _simulate_one(
    symbol: str,
    direction: str,
    ts: datetime,
    df_5m: pd.DataFrame,
    df_15m: pd.DataFrame,
    stop_atr: float,
    target_atr: float,
) -> Outcome:
    """Walk forward HORIZON_5M_CANDLES candles from `ts`. Classify outcome."""
    # Find the candle whose timestamp covers `ts`
    if df_5m.empty or df_15m.empty:
        return Outcome(symbol, direction, ts, 0, 0, 0, 0, "no_data")

    # Normalize comparison to UTC tz-naive (phemex returns tz-naive timestamps)
    ts_naive = ts.replace(tzinfo=None) if ts.tzinfo else ts

    df_5m = df_5m.copy()
    df_5m["timestamp"] = pd.to_datetime(df_5m["timestamp"], errors="coerce")
    df_15m = df_15m.copy()
    df_15m["timestamp"] = pd.to_datetime(df_15m["timestamp"], errors="coerce")

    # ATR at the rejection point (last 15m candle whose timestamp <= ts)
    df_15m_until = df_15m[df_15m["timestamp"] <= ts_naive]
    if len(df_15m_until) < ATR_PERIOD + 1:
        return Outcome(symbol, direction, ts, 0, 0, 0, 0, "no_data")
    atr_series = _compute_atr(df_15m_until)
    atr_val = float(atr_series.iloc[-1])
    if not (atr_val > 0):
        return Outcome(symbol, direction, ts, 0, 0, 0, 0, "no_data")

    # Entry: open of the next 5m candle after `ts` (simulating that the
    # signal would have been emitted at `ts` and filled on the next bar's open)
    fwd_5m = df_5m[df_5m["timestamp"] > ts_naive].reset_index(drop=True)
    if len(fwd_5m) < 1:
        return Outcome(symbol, direction, ts, 0, 0, 0, 0, "no_data")

    entry = float(fwd_5m.iloc[0]["open"])
    if not (entry > 0):
        return Outcome(symbol, direction, ts, 0, 0, 0, 0, "no_data")

    if direction == "LONG":
        stop = entry - stop_atr * atr_val
        target = entry + target_atr * atr_val
    else:  # SHORT
        stop = entry + stop_atr * atr_val
        target = entry - target_atr * atr_val

    # Walk forward up to HORIZON_5M_CANDLES candles
    horizon = fwd_5m.iloc[:HORIZON_5M_CANDLES]
    for i, row in horizon.iterrows():
        h, l = float(row["high"]), float(row["low"])
        # Conservative tie-break: if a single candle hits both, assume stop hit first
        # (worst-case for the trader; protects against overstating gate over-blocking)
        if direction == "LONG":
            stop_hit = (l <= stop)
            target_hit = (h >= target)
        else:
            stop_hit = (h >= stop)
            target_hit = (l <= target)

        if stop_hit:
            return Outcome(
                symbol, direction, ts, entry, stop, target, atr_val,
                "stop", minutes_to_hit=int((i + 1) * 5), exit_price=stop,
            )
        if target_hit:
            return Outcome(
                symbol, direction, ts, entry, stop, target, atr_val,
                "target", minutes_to_hit=int((i + 1) * 5), exit_price=target,
            )

    # Neither hit in the horizon
    exit_close = float(horizon.iloc[-1]["close"]) if len(horizon) > 0 else entry
    return Outcome(
        symbol, direction, ts, entry, stop, target, atr_val,
        "timeout", minutes_to_hit=HORIZON_5M_CANDLES * 5, exit_price=exit_close,
    )


def _fetch_per_symbol_candles(
    adapter,
    symbols: List[str],
    session_start_ts: datetime,
) -> Dict[str, Tuple[pd.DataFrame, pd.DataFrame]]:
    """Bulk-fetch 5m + 15m for each symbol. Returns dict[symbol → (5m_df, 15m_df)]."""
    out: Dict[str, Tuple[pd.DataFrame, pd.DataFrame]] = {}
    for sym in symbols:
        try:
            # 500 × 5m  = ~41 hours of history → easily covers an 11-hour session
            # plus the 60-min forward-look window past session end.
            df_5m = adapter.fetch_ohlcv(sym, EXEC_TIMEFRAME, limit=500)
            df_15m = adapter.fetch_ohlcv(sym, ATR_TIMEFRAME, limit=300)
            out[sym] = (df_5m if df_5m is not None else pd.DataFrame(),
                        df_15m if df_15m is not None else pd.DataFrame())
        except Exception as exc:
            print(f"  WARN: fetch failed for {sym}: {type(exc).__name__}: {exc}")
            out[sym] = (pd.DataFrame(), pd.DataFrame())
    return out


def _verdict(target_n: int, stop_n: int, target_atr: float, stop_atr: float, total_n: int) -> Tuple[str, float, float, float]:
    """Return (verdict_label, win_rate, net_R, R_per_signal).

    Verdict is net-R-centric, not win-rate-centric. At 1:2 RR a 33% win
    rate is positive EV; win-rate-only verdicts would falsely call that
    "correct-blocking". R_per_signal divides net_R by ALL signals
    (including timeouts at 0R) to express EV per blocked evaluation —
    directly comparable to typical scalp transaction-cost band
    (~0.05R combined slippage+fees on perps).
    """
    decisive = target_n + stop_n
    if decisive == 0 or total_n == 0:
        return ("AMBIGUOUS (no decisive outcomes)", 0.0, 0.0, 0.0)
    win_rate = target_n / decisive
    net_R = target_n * (target_atr / stop_atr) - stop_n * 1.0
    r_per_signal = net_R / total_n

    # Thresholds calibrated around typical scalp transaction-cost band.
    # A blocked-signal EV below cost is "correctly blocked"; above cost
    # is "over-blocked". The ±0.05R band keeps the verdict honest about
    # uncertainty when EV is near break-even.
    if r_per_signal > 0.05:
        verdict = "OVER-BLOCKING"
    elif r_per_signal < -0.05:
        verdict = "CORRECT-BLOCKING"
    else:
        verdict = "AMBIGUOUS"
    return (verdict, win_rate, net_R, r_per_signal)


def main(argv: List[str]) -> int:
    session_id_arg = argv[1] if len(argv) > 1 else None
    stop_atr = float(argv[2]) if len(argv) > 2 else DEFAULT_STOP_ATR
    target_atr = float(argv[3]) if len(argv) > 3 else DEFAULT_TARGET_ATR

    print("=" * 78)
    print("  CONFLICT-DENSITY FORENSICS — counterfactual analysis")
    print("=" * 78)

    path, sid = _resolve_session_path(session_id_arg)
    print(f"  Session   : {sid}")
    print(f"  Source    : {path}")
    print(f"  Geometry  : stop={stop_atr} × ATR({ATR_TIMEFRAME})  target={target_atr} × ATR({ATR_TIMEFRAME})")
    print(f"  Horizon   : {DEFAULT_HORIZON_MIN} minutes ({HORIZON_5M_CANDLES} × 5m candles)")
    print(f"  RR        : 1:{target_atr / stop_atr:.2f}")

    blocked_rows = _load_blocked_rows(path)
    if not blocked_rows:
        print("\n  No conflict_density rejections found in this session — nothing to analyse.")
        return 0

    # Group by symbol for bulk-fetch
    by_symbol: Dict[str, List[Dict]] = defaultdict(list)
    for r in blocked_rows:
        by_symbol[r.get("symbol", "?")].append(r)

    print(f"\n  Blocked evals : {len(blocked_rows)}")
    print(f"  Symbols touched: {len(by_symbol)}")
    print(f"  Per-symbol counts (top 15):")
    for s, rows in sorted(by_symbol.items(), key=lambda x: -len(x[1]))[:15]:
        print(f"    {s:14}{len(rows):>6}")

    # Resolve session start time (earliest blocked-row timestamp)
    timestamps = []
    for r in blocked_rows:
        ts_str = r.get("timestamp") or r.get("ts")
        if ts_str:
            try:
                timestamps.append(datetime.fromisoformat(ts_str.replace("Z", "+00:00")))
            except Exception:
                continue
    if not timestamps:
        print("\n  No parseable timestamps. Aborting.")
        return 1
    session_start = min(timestamps)

    # Fetch candles per symbol
    print(f"\n  Fetching {EXEC_TIMEFRAME}+{ATR_TIMEFRAME} candles for {len(by_symbol)} symbols…")
    from backend.data.adapters.phemex import PhemexAdapter
    adapter = PhemexAdapter()
    candles = _fetch_per_symbol_candles(adapter, list(by_symbol.keys()), session_start)

    # Run simulations
    print(f"\n  Simulating outcomes…")
    outcomes_by_symbol: Dict[str, List[Outcome]] = defaultdict(list)
    for sym, rows in by_symbol.items():
        df_5m, df_15m = candles.get(sym, (pd.DataFrame(), pd.DataFrame()))
        for r in rows:
            ts_str = r.get("timestamp") or r.get("ts")
            direction = r.get("direction", "LONG")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except Exception:
                continue
            outcome = _simulate_one(sym, direction, ts, df_5m, df_15m, stop_atr, target_atr)
            outcomes_by_symbol[sym].append(outcome)

    # ── Per-symbol table ─────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("  PER-SYMBOL OUTCOME (blocked direction = LONG/SHORT as picked pre-gate)")
    print("=" * 78)
    print(f"  {'symbol':14}{'n':>5}{'target':>9}{'stop':>8}{'timeout':>9}{'no_data':>9}{'win%':>7}{'netR':>8}{'R/sig':>8}  verdict")
    print("  " + "─" * 84)

    total_target = total_stop = total_timeout = total_no_data = 0
    for sym in sorted(outcomes_by_symbol.keys(), key=lambda s: -len(outcomes_by_symbol[s])):
        outs = outcomes_by_symbol[sym]
        n = len(outs)
        tg = sum(1 for o in outs if o.result == "target")
        sp = sum(1 for o in outs if o.result == "stop")
        to = sum(1 for o in outs if o.result == "timeout")
        nd = sum(1 for o in outs if o.result == "no_data")
        verdict, wr, nr, rps = _verdict(tg, sp, target_atr, stop_atr, n)
        total_target += tg
        total_stop += sp
        total_timeout += to
        total_no_data += nd
        print(
            f"  {sym:14}{n:>5}{tg:>6} ({100*tg/n if n else 0:>3.0f}%) "
            f"{sp:>4} ({100*sp/n if n else 0:>3.0f}%) "
            f"{to:>4} ({100*to/n if n else 0:>3.0f}%) "
            f"{nd:>4} ({100*nd/n if n else 0:>3.0f}%) "
            f"{100*wr:>5.0f}%{nr:>+7.1f}{rps:>+8.3f}  {verdict}"
        )

    # ── Aggregate ────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("  AGGREGATE COUNTERFACTUAL")
    print("=" * 78)
    grand_n = total_target + total_stop + total_timeout + total_no_data
    decisive = total_target + total_stop
    print(f"  Total blocked simulations : {grand_n}")
    print(f"  Hit target  : {total_target} ({100*total_target/grand_n if grand_n else 0:.1f}%)")
    print(f"  Hit stop    : {total_stop} ({100*total_stop/grand_n if grand_n else 0:.1f}%)")
    print(f"  Timed out   : {total_timeout} ({100*total_timeout/grand_n if grand_n else 0:.1f}%)")
    print(f"  No data     : {total_no_data} ({100*total_no_data/grand_n if grand_n else 0:.1f}%)")

    if decisive > 0:
        agg_verdict, agg_wr, agg_nr, agg_rps = _verdict(total_target, total_stop, target_atr, stop_atr, grand_n)
        print(f"\n  Win rate (of decisive outcomes): {100*agg_wr:.1f}%")
        print(f"  Net R if all allowed at 1:{target_atr/stop_atr:.2f} RR: {agg_nr:+.1f}R")
        print(f"  R per blocked signal (EV proxy): {agg_rps:+.3f}R  (cost band ≈ ±0.05R)")
        print(f"\n  GATE VERDICT: {agg_verdict}")
        print()
        if agg_verdict == "OVER-BLOCKING":
            print("  Interpretation: at this geometry, removing the conflict_density gate")
            print("  would have produced positive EV across the blocked cohort. The gate is")
            print("  rejecting setups that would have netted profit at THIS scalp profile.")
            print("  Sweep across tighter/wider geometry to see whether this verdict holds")
            print("  at the bot's actual planner profile.")
        elif agg_verdict == "CORRECT-BLOCKING":
            print("  Interpretation: at this geometry, the conflict_density gate is doing")
            print("  what it should — the blocked cohort had negative EV. Keep current logic;")
            print("  tuning the threshold would degrade results at this scalp profile.")
        else:
            print("  Interpretation: EV is within the transaction-cost band — outcome is")
            print("  effectively break-even at this geometry. Re-run with TIGHTER stops")
            print("  (0.5 × ATR) or BALANCED 1:1 RR to test whether a different scalp profile")
            print("  would have benefited from the blocked cohort. Sample run on session")
            print("  84fd5c96 (May 2026): standard 1.0/2.0 = AMBIGUOUS (-0.008R/sig);")
            print("  tight 0.5/1.0 = OVER-BLOCKING (+0.107R/sig); balanced 1.0/1.0 =")
            print("  OVER-BLOCKING (+0.148R/sig). Geometry-sensitive verdicts mean the")
            print("  STRATEGIC choice is whether the bot's scalp profile matches the gate.")

    # ── Per-symbol verdict distribution ─────────────────────────────
    print("\n" + "─" * 78)
    print("  PER-SYMBOL VERDICT DISTRIBUTION")
    print("─" * 78)
    verdicts = defaultdict(list)
    for sym, outs in outcomes_by_symbol.items():
        tg = sum(1 for o in outs if o.result == "target")
        sp = sum(1 for o in outs if o.result == "stop")
        n = len(outs)
        v, _, _, _ = _verdict(tg, sp, target_atr, stop_atr, n)
        verdicts[v].append(sym)
    for v in ("OVER-BLOCKING", "CORRECT-BLOCKING", "AMBIGUOUS"):
        syms = verdicts.get(v, [])
        if syms:
            print(f"  {v} ({len(syms)} symbols): {', '.join(syms)}")
        else:
            also = [k for k in verdicts.keys() if v in k]
            if also:
                print(f"  {v} ({len(also)} symbols): {also}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
