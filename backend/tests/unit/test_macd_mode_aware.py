"""
Unit tests for mode-aware MACD evaluation.

Tests the different MACD behaviors across scanner modes:
- HTF/Swing modes: MACD as primary decision-maker
- Balanced modes: MACD as weighted confluence
- Scalp/Surgical modes: MACD as HTF context + LTF veto
"""

import pytest
from backend.shared.config.scanner_modes import MACDModeConfig, MACD_MODE_CONFIGS, get_macd_config
from backend.shared.models.indicators import IndicatorSnapshot
from backend.strategy.confluence.scorer import evaluate_macd_for_mode


def make_indicator_snapshot(
    rsi: float = 50.0,
    stoch_rsi: float = 50.0,
    bb_upper: float = 105.0,
    bb_middle: float = 100.0,
    bb_lower: float = 95.0,
    atr: float = 2.0,
    volume_spike: bool = False,
    macd_line: float = 0.001,
    macd_signal: float = 0.0005,
    macd_histogram: float = 0.0005,
    macd_line_series: list = None,
    macd_signal_series: list = None,
    macd_histogram_series: list = None,
) -> IndicatorSnapshot:
    """Helper to create IndicatorSnapshot with MACD data."""
    snapshot = IndicatorSnapshot(
        rsi=rsi,
        stoch_rsi=stoch_rsi,
        bb_upper=bb_upper,
        bb_middle=bb_middle,
        bb_lower=bb_lower,
        atr=atr,
        volume_spike=volume_spike,
    )
    snapshot.macd_line = macd_line
    snapshot.macd_signal = macd_signal
    snapshot.macd_histogram = macd_histogram
    snapshot.macd_line_series = macd_line_series or [0.0008, 0.0009, 0.001, 0.0011, 0.001]
    snapshot.macd_signal_series = macd_signal_series or [0.0004, 0.0004, 0.0005, 0.0005, 0.0005]
    snapshot.macd_histogram_series = macd_histogram_series or [
        0.0004,
        0.0005,
        0.0005,
        0.0006,
        0.0005,
    ]
    return snapshot


class TestMACDModeConfig:
    """Test MACDModeConfig dataclass and mode profiles."""

    def test_all_profiles_have_config(self):
        """Ensure all mode profiles have MACD config."""
        expected_profiles = [
            "macro_surveillance",
            "balanced",
            "intraday_aggressive",
            "precision",
            "stealth_balanced",
        ]
        for profile in expected_profiles:
            assert profile in MACD_MODE_CONFIGS

    def test_get_macd_config_known_profile(self):
        """Test get_macd_config returns correct config for known profile."""
        config = get_macd_config("precision")
        assert config.use_htf_bias is True
        assert config.treat_as_primary is False
        assert config.weight == 0.6
        assert config.min_persistence_bars == 3
        assert config.macd_settings == (24, 52, 9)  # Longer settings for LTF

    def test_get_macd_config_unknown_profile_fallback(self):
        """Test get_macd_config falls back to balanced for unknown profile."""
        config = get_macd_config("unknown_mode")
        balanced_config = MACD_MODE_CONFIGS["balanced"]
        assert config == balanced_config

    def test_macro_surveillance_is_primary(self):
        """Test macro_surveillance mode treats MACD as primary."""
        config = get_macd_config("macro_surveillance")
        assert config.treat_as_primary is True
        assert config.weight == 1.5
        assert config.use_histogram_strict is True
        assert config.allow_ltf_veto is False

    def test_precision_allows_veto(self):
        """Test precision mode allows LTF veto."""
        config = get_macd_config("precision")
        assert config.allow_ltf_veto is True
        assert config.treat_as_primary is False


