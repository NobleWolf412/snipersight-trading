"""
Deep diagnostic: Why no trades for Strike/Surgical/Stealth?
"""
import sys
sys.path.insert(0, ".")
import json

from backend.shared.config.defaults import ScanConfig
from backend.shared.config.scanner_modes import get_mode
from backend.data.adapters.phemex import PhemexAdapter
from backend.engine.orchestrator import Orchestrator

output = []

def log(msg):
    output.append(msg)

for mode_name in ["strike"]:
    log(f"\n{'='*60}")
    log(f"  DIAGNOSTIC: {mode_name.upper()} MODE")
    log(f"{'='*60}")
    
    mode = get_mode(mode_name)
    config = ScanConfig()
    config.min_confluence_score = mode.min_confluence_score
    
    log(f"  Min confluence: {mode.min_confluence_score}")
    log(f"  Timeframes: {mode.timeframes}")
    log(f"  Profile: {mode.profile}")
    
    adapter = PhemexAdapter()
    orchestrator = Orchestrator(config=config, exchange_adapter=adapter)
    orchestrator.apply_mode(mode)
    
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    
    try:
        trade_plans, rejections = orchestrator.scan(symbols)
        log(f"  Generated: {len(trade_plans)} trade plans")
        log(f"  Rejections type: {type(rejections).__name__}")
        
        # Handle rejections as dict or list
        if isinstance(rejections, dict):
            log(f"  Rejection keys: {list(rejections.keys())}")
            for sym, rej_list in rejections.items():
                log(f"\n  Symbol: {sym}")
                if isinstance(rej_list, list):
                    for rej in rej_list:
                        log(f"    {json.dumps(rej, default=str)[:300]}")
                elif isinstance(rej_list, dict):
                    log(f"    {json.dumps(rej_list, default=str)[:300]}")
                else:
                    log(f"    {str(rej_list)[:300]}")
        elif isinstance(rejections, list):
            log(f"  Rejections count: {len(rejections)}")
            for i, rej in enumerate(rejections[:20]):
                log(f"  REJ[{i}]: {json.dumps(rej, default=str)[:300]}")
        else:
            log(f"  Rejections raw: {str(rejections)[:500]}")
        
        for plan in trade_plans:
            log(f"  ACCEPTED: {plan.symbol} {plan.direction} score={plan.confidence_score}")
        
    except Exception as e:
        import traceback
        log(f"  ERROR: {e}")
        log(traceback.format_exc())

with open("diagnostic_output.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))
print("Saved to diagnostic_output.txt")
