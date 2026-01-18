"""
Reversal Detection Module

Combines cycle timing context with SMC signals to identify
high-probability reversal setups for both long and short directions.

Reversal components:
1. Cycle extreme (DCL/WCL zone for longs, LTR distribution for shorts)
2. CHoCH (Change of Character) structural break
3. Volume displacement confirmation
4. Liquidity sweep (stop hunt before reversal)

When 3+ components align, activates HTF alignment bypass for the CHoCH.
"""

from typing import Optional, List
import logging

from backend.shared.models.smc import (
    CycleContext,
    CyclePhase,
    CycleTranslation,
    CycleConfirmation,
    ReversalContext,
    SMCSnapshot,
    StructuralBreak,
)
from backend.shared.models.indicators import IndicatorSnapshot

logger = logging.getLogger(__name__)


def detect_reversal_context(
    smc_snapshot: Optional[SMCSnapshot],
    cycle_context: Optional[CycleContext],
    indicators: Optional[IndicatorSnapshot] = None,
    current_price: Optional[float] = None,
    direction: Optional[str] = None,
) -> ReversalContext:
    """
    Detect reversal setup by combining cycle timing with SMC signals.

    Evaluates both long and short reversal conditions unless direction specified.
    Returns the stronger reversal setup if both are valid.

    Args:
        smc_snapshot: SMC patterns (order blocks, FVGs, structural breaks, sweeps)
        cycle_context: Cycle timing context (DCL/WCL, translation, phase)
        indicators: Technical indicators for volume confirmation
        current_price: Current market price
        direction: Optional - force evaluation of specific direction only

    Returns:
        ReversalContext with reversal setup details
    """
    if smc_snapshot is None or cycle_context is None:
        return ReversalContext()

    # Evaluate both directions
    long_reversal = detect_long_reversal(smc_snapshot, cycle_context, indicators)
    short_reversal = detect_short_reversal(smc_snapshot, cycle_context, indicators)

    if direction:
        if direction.upper() == "LONG":
            return long_reversal
        elif direction.upper() == "SHORT":
            return short_reversal

    # Return stronger setup
    if long_reversal.is_reversal_setup and short_reversal.is_reversal_setup:
        return (
            long_reversal
            if long_reversal.confidence >= short_reversal.confidence
            else short_reversal
        )
    elif long_reversal.is_reversal_setup:
        return long_reversal
    elif short_reversal.is_reversal_setup:
        return short_reversal

    return ReversalContext()


