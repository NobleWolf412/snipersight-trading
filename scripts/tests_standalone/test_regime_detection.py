"""
Test script to check current regime detection with detailed breakdown.
Run this after a scan to see WHY a specific regime was determined.
"""

import logging
import asyncio
from datetime import datetime

# Set up logging to see all the details
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%H:%M:%S'
)

# Reduce noise from other modules
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('ccxt').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)


async def test_regime():
    from backend.analysis.regime_detector import get_regime_detector, RegimeDetector
    from backend.data.ingestion_pipeline import IngestionPipeline
    from backend.services.indicator_service import IndicatorService
    
    print("\n" + "="*70)
    print("                    REGIME DETECTION TEST")
    print("="*70 + "\n")
    
    # Create fresh detector to see initial confirmation
    detector = RegimeDetector(mode_profile="stealth_balanced")
    
    # Fetch BTC data
    print("📡 Fetching BTC/USDT data...")
    from backend.data.adapters.phemex import PhemexAdapter
    adapter = PhemexAdapter()
    pipeline = IngestionPipeline(adapter)
    btc_data = pipeline.fetch_multi_timeframe("BTC/USDT", ["1d", "4h", "1h"], limit=500)
    
    if not btc_data.timeframes:
        print("❌ Failed to fetch BTC data")
        return
    
    print(f"✅ Fetched data for timeframes: {list(btc_data.timeframes.keys())}")
    for tf, df in btc_data.timeframes.items():
        print(f"   {tf}: {len(df)} candles, latest close: ${df['close'].iloc[-1]:,.2f}")
    
    # Calculate indicators
    print("\n📊 Calculating indicators...")
    indicator_service = IndicatorService()
    btc_indicators = indicator_service.compute(btc_data)
    
    if btc_indicators.by_timeframe:
        for tf, ind in btc_indicators.by_timeframe.items():
            rsi = getattr(ind, 'rsi', None)
            atr = getattr(ind, 'atr', None)
            atr_pct = getattr(ind, 'atr_percent', None)
            rsi_str = f"{rsi:.1f}" if rsi else "N/A"
            atr_str = f"{atr:.2f}" if atr else "N/A"
            atr_pct_str = f"{atr_pct:.2f}" if atr_pct else "N/A"
            print(f"   {tf}: RSI={rsi_str}, ATR={atr_str}, ATR%={atr_pct_str}%")
    
    # Detect regime (this will print detailed breakdown)
    print("\n🔍 Detecting regime (watch for detailed breakdown in logs)...\n")
    regime = detector.detect_global_regime(btc_data, btc_indicators)
    
    print("\n" + "="*70)
    print("                    REGIME RESULT SUMMARY")
    print("="*70)
    print(f"\n  📈 COMPOSITE LABEL: {regime.composite}")
    print(f"  📊 SCORE:          {regime.score:.1f}")
    print(f"\n  DIMENSIONS:")
    print(f"    • Trend:         {regime.dimensions.trend} (score: {regime.trend_score:.1f})")
    print(f"    • Volatility:    {regime.dimensions.volatility} (score: {regime.volatility_score:.1f})")
    print(f"    • Liquidity:     {regime.dimensions.liquidity} (score: {regime.liquidity_score:.1f})")
    print(f"    • Risk Appetite: {regime.dimensions.risk_appetite} (score: {regime.risk_score:.1f})")
    print(f"    • Derivatives:   {regime.dimensions.derivatives} (score: {regime.derivatives_score:.1f})")
    
    print(f"\n  CONFIRMATION STATE:")
    print(f"    • Confirmed:     {detector._confirmed_regime.composite if detector._confirmed_regime else 'None'}")
    print(f"    • Pending:       {detector._pending_regime or 'None'} ({detector._pending_count}/{detector._confirmation_required})")
    
    # Run detection multiple times to show confirmation behavior
    print("\n" + "="*70)
    print("             RUNNING MULTIPLE DETECTIONS TO SHOW CONFIRMATION")
    print("="*70 + "\n")
    
    for i in range(5):
        print(f"--- Detection #{i+2} ---")
        regime = detector.detect_global_regime(btc_data, btc_indicators)
        print(f"  Result: {regime.composite} | Confirmed: {detector._confirmed_regime.composite if detector._confirmed_regime else 'None'} | Pending: {detector._pending_regime} ({detector._pending_count}/{detector._confirmation_required})\n")
    
    print("="*70)
    print("                    TEST COMPLETE")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(test_regime())
