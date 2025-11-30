"""
Smart-Money Concepts (SMC) detection models.

This module defines data structures for institutional trading patterns:
- Order Blocks (OB): Institutional entry/exit zones
- Fair Value Gaps (FVG): Imbalance zones requiring fill
- Structural Breaks: BOS (Break of Structure) and CHoCH (Change of Character)
- Liquidity Sweeps: Stop hunt patterns
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal


@dataclass
class OrderBlock:
    """
    Order Block - Institutional supply/demand zone.
    
    Represents a price zone where smart money entered positions,
    identified by strong rejection candles with displacement.
    
    Attributes:
        timeframe: Timeframe where OB was detected (e.g., '4H', '1H')
        direction: 'bullish' (demand zone) or 'bearish' (supply zone)
        high: Upper boundary of the order block
        low: Lower boundary of the order block
        timestamp: When the OB was formed
        displacement_strength: Strength of move away from zone (0-100)
        mitigation_level: How much price has revisited the zone (0-1)
        freshness_score: Recency score, decreases over time (0-100)
    """
    timeframe: str
    direction: Literal["bullish", "bearish"]
    high: float
    low: float
    timestamp: datetime
    displacement_strength: float
    mitigation_level: float
    freshness_score: float
    
    def __post_init__(self):
        """Validate order block data."""
        if self.high <= self.low:
            raise ValueError(f"OB high ({self.high}) must be > low ({self.low})")
        if not 0 <= self.displacement_strength <= 100:
            raise ValueError(f"Displacement strength must be 0-100, got {self.displacement_strength}")
        if not 0 <= self.mitigation_level <= 1:
            raise ValueError(f"Mitigation level must be 0-1, got {self.mitigation_level}")
        if not 0 <= self.freshness_score <= 100:
            raise ValueError(f"Freshness score must be 0-100, got {self.freshness_score}")
    
    @property
    def is_fresh(self) -> bool:
        """Check if OB is fresh (freshness > 70 and mitigation < 0.3)."""
        return self.freshness_score > 70 and self.mitigation_level < 0.3
    
    @property
    def midpoint(self) -> float:
        """Calculate midpoint of the order block."""
        return (self.high + self.low) / 2


@dataclass
class FVG:
    """
    Fair Value Gap - Price imbalance requiring fill.
    
    Occurs when candle 1's high/low doesn't overlap with candle 3's low/high,
    leaving a gap that price tends to revisit.
    
    Attributes:
        timeframe: Timeframe where FVG was detected
        direction: 'bullish' (gap up) or 'bearish' (gap down)
        top: Upper boundary of the gap
        bottom: Lower boundary of the gap
        timestamp: When the FVG was formed
        size: Gap size in price points
        overlap_with_price: Percentage of gap filled by price (0.0-1.0)
    """
    timeframe: str
    direction: Literal["bullish", "bearish"]
    top: float
    bottom: float
    timestamp: datetime
    size: float
    overlap_with_price: float  # 0.0 (fresh) to 1.0 (completely filled)
    
    def __post_init__(self):
        """Validate FVG data."""
        if self.top <= self.bottom:
            raise ValueError(f"FVG top ({self.top}) must be > bottom ({self.bottom})")
        expected_size = self.top - self.bottom
        if abs(self.size - expected_size) > 0.01:  # Allow small floating point error
            raise ValueError(f"FVG size mismatch: {self.size} vs calculated {expected_size}")
    
    @property
    def midpoint(self) -> float:
        """Calculate midpoint of the FVG."""
        return (self.top + self.bottom) / 2
    
    def contains_price(self, price: float) -> bool:
        """Check if a price is within the FVG."""
        return self.bottom <= price <= self.top


@dataclass
class StructuralBreak:
    """
    Structural Break - BOS or CHoCH pattern.
    
    - BOS (Break of Structure): Continuation pattern, breaks previous high/low in trend direction
    - CHoCH (Change of Character): Reversal signal, breaks structure against trend
    
    Attributes:
        timeframe: Timeframe where break was detected
        break_type: 'BOS' (continuation) or 'CHoCH' (reversal)
        level: Price level that was broken
        timestamp: When the break occurred
        htf_aligned: Whether break aligns with higher timeframe trend
    """
    timeframe: str
    break_type: Literal["BOS", "CHoCH"]
    level: float
    timestamp: datetime
    htf_aligned: bool
    
    @property
    def is_continuation(self) -> bool:
        """Check if this is a continuation pattern (BOS)."""
        return self.break_type == "BOS"
    
    @property
    def is_reversal(self) -> bool:
        """Check if this is a reversal pattern (CHoCH)."""
        return self.break_type == "CHoCH"


@dataclass
class LiquiditySweep:
    """
    Liquidity Sweep - Stop hunt pattern.
    
    Identifies when price sweeps above/below key levels to trigger stops
    before reversing, indicating institutional accumulation/distribution.
    
    Attributes:
        level: Price level that was swept
        sweep_type: 'high' (swept above) or 'low' (swept below)
        confirmation: Whether sweep was confirmed by reversal
        timestamp: When the sweep occurred
    """
    level: float
    sweep_type: Literal["high", "low"]
    confirmation: bool
    timestamp: datetime
    
    @property
    def is_confirmed(self) -> bool:
        """Check if sweep is confirmed."""
        return self.confirmation


@dataclass
class SMCSnapshot:
    """
    Complete SMC analysis snapshot for a symbol.
    
    Contains all detected Smart-Money patterns across timeframes.
    This is populated by the SMC detection modules and used for
    confluence scoring and trade planning.
    
    Attributes:
        order_blocks: List of all detected order blocks
        fvgs: List of all detected fair value gaps
        structural_breaks: List of all detected BOS/CHoCH patterns
        liquidity_sweeps: List of all detected liquidity sweeps
    """
    order_blocks: List[OrderBlock]
    fvgs: List[FVG]
    structural_breaks: List[StructuralBreak]
    liquidity_sweeps: List[LiquiditySweep]
    
    def __post_init__(self):
        """Initialize empty lists if None provided."""
        if self.order_blocks is None:
            self.order_blocks = []
        if self.fvgs is None:
            self.fvgs = []
        if self.structural_breaks is None:
            self.structural_breaks = []
        if self.liquidity_sweeps is None:
            self.liquidity_sweeps = []
    
    def get_fresh_order_blocks(self) -> List[OrderBlock]:
        """Get only fresh, unmitigated order blocks."""
        return [ob for ob in self.order_blocks if ob.is_fresh]
    
    def get_unfilled_fvgs(self) -> List[FVG]:
        """Get FVGs that haven't been filled yet."""
        return [fvg for fvg in self.fvgs if not fvg.overlap_with_price]
    
    def get_htf_aligned_breaks(self) -> List[StructuralBreak]:
        """Get structural breaks aligned with higher timeframe."""
        return [sb for sb in self.structural_breaks if sb.htf_aligned]
    
    def get_confirmed_sweeps(self) -> List[LiquiditySweep]:
        """Get confirmed liquidity sweeps."""
        return [sweep for sweep in self.liquidity_sweeps if sweep.is_confirmed]
    
    def has_smc_data(self) -> bool:
        """Check if any SMC patterns were detected."""
        return bool(self.order_blocks or self.fvgs or 
                   self.structural_breaks or self.liquidity_sweeps)
