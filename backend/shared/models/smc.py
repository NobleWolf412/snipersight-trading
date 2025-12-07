"""
Smart-Money Concepts (SMC) detection models.

This module defines data structures for institutional trading patterns:
- Order Blocks (OB): Institutional entry/exit zones
- Fair Value Gaps (FVG): Imbalance zones requiring fill
- Structural Breaks: BOS (Break of Structure) and CHoCH (Change of Character)
- Liquidity Sweeps: Stop hunt patterns
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Literal, Optional
from enum import Enum


# Pattern quality grade - A (excellent), B (good), C (marginal)
PatternGrade = Literal['A', 'B', 'C']


class CyclePhase(str, Enum):
    """
    Market cycle phase based on Camel Finance methodology.
    
    Phases represent where we are in the cycle relative to lows/highs:
    - ACCUMULATION: At or near cycle low (DCL/WCL), smart money accumulating
    - MARKUP: Rising from cycle low toward high, trend in progress
    - DISTRIBUTION: At or near cycle high, smart money distributing
    - MARKDOWN: Falling from cycle high toward next low
    """
    ACCUMULATION = "accumulation"
    MARKUP = "markup"
    DISTRIBUTION = "distribution"
    MARKDOWN = "markdown"
    UNKNOWN = "unknown"


class CycleTranslation(str, Enum):
    """
    Cycle translation indicates when the cycle topped relative to midpoint.
    
    Per Camel Finance:
    - LTR (Left-Translated): Topped early (before midpoint) = bearish bias
    - MTR (Mid-Translated): Topped mid-cycle = neutral
    - RTR (Right-Translated): Topped late (after midpoint) = bullish bias
    """
    LTR = "left_translated"   # 🟥 Bearish - topped early
    MTR = "mid_translated"    # 🟧 Neutral - topped mid-cycle
    RTR = "right_translated"  # 🟩 Bullish - topped late
    UNKNOWN = "unknown"


class CycleConfirmation(str, Enum):
    """
    Confirmation state of a cycle low/high detection.
    
    Based on Camel Finance confirmation logic:
    - CONFIRMED: All rules align, high-confidence trigger
    - UNCONFIRMED: Provisional, not ready yet
    - CANCELLED: Broke down post-trigger, invalidated
    - UPDATED: New low/high replaced an invalidated one
    """
    CONFIRMED = "confirmed"      # ✅
    UNCONFIRMED = "unconfirmed"  # 🕓
    CANCELLED = "cancelled"      # ❌
    UPDATED = "updated"          # 🔄


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
    grade: PatternGrade = 'B'  # Quality grade: A (excellent), B (good), C (marginal)
    displacement_atr: float = 0.0  # ATR-normalized displacement for reference
    
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
        freshness_score: Recency score, decreases over time (0.0-1.0)
    """
    timeframe: str
    direction: Literal["bullish", "bearish"]
    top: float
    bottom: float
    timestamp: datetime
    size: float
    overlap_with_price: float  # 0.0 (fresh) to 1.0 (completely filled)
    freshness_score: float = 1.0  # Time-based decay, similar to OB
    grade: PatternGrade = 'B'  # Quality grade: A (excellent), B (good), C (marginal)
    size_atr: float = 0.0  # ATR-normalized gap size for reference
    
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
    
    @property
    def is_fresh(self) -> bool:
        """Check if FVG is fresh (freshness > 0.5 and less than 50% filled)."""
        return self.freshness_score > 0.5 and self.overlap_with_price < 0.5
    
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
    grade: PatternGrade = 'B'  # Quality grade: A (excellent), B (good), C (marginal)
    break_distance_atr: float = 0.0  # ATR-normalized break distance for reference
    direction: Literal["bullish", "bearish"] = "bullish"  # Direction of the break
    
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
        grade: Pattern quality grade (A/B/C) based on reversal strength
    """
    level: float
    sweep_type: Literal["high", "low"]
    confirmation: bool
    timestamp: datetime
    grade: PatternGrade = 'B'  # Graded by reversal strength in ATR units
    
    @property
    def is_confirmed(self) -> bool:
        """Check if sweep is confirmed."""
        return self.confirmation


@dataclass
class LiquidityPool:
    """
    Liquidity Pool - Equal highs or equal lows cluster.
    
    Represents clustered swing points at similar price levels where
    stop-loss liquidity accumulates. These are high-probability sweep targets.
    
    Attributes:
        level: Average price level of the cluster
        pool_type: 'equal_highs' or 'equal_lows'
        touches: Number of swing points in the cluster
        timeframe: Timeframe where detected
        grade: Quality grade based on touch count (A=4+, B=3, C=2)
        first_touch: Timestamp of first swing point in cluster
        last_touch: Timestamp of most recent swing point
        tolerance_used: Price tolerance that defined this cluster
        spread: Price spread within the cluster (high - low of touches)
    """
    level: float
    pool_type: Literal["equal_highs", "equal_lows"]
    touches: int
    timeframe: str
    grade: PatternGrade = 'B'
    first_touch: Optional[datetime] = None
    last_touch: Optional[datetime] = None
    tolerance_used: float = 0.002  # Tolerance % used for clustering
    spread: float = 0.0  # Price spread within cluster
    
    @property
    def is_strong(self) -> bool:
        """Check if this is a strong liquidity pool (3+ touches or Grade A/B)."""
        return self.touches >= 3 or self.grade in ('A', 'B')
    
    @property
    def is_fresh(self) -> bool:
        """Check if pool was touched recently (last 7 days)."""
        if not self.last_touch:
            return True
        age = datetime.now() - self.last_touch
        return age.days <= 7
    
    def contains_price(self, price: float) -> bool:
        """Check if price is within the liquidity pool zone."""
        tolerance = self.level * self.tolerance_used
        return abs(price - self.level) <= tolerance


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
        equal_highs: Price levels with clustered equal highs (DEPRECATED - use liquidity_pools)
        equal_lows: Price levels with clustered equal lows (DEPRECATED - use liquidity_pools)
        liquidity_pools: List of structured LiquidityPool objects (NEW)
    """
    order_blocks: List[OrderBlock]
    fvgs: List[FVG]
    structural_breaks: List[StructuralBreak]
    liquidity_sweeps: List[LiquiditySweep]
    equal_highs: List[float] = field(default_factory=list)  # DEPRECATED but kept for backward compat
    equal_lows: List[float] = field(default_factory=list)   # DEPRECATED but kept for backward compat
    liquidity_pools: List[LiquidityPool] = field(default_factory=list)  # NEW: structured pools
    swing_structure: dict = field(default_factory=dict)  # {timeframe: SwingStructure.to_dict()}
    premium_discount: dict = field(default_factory=dict)  # {timeframe: PremiumDiscountZone.to_dict()}
    key_levels: Optional[dict] = None  # KeyLevels.to_dict()
    
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
        if self.equal_highs is None:
            self.equal_highs = []
        if self.equal_lows is None:
            self.equal_lows = []
        if self.liquidity_pools is None:
            self.liquidity_pools = []
        if self.swing_structure is None:
            self.swing_structure = {}
        if self.premium_discount is None:
            self.premium_discount = {}
    
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
    
    def get_strong_liquidity_pools(self) -> List[LiquidityPool]:
        """Get strong liquidity pools (3+ touches or Grade A/B)."""
        return [pool for pool in self.liquidity_pools if pool.is_strong]
    
    def get_equal_highs_pools(self) -> List[LiquidityPool]:
        """Get liquidity pools of equal highs type."""
        return [pool for pool in self.liquidity_pools if pool.pool_type == "equal_highs"]
    
    def get_equal_lows_pools(self) -> List[LiquidityPool]:
        """Get liquidity pools of equal lows type."""
        return [pool for pool in self.liquidity_pools if pool.pool_type == "equal_lows"]
    
    def get_nearest_pool(self, price: float, pool_type: Optional[str] = None) -> Optional[LiquidityPool]:
        """
        Get the nearest liquidity pool to a given price.
        
        Args:
            price: Reference price
            pool_type: Optional filter ('equal_highs' or 'equal_lows')
            
        Returns:
            Nearest LiquidityPool or None
        """
        pools = self.liquidity_pools
        if pool_type:
            pools = [p for p in pools if p.pool_type == pool_type]
        
        if not pools:
            return None
        
        return min(pools, key=lambda p: abs(p.level - price))
    
    def has_smc_data(self) -> bool:
        """Check if any SMC patterns were detected."""
        return bool(self.order_blocks or self.fvgs or 
                   self.structural_breaks or self.liquidity_sweeps or
                   self.liquidity_pools)


