"""
Trade planning models.

This module defines the complete trade plan structure with entries, stops,
targets, and rationale. Following the "No-Null Outputs" principle, all
TradePlan instances must be fully populated.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Literal, Optional
from .scoring import ConfluenceBreakdown


@dataclass
class EntryZone:
    """
    Dual entry zone specification.
    
    Provides near (aggressive) and far (conservative) entry points
    anchored to structure (order blocks, FVGs).
    
    Attributes:
        near_entry: Aggressive entry at zone boundary
        far_entry: Conservative entry deeper in zone
        rationale: Explanation of entry zone placement
    """
    near_entry: float
    far_entry: float
    rationale: str
    
    def __post_init__(self):
        """Validate entry zone data."""
        if not self.rationale:
            raise ValueError("Entry zone rationale cannot be empty")
        # For longs: far < near (far is lower, deeper in OB)
        # For shorts: far > near (far is higher, deeper in OB)
        # We can't validate direction here, so just ensure they're different
        if self.near_entry == self.far_entry:
            raise ValueError("Near and far entries must be different")
    
    @property
    def zone_size(self) -> float:
        """Calculate size of entry zone."""
        return abs(self.near_entry - self.far_entry)
    
    @property
    def midpoint(self) -> float:
        """Calculate midpoint of entry zone."""
        return (self.near_entry + self.far_entry) / 2


@dataclass
class StopLoss:
    """
    Stop loss specification with structure-based placement.
    
    Stop is placed beyond invalidation level (below bullish OB,
    above bearish OB) with ATR-based buffer.
    
    Attributes:
        level: Stop loss price
        distance_atr: Distance from entry in ATR units
        rationale: Explanation of stop placement
        structure_tf_used: Timeframe of structure used for stop (optional)
    """
    level: float
    distance_atr: float
    rationale: str
    structure_tf_used: Optional[str] = None
    
    def __post_init__(self):
        """Validate stop loss data."""
        if self.level <= 0:
            raise ValueError(f"Stop loss level must be positive, got {self.level}")
        if self.distance_atr <= 0:
            raise ValueError(f"ATR distance must be positive, got {self.distance_atr}")
        if not self.rationale:
            raise ValueError("Stop loss rationale cannot be empty")


@dataclass
class Target:
    """
    Take profit target specification.
    
    Each target includes a price level, percentage of position to close,
    and rationale for placement (structure level, extension, FVG fill).
    
    Attributes:
        level: Target price
        rationale: Explanation of target placement
        percentage: Percentage of position to close (0-100), assigned after creation
        label: Optional short label for display (e.g., "TP1 (2.0R)")
        rr_ratio: Risk-reward ratio at this target level
        weight: Weight/priority for this target (0.0-1.0)
    """
    level: float
    rationale: str
    percentage: float = 0.0  # Assigned after target creation
    label: str = ""  # Optional display label
    rr_ratio: float = 0.0  # R:R ratio at this target
    weight: float = 1.0  # Target priority weight
    
    def __post_init__(self):
        """Validate target data."""
        if self.level <= 0:
            raise ValueError(f"Target level must be positive, got {self.level}")
        # percentage validation moved to TradePlan level
        if not self.rationale:
            raise ValueError("Target rationale cannot be empty")


@dataclass
class TradePlan:
    """
    Complete trade plan with all required fields populated.
    
    This is the core output of the SniperSight pipeline. Following the
    "No-Null Outputs" principle, every field must be populated except metadata.
    
    Attributes:
        symbol: Trading pair (e.g., 'BTC/USDT')
        direction: 'LONG' or 'SHORT'
        setup_type: Trade classification ('Scalp Trade', 'Swing Trade', etc.)
        entry_zone: Entry specification with near/far entries
        stop_loss: Stop loss specification
        targets: List of take profit targets (must have at least 1)
        risk_reward_ratio: Overall R:R ratio (targets weighted by percentage)
        timeframe: Primary timeframe for this trade
        status: Plan status ('PENDING', 'ACTIVE', 'CLOSED')
        trade_type: Derived trade type ('scalp', 'intraday', 'swing')
        confidence_score: Confluence score (0-100)
        confluence_breakdown: Detailed scoring breakdown
        rationale: Multi-paragraph human-readable explanation
        plan_type: How plan was generated (SMC vs ATR fallback vs hybrid)
        conviction_class: Signal quality tier (A=best, B=good, C=acceptable)
        metadata: Optional additional data
        timestamp: When plan was generated
    """
    symbol: str
    direction: Literal["LONG", "SHORT"]
    setup_type: Literal["Scalp Trade", "Day Trade", "Swing Trade", "Position Trade"]
    entry_zone: EntryZone
    stop_loss: StopLoss
    targets: List[Target]
    risk_reward_ratio: float  # Changed from risk_reward for consistency
    timeframe: str = "1h"  # Primary planning timeframe
    status: str = "PENDING"  # Plan status
    trade_type: str = "swing"  # Derived trade type
    confidence_score: float = 0.0
    confluence_breakdown: Optional[ConfluenceBreakdown] = None
    rationale: str = ""
    plan_type: Literal["SMC", "ATR_FALLBACK", "HYBRID"] = "SMC"
    conviction_class: Literal["A", "B", "C"] = "B"
    missing_critical_timeframes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Backward compatibility alias
    @property
    def risk_reward(self) -> float:
        return self.risk_reward_ratio
    
    def __post_init__(self):
        """Validate trade plan completeness."""
        # Required string fields
        if not self.symbol:
            raise ValueError("Symbol cannot be empty")
        # Rationale is now optional (has default)
        
        # Must have at least one target
        if not self.targets:
            raise ValueError("Trade plan must have at least one target")
        
        # Validate target percentages sum to 100
        total_pct = sum(t.percentage for t in self.targets)
        if not 99 <= total_pct <= 101:  # Allow small floating point error
            raise ValueError(
                f"Target percentages must sum to 100, got {total_pct}. "
                f"Targets: {[(t.level, t.percentage) for t in self.targets]}"
            )
        
        # Validate R:R ratio
        if self.risk_reward_ratio < 0:
            raise ValueError(f"Risk:reward ratio must be positive, got {self.risk_reward_ratio}")
        
        # Validate confidence score
        if not 0 <= self.confidence_score <= 100:
            raise ValueError(f"Confidence score must be 0-100, got {self.confidence_score}")
        
        # Validate entries and stops make sense for direction
        if self.direction == "LONG":
            # For longs: entry > stop
            if self.entry_zone.near_entry <= self.stop_loss.level:
                raise ValueError(
                    f"LONG: Entry ({self.entry_zone.near_entry}) must be > "
                    f"stop ({self.stop_loss.level})"
                )
            # For longs: targets > entry
            for target in self.targets:
                if target.level <= self.entry_zone.near_entry:
                    raise ValueError(
                        f"LONG: Target ({target.level}) must be > "
                        f"entry ({self.entry_zone.near_entry})"
                    )
        else:  # SHORT
            # For shorts: entry < stop
            if self.entry_zone.near_entry >= self.stop_loss.level:
                raise ValueError(
                    f"SHORT: Entry ({self.entry_zone.near_entry}) must be < "
                    f"stop ({self.stop_loss.level})"
                )
            # For shorts: targets < entry
            for target in self.targets:
                if target.level >= self.entry_zone.near_entry:
                    raise ValueError(
                        f"SHORT: Target ({target.level}) must be < "
                        f"entry ({self.entry_zone.near_entry})"
                    )
    
    @property
    def risk_amount(self) -> float:
        """Calculate risk amount (entry to stop distance)."""
        return abs(self.entry_zone.near_entry - self.stop_loss.level)
    
    @property
    def reward_amount(self) -> float:
        """Calculate weighted average reward (entry to targets)."""
        total_reward = sum(
            abs(t.level - self.entry_zone.near_entry) * (t.percentage / 100)
            for t in self.targets
        )
        return total_reward
    
    def calculate_rr(self) -> float:
        """Recalculate risk:reward ratio."""
        if self.risk_amount == 0:
            return 0
        return self.reward_amount / self.risk_amount
    
    def get_summary(self) -> str:
        """Generate a brief summary of the trade plan."""
        return (
            f"{self.symbol} {self.direction} ({self.setup_type})\n"
            f"Entry: {self.entry_zone.near_entry:.2f} - {self.entry_zone.far_entry:.2f}\n"
            f"Stop: {self.stop_loss.level:.2f} ({self.stop_loss.distance_atr:.1f} ATR)\n"
            f"Targets: {', '.join(f'{t.level:.2f} ({t.percentage:.0f}%)' for t in self.targets)}\n"
            f"R:R: {self.risk_reward:.2f}:1\n"
            f"Confidence: {self.confidence_score:.1f}/100"
        )
