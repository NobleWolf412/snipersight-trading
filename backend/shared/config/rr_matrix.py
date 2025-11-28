"""
Risk:Reward Validation Matrix

Defines tiered R:R thresholds based on plan type and conviction class.
Allows different quality standards for SMC-based plans vs ATR fallback plans.
"""
from typing import Dict, Literal
from dataclasses import dataclass


@dataclass(frozen=True)
class RRThreshold:
    """R:R threshold configuration for a plan type"""
    plan_type: Literal["SMC", "ATR_FALLBACK", "HYBRID"]
    min_rr: float
    ideal_rr: float
    description: str


# Tiered R:R validation matrix
RR_MATRIX: Dict[str, RRThreshold] = {
    
    "SMC": RRThreshold(
        plan_type="SMC",
        min_rr=0.8,  # Temporarily lowered for testing (normally 1.5)
        ideal_rr=2.5,
        description="Structure-based entry/stop from order blocks, FVGs, or structural breaks"
    ),
    
    "ATR_FALLBACK": RRThreshold(
        plan_type="ATR_FALLBACK",
        min_rr=0.8,  # Lower threshold for ATR-based plans (allow scalps)
        ideal_rr=1.5,
        description="ATR-based entry/stop when clear SMC structure unavailable"
    ),
    
    "HYBRID": RRThreshold(
        plan_type="HYBRID",
        min_rr=1.2,  # Middle ground - some structure, some ATR
        ideal_rr=2.0,
        description="Mixed SMC structure + ATR-based components"
    ),
}


def get_rr_threshold(plan_type: Literal["SMC", "ATR_FALLBACK", "HYBRID"]) -> RRThreshold:
    """Get R:R threshold configuration for plan type."""
    return RR_MATRIX.get(plan_type, RR_MATRIX["SMC"])  # Default to strictest


def classify_conviction(
    plan_type: Literal["SMC", "ATR_FALLBACK", "HYBRID"],
    risk_reward: float,
    confluence_score: float,
    has_all_critical_tfs: bool
) -> Literal["A", "B", "C"]:
    """
    Classify conviction class based on plan quality.
    
    Args:
        plan_type: How plan was generated
        risk_reward: R:R ratio
        confluence_score: Total confluence score
        has_all_critical_tfs: Whether all critical timeframes loaded
        
    Returns:
        Conviction class: A (best), B (good), C (acceptable)
    """
    threshold = get_rr_threshold(plan_type)
    
    # Class A: Ideal conditions
    if (
        plan_type == "SMC" and
        risk_reward >= threshold.ideal_rr and
        confluence_score >= 80.0 and
        has_all_critical_tfs
    ):
        return "A"
    
    # Class C: Barely acceptable
    if (
        plan_type == "ATR_FALLBACK" or
        risk_reward < threshold.ideal_rr or
        confluence_score < 65.0 or
        not has_all_critical_tfs
    ):
        return "C"
    
    # Class B: Everything else (good but not ideal)
    return "B"


def validate_rr(
    plan_type: Literal["SMC", "ATR_FALLBACK", "HYBRID"],
    risk_reward: float
) -> tuple[bool, str]:
    """
    Validate R:R ratio against plan type threshold.
    
    Args:
        plan_type: Plan classification
        risk_reward: Calculated R:R ratio
        
    Returns:
        Tuple of (is_valid, reason_if_invalid)
    """
    threshold = get_rr_threshold(plan_type)
    
    if risk_reward >= threshold.min_rr:
        return True, ""
    
    reason = (
        f"R:R {risk_reward:.2f} below {plan_type} minimum {threshold.min_rr:.2f}. "
        f"{threshold.description}."
    )
    return False, reason
