import asyncio
from backend.engine.orchestrator import Orchestrator
from backend.data.adapters.phemex import PhemexAdapter
from backend.data.ingestion_pipeline import IngestionPipeline
from backend.shared.config.scanner_modes import get_mode
import json

async def test_overwatch():
    adapter = PhemexAdapter(default_type="swap")
    pipeline = IngestionPipeline(adapter)
    from backend.shared.config.defaults import ScanConfig
    mode = get_mode("overwatch")
    orchestra = Orchestrator(exchange_adapter=adapter, config=ScanConfig())
    orchestra.apply_mode(mode)
    print(f"Mode applied: {mode.name}, Threshold: {mode.min_confluence_score}")
    
    symbols = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
    
    trade_plans, rejections = orchestra.scan(symbols)
    
    print("\n--- RESULTS ---")
    print(f"Plans: {len(trade_plans)}")
    for p in trade_plans:
        print(f" {p.symbol} {p.direction} - {p.confidence_score}%")
        
    print("\n--- REJECTIONS ---")
    for r in rejections.get('details', {}).get('low_confluence', []):
        print(f" Low Confluence: {r['symbol']} ({r['score']} < {r['threshold']})")
    
    missing_tf = rejections.get('details', {}).get('missing_critical_tf', [])
    for r in missing_tf:
        print(f" Missing Critical TF: {r['symbol']} ({r['reason']})")
        
    no_data = rejections.get('details', {}).get('no_data', [])
    for r in no_data:
        print(f" No Data: {r['symbol']} ({r['reason']})")
        
    errors = rejections.get('details', {}).get('errors', [])
    for r in errors:
        print(f" Error: {r['symbol']} ({r['reason']})")

if __name__ == "__main__":
    asyncio.run(test_overwatch())
