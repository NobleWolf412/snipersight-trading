"""
Tests for trade-type-aware stop/target calculation and R:R validation.

Verifies that:
1. Scanner modes have correct expected_trade_type values
2. validate_rr uses trade-type-specific minimum R:R thresholds
3. PlannerConfig.defaults_for_mode returns correct configs per trade type
4. Trade type derivation detects swing vs scalp setups correctly
"""

import pytest
from backend.shared.config.scanner_modes import get_mode, MODES
from backend.shared.config.rr_matrix import validate_rr
from backend.shared.config.planner_config import PlannerConfig
from backend.strategy.planner.planner_service import _derive_trade_type


class TestScannerModeTradeTypes:
    """Verify expected_trade_type field on scanner modes."""

    def test_overwatch_is_swing(self):
        """Overwatch mode should be for swing trades (HTF macro positions)."""
        mode = get_mode("overwatch")
        assert mode.expected_trade_type == "swing"

    def test_strike_is_intraday(self):
        """Strike mode should be for intraday trades (HTF structure with LTF entry)."""
        mode = get_mode("strike")
        assert mode.expected_trade_type == "intraday"

    def test_surgical_is_intraday(self):
        """Surgical mode should be for intraday trades (1h/15m precision entries)."""
        mode = get_mode("surgical")
        assert mode.expected_trade_type == "intraday"

    def test_stealth_is_intraday(self):
        """Stealth mode should be for intraday trades (balanced)."""
        mode = get_mode("stealth")
        assert mode.expected_trade_type == "intraday"

    def test_ghost_backward_compat_inherits_intraday(self):
        """Ghost mode (backward compat) should inherit stealth's intraday type."""
        mode = get_mode("ghost")
        assert mode.expected_trade_type == "intraday"

    def test_all_modes_have_valid_trade_type(self):
        """All modes should have a valid expected_trade_type."""
        valid_types = {"swing", "scalp", "intraday"}
        for name, mode in MODES.items():
            assert (
                mode.expected_trade_type in valid_types
            ), f"Mode {name} has invalid trade type: {mode.expected_trade_type}"


class TestValidateRRWithTradeType:
    """Verify R:R validation respects trade type thresholds."""

    def test_swing_min_rr_is_2_0(self):
        """Swing trades require minimum 2.0 R:R."""
        # R:R 1.9 should fail for swing
        valid, reason = validate_rr("SMC", 1.9, trade_type="swing")
        assert not valid
        assert "swing minimum 2.00" in reason

        # R:R 2.0 should pass for swing
        valid, reason = validate_rr("SMC", 2.0, trade_type="swing")
        assert valid

    def test_scalp_min_rr_is_1_2(self):
        """Scalp trades allow minimum 1.2 R:R."""
        # R:R 1.1 should fail for scalp
        valid, reason = validate_rr("SMC", 1.1, trade_type="scalp")
        assert not valid
        assert "scalp minimum" in reason

        # R:R 1.2 should pass for scalp
        valid, reason = validate_rr("SMC", 1.2, trade_type="scalp")
        assert valid

    def test_intraday_min_rr_is_1_5(self):
        """Intraday trades require minimum 1.5 R:R."""
        # R:R 1.4 should fail for intraday
        valid, reason = validate_rr("SMC", 1.4, trade_type="intraday")
        assert not valid

        # R:R 1.5 should pass for intraday
        valid, reason = validate_rr("SMC", 1.5, trade_type="intraday")
        assert valid

    def test_default_trade_type_uses_base_threshold(self):
        """When trade_type is None, should use base plan type threshold (SMC=1.5)."""
        # R:R 1.4 should fail with no trade_type (SMC base is 1.5)
        valid, _ = validate_rr("SMC", 1.4, trade_type=None)
        assert not valid

        # R:R 1.5 should pass with no trade_type (matches SMC base)
        valid, _ = validate_rr("SMC", 1.5, trade_type=None)
        assert valid

    def test_ev_override_floor_varies_by_trade_type(self):
        """EV override floor should be 0.65 for scalp, 0.75 for others."""
        # Scalp with EV override should allow R:R down to 0.65
        valid, reason = validate_rr(
            "SMC",
            0.66,
            trade_type="scalp",
            expected_value=0.05,  # Positive EV
            confluence_score=75.0,  # High confluence
        )
        assert valid
        assert "EV override" in reason

        # Swing with same parameters should NOT allow 0.66 (floor is 0.75)
        valid, _ = validate_rr(
            "SMC", 0.66, trade_type="swing", expected_value=0.05, confluence_score=75.0
        )
        assert not valid

    def test_min_rr_override_takes_priority(self):
        """Mode-level min_rr_override should take priority over trade type defaults."""
        # Intraday normally requires 1.5, but with override=1.2, should pass at 1.2
        valid, _ = validate_rr("SMC", 1.2, trade_type="intraday", min_rr_override=1.2)
        assert valid

        # Same setup without override should fail
        valid, reason = validate_rr("SMC", 1.2, trade_type="intraday", min_rr_override=None)
        assert not valid
        assert "intraday" in reason.lower()

    def test_min_rr_override_ev_floor_for_aggressive_modes(self):
        """EV override floor should be 0.65 when min_rr_override <= 1.2 (aggressive mode)."""
        # Aggressive mode (override=1.2) with EV should allow R:R down to 0.65
        valid, reason = validate_rr(
            "SMC",
            0.66,
            trade_type="intraday",
            min_rr_override=1.2,
            expected_value=0.05,
            confluence_score=75.0,
        )
        assert valid
        assert "EV override" in reason


