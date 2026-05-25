"""
SMC Detector Per-Symbol Diagnostic
===================================
Answers: why does PEPE/USDT show 100% miss on Order Block / FVG / Liquidity Sweep /
HTF Composite across 220+ cycles while majors show clean detection?

Hypothesis the operator wanted tested:
  - Is PEPE's SMC detector returning empty because the symbol's micro-price scale
    (~$0.0000XX) trips a hardcoded threshold in OB/FVG/Sweep helpers?
  - Or does PEPE genuinely have no structure right now and the strategy is
    correctly refusing?

Method:
  1. Fetch live OHLCV for PEPE/USDT and one or more control symbols across all
     STEALTH timeframes (1d, 4h, 1h, 15m, 5m) from the Phemex adapter.
  2. Run SMCDetectionService.detect() configured in STEALTH mode.
  3. Print per-symbol per-TF detection counts (OB by grade, FVG, BOS, sweep,
     equal highs/lows). A symbol returning all zeros across all TFs while a
     control symbol returns >0 counts is the smoking gun.

Output: paste-friendly summary first, per-TF table second, raw counts last.

Usage:
    python -m backend.diagnostics.smc_detector_per_symbol_diagnostic
    python -m backend.diagnostics.smc_detector_per_symbol_diagnostic PEPE/USDT WIF/USDT BNB/USDT

Exit 0 if PEPE's detection matches controls within tolerance; exit 1 if PEPE is
structurally a 0-detection outlier (= bug class symbol-scale-dependent detector).

Per CLAUDE.md §11 silent-bug surfacing + §12 paste-friendly diagnostics.
"""

from __future__ import annotations

import sys
from typing import Dict, List, Tuple

import pandas as pd

from backend.data.adapters.phemex import PhemexAdapter
from backend.services.smc_service import SMCDetectionService
from backend.shared.models.data import MultiTimeframeData
from backend.strategy.confluence.scorer import (
    _score_order_blocks_incremental,
    _score_fvgs_incremental,
    _score_liquidity_sweeps_incremental,
    _score_market_structure_incremental,
)


STEALTH_TFS = ("1d", "4h", "1h", "15m", "5m")
DEFAULT_SYMBOLS = ("PEPE/USDT", "WIF/USDT", "BNB/USDT", "ADA/USDT")

CANDLES_PER_TF = {
    "1d": 200,
    "4h": 300,
    "1h": 400,
    "15m": 500,
    "5m": 500,
}


def _fetch_multi_tf(adapter: PhemexAdapter, symbol: str) -> Tuple[MultiTimeframeData, float, Dict[str, int]]:
    """Fetch all STEALTH TFs for a symbol. Returns (mtf, current_price, candle_counts)."""
    tf_data: Dict[str, pd.DataFrame] = {}
    counts: Dict[str, int] = {}
    for tf in STEALTH_TFS:
        df = adapter.fetch_ohlcv(symbol, tf, limit=CANDLES_PER_TF[tf])
        if df is not None and not df.empty:
            # MultiTimeframeData requires `timestamp` as a column; SMC detector
            # promotes it to DatetimeIndex internally (see smc_service.detect()).
            tf_data[tf] = df
            counts[tf] = len(df)
        else:
            tf_data[tf] = pd.DataFrame()
            counts[tf] = 0

    current_price = 0.0
    # Use the latest 5m close as the spot reference, fall back to 15m, 1h
    for tf in ("5m", "15m", "1h"):
        if tf in tf_data and not tf_data[tf].empty:
            current_price = float(tf_data[tf]["close"].iloc[-1])
            break

    mtf = MultiTimeframeData(symbol=symbol, timeframes=tf_data)
    return mtf, current_price, counts


def _count_per_tf(items, attr: str = "timeframe") -> Dict[str, int]:
    """Count items by timeframe attribute."""
    out: Dict[str, int] = {}
    for it in items:
        tf = (getattr(it, attr, None) or "?").lower()
        out[tf] = out.get(tf, 0) + 1
    return out


