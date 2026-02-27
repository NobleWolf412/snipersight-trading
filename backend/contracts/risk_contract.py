"""
Risk management contracts.

Defines interfaces for position sizing, exposure limits, and compliance.
Following ARCHITECTURE.md risk package specifications.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional
from backend.shared.models.planner import TradePlan


@dataclass
class RiskPlan:
    """Risk validation result and position sizing."""

    approved: bool
    position_size: float
    leverage: float
    risk_amount: float
    risk_percentage: float
    rejection_reason: Optional[str] = None


class PositionSizer(ABC):
    """Abstract interface for position sizing calculation."""

    @abstractmethod
    def calculate_position_size(
        self,
        account_balance: float,
        risk_pct: float,
        entry: float,
        stop: float,
        leverage: float = 1.0,
    ) -> float:
        """
        Calculate position size based on account risk parameters.

        Args:
            account_balance: Total account balance
            risk_pct: Maximum risk percentage per trade
            entry: Entry price
            stop: Stop loss price
            leverage: Allowed leverage multiplier

        Returns:
            Position size in base currency
        """


class ExposureManager(ABC):
    """Abstract interface for exposure limit checking."""

    @abstractmethod
    def check_exposure_limits(
        self, symbol: str, proposed_size: float, existing_positions: Dict
    ) -> bool:
        """
        Check if proposed position violates exposure limits.

        Args:
            symbol: Trading symbol
            proposed_size: Proposed position size
            existing_positions: Dictionary of current open positions

        Returns:
            True if within limits, False otherwise
        """


class ComplianceChecker(ABC):
    """Abstract interface for compliance validation."""

    @abstractmethod
    def validate_trade(self, plan: TradePlan, account: Dict, existing_positions: Dict) -> RiskPlan:
        """
        Validate trade plan against all risk rules and compliance checks.

        Args:
            plan: Complete trade plan to validate
            account: Account information
            existing_positions: Current open positions

        Returns:
            RiskPlan with approval status and sizing
        """
