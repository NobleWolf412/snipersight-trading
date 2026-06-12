"""
diag_ob_source_composition.py - measure-first diagnostic for OB source-tagging fix T3-3.

OPERATOR QUESTION (2026-06-09): smc_service.py:509-530 merges THREE OB detectors into
one undifferentiated List[OrderBlock] - rejection-wick (detect_order_blocks), structural
(detect_order_blocks_structural), and BOS-linked (detect_obs_from_bos, "THIS IS THE
CORRECT SMC METHOD"). Before tagging+demoting wick OBs (operator decision 2026-06-09:
keep, tag, confluence-only), measure what the merged pool is actually made of:

  COMPOSITION : per-source counts, per timeframe and per mode, pre- and post-
                filter_obs_by_mode (Gate 2) - who survives to the scorer?
  WRONG-COLOR : fraction of wick-source OBs whose origin candle color contradicts the
                SMC definition (bullish OB origin should be a RED candle, bearish GREEN
                - the doctrine detect_obs_from_bos encodes at order_blocks.py:817-819).
                Audit claim under test: wick detector never checks color.
  DUAL-TAG    : wick-source candles tagged BOTH bullish and bearish at the same
                timestamp (empirically reproduced in the audit; frequency unknown).
  AGREEMENT   : fraction of wick OBs overlapping (>=50% of the wick zone) a same-
                direction structure-confirmed OB - the population that earns the
                planned "score higher when they agree" bonus instead of standalone
                weight. This number predicts how much signal the demotion keeps.

FIDELITY: uses the real SMCDetectionService per mode for config construction
(get_tf_smc_config -> _create_tf_smc_config) and runs the detectors in the exact
service order - structure breaks FIRST (BOS-ordering standing fix, smc_service.py:496),
then wick, structural, BOS-linked. Source attribution is by call site, locally tagged;
no model or engine changes.

READ-ONLY. No engine files modified. No thresholds proposed - numbers only.

USAGE
    python -m backend.diagnostics.diag_ob_source_composition --synthetic
    python -m backend.diagnostics.diag_ob_source_composition --csv data/btc_1h.csv --timeframe 1h
    python -m backend.diagnostics.diag_ob_source_composition --csv a_15m.csv b_4h.csv --timeframe 15m 4h
    python -m backend.diagnostics.diag_ob_source_composition --live BTC/USDT:USDT ETH/USDT:USDT
    # --modes overwatch stealth strike surgical   (default: all four)

CSV format: timestamp,open,high,low,close,volume (timestamp ISO8601 or epoch ms).
--live uses backend.data.ingestion_pipeline and requires exchange connectivity.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

MODES = ("overwatch", "stealth", "strike", "surgical")
SOURCES = ("bos", "structural", "rejection_wick")


# ---------------------------------------------------------------------------
# Detection - mirrors smc_service._detect_timeframe_patterns OB section verbatim,
# with per-call-site source tags. Order is load-bearing (BOS-ordering standing fix).
# ---------------------------------------------------------------------------
def detect_tagged(df: pd.DataFrame, timeframe: str, mode: str) -> List[Tuple[str, object]]:
    from backend.services.smc_service import SMCDetectionService
    from backend.shared.config.smc_config import get_tf_smc_config
    from backend.strategy.smc.bos_choch import (
        _detect_swing_highs,
        _detect_swing_lows,
        detect_structural_breaks,
    )
    from backend.strategy.smc.order_blocks import (
        detect_obs_from_bos,
        detect_order_blocks,
        detect_order_blocks_structural,
    )

    svc = SMCDetectionService(mode=mode)
    tf_config = get_tf_smc_config(timeframe, svc._mode)
    tf_smc_config = svc._create_tf_smc_config(tf_config)

    swing_lookback = tf_config.get(
        "structure_swing_lookback", getattr(svc._smc_config, "structure_swing_lookback", 10)
    )
    swing_highs = _detect_swing_highs(df, swing_lookback)
    swing_lows = _detect_swing_lows(df, swing_lookback)

    # 1) Structure breaks FIRST - detect_obs_from_bos depends on them (standing fix).
    breaks = detect_structural_breaks(df, tf_smc_config, mode_profile=svc._mode_profile)

    tagged: List[Tuple[str, object]] = []
    # 2) rejection-wick / engulfing detector
    try:
        tagged += [("rejection_wick", ob) for ob in detect_order_blocks(df, tf_smc_config)]
    except Exception as e:
        print(f"  [warn] wick detector failed on {timeframe}/{mode}: {e}", file=sys.stderr)
    # 3) structural detector
    try:
        tagged += [
            ("structural", ob)
            for ob in detect_order_blocks_structural(df, swing_highs, swing_lows, tf_smc_config)
        ]
    except Exception as e:
        print(f"  [warn] structural detector failed on {timeframe}/{mode}: {e}", file=sys.stderr)
    # 4) BOS-linked (the correct method)
    try:
        tagged += [("bos", ob) for ob in detect_obs_from_bos(df, breaks, tf_smc_config)]
    except Exception as e:
        print(f"  [warn] bos detector failed on {timeframe}/{mode}: {e}", file=sys.stderr)
    return tagged


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def candle_color(df: pd.DataFrame, ts) -> Optional[str]:
    try:
        row = df.loc[ts]
    except KeyError:
        return None
    if isinstance(row, pd.DataFrame):
        row = row.iloc[0]
    if row["close"] > row["open"]:
        return "green"
    if row["close"] < row["open"]:
        return "red"
    return "doji"


def is_wrong_color(direction: str, color: Optional[str]) -> Optional[bool]:
    # Correct SMC origin: bullish OB = last RED candle; bearish OB = last GREEN candle.
    if color in (None, "doji"):
        return None
    return (direction == "bullish" and color == "green") or (
        direction == "bearish" and color == "red"
    )


def zone_overlap_frac(a_low, a_high, b_low, b_high) -> float:
    lo, hi = max(a_low, b_low), min(a_high, b_high)
    if hi <= lo or a_high <= a_low:
        return 0.0
    return (hi - lo) / (a_high - a_low)


def analyze(
    tagged: List[Tuple[str, object]], df: pd.DataFrame, timeframe: str, mode: str
) -> Dict:
    from backend.strategy.smc.order_blocks import filter_obs_by_mode
    from backend.services.smc_service import SMCDetectionService

    counts = Counter(src for src, _ in tagged)

    wick = [ob for src, ob in tagged if src == "rejection_wick"]
    confirmed = [ob for src, ob in tagged if src in ("bos", "structural")]

    # Wrong-color and dual-tag on the wick population.
    # Split by 4C production source field (rejection_wick vs engulfing): the color
    # gate added in 4C only applies to the rejection_wick branch; engulfing OBs
    # deliberately bypass it (different pattern, different color doctrine). The
    # blended rate therefore UNDERSTATES the gate's effect — per-source isolates
    # whether the color gate is actually firing (rejection_wick should be ~0%).
    wrong = total_colored = 0
    wrong_by_source: Dict[str, List[int]] = defaultdict(lambda: [0, 0])  # src -> [wrong, colored]
    for ob in wick:
        wc = is_wrong_color(ob.direction, candle_color(df, pd.Timestamp(ob.timestamp)))
        if wc is not None:
            total_colored += 1
            wrong += int(wc)
            src_field = str(getattr(ob, "source", "?"))
            wrong_by_source[src_field][1] += 1
            wrong_by_source[src_field][0] += int(wc)
    by_ts = defaultdict(set)
    for ob in wick:
        by_ts[ob.timestamp].add(ob.direction)
    dual = sum(1 for dirs in by_ts.values() if len(dirs) == 2)

    # Agreement: wick zone >=50% inside a same-direction confirmed zone
    agree = 0
    for w in wick:
        if any(
            c.direction == w.direction
            and zone_overlap_frac(w.low, w.high, c.low, c.high) >= 0.5
            for c in confirmed
        ):
            agree += 1

    # Gate-2 survivors (filter_obs_by_mode) - who actually reaches the scorer
    profile = SMCDetectionService(mode=mode)._mode_profile
    id_to_src = {id(ob): src for src, ob in tagged}
    survivors = filter_obs_by_mode(
        [ob for _, ob in tagged], mode_profile=profile, current_time=df.index[-1].to_pydatetime()
    )
    surv_counts = Counter(id_to_src.get(id(ob), "?") for ob in survivors)

    return {
        "timeframe": timeframe,
        "mode": mode,
        "counts": counts,
        "wick_total": len(wick),
        "wick_colored": total_colored,
        "wick_wrong_color": wrong,
        "wick_dual_tag_ts": dual,
        "wick_agreeing": agree,
        "wick_wrong_by_source": dict(wrong_by_source),
        "survivors": surv_counts,
        "gate2_profile": profile,
    }


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    ts = df["timestamp"]
    df.index = pd.to_datetime(ts, unit="ms") if np.issubdtype(ts.dtype, np.number) else pd.to_datetime(ts)
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def synthetic_df(timeframe: str = "1h", n: int = 400, seed: int = 11) -> pd.DataFrame:
    """Continuous-market walk (open == prev close) with periodic impulses so every
    detector has material: trends, displacement legs, and wick rejections."""
    rng = np.random.default_rng(seed)
    freq = {"5m": "5min", "15m": "15min", "1h": "1h", "4h": "4h", "1d": "1D"}.get(timeframe, "1h")
    idx = pd.date_range("2025-06-01", periods=n, freq=freq)
    o, h, l, c, v = [100.0], [], [], [], []
    for i in range(n):
        op = o[-1]
        drift = 0.4 if (i // 60) % 2 == 0 else -0.4  # alternating regimes
        cl = op + rng.normal(drift * 0.2, 0.6)
        if i % 47 == 30:
            cl = op + 3.5 * (1 if drift > 0 else -1)  # displacement impulse
        wick = abs(rng.normal(0, 0.35))
        if i % 31 == 12:
            wick += 1.8  # forced rejection wick
        h.append(max(op, cl) + wick * 0.5)
        l.append(min(op, cl) - wick)
        c.append(cl)
        v.append(1000 * (3.0 if i % 47 == 30 else 1.0) * (1 + abs(rng.normal(0, 0.2))))
        o.append(cl)
    return pd.DataFrame(
        {"open": o[:-1], "high": h, "low": l, "close": c, "volume": v}, index=idx
    )


def load_live(symbols: List[str], timeframes: List[str]) -> Dict[str, Dict[str, pd.DataFrame]]:
    from backend.data.ingestion_pipeline import IngestionPipeline  # type: ignore
    from backend.data.adapters.phemex import PhemexAdapter  # type: ignore

    pipe = IngestionPipeline(PhemexAdapter())
    out: Dict[str, Dict[str, pd.DataFrame]] = {}
    for sym in symbols:
        mtf = pipe.fetch_multi_timeframe(sym, timeframes)
        out[sym] = getattr(mtf, "timeframes", mtf)
    return out


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def report(results: List[Dict]) -> int:
    if not results:
        print("No detection results - nothing to report.")
        return 1
    print("=" * 92)
    print("OB SOURCE COMPOSITION  (measure-first for T3-3: tag + demote rejection-wick OBs)")
    print("sources: bos = detect_obs_from_bos (correct) | structural | rejection_wick")
    print("=" * 92)
    print(f"{'dataset':<22}{'tf':<5}{'mode':<10}{'bos':>5}{'struct':>7}{'wick':>6}"
          f"{'wrongClr':>9}{'dualTag':>8}{'agree':>7}{'gate2 surv (b/s/w)':>20}")
    print("-" * 92)

    agg = Counter()
    agg_wick = agg_colored = agg_wrong = agg_dual = agg_agree = 0
    surv_agg = Counter()
    wrong_by_source_agg: Dict[str, List[int]] = defaultdict(lambda: [0, 0])  # src -> [wrong, colored]
    for r in results:
        cnt, sv = r["counts"], r["survivors"]
        wcp = (f"{100.0 * r['wick_wrong_color'] / r['wick_colored']:.0f}%"
               if r["wick_colored"] else "n/a")
        agp = (f"{100.0 * r['wick_agreeing'] / r['wick_total']:.0f}%" if r["wick_total"] else "n/a")
        print(f"{r['dataset'][:21]:<22}{r['timeframe']:<5}{r['mode']:<10}"
              f"{cnt.get('bos', 0):>5}{cnt.get('structural', 0):>7}{cnt.get('rejection_wick', 0):>6}"
              f"{wcp:>9}{r['wick_dual_tag_ts']:>8}{agp:>7}"
              f"{sv.get('bos', 0):>9}/{sv.get('structural', 0)}/{sv.get('rejection_wick', 0):<6}")
        agg.update(cnt)
        agg_wick += r["wick_total"]; agg_colored += r["wick_colored"]
        agg_wrong += r["wick_wrong_color"]; agg_dual += r["wick_dual_tag_ts"]
        agg_agree += r["wick_agreeing"]
        surv_agg.update(sv)
        for src_field, (w, c) in r.get("wick_wrong_by_source", {}).items():
            wrong_by_source_agg[src_field][0] += w
            wrong_by_source_agg[src_field][1] += c

    tot = sum(agg.values()) or 1
    print("-" * 92)
    print(f"pool composition:        bos {agg.get('bos',0)} ({100*agg.get('bos',0)/tot:.0f}%)  "
          f"structural {agg.get('structural',0)} ({100*agg.get('structural',0)/tot:.0f}%)  "
          f"rejection_wick {agg.get('rejection_wick',0)} ({100*agg.get('rejection_wick',0)/tot:.0f}%)")
    if agg_colored:
        print(f"wick wrong-color rate:   {agg_wrong}/{agg_colored} "
              f"({100*agg_wrong/agg_colored:.0f}%)   <-- blended (rejection_wick + engulfing)")
    if wrong_by_source_agg:
        parts = []
        for src_field in sorted(wrong_by_source_agg):
            w, c = wrong_by_source_agg[src_field]
            parts.append(f"{src_field} {w}/{c} ({100*w/c:.0f}%)" if c else f"{src_field} 0/0 (n/a)")
        print(f"  by 4C source:          " + "   ".join(parts))
        print(f"                         ^ rejection_wick ~0% = 4C color gate firing; "
              f"engulfing bypasses gate by design")
    print(f"wick dual-tag candles:   {agg_dual}")
    if agg_wick:
        print(f"wick agreement rate:     {agg_agree}/{agg_wick} ({100*agg_agree/agg_wick:.0f}%)"
              f"   <-- population keeping value as confluence bonus")
    stot = sum(surv_agg.values()) or 1
    print(f"Gate-2 survivor mix:     bos {100*surv_agg.get('bos',0)/stot:.0f}%  "
          f"structural {100*surv_agg.get('structural',0)/stot:.0f}%  "
          f"wick {100*surv_agg.get('rejection_wick',0)/stot:.0f}%   "
          f"<-- what the scorer currently sees, anonymized")
    print()
    print("NOTE: high wick share + nonzero wrong-color confirms the conflation defect; "
          "high agreement rate means the planned demotion preserves most wick signal "
          "as confirmation rather than deleting it.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Per-source OB composition (read-only).")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--synthetic", action="store_true")
    src.add_argument("--csv", nargs="+", metavar="FILE")
    src.add_argument("--live", nargs="+", metavar="SYMBOL")
    ap.add_argument("--timeframe", nargs="+", default=["1h"],
                    help="timeframe per --csv file (or list for --live/--synthetic)")
    ap.add_argument("--modes", nargs="+", default=list(MODES), choices=list(MODES))
    args = ap.parse_args()

    datasets: List[Tuple[str, str, pd.DataFrame]] = []  # (label, timeframe, df)
    if args.synthetic:
        for tf in args.timeframe:
            datasets.append((f"synthetic-{tf}", tf, synthetic_df(tf)))
    elif args.csv:
        tfs = args.timeframe * len(args.csv) if len(args.timeframe) == 1 else args.timeframe
        if len(tfs) < len(args.csv):
            ap.error("--timeframe count must be 1 or match --csv count")
        for path, tf in zip(args.csv, tfs):
            datasets.append((path.split("/")[-1], tf, load_csv(path)))
    else:
        live = load_live(args.live, args.timeframe)
        for sym, tf_map in live.items():
            for tf, df in tf_map.items():
                if tf in args.timeframe and df is not None and len(df):
                    datasets.append((sym, tf, df))

    results = []
    for label, tf, df in datasets:
        for mode in args.modes:
            try:
                tagged = detect_tagged(df, tf, mode)
            except Exception as e:
                print(f"[warn] detection failed for {label}/{tf}/{mode}: {e}", file=sys.stderr)
                continue
            r = analyze(tagged, df, tf, mode)
            r["dataset"] = label
            results.append(r)
    return report(results)


if __name__ == "__main__":
    raise SystemExit(main())
