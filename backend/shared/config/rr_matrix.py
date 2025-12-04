"""
Risk:Reward Validation Matrix

Defines tiered R:R thresholds based on plan type, mode profile, and conviction class.
Allows different quality standards for SMC-based plans vs ATR fallback plans.
Also supports mode-aware thresholds (scalp vs swing horizons).
"""
from typing import Dict, Literal, Optional
from dataclasses import dataclass


@dataclass(frozen=True)
class RRThreshold:
    """R:R threshold configuration for a plan type"""
    plan_type: Literal["SMC", "ATR_FALLBACK", "HYBRID"]
    min_rr: float
    ideal_rr: float
    description: str


# Base R:R validation matrix (production-ready values - TUNED for stricter quality)
RR_MATRIX: Dict[str, RRThreshold] = {
    
    "SMC": RRThreshold(
        plan_type="SMC",
        min_rr=1.5,
        ideal_rr=2.5,
        description="Structure-based entry/stop from order blocks, FVGs, or structural breaks"
    ),
    
    "ATR_FALLBACK": RRThreshold(
        plan_type="ATR_FALLBACK",
        min_rr=1.5,       # TUNED: was 1.0 - force better R:R when no structure
        ideal_rr=2.0,     # TUNED: was 1.8 - higher ideal for fallback plans
        description="ATR-based entry/stop when clear SMC structure unavailable"
    ),
    
    "HYBRID": RRThreshold(
        plan_type="HYBRID",
        min_rr=1.2,       # TUNED: was 0.9 - raise floor for mixed plans
        ideal_rr=2.0,
        description="Mixed SMC structure + ATR-based components"
    ),
}

# Mode-specific R:R adjustments (profile-aware)
MODE_RR_MULTIPLIERS: Dict[str, tuple[float, float]] = {
    "precision": (1.0, 1.0),           # surgical: default strict
    "intraday_aggressive": (0.85, 0.9),  # strike: slightly looser for scalps
    "balanced": (1.0, 1.0),            # recon: default
    "macro_surveillance": (1.1, 1.15),  # overwatch: tighter for swings
    "stealth_balanced": (1.0, 1.0),    # ghost: default
}


def get_rr_threshold(
    plan_type: Literal["SMC", "ATR_FALLBACK", "HYBRID"],
    mode_profile: Optional[str] = None
) -> RRThreshold:
    """
    Get the mode-aware R:R validation threshold for a plan type.
    
    Args:
        plan_type: Type of trade plan (SMC, ATR_FALLBACK, HYBRID)
        mode_profile: Scanner mode profile for threshold adjustments
            - precision (surgical): strictest thresholds
            - intraday_aggressive (strike): looser for scalps (0.85x min, 0.9x ideal)
            - macro_surveillance (overwatch): tighter for swings (1.1x min, 1.15x ideal)
            - balanced/stealth_balanced: default thresholds
        
    Returns:
        RRThreshold configuration with mode-adjusted values
    """
    base_threshold = RR_MATRIX.get(plan_type, RR_MATRIX["SMC"])
    
    # Apply mode multipliers if profile provided
    if mode_profile and mode_profile in MODE_RR_MULTIPLIERS:
        min_mult, ideal_mult = MODE_RR_MULTIPLIERS[mode_profile]
        return RRThreshold(
            plan_type=base_threshold.plan_type,
            min_rr=base_threshold.min_rr * min_mult,
            ideal_rr=base_threshold.ideal_rr * ideal_mult,
            description=base_threshold.description
        )
    
    return base_threshold


def classify_conviction(
    plan_type: Literal["SMC", "ATR_FALLBACK", "HYBRID"],
    risk_reward: float,
    confluence_score: float,
    has_all_critical_tfs: bool,
    mode_profile: Optional[str] = None
) -> Literal["A", "B", "C"]:
    """
    Classify conviction class based on plan quality using band-based logic.
    
    Conviction Classes (Quality Bands):
    - A: Best of best - SMC structure + ideal R:R + high confluence + complete data
    - B: Close to ideal OR decent confluence - allows good ATR_FALLBACK plans
    - C: Barely acceptable - meets minimum thresholds but nothing special
    
    ATR_FALLBACK plans are capped at B (can be good, but never A-tier without structure).
    
    Args:
        plan_type: How plan was generated (SMC/HYBRID/ATR_FALLBACK)
        risk_reward: R:R ratio
        confluence_score: Total confluence score (0-100)
        has_all_critical_tfs: Whether all critical timeframes loaded
        mode_profile: Scanner mode profile for threshold adjustments
        
    Returns:
        Conviction class: A (best), B (good), C (acceptable)
    """
    threshold = get_rr_threshold(plan_type, mode_profile)
    
    # Class A: Best of best (requires SMC structure)
    # - Perfect plan type + ideal R:R + high confluence + complete data
    if (
        plan_type == "SMC" and
        risk_reward >= threshold.ideal_rr and
        confluence_score >= 80.0 and
        has_all_critical_tfs
    ):
        return "A"
    
    # Class B: Close to ideal (allows good ATR_FALLBACK)
    # - R:R near ideal (≥80% of ideal) + decent confluence (≥65)
    # - OR strong structure (SMC/HYBRID) with decent R:R
    rr_near_ideal = risk_reward >= (threshold.ideal_rr * 0.8)
    decent_confluence = confluence_score >= 65.0
    
    if rr_near_ideal and decent_confluence:
        return "B"
    
    if plan_type in ("SMC", "HYBRID") and risk_reward >= threshold.min_rr and decent_confluence:
        return "B"
    
    # ATR_FALLBACK cap: can be B if decent, but never A
    if plan_type == "ATR_FALLBACK" and risk_reward >= threshold.min_rr and confluence_score >= 60.0:
        return "B"
    
    # Class C: Barely acceptable
    # - Meets minimum thresholds but nothing special
    return "C"


