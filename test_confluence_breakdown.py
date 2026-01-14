"""
Quick test script to capture confluence breakdown from a scan.

Run this to see detailed score breakdowns for investigation.
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from backend.services.scanner_service import ScannerService
from backend.shared.config.scanner_modes import SCANNER_MODES
from loguru import logger

async def test_confluence_breakdown():
    """Run a quick OVERWATCH scan to capture confluence breakdown."""
    
    logger.info("🔍 Running OVERWATCH scan to capture confluence breakdown...")
    
    # Get OVERWATCH mode config
    mode_config = SCANNER_MODES.get("OVERWATCH")
    if not mode_config:
        logger.error("OVERWATCH mode not found")
        return
    
    # Use a small set of pairs for quick test
    test_pairs = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    mode_config.pairs = test_pairs
    
    # Run scan
    scanner = ScannerService()
    
    try:
        results = await scanner.scan(mode_config)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"RESULTS SUMMARY:")
        logger.info(f"  Total scanned: {len(test_pairs)}")
        logger.info(f"  Passed threshold: {len(results)} signals")
        logger.info(f"  Pass rate: {len(results)/len(test_pairs)*100:.1f}%")
        logger.info(f"{'='*80}\n")
        
        if results:
            logger.info("Signals generated:")
            for sig in results:
                logger.info(f"  - {sig.symbol}: {sig.score:.2f} ({sig.direction})")
        
    except Exception as e:
        logger.error(f"Scan failed: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_confluence_breakdown())