def detect_long_reversal(
    smc_snapshot: SMCSnapshot,
    cycle_context: CycleContext,
    indicators: Optional[IndicatorSnapshot] = None,
) -> ReversalContext:
    """
    Detect bullish reversal setup (for LONG entry).

    Long reversal conditions:
    1. At cycle low extreme (DCL/WCL zone, accumulation phase)
    2. Bullish CHoCH detected (structure breaking upward from downtrend)
    3. Volume spike/displacement confirming the move
    4. Liquidity sweep of lows (stop hunt before reversal)

    Additional context:
    - RTR translation history supports long bias
    - Bullish order block in proximity

    Args:
        smc_snapshot: SMC patterns
        cycle_context: Cycle timing context
        indicators: Technical indicators

    Returns:
        ReversalContext for long reversal
    """
    signals = []
    component_flags = {
        "cycle_aligned": False,
        "choch_detected": False,
        "volume_displacement": False,
        "liquidity_swept": False,
    }

    # === 1. CYCLE ALIGNMENT ===
    # At DCL/WCL zone or accumulation phase
    cycle_score = 0.0

    if cycle_context.phase == CyclePhase.ACCUMULATION:
        component_flags["cycle_aligned"] = True
        signals.append("Accumulation phase detected")
        cycle_score = 30.0

        if cycle_context.dcl_confirmation == CycleConfirmation.CONFIRMED:
            signals.append("✅ DCL confirmed")
            cycle_score += 15.0

    if cycle_context.in_dcl_zone:
        component_flags["cycle_aligned"] = True
        signals.append(f"In DCL timing window (day {cycle_context.dcl_days_since})")
        cycle_score += 10.0

    if cycle_context.in_wcl_zone:
        component_flags["cycle_aligned"] = True
        signals.append(f"In WCL timing window (day {cycle_context.wcl_days_since})")
        cycle_score += 15.0  # WCL more significant

    if cycle_context.translation == CycleTranslation.RTR:
        signals.append("🟩 RTR translation (bullish cycle history)")
        cycle_score += 10.0

    # === 2. CHoCH DETECTION ===
    # Look for bullish CHoCH (in downtrend, breaking upward)
    bullish_choch = _find_bullish_choch(smc_snapshot.structural_breaks)

    if bullish_choch:
        component_flags["choch_detected"] = True
        signals.append(f"Bullish CHoCH at {bullish_choch.level:.4f}")

    # === 3. VOLUME DISPLACEMENT ===
    if indicators and indicators.volume_spike:
        component_flags["volume_displacement"] = True
        signals.append("Volume spike confirms reversal")

    # Check for strong displacement via ATR
    if indicators and indicators.atr_percent:
        # Strong move = ATR% above normal
        if indicators.atr_percent > 0.8:  # Above average volatility
            signals.append(f"Strong displacement (ATR% {indicators.atr_percent:.2f}%)")
            if not component_flags["volume_displacement"]:
                component_flags["volume_displacement"] = True

    # Volume acceleration check for LONG reversal
    # For LONG: we want bullish acceleration (volume building as price recovers)
    # OR exhaustion of bearish move (sellers losing steam)
    vol_accel_dir = getattr(indicators, "volume_accel_direction", None) if indicators else None
    vol_is_accel = getattr(indicators, "volume_is_accelerating", False) if indicators else False
    vol_exhaust = getattr(indicators, "volume_exhaustion", False) if indicators else False
    vol_accel_val = getattr(indicators, "volume_acceleration", None) if indicators else None

    if vol_is_accel and vol_accel_dir == "bullish":
        # Volume accelerating in bullish direction - confirming reversal
        signals.append(f"📈 Bullish volume acceleration ({vol_accel_val:.2f})")
        if not component_flags["volume_displacement"]:
            component_flags["volume_displacement"] = True

    if vol_exhaust:
        # Volume exhaustion - prior bearish move losing steam
        signals.append("🔋 Volume exhaustion (sellers tiring)")

    # === 4. LIQUIDITY SWEEP ===
    # Look for sweep of lows (stop hunt) followed by reversal
    low_sweeps = [
        s for s in smc_snapshot.liquidity_sweeps if s.sweep_type == "low" and s.confirmation
    ]

    if low_sweeps:
        component_flags["liquidity_swept"] = True
        latest_sweep = max(low_sweeps, key=lambda s: s.timestamp)
        signals.append(f"Lows swept at {latest_sweep.level:.4f} (stop hunt)")

    # === CALCULATE CONFIDENCE ===
    component_count = sum(component_flags.values())

    # Base confidence from components
    confidence = 25.0 * component_count  # 25 per component, max 100

    # Volume acceleration bonus for reversal confidence
    if vol_is_accel and vol_accel_dir == "bullish" and vol_accel_val:
        if vol_accel_val > 0.2:
            confidence += 10.0  # Strong bullish acceleration into reversal
        elif vol_accel_val > 0.1:
            confidence += 5.0  # Moderate bullish acceleration

    # Volume exhaustion bonus (confirms prior move exhausting)
    if vol_exhaust:
        confidence += 8.0

    # Bonus for cycle context quality
    if cycle_context.phase == CyclePhase.ACCUMULATION:
        confidence += 10.0

    if cycle_context.dcl_confirmation == CycleConfirmation.CONFIRMED:
        confidence += 10.0

    # === DETERMINE IF VALID REVERSAL ===
    # Need at least 2 components for valid reversal, 3+ for HTF bypass
    is_reversal = component_count >= 2 and component_flags["cycle_aligned"]
    htf_bypass = component_count >= 3 and component_flags["choch_detected"]

    # Build rationale
    if is_reversal:
        rationale = f"Bullish reversal: {component_count}/4 components. "
        if component_flags["cycle_aligned"]:
            rationale += f"At {cycle_context.phase.value} phase. "
        if component_flags["choch_detected"]:
            rationale += "CHoCH confirmed structure break. "
        if htf_bypass:
            rationale += "HTF alignment bypassed."
    else:
        rationale = f"Insufficient reversal signals ({component_count}/4)"

    return ReversalContext(
        is_reversal_setup=is_reversal,
        direction="LONG" if is_reversal else "NONE",
        cycle_aligned=component_flags["cycle_aligned"],
        choch_detected=component_flags["choch_detected"],
        volume_displacement=component_flags["volume_displacement"],
        liquidity_swept=component_flags["liquidity_swept"],
        htf_bypass_active=htf_bypass,
        signals=signals,
        confidence=min(100.0, confidence),
        rationale=rationale,
    )


