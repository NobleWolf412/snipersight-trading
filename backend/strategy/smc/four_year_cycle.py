"""
4-Year Cycle Detection Module

Implements macro cycle tracking based on Bitcoin halving cycles per Camel Finance.

The 4-year cycle (FYC) is NOT detected dynamically from price action like DCL/WCL.
Instead, it's based on known historical events (halving + capitulation) with forward
projection. This provides macro context for all trading decisions.

Historical 4YC Lows:
- Nov 2011: ~$2
- Jan 2015: ~$170
- Dec 2018: ~$3,200
- Nov 2022: ~$15,500 (FTX collapse bottom)
- Est. 2026: TBD (mid-to-late 2026)

Usage:
    from backend.strategy.smc.four_year_cycle import get_four_year_cycle_context

    ctx = get_four_year_cycle_context()
    print(f"Day {ctx.days_since_fyc_low} - Phase: {ctx.phase.value}")
    print(f"Macro Bias: {ctx.macro_bias} ({ctx.confidence:.0f}%)")
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional, Literal, Dict, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class FYCPhase(str, Enum):
    """
    4-Year Cycle phase.

    Each phase represents roughly one year of the cycle:
    - ACCUMULATION: Year 1 (0-25%) - Post-bottom recovery, smart money loading
    - MARKUP: Year 2 (25-50%) - Bull market expansion, retail FOMO builds
    - DISTRIBUTION: Year 3 (50-75%) - Blow-off top zone, smart money exits
    - MARKDOWN: Year 4 (75-100%) - Bear market grinding, capitulation
    """

    ACCUMULATION = "accumulation"
    MARKUP = "markup"
    DISTRIBUTION = "distribution"
    MARKDOWN = "markdown"
    UNKNOWN = "unknown"


@dataclass
class FourYearCycleContext:
    """
    4-Year cycle tracking context.

    Provides macro context for trading decisions based on position within
    the ~4-year Bitcoin halving cycle.

    Attributes:
        days_since_fyc_low: Days elapsed since last confirmed 4YC low
        days_until_expected_low: Days until expected next 4YC low
        cycle_position_pct: Position in cycle as percentage (0-100)

        phase: Current cycle phase (accumulation/markup/distribution/markdown)
        phase_progress_pct: Progress within current phase (0-100)

        last_fyc_low_date: Date of last confirmed 4YC low
        last_fyc_low_price: Price at last 4YC low
        last_fyc_low_event: Description of what caused the low

        expected_next_low_date: Projected date of next 4YC low

        macro_bias: Overall market direction bias
        confidence: Confidence in the macro bias (0-100)

        is_in_danger_zone: True if in late distribution or markdown
        is_in_opportunity_zone: True if in accumulation or early markup
    """

    # Core timing
    days_since_fyc_low: int
    days_until_expected_low: int
    cycle_position_pct: float

    # Phase info
    phase: FYCPhase
    phase_progress_pct: float

    # Historical reference
    last_fyc_low_date: date
    last_fyc_low_price: float
    last_fyc_low_event: str

    # Projection
    expected_next_low_date: date

    # Trade bias
    macro_bias: Literal["BULLISH", "NEUTRAL", "BEARISH"]
    confidence: float

    # Risk zones
    is_in_danger_zone: bool
    is_in_opportunity_zone: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "days_since_low": self.days_since_fyc_low,
            "days_until_expected_low": self.days_until_expected_low,
            "cycle_position_pct": round(self.cycle_position_pct, 1),
            "phase": self.phase.value.upper(),
            "phase_progress_pct": round(self.phase_progress_pct, 1),
            "last_low": {
                "date": self.last_fyc_low_date.isoformat(),
                "price": self.last_fyc_low_price,
                "event": self.last_fyc_low_event,
            },
            "expected_next_low": self.expected_next_low_date.isoformat(),
            "macro_bias": self.macro_bias,
            "confidence": round(self.confidence, 1),
            "zones": {
                "is_danger_zone": self.is_in_danger_zone,
                "is_opportunity_zone": self.is_in_opportunity_zone,
            },
        }

    @property
    def suggests_long(self) -> bool:
        """Check if cycle context supports long positions."""
        return self.macro_bias == "BULLISH" or self.phase in [
            FYCPhase.ACCUMULATION,
            FYCPhase.MARKUP,
        ]

    @property
    def suggests_short(self) -> bool:
        """Check if cycle context supports short positions."""
        return self.macro_bias == "BEARISH" or self.phase in [
            FYCPhase.DISTRIBUTION,
            FYCPhase.MARKDOWN,
        ]


# ==============================================================================
# HISTORICAL 4-YEAR CYCLE LOWS AND HALVINGS
# ==============================================================================
# The 4YC is anchored by both the cycle low AND the halving event.
# Halving typically occurs ~18 months after cycle low, triggering markup.

HISTORICAL_4YC_LOWS = [
    {"date": date(2011, 11, 18), "price": 2.0, "event": "Post-Mt.Gox hack bottom"},
    {"date": date(2015, 1, 14), "price": 170.0, "event": "Post-2014 halving capitulation"},
    {"date": date(2018, 12, 15), "price": 3200.0, "event": "Crypto winter bottom"},
    {"date": date(2022, 11, 21), "price": 15476.0, "event": "FTX collapse capitulation"},
]

# Bitcoin halving dates - key catalyst for markup phase
BTC_HALVINGS = [
    date(2012, 11, 28),  # Halving #1: 25 BTC -> 12.5 BTC
    date(2016, 7, 9),  # Halving #2: 12.5 BTC -> 6.25 BTC
    date(2020, 5, 11),  # Halving #3: 6.25 BTC -> 3.125 BTC
    date(2024, 4, 20),  # Halving #4: 3.125 BTC -> 1.5625 BTC
]

# Current anchor points
LAST_4YC_LOW = HISTORICAL_4YC_LOWS[-1]
LAST_HALVING = BTC_HALVINGS[-1]  # April 2024
NEXT_HALVING_EST = date(2028, 4, 1)  # ~4 years after 2024 halving

# Expected cycle length in days (~4 years)
EXPECTED_CYCLE_DAYS = 1460

# Phase boundaries - ADJUSTED for halving-aware timing
# The halving typically occurs ~500 days (17 months) after cycle low
# and triggers the transition from late accumulation to markup.
#
# Typical Pattern:
# - Cycle Low to Halving: ~500 days (accumulation)
# - Halving to Peak: ~500-550 days (markup to distribution)
# - Peak to Next Low: ~400-450 days (markdown)
#
# For current cycle (Nov 2022 low, April 2024 halving):
# - Nov 2022 - Apr 2024: Accumulation (~520 days)
# - Apr 2024 - Late 2025: Markup/Distribution (~500 days)
# - Late 2025 - Late 2026: Markdown (~400 days)

PHASE_BOUNDARIES = {
    "accumulation_end": 35.0,  # ~510 days - until halving
    "markup_end": 65.0,  # ~950 days - post-halving rally
    "distribution_end": 80.0,  # ~1170 days - blow-off top zone
    # markdown: 80-100%          # ~1170-1460 days - bear market
}


def get_four_year_cycle_context(
    current_date: Optional[date] = None, custom_anchor: Optional[Dict] = None
) -> FourYearCycleContext:
    """
    Get current 4-year cycle context.

    Calculates position within the Bitcoin 4-year halving cycle based on
    the known November 2022 bottom. This is primarily date-based - price
    action does not change the cycle position.

    Args:
        current_date: Date to calculate for (defaults to today)
        custom_anchor: Optional custom anchor point for testing

    Returns:
        FourYearCycleContext with complete macro cycle information

    Example:
        >>> ctx = get_four_year_cycle_context()
        >>> print(f"Day {ctx.days_since_fyc_low}, Phase: {ctx.phase.value}")
        Day 760, Phase: markup
    """
    if current_date is None:
        current_date = date.today()

    # Use custom anchor if provided, otherwise use last known 4YC low
    anchor = custom_anchor if custom_anchor else LAST_4YC_LOW
    fyc_low_date = anchor["date"]
    fyc_low_price = anchor["price"]
    fyc_low_event = anchor["event"]

    # Calculate days since known low
    days_since = (current_date - fyc_low_date).days

    # Handle edge case where current_date is before the anchor
    if days_since < 0:
        logger.warning(
            "Current date %s is before 4YC anchor %s, returning unknown phase",
            current_date,
            fyc_low_date,
        )
        return FourYearCycleContext(
            days_since_fyc_low=0,
            days_until_expected_low=0,
            cycle_position_pct=0.0,
            phase=FYCPhase.UNKNOWN,
            phase_progress_pct=0.0,
            last_fyc_low_date=fyc_low_date,
            last_fyc_low_price=fyc_low_price,
            last_fyc_low_event=fyc_low_event,
            expected_next_low_date=fyc_low_date,
            macro_bias="NEUTRAL",
            confidence=0.0,
            is_in_danger_zone=False,
            is_in_opportunity_zone=False,
        )

    # Calculate expected next low (roughly 4 years from last low)
    expected_next = fyc_low_date + timedelta(days=EXPECTED_CYCLE_DAYS)
    days_until = (expected_next - current_date).days

    # Cycle position as percentage (cap at 100% even if past expected)
    position_pct = min(100.0, (days_since / EXPECTED_CYCLE_DAYS) * 100)

    # Determine phase based on position
    phase, phase_progress = _determine_phase(position_pct)

    # Calculate macro bias based on phase and position
    macro_bias, confidence = _calculate_macro_bias(phase, position_pct, phase_progress)

    # Risk zones - adjusted for halving-aware timing
    # Opportunity: Accumulation + early markup (pre-halving + first 6 months post)
    # Danger: Late distribution + markdown
    is_danger = position_pct > 72  # Late distribution + markdown
    is_opportunity = position_pct < 45  # Accumulation + early/mid markup

    logger.debug(
        "4YC Context: Day %d (%.1f%%) - %s - %s (%.0f%% conf)",
        days_since,
        position_pct,
        phase.value,
        macro_bias,
        confidence,
    )

    return FourYearCycleContext(
        days_since_fyc_low=days_since,
        days_until_expected_low=max(0, days_until),
        cycle_position_pct=position_pct,
        phase=phase,
        phase_progress_pct=phase_progress,
        last_fyc_low_date=fyc_low_date,
        last_fyc_low_price=fyc_low_price,
        last_fyc_low_event=fyc_low_event,
        expected_next_low_date=expected_next,
        macro_bias=macro_bias,
        confidence=confidence,
        is_in_danger_zone=is_danger,
        is_in_opportunity_zone=is_opportunity,
    )


def _determine_phase(position_pct: float) -> tuple[FYCPhase, float]:
    """
    Determine cycle phase and progress within phase.

    Uses halving-aware boundaries:
    - Accumulation: 0-35% (~510 days, pre-halving)
    - Markup: 35-65% (~440 days, post-halving rally)
    - Distribution: 65-80% (~220 days, blow-off zone)
    - Markdown: 80-100% (~290 days, bear market)

    Args:
        position_pct: Position in cycle (0-100)

    Returns:
        Tuple of (phase, phase_progress_pct)
    """
    acc_end = PHASE_BOUNDARIES["accumulation_end"]
    mkp_end = PHASE_BOUNDARIES["markup_end"]
    dst_end = PHASE_BOUNDARIES["distribution_end"]

    if position_pct < acc_end:
        # Accumulation (0-35%)
        phase = FYCPhase.ACCUMULATION
        phase_progress = (position_pct / acc_end) * 100

    elif position_pct < mkp_end:
        # Markup (35-65%)
        phase = FYCPhase.MARKUP
        phase_progress = ((position_pct - acc_end) / (mkp_end - acc_end)) * 100

    elif position_pct < dst_end:
        # Distribution (65-80%)
        phase = FYCPhase.DISTRIBUTION
        phase_progress = ((position_pct - mkp_end) / (dst_end - mkp_end)) * 100

    else:
        # Markdown (80-100%)
        phase = FYCPhase.MARKDOWN
        phase_progress = min(100.0, ((position_pct - dst_end) / (100 - dst_end)) * 100)

    return phase, phase_progress


def _calculate_macro_bias(
    phase: FYCPhase, position_pct: float, phase_progress: float
) -> tuple[Literal["BULLISH", "NEUTRAL", "BEARISH"], float]:
    """
    Calculate macro bias based on cycle position.

    Logic:
    - Accumulation: Strong bullish (loading zone)
    - Early Markup (<40%): Strong bullish (trend confirmed)
    - Late Markup (40-50%): Moderate bullish (watch for distribution)
    - Early Distribution: Neutral to bearish
    - Late Distribution: Bearish
    - Markdown: Strong bearish

    Args:
        phase: Current cycle phase
        position_pct: Overall position in cycle
        phase_progress: Progress within current phase

    Returns:
        Tuple of (bias, confidence)
    """
    if phase == FYCPhase.ACCUMULATION:
        # Strong bullish - smart money loading
        # Higher confidence early in accumulation
        confidence = 85.0 - (phase_progress * 0.2)
        return ("BULLISH", confidence)

    elif phase == FYCPhase.MARKUP:
        # Bullish but confidence decreases as we progress
        if phase_progress < 60:  # Early/mid markup
            confidence = 80.0 - (phase_progress * 0.3)
            return ("BULLISH", confidence)
        else:  # Late markup
            confidence = 65.0 - ((phase_progress - 60) * 0.4)
            return ("BULLISH", max(50.0, confidence))

    elif phase == FYCPhase.DISTRIBUTION:
        if phase_progress < 40:
            # Early distribution - mixed signals
            return ("NEUTRAL", 55.0)
        elif phase_progress < 70:
            # Mid distribution - turning bearish
            confidence = 55.0 + ((phase_progress - 40) * 0.5)
            return ("BEARISH", confidence)
        else:
            # Late distribution - clear bearish
            return ("BEARISH", 75.0)

    else:  # MARKDOWN
        # Bearish - deeper into markdown = higher confidence
        confidence = 70.0 + (phase_progress * 0.15)
        return ("BEARISH", min(90.0, confidence))


def get_fyc_confluence_modifier(
    fyc_context: FourYearCycleContext, direction: str
) -> tuple[float, str]:
    """
    Get confluence score modifier based on 4-year cycle position.

    This is used by the confluence scorer to adjust signal scores
    based on macro cycle context.

    Args:
        fyc_context: 4-Year cycle context
        direction: Trade direction ("LONG" or "SHORT")

    Returns:
        Tuple of (modifier, rationale)
        - Positive modifier = bonus points
        - Negative modifier = penalty points

    Example:
        >>> ctx = get_four_year_cycle_context()
        >>> mod, reason = get_fyc_confluence_modifier(ctx, "LONG")
        >>> print(f"Modifier: {mod:+.0f} - {reason}")
        Modifier: +10 - 4YC Markup - favorable for longs
    """
    phase = fyc_context.phase
    position = fyc_context.cycle_position_pct
    phase_prog = fyc_context.phase_progress_pct
    dir_upper = direction.upper()

    # === LONG TRADES ===
    if dir_upper == "LONG":
        if phase == FYCPhase.ACCUMULATION:
            if phase_prog < 50:
                return (15.0, "4YC Early Accumulation - prime long entry zone")
            else:
                return (12.0, "4YC Late Accumulation - still favorable for longs")

        elif phase == FYCPhase.MARKUP:
            if phase_prog < 40:
                return (12.0, "4YC Early Markup - strong bullish backdrop")
            elif phase_prog < 75:
                return (8.0, "4YC Mid Markup - favorable for longs")
            else:
                return (4.0, "4YC Late Markup - longs ok but watch for distribution")

        elif phase == FYCPhase.DISTRIBUTION:
            if phase_prog < 50:
                return (-5.0, "4YC Early Distribution - longs increasingly risky")
            else:
                return (-12.0, "4YC Late Distribution - avoid new longs")

        else:  # MARKDOWN
            if phase_prog > 80:
                # Very late markdown - approaching next accumulation
                return (-5.0, "4YC Very Late Markdown - approaching next cycle low")
            else:
                return (-15.0, "4YC Markdown - strongly avoid longs")

    # === SHORT TRADES ===
    elif dir_upper == "SHORT":
        if phase == FYCPhase.MARKDOWN:
            if phase_prog < 50:
                return (12.0, "4YC Early Markdown - favorable for shorts")
            elif phase_prog < 80:
                return (8.0, "4YC Mid Markdown - shorts ok")
            else:
                return (3.0, "4YC Late Markdown - watch for accumulation")

        elif phase == FYCPhase.DISTRIBUTION:
            if phase_prog < 30:
                return (3.0, "4YC Early Distribution - shorts starting to work")
            elif phase_prog < 60:
                return (8.0, "4YC Mid Distribution - shorts gaining edge")
            else:
                return (12.0, "4YC Late Distribution - favorable for shorts")

        elif phase == FYCPhase.MARKUP:
            if phase_prog > 70:
                return (-4.0, "4YC Late Markup - shorts risky but possible")
            else:
                return (-10.0, "4YC Markup - avoid shorts")

        else:  # ACCUMULATION
            return (-15.0, "4YC Accumulation - strongly avoid shorts")

    return (0.0, "4YC context neutral for this direction")


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================


def get_all_historical_lows() -> list[Dict]:
    """Get all historical 4YC lows for reference/charting."""
    return HISTORICAL_4YC_LOWS.copy()


def get_halving_info() -> Dict:
    """
    Get Bitcoin halving information.

    Returns:
        Dict with last halving, next halving estimate, and days info
    """
    today = date.today()
    days_since_halving = (today - LAST_HALVING).days
    days_until_next = (NEXT_HALVING_EST - today).days

    return {
        "last_halving": {
            "date": LAST_HALVING.isoformat(),
            "days_since": days_since_halving,
            "number": 4,
            "block_reward": "3.125 BTC",
        },
        "next_halving": {
            "estimated_date": NEXT_HALVING_EST.isoformat(),
            "days_until": max(0, days_until_next),
            "number": 5,
            "block_reward": "1.5625 BTC",
        },
        "halving_history": [
            {"date": h.isoformat(), "number": i + 1} for i, h in enumerate(BTC_HALVINGS)
        ],
    }


def estimate_next_fyc_low() -> Dict:
    """
    Estimate the next 4YC low based on historical patterns.

    Returns dict with estimated date range and confidence.
    """
    last_low = LAST_4YC_LOW["date"]

    # Historical cycle lengths: ~1150, ~1430, ~1430 days
    # Average around 1340 days, but more recent cycles are ~1430

    early_estimate = last_low + timedelta(days=1350)
    central_estimate = last_low + timedelta(days=1460)
    late_estimate = last_low + timedelta(days=1550)

    return {
        "early_estimate": early_estimate.isoformat(),
        "central_estimate": central_estimate.isoformat(),
        "late_estimate": late_estimate.isoformat(),
        "confidence_note": "Based on ~4-year halving cycle. Actual timing depends on macro conditions.",
        "expected_year": central_estimate.year,
    }
