
import pandas as pd
import numpy as np
from backend.services.indicator_service import IndicatorService
from backend.shared.models.data import MultiTimeframeData
from backend.shared.models.indicators import IndicatorSet

def generate_synthetic_squeeze():
    """
    Generate synthetic OHLCV data that transitions from:
    1. High Volatility (Wide Bands)
    2. Consolidation (Narrow Bands - Squeeze ON)
    3. Expansion (Breakout - Squeeze FIRE)
    """
    length = 100
    dates = pd.date_range(start='2024-01-01', periods=length, freq='1h')
    
    # Base price trend
    price = 10000.0
    prices = []
    
    # 1. Normal (0-40)
    for i in range(40):
        # High volatility noise
        change = np.random.normal(0, 50) 
        price += change
        prices.append(price)
        
    # 2. Squeeze (40-80)
    squeeze_start_price = price
    for i in range(40):
        # Very low volatility noise (Compression)
        change = np.random.normal(0, 5) 
        price += change
        # Keep it tight around mean
        price = squeeze_start_price + (price - squeeze_start_price) * 0.1
        prices.append(price)
        
    # 3. Fire (80-100)
    for i in range(20):
        # Massive expansion
        change = np.random.normal(100, 20) # Directional up
        price += change
        prices.append(price)
        
    df = pd.DataFrame({
        'timestamp': dates,
        'open': prices,
        'high': [p + 10 for p in prices],
        'low': [p - 10 for p in prices],
        'close': prices,
        'volume': [1000.0] * length
    })
    # MultiTimeframeData requires 'timestamp' column AND datetime index usually, 
    # but the validator explicitly checks 'timestamp' column existence.
    # df.set_index('timestamp', inplace=True) # REMOVED: Keep timestamp column
    return df

def test_ttm_squeeze():
    print("--- Testing TTM Squeeze Logic ---")
    df = generate_synthetic_squeeze()
    print(f"Generated {len(df)} candles.")
    
    # Create Data Object
    mtf_data = MultiTimeframeData(symbol="BTC/USDT", timeframes={"1h": df})
    
    # Compute Indicators
    service = IndicatorService()
    indicators = service.compute(mtf_data)
    
    # Analyze Squeeze State
    # We can't access full history from snapshot (it only keeps latest).
    # BUT, IndicatorService logs values. 
    # To verify transitions, we really need to run compute on slicing windows or check the service internals.
    # Service internal `_compute_timeframe_indicators` does the logic on the full DF.
    # Let's verify by calling `_compute_timeframe_indicators` directly and inspecting the fields?
    # No, let's trust the logic if we see the final state (Fire).
    
    # Actually, the best way is to call the underlying functions or check the service output for the *final* candle (which is in expansion).
    
    snapshot = indicators.get_indicator("1h")
    
    print(f"Final Candle State:")
    print(f"BB: {snapshot.bb_lower:.2f} - {snapshot.bb_upper:.2f}")
    print(f"KC: {snapshot.kc_lower:.2f} - {snapshot.kc_upper:.2f}")
    print(f"Squeeze ON: {snapshot.ttm_squeeze_on}")
    print(f"Squeeze FIRING: {snapshot.ttm_squeeze_firing}")
    
    # Ideally, the final candle (expansion) should have Squeeze ON = False.
    # If we check candle 70 (middle of squeeze), it should be ON.
    
    print("\n--- Deep Inspection (Simulating rolling check) ---")
    # Let's slice the DF to simulating checking at different times
    
    # Check during Squeeze (Candle 60)
    df_squeeze = df.iloc[:60]
    mtf_squeeze = MultiTimeframeData(symbol="BTC/USDT", timeframes={"1h": df_squeeze})
    snap_squeeze = service.compute(mtf_squeeze).get_indicator("1h")
    print(f"During Squeeze (Candle 60): ON={snap_squeeze.ttm_squeeze_on} (Expect True)")
    
    # Check at Breakout (Candle 82)
    df_fire = df.iloc[:82]
    mtf_fire = MultiTimeframeData(symbol="BTC/USDT", timeframes={"1h": df_fire})
    snap_fire = service.compute(mtf_fire).get_indicator("1h")
    print(f"At Breakout (Candle 82): ON={snap_fire.ttm_squeeze_on}, FIRING={snap_fire.ttm_squeeze_firing} (Expect Firing=True)")

if __name__ == "__main__":
    test_ttm_squeeze()
