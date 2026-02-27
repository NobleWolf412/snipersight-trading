
import sys
import os
import pandas as pd
import logging

# Add project root to path
sys.path.insert(0, '/home/maccardi4431/snipersight-trading')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# from backend.data.adapters.csv_adapter import CSVDataAdapter
from backend.services.smc_service import SMCDetectionService
from backend.services.indicator_service import IndicatorService
from backend.shared.models.data import MultiTimeframeData
from backend.shared.config.scanner_modes import get_mode
from backend.shared.config.defaults import ScanConfig

def test_detection():
    # Load data
    csv_path = '/home/maccardi4431/snipersight-trading/backend/tests/backtest/backtest_multitimeframe_real.csv'
    logger.info(f"Loading data from {csv_path}")
    
    # Manually load CSV to create MultiTimeframeData
    df_raw = pd.read_csv(csv_path)
    df_raw['timestamp'] = pd.to_datetime(df_raw['timestamp'])
    
    # Split by symbol and timeframe
    symbol = 'BTC/USDT'
    timeframes = ['1d', '4h', '1h', '15m', '5m']
    
    data_map = {}
    for tf in timeframes:
        mask = (df_raw['symbol'] == symbol) & (df_raw['timeframe'] == tf)
        df_tf = df_raw[mask].copy().sort_values('timestamp')
        
        # Ensure numeric columns
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df_tf[col] = pd.to_numeric(df_tf[col], errors='coerce')
        
        if not df_tf.empty:
            data_map[tf] = df_tf
            zero_vol = (df_tf['volume'] == 0).sum()
            logger.info(f"Loaded {tf}: {len(df_tf)} rows. Zero volume: {zero_vol} ({zero_vol/len(df_tf)*100:.1f}%)")
    
    if not data_map:
        logger.error("No data found for BTC/USDT")
        return

    # Create MultiTimeframeData
    mtf_data = MultiTimeframeData(
        symbol=symbol,
        timeframes=data_map,
        metadata={'exchange': 'test'}
    )
    
    # Initialize Services
    smc_service = SMCDetectionService()
    indicator_service = IndicatorService()
    
    # Test Indicator Computation
    logger.info("--- Testing Indicator Computation ---")
    indicators = indicator_service.compute(mtf_data)
    for tf, snapshot in indicators.by_timeframe.items():
        logger.info(f"Indicators for {tf}: ATR={snapshot.atr:.2f} (valid)")
        
    if not indicators.by_timeframe:
        logger.error("No indicators computed!")
        
    # Test SMC Detection
    logger.info("--- Testing SMC Detection ---")
    current_price = data_map['5m']['close'].iloc[-1]
    smc_snapshot = smc_service.detect(mtf_data, current_price)
    
    logger.info(f"SMC Results:")
    logger.info(f"  Order Blocks: {len(smc_snapshot.order_blocks)}")
    logger.info(f"  FVGs: {len(smc_snapshot.fvgs)}")
    logger.info(f"  Breaks: {len(smc_snapshot.structural_breaks)}")
    logger.info(f"  Sweeps: {len(smc_snapshot.liquidity_sweeps)}")
    
    # Check if we have minimal requirements for a trade
    has_structure = len(smc_snapshot.order_blocks) > 0 or len(smc_snapshot.fvgs) > 0
    logger.info(f"Has usable structure? {has_structure}")

if __name__ == "__main__":
    test_detection()
