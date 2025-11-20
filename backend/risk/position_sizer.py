"""
Position Sizing Calculator

Implements multiple position sizing strategies with comprehensive safety checks.
Follows "No Silent Failures" - all invalid inputs raise exceptions.

Sizing Strategies:
1. Fixed Fractional - Risk fixed % of account per trade
2. Kelly Criterion - Optimal sizing based on win rate and payoff ratio
3. ATR-Based - Volatility-adjusted position sizing
4. Fixed Dollar Risk - Risk fixed dollar amount per trade

All calculations respect max position size limits and minimum order requirements.
"""

import math
from typing import Optional, Literal
from dataclasses import dataclass


@dataclass
class PositionSize:
    """
    Position sizing result with all relevant metrics.
    
    Attributes:
        quantity: Position size in base asset (e.g., BTC)
        notional_value: Position value in quote asset (e.g., USDT)
        risk_amount: Dollar amount at risk
        risk_percentage: Percentage of account at risk
        position_percentage: Position size as % of account
        method: Sizing method used
        metadata: Additional calculation details
    """
    quantity: float
    notional_value: float
    risk_amount: float
    risk_percentage: float
    position_percentage: float
    method: str
    metadata: dict
    
    def __post_init__(self):
        """Validate position size data."""
        if self.quantity < 0:
            raise ValueError(f"Position quantity must be >= 0, got {self.quantity}")
        if self.notional_value < 0:
            raise ValueError(f"Notional value must be >= 0, got {self.notional_value}")
        if self.risk_amount < 0:
            raise ValueError(f"Risk amount must be >= 0, got {self.risk_amount}")
        if not 0 <= self.risk_percentage <= 100:
            raise ValueError(f"Risk percentage must be 0-100, got {self.risk_percentage}")