def detect_short_reversal(
    smc_snapshot: SMCSnapshot,
    cycle_context: CycleContext,
    indicators: Optional[IndicatorSnapshot] = None,
) -> ReversalContext:
    """
    Detect bearish reversal setup (for SHORT entry).

    Short reversal conditions:
    1. At distribution/markdown phase with LTR translation
    2. Bearish CHoCH detected (structure breaking downward from uptrend)
    3. Volume spike/displacement confirming the move
    4. Liquidity sweep of highs (stop hunt before reversal)

    Key insight: Cycle lows (DCL/WCL) signal long entries.
    For shorts, we use TRANSLATION (LTR = bearish) + PHASE (distribution/markdown).

    Args:
        smc_snapshot: SMC patterns
        cycle_context: Cycle timing context
        indicators: Technical indicators

    Returns:
        ReversalContext for short reversal
    """
    signals = []
    component_flags = {
        "cycle_aligned": False,
        "choch_detected": False,
        "volume_displacement": False,
        "liquidity_swept": False,
    }

    # === 1. CYCLE ALIGNMENT FOR SHORTS ===
    # LTR translation + distribution/markdown phase
    cycle_score = 0.0

    if cycle_context.translation == CycleTranslation.LTR:
        component_flags["cycle_aligned"] = True
        signals.append("🟥 LTR translation (cycle topped early - bearish)")
        cycle_score = 25.0

    if cycle_context.phase == CyclePhase.DISTRIBUTION:
        component_flags["cycle_aligned"] = True
        signals.append("Distribution phase detected (topping)")
        cycle_score += 20.0

    if cycle_context.phase == CyclePhase.MARKDOWN:
        component_flags["cycle_aligned"] = True
        signals.append("Markdown phase (falling from cycle high)")
        cycle_score += 15.0

    # Price below cycle midpoint = bearish structure
    if (
        cycle_context.cycle_midpoint_price
        and cycle_context.dcl_price
        and indicators
        and hasattr(indicators, "close")
    ):
        # Can check if current price below midpoint
        pass  # Would need current price passed in

    # === 2. CHoCH DETECTION ===
    # Look for bearish CHoCH (in uptrend, breaking downward)
    bearish_choch = _find_bearish_choch(smc_snapshot.structural_breaks)

    if bearish_choch:
        component_flags["choch_detected"] = True
        signals.append(f"Bearish CHoCH at {bearish_choch.level:.4f}")

    # === 3. VOLUME DISPLACEMENT ===
    if indicators and indicators.volume_spike:
        component_flags["volume_displacement"] = True
        signals.append("Volume spike confirms reversal")

    if indicators and indicators.atr_percent:
        if indicators.atr_percent > 0.8:
            signals.append(f"Strong displacement (ATR% {indicators.atr_percent:.2f}%)")
            if not component_flags["volume_displacement"]:
                component_flags["volume_displacement"] = True

    # Volume acceleration check for SHORT reversal
    # For SHORT: we want bearish acceleration (volume building as price drops)
    # OR exhaustion of bullish move (buyers losing steam)
    vol_accel_dir = getattr(indicators, "volume_accel_direction", None) if indicators else None
    vol_is_accel = getattr(indicators, "volume_is_accelerating", False) if indicators else False
    vol_exhaust = getattr(indicators, "volume_exhaustion", False) if indicators else False
    vol_accel_val = getattr(indicators, "volume_acceleration", None) if indicators else None

    if vol_is_accel and vol_accel_dir == "bearish":
        # Volume accelerating in bearish direction - confirming reversal
        signals.append(f"📉 Bearish volume acceleration ({vol_accel_val:.2f})")
        if not component_flags["volume_displacement"]:
            component_flags["volume_displacement"] = True

    if vol_exhaust:
        # Volume exhaustion - prior bullish move losing steam (FOMO buyers exhausted)
        signals.append("🔋 Volume exhaustion (buyers tiring)")

    # === 4. LIQUIDITY SWEEP ===
    # Look for sweep of highs (stop hunt) followed by reversal
    high_sweeps = [
        s for s in smc_snapshot.liquidity_sweeps if s.sweep_type == "high" and s.confirmation
    ]

    if high_sweeps:
        component_flags["liquidity_swept"] = True
        latest_sweep = max(high_sweeps, key=lambda s: s.timestamp)
        signals.append(f"Highs swept at {latest_sweep.level:.4f} (stop hunt)")

    # === CALCULATE CONFIDENCE ===
    component_count = sum(component_flags.values())
    confidence = 25.0 * component_count

    # Volume acceleration bonus for SHORT reversal confidence
    if vol_is_accel and vol_accel_dir == "bearish" and vol_accel_val:
        if vol_accel_val > 0.2:
            confidence += 10.0  # Strong bearish acceleration into reversal
        elif vol_accel_val > 0.1:
            confidence += 5.0  # Moderate bearish acceleration

    # Volume exhaustion bonus (confirms prior bullish move exhausting)
    if vol_exhaust:
        confidence += 8.0

    # Bonus for strong LTR + distribution combo
    if cycle_context.translation == CycleTranslation.LTR and cycle_context.phase in [
        CyclePhase.DISTRIBUTION,
        CyclePhase.MARKDOWN,
    ]:
        confidence += 15.0

    # === DETERMINE IF VALID REVERSAL ===
    is_reversal = component_count >= 2 and component_flags["cycle_aligned"]
    htf_bypass = component_count >= 3 and component_flags["choch_detected"]

    # Build rationale
    if is_reversal:
        rationale = f"Bearish reversal: {component_count}/4 components. "
        if cycle_context.translation == CycleTranslation.LTR:
            rationale += "LTR cycle (topped early). "
        if component_flags["choch_detected"]:
            rationale += "CHoCH confirmed structure break. "
        if htf_bypass:
            rationale += "HTF alignment bypassed."
    else:
        rationale = f"Insufficient reversal signals ({component_count}/4)"

    return ReversalContext(
        is_reversal_setup=is_reversal,
        direction="SHORT" if is_reversal else "NONE",
        cycle_aligned=component_flags["cycle_aligned"],
        choch_detected=component_flags["choch_detected"],
        volume_displacement=component_flags["volume_displacement"],
        liquidity_swept=component_flags["liquidity_swept"],
        htf_bypass_active=htf_bypass,
        signals=signals,
        confidence=min(100.0, confidence),
        rationale=rationale,
    )