def _count_by_grade(items) -> Dict[str, int]:
    out: Dict[str, int] = {"A": 0, "B": 0, "C": 0, "?": 0}
    for it in items:
        g = getattr(it, "grade", None) or "?"
        out[g] = out.get(g, 0) + 1
    return out


def _count_by_direction(items) -> Dict[str, int]:
    out: Dict[str, int] = {"bullish": 0, "bearish": 0, "?": 0}
    for it in items:
        d = getattr(it, "direction", None) or "?"
        out[d] = out.get(d, 0) + 1
    return out


def _scan_one(adapter: PhemexAdapter, smc: SMCDetectionService, symbol: str) -> Dict:
    print(f"\n  Fetching candles for {symbol}…")
    mtf, current_price, counts = _fetch_multi_tf(adapter, symbol)
    print(f"    spot ≈ {current_price:.12f}".rstrip("0").rstrip(".") + f"   candle counts: {counts}")

    snapshot = smc.detect(mtf, current_price)

    # Score each SMC primitive in BOTH directions. If a symbol detects N OBs
    # but all are bearish, the LONG scorer returns 0 — `convergence_missing`
    # then logs "Order Block" as missing for LONG, even though detection ran
    # fine. This pair (long_score / short_score) is the key column.
    ob_long  = _score_order_blocks_incremental(snapshot.order_blocks, "LONG")
    ob_short = _score_order_blocks_incremental(snapshot.order_blocks, "SHORT")
    fvg_long  = _score_fvgs_incremental(snapshot.fvgs, "LONG")
    fvg_short = _score_fvgs_incremental(snapshot.fvgs, "SHORT")
    sw_long  = _score_liquidity_sweeps_incremental(snapshot.liquidity_sweeps, "LONG")
    sw_short = _score_liquidity_sweeps_incremental(snapshot.liquidity_sweeps, "SHORT")
    ms_long  = _score_market_structure_incremental(snapshot, "LONG")
    ms_short = _score_market_structure_incremental(snapshot, "SHORT")

    result = {
        "symbol": symbol,
        "spot": current_price,
        "candle_counts": counts,
        "ob_total": len(snapshot.order_blocks),
        "ob_by_grade": _count_by_grade(snapshot.order_blocks),
        "ob_by_direction": _count_by_direction(snapshot.order_blocks),
        "ob_per_tf": _count_per_tf(snapshot.order_blocks),
        "fvg_total": len(snapshot.fvgs),
        "fvg_by_direction": _count_by_direction(snapshot.fvgs),
        "fvg_per_tf": _count_per_tf(snapshot.fvgs),
        "bos_total": len(snapshot.structural_breaks),
        "bos_by_direction": _count_by_direction(snapshot.structural_breaks),
        "bos_per_tf": _count_per_tf(snapshot.structural_breaks),
        "sweep_total": len(snapshot.liquidity_sweeps),
        "sweep_by_direction": _count_by_direction(snapshot.liquidity_sweeps),
        "sweep_per_tf": _count_per_tf(snapshot.liquidity_sweeps),
        "eqh_total": len(snapshot.equal_highs),
        "eql_total": len(snapshot.equal_lows),
        "ob_score_long":   ob_long.get("score", 0.0),
        "ob_score_short":  ob_short.get("score", 0.0),
        "fvg_score_long":  fvg_long.get("score", 0.0),
        "fvg_score_short": fvg_short.get("score", 0.0),
        "sw_score_long":   sw_long.get("score", 0.0),
        "sw_score_short":  sw_short.get("score", 0.0),
        "ms_score_long":   ms_long.get("score", 0.0),
        "ms_score_short":  ms_short.get("score", 0.0),
    }
    return result