@dataclass
class CycleContext:
    """
    Cycle timing context based on Camel Finance methodology.
    
    Tracks Daily Cycle Low (DCL), Weekly Cycle Low (WCL), and cycle translation
    to determine optimal entry/exit timing for both long and short trades.
    
    Crypto timing windows (per Camel Finance):
    - DCL: 18-28 trading days
    - WCL: 35-50 trading days (nests 2-3 DCLs)
    - YCL: 200-250 trading days
    
    Attributes:
        phase: Current market cycle phase (accumulation/markup/distribution/markdown)
        translation: Cycle translation (LTR/MTR/RTR) - indicates bearish/neutral/bullish bias
        
        dcl_days_since: Days since last Daily Cycle Low
        dcl_confirmation: Confirmation state of current DCL
        dcl_price: Price level of last confirmed DCL
        dcl_timestamp: Timestamp of last DCL
        
        wcl_days_since: Days since last Weekly Cycle Low
        wcl_confirmation: Confirmation state of current WCL
        wcl_price: Price level of last confirmed WCL
        wcl_timestamp: Timestamp of last WCL
        
        cycle_high_price: Price of current cycle high (for translation calc)
        cycle_high_timestamp: When cycle high occurred
        cycle_midpoint_price: Price at cycle midpoint (DCL high + DCL low) / 2
        
        in_dcl_zone: Whether price is in DCL timing window (ready for long entry)
        in_wcl_zone: Whether price is in WCL timing window (major reversal zone)
        
        trade_bias: Recommended trade direction based on cycle ('LONG', 'SHORT', 'NEUTRAL')
        confidence: Confidence in cycle assessment (0-100)
    """
    phase: CyclePhase = CyclePhase.UNKNOWN
    translation: CycleTranslation = CycleTranslation.UNKNOWN
    
    # Daily Cycle Low tracking
    dcl_days_since: Optional[int] = None
    dcl_confirmation: CycleConfirmation = CycleConfirmation.UNCONFIRMED
    dcl_price: Optional[float] = None
    dcl_timestamp: Optional[datetime] = None
    
    # Weekly Cycle Low tracking
    wcl_days_since: Optional[int] = None
    wcl_confirmation: CycleConfirmation = CycleConfirmation.UNCONFIRMED
    wcl_price: Optional[float] = None
    wcl_timestamp: Optional[datetime] = None
    
    # Cycle high tracking (for translation)
    cycle_high_price: Optional[float] = None
    cycle_high_timestamp: Optional[datetime] = None
    cycle_midpoint_price: Optional[float] = None
    
    # Timing zone flags
    in_dcl_zone: bool = False
    in_wcl_zone: bool = False
    
    # Trade recommendation
    trade_bias: Literal["LONG", "SHORT", "NEUTRAL"] = "NEUTRAL"
    confidence: float = 0.0
    
    def __post_init__(self):
        """Validate confidence range."""
        self.confidence = max(0.0, min(100.0, self.confidence))
    
    @property
    def is_at_cycle_low(self) -> bool:
        """Check if currently at a confirmed cycle low (DCL or WCL)."""
        return (
            self.in_dcl_zone or self.in_wcl_zone
        ) and self.phase == CyclePhase.ACCUMULATION
    
    @property
    def is_at_cycle_high(self) -> bool:
        """Check if currently at cycle high (distribution phase with LTR)."""
        return self.phase == CyclePhase.DISTRIBUTION
    
    @property
    def suggests_long(self) -> bool:
        """Check if cycle context suggests looking for longs."""
        return (
            self.trade_bias == "LONG" or 
            self.phase == CyclePhase.ACCUMULATION or
            self.translation == CycleTranslation.RTR
        )
    
    @property
    def suggests_short(self) -> bool:
        """Check if cycle context suggests looking for shorts."""
        return (
            self.trade_bias == "SHORT" or
            self.phase == CyclePhase.DISTRIBUTION or
            self.translation == CycleTranslation.LTR
        )