class TestEvaluateMACDForMode:
    """Test evaluate_macd_for_mode function."""

    def test_bullish_with_bullish_macd_primary_mode(self):
        """Test bullish setup with bullish MACD in primary mode."""
        config = MACDModeConfig(
            use_htf_bias=False,
            treat_as_primary=True,
            min_persistence_bars=3,
            weight=1.5,
            use_histogram_strict=True,
            allow_ltf_veto=False,
        )
        indicators = make_indicator_snapshot(
            macd_line=0.002,
            macd_signal=0.001,
            macd_histogram=0.001,
            macd_line_series=[0.0015, 0.0017, 0.0019, 0.002, 0.002],
            macd_signal_series=[0.0008, 0.0009, 0.001, 0.001, 0.001],
        )

        result = evaluate_macd_for_mode(
            indicators=indicators, direction="bullish", macd_config=config, timeframe="4h"
        )

        assert result["score"] > 0
        assert result["role"] == "PRIMARY"
        assert result["veto_active"] is False
        assert "persistence" in str(result["reasons"]).lower() or "PRIMARY" in str(
            result["reasons"]
        )

    def test_bearish_with_bullish_macd_filter_mode_veto(self):
        """Test bearish setup with bullish MACD triggers veto in filter mode."""
        config = MACDModeConfig(
            use_htf_bias=False,
            treat_as_primary=False,
            min_persistence_bars=2,
            weight=0.6,
            use_histogram_strict=False,
            allow_ltf_veto=True,
        )
        # Bullish MACD (line > signal) with persistence
        indicators = make_indicator_snapshot(
            macd_line=0.002,
            macd_signal=0.001,
            macd_histogram=0.001,
            macd_line_series=[0.0018, 0.0019, 0.002, 0.002, 0.002],
            macd_signal_series=[0.0008, 0.0009, 0.001, 0.001, 0.001],
        )

        result = evaluate_macd_for_mode(
            indicators=indicators,
            direction="bearish",  # Opposing direction
            macd_config=config,
            timeframe="5m",
        )

        assert result["score"] < 0
        assert result["veto_active"] is True
        assert result["role"] == "VETO"

    def test_htf_bias_support(self):
        """Test HTF bias supporting trade direction."""
        config = MACDModeConfig(
            use_htf_bias=True,
            treat_as_primary=False,
            min_persistence_bars=2,
            weight=1.0,
            use_histogram_strict=False,
            allow_ltf_veto=True,
            htf_timeframe="1h",
        )
        # LTF indicators
        ltf_indicators = make_indicator_snapshot(
            macd_line=0.001,
            macd_signal=0.0008,
        )
        # HTF indicators with bullish bias
        htf_indicators = make_indicator_snapshot(
            macd_line=0.005,
            macd_signal=0.003,
        )

        result = evaluate_macd_for_mode(
            indicators=ltf_indicators,
            direction="bullish",
            macd_config=config,
            htf_indicators=htf_indicators,
            timeframe="15m",
        )

        assert result["htf_bias"] == "bullish"
        assert any("HTF" in r for r in result["reasons"])
        assert result["score"] > 0

    def test_htf_bias_conflict(self):
        """Test HTF bias conflicting with trade direction."""
        config = MACDModeConfig(
            use_htf_bias=True,
            treat_as_primary=False,
            min_persistence_bars=2,
            weight=1.0,
            use_histogram_strict=False,
            allow_ltf_veto=True,
        )
        # LTF indicators
        ltf_indicators = make_indicator_snapshot()
        # HTF indicators with bearish bias
        htf_indicators = make_indicator_snapshot(
            macd_line=-0.005,
            macd_signal=-0.003,
        )

        result = evaluate_macd_for_mode(
            indicators=ltf_indicators,
            direction="bullish",  # Trying bullish but HTF is bearish
            macd_config=config,
            htf_indicators=htf_indicators,
            timeframe="15m",
        )

        assert result["htf_bias"] == "bearish"
        # HTF conflict adds penalty but may not push below zero depending on LTF support
        assert any("conflicts" in r.lower() for r in result["reasons"])

    def test_minimum_amplitude_filter(self):
        """Test minimum amplitude filter rejects chop."""
        config = MACDModeConfig(
            use_htf_bias=False,
            treat_as_primary=True,
            min_persistence_bars=2,
            weight=1.0,
            use_histogram_strict=False,
            allow_ltf_veto=False,
            min_amplitude=0.001,  # Require separation > 0.001
        )
        # MACD in chop zone (very small separation)
        indicators = make_indicator_snapshot(
            macd_line=0.0001,
            macd_signal=0.00008,  # Difference < min_amplitude
        )

        result = evaluate_macd_for_mode(
            indicators=indicators, direction="bullish", macd_config=config, timeframe="5m"
        )

        assert result["score"] == 0.0
        assert "chop" in str(result["reasons"]).lower()
        assert result["role"] == "NEUTRAL"

    def test_histogram_strict_expansion(self):
        """Test histogram strict mode rewards expansion."""
        config = MACDModeConfig(
            use_htf_bias=False,
            treat_as_primary=True,
            min_persistence_bars=2,
            weight=1.0,
            use_histogram_strict=True,
            allow_ltf_veto=False,
        )
        # Bullish MACD with expanding histogram
        indicators = make_indicator_snapshot(
            macd_line=0.003,
            macd_signal=0.001,
            macd_histogram=0.002,
            macd_line_series=[0.002, 0.0025, 0.003],
            macd_signal_series=[0.001, 0.001, 0.001],
            macd_histogram_series=[0.001, 0.0015, 0.002],  # Expanding
        )

        result = evaluate_macd_for_mode(
            indicators=indicators, direction="bullish", macd_config=config, timeframe="4h"
        )

        assert result["score"] > 0
        assert any("histogram" in r.lower() for r in result["reasons"])

    def test_no_macd_data_returns_zero(self):
        """Test missing MACD data returns zero score."""
        config = get_macd_config("balanced")
        indicators = IndicatorSnapshot(
            rsi=50.0,
            stoch_rsi=50.0,
            bb_upper=105.0,
            bb_middle=100.0,
            bb_lower=95.0,
            atr=2.0,
            volume_spike=False,
        )
        # No MACD attached

        result = evaluate_macd_for_mode(
            indicators=indicators, direction="bullish", macd_config=config, timeframe="15m"
        )

        assert result["score"] == 0.0
        assert "unavailable" in str(result["reasons"]).lower()

    def test_persistence_tracking(self):
        """Test persistence bars are tracked correctly."""
        config = MACDModeConfig(
            use_htf_bias=False,
            treat_as_primary=True,
            min_persistence_bars=3,
            weight=1.0,
            use_histogram_strict=False,
            allow_ltf_veto=False,
        )
        # 5 bars of bullish MACD (line > signal)
        indicators = make_indicator_snapshot(
            macd_line=0.003,
            macd_signal=0.001,
            macd_line_series=[0.002, 0.0022, 0.0025, 0.0028, 0.003],
            macd_signal_series=[0.001, 0.001, 0.001, 0.001, 0.001],
        )

        result = evaluate_macd_for_mode(
            indicators=indicators, direction="bullish", macd_config=config, timeframe="1h"
        )

        assert result["persistent_bars"] >= 3


