"""
Position Manager Module

Real-time position monitoring and management for live trading.
Handles stop loss, take profit, breakeven, and trailing stop logic.

This is the critical missing component for production trading - it continuously
monitors open positions and executes risk management actions in real-time.

Features:
- Real-time SL/TP monitoring
- Breakeven stop logic (move SL to entry after first target)
- Trailing stop implementation
- Position state tracking
- Emergency exit handling
- Market data integration for accurate price checks
"""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import asyncio
import logging
from threading import Lock

from backend.shared.models.planner import TradePlan, Target

logger = logging.getLogger(__name__)


class PositionStatus(Enum):
    """Position lifecycle states."""

    PENDING = "PENDING"  # Order placed but not filled
    OPEN = "OPEN"  # Position active
    PARTIAL = "PARTIAL"  # Some targets hit
    CLOSED = "CLOSED"  # All targets hit or stopped out
    STOPPED_OUT = "STOPPED_OUT"  # Hit stop loss
    EMERGENCY_EXIT = "EMERGENCY_EXIT"  # Emergency closure


@dataclass
class PositionState:
    """
    Real-time position state tracking.

    Tracks position lifecycle from entry through partial exits to final closure.

    Attributes:
        position_id: Unique position identifier
        symbol: Trading pair
        direction: LONG or SHORT
        entry_price: Actual fill price
        quantity: Initial position size
        remaining_quantity: Current position size (reduced as targets hit)
        stop_loss: Current stop loss level (can trail)
        targets: List of remaining targets
        targets_hit: List of targets already hit
        status: Current position status
        unrealized_pnl: Current P&L
        realized_pnl: P&L from partial exits
        created_at: Position entry timestamp
        updated_at: Last update timestamp
        breakeven_active: Whether stop has moved to breakeven
        trailing_active: Whether trailing stop is active
        highest_price: Highest price seen (for trailing longs)
        lowest_price: Lowest price seen (for trailing shorts)
    """

    position_id: str
    symbol: str
    direction: str  # "LONG" or "SHORT"
    entry_price: float
    quantity: float
    remaining_quantity: float
    stop_loss: float
    targets: List[Target]
    targets_hit: List[Target] = field(default_factory=list)
    status: PositionStatus = PositionStatus.OPEN
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    breakeven_active: bool = False
    trailing_active: bool = False
    highest_price: Optional[float] = None
    lowest_price: Optional[float] = None

    def __post_init__(self):
        """Initialize price tracking."""
        if self.direction == "LONG":
            self.highest_price = self.entry_price
        else:
            self.lowest_price = self.entry_price

    def update_unrealized_pnl(self, current_price: float):
        """Calculate unrealized P&L based on current price."""
        if self.direction == "LONG":
            pnl_per_unit = current_price - self.entry_price
        else:  # SHORT
            pnl_per_unit = self.entry_price - current_price

        self.unrealized_pnl = pnl_per_unit * self.remaining_quantity
        self.updated_at = datetime.now(timezone.utc)

    def update_price_extremes(self, current_price: float):
        """Track highest/lowest prices for trailing stops."""
        if self.direction == "LONG":
            if self.highest_price is None or current_price > self.highest_price:
                self.highest_price = current_price
        else:  # SHORT
            if self.lowest_price is None or current_price < self.lowest_price:
                self.lowest_price = current_price

    @property
    def total_pnl(self) -> float:
        """Total P&L (realized + unrealized)."""
        return self.realized_pnl + self.unrealized_pnl

    @property
    def pnl_percentage(self) -> float:
        """P&L as percentage of entry value."""
        entry_value = self.entry_price * self.quantity
        if entry_value == 0:
            return 0.0
        return (self.total_pnl / entry_value) * 100


