"""
Diagnostic: Figure out why Strike/Surgical/Stealth produce 0 trades.
Runs the scanner for each mode and captures rejection reasons.
"""
import sys
sys.path.insert(0, ".")

from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode, MODES
from backend.data.adapters.phemex import PhemexAdapter
from backend.engine.orchestrator import Orchestrator
import json

symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT",
           "XRP/USDT", "DOGE/USDT", "LINK/USDT", "ADA/USDT"]

results = {}

for mode_name in ["strike", "surgical", "stealth", "overwatch"]:
    print(f"\n=== {mode_name.upper()} ===")
    mode = get_mode(mode_name)
    config = ScanConfig()
    config.min_confluence_score = mode.min_confluence_score
    
    print(f"  Min confluence score: {mode.min_confluence_score}")
    print(f"  Timeframes: {mode.timeframes}")
    print(f"  Profile: {mode.profile}")
    
    adapter = PhemexAdapter()
    orchestrator = Orchestrator(config=config, exchange_adapter=adapter)
    orchestrator.apply_mode(mode)
    
    try:
        trade_plans, rejections = orchestrator.scan(symbols)
        print(f"  Trade plans: {len(trade_plans)}")
        print(f"  Rejections: {len(rejections)}")
        
        results[mode_name] = {
            "trade_plans": len(trade_plans),
            "rejections_count": len(rejections),
            "rejection_reasons": [],
            "min_score": mode.min_confluence_score,
        }
        
        # Capture rejection reasons
        if rejections:
            for rej in rejections[:20]:  # First 20
                if isinstance(rej, dict):
                    reason = rej.get("reason", str(rej))
                    symbol = rej.get("symbol", "?")
                    score = rej.get("score", "?")
                    results[mode_name]["rejection_reasons"].append(
                        f"{symbol}: {reason} (score={score})"
                    )
                    print(f"    Rejected: {symbol} - {reason} (score={score})")
                elif isinstance(rej, tuple):
                    results[mode_name]["rejection_reasons"].append(str(rej))
                    print(f"    Rejected: {rej}")
                else:
                    reason_str = str(rej)[:150]
                    results[mode_name]["rejection_reasons"].append(reason_str)
                    print(f"    Rejected: {reason_str}")
        
        # Show accepted plans
        for plan in trade_plans:
            sym = getattr(plan, "symbol", "?")
            direction = getattr(plan, "direction", "?")
            score = getattr(plan, "confidence_score", "?")
            print(f"    Accepted: {sym} {direction} (score={score})")
            
    except Exception as e:
        import traceback
        print(f"  ERROR: {e}")
        results[mode_name] = {"error": str(e), "traceback": traceback.format_exc()[-500:]}

with open("backtest_diagnostic.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
print("\nDiagnostic saved to backtest_diagnostic.json")
