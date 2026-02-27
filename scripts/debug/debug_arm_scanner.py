
import asyncio
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Filter out noisy libraries
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("ccxt").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

from backend.data.adapters.phemex import PhemexAdapter
from backend.data.adapters.bybit import BybitAdapter
from backend.data.adapters.okx import OKXAdapter
from backend.data.adapters.bitget import BitgetAdapter
from backend.risk.position_sizer import PositionSizer
from backend.risk.risk_manager import RiskManager
from backend.engine.orchestrator import Orchestrator
from backend.shared.config.defaults import ScanConfig
from backend.services.scanner_service import configure_scanner_service

async def main():
    print("🚀 Initializing Scanner Debug Environment...")
    
    # 1. Initialize Adapters
    print("🔌 Initializing Exchange Adapters...")
    EXCHANGE_ADAPTERS = {
        'bybit': lambda: BybitAdapter(testnet=False),
        'phemex': lambda: PhemexAdapter(testnet=False),
        'okx': lambda: OKXAdapter(testnet=False),
        'bitget': lambda: BitgetAdapter(testnet=False),
    }
    
    # 2. Initialize Core Components
    print("⚙️  Initializing Risk & Position Managers...")
    position_sizer = PositionSizer(account_balance=10000, max_risk_pct=2.0)
    risk_manager = RiskManager(
        account_balance=10000,
        max_open_positions=5,
        max_asset_exposure_pct=50.0
    )
    
    # 3. Initialize Orchestrator
    print("🧠 Initializing Orchestrator...")
    # Use Phemex for testing as it doesn't geo-block usually
    exchange_adapter = PhemexAdapter(testnet=False)
    
    default_config = ScanConfig(
        profile="recon",
        timeframes=("1h", "4h", "1d"),
        min_confluence_score=70.0,
        max_risk_pct=2.0
    )
    
    orchestrator = Orchestrator(
        config=default_config,
        exchange_adapter=exchange_adapter,
        risk_manager=risk_manager,
        position_sizer=position_sizer,
        concurrency_workers=4
    )
    
    # 4. Initialize Scanner Service
    print("📡 Initializing Scanner Service...")
    # Define a simple log handler to print captured logs
    class PrintLogHandler:
        def set_current_job(self, job):
            if job:
                print(f"📝 Capturing logs for job {job.run_id}")
            else:
                print("📝 Stopped capturing logs")
                
    scanner_service = configure_scanner_service(
        orchestrator=orchestrator,
        exchange_adapters=EXCHANGE_ADAPTERS,
        log_handler=PrintLogHandler()
    )
    
    # 5. Execute "Arm Scanner" Flow
    print("\n🎯 ARMING SCANNER (Simulating 'Arm Scanner' button click)...")
    try:
        # Create scan with typical frontend params
        job = await scanner_service.create_scan(
            limit=3,          # Small limit for debug speed
            min_score=60,     # Lower score to hopefully find something
            sniper_mode="recon",
            majors=True,
            altcoins=True,
            meme_mode=False,
            exchange="phemex",
            leverage=10,
            macro_overlay=False
        )
        
        print(f"✅ Scan Job Created: ID={job.run_id}")
        
        # Poll for completion
        print("\n⏳ Polling for completion...")
        start_time = time.time()
        
        while True:
            current_job = scanner_service.get_job(job.run_id)
            elapsed = time.time() - start_time
            
            print(f"   Status: {current_job.status.upper()} | Progress: {current_job.progress}/{current_job.total} | Elapsed: {elapsed:.1f}s")
            
            if current_job.status in ["completed", "failed", "cancelled"]:
                break
                
            await asyncio.sleep(2)
            
        print("\n" + "="*50)
        print("🏁 SCAN COMPLETE")
        print("="*50)
        
        if current_job.status == "completed":
            print(f"📊 Scanned: {current_job.metadata.get('scanned', 0)}")
            print(f"🚫 Rejected: {current_job.metadata.get('rejected', 0)}")
            print(f"✅ Signals: {len(current_job.signals)}")
            
            if current_job.signals:
                print("\n💡 FOUND SIGNALS:")
                for i, signal in enumerate(current_job.signals, 1):
                    # Use .get() method on signal dictionary to safely access keys
                    print(f"  {i}. {signal.get('symbol')} {signal.get('direction')} (Score: {signal.get('score')})")
                    print(f"     Why: {signal.get('rationale')}")
            else:
                print("\n📉 No signals found. Rejection breakdown:")
                # Use .get() on rejections dictionary as well
                rejections = current_job.rejections
                if rejections and isinstance(rejections, dict) and 'by_reason' in rejections:
                    for reason, count in rejections.get('by_reason', {}).items():
                        print(f"  - {reason}: {count}")
                else:
                    print("  No rejection data available.")
                    
        elif current_job.status == "failed":
            print(f"❌ SCAN FAILED: {current_job.error}")
            
    except Exception as e:
        print(f"💥 FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