class PositionManager:
    """
    Real-time position management and monitoring.

    This is the critical component that was missing from the system review.
    It continuously monitors positions and executes risk management logic.

    Usage:
        manager = PositionManager(price_fetcher=get_current_price)
        position_id = manager.open_position(trade_plan, entry_price, quantity)

        # In main loop:
        await manager.monitor_all_positions()
    """

    def __init__(
        self,
        price_fetcher: Callable[[str], float],
        order_executor: Optional[Callable] = None,
        check_interval: float = 1.0,
        breakeven_after_target: int = 1,
        trailing_stop_activation: float = 1.5,  # Activate after 1.5R profit
        trailing_stop_distance: float = 0.5,  # Trail 0.5R behind
    ):
        """
        Initialize Position Manager.

        Args:
            price_fetcher: Function to fetch current price for symbol
            order_executor: Function to execute orders (market sell/buy)
            check_interval: How often to check positions (seconds)
            breakeven_after_target: Move to breakeven after Nth target
            trailing_stop_activation: R multiple to activate trailing
            trailing_stop_distance: R multiple to trail behind
        """
        self.price_fetcher = price_fetcher
        self.order_executor = order_executor
        self.check_interval = check_interval
        self.breakeven_after_target = breakeven_after_target
        self.trailing_stop_activation = trailing_stop_activation
        self.trailing_stop_distance = trailing_stop_distance

        self.positions: Dict[str, PositionState] = {}
        self._lock = Lock()
        self._running = False

        logger.info(
            f"PositionManager initialized: check_interval={check_interval}s, "
            f"breakeven_after_target={breakeven_after_target}, "
            f"trailing_activation={trailing_stop_activation}R"
        )

    def open_position(self, trade_plan: TradePlan, entry_price: float, quantity: float) -> str:
        """
        Open new position from trade plan.

        Args:
            trade_plan: Trade plan with stops/targets
            entry_price: Actual entry fill price
            quantity: Position size

        Returns:
            position_id: Unique position identifier
        """
        position_id = f"{trade_plan.symbol}_{datetime.now(timezone.utc).timestamp()}"

        position = PositionState(
            position_id=position_id,
            symbol=trade_plan.symbol,
            direction=trade_plan.direction,
            entry_price=entry_price,
            quantity=quantity,
            remaining_quantity=quantity,
            stop_loss=trade_plan.stop_loss.level,
            targets=trade_plan.targets.copy(),
            status=PositionStatus.OPEN,
        )

        with self._lock:
            self.positions[position_id] = position

        logger.info(
            f"Position opened: {position_id} | {trade_plan.symbol} {trade_plan.direction} "
            f"| Entry: {entry_price} | Qty: {quantity} | SL: {trade_plan.stop_loss.level}"
        )

        return position_id

    def close_position(self, position_id: str, reason: str, current_price: Optional[float] = None):
        """
        Close position completely.

        Args:
            position_id: Position to close
            reason: Reason for closure
            current_price: Price at closure (for P&L calculation)
        """
        with self._lock:
            if position_id not in self.positions:
                logger.warning(f"Position {position_id} not found for closure")
                return

            position = self.positions[position_id]

            # Calculate final P&L if price provided
            if current_price:
                position.update_unrealized_pnl(current_price)
                position.realized_pnl += position.unrealized_pnl
                position.unrealized_pnl = 0.0

            position.remaining_quantity = 0.0
            position.status = PositionStatus.CLOSED
            position.updated_at = datetime.now(timezone.utc)

        logger.info(
            f"Position closed: {position_id} | Reason: {reason} | "
            f"Total P&L: {position.total_pnl:.2f} ({position.pnl_percentage:.2f}%)"
        )

    async def monitor_all_positions(self):
        """
        Monitor all open positions and execute risk management.

        This is the main monitoring loop - should run continuously.
        Checks each position for:
        - Stop loss hit
        - Target hit
        - Breakeven conditions
        - Trailing stop activation
        """
        with self._lock:
            open_positions = [
                p
                for p in self.positions.values()
                if p.status in [PositionStatus.OPEN, PositionStatus.PARTIAL]
            ]

        if not open_positions:
            return

        logger.debug(f"Monitoring {len(open_positions)} positions")

        for position in open_positions:
            try:
                await self._monitor_position(position)
            except Exception as e:
                logger.error(f"Error monitoring position {position.position_id}: {e}")

    async def _monitor_position(self, position: PositionState):
        """
        Monitor single position and execute risk management logic.

        Order of checks:
        1. Stop loss hit (immediate exit)
        2. Target hit (partial exit)
        3. Breakeven logic
        4. Trailing stop update
        """
        # Fetch current price
        try:
            current_price = self.price_fetcher(position.symbol)
        except Exception as e:
            logger.error(f"Failed to fetch price for {position.symbol}: {e}")
            return

        # Update P&L and price extremes
        position.update_unrealized_pnl(current_price)
        position.update_price_extremes(current_price)

        # --- Check Stop Loss ---
        if self._check_stop_hit(position, current_price):
            logger.warning(
                f"STOP HIT: {position.position_id} | {position.symbol} | "
                f"Price: {current_price} | SL: {position.stop_loss} | "
                f"P&L: {position.total_pnl:.2f}"
            )

            if self.order_executor:
                # Execute market close
                await self._execute_exit(position, current_price, "STOP_LOSS")

            with self._lock:
                position.status = PositionStatus.STOPPED_OUT
                position.remaining_quantity = 0.0

            return  # Position closed, no further checks

        # --- Check Targets ---
        target_hit = self._check_targets_hit(position, current_price)
        if target_hit:
            logger.info(
                f"TARGET HIT: {position.position_id} | {position.symbol} | "
                f"Level: {target_hit.level} | Closing {target_hit.percentage}%"
            )

            # Calculate quantity to close
            close_qty = (target_hit.percentage / 100) * position.quantity

            if self.order_executor:
                await self._execute_partial_exit(position, current_price, close_qty)

            with self._lock:
                # Update position state
                position.remaining_quantity -= close_qty
                position.targets.remove(target_hit)
                position.targets_hit.append(target_hit)

                # Update realized P&L
                if position.direction == "LONG":
                    partial_pnl = (current_price - position.entry_price) * close_qty
                else:
                    partial_pnl = (position.entry_price - current_price) * close_qty
                position.realized_pnl += partial_pnl

                # Update status
                if position.remaining_quantity < 1e-9:  # All targets hit
                    position.status = PositionStatus.CLOSED
                else:
                    position.status = PositionStatus.PARTIAL

            # Check if should move to breakeven
            if len(position.targets_hit) >= self.breakeven_after_target:
                self._move_to_breakeven(position)

        # --- Update Trailing Stop ---
        if position.trailing_active:
            self._update_trailing_stop(position)
        else:
            # Check if should activate trailing
            self._check_trailing_activation(position, current_price)

    def _check_stop_hit(self, position: PositionState, current_price: float) -> bool:
        """Check if stop loss was hit."""
        if position.direction == "LONG":
            return current_price <= position.stop_loss
        else:  # SHORT
            return current_price >= position.stop_loss

    def _check_targets_hit(self, position: PositionState, current_price: float) -> Optional[Target]:
        """
        Check if any targets were hit.

        Returns first target hit (closest to entry).
        """
        if not position.targets:
            return None

        for target in position.targets:
            if position.direction == "LONG":
                if current_price >= target.level:
                    return target
            else:  # SHORT
                if current_price <= target.level:
                    return target

        return None

    def _move_to_breakeven(self, position: PositionState):
        """Move stop loss to breakeven (entry price)."""
        if position.breakeven_active:
            return  # Already at breakeven

        old_stop = position.stop_loss
        position.stop_loss = position.entry_price
        position.breakeven_active = True

        logger.info(
            f"BREAKEVEN: {position.position_id} | {position.symbol} | "
            f"Stop moved: {old_stop} -> {position.stop_loss}"
        )

    def _check_trailing_activation(self, position: PositionState, current_price: float):
        """Check if trailing stop should be activated."""
        if position.trailing_active:
            return

        # Calculate profit in R multiples
        risk = abs(position.entry_price - position.stop_loss)
        if risk == 0:
            return

        if position.direction == "LONG":
            profit = current_price - position.entry_price
        else:
            profit = position.entry_price - current_price

        profit_r = profit / risk

        if profit_r >= self.trailing_stop_activation:
            position.trailing_active = True
            logger.info(
                f"TRAILING ACTIVATED: {position.position_id} | {position.symbol} | "
                f"Profit: {profit_r:.2f}R"
            )
            self._update_trailing_stop(position)

    def _update_trailing_stop(self, position: PositionState):
        """Update trailing stop based on price movement."""
        if not position.trailing_active:
            return

        risk = abs(position.entry_price - position.stop_loss)
        trail_distance = self.trailing_stop_distance * risk

        if position.direction == "LONG":
            if position.highest_price is None:
                return
            new_stop = position.highest_price - trail_distance
            # Only trail up, never down
            if new_stop > position.stop_loss:
                old_stop = position.stop_loss
                position.stop_loss = new_stop
                logger.debug(
                    f"TRAIL UPDATE: {position.position_id} | "
                    f"Stop: {old_stop:.2f} -> {new_stop:.2f}"
                )
        else:  # SHORT
            if position.lowest_price is None:
                return
            new_stop = position.lowest_price + trail_distance
            # Only trail down, never up
            if new_stop < position.stop_loss:
                old_stop = position.stop_loss
                position.stop_loss = new_stop
                logger.debug(
                    f"TRAIL UPDATE: {position.position_id} | "
                    f"Stop: {old_stop:.2f} -> {new_stop:.2f}"
                )

    async def _execute_exit(self, position: PositionState, price: float, reason: str):
        """Execute full position exit."""
        if not self.order_executor:
            logger.warning("No order executor configured - simulating exit")
            return

        try:
            # Execute market order to close
            order_side = "SELL" if position.direction == "LONG" else "BUY"
            await self.order_executor(
                symbol=position.symbol,
                side=order_side,
                quantity=position.remaining_quantity,
                order_type="MARKET",
            )
            logger.info(
                f"Exit executed: {position.position_id} | {reason} | "
                f"Qty: {position.remaining_quantity} @ {price}"
            )
        except Exception as e:
            logger.error(f"Failed to execute exit for {position.position_id}: {e}")

    async def _execute_partial_exit(self, position: PositionState, price: float, quantity: float):
        """Execute partial position exit at target."""
        if not self.order_executor:
            logger.warning("No order executor configured - simulating partial exit")
            return

        try:
            order_side = "SELL" if position.direction == "LONG" else "BUY"
            await self.order_executor(
                symbol=position.symbol, side=order_side, quantity=quantity, order_type="MARKET"
            )
            logger.info(
                f"Partial exit executed: {position.position_id} | " f"Qty: {quantity} @ {price}"
            )
        except Exception as e:
            logger.error(f"Failed to execute partial exit for {position.position_id}: {e}")

    def get_position(self, position_id: str) -> Optional[PositionState]:
        """Get position state by ID."""
        with self._lock:
            return self.positions.get(position_id)

    def get_all_positions(self) -> List[PositionState]:
        """Get all positions."""
        with self._lock:
            return list(self.positions.values())

    def get_open_positions(self) -> List[PositionState]:
        """Get only open/partial positions."""
        with self._lock:
            return [
                p
                for p in self.positions.values()
                if p.status in [PositionStatus.OPEN, PositionStatus.PARTIAL]
            ]

    def emergency_close_all(self, reason: str = "EMERGENCY"):
        """
        Emergency close all open positions.

        Use in case of system shutdown, critical error, or risk event.
        """
        logger.critical(f"EMERGENCY CLOSE ALL: {reason}")

        open_positions = self.get_open_positions()

        for position in open_positions:
            try:
                current_price = self.price_fetcher(position.symbol)
                self.close_position(position.position_id, f"EMERGENCY: {reason}", current_price)

                # Mark as emergency exit
                with self._lock:
                    position.status = PositionStatus.EMERGENCY_EXIT
            except Exception as e:
                logger.error(f"Failed to emergency close {position.position_id}: {e}")

    async def start_monitoring(self):
        """
        Start continuous position monitoring loop.

        Run this in background task/thread.
        """
        self._running = True
        logger.info("Position monitoring started")

        while self._running:
            try:
                await self.monitor_all_positions()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)

    def stop_monitoring(self):
        """Stop monitoring loop."""
        self._running = False
        logger.info("Position monitoring stopped")
