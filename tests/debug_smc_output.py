
import sys
import os
import json
import logging

# Add project root to path
sys.path.append(os.getcwd())

from backend.shared.config.defaults import ScanConfig
from backend.engine.orchestrator import Orchestrator
from backend.data.adapters.mocks import MockExchangeAdapter

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting SMC Debug...")
    
    # 1. Setup Config
    config = ScanConfig(
        profile="stealth", # User mentioned "stealth"
        timeframes=('1W', '1D', '4H', '1H', '15m', '5m'),
        max_symbols=1
    )
    
    # 2. Setup Orchestrator (using MockAdapter if live keys not available, 
    # but let's try to assume live env if possible or use Mock if that's safer.
    # Given I don't have API keys, I should stick to MockAdapter if possible,
    # OR rely on existing integration tests.
    # However, the user environment seems to be a real workspace.
    # I'll check if I can use a real adapter or if I should assume mocks.
    # Safe to use MockAdapter for structure verification.)
    
    # Actually, let's use the real IngestionPipeline logic if possible, but 
    # to be safe and avoid auth errors, I'll check how tests do it.
    # I'll just use MockExchangeAdapter for now to ensure pipeline flow works.
    
    adapter = MockExchangeAdapter()
    
    orchestrator = Orchestrator(
        config=config,
        exchange_adapter=adapter
    )
    
    # 3. Scan a symbol
    symbols = ['BTC/USDT']
    signals, rejection_summary = orchestrator.scan(symbols)
    
    # 4. Inspect Output
    if not signals:
        logger.error("No signals generated. Rejection summary:")
        print(json.dumps(rejection_summary, indent=2, default=str))
        return

    signal = signals[0]
    print(f"\nSignal Generated for {signal.symbol}")
    
    # Check SMC Geometry
    smc = getattr(signal, 'smc_geometry', None)
    if not smc:
        logger.error("No SMC Geometry found!")
        return
        
    obs = smc.order_blocks
    print(f"Total OBs: {len(obs)}")
    
    # Group by timeframe
    by_tf = {}
    for ob in obs:
        tf = ob.timeframe
        if tf not in by_tf:
            by_tf[tf] = []
        by_tf[tf].append(ob)
        
    print("\nOBs by Timeframe:")
    for tf, ob_list in by_tf.items():
        print(f"  {tf}: {len(ob_list)} OBs")
        # Print first one
        if ob_list:
            print(f"    Sample: {ob_list[0]}")

if __name__ == "__main__":
    main()
