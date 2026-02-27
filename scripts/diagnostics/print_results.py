import json

d = json.load(open("backtest_fresh_results.json"))
lines = []
lines.append("=" * 60)
lines.append("  FRESH BACKTEST RESULTS — ALL MODES")
lines.append("  Date: 2026-02-17 ~7PM EST")
lines.append("  Period: Last 7 days | Leverage: 1x | Fees: 0.1%")
lines.append("=" * 60)

for m, r in d.items():
    lines.append("")
    lines.append(f"{'='*50}")
    lines.append(f"  MODE: {m.upper()}")
    lines.append(f"{'='*50}")
    if "error" in r:
        lines.append(f"  ERROR: {r['error'][:200]}")
        if "traceback" in r:
            lines.append(f"  TRACEBACK:")
            for tl in r["traceback"].split("\n")[-10:]:
                lines.append(f"    {tl}")
    else:
        lines.append(f"  Total Trades: {r['total_trades']}")
        lines.append(f"  Wins: {r['wins']} | Losses: {r['losses']}")
        lines.append(f"  Win Rate: {r['win_rate']}%")
        lines.append(f"  Total PnL: {r['total_pnl_pct']}%")
        lines.append(f"  Avg PnL/Trade: {r['avg_pnl_pct']}%")
        lines.append(f"  Avg R: {r['avg_r']}")
        lines.append(f"  Profit Factor: {r['profit_factor']}")
        lines.append(f"  Max Drawdown: {r['max_drawdown_pct']}%")
        lines.append(f"  Final Equity: ${r['final_equity']} (from ${r.get('initial_equity', 10000)})")
        ret = (r['final_equity'] - r.get('initial_equity', 10000)) / r.get('initial_equity', 10000) * 100
        lines.append(f"  Return: {ret:+.2f}%")
        if r.get("by_direction"):
            lines.append(f"  ---")
            lines.append(f"  By Direction:")
            for d2, s in r["by_direction"].items():
                wr = s["wins"] / s["trades"] * 100 if s["trades"] > 0 else 0
                lines.append(f"    {d2}: {s['trades']} trades, {wr:.0f}% WR, {s['pnl']:.2f}% PnL")
        if r.get("by_symbol"):
            lines.append(f"  ---")
            lines.append(f"  By Symbol:")
            for sym, s in sorted(r["by_symbol"].items(), key=lambda x: x[1]["pnl"], reverse=True):
                wr = s["wins"] / s["trades"] * 100 if s["trades"] > 0 else 0
                lines.append(f"    {sym}: {s['trades']} trades, {wr:.0f}% WR, {s['pnl']:.2f}% PnL")
    lines.append("")

with open("backtest_summary.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("Written to backtest_summary.txt")