@dataclass
class ReversalContext:
    """
    Reversal detection context combining cycle timing with SMC signals.
    
    Identifies high-probability reversal setups by combining:
    - Cycle extreme (DCL/WCL zone or distribution zone)
    - CHoCH (Change of Character) structural break
    - Volume displacement confirmation
    - Liquidity sweep (stop hunt before reversal)
    
    Attributes:
        is_reversal_setup: Whether conditions meet reversal criteria
        direction: Reversal direction ('LONG' for bullish reversal, 'SHORT' for bearish)
        
        cycle_aligned: Whether cycle context supports the reversal
        choch_detected: Whether CHoCH was detected
        volume_displacement: Whether volume spike confirmed the move
        liquidity_swept: Whether recent liquidity sweep occurred
        
        htf_bypass_active: Whether to bypass HTF EMA alignment (cycle extreme + structure broken)
        
        signals: List of component signals that formed the reversal context
        confidence: Overall reversal confidence (0-100)
        rationale: Human-readable explanation of reversal setup
    """
    is_reversal_setup: bool = False
    direction: Literal["LONG", "SHORT", "NONE"] = "NONE"
    
    # Component signals
    cycle_aligned: bool = False
    choch_detected: bool = False
    volume_displacement: bool = False
    liquidity_swept: bool = False
    
    # Bypass flag for HTF alignment
    htf_bypass_active: bool = False
    
    # Details
    signals: List[str] = field(default_factory=list)
    confidence: float = 0.0
    rationale: str = ""
    
    def __post_init__(self):
        """Validate and ensure signals list exists."""
        if self.signals is None:
            self.signals = []
        self.confidence = max(0.0, min(100.0, self.confidence))
    
    @property
    def component_count(self) -> int:
        """Count how many reversal components are present."""
        return sum([
            self.cycle_aligned,
            self.choch_detected,
            self.volume_displacement,
            self.liquidity_swept
        ])
    
    @property
    def is_high_confidence(self) -> bool:
        """Check if reversal has high confidence (3+ components)."""
        return self.component_count >= 3 and self.confidence >= 70.0


# --- Pattern Grading Helper ---

def grade_pattern(
    value: float,
    atr: float,
    a_threshold: float = 1.5,
    b_threshold: float = 1.0
) -> PatternGrade:
    """
    Grade a pattern based on its ATR-relative strength.
    
    This replaces hard rejection with soft grading:
    - Grade A: Excellent pattern (value >= a_threshold * ATR)
    - Grade B: Good pattern (value >= b_threshold * ATR)  
    - Grade C: Marginal pattern (below b_threshold)
    
    Args:
        value: The pattern's characteristic value (displacement, gap size, etc.)
        atr: Current ATR for normalization
        a_threshold: ATR multiplier for Grade A (default 1.5)
        b_threshold: ATR multiplier for Grade B (default 1.0)
        
    Returns:
        PatternGrade: 'A', 'B', or 'C'
    """
    if atr <= 0:
        return 'B'  # Can't grade without ATR, default to B
    
    atr_ratio = value / atr
    
    if atr_ratio >= a_threshold:
        return 'A'
    elif atr_ratio >= b_threshold:
        return 'B'
    else:
        return 'C'