def _print_summary(results: List[Dict]) -> None:
    print("\n" + "=" * 78)
    print(f"  {'symbol':14}{'OB':>5}{'FVG':>5}{'BOS':>5}{'Swp':>5}{'EQH':>5}{'EQL':>5}   spot")
    print("  " + "─" * 76)
    for r in results:
        spot = r["spot"]
        spot_s = f"{spot:.12f}".rstrip("0").rstrip(".") if spot else "?"
        print(
            f"  {r['symbol']:14}"
            f"{r['ob_total']:>5}{r['fvg_total']:>5}{r['bos_total']:>5}"
            f"{r['sweep_total']:>5}{r['eqh_total']:>5}{r['eql_total']:>5}   {spot_s}"
        )


def _print_detail(results: List[Dict]) -> None:
    print("\n  Per-TF detection table (rows = symbols, cols = TFs):")
    for kind in ("ob_per_tf", "fvg_per_tf", "bos_per_tf", "sweep_per_tf"):
        label = {"ob_per_tf": "Order Blocks", "fvg_per_tf": "Fair Value Gaps",
                 "bos_per_tf": "BOS", "sweep_per_tf": "Liquidity Sweeps"}[kind]
        print(f"\n    {label}:")
        header = f"      {'symbol':14}" + "".join(f"{tf:>6}" for tf in STEALTH_TFS) + "  TOTAL"
        print(header)
        for r in results:
            row = f"      {r['symbol']:14}"
            tot = 0
            for tf in STEALTH_TFS:
                n = r[kind].get(tf, 0)
                row += f"{n:>6d}"
                tot += n
            row += f"  {tot:>5d}"
            print(row)

    # Direction breakdown — the column most likely to explain the "missing factor" mystery.
    print("\n  Direction breakdown (bull / bear / unknown):")
    print(f"      {'symbol':14}{'OB':>16}{'FVG':>16}{'BOS':>16}{'Sweep':>16}")
    for r in results:
        ob = r["ob_by_direction"]
        fv = r["fvg_by_direction"]
        bs = r["bos_by_direction"]
        sw = r["sweep_by_direction"]
        fmt = lambda d: f"{d.get('bullish',0)}/{d.get('bearish',0)}/{d.get('?',0)}"
        print(f"      {r['symbol']:14}{fmt(ob):>16}{fmt(fv):>16}{fmt(bs):>16}{fmt(sw):>16}")

    # Per-direction factor scores — exactly what the scorer sees per direction.
    # A 0/0 column for PEPE means "no aligned OB found in EITHER direction" — that's
    # a detection issue. A 0/X or X/0 means direction-selection picked the wrong side.
    print("\n  Per-direction factor scores (LONG / SHORT) — what the scorer returns:")
    print(f"      {'symbol':14}{'OB':>14}{'FVG':>14}{'Sweep':>14}{'MktStruct':>14}")
    for r in results:
        fmt = lambda a, b: f"{a:.0f}/{b:.0f}"
        ob_s = fmt(r["ob_score_long"],  r["ob_score_short"])
        fv_s = fmt(r["fvg_score_long"], r["fvg_score_short"])
        sw_s = fmt(r["sw_score_long"],  r["sw_score_short"])
        ms_s = fmt(r["ms_score_long"],  r["ms_score_short"])
        print(f"      {r['symbol']:14}{ob_s:>14}{fv_s:>14}{sw_s:>14}{ms_s:>14}")


