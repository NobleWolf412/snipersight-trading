"""
Regime Policies - Mode-specific regime handling

Defines how each scanner mode responds to market regimes.
"""
from typing import Dict
from backend.shared.models.regime import RegimePolicy

# Per-mode regime policies
REGIME_POLICIES: Dict[str, RegimePolicy] = {
    
    "overwatch": RegimePolicy(
        mode_name="overwatch",
        min_regime_score=60.0,  # Conservative - need good conditions
        allow_in_risk_off=False,  # Only trade during risk_on
        position_size_adjustment={
            "strong_up": 1.2,  # Increase size in strong trends
            "up": 1.1,
            "sideways": 0.8,  # Reduce size in chop
            "down": 0.6,
            "strong_down": 0.0,  # No longs in strong downtrend
        },
        confluence_adjustment={
            # Boost confluence in good regimes
            "bullish_risk_on": 5.0,
            "strong_up_normal": 3.0,
            "choppy_risk_off": -10.0,  # Penalize chop
            "chaotic_volatile": -15.0,
        },
        rr_adjustment={
            # Tighten targets in choppy regimes, extend in trends
            "sideways": 0.8,  # Lower R:R acceptable
            "strong_up": 1.3,  # Can push for higher targets
            "chaotic_volatile": 0.7,
        }
    ),
    
    "recon": RegimePolicy(
        mode_name="recon",
        min_regime_score=45.0,  # Adjusted to 45 (was 50) to capture 'normal' 47.0 regimes
        allow_in_risk_off=True,  # Can trade both directions
        position_size_adjustment={
            "strong_up": 1.1,
            "up": 1.0,
            "sideways": 0.9,
            "down": 1.0,  # Can short
            "strong_down": 1.1,  # Bigger size in strong shorts
        },
        confluence_adjustment={
            "bullish_risk_on": 3.0,
            "bearish_risk_off": 3.0,  # Reward both trends
            "choppy_risk_off": -5.0,
            "chaotic_volatile": -10.0,
        },
        rr_adjustment={
            "sideways": 0.9,
            "strong_up": 1.2,
            "strong_down": 1.2,
            "chaotic_volatile": 0.8,
        }
    ),
    
    "strike": RegimePolicy(
        mode_name="strike",
        min_regime_score=40.0,  # Aggressive - can trade most conditions
        allow_in_risk_off=True,
        position_size_adjustment={
            "strong_up": 1.3,  # Maximize strong moves
            "up": 1.1,
            "sideways": 1.0,  # Will scalp ranges
            "down": 1.1,
            "strong_down": 1.3,
        },
        confluence_adjustment={
            "bullish_risk_on": 2.0,
            "bearish_risk_off": 2.0,
            "range_coiling": 5.0,  # Love compressed ranges (breakout setups)
            "chaotic_volatile": -8.0,
        },
        rr_adjustment={
            "sideways": 1.0,  # Accept lower R:R for scalps
            "strong_up": 1.4,
            "strong_down": 1.4,
            "compressed": 1.2,  # Coils can deliver
        }
    ),
    
    "surgical": RegimePolicy(
        mode_name="surgical",
        min_regime_score=30.0,  # Very aggressive - trades anything
        allow_in_risk_off=True,
        position_size_adjustment={
            "strong_up": 1.5,  # Max size in clear setups
            "up": 1.2,
            "sideways": 1.1,
            "down": 1.2,
            "strong_down": 1.5,
        },
        confluence_adjustment={
            # Less regime-dependent, more setup-driven
            "bullish_risk_on": 1.0,
            "bearish_risk_off": 1.0,
            "chaotic_volatile": -5.0,  # Still avoid chaos
        },
        rr_adjustment={
            "sideways": 1.1,
            "strong_up": 1.5,
            "strong_down": 1.5,
            "compressed": 1.3,
        }
    ),
    

}


def get_regime_policy(mode_name: str) -> RegimePolicy:
    """Get regime policy for scanner mode."""
    return REGIME_POLICIES.get(
        mode_name,
        # Default fallback policy
        RegimePolicy(
            mode_name=mode_name,
            min_regime_score=50.0,
            allow_in_risk_off=True,
            position_size_adjustment={},
            confluence_adjustment={},
            rr_adjustment={}
        )
    )