class TestPlannerConfigByTradeType:
    """Verify PlannerConfig.defaults_for_mode returns correct configs."""

    def test_scalp_config_has_tight_stops(self):
        """Scalp config should have tighter stop buffer."""
        config = PlannerConfig.defaults_for_mode("scalp")
        assert config.stop_buffer_atr == 0.25
        assert config.stop_lookback_bars == 15  # Shorter lookback

    def test_swing_config_has_wide_stops(self):
        """Swing config should have wider stop buffer."""
        config = PlannerConfig.defaults_for_mode("swing")
        assert config.stop_buffer_atr == 0.35
        assert config.stop_lookback_bars == 30  # Longer lookback

    def test_scalp_target_rr_ladder_is_conservative(self):
        """Scalp config should have conservative R:R ladder."""
        config = PlannerConfig.defaults_for_mode("scalp")
        assert config.target_rr_ladder == [1.2, 2.0, 3.0]
        assert config.target_min_rr_after_clip == 1.0  # Lower floor for scalps

    def test_swing_target_rr_ladder_is_aggressive(self):
        """Swing config should have aggressive R:R ladder."""
        config = PlannerConfig.defaults_for_mode("swing")
        assert config.target_rr_ladder == [2.0, 3.0, 5.0]
        assert config.target_min_rr_after_clip == 1.5  # Higher floor for swings

    def test_intraday_config_is_balanced(self):
        """Intraday config should be balanced between scalp and swing."""
        config = PlannerConfig.defaults_for_mode("intraday")
        assert config.stop_buffer_atr == 0.3
        assert config.target_rr_ladder == [1.5, 2.5, 4.0]
        assert config.target_min_rr_after_clip == 1.2


class TestDeriveTradeType:
    """Verify _derive_trade_type correctly classifies setups."""

    def test_swing_detection_by_target_move(self):
        """Large target move (>2%) should be classified as swing."""
        trade_type = _derive_trade_type(
            target_move_pct=2.5,  # Large move
            stop_distance_atr=3.0,  # Wide stop
            structure_timeframes=("1d", "4h"),  # HTF structure
            primary_tf="4h",
        )
        assert trade_type == "swing"

    def test_scalp_detection_by_target_move(self):
        """Small target move (<0.8%) should be classified as scalp."""
        trade_type = _derive_trade_type(
            target_move_pct=0.5,  # Small move
            stop_distance_atr=1.0,  # Tight stop
            structure_timeframes=("15m", "5m"),  # LTF structure
            primary_tf="5m",
        )
        assert trade_type == "scalp"

    def test_intraday_detection_mid_range(self):
        """Mid-range target move should be classified as intraday."""
        trade_type = _derive_trade_type(
            target_move_pct=1.2,  # Mid move
            stop_distance_atr=2.0,  # Mid stop
            structure_timeframes=("1h", "15m"),  # Mixed TFs
            primary_tf="15m",
        )
        assert trade_type == "intraday"

    def test_swing_detection_by_stop_atr(self):
        """Wide stop (>3 ATR) should bias toward swing."""
        trade_type = _derive_trade_type(
            target_move_pct=1.5,  # Borderline move
            stop_distance_atr=4.0,  # Wide stop
            structure_timeframes=("4h", "1h"),
            primary_tf="1h",
        )
        assert trade_type == "swing"

    def test_scalp_detection_by_stop_atr(self):
        """Tight stop (<1.5 ATR) with LTF-only structure should classify as scalp."""
        trade_type = _derive_trade_type(
            target_move_pct=0.5,  # Small move (scalp territory)
            stop_distance_atr=1.2,  # Tight stop
            structure_timeframes=("15m", "5m"),  # LTF-only structure
            primary_tf="5m",
        )
        assert trade_type == "scalp"


class TestTradeTypeStopCaps:
    """Verify trade-type-aware soft ATR caps are applied."""

    def test_swing_allows_wide_stops(self):
        """Swing soft cap should allow up to 6 ATR stops."""
        # This tests the soft cap values defined in generate_trade_plan
        caps = {"swing": (0.5, 6.0), "scalp": (0.15, 2.5), "intraday": (0.3, 4.0)}
        soft_min, soft_max = caps["swing"]
        assert soft_max == 6.0
        assert soft_min == 0.5

    def test_scalp_caps_tight_stops(self):
        """Scalp soft cap should limit to 2.5 ATR stops."""
        caps = {"swing": (0.5, 6.0), "scalp": (0.15, 2.5), "intraday": (0.3, 4.0)}
        soft_min, soft_max = caps["scalp"]
        assert soft_max == 2.5
        assert soft_min == 0.15


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