def _find_bullish_choch(structural_breaks: List[StructuralBreak]) -> Optional[StructuralBreak]:
    """
    Find the most recent bullish CHoCH (reversal from downtrend to uptrend).

    A bullish CHoCH occurs when price breaks above structure during a downtrend,
    signaling potential trend reversal to the upside.

    Args:
        structural_breaks: List of detected structural breaks

    Returns:
        Most recent bullish CHoCH or None
    """
    # Now correctly checks specific direction
    chochs = [
        sb
        for sb in structural_breaks
        if sb.break_type == "CHoCH" and getattr(sb, "direction", "bullish") == "bullish"
    ]

    if not chochs:
        return None

    # Get most recent CHoCH
    latest = max(chochs, key=lambda c: c.timestamp)
    return latest


def _find_bearish_choch(structural_breaks: List[StructuralBreak]) -> Optional[StructuralBreak]:
    """
    Find the most recent bearish CHoCH (reversal from uptrend to downtrend).

    A bearish CHoCH occurs when price breaks below structure during an uptrend,
    signaling potential trend reversal to the downside.

    Args:
        structural_breaks: List of detected structural breaks

    Returns:
        Most recent bearish CHoCH or None
    """
    # Now correctly checks specific direction
    chochs = [
        sb
        for sb in structural_breaks
        if sb.break_type == "CHoCH" and getattr(sb, "direction", "bearish") == "bearish"
    ]

    if not chochs:
        return None

    # Get most recent CHoCH
    latest = max(chochs, key=lambda c: c.timestamp)
    return latest


