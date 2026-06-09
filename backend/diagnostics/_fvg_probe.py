"""TEMP probe: run detect_fvgs directly on BTC 4h/1d to root-cause the 0-FVG perception bug.
Reports potential gaps, overlap fails, size fails, and final FVGs per TF.
"""
import sys
from backend.data.adapters.phemex import PhemexAdapter
from backend.data.ingestion_pipeline import IngestionPipeline
from backend.strategy.smc.fvg import detect_fvgs, MODE_FVG_MIN_SIZE
from backend.indicators.volatility import compute_atr

sym = sys.argv[1] if len(sys.argv) > 1 else "BTC/USDT"
adapter = PhemexAdapter()
pipe = IngestionPipeline(adapter)
mtf = pipe.fetch_multi_timeframe(sym, ["15m", "1h", "4h", "1d"])

for tf in ["4h", "1d"]:
    df = mtf.timeframes.get(tf)
    if df is None or len(df) < 20:
        print(f"\n=== {tf}: no/short data ({0 if df is None else len(df)} rows) ===")
        continue
    atr = compute_atr(df, period=14)
    print(f"\n=== {tf} ({len(df)} candles) | last close {df['close'].iloc[-1]:.0f} | "
          f"date range {df.index[0]} -> {df.index[-1]} | ATR(last)={atr.iloc[-1]:.1f} ===")
    # raw 3-candle gaps (no filter) — does the STRUCTURE exist at all?
    raw_bull = raw_bear = 0
    examples = []
    for i in range(2, len(df)):
        c0, c2 = df.iloc[i-2], df.iloc[i]
        if c0["high"] < c2["low"]:
            raw_bull += 1
            if len(examples) < 6:
                examples.append((str(df.index[i].date()), "bull", round(c0["high"]), round(c2["low"]), round(c2["low"]-c0["high"])))
        if c0["low"] > c2["high"]:
            raw_bear += 1
            if len(examples) < 6:
                examples.append((str(df.index[i].date()), "bear", round(c2["high"]), round(c0["low"]), round(c0["low"]-c2["high"])))
    print(f"  RAW 3-candle gaps in data: {raw_bull} bullish, {raw_bear} bearish")
    print(f"  sample raw gaps (date,dir,bottom,top,size): {examples}")
    # now the actual detector (stealth profile)
    fvgs, raw_count = detect_fvgs(df, mode_profile="stealth", _return_raw_count=True)
    print(f"  detect_fvgs(stealth, min_gap_atr={MODE_FVG_MIN_SIZE['stealth']}): "
          f"raw_passed_overlap={raw_count}  final={len(fvgs)}")
    for f in fvgs[:6]:
        print(f"    FVG {f.direction} {f.bottom:.0f}-{f.top:.0f} size_atr={f.size_atr:.2f} grade={f.grade} @ {f.timestamp.date()}")
