"""
Test HTF gradient bias logic.

Validates linear interpolation of offset factors based on distance to HTF levels.
"""

import pytest
from backend.strategy.planner.planner_service import _calculate_htf_bias_factor
from backend.shared.config.planner_config import PlannerConfig


def test_htf_bias_at_zero_distance():
    """When right on top of HTF level (distance = 0), factor should equal min_factor."""
    
    planner_cfg = PlannerConfig.defaults_for_mode("intraday")
    planner_cfg.htf_bias_offset_min_factor = 0.3
    planner_cfg.htf_bias_max_atr_distance = 1.0
    
    factor = _calculate_htf_bias_factor(distance_atr=0.0, planner_cfg=planner_cfg)
    
    assert factor == pytest.approx(0.3, abs=0.01), \
        f"At distance=0, factor should be min_factor (0.3), got {factor}"


def test_htf_bias_at_max_distance():
    """When at or beyond max distance, factor should equal 1.0 (no offset reduction)."""
    
    planner_cfg = PlannerConfig.defaults_for_mode("intraday")
    planner_cfg.htf_bias_offset_min_factor = 0.3
    planner_cfg.htf_bias_max_atr_distance = 1.0
    
    # At max distance
    factor_at_max = _calculate_htf_bias_factor(distance_atr=1.0, planner_cfg=planner_cfg)
    assert factor_at_max == pytest.approx(1.0, abs=0.01), \
        f"At max distance, factor should be 1.0, got {factor_at_max}"
    
    # Beyond max distance (should clamp to 1.0)
    factor_beyond = _calculate_htf_bias_factor(distance_atr=2.0, planner_cfg=planner_cfg)
    assert factor_beyond == pytest.approx(1.0, abs=0.01), \
        f"Beyond max distance, factor should clamp to 1.0, got {factor_beyond}"


def test_htf_bias_linear_interpolation():
    """Factor should linearly interpolate between min_factor and 1.0."""
    
    planner_cfg = PlannerConfig.defaults_for_mode("intraday")
    planner_cfg.htf_bias_offset_min_factor = 0.2  # 20%
    planner_cfg.htf_bias_max_atr_distance = 1.0
    
    # At midpoint (0.5 ATR), should be midway between 0.2 and 1.0
    # Formula: min_factor + (1.0 - min_factor) * t
    # t = 0.5 / 1.0 = 0.5
    # factor = 0.2 + (1.0 - 0.2) * 0.5 = 0.2 + 0.4 = 0.6
    factor_mid = _calculate_htf_bias_factor(distance_atr=0.5, planner_cfg=planner_cfg)
    assert factor_mid == pytest.approx(0.6, abs=0.01), \
        f"At mid distance, expected 0.6, got {factor_mid}"
    
    # At 0.25 ATR (1/4 of max)
    # t = 0.25 / 1.0 = 0.25
    # factor = 0.2 + 0.8 * 0.25 = 0.2 + 0.2 = 0.4
    factor_quarter = _calculate_htf_bias_factor(distance_atr=0.25, planner_cfg=planner_cfg)
    assert factor_quarter == pytest.approx(0.4, abs=0.01), \
        f"At 1/4 distance, expected 0.4, got {factor_quarter}"
    
    # At 0.75 ATR (3/4 of max)
    # t = 0.75 / 1.0 = 0.75
    # factor = 0.2 + 0.8 * 0.75 = 0.2 + 0.6 = 0.8
    factor_three_quarters = _calculate_htf_bias_factor(distance_atr=0.75, planner_cfg=planner_cfg)
    assert factor_three_quarters == pytest.approx(0.8, abs=0.01), \
        f"At 3/4 distance, expected 0.8, got {factor_three_quarters}"


def test_htf_bias_disabled():
    """When HTF bias is disabled, should always return 1.0."""
    
    planner_cfg = PlannerConfig.defaults_for_mode("intraday")
    planner_cfg.htf_bias_enabled = False
    planner_cfg.htf_bias_offset_min_factor = 0.3
    
    # At any distance, should return 1.0 when disabled
    assert _calculate_htf_bias_factor(0.0, planner_cfg) == 1.0
    assert _calculate_htf_bias_factor(0.5, planner_cfg) == 1.0
    assert _calculate_htf_bias_factor(1.0, planner_cfg) == 1.0
    assert _calculate_htf_bias_factor(2.0, planner_cfg) == 1.0


def test_htf_bias_different_configs():
    """Test behavior with different mode configs (scalp vs swing)."""
    
    # Scalp mode: less aggressive HTF bias (min_factor = 0.4)
    scalp_cfg = PlannerConfig.defaults_for_mode("scalp")
    assert scalp_cfg.htf_bias_offset_min_factor == 0.4
    
    factor_scalp = _calculate_htf_bias_factor(distance_atr=0.0, planner_cfg=scalp_cfg)
    assert factor_scalp == pytest.approx(0.4, abs=0.01)
    
    # Swing mode: more aggressive HTF bias (min_factor = 0.2)
    swing_cfg = PlannerConfig.defaults_for_mode("swing")
    assert swing_cfg.htf_bias_offset_min_factor == 0.2
    
    factor_swing = _calculate_htf_bias_factor(distance_atr=0.0, planner_cfg=swing_cfg)
    assert factor_swing == pytest.approx(0.2, abs=0.01)
    
    # Swing should reduce offsets more aggressively than scalp when near HTF
    assert factor_swing < factor_scalp


def test_htf_bias_negative_distance_handling():
    """Should handle edge case of negative distance (clamp to 0)."""
    
    planner_cfg = PlannerConfig.defaults_for_mode("intraday")
    planner_cfg.htf_bias_offset_min_factor = 0.3
    
    # Negative distance should be treated as 0
    factor = _calculate_htf_bias_factor(distance_atr=-0.5, planner_cfg=planner_cfg)
    assert factor == pytest.approx(0.3, abs=0.01), \
        "Negative distance should clamp to 0, giving min_factor"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