def combine_reversal_with_cycle_bonus(
    reversal_context: ReversalContext, cycle_context: CycleContext
) -> float:
    """
    Calculate combined synergy bonus when reversal aligns with cycle.

    Used by confluence scorer to add synergy bonuses for cycle-aligned reversals.

    Bonus structure:
    - Cycle Turn Bonus (+15): CHoCH + cycle extreme + volume
    - Distribution Break Bonus (+15): CHoCH + LTR + distribution phase
    - Accumulation Zone Bonus (+12): Liquidity sweep + DCL/WCL + bullish OB

    Args:
        reversal_context: Detected reversal setup
        cycle_context: Cycle timing context

    Returns:
        Total synergy bonus to add
    """
    bonus = 0.0

    if not reversal_context.is_reversal_setup:
        return 0.0

    # === CYCLE TURN BONUS (for longs at cycle low) ===
    if reversal_context.direction == "LONG":
        if (
            reversal_context.choch_detected
            and reversal_context.cycle_aligned
            and (cycle_context.in_dcl_zone or cycle_context.in_wcl_zone)
        ):
            bonus += 15.0
            logger.debug("📈 Cycle Turn bonus (+15): CHoCH at cycle low")

        # Accumulation zone bonus
        if reversal_context.liquidity_swept and cycle_context.phase == CyclePhase.ACCUMULATION:
            bonus += 12.0
            logger.debug("📈 Accumulation Zone bonus (+12): Sweep at accumulation")

    # === DISTRIBUTION BREAK BONUS (for shorts at cycle high) ===
    if reversal_context.direction == "SHORT":
        if (
            reversal_context.choch_detected
            and cycle_context.translation == CycleTranslation.LTR
            and cycle_context.phase in [CyclePhase.DISTRIBUTION, CyclePhase.MARKDOWN]
        ):
            bonus += 15.0
            logger.debug("📉 Distribution Break bonus (+15): CHoCH at LTR distribution")

        # Highs swept bonus
        if reversal_context.liquidity_swept and cycle_context.phase == CyclePhase.DISTRIBUTION:
            bonus += 12.0
            logger.debug("📉 Distribution Sweep bonus (+12): Highs swept at top")

    # === HTF BYPASS BONUS ===
    # Extra confidence when bypass is active
    if reversal_context.htf_bypass_active:
        bonus += 5.0
        logger.debug("🔓 HTF Bypass bonus (+5): Structure broken at cycle extreme")

    return bonus


def get_reversal_rationale_for_plan(
    reversal_context: Optional[ReversalContext] = None,
    cycle_context: Optional[CycleContext] = None,
    reversal_metadata: Optional[dict] = None,
    cycle_metadata: Optional[dict] = None,
) -> str:
    """
    Generate detailed rationale for trade plan when reversal context is active.

    Accepts either dataclass objects or serialized metadata dicts.

    Args:
        reversal_context: Detected reversal (dataclass)
        cycle_context: Cycle timing context (dataclass)
        reversal_metadata: Serialized reversal dict (from plan.metadata)
        cycle_metadata: Serialized cycle dict (from plan.metadata)

    Returns:
        Human-readable rationale string
    """
    # If using metadata dicts, extract values directly
    if reversal_metadata:
        if not reversal_metadata.get("is_reversal", False):
            return ""

        parts = []

        # Direction
        direction = reversal_metadata.get("reversal_type", "")
        if "long" in direction.lower() or "bullish" in direction.lower():
            parts.append("🔄 BULLISH REVERSAL DETECTED")
        elif "short" in direction.lower() or "bearish" in direction.lower():
            parts.append("🔄 BEARISH REVERSAL DETECTED")
        else:
            parts.append("🔄 REVERSAL DETECTED")

        # Cycle context from metadata
        if cycle_metadata:
            phase = cycle_metadata.get("phase", "unknown")
            if phase != "unknown":
                parts.append(f"Cycle phase: {phase.upper()}")

            translation = cycle_metadata.get("translation", "unknown")
            if translation != "unknown":
                translation_emoji = {"ltr": "🟥", "mtr": "🟧", "rtr": "🟩"}
                emoji = translation_emoji.get(translation.lower(), "")
                parts.append(f"Translation: {emoji} {translation.upper()}")

        # Reversal rationale from metadata
        rationale = reversal_metadata.get("rationale", "")
        if rationale:
            parts.append(rationale)

        # Confidence
        confidence = reversal_metadata.get("confidence", 0)
        if confidence:
            parts.append(f"Reversal confidence: {confidence:.0f}%")

        # Cycle-aligned status
        if reversal_metadata.get("cycle_aligned"):
            parts.append("✓ Cycle-aligned reversal")

        return " | ".join(parts)

    # Fall back to original dataclass logic
    if not reversal_context or not reversal_context.is_reversal_setup:
        return ""

    parts = []

    # Direction
    if reversal_context.direction == "LONG":
        parts.append("🔄 BULLISH REVERSAL DETECTED")
    else:
        parts.append("🔄 BEARISH REVERSAL DETECTED")

    # Cycle context
    if cycle_context.phase != CyclePhase.UNKNOWN:
        parts.append(f"Cycle phase: {cycle_context.phase.value.upper()}")

    if cycle_context.translation != CycleTranslation.UNKNOWN:
        translation_emoji = {
            CycleTranslation.LTR: "🟥",
            CycleTranslation.MTR: "🟧",
            CycleTranslation.RTR: "🟩",
        }
        emoji = translation_emoji.get(cycle_context.translation, "")
        parts.append(f"Translation: {emoji} {cycle_context.translation.value}")

    # Components
    components = []
    if reversal_context.cycle_aligned:
        components.append("cycle timing")
    if reversal_context.choch_detected:
        components.append("CHoCH")
    if reversal_context.volume_displacement:
        components.append("volume")
    if reversal_context.liquidity_swept:
        components.append("liquidity sweep")

    if components:
        parts.append(f"Reversal signals: {', '.join(components)}")

    # Bypass status
    if reversal_context.htf_bypass_active:
        parts.append("⚡ HTF alignment bypassed (cycle extreme + structure broken)")

    # Confidence
    parts.append(f"Reversal confidence: {reversal_context.confidence:.0f}%")

    return " | ".join(parts)


