"""
Daily ATR%-of-price baseline — calibration data for the regime volatility bands.

Context: RegimeDetector._detect_volatility was bugged to read 5-minute ATR%
(see regime_tf_selection_diagnostic.py); the fix re-points it to the highest
available timeframe (1D in practice). The existing bands (0.8/1.5/2.5/4.0%)
were tuned implicitly for the wrong TF and mislabel daily ranges. This script
samples the ACTUAL distribution of daily ATR-14 %-of-price across BTC + a
basket of alts so the new bands can be set from data, not guessed
(CLAUDE.md §15 — baseline before tuning).

The regime is BTC-driven (global) but the SAME _detect_volatility also serves
per-symbol regime, so the bands must be sane for alts too — hence the basket.

Run:  python -m backend.diagnostics.daily_atr_baseline
"""
from __future__ import annotations

import sys
from statistics import median

BASKET = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "DOGE/USDT"]
TF = "1D"
ATR_PERIOD = 14


def _percentiles(vals, ps):
    s = sorted(vals)
    n = len(s)
    out = {}
    for p in ps:
        if n == 0:
            out[p] = None
            continue
        idx = min(n - 1, max(0, int(round((p / 100.0) * (n - 1)))))
        out[p] = s[idx]
    return out


def main() -> int:
    try:
        from backend.data.adapters.phemex import PhemexAdapter
        from backend.data.ingestion_pipeline import IngestionPipeline
        from backend.indicators.volatility import compute_atr
    except Exception as e:  # pragma: no cover
        print(f"[abort] import failed: {e}")
        return 2

    adapter = PhemexAdapter(testnet=False)
    pipeline = IngestionPipeline(adapter)
    try:
        fetched = pipeline.parallel_fetch(
            symbols=BASKET, timeframes=[TF], limit=500, max_workers=4
        )
    except Exception as e:  # pragma: no cover
        print(f"[abort] fetch failed: {e}")
        return 2

    all_vals = []
    per_symbol = {}
    print(f"=== DAILY ({TF}) ATR-{ATR_PERIOD} %-of-price baseline ===\n")
    print(f"  {'symbol':>10} {'n':>4} {'min':>7} {'p10':>7} {'p50':>7} {'p90':>7} {'max':>7}")
    for sym in BASKET:
        mtf = fetched.get(sym)
        tfmap = getattr(mtf, "timeframes", None) or {}
        # key may be '1d' or '1D' depending on pipeline normalization
        df = None
        for k in (TF, TF.lower(), TF.upper()):
            if k in tfmap:
                df = tfmap[k]
                break
        if df is None or len(df) < ATR_PERIOD + 5 or "close" not in df.columns:
            print(f"  {sym:>10}  no-data")
            continue
        atr = compute_atr(df, period=ATR_PERIOD)
        pct = (atr / df["close"]).mul(100).dropna()
        vals = [float(v) for v in pct.tolist() if v == v]  # drop NaN
        if not vals:
            print(f"  {sym:>10}  empty")
            continue
        per_symbol[sym] = vals
        all_vals.extend(vals)
        q = _percentiles(vals, [0, 10, 50, 90, 100])
        print(
            f"  {sym:>10} {len(vals):>4} {q[0]:>7.2f} {q[10]:>7.2f} {q[50]:>7.2f} {q[90]:>7.2f} {q[100]:>7.2f}"
        )

    if not all_vals:
        print("\n[abort] no data collected")
        return 2

    print(f"\n=== POOLED DISTRIBUTION (n={len(all_vals)} daily bars across {len(per_symbol)} symbols) ===")
    q = _percentiles(all_vals, [5, 10, 25, 50, 75, 90, 95, 99])
    for p in [5, 10, 25, 50, 75, 90, 95, 99]:
        print(f"  p{p:<2} = {q[p]:.2f}%")
    print(f"  median-of-per-symbol-medians = {median([median(v) for v in per_symbol.values()]):.2f}%")

    # Proposed data-derived bands (quantile anchors; operator confirms in the plan):
    #   compressed = below p10 (genuinely dead)
    #   normal     = p10..p50
    #   elevated   = p50..p80
    #   volatile   = p80..p95
    #   chaotic    = above p95
    qb = _percentiles(all_vals, [10, 50, 80, 95])
    print("\n=== PROPOSED DATA-DERIVED BANDS (quantile anchors — confirm in plan) ===")
    print(f"  compressed : atr% <  {qb[10]:.2f}   (below p10 — genuinely dead daily range)")
    print(f"  normal     : {qb[10]:.2f} .. {qb[50]:.2f}   (p10..p50)")
    print(f"  elevated   : {qb[50]:.2f} .. {qb[80]:.2f}   (p50..p80)")
    print(f"  volatile   : {qb[80]:.2f} .. {qb[95]:.2f}   (p80..p95)")
    print(f"  chaotic    : atr% >= {qb[95]:.2f}   (above p95)")
    print("\n  (current hardcoded bands: 0.8 / 1.5 / 2.5 / 4.0 — tuned for the wrong TF)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
