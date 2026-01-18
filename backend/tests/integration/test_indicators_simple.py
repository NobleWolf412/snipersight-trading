"""
Simplified integration tests for indicators using DataFrame API.

Tests basic functionality of RSI, ATR, Bollinger Bands.
"""

import pandas as pd
from backend.indicators.momentum import compute_rsi
from backend.indicators.volatility import compute_atr, compute_bollinger_bands
from backend.indicators.volume import detect_volume_spike
from backend.tests.fixtures.market_data import (
    generate_bullish_trend_ohlcv,
)


def candles_to_df(candles):
    """Convert Candle objects to DataFrame."""
    return pd.DataFrame(
        [
            {
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in candles
        ]
    )


class TestRSIIndicator:
    """Test RSI calculations."""

    def test_rsi_computes_successfully(self):
        """RSI should compute without errors."""
        candles = generate_bullish_trend_ohlcv(100)
        df = candles_to_df(candles)

        rsi = compute_rsi(df, period=14)

        assert isinstance(rsi, pd.Series)
        assert len(rsi) == len(df)

    def test_rsi_values_in_valid_range(self):
        """RSI should be between 0 and 100."""
        candles = generate_bullish_trend_ohlcv(100)
        df = candles_to_df(candles)

        rsi = compute_rsi(df, period=14)
        valid_rsi = rsi.dropna()

        assert all((0 <= val <= 100) for val in valid_rsi)

    def test_rsi_different_periods(self):
        """RSI should work with different periods."""
        candles = generate_bullish_trend_ohlcv(100)
        df = candles_to_df(candles)

        rsi_14 = compute_rsi(df, period=14)
        rsi_21 = compute_rsi(df, period=21)

        assert len(rsi_14) == len(rsi_21)
        # Different periods may produce different values
        assert not rsi_14.equals(rsi_21)


class TestATRIndicator:
    """Test ATR calculations."""

    def test_atr_computes_successfully(self):
        """ATR should compute without errors."""
        candles = generate_bullish_trend_ohlcv(100)
        df = candles_to_df(candles)

        atr = compute_atr(df, period=14)

        assert isinstance(atr, pd.Series)
        assert len(atr) == len(df)

    def test_atr_always_positive(self):
        """ATR must be positive."""
        candles = generate_bullish_trend_ohlcv(100)
        df = candles_to_df(candles)

        atr = compute_atr(df, period=14)
        valid_atr = atr.dropna()

        assert all(val > 0 for val in valid_atr)

    def test_atr_different_periods(self):
        """ATR should work with different periods."""
        candles = generate_bullish_trend_ohlcv(100)
        df = candles_to_df(candles)

        atr_14 = compute_atr(df, period=14)
        atr_21 = compute_atr(df, period=21)

        assert len(atr_14) == len(atr_21)


class TestBollingerBands:
    """Test Bollinger Bands calculations."""

    def test_bollinger_bands_compute_successfully(self):
        """BB should compute three bands."""
        candles = generate_bullish_trend_ohlcv(100)
        df = candles_to_df(candles)

        upper, middle, lower = compute_bollinger_bands(df, period=20, std_dev=2.0)

        assert isinstance(upper, pd.Series)
        assert isinstance(middle, pd.Series)
        assert isinstance(lower, pd.Series)
        assert len(upper) == len(df)

    def test_bollinger_bands_ordered(self):
        """Upper > Middle > Lower."""
        candles = generate_bullish_trend_ohlcv(100)
        df = candles_to_df(candles)

        upper, middle, lower = compute_bollinger_bands(df, period=20)

        # Check last valid values
        for i in range(-10, 0):
            if not (pd.isna(upper.iloc[i]) or pd.isna(middle.iloc[i]) or pd.isna(lower.iloc[i])):
                assert upper.iloc[i] > middle.iloc[i] > lower.iloc[i]


class TestVolumeIndicators:
    """Test volume spike detection."""

    def test_volume_spike_detection(self):
        """Should detect volume spikes."""
        candles = generate_bullish_trend_ohlcv(100)
        df = candles_to_df(candles)

        spikes = detect_volume_spike(df, threshold=2.0, lookback=20)

        assert isinstance(spikes, pd.Series)
        assert len(spikes) == len(df)
        assert spikes.dtype == bool

    def test_volume_spike_returns_booleans(self):
        """Volume spike should return True/False."""
        candles = generate_bullish_trend_ohlcv(50)
        df = candles_to_df(candles)

        spikes = detect_volume_spike(df, threshold=2.0)

        assert all(isinstance(val, (bool, type(pd.NA))) for val in spikes)


class TestIndicatorIntegration:
    """Test indicators working together."""

    def test_all_indicators_from_same_dataframe(self):
        """All indicators should process same DataFrame."""
        candles = generate_bullish_trend_ohlcv(100)
        df = candles_to_df(candles)

        rsi = compute_rsi(df, period=14)
        atr = compute_atr(df, period=14)
        upper, middle, lower = compute_bollinger_bands(df, period=20)
        spikes = detect_volume_spike(df, threshold=2.0)

        # All should have same length
        assert len(rsi) == len(df)
        assert len(atr) == len(df)
        assert len(upper) == len(df)
        assert len(spikes) == len(df)

    def test_indicators_handle_minimal_data(self):
        """Indicators should handle small datasets gracefully."""
        candles = generate_bullish_trend_ohlcv(30)
        df = candles_to_df(candles)

        # Should not crash
        rsi = compute_rsi(df, period=14)
        atr = compute_atr(df, period=14)

        assert len(rsi) == 30
        assert len(atr) == 30
