"""
Phase 5-pre — P/D anchor disagreement: window(50) vs structure-anchored dealing range.

Purpose
-------
MEASURE-FIRST gate for Phase 5 (design entry:
decisions/2026-06-12__phase5-design-pd-structure-anchored-dealing-range.md).
Before any production code changes, quantify how the approved structure-anchored
dealing range (algorithm a*: last confirmed swing pair + running-extreme extension)
disagrees with the current fixed `lookback=50` window:

  PART A (live grid)   : per symbol x TF x mode — classification flip rate
                         (premium<->discount), EQ delta in ATR units, zone_percentage
                         delta, sparse-structure FALLBACK rate, mass conservation.
  PART B (gate cf.)    : replay historical gate-clearers from signals.jsonl through
                         the gate's step-5 `in_optimal_zone` predicate (scorer.py
                         :1138-1140) with BOTH equilibria on the gate's HTF df (1d —
                         structure_tfs defaults to ("4h","1d"), gate takes max).
                         Reports the in_optimal_zone flip rate = UPPER BOUND on
                         PremiumDiscount_VIOLATION (-40) flips. It is an upper bound
                         because the -40 additionally requires min_aligned_distance
                         > 1.0 ATR (gate state not reconstructable from JSONL).

The structural range mirrors the APPROVED design exactly (operator-locked Q1: RAW
fractals, no ATR filter):
  - swings: _detect_swing_highs/_lows (bos_choch.py) with TF-scaled
    structure_swing_lookback from get_tf_smc_config(tf, mode) / scale_lookback —
    the same structure the BOS/CHoCH engine sees
  - dedup to alternating sequence via _build_swing_sequence
  - SH* / SL* = last high-type / low-type entries of the cleaned sequence
  - range_high = max(SH*, running high after SH*); range_low = min(SL*, running
    low after SL*)
  - EQ / classification formulas IDENTICAL to premium_discount.py:74-100
    (same >= tie-break -> premium)
  - no confirmed SH or SL -> window fallback (counted; loud)

READ-ONLY. No engine files modified. No thresholds proposed — numbers only.
This script is the STOP point: operator reviews output before 5B/5C land (Q5).

USAGE
    python -X utf8 -m backend.diagnostics.phase5_pd_anchor_disagreement
    python -X utf8 -m backend.diagnostics.phase5_pd_anchor_disagreement --skip-part-b
    # defaults: 5 majors x {15m,1h,4h,1d} x 4 modes; Part B on logs/paper_trading/*
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

import pandas as pd

MODES = ("overwatch", "stealth", "strike", "surgical")
DEFAULT_SYMBOLS = [
    "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "BNB/USDT:USDT", "XRP/USDT:USDT",
]
DEFAULT_TFS = ["15m", "1h", "4h", "1d"]
GATE_HTF = "1d"  # max(structure_tfs) with the ("4h","1d") default — scorer.py:958,:1123


# ---------------------------------------------------------------------------
# Structural dealing range — mirrors the APPROVED Phase 5 design (a*) exactly
# ---------------------------------------------------------------------------
def structural_dealing_range(
    df: pd.DataFrame, swing_lookback: int
) -> Optional[Tuple[float, float, object, object]]:
    """Return (range_high, range_low, sh_ts, sl_ts) or None -> window fallback."""
    from backend.strategy.smc.bos_choch import (
        _build_swing_sequence,
        _detect_swing_highs,
        _detect_swing_lows,
    )

    swing_highs = _detect_swing_highs(df, swing_lookback)
    swing_lows = _detect_swing_lows(df, swing_lookback)
    if swing_highs.empty or swing_lows.empty:
        return None

    hl_order, level_order, idx_order = _build_swing_sequence(swing_highs, swing_lows)
    sh_px = sh_ts = sl_px = sl_ts = None
    for typ, level, ts in zip(hl_order, level_order, idx_order):
        if typ == 1:
            sh_px, sh_ts = level, ts
        else:
            sl_px, sl_ts = level, ts
    if sh_ts is None or sl_ts is None:
        return None

    after_sh = df[df.index > sh_ts]
    after_sl = df[df.index > sl_ts]
    range_high = max(float(sh_px), float(after_sh["high"].max()) if len(after_sh) else float(sh_px))
    range_low = min(float(sl_px), float(after_sl["low"].min()) if len(after_sl) else float(sl_px))

    # Design sanity invariant (degenerate geometry -> treat as fallback, loudly)
    if not (range_low <= range_high):
        print(f"  [sanity] degenerate structural range low={range_low} high={range_high}",
              file=sys.stderr)
        return None
    return range_high, range_low, sh_ts, sl_ts


def classify(price: float, range_high: float, range_low: float) -> Tuple[str, float]:
    """Mirror premium_discount.py:74-100 — same formulas, same >= tie-break."""
    size = range_high - range_low
    eq = range_low + size * 0.5
    pct = ((price - range_low) / size * 100) if size > 0 else 50.0
    zone = "premium" if price >= eq else "discount"
    return zone, pct


def simple_atr(df: pd.DataFrame, period: int = 14) -> float:
    h, l, c = df["high"], df["low"], df["close"]
    prev_c = c.shift(1)
    tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    atr = float(tr.tail(period).mean())
    return atr if atr > 0 else float("nan")


def scaled_swing_lookback(tf: str, mode: str) -> int:
    from backend.shared.config.smc_config import get_tf_smc_config, scale_lookback

    cfg = get_tf_smc_config(tf, mode)
    base = cfg.get("structure_swing_lookback", 10)
    return scale_lookback(base, tf)


# ---------------------------------------------------------------------------
# PART A — live grid
# ---------------------------------------------------------------------------
def part_a(symbols: List[str], timeframes: List[str], modes: List[str]) -> Dict:
    from backend.analysis.premium_discount import detect_premium_discount
    from backend.data.adapters.phemex import PhemexAdapter
    from backend.data.ingestion_pipeline import IngestionPipeline

    pipe = IngestionPipeline(PhemexAdapter())
    rows: List[Dict] = []
    for sym in symbols:
        try:
            mtf = pipe.fetch_multi_timeframe(sym, timeframes)
            tf_map = getattr(mtf, "timeframes", mtf)
        except Exception as e:
            print(f"[warn] fetch failed {sym}: {e}", file=sys.stderr)
            continue
        for tf in timeframes:
            df = tf_map.get(tf) if hasattr(tf_map, "get") else None
            if df is None or not len(df):
                continue
            price = float(df["close"].iloc[-1])
            atr = simple_atr(df)
            old = detect_premium_discount(df, lookback=50, current_price=price)
            for mode in modes:
                lb = scaled_swing_lookback(tf, mode)
                rng = structural_dealing_range(df, lb)
                if rng is None:
                    rows.append({"sym": sym, "tf": tf, "mode": mode, "outcome": "fallback",
                                 "lb": lb, "eq_delta_atr": 0.0, "pct_delta": 0.0})
                    continue
                r_high, r_low, _, _ = rng
                new_zone, new_pct = classify(price, r_high, r_low)
                new_eq = r_low + (r_high - r_low) * 0.5
                eq_delta_atr = abs(new_eq - old.equilibrium) / atr if atr == atr else float("nan")
                outcome = "flip" if new_zone != old.current_zone else "same"
                rows.append({"sym": sym, "tf": tf, "mode": mode, "outcome": outcome, "lb": lb,
                             "old_zone": old.current_zone, "new_zone": new_zone,
                             "eq_delta_atr": eq_delta_atr,
                             "pct_delta": abs((new_pct or 0) - (old.zone_percentage or 0))})
    return {"rows": rows}


# ---------------------------------------------------------------------------
# PART B — gate counterfactual on historical gate-clearers
# ---------------------------------------------------------------------------
def _dedup_gate_clearers(signals_glob: str, max_setups: int) -> List[Dict]:
    setups: Dict[Tuple[str, str, str], Dict] = {}
    for path in sorted(glob.glob(signals_glob)):
        sid = os.path.basename(os.path.dirname(path))
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    r = json.loads(line)
                    if not r.get("factors"):
                        continue
                    entry = float(r.get("entry_zone") or 0)
                    if entry <= 0:
                        continue
                    setups[(sid, r.get("symbol"), r.get("direction"))] = {
                        "symbol": r["symbol"], "direction": r["direction"],
                        "entry": entry, "ts": r["timestamp"], "session": sid,
                    }
        except Exception as e:
            print(f"[warn] {path}: {e}", file=sys.stderr)
    out = list(setups.values())
    if len(out) > max_setups:
        print(f"[note] capping Part B at {max_setups} of {len(out)} setups "
              f"(most recent kept)", file=sys.stderr)
        out = sorted(out, key=lambda s: s["ts"])[-max_setups:]
    return out


def part_b(signals_glob: str, max_setups: int) -> Dict:
    from backend.data.adapters.phemex import PhemexAdapter
    from backend.data.ingestion_pipeline import IngestionPipeline

    setups = _dedup_gate_clearers(signals_glob, max_setups)
    if not setups:
        return {"setups": 0, "rows": [], "skipped": 0}

    pipe = IngestionPipeline(PhemexAdapter())
    df_cache: Dict[str, Optional[pd.DataFrame]] = {}

    def get_htf_df(sym_raw: str) -> Optional[pd.DataFrame]:
        if sym_raw in df_cache:
            return df_cache[sym_raw]
        sym = sym_raw if ":" in sym_raw else f"{sym_raw}:USDT"
        df = None
        try:
            mtf = pipe.fetch_multi_timeframe(sym, [GATE_HTF])
            tf_map = getattr(mtf, "timeframes", mtf)
            df = tf_map.get(GATE_HTF) if hasattr(tf_map, "get") else None
        except Exception as e:
            print(f"[warn] HTF fetch failed {sym}: {e}", file=sys.stderr)
        df_cache[sym_raw] = df
        return df

    rows: List[Dict] = []
    skipped = 0
    # Bot sessions run STEALTH (hard boundary) — swing lookback config follows it.
    lb = scaled_swing_lookback(GATE_HTF, "stealth")
    for s in setups:
        # Defensive: replay only directions the gate predicate is defined for.
        # (Today 0 qualifying rows are non-LONG/SHORT; guard is future-proofing.)
        if s["direction"] not in ("LONG", "SHORT"):
            print(f"[warn] Part B skipping unknown direction {s['direction']!r} "
                  f"({s['symbol']} {s['session']})", file=sys.stderr)
            skipped += 1
            continue
        df = get_htf_df(s["symbol"])
        if df is None or not len(df):
            skipped += 1
            continue
        ts = pd.Timestamp(s["ts"])
        idx = df.index
        if getattr(idx, "tz", None) is not None and ts.tzinfo is None:
            ts = ts.tz_localize(idx.tz)
        elif getattr(idx, "tz", None) is None and ts.tzinfo is not None:
            ts = ts.tz_localize(None)
        hist = df[df.index <= ts]
        if len(hist) < 60:  # need window-50 + headroom
            skipped += 1
            continue

        entry, is_long = s["entry"], s["direction"] == "LONG"
        # OLD: window EQ (mirror of detect_premium_discount tail(50))
        recent = hist.tail(50)
        old_eq = float(recent["low"].min()) + (float(recent["high"].max()) - float(recent["low"].min())) * 0.5
        # NEW: structural EQ
        rng = structural_dealing_range(hist, lb)
        if rng is None:
            rows.append({**s, "outcome": "fallback"})
            continue
        r_high, r_low, _, _ = rng
        new_eq = r_low + (r_high - r_low) * 0.5
        atr = simple_atr(hist)

        # Gate step-5 predicate, both ways (scorer.py:1138-1140 verbatim semantics)
        in_opt_old = (is_long and entry <= old_eq) or (not is_long and entry >= old_eq)
        in_opt_new = (is_long and entry <= new_eq) or (not is_long and entry >= new_eq)
        rows.append({**s, "outcome": "flip" if in_opt_old != in_opt_new else "same",
                     "in_opt_old": in_opt_old, "in_opt_new": in_opt_new,
                     "eq_delta_atr": abs(new_eq - old_eq) / atr if atr == atr else float("nan")})
    # Full mass identity: every deduped setup is either evaluated or skipped-loud.
    assert len(rows) + skipped == len(setups), (
        f"PART B setup conservation: rows={len(rows)} + skipped={skipped} != {len(setups)}"
    )
    return {"setups": len(setups), "rows": rows, "skipped": skipped}


# ---------------------------------------------------------------------------
# Report — summary first, structured detail second (CLAUDE.md §12)
# ---------------------------------------------------------------------------
def _pct(n: int, d: int) -> str:
    return f"{100.0 * n / d:.0f}%" if d else "n/a"


def report(a: Dict, b: Optional[Dict]) -> int:
    rows = a["rows"]
    total = len(rows)
    n_flip = sum(1 for r in rows if r["outcome"] == "flip")
    n_same = sum(1 for r in rows if r["outcome"] == "same")
    n_fb = sum(1 for r in rows if r["outcome"] == "fallback")
    # Mass conservation — every grid cell accounted for exactly once
    assert n_flip + n_same + n_fb == total, (
        f"PART A mass conservation: {n_flip}+{n_same}+{n_fb} != {total}"
    )

    print("PHASE 5-PRE — P/D ANCHOR DISAGREEMENT (window-50 vs structure-anchored)")
    print(f"  PART A grid cells: {total}  |  flip {n_flip} ({_pct(n_flip, total)})  "
          f"same {n_same}  fallback {n_fb} ({_pct(n_fb, total)})")
    if b is not None:
        bres = [r for r in b["rows"]]
        bf = sum(1 for r in bres if r["outcome"] == "flip")
        bfb = sum(1 for r in bres if r["outcome"] == "fallback")
        bn = len(bres)
        assert bf + bfb + sum(1 for r in bres if r["outcome"] == "same") == bn, \
            "PART B mass conservation violated"
        print(f"  PART B gate-clearers: {b['setups']} distinct (skipped {b['skipped']} "
              f"no-data) -> in_optimal_zone FLIPS {bf}/{bn} ({_pct(bf, bn)})  "
              f"[UPPER BOUND on -40 flips]  fallback {bfb}")
    print()

    print("=" * 86)
    print("PART A — per TF (all modes pooled)")
    print("-" * 86)
    by_tf: Dict[str, Counter] = defaultdict(Counter)
    eq_by_tf: Dict[str, List[float]] = defaultdict(list)
    for r in rows:
        by_tf[r["tf"]][r["outcome"]] += 1
        if r["outcome"] != "fallback" and r["eq_delta_atr"] == r["eq_delta_atr"]:
            eq_by_tf[r["tf"]].append(r["eq_delta_atr"])
    print(f"{'tf':<6}{'cells':>6}{'flip':>7}{'fallback':>10}{'median eqΔ(ATR)':>17}{'max eqΔ(ATR)':>14}")
    for tf in sorted(by_tf, key=lambda t: {"15m": 0, "1h": 1, "4h": 2, "1d": 3}.get(t, 9)):
        c = by_tf[tf]
        n = sum(c.values())
        eqs = sorted(eq_by_tf[tf])
        med = eqs[len(eqs) // 2] if eqs else float("nan")
        mx = eqs[-1] if eqs else float("nan")
        print(f"{tf:<6}{n:>6}{_pct(c['flip'], n):>7}{_pct(c['fallback'], n):>10}"
              f"{med:>17.2f}{mx:>14.2f}")

    print("-" * 86)
    print("PART A — per mode (all TFs pooled; lookback differs by mode config)")
    by_mode: Dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        by_mode[r["mode"]][r["outcome"]] += 1
    for mode in MODES:
        if mode not in by_mode:
            continue
        c = by_mode[mode]
        n = sum(c.values())
        print(f"  {mode:<10} cells {n:>4}  flip {_pct(c['flip'], n):>5}  "
              f"fallback {_pct(c['fallback'], n):>5}")

    flips = [r for r in rows if r["outcome"] == "flip"]
    if flips:
        print("-" * 86)
        print("PART A — flipped cells (raw)")
        for r in flips:
            print(f"  {r['sym']:<16}{r['tf']:<5}{r['mode']:<10}"
                  f"{r['old_zone']:>9} -> {r['new_zone']:<9} eqΔ={r['eq_delta_atr']:.2f} ATR")

    if b is not None and b["rows"]:
        print("=" * 86)
        print(f"PART B — gate counterfactual on {GATE_HTF} (gate HTF; stealth swing config)")
        print("-" * 86)
        for r in b["rows"]:
            if r["outcome"] == "flip":
                print(f"  FLIP  {r['session'][:12]:<14}{r['symbol']:<14}{r['direction']:<6}"
                      f"entry={r['entry']:<12g} in_opt {r['in_opt_old']} -> {r['in_opt_new']}"
                      f"  eqΔ={r['eq_delta_atr']:.2f} ATR")
        n_show = sum(1 for r in b["rows"] if r["outcome"] == "flip")
        if not n_show:
            print("  (no flips)")
    print()
    print("NOTE: Part B flip rate is an UPPER BOUND on PremiumDiscount_VIOLATION (-40)")
    print("flips — the -40 additionally requires min_aligned_distance > 1.0 ATR, which")
    print("cannot be reconstructed from signals.jsonl. Q5 sign-off uses these numbers.")
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Phase 5-pre P/D anchor disagreement (read-only).")
    ap.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    ap.add_argument("--timeframes", nargs="+", default=DEFAULT_TFS)
    ap.add_argument("--modes", nargs="+", default=list(MODES), choices=list(MODES))
    ap.add_argument("--signals-glob", default="logs/paper_trading/session_*/signals.jsonl")
    ap.add_argument("--max-setups", type=int, default=200)
    ap.add_argument("--skip-part-b", action="store_true")
    args = ap.parse_args()

    a = part_a(args.symbols, args.timeframes, args.modes)
    b = None if args.skip_part_b else part_b(args.signals_glob, args.max_setups)
    return report(a, b)


if __name__ == "__main__":
    raise SystemExit(main())