class TestMACDModeIntegration:
    """Integration tests for MACD across different scanner mode profiles."""

    def test_overwatch_mode_primary_behavior(self):
        """Test overwatch (macro_surveillance) uses MACD as primary."""
        config = get_macd_config("macro_surveillance")

        # Strong bullish MACD
        indicators = make_indicator_snapshot(
            macd_line=0.01,
            macd_signal=0.005,
            macd_histogram=0.005,
            macd_line_series=[0.008, 0.009, 0.0095, 0.01, 0.01],
            macd_signal_series=[0.004, 0.0045, 0.005, 0.005, 0.005],
        )

        result = evaluate_macd_for_mode(
            indicators=indicators, direction="bullish", macd_config=config, timeframe="4h"
        )

        # High score expected due to primary mode + persistence
        assert result["score"] > 30  # Significant positive impact
        assert result["role"] == "PRIMARY"

    def test_surgical_mode_veto_behavior(self):
        """Test surgical (precision) uses MACD as filter with veto."""
        config = get_macd_config("precision")

        # Strong bearish MACD
        indicators = make_indicator_snapshot(
            macd_line=-0.003,
            macd_signal=-0.001,
            macd_histogram=-0.002,
            macd_line_series=[-0.002, -0.0025, -0.003, -0.003, -0.003],
            macd_signal_series=[-0.0008, -0.0009, -0.001, -0.001, -0.001],
        )

        result = evaluate_macd_for_mode(
            indicators=indicators,
            direction="bullish",  # Trying bullish against bearish MACD
            macd_config=config,
            timeframe="5m",
        )

        # Should activate veto and negative score
        assert result["veto_active"] is True
        assert result["score"] < 0
        assert result["role"] == "VETO"

    def test_balanced_mode_weighted_behavior(self):
        """Test balanced mode uses MACD as weighted confluence."""
        config = get_macd_config("balanced")

        # Moderate bullish MACD
        indicators = make_indicator_snapshot(
            macd_line=0.002,
            macd_signal=0.001,
            macd_line_series=[0.0015, 0.0018, 0.002],
            macd_signal_series=[0.0008, 0.0009, 0.001],
        )

        result = evaluate_macd_for_mode(
            indicators=indicators, direction="bullish", macd_config=config, timeframe="1h"
        )

        # Moderate positive score, not primary
        assert result["score"] > 0
        assert result["score"] < 25  # Not as high as primary mode
        assert result["role"] == "FILTER"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