def _verdict(results: List[Dict]) -> int:
    """Decide pass/fail.

    Mass-conservation-style check: PEPE is the target; if PEPE's total
    detections across the 4 SMC primitives (OB+FVG+BOS+Sweep) is zero AND any
    control symbol has >0, that confirms symbol-specific detector failure.
    """
    pepe = next((r for r in results if r["symbol"] == "PEPE/USDT"), None)
    if pepe is None:
        print("\n  VERDICT: PEPE/USDT was not scanned — cannot conclude.")
        return 0

    pepe_total = pepe["ob_total"] + pepe["fvg_total"] + pepe["bos_total"] + pepe["sweep_total"]
    controls = [r for r in results if r["symbol"] != "PEPE/USDT"]
    control_totals = [(r["symbol"], r["ob_total"] + r["fvg_total"] + r["bos_total"] + r["sweep_total"])
                      for r in controls]

    print("\n  VERDICT:")
    print(f"    PEPE total SMC detections (OB+FVG+BOS+Sweep): {pepe_total}")
    for sym, tot in control_totals:
        print(f"    {sym:14s} total SMC detections: {tot}")

    if pepe_total == 0 and any(tot > 0 for _, tot in control_totals):
        print("\n    ❌ DETECTOR-FAIL SUSPECT: PEPE returns 0 SMC primitives while at least one")
        print("       control symbol returns >0. This matches the session signals.jsonl pattern")
        print("       (PEPE 100% miss on OB/FVG/Sweep). Investigate symbol-scale-dependent")
        print("       threshold logic in:")
        print("       - backend/strategy/smc/order_block.py  (min_displacement_atr, min_wick_ratio)")
        print("       - backend/strategy/smc/fvg.py          (min_gap_atr)")
        print("       - backend/strategy/smc/liquidity.py    (sweep magnitude thresholds)")
        return 1

    if pepe_total > 0:
        print("\n    DETECTORS RETURN >0 FOR PEPE: not a detector-empty bug.")
        print("       The 100% miss in signals.jsonl is therefore downstream of detection.")
        # Direction-aligned scoring is the prime suspect.
        ob_l, ob_s = pepe.get("ob_score_long", 0.0), pepe.get("ob_score_short", 0.0)
        sw_l, sw_s = pepe.get("sw_score_long", 0.0),  pepe.get("sw_score_short", 0.0)
        ms_l, ms_s = pepe.get("ms_score_long", 0.0),  pepe.get("ms_score_short", 0.0)
        if (ob_l == 0 and ob_s > 0) or (sw_l == 0 and sw_s > 0) or (ms_l == 0 and ms_s > 0):
            print("\n    DIRECTION-MISMATCH CONFIRMED: PEPE's detected SMC primitives are aligned")
            print(f"    for SHORT but the bot was evaluating LONG every cycle. Per-factor scores:")
            print(f"      OB    LONG={ob_l:.0f}  SHORT={ob_s:.0f}")
            print(f"      Sweep LONG={sw_l:.0f}  SHORT={sw_s:.0f}")
            print(f"      MktSt LONG={ms_l:.0f}  SHORT={ms_s:.0f}")
            print("\n    The 100% 'missing factor' tag in signals.jsonl is a labeling artifact —")
            print("    factor IS present, it's just aligned for the opposite direction. The real")
            print("    question is: why does the direction-selection at orchestrator.py:1579 keep")
            print("    picking LONG for PEPE when the SMC structure points SHORT?")
            print("    This is a DIRECTION-SHORT-CIRCUIT class issue, not a detector bug.")
        else:
            print("       Likely culprits: grade-filtering, freshness-filtering, or distance-from-")
            print("       spot thresholds in the per-factor scorer rejecting low-grade detections.")
        return 0

    print("\n    🟡 ALL SYMBOLS RETURN 0: detector is universally empty across this snapshot.")
    print("       Likely a transient market-state issue or a global detector bug. Re-run later.")
    return 0


def main(argv: List[str]) -> int:
    symbols = tuple(argv[1:]) if len(argv) > 1 else DEFAULT_SYMBOLS
    print("─" * 78)
    print("  SMC DETECTOR PER-SYMBOL DIAGNOSTIC")
    print(f"  Symbols: {', '.join(symbols)}")
    print(f"  Timeframes: {', '.join(STEALTH_TFS)}")
    print("─" * 78)

    adapter = PhemexAdapter()
    smc = SMCDetectionService(mode="stealth")

    results: List[Dict] = []
    for sym in symbols:
        try:
            results.append(_scan_one(adapter, smc, sym))
        except Exception as exc:
            print(f"  ❌ {sym} failed: {type(exc).__name__}: {exc}")
            import traceback; traceback.print_exc()

    if not results:
        print("\n  No symbols completed.")
        return 1

    _print_summary(results)
    _print_detail(results)
    return _verdict(results)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
