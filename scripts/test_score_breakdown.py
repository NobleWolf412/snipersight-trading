import asyncio
import traceback
from backend.services.orchestrator import StrategyOrchestrator
from backend.data.adapters.phemex import PhemexAdapter
from backend.data.ingestion_pipeline import IngestionPipeline
from backend.shared.config.scanner_modes import get_mode
import json

async def run_scan():
    print("Initializing...")
    adapter = PhemexAdapter(default_type="swap")
    pipeline = IngestionPipeline(adapter)
    
    # Initialize orchestrator
    orchestrator = StrategyOrchestrator(exchange_adapter=adapter)
    orchestrator.ingestion_pipeline = pipeline
    
    # Apply surgical mode
    mode = get_mode("surgical")
    orchestrator.apply_mode(mode)
    
    print(f"Mode applied: {mode.name}, Threshold: {mode.min_confluence_score}")
    
    # Target symbols 
    symbols = ["SOL/USDT:USDT"]
    print(f"Scanning symbols: {symbols}")
    
    # Run scan
    try:
        # scan is synchronous currently in StrategyOrchestrator
        trade_plans, rejections = orchestrator.scan(symbols)
        
        print("\n=== SCAN COMPLETE ===")
        print(f"Trade Plans Generated: {len(trade_plans)}")
        
        if len(trade_plans) > 0:
            for plan in trade_plans:
                print(f"PLAN FOR {plan.symbol} ({plan.direction}): Score {plan.confluence_score}")
        
        print(f"\nRejections for SOL/USDT:USDT:")
        
        # Pull low confluence details
        for rej in rejections.get('details', {}).get('low_confluence', []):
            if rej.get('symbol') == "SOL/USDT:USDT":
                # Look specifically for the detailed breakdown if it's there
                print(json.dumps(rej, indent=2))
        
        # Let's see all rejections for SOL to ensure we don't miss it
        print("All rejections:")
        print(json.dumps(rejections, indent=2))
        
    except Exception as e:
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_scan())
