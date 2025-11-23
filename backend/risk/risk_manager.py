"""
Risk Manager

Portfolio-level risk control and compliance validation.
Enforces exposure limits, correlation checks, and loss limits.

Features:
- Per-asset exposure limits
- Maximum concurrent positions
- Daily/weekly loss limits
- Portfolio correlation checks
- Pre-execution compliance validation
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import logging
import threading

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """
    Active position representation.
    
    Attributes:
        symbol: Trading pair (e.g., 'BTC/USDT')
        direction: 'LONG' or 'SHORT'
        quantity: Position size in base asset
        entry_price: Average entry price
        current_price: Current market price
        unrealized_pnl: Unrealized profit/loss
        opened_at: Position open timestamp
    """
    symbol: str
    direction: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def notional_value(self) -> float:
        """Calculate position notional value."""
        return self.quantity * self.current_price
    
    @property
    def pnl_pct(self) -> float:
        """Calculate PnL as percentage."""
        if self.entry_price == 0:
            return 0.0
        
        if self.direction == "LONG":
            return ((self.current_price - self.entry_price) / self.entry_price) * 100
        else:  # SHORT
            return ((self.entry_price - self.current_price) / self.entry_price) * 100


@dataclass
class Trade:
    """
    Completed trade record.
    
    Attributes:
        symbol: Trading pair
        direction: 'LONG' or 'SHORT'
        pnl: Realized profit/loss
        closed_at: Trade close timestamp
    """
    symbol: str
    direction: str
    pnl: float
    closed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RiskCheck:
    """
    Risk validation result.
    
    Attributes:
        passed: Whether risk check passed
        reason: Explanation if failed
        limits_hit: List of specific limits violated
    """
    passed: bool
    reason: str = ""
    limits_hit: List[str] = field(default_factory=list)


class RiskManager:
    """
    Portfolio-level risk management and compliance.
    
    Enforces multiple layers of risk control:
    - Position limits (max open positions)
    - Exposure limits (max % in single asset)
    - Correlation limits (max exposure to correlated assets)
    - Loss limits (daily, weekly drawdown caps)
    - Concentration limits (max % of portfolio in one trade)
    
    Usage:
        risk_mgr = RiskManager(
            account_balance=10000,
            max_open_positions=5,
            max_asset_exposure_pct=20.0,
            max_daily_loss_pct=5.0
        )
        
        # Check if new trade is allowed
        check = risk_mgr.validate_new_trade(
            symbol="BTC/USDT",
            direction="LONG",
            position_value=2000,
            risk_amount=100
        )
        
        if check.passed:
            # Execute trade
            pass
        else:
            logger.warning(f"Trade rejected: {check.reason}")
    """
    
    def __init__(
        self,
        account_balance: float,
        max_open_positions: int = 5,
        max_asset_exposure_pct: float = 20.0,
        max_correlated_exposure_pct: float = 40.0,
        max_daily_loss_pct: float = 5.0,
        max_weekly_loss_pct: float = 10.0,
        max_position_concentration_pct: float = 25.0
    ):
        """
        Initialize risk manager.
        
        Args:
            account_balance: Total account balance
            max_open_positions: Maximum concurrent positions
            max_asset_exposure_pct: Max exposure to single asset (% of account)
            max_correlated_exposure_pct: Max exposure to correlated assets
            max_daily_loss_pct: Maximum daily loss (% of account)
            max_weekly_loss_pct: Maximum weekly loss (% of account)
            max_position_concentration_pct: Max single position size (% of account)
            
        Raises:
            ValueError: If any parameter is invalid
        """
        if account_balance <= 0:
            raise ValueError(f"Account balance must be positive, got {account_balance}")
        if max_open_positions < 1:
            raise ValueError(f"Max open positions must be >= 1, got {max_open_positions}")
        if not 0 < max_asset_exposure_pct <= 100:
            raise ValueError(f"Max asset exposure must be 0-100%, got {max_asset_exposure_pct}")
        if not 0 < max_daily_loss_pct <= 100:
            raise ValueError(f"Max daily loss must be 0-100%, got {max_daily_loss_pct}")
        if not 0 < max_weekly_loss_pct <= 100:
            raise ValueError(f"Max weekly loss must be 0-100%, got {max_weekly_loss_pct}")
        
        self.account_balance = account_balance
        self.initial_balance = account_balance
        self.max_open_positions = max_open_positions
        self.max_asset_exposure_pct = max_asset_exposure_pct
        self.max_correlated_exposure_pct = max_correlated_exposure_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_weekly_loss_pct = max_weekly_loss_pct
        self.max_position_concentration_pct = max_position_concentration_pct
        
        # Active positions
        self.positions: Dict[str, Position] = {}
        
        # Trade history
        self.trade_history: List[Trade] = []
        
        # Asset correlation groups (simplified - BTC correlation)
        # In production, this would be dynamic based on actual correlation analysis
        self.correlation_groups = {
            'BTC': ['BTC/USDT', 'BTC/USD', 'BTCUSDT'],
            'ETH': ['ETH/USDT', 'ETH/USD', 'ETHUSDT'],
            'MAJORS': ['BTC/USDT', 'ETH/USDT', 'BNB/USDT'],
            'ALTS': []  # Define alt correlation groups as needed
        }

        # Lock for thread-safe position/trade mutations under concurrent scans
        self._lock = threading.Lock()
    
    def validate_new_trade(
        self,
        symbol: str,
        direction: str,
        position_value: float,
        risk_amount: float
    ) -> RiskCheck:
        """
        Validate if new trade passes all risk checks.
        
        Performs comprehensive pre-execution validation:
        1. Max open positions check
        2. Asset exposure limit check
        3. Correlated exposure check
        4. Daily loss limit check
        5. Weekly loss limit check
        6. Position concentration check
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            direction: 'LONG' or 'SHORT'
            position_value: Notional position value
            risk_amount: Amount at risk (stop distance * quantity)
            
        Returns:
            RiskCheck with validation result
        """
        limits_hit = []
        
        # Check 1: Max open positions
        if len(self.positions) >= self.max_open_positions:
            # Allow if replacing existing position in same symbol
            if symbol not in self.positions:
                return RiskCheck(
                    passed=False,
                    reason=f"Max open positions reached ({self.max_open_positions})",
                    limits_hit=['max_open_positions']
                )
        
        # Check 2: Asset exposure limit
        current_exposure = self._get_asset_exposure(symbol)
        new_exposure = current_exposure + position_value
        max_exposure = self.account_balance * (self.max_asset_exposure_pct / 100)
        
        if new_exposure > max_exposure:
            return RiskCheck(
                passed=False,
                reason=f"Asset exposure limit exceeded: ${new_exposure:.2f} > ${max_exposure:.2f} "
                       f"({self.max_asset_exposure_pct}% of account)",
                limits_hit=['asset_exposure']
            )
        
        # Check 3: Correlated exposure
        correlated_exposure = self._get_correlated_exposure(symbol)
        new_correlated_exposure = correlated_exposure + position_value
        max_correlated = self.account_balance * (self.max_correlated_exposure_pct / 100)
        
        if new_correlated_exposure > max_correlated:
            limits_hit.append('correlated_exposure')
            return RiskCheck(
                passed=False,
                reason=f"Correlated exposure limit exceeded: ${new_correlated_exposure:.2f} > "
                       f"${max_correlated:.2f} ({self.max_correlated_exposure_pct}% of account)",
                limits_hit=limits_hit
            )
        
        # Check 4: Daily loss limit
        daily_loss = self._get_period_loss(hours=24)
        max_daily_loss = self.account_balance * (self.max_daily_loss_pct / 100)
        
        if daily_loss >= max_daily_loss:
            return RiskCheck(
                passed=False,
                reason=f"Daily loss limit hit: ${daily_loss:.2f} >= ${max_daily_loss:.2f} "
                       f"({self.max_daily_loss_pct}% of account). Trading halted.",
                limits_hit=['daily_loss_limit']
            )
        
        # Check 5: Weekly loss limit
        weekly_loss = self._get_period_loss(hours=168)  # 7 days
        max_weekly_loss = self.account_balance * (self.max_weekly_loss_pct / 100)
        
        if weekly_loss >= max_weekly_loss:
            return RiskCheck(
                passed=False,
                reason=f"Weekly loss limit hit: ${weekly_loss:.2f} >= ${max_weekly_loss:.2f} "
                       f"({self.max_weekly_loss_pct}% of account). Trading halted.",
                limits_hit=['weekly_loss_limit']
            )
        
        # Check 6: Position concentration
        max_position_value = self.account_balance * (self.max_position_concentration_pct / 100)
        
        if position_value > max_position_value:
            return RiskCheck(
                passed=False,
                reason=f"Position too large: ${position_value:.2f} > ${max_position_value:.2f} "
                       f"({self.max_position_concentration_pct}% of account)",
                limits_hit=['position_concentration']
            )
        
        # All checks passed
        return RiskCheck(passed=True, reason="All risk checks passed")
    
    def add_position(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        entry_price: float,
        current_price: Optional[float] = None
    ) -> None:
        """
        Add new position to tracking.
        
        Args:
            symbol: Trading pair
            direction: 'LONG' or 'SHORT'
            quantity: Position size
            entry_price: Entry price
            current_price: Current market price (defaults to entry_price)
        """
        if current_price is None:
            current_price = entry_price
        
        position = Position(
            symbol=symbol,
            direction=direction,
            quantity=quantity,
            entry_price=entry_price,
            current_price=current_price,
            unrealized_pnl=0.0
        )
        
        with self._lock:
            self.positions[symbol] = position
        logger.info(f"Position added: {symbol} {direction} {quantity} @ {entry_price}")
    
    def update_position(self, symbol: str, current_price: float) -> None:
        """
        Update position with current market price.
        
        Args:
            symbol: Trading pair
            current_price: Current market price
            
        Raises:
            KeyError: If position not found
        """
        if symbol not in self.positions:
            raise KeyError(f"Position not found: {symbol}")
        
        with self._lock:
            position = self.positions[symbol]
            position.current_price = current_price
            if position.direction == "LONG":
                position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
            else:  # SHORT
                position.unrealized_pnl = (position.entry_price - current_price) * position.quantity
    
    def close_position(self, symbol: str, exit_price: float) -> Trade:
        """
        Close position and record trade.
        
        Args:
            symbol: Trading pair
            exit_price: Exit price
            
        Returns:
            Trade record
            
        Raises:
            KeyError: If position not found
        """
        if symbol not in self.positions:
            raise KeyError(f"Position not found: {symbol}")
        
        with self._lock:
            position = self.positions[symbol]
        
        # Calculate realized PnL
        if position.direction == "LONG":
            pnl = (exit_price - position.entry_price) * position.quantity
        else:  # SHORT
            pnl = (position.entry_price - exit_price) * position.quantity
        
        # Create trade record
        trade = Trade(
            symbol=symbol,
            direction=position.direction,
            pnl=pnl,
            closed_at=datetime.now(timezone.utc)
        )
        
        with self._lock:
            self.trade_history.append(trade)
            self.account_balance += pnl
            del self.positions[symbol]
        
        logger.info(f"Position closed: {symbol} PnL: ${pnl:.2f}")
        
        return trade
    
    def get_total_exposure(self) -> float:
        """Calculate total portfolio exposure (sum of all position values)."""
        return sum(pos.notional_value for pos in self.positions.values())
    
    def get_unrealized_pnl(self) -> float:
        """Calculate total unrealized PnL across all positions."""
        return sum(pos.unrealized_pnl for pos in self.positions.values())
    
    def get_equity(self) -> float:
        """Calculate current account equity (balance + unrealized PnL)."""
        return self.account_balance + self.get_unrealized_pnl()
    
    def get_drawdown(self) -> float:
        """Calculate current drawdown from peak equity."""
        current_equity = self.get_equity()
        if self.initial_balance == 0:
            return 0.0
        return ((self.initial_balance - current_equity) / self.initial_balance) * 100
    
    def reset_daily_stats(self) -> None:
        """Reset daily statistics (call at start of each trading day)."""
        # In production, this would track daily high water mark
        # For now, we rely on trade history timestamps
        pass
    
    def get_position_count(self) -> int:
        """Get number of open positions."""
        return len(self.positions)
    
    def get_positions_by_direction(self) -> Dict[str, int]:
        """Get position count by direction."""
        counts = {'LONG': 0, 'SHORT': 0}
        for pos in self.positions.values():
            counts[pos.direction] += 1
        return counts
    
    def _get_asset_exposure(self, symbol: str) -> float:
        """
        Calculate current exposure to specific asset.
        
        Args:
            symbol: Trading pair
            
        Returns:
            Total exposure value in quote currency
        """
        if symbol in self.positions:
            return self.positions[symbol].notional_value
        return 0.0
    
    def _get_correlated_exposure(self, symbol: str) -> float:
        """
        Calculate exposure to correlated assets.
        
        Args:
            symbol: Trading pair to check
            
        Returns:
            Total correlated exposure
        """
        # Find correlation group
        correlated_symbols = set()
        for group_symbols in self.correlation_groups.values():
            if symbol in group_symbols:
                correlated_symbols.update(group_symbols)
        
        # If no correlation group found, treat as isolated
        if not correlated_symbols:
            return self._get_asset_exposure(symbol)
        
        # Sum exposure across correlated assets
        total_exposure = 0.0
        for pos_symbol, position in self.positions.items():
            if pos_symbol in correlated_symbols:
                total_exposure += position.notional_value
        
        return total_exposure
    
    def _get_period_loss(self, hours: int) -> float:
        """
        Calculate realized losses over specified period.
        
        Args:
            hours: Lookback period in hours
            
        Returns:
            Total loss amount (positive number)
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        period_pnl = sum(
            trade.pnl
            for trade in self.trade_history
            if trade.closed_at >= cutoff_time
        )
        
        # Return loss as positive number
        return abs(min(0, period_pnl))
    
    def get_risk_summary(self) -> Dict:
        """
        Get comprehensive risk summary.
        
        Returns:
            Dictionary with risk metrics
        """
        return {
            'account_balance': self.account_balance,
            'equity': self.get_equity(),
            'unrealized_pnl': self.get_unrealized_pnl(),
            'drawdown_pct': self.get_drawdown(),
            'open_positions': self.get_position_count(),
            'max_positions': self.max_open_positions,
            'total_exposure': self.get_total_exposure(),
            'exposure_pct': (self.get_total_exposure() / self.account_balance * 100) if self.account_balance > 0 else 0,
            'daily_loss': self._get_period_loss(24),
            'weekly_loss': self._get_period_loss(168),
            'positions_by_direction': self.get_positions_by_direction()
        }
