"""
Run a fresh backtest across all 4 modes with the fixed ingestion pipeline.
Write results to JSON for clean reading.
"""
import sys
sys.path.insert(0, ".")

from scripts.run_backtest import run_backtest
import json
import traceback

modes = ["strike", "surgical", "stealth", "overwatch"]
results = {}

for mode in modes:
    print(f"Running {mode.upper()}...", flush=True)
    try:
        r = run_backtest(mode_name=mode, days=7, leverage=1, verbose=False)
        results[mode] = {
            "total_trades": r.total_trades,
            "wins": r.wins,
            "losses": r.losses,
            "win_rate": round(r.win_rate, 2),
            "total_pnl_pct": round(r.total_pnl_pct, 2),
            "avg_pnl_pct": round(r.avg_pnl_pct, 2),
            "avg_r": round(r.avg_r, 2),
            "profit_factor": round(r.profit_factor, 2),
            "max_drawdown_pct": round(r.max_drawdown_pct, 2),
            "final_equity": round(r.final_equity, 2),
            "initial_equity": round(r.initial_equity, 2),
            "by_direction": dict(r.by_direction) if r.by_direction else {},
            "by_symbol": dict(r.by_symbol) if r.by_symbol else {},
        }
        print(f"  -> {r.total_trades} trades, {r.win_rate:.1f}% WR, {r.total_pnl_pct:+.2f}% PnL", flush=True)
    except Exception as e:
        results[mode] = {"error": str(e), "traceback": traceback.format_exc()[-500:]}
        print(f"  -> ERROR: {e}", flush=True)

with open("backtest_fresh_results.json", "w") as f:
    json.dump(results, f, indent=2)
print("\nResults saved to backtest_fresh_results.json", flush=True)
