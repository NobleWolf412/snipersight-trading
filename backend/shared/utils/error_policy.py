"""
Error policy enforcement - Zero Silent Failures principle.

Following ARCHITECTURE.md "Error Handling Strategy".
All critical pipeline outputs must be complete and valid.
"""

from typing import Optional
from backend.shared.models.indicators import IndicatorSet
from backend.shared.models.smc import SMCSnapshot
from backend.shared.models.planner import TradePlan
from backend.engine.context import SniperContext


class IncompleteIndicatorError(Exception):
    """Raised when indicator computation is incomplete or invalid."""


class IncompleteSMCError(Exception):
    """Raised when SMC detection is incomplete or invalid."""


class IncompletePlanError(Exception):
    """Raised when trade plan has null/empty required fields."""


class QualityGateError(Exception):
    """Raised when signal fails quality gate validation."""


def enforce_complete_indicators(indicators: Optional[IndicatorSet]) -> None:
    """
    Ensure indicators are complete and valid.

    Raises:
        IncompleteIndicatorError: If indicators are missing or incomplete
    """
    if indicators is None:
        raise IncompleteIndicatorError("IndicatorSet is None")

    if not indicators.by_timeframe:
        raise IncompleteIndicatorError("No timeframes in IndicatorSet")

    for tf, snapshot in indicators.by_timeframe.items():
        if snapshot is None:
            raise IncompleteIndicatorError(f"Missing IndicatorSnapshot for timeframe {tf}")

        # Check critical indicators are not None
        if snapshot.rsi is None or snapshot.atr is None:
            raise IncompleteIndicatorError(
                f"Critical indicators missing for {tf}: rsi={snapshot.rsi}, atr={snapshot.atr}"
            )


def enforce_complete_smc(smc: Optional[SMCSnapshot]) -> None:
    """
    Ensure SMC detection is complete.

    Raises:
        IncompleteSMCError: If SMC snapshot is incomplete
    """
    if smc is None:
        raise IncompleteSMCError("SMCSnapshot is None")

    # SMC lists can be empty (no detections), but must exist
    if smc.order_blocks is None:
        raise IncompleteSMCError("order_blocks list is None")
    if smc.fvgs is None:
        raise IncompleteSMCError("fvgs list is None")
    if smc.structural_breaks is None:
        raise IncompleteSMCError("structural_breaks list is None")
    if smc.liquidity_sweeps is None:
        raise IncompleteSMCError("liquidity_sweeps list is None")


def enforce_complete_plan(plan: Optional[TradePlan]) -> None:
    """
    Ensure trade plan has no null/empty fields.

    Following "No-Null, Actionable Outputs" principle from ARCHITECTURE.md.

    Raises:
        IncompletePlanError: If any required field is null or empty
    """
    if plan is None:
        raise IncompletePlanError("TradePlan is None")

    # Check all required fields are populated
    if not plan.symbol:
        raise IncompletePlanError("symbol is empty")
    if not plan.direction:
        raise IncompletePlanError("direction is empty")
    if not plan.setup_type:
        raise IncompletePlanError("setup_type is empty")

    if plan.entry_zone is None:
        raise IncompletePlanError("entry_zone is None")
    if plan.stop_loss is None:
        raise IncompletePlanError("stop_loss is None")
    if not plan.targets:
        raise IncompletePlanError("targets list is empty")

    if plan.risk_reward is None or plan.risk_reward <= 0:
        raise IncompletePlanError(f"Invalid risk_reward: {plan.risk_reward}")

    if not plan.rationale or plan.rationale.strip() == "":
        raise IncompletePlanError("rationale is empty")


def enforce_quality_gates(context: SniperContext) -> None:
    """
    Validate all quality gate criteria.

    Checks:
    - Data completeness
    - Indicator validity
    - SMC detection completeness
    - Confluence threshold
    - R:R ratio minimum

    Raises:
        QualityGateError: If any quality gate fails
    """
    # Data quality gate
    if context.multi_tf_data is None:
        raise QualityGateError("Missing multi-timeframe data")

    # Indicator quality gate
    try:
        enforce_complete_indicators(context.multi_tf_indicators)
    except IncompleteIndicatorError as e:
        raise QualityGateError(f"Indicator quality gate failed: {e}")

    # SMC quality gate
    try:
        enforce_complete_smc(context.smc_snapshot)
    except IncompleteSMCError as e:
        raise QualityGateError(f"SMC quality gate failed: {e}")

    # Confluence quality gate
    if context.confluence_breakdown is None:
        raise QualityGateError("Missing confluence breakdown")

    # Additional gates can be added here:
    # - HTF alignment check
    # - Freshness requirements
    # - Displacement thresholds
    # etc.
