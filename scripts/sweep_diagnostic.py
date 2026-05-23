"""
Liquidity Sweep Diagnostic Script — SniperSight
================================================
Runs Liquidity Sweep detection with full pipeline visibility.
Shows exactly how many sweeps survive each confirmation tier, 
grade breakdown, and reversal distance distributions.

Usage:
    python sweep_diagnostic.py --symbol BTC/USDT --timeframe 15m --limit 500
    python sweep_diagnostic.py --symbol ETH/USDT --timeframe 1h --limit 500 --exchange bitget
"""

import argparse
import sys
import os
from datetime import datetime

import pandas as pd
import numpy as np

# Add backend to path so imports work
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, os.path.join(parent_dir, "snipersight-trading"))

from backend.strategy.smc.liquidity_sweeps import detect_liquidity_sweeps
from backend.shared.config.smc_config import SMCConfig

# ── ASCII histogram ───────────────────────────────────────────────────────────

def ascii_histogram(values: list[float], bins: int = 15, width: int = 50, label: str = "") -> str:
    if not values:
        return "  (no data)"
    min_v, max_v = min(values), max(values)
    if min_v == max_v:
        return f"  All values: {min_v:.3f}"

    bin_size = (max_v - min_v) / bins
    if bin_size == 0:
        return f"  All values: {min_v:.3f}"
        
    counts   = [0] * bins
    for v in values:
        idx = min(int((v - min_v) / bin_size), bins - 1)
        counts[idx] += 1

    max_count = max(counts) or 1
    lines = []
    if label:
        lines.append(f"  {label}")
    for i, count in enumerate(counts):
        lo  = min_v + i * bin_size
        hi  = lo + bin_size
        bar = "█" * int(count / max_count * width)
        pct = count / len(values) * 100
        lines.append(f"  {lo:6.3f}-{hi:6.3f} │{bar:<{width}}│ {count:3d} ({pct:4.1f}%)")
    return "\n".join(lines)


# ── Data loading ──────────────────────────────────────────────────────────────

def load_from_exchange(symbol: str, timeframe: str, limit: int = 500, exchange: str = "bitget") -> pd.DataFrame:
    try:
        import ccxt
        ex_class = getattr(ccxt, exchange)
        ex = ex_class()
        print(f"Fetching {limit} bars of {symbol} {timeframe} from {exchange.upper()}...")
        ohlcv = ex.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.set_index('timestamp')
        return df
    except Exception as e:
        print(f"Error fetching data: {e}")
        sys.exit(1)


# ── Pipeline runner ───────────────────────────────────────────────────────────

def run_pipeline(df: pd.DataFrame, timeframe: str) -> dict:
    """
    Runs the Liquidity Sweep pipeline and extracts diagnostic metrics.
    """
    current_time = df.index[-1].to_pydatetime()
    current_price = df["close"].iloc[-1]

    # Run actual detection
    config = SMCConfig.defaults()
    sweeps = detect_liquidity_sweeps(df, config=config)

    # Gather metrics
    high_sweeps = [s for s in sweeps if s.sweep_type == "high"]
    low_sweeps = [s for s in sweeps if s.sweep_type == "low"]

    grade_counts = {"A": 0, "B": 0, "C": 0}
    conf_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    reversal_patterns = 0

    for s in sweeps:
        grade_counts[s.grade] += 1
        conf_counts[s.confirmation_level] += 1
        if s.has_reversal_pattern:
            reversal_patterns += 1

    return {
        "timeframe": timeframe,
        "current_price": current_price,
        "candles": len(df),
        "total_sweeps": len(sweeps),
        "high_sweeps": len(high_sweeps),
        "low_sweeps": len(low_sweeps),
        "grades": grade_counts,
        "confirmations": conf_counts,
        "reversal_patterns": reversal_patterns,
        "sweeps": sweeps,
    }

# ── Report generation ─────────────────────────────────────────────────────────

def generate_report(symbol: str, result: dict, out_path: str = "sweep_diagnostic_report.txt") -> str:
    sep  = "═" * 72
    thin = "─" * 72
    lines = []
    tf = result["timeframe"]

    lines.append(sep)
    lines.append(f"  SNIPERSIGHT — LIQUIDITY SWEEP DIAGNOSTIC REPORT")
    lines.append(f"  Symbol: {symbol}  |  Timeframe: {tf}  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(sep)

    lines.append(f"\n  DATASET")
    lines.append(thin)
    lines.append(f"  Candles:          {result['candles']}")
    lines.append(f"  Current Price:    {result['current_price']:.4f}")

    lines.append(f"\n  PIPELINE FUNNEL")
    lines.append(thin)
    lines.append(f"  Total Sweeps Detected:  {result['total_sweeps']}")
    lines.append(f"    High Sweeps (Bearish Reversal): {result['high_sweeps']}")
    lines.append(f"    Low Sweeps (Bullish Reversal):  {result['low_sweeps']}")
    
    lines.append(f"\n  QUALITY BREAKDOWN")
    lines.append(thin)
    gc = result["grades"]
    lines.append(f"  By Grade:       A= {gc['A']:<3} B= {gc['B']:<3} C= {gc['C']:<3}")
    
    cc = result["confirmations"]
    lines.append(f"  By Conf Level:  L3= {cc[3]:<3} L2= {cc[2]:<3} L1= {cc[1]:<3} L0= {cc[0]:<3}")
    lines.append(f"  (L3=Climactic Vol, L2=Strong Vol, L1=Pattern Only, L0=None)")
    lines.append(f"  Reversal Pattern Found: {result['reversal_patterns']} / {result['total_sweeps']}")

    lines.append(f"\n{sep}")
    report = "\n".join(lines)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Liquidity Sweep Diagnostic Tool")
    parser.add_argument("--symbol", type=str, default="BTC/USDT")
    parser.add_argument("--timeframes", type=str, default="all", help="Comma-separated timeframes or 'all'")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--exchange", type=str, default="bitget")
    parser.add_argument("--out", type=str, default=r"c:\Users\macca\snipersight-trading\sweep_diagnostic_report.txt")
    args = parser.parse_args()

    # Determine timeframes to run
    if args.timeframes.lower() == "all":
        tfs = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
    else:
        tfs = [t.strip() for t in args.timeframes.split(",")]

    # Clear out previous run if it exists
    if os.path.exists(args.out):
        os.remove(args.out)

    combined_report = []

    for tf in tfs:
        print(f"\nProcessing {args.symbol} on {tf} timeframe...")
        df = load_from_exchange(args.symbol, tf, args.limit, args.exchange)
        
        print(f"Running sweep detection on {len(df)} candles...")
        result = run_pipeline(df, tf)
        
        report_text = generate_report(args.symbol, result, args.out + ".tmp")
        combined_report.append(report_text)
        
        # Append to main file
        with open(args.out, "a", encoding="utf-8") as f:
            f.write(report_text + "\n\n")

    if os.path.exists(args.out + ".tmp"):
        os.remove(args.out + ".tmp")

    print("\n" + "═"*72)
    print(f"Finished processing {len(tfs)} timeframes.")
    print(f"Full combined report saved to {args.out}")
