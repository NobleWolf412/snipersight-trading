"""
Confluence scoring models.

This module defines the data structures for multi-factor confluence scoring,
which aggregates signals from structure, momentum, volatility, volume, and
regime analysis to produce a unified setup quality score.
"""

from dataclasses import dataclass, field
from typing import List, Literal, Optional


@dataclass
class ConfluenceFactor:
    """
    Individual confluence factor contribution.
    
    Represents a single scoring dimension (e.g., structure alignment,
    momentum confirmation, volatility conditions).
    
    Attributes:
        name: Factor identifier (e.g., 'structure', 'momentum', 'volume')
        score: Raw score for this factor (0-100)
        weight: Importance weight (0-1, sum of all weights = 1)
        rationale: Human-readable explanation of the score
    """
    name: str
    score: float
    weight: float
    rationale: str
    
    def __post_init__(self):
        """Validate confluence factor data."""
        if not self.name:
            raise ValueError("Factor name cannot be empty")
        if not 0 <= self.score <= 100:
            raise ValueError(f"Score must be 0-100, got {self.score}")
        if not 0 <= self.weight <= 1:
            raise ValueError(f"Weight must be 0-1, got {self.weight}")
        if not self.rationale:
            raise ValueError("Rationale cannot be empty")
    
    @property
    def weighted_score(self) -> float:
        """Calculate weighted contribution to total score."""
        return self.score * self.weight


@dataclass
class ConfluenceBreakdown:
    """
    Complete confluence scoring breakdown.
    
    Aggregates multiple ConfluenceFactors with synergy bonuses and
    conflict penalties to produce a final setup quality score.
    
    Attributes:
        total_score: Final confluence score (0-100)
        factors: List of individual ConfluenceFactor contributions
        synergy_bonus: Bonus points for aligned factors (0-10)
        conflict_penalty: Deduction for conflicting signals (0-20)
        regime: Market regime classification
        htf_aligned: Whether setup aligns with higher timeframe trend
        btc_impulse_gate: Whether BTC impulse gate is passed (if enabled)
        weekly_stoch_rsi_gate: DEPRECATED - Always True (kept for backward compat)
        weekly_stoch_rsi_bonus: Weekly StochRSI directional bonus/penalty (-10 to +15)
    """
    total_score: float
    factors: List[ConfluenceFactor]
    synergy_bonus: float
    conflict_penalty: float
    regime: Literal["trend", "range", "risk_on", "risk_off", "choppy", "unknown"]
    htf_aligned: bool
    btc_impulse_gate: bool
    weekly_stoch_rsi_gate: bool = True  # DEPRECATED - always True now
    weekly_stoch_rsi_bonus: float = 0.0  # NEW - directional bonus/penalty
    # Optional HTF proximity context (for transparency in UI/telemetry)
    htf_proximity_atr: Optional[float] = None
    htf_proximity_pct: Optional[float] = None
    nearest_htf_level_timeframe: Optional[str] = None
    nearest_htf_level_type: Optional[Literal['support','resistance']] = None
    
    def __post_init__(self):
        """Validate confluence breakdown data."""
        if not 0 <= self.total_score <= 100:
            raise ValueError(f"Total score must be 0-100, got {self.total_score}")
        if not self.factors:
            raise ValueError("Confluence breakdown must have at least one factor")
        if not 0 <= self.synergy_bonus <= 10:
            raise ValueError(f"Synergy bonus must be 0-10, got {self.synergy_bonus}")
        if not 0 <= self.conflict_penalty <= 20:
            raise ValueError(f"Conflict penalty must be 0-20, got {self.conflict_penalty}")
        
        # Validate factor weights sum to approximately 1.0
        total_weight = sum(f.weight for f in self.factors)
        if not 0.99 <= total_weight <= 1.01:  # Allow small floating point error
            raise ValueError(
                f"Factor weights must sum to 1.0, got {total_weight}. "
                f"Factors: {[(f.name, f.weight) for f in self.factors]}"
            )
    
    def get_factor(self, name: str) -> ConfluenceFactor:
        """Get a specific factor by name."""
        for factor in self.factors:
            if factor.name == name:
                return factor
        raise KeyError(f"Factor '{name}' not found in confluence breakdown")
    
    def has_factor(self, name: str) -> bool:
        """Check if a factor exists."""
        return any(f.name == name for f in self.factors)
    
    @property
    def base_score(self) -> float:
        """Calculate base score before bonuses/penalties."""
        return sum(f.weighted_score for f in self.factors)
    
    @property
    def is_high_quality(self) -> bool:
        """Check if this is a high-quality setup (score >= 75)."""
        return self.total_score >= 75
    
    @property
    def passes_quality_gate(self, min_score: float = 65.0) -> bool:
        """Check if setup passes minimum quality threshold."""
        return self.total_score >= min_score
    
    def get_rationale_summary(self) -> str:
        """Generate a summary of all factor rationales."""
        lines = [f"Total Score: {self.total_score:.1f}/100"]
        lines.append(f"Regime: {self.regime.upper()}")
        lines.append(f"HTF Aligned: {'✓' if self.htf_aligned else '✗'}")
        lines.append(f"BTC Impulse Gate: {'✓' if self.btc_impulse_gate else '✗'}")
        lines.append(f"Weekly StochRSI Gate: {'✓' if self.weekly_stoch_rsi_gate else '✗'}")
        lines.append("")
        lines.append("Factor Breakdown:")
        
        for factor in sorted(self.factors, key=lambda f: f.weighted_score, reverse=True):
            lines.append(
                f"  • {factor.name.upper()}: {factor.score:.1f} "
                f"(weight: {factor.weight:.2f}) = {factor.weighted_score:.1f}"
            )
            lines.append(f"    {factor.rationale}")
        
        lines.append("")
        lines.append(f"Synergy Bonus: +{self.synergy_bonus:.1f}")
        lines.append(f"Conflict Penalty: -{self.conflict_penalty:.1f}")
        
        return "\n".join(lines)