def validate_reversal_profile(
    reversal: ReversalContext, profile: str = "balanced"
) -> ReversalContext:
    """
    Validate reversal quality against scanner mode requirements.

    Modes apply different gates:
    - Surgical/Precision: Requires High Confidence (>75%) OR robust signal count (3+).
    - Overwatch/Macro: Requires Cycle Alignment (DCL/WCL/LTR).
    - Stealth: Requires 'Hidden' intent (Liquidity Sweep or Volume Displacement).
    - Strike/Aggressive: Standard Confidence (>50%).

    If validation fails, returns a context with is_reversal_setup=False
    and an updated rationale explaining the rejection.
    """
    if not reversal.is_reversal_setup:
        return reversal

    profile = profile.lower()
    reject_reason = ""

    # 1. Surgical/Precision (Strict Quality)
    if profile in ("surgical", "precision"):
        # Require High Confidence OR 3+ Components
        # htf_bypass_active usually implies high structural quality
        is_high_quality = reversal.confidence >= 75.0 or reversal.htf_bypass_active
        if not is_high_quality:
            # Check component count manually if htf_bypass not active
            comp_count = sum(
                [
                    reversal.cycle_aligned,
                    reversal.choch_detected,
                    reversal.volume_displacement,
                    reversal.liquidity_swept,
                ]
            )
            if comp_count < 3:
                reject_reason = f"Surgical requires High Conf (75%+) or 3+ Signals. Current: {reversal.confidence:.0f}% / {comp_count}"

    # 2. Overwatch/Macro (Strict Structure/Cycle)
    elif profile in ("overwatch", "macro_surveillance"):
        # Must be cycle aligned (TopDown approach)
        if not reversal.cycle_aligned:
            reject_reason = "Overwatch requires Cycle Alignment (DCL/WCL/LTR)"

    # 3. Stealth (Smart Money Footprint)
    elif "stealth" in profile:
        # Must have "Hidden" signs: Sweep or Volume (CHoCH alone is too obvious/late)
        if not (reversal.liquidity_swept or reversal.volume_displacement):
            reject_reason = "Stealth requires Liquidity Sweep or Volume Displacement"

    # 4. Strike/Aggressive (Momentum)
    elif profile in ("strike", "intraday_aggressive"):
        if reversal.confidence < 50.0:
            reject_reason = (
                f"Strike requires min 50% confidence. Current: {reversal.confidence:.0f}%"
            )

    if reject_reason:
        # Return modified copy
        from dataclasses import replace

        return replace(reversal, is_reversal_setup=False, rationale=f"⛔ {reject_reason}")

    return reversal