def validate_rr(
    plan_type: Literal["SMC", "ATR_FALLBACK", "HYBRID"],
    risk_reward: float,
    mode_profile: Optional[str] = None,
    expected_value: Optional[float] = None,
    confluence_score: Optional[float] = None
) -> tuple[bool, str]:
    """
    Validate R:R ratio against plan type threshold with EV-based override.
    
    Single source of truth for R:R validation - all other components should
    delegate to this function rather than implementing their own thresholds.
    
    EV Override Logic:
    - If expected_value provided and > 0.02 (positive expected value)
    - AND confluence_score >= 70 (strong confluence)
    - Allow R:R down to 0.75 (25% below standard minimum)
    
    Args:
        plan_type: Plan classification (SMC/HYBRID/ATR_FALLBACK)
        risk_reward: Calculated R:R ratio
        mode_profile: Scanner mode profile for threshold adjustments
        expected_value: Optional computed EV for override consideration
        confluence_score: Optional confluence score for override gating
        
    Returns:
        Tuple of (is_valid, reason_if_invalid)
    """
    threshold = get_rr_threshold(plan_type, mode_profile)
    
    # Standard validation
    if risk_reward >= threshold.min_rr:
        return True, ""
    
    # EV-based override for borderline cases
    if (
        expected_value is not None and
        confluence_score is not None and
        expected_value > 0.02 and
        confluence_score >= 70.0 and
        risk_reward >= 0.75  # Hard floor (75% of typical minimum)
    ):
        return True, f"EV override: R:R {risk_reward:.2f} < {threshold.min_rr:.2f} but EV={expected_value:.3f} with {confluence_score:.1f}% confluence"
    
    reason = (
        f"R:R {risk_reward:.2f} below {plan_type} minimum {threshold.min_rr:.2f}. "
        f"{threshold.description}."
    )
    return False, reason


def calculate_implied_pwin(risk_reward: float, target_ev: float = 0.0) -> float:
    """
    Calculate implied win probability needed for target EV given R:R.
    
    EV formula: EV = p_win * R - (1 - p_win) * 1
    Solving for p_win: p_win = (EV + 1) / (R + 1)
    
    Args:
        risk_reward: R:R ratio
        target_ev: Target expected value (default 0 for breakeven)
        
    Returns:
        Implied win probability (0.0 to 1.0)
    """
    if risk_reward <= 0:
        return 1.0  # Need 100% win rate for zero/negative R:R
    
    p_win = (target_ev + 1.0) / (risk_reward + 1.0)
    return max(0.0, min(1.0, p_win))  # Clamp to valid probability range


def get_conviction_behavior_guide() -> Dict[str, Dict[str, str]]:
    """
    Guide for how conviction class should influence behavior across the system.
    
    Conviction should modulate:
    - Target spacing (A: aggressive ladders, C: conservative single targets)
    - Position sizing (A: full allocation, C: reduced size)
    - Entry patience (A: wait for perfect entry, C: accept wider zones)
    - Gate strictness (A: pass all gates, C: borderline may slip through)
    
    Returns:
        Nested dict mapping conviction class to behavior dimensions
    """
    return {
        "A": {
            "target_spacing": "Aggressive ladder - 3+ targets with tight spacing",
            "position_sizing": "Full mode allocation (up to max account %)",
            "entry_patience": "Wait for premium entry within tight zone",
            "gate_strictness": "Must pass all quality gates with margin",
            "hold_behavior": "Hold through noise, conviction-driven exits only",
        },
        "B": {
            "target_spacing": "Balanced ladder - 2-3 targets, moderate spacing",
            "position_sizing": "75% of mode allocation",
            "entry_patience": "Accept mid-zone entries, don't chase extremes",
            "gate_strictness": "Pass standard gates, minor violations acceptable",
            "hold_behavior": "Manage actively, respect technical exits",
        },
        "C": {
            "target_spacing": "Conservative - single target or minimal ladder",
            "position_sizing": "50% of mode allocation (test position)",
            "entry_patience": "Accept wider entry zones, don't force precision",
            "gate_strictness": "Borderline passes allowed if other factors strong",
            "hold_behavior": "Exit quickly on adverse signals, tight leash",
        },
    }
