"""
Curate the SniperSight "Master Fixture" for the Lessons library.

Scans available BTC 15m backtest data for 60-bar windows that contain a clean
confluence of the four core SMC primitives:
  - A valid order block (with body close confirmation)
  - A 3-candle FVG within close proximity of the OB
  - An equal-highs/lows cluster swept just before the OB formed
  - Inside or adjacent to an ICT kill zone (London Open / NY AM / NY PM)

Outputs candidate rankings + (on --emit) the chosen window as JSON fixture +
annotation file for the frontend lessons content layer.

Per CLAUDE.md §12: paste-friendly output, supports re-curation, lives in
backend/diagnostics/.

Usage:
    python -m backend.diagnostics.curate_master_fixture --rank
    python -m backend.diagnostics.curate_master_fixture --emit <N>
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import time
from pathlib import Path
from typing import Optional

import pandas as pd

from backend.strategy.smc.order_blocks import detect_order_blocks
from backend.strategy.smc.fvg import detect_fvgs
from backend.strategy.smc.liquidity_sweeps import detect_liquidity_sweeps


CSV_PATH = Path("backend/tests/backtest/backtest_multitimeframe_real.csv")
WINDOW_SIZE = 80  # bot's sweep detector requires 68 bars; 80 gives headroom
WINDOW_STRIDE = 10  # every 10 bars (balance: granularity vs scan time)

# Symbol + timeframe selectable via CLI
DEFAULT_SYMBOL = "BTC/USDT"
DEFAULT_TIMEFRAME = "15m"

TF_BAR_SECONDS = {
    "5m": 5 * 60,
    "15m": 15 * 60,
    "1h": 60 * 60,
    "4h": 4 * 60 * 60,
    "1d": 24 * 60 * 60,
}

# ICT kill zones in UTC (NY ET, EST/EDT difference ignored at first pass).
# Backtest CSV is Oct-Dec 2025; US is on EST (UTC-5) from 2025-11-02 onward.
# Using EST offsets — accept ~1h imprecision for the Oct 11 → Nov 2 window.
KILL_ZONES_UTC = [
    (time(7, 0),  time(10, 0), "london_open"),
    (time(13, 30), time(16, 0), "ny_am"),
    (time(18, 30), time(21, 0), "ny_pm"),
]


def load_ohlcv(symbol: str = DEFAULT_SYMBOL, timeframe: str = DEFAULT_TIMEFRAME) -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH)
    df = df[(df["symbol"] == symbol) & (df["timeframe"] == timeframe)].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[["open", "high", "low", "close", "volume"]].dropna()
    return df


def inside_kill_zone(ts: pd.Timestamp) -> Optional[str]:
    t = ts.time()
    for start, end, name in KILL_ZONES_UTC:
        if start <= t <= end:
            return name
    return None


def _delta_bars(ts_a, ts_b, bar_seconds: int) -> float:
    return (ts_a - ts_b).total_seconds() / bar_seconds


def score_window(
    df_win: pd.DataFrame, bar_seconds: int, require_all_four: bool = False
) -> Optional[dict]:
    """Score a single 80-bar window. Returns None if no OB present.

    Master-Fixture criterion: each lens primitive (OB, FVG, sweep) need only
    exist *somewhere* in the window. Colocation (sweep -> OB -> FVG sequence
    within ~25 bars) is a bonus, not a requirement. The chapters annotate where
    each one is; the chart doesn't need them clustered.
    """
    try:
        obs = detect_order_blocks(df_win)
    except Exception:
        return None
    if not obs:
        return None

    try:
        fvgs = detect_fvgs(df_win)
    except Exception:
        fvgs = []

    try:
        sweeps = detect_liquidity_sweeps(df_win)
    except Exception:
        sweeps = []

    if require_all_four and (not fvgs or not sweeps):
        return None

    # Highest-displacement OB anchors the window
    best_ob = max(obs, key=lambda o: float(getattr(o, "displacement_strength", 0) or 0))
    ob_ts = best_ob.timestamp
    if isinstance(ob_ts, str):
        ob_ts = pd.Timestamp(ob_ts)

    # Find the FVG most-colocated with the OB (prefer same-direction)
    best_fvg = None
    best_fvg_delta = float("inf")
    for fvg in fvgs:
        fvg_ts = fvg.timestamp
        if isinstance(fvg_ts, str):
            fvg_ts = pd.Timestamp(fvg_ts)
        delta = abs(_delta_bars(fvg_ts, ob_ts, bar_seconds))
        same_dir_bonus = 0 if fvg.direction == best_ob.direction else 2
        adjusted = delta + same_dir_bonus
        if adjusted < best_fvg_delta:
            best_fvg_delta = adjusted
            best_fvg = fvg

    # Find the sweep most-colocated with the OB (prefer direction-matching, prefer preceding)
    best_sweep = None
    best_sweep_delta = float("inf")
    for sweep in sweeps:
        sw_ts = sweep.timestamp
        if isinstance(sw_ts, str):
            sw_ts = pd.Timestamp(sw_ts)
        delta = _delta_bars(ob_ts, sw_ts, bar_seconds)
        expected = "low" if best_ob.direction == "bullish" else "high"
        dir_bonus = 0 if sweep.sweep_type == expected else 3
        # Strong preference for sweeps PRECEDING the OB (positive delta)
        time_bonus = 0 if 0 <= delta <= 25 else (5 if delta < 0 else 2)
        adjusted = abs(delta) + dir_bonus + time_bonus
        if adjusted < best_sweep_delta:
            best_sweep_delta = adjusted
            best_sweep = sweep

    kz = inside_kill_zone(ob_ts)

    # Colocation bonus — tight 4-primitive cluster is the gold standard
    colocation_bonus = 0
    if best_fvg is not None and best_fvg_delta <= 5:
        colocation_bonus += 30
    if best_sweep is not None and best_sweep_delta <= 25:
        colocation_bonus += 50

    score = (
        float(getattr(best_ob, "displacement_strength", 0) or 0)
        + (40 if best_fvg else 0)  # presence
        + (60 if best_sweep else 0)
        + colocation_bonus
        + (25 if kz else 0)
        + (25 if getattr(best_ob, "grade", "C") == "A" else 0)
    )

    colocated_fvg = best_fvg
    preceding_sweep = best_sweep

    return {
        "window_start": df_win.index[0].isoformat(),
        "window_end": df_win.index[-1].isoformat(),
        "ob": {
            "timestamp": ob_ts.isoformat(),
            "direction": best_ob.direction,
            "high": float(best_ob.high),
            "low": float(best_ob.low),
            "grade": getattr(best_ob, "grade", None),
            "displacement_strength": float(
                getattr(best_ob, "displacement_strength", 0) or 0
            ),
        },
        "fvg": (
            {
                "timestamp": (pd.Timestamp(colocated_fvg.timestamp)).isoformat()
                if isinstance(colocated_fvg.timestamp, str)
                else colocated_fvg.timestamp.isoformat(),
                "direction": colocated_fvg.direction,
                "top": float(colocated_fvg.top),
                "bottom": float(colocated_fvg.bottom),
            }
            if colocated_fvg
            else None
        ),
        "sweep": (
            {
                "timestamp": (pd.Timestamp(preceding_sweep.timestamp)).isoformat()
                if isinstance(preceding_sweep.timestamp, str)
                else preceding_sweep.timestamp.isoformat(),
                "sweep_type": preceding_sweep.sweep_type,
                "level": float(preceding_sweep.level),
                "confirmation_level": getattr(preceding_sweep, "confirmation_level", None),
            }
            if preceding_sweep
            else None
        ),
        "kill_zone": kz,
        "score": round(score, 2),
    }


def rank_windows(
    df: pd.DataFrame,
    bar_seconds: int,
    max_candidates: int = 10,
    require_all_four: bool = False,
) -> list[dict]:
    results = []
    total_windows = (len(df) - WINDOW_SIZE) // WINDOW_STRIDE
    for i, start in enumerate(range(0, len(df) - WINDOW_SIZE, WINDOW_STRIDE)):
        win = df.iloc[start : start + WINDOW_SIZE]
        result = score_window(
            win, bar_seconds=bar_seconds, require_all_four=require_all_four
        )
        if result:
            results.append(result)
        if i % 50 == 0:
            print(f"  scanned {i}/{total_windows} windows...", file=sys.stderr)
    results.sort(key=lambda r: r["score"], reverse=True)
    # Dedup: same OB timestamp from overlapping windows produces dupes
    seen_ob_ts = set()
    deduped = []
    for r in results:
        key = r["ob"]["timestamp"]
        if key not in seen_ob_ts:
            seen_ob_ts.add(key)
            deduped.append(r)
    return deduped[:max_candidates]


def emit_fixture(
    df: pd.DataFrame, meta: dict, fixture_path: Path, annotations_path: Path
) -> None:
    win = df.loc[meta["window_start"] : meta["window_end"]].copy()

    bars = [
        {
            "t": ts.isoformat(),
            "o": float(row["open"]),
            "h": float(row["high"]),
            "l": float(row["low"]),
            "c": float(row["close"]),
            "v": float(row["volume"]),
        }
        for ts, row in win.iterrows()
    ]

    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(
        json.dumps(
            {
                "symbol": meta.get("_symbol", "BTC/USDT"),
                "timeframe": meta.get("_timeframe", "15m"),
                "source": str(CSV_PATH),
                "window": {
                    "start": meta["window_start"],
                    "end": meta["window_end"],
                    "bar_count": len(bars),
                },
                "bars": bars,
            },
            indent=2,
        )
    )

    annotations_path.write_text(
        json.dumps(
            {
                "ob": meta["ob"],
                "fvg": meta["fvg"],
                "sweep": meta["sweep"],
                "kill_zone": meta["kill_zone"],
                "score": meta["score"],
                "notes": (
                    "Generated by backend/diagnostics/curate_master_fixture.py. "
                    "Lenses (Wyckoff phase, regime band) computed at render time."
                ),
            },
            indent=2,
        )
    )


def _fmt_candidate(i: int, c: dict) -> str:
    ob = c["ob"]
    fvg_str = (
        f"{c['fvg']['direction']:8s} @ {c['fvg']['timestamp'][11:16]}"
        if c["fvg"]
        else "— none colocated"
    )
    sw_str = (
        f"{c['sweep']['sweep_type']:5s} @ {c['sweep']['timestamp'][11:16]}  "
        f"(lvl {c['sweep']['confirmation_level']})"
        if c["sweep"]
        else "— none preceding"
    )
    return (
        f"[{i:2d}] score={c['score']:6.1f}  "
        f"window={c['window_start'][:10]} -> {c['window_end'][:10]}  "
        f"kz={c['kill_zone'] or '-':<11s}\n"
        f"     OB:    {ob['direction']:8s} grade={ob['grade'] or '?'}  "
        f"disp={ob['displacement_strength']:.1f}  "
        f"[{ob['low']:.1f} - {ob['high']:.1f}]\n"
        f"     FVG:   {fvg_str}\n"
        f"     Sweep: {sw_str}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rank", action="store_true", help="Print top candidates")
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL, help="e.g. BTC/USDT ETH/USDT SOL/USDT")
    parser.add_argument("--timeframe", default=DEFAULT_TIMEFRAME, help="5m / 15m / 1h / 4h / 1d")
    parser.add_argument(
        "--require-all-four",
        action="store_true",
        help="Only return candidates with OB + FVG + sweep all present in window",
    )
    parser.add_argument(
        "--emit", type=int, default=None, help="Emit Nth-ranked candidate"
    )
    parser.add_argument(
        "--out-candidates",
        type=Path,
        default=Path("backend/diagnostics/research/lessons/master_fixture_candidates.json"),
    )
    parser.add_argument(
        "--out-fixture",
        type=Path,
        default=Path("src/content/lessons/_fixtures/master-btc.json"),
    )
    parser.add_argument(
        "--out-annotations",
        type=Path,
        default=Path("src/content/lessons/_fixtures/master-btc.annotations.json"),
    )
    args = parser.parse_args()

    df = load_ohlcv(args.symbol, args.timeframe)
    bar_seconds = TF_BAR_SECONDS[args.timeframe]
    print(
        f"Loaded {len(df)} {args.symbol} {args.timeframe} bars "
        f"({df.index[0]} -> {df.index[-1]})",
        file=sys.stderr,
    )

    candidates = rank_windows(
        df, bar_seconds=bar_seconds, require_all_four=args.require_all_four
    )

    args.out_candidates.parent.mkdir(parents=True, exist_ok=True)
    args.out_candidates.write_text(json.dumps(candidates, indent=2))

    # Summary header
    print(f"\nTop {len(candidates)} Master Fixture candidates:\n")
    for i, c in enumerate(candidates):
        print(_fmt_candidate(i, c))
        print()

    if args.emit is not None:
        if args.emit >= len(candidates):
            print(
                f"Index {args.emit} out of range (only {len(candidates)} candidates)",
                file=sys.stderr,
            )
            sys.exit(1)
        meta = candidates[args.emit].copy()
        meta["_symbol"] = args.symbol
        meta["_timeframe"] = args.timeframe
        emit_fixture(df, meta, args.out_fixture, args.out_annotations)
        print(f"Emitted candidate [{args.emit}] →")
        print(f"  fixture:     {args.out_fixture}")
        print(f"  annotations: {args.out_annotations}")


if __name__ == "__main__":
    main()