class PositionSizer:
    """
    Position sizing calculator with multiple strategies.
    
    Implements industry-standard position sizing methods with safety constraints:
    - Account balance limits
    - Maximum position sizes
    - Minimum order requirements
    - Risk percentage caps
    
    Usage:
        sizer = PositionSizer(
            account_balance=10000,
            max_position_pct=25.0,
            max_risk_pct=2.0
        )
        
        # Fixed fractional sizing
        size = sizer.calculate_fixed_fractional(
            risk_pct=1.0,
            entry_price=50000,
            stop_price=49000
        )
        
        # Kelly criterion
        size = sizer.calculate_kelly(
            win_rate=0.65,
            avg_win=2.5,
            avg_loss=1.0,
            entry_price=50000,
            stop_price=49000
        )
    """
    
    def __init__(
        self,
        account_balance: float,
        max_position_pct: float = 25.0,
        max_risk_pct: float = 2.0,
        min_order_value: float = 10.0
    ):
        """
        Initialize position sizer.
        
        Args:
            account_balance: Total account balance in quote asset (USDT)
            max_position_pct: Maximum position size as % of account (default 25%)
            max_risk_pct: Maximum risk per trade as % of account (default 2%)
            min_order_value: Minimum order value required by exchange (default $10)
            
        Raises:
            ValueError: If any parameter is invalid
        """
        if account_balance <= 0:
            raise ValueError(f"Account balance must be positive, got {account_balance}")
        if not 0 < max_position_pct <= 100:
            raise ValueError(f"Max position % must be 0-100, got {max_position_pct}")
        if not 0 < max_risk_pct <= 100:
            raise ValueError(f"Max risk % must be 0-100, got {max_risk_pct}")
        if min_order_value < 0:
            raise ValueError(f"Min order value must be >= 0, got {min_order_value}")
        
        self.account_balance = account_balance
        self.max_position_pct = max_position_pct
        self.max_risk_pct = max_risk_pct
        self.min_order_value = min_order_value
    
    def calculate_fixed_fractional(
        self,
        risk_pct: float,
        entry_price: float,
        stop_price: float,
        leverage: float = 1.0
    ) -> PositionSize:
        """
        Calculate position size using fixed fractional method.
        
        Risk fixed percentage of account balance per trade.
        Most common retail position sizing method.
        
        Formula:
            risk_amount = account_balance * (risk_pct / 100)
            stop_distance = abs(entry_price - stop_price)
            quantity = risk_amount / stop_distance
        
        Args:
            risk_pct: Percentage of account to risk (e.g., 1.0 = 1%)
            entry_price: Entry price for position
            stop_price: Stop loss price
            leverage: Leverage multiplier (default 1.0 for spot)
            
        Returns:
            PositionSize with calculated metrics
            
        Raises:
            ValueError: If inputs are invalid
        """
        # Validate inputs
        if not 0 < risk_pct <= self.max_risk_pct:
            raise ValueError(
                f"Risk % must be 0-{self.max_risk_pct}, got {risk_pct}"
            )
        if entry_price <= 0:
            raise ValueError(f"Entry price must be positive, got {entry_price}")
        if stop_price <= 0:
            raise ValueError(f"Stop price must be positive, got {stop_price}")
        if entry_price == stop_price:
            raise ValueError("Entry and stop prices must be different")
        if leverage < 1.0:
            raise ValueError(f"Leverage must be >= 1.0, got {leverage}")
        
        # Calculate risk amount
        risk_amount = self.account_balance * (risk_pct / 100)
        
        # Calculate stop distance
        stop_distance = abs(entry_price - stop_price)
        
        # Calculate base quantity (without leverage)
        # Quantity needed so that quantity * stop_distance = risk_amount
        quantity = risk_amount / stop_distance
        
        # Calculate notional value (position value in quote currency)
        notional_value = quantity * entry_price
        
        # Note: Leverage does NOT change the quantity or risk
        # Leverage only affects margin requirement
        # Risk is still quantity * stop_distance
        
        # Apply constraints
        quantity, notional_value, actual_risk = self._apply_constraints(
            quantity=quantity,
            notional_value=notional_value,
            entry_price=entry_price,
            stop_distance=stop_distance,
            leverage=leverage
        )
        
        # Calculate final metrics
        position_pct = (notional_value / self.account_balance) * 100
        actual_risk_pct = (actual_risk / self.account_balance) * 100
        
        return PositionSize(
            quantity=quantity,
            notional_value=notional_value,
            risk_amount=actual_risk,
            risk_percentage=actual_risk_pct,
            position_percentage=position_pct,
            method="fixed_fractional",
            metadata={
                "target_risk_pct": risk_pct,
                "entry_price": entry_price,
                "stop_price": stop_price,
                "stop_distance": stop_distance,
                "leverage": leverage
            }
        )
    
    def calculate_kelly(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        entry_price: float,
        stop_price: float,
        kelly_fraction: float = 0.25,
        leverage: float = 1.0
    ) -> PositionSize:
        """
        Calculate position size using Kelly Criterion.
        
        Optimal position sizing based on win rate and payoff ratio.
        Kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_loss
        
        Uses fractional Kelly (default 25%) to reduce risk of ruin.
        
        Args:
            win_rate: Historical win rate (0-1, e.g., 0.65 = 65%)
            avg_win: Average win in R multiples (e.g., 2.5R)
            avg_loss: Average loss in R multiples (typically 1.0R)
            entry_price: Entry price for position
            stop_price: Stop loss price
            kelly_fraction: Fraction of Kelly to use (default 0.25 = quarter Kelly)
            leverage: Leverage multiplier (default 1.0 for spot)
            
        Returns:
            PositionSize with calculated metrics
            
        Raises:
            ValueError: If inputs are invalid
        """
        # Validate inputs
        if not 0 < win_rate < 1:
            raise ValueError(f"Win rate must be 0-1, got {win_rate}")
        if avg_win <= 0:
            raise ValueError(f"Average win must be positive, got {avg_win}")
        if avg_loss <= 0:
            raise ValueError(f"Average loss must be positive, got {avg_loss}")
        if not 0 < kelly_fraction <= 1:
            raise ValueError(f"Kelly fraction must be 0-1, got {kelly_fraction}")
        if entry_price <= 0:
            raise ValueError(f"Entry price must be positive, got {entry_price}")
        if stop_price <= 0:
            raise ValueError(f"Stop price must be positive, got {stop_price}")
        if entry_price == stop_price:
            raise ValueError("Entry and stop prices must be different")
        if leverage < 1.0:
            raise ValueError(f"Leverage must be >= 1.0, got {leverage}")
        
        # Calculate Kelly percentage
        # Kelly = (p * b - q) / b
        # Where: p = win rate, q = 1-p, b = avg_win/avg_loss
        b = avg_win / avg_loss  # Payoff ratio
        kelly_pct = ((win_rate * b) - (1 - win_rate)) / b
        
        # Apply fractional Kelly
        kelly_pct = kelly_pct * kelly_fraction
        
        # Kelly can be negative (edge < 0) or > 100% - cap it
        kelly_pct = max(0, min(kelly_pct, self.max_risk_pct / 100))
        
        # Convert to risk percentage (capped at max_risk_pct)
        risk_pct = min(kelly_pct * 100, self.max_risk_pct)
        
        # Use fixed fractional with calculated risk %
        result = self.calculate_fixed_fractional(
            risk_pct=risk_pct,
            entry_price=entry_price,
            stop_price=stop_price,
            leverage=leverage
        )
        
        # Update metadata
        result.method = "kelly_criterion"
        result.metadata.update({
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "payoff_ratio": b,
            "kelly_pct": kelly_pct * 100,
            "kelly_fraction": kelly_fraction,
            "capped_at_max_risk": kelly_pct * 100 > self.max_risk_pct
        })
        
        return result
    
    def calculate_atr_based(
        self,
        atr: float,
        atr_multiplier: float,
        entry_price: float,
        risk_pct: Optional[float] = None,
        leverage: float = 1.0
    ) -> PositionSize:
        """
        Calculate position size using ATR-based method.
        
        Sets stop distance as ATR * multiplier, then sizes position
        to risk specified percentage of account.
        
        Args:
            atr: Average True Range value
            atr_multiplier: ATR multiplier for stop (e.g., 2.0 = 2x ATR)
            entry_price: Entry price for position
            risk_pct: Risk percentage (uses max_risk_pct if None)
            leverage: Leverage multiplier (default 1.0 for spot)
            
        Returns:
            PositionSize with calculated metrics
            
        Raises:
            ValueError: If inputs are invalid
        """
        # Validate inputs
        if atr <= 0:
            raise ValueError(f"ATR must be positive, got {atr}")
        if atr_multiplier <= 0:
            raise ValueError(f"ATR multiplier must be positive, got {atr_multiplier}")
        if entry_price <= 0:
            raise ValueError(f"Entry price must be positive, got {entry_price}")
        if leverage < 1.0:
            raise ValueError(f"Leverage must be >= 1.0, got {leverage}")
        
        # Use max risk if not specified
        if risk_pct is None:
            risk_pct = self.max_risk_pct
        
        # Calculate stop distance
        stop_distance = atr * atr_multiplier
        
        # Determine stop price (assume long, will work same for short)
        stop_price = entry_price - stop_distance
        
        # Use fixed fractional with calculated stop
        result = self.calculate_fixed_fractional(
            risk_pct=risk_pct,
            entry_price=entry_price,
            stop_price=stop_price,
            leverage=leverage
        )
        
        # Update metadata
        result.method = "atr_based"
        result.metadata.update({
            "atr": atr,
            "atr_multiplier": atr_multiplier,
            "stop_distance_atr": atr_multiplier
        })
        
        return result
    
    def calculate_fixed_dollar_risk(
        self,
        risk_amount: float,
        entry_price: float,
        stop_price: float,
        leverage: float = 1.0
    ) -> PositionSize:
        """
        Calculate position size for fixed dollar risk.
        
        Risk specific dollar amount per trade, useful for:
        - Consistent P&L across trades
        - Simple accounting
        - Professional money management
        
        Args:
            risk_amount: Dollar amount to risk (e.g., $100)
            entry_price: Entry price for position
            stop_price: Stop loss price
            leverage: Leverage multiplier (default 1.0 for spot)
            
        Returns:
            PositionSize with calculated metrics
            
        Raises:
            ValueError: If inputs are invalid
        """
        # Validate inputs
        if risk_amount <= 0:
            raise ValueError(f"Risk amount must be positive, got {risk_amount}")
        if risk_amount > self.account_balance:
            raise ValueError(
                f"Risk amount ({risk_amount}) exceeds account balance ({self.account_balance})"
            )
        if entry_price <= 0:
            raise ValueError(f"Entry price must be positive, got {entry_price}")
        if stop_price <= 0:
            raise ValueError(f"Stop price must be positive, got {stop_price}")
        if entry_price == stop_price:
            raise ValueError("Entry and stop prices must be different")
        if leverage < 1.0:
            raise ValueError(f"Leverage must be >= 1.0, got {leverage}")
        
        # Calculate stop distance
        stop_distance = abs(entry_price - stop_price)
        
        # Calculate base quantity
        quantity = risk_amount / stop_distance
        
        # Calculate notional value
        notional_value = quantity * entry_price
        
        # Note: Leverage does NOT change quantity or risk
        # It only affects margin requirement
        
        # Apply constraints
        quantity, notional_value, actual_risk = self._apply_constraints(
            quantity=quantity,
            notional_value=notional_value,
            entry_price=entry_price,
            stop_distance=stop_distance,
            leverage=leverage
        )
        
        # Calculate final metrics
        position_pct = (notional_value / self.account_balance) * 100
        risk_pct = (actual_risk / self.account_balance) * 100
        
        return PositionSize(
            quantity=quantity,
            notional_value=notional_value,
            risk_amount=actual_risk,
            risk_percentage=risk_pct,
            position_percentage=position_pct,
            method="fixed_dollar_risk",
            metadata={
                "target_risk_amount": risk_amount,
                "entry_price": entry_price,
                "stop_price": stop_price,
                "stop_distance": stop_distance,
                "leverage": leverage
            }
        )
    
    def _apply_constraints(
        self,
        quantity: float,
        notional_value: float,
        entry_price: float,
        stop_distance: float,
        leverage: float
    ) -> tuple[float, float, float]:
        """
        Apply position size constraints and return adjusted values.
        
        Constraints:
        1. Minimum order value
        2. Maximum position size (% of account)
        3. Maximum account balance
        
        Args:
            quantity: Raw calculated quantity
            notional_value: Raw notional value
            entry_price: Entry price
            stop_distance: Stop distance in price
            leverage: Leverage multiplier
            
        Returns:
            Tuple of (adjusted_quantity, adjusted_notional, actual_risk)
        """
        # For leveraged positions, adjust notional calculation
        # notional_value represents the full position value
        # but with leverage, we only need margin = notional / leverage
        
        # Constraint 1: Minimum order value
        if notional_value < self.min_order_value:
            # Scale up to minimum
            scale_factor = self.min_order_value / notional_value
            quantity = quantity * scale_factor
            notional_value = self.min_order_value
        
        # Constraint 2: Maximum position size
        max_position_value = self.account_balance * (self.max_position_pct / 100)
        if notional_value > max_position_value:
            # Scale down to max position
            scale_factor = max_position_value / notional_value
            quantity = quantity * scale_factor
            notional_value = max_position_value
        
        # Constraint 3: Can't exceed account balance (accounting for leverage)
        # With leverage, the margin required is notional_value / leverage
        margin_required = notional_value / leverage
        if margin_required > self.account_balance:
            scale_factor = (self.account_balance * leverage) / notional_value
            quantity = quantity * scale_factor
            notional_value = self.account_balance * leverage
        
        # Calculate actual risk after constraints
        # Risk is always quantity * stop_distance, regardless of leverage
        actual_risk = quantity * stop_distance
        
        return quantity, notional_value, actual_risk
    
    def update_balance(self, new_balance: float) -> None:
        """
        Update account balance (e.g., after profit/loss).
        
        Args:
            new_balance: New account balance
            
        Raises:
            ValueError: If new balance is invalid
        """
        if new_balance < 0:
            raise ValueError(f"Account balance cannot be negative, got {new_balance}")
        
        self.account_balance = new_balance
    
    def get_max_position_value(self) -> float:
        """Get maximum position value based on current settings."""
        return self.account_balance * (self.max_position_pct / 100)
    
    def get_max_risk_value(self) -> float:
        """Get maximum risk value based on current settings."""
        return self.account_balance * (self.max_risk_pct / 100)
    
    def validate_position_size(
        self,
        quantity: float,
        entry_price: float,
        stop_price: float
    ) -> tuple[bool, str]:
        """
        Validate if a position size meets all constraints.
        
        Args:
            quantity: Position quantity
            entry_price: Entry price
            stop_price: Stop price
            
        Returns:
            Tuple of (is_valid, reason)
        """
        notional_value = quantity * entry_price
        
        # Check minimum order value
        if notional_value < self.min_order_value:
            return False, f"Position value ${notional_value:.2f} below minimum ${self.min_order_value:.2f}"
        
        # Check maximum position size
        max_value = self.get_max_position_value()
        if notional_value > max_value:
            return False, f"Position value ${notional_value:.2f} exceeds max ${max_value:.2f}"
        
        # Check risk
        stop_distance = abs(entry_price - stop_price)
        risk_amount = quantity * stop_distance
        max_risk = self.get_max_risk_value()
        
        if risk_amount > max_risk:
            return False, f"Risk ${risk_amount:.2f} exceeds max ${max_risk:.2f}"
        
        return True, "Position size valid"
