"""
Paper Trading Executor

Simulates order execution without real exchange interaction.
Provides realistic fill simulation with slippage, partial fills, and market impact.

Features:
- Market and limit order simulation
- Realistic slippage modeling
- Partial fill simulation
- Order state management
- Virtual balance tracking
- Trade history logging
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import random

logger = logging.getLogger(__name__)


class OrderType(Enum):
    """Order type enumeration."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"


class OrderStatus(Enum):
    """Order status enumeration."""

    PENDING = "PENDING"
    OPEN = "OPEN"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderSide(Enum):
    """Order side enumeration."""

    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Order:
    """
    Order representation.

    Attributes:
        order_id: Unique order identifier
        symbol: Trading pair (e.g., 'BTC/USDT')
        side: BUY or SELL
        order_type: Order type (MARKET, LIMIT, etc.)
        quantity: Order quantity in base asset
        price: Order price (None for market orders)
        filled_quantity: Quantity filled so far
        average_fill_price: Average price of fills
        status: Current order status
        stop_price: Stop trigger price (for stop orders)
        created_at: Order creation timestamp
        updated_at: Last update timestamp
    """

    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    stop_price: Optional[float] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def remaining_quantity(self) -> float:
        """Calculate remaining unfilled quantity."""
        return self.quantity - self.filled_quantity

    @property
    def is_filled(self) -> bool:
        """Check if order is completely filled."""
        return self.filled_quantity >= self.quantity - 1e-9  # Account for floating point precision

    @property
    def fill_percentage(self) -> float:
        """Calculate fill percentage."""
        if self.quantity == 0:
            return 0.0
        return (self.filled_quantity / self.quantity) * 100


@dataclass
class Fill:
    """
    Order fill record.

    Attributes:
        order_id: Associated order ID
        quantity: Fill quantity
        price: Fill price
        fee: Trading fee amount
        timestamp: Fill timestamp
    """

    order_id: str
    quantity: float
    price: float
    fee: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PaperExecutor:
    """
    Paper trading executor with realistic simulation.

    Simulates order execution with:
    - Market impact and slippage
    - Partial fills for large orders
    - Virtual balance management
    - Order book simulation
    """

    def __init__(
        self,
        initial_balance: float,
        fee_rate: float = 0.001,  # 0.1% default fee
        slippage_bps: float = 5.0,  # 5 basis points default slippage
        enable_partial_fills: bool = True,
        max_fill_pct: float = 0.3,  # Max 30% of order per tick
    ):
        """
        Initialize paper executor.

        Args:
            initial_balance: Starting balance in quote currency
            fee_rate: Trading fee as decimal (0.001 = 0.1%)
            slippage_bps: Slippage in basis points (1 bp = 0.01%)
            enable_partial_fills: Whether to simulate partial fills
            max_fill_pct: Maximum percentage of order to fill per tick

        Raises:
            ValueError: If parameters are invalid
        """
        if initial_balance <= 0:
            raise ValueError("Initial balance must be positive")
        if fee_rate < 0 or fee_rate > 1:
            raise ValueError("Fee rate must be between 0 and 1")
        if slippage_bps < 0:
            raise ValueError("Slippage must be non-negative")
        if max_fill_pct <= 0 or max_fill_pct > 1:
            raise ValueError("Max fill percentage must be between 0 and 1")

        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.fee_rate = fee_rate
        self.slippage_bps = slippage_bps
        self.enable_partial_fills = enable_partial_fills
        self.max_fill_pct = max_fill_pct

        self.orders: Dict[str, Order] = {}
        self.fills: List[Fill] = []
        self.positions: Dict[str, float] = {}  # symbol -> quantity
        self.order_counter = 0

        logger.info(f"Paper executor initialized with ${initial_balance:.2f}")

    def _generate_order_id(self) -> str:
        """Generate unique order ID."""
        self.order_counter += 1
        return f"PAPER_{self.order_counter:08d}"

    def _calculate_slippage(self, price: float, side: OrderSide) -> float:
        """
        Calculate slippage for order.

        Args:
            price: Base price
            side: Order side (BUY or SELL)

        Returns:
            Price after slippage
        """
        slippage = price * (self.slippage_bps / 10000)

        # Slippage works against the trader
        if side == OrderSide.BUY:
            return price + slippage
        else:
            return price - slippage

    def _calculate_fee(self, quantity: float, price: float) -> float:
        """Calculate trading fee."""
        return quantity * price * self.fee_rate

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> Order:
        """
        Place a new order.

        Args:
            symbol: Trading pair
            side: 'BUY' or 'SELL'
            order_type: 'MARKET', 'LIMIT', 'STOP_LOSS', 'TAKE_PROFIT'
            quantity: Order quantity
            price: Limit price (required for LIMIT orders)
            stop_price: Stop trigger price (required for stop orders)

        Returns:
            Created order

        Raises:
            ValueError: If order parameters are invalid
        """
        # Validate inputs
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        try:
            order_side = OrderSide[side.upper()]
            order_type_enum = OrderType[order_type.upper()]
        except KeyError:
            raise ValueError(f"Invalid order side '{side}' or type '{order_type}'")

        # Validate price requirements
        if order_type_enum == OrderType.LIMIT and price is None:
            raise ValueError("Limit orders require a price")

        if order_type_enum in (OrderType.STOP_LOSS, OrderType.TAKE_PROFIT):
            if stop_price is None:
                raise ValueError("Stop orders require a stop_price")

        # Create order
        order_id = self._generate_order_id()
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=order_side,
            order_type=order_type_enum,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            status=OrderStatus.OPEN,
        )

        self.orders[order_id] = order
        logger.info(f"Order placed: {order_id} {side} {quantity} {symbol} @ {price}")

        return order

    def execute_market_order(self, order_id: str, current_price: float) -> Optional[Fill]:
        """
        Execute a market order immediately.

        Args:
            order_id: Order to execute
            current_price: Current market price

        Returns:
            Fill record if executed, None otherwise

        Raises:
            ValueError: If order doesn't exist or isn't a market order
        """
        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")

        order = self.orders[order_id]

        if order.order_type != OrderType.MARKET:
            raise ValueError(f"Order {order_id} is not a market order")

        if order.status == OrderStatus.FILLED:
            logger.warning(f"Order {order_id} already filled")
            return None

        # Calculate fill quantity (partial or full)
        fill_qty = order.remaining_quantity
        if self.enable_partial_fills and fill_qty > 0:
            # Randomly fill between max_fill_pct and 100%
            fill_pct = random.uniform(self.max_fill_pct, 1.0)
            fill_qty = order.remaining_quantity * fill_pct

        # Apply slippage
        fill_price = self._calculate_slippage(current_price, order.side)

        # Calculate fee
        fee = self._calculate_fee(fill_qty, fill_price)

        # Check if we have enough balance (for BUY orders)
        if order.side == OrderSide.BUY:
            cost = fill_qty * fill_price + fee
            if cost > self.balance:
                order.status = OrderStatus.REJECTED
                order.updated_at = datetime.now(timezone.utc)
                logger.warning(f"Order {order_id} rejected: insufficient balance")
                return None

            # Deduct balance
            self.balance -= cost
        else:  # SELL
            # Check if we have enough position
            current_position = self.positions.get(order.symbol, 0.0)
            if fill_qty > current_position:
                order.status = OrderStatus.REJECTED
                order.updated_at = datetime.now(timezone.utc)
                logger.warning(f"Order {order_id} rejected: insufficient position")
                return None

            # Add to balance (subtract fee)
            self.balance += fill_qty * fill_price - fee

        # Create fill record
        fill = Fill(order_id=order_id, quantity=fill_qty, price=fill_price, fee=fee)
        self.fills.append(fill)

        # Update order
        order.filled_quantity += fill_qty
        order.average_fill_price = (
            order.average_fill_price * (order.filled_quantity - fill_qty) + fill_price * fill_qty
        ) / order.filled_quantity

        if order.is_filled:
            order.status = OrderStatus.FILLED
        else:
            order.status = OrderStatus.PARTIALLY_FILLED

        order.updated_at = datetime.now(timezone.utc)

        # Update position
        if order.side == OrderSide.BUY:
            self.positions[order.symbol] = self.positions.get(order.symbol, 0.0) + fill_qty
        else:
            self.positions[order.symbol] = self.positions.get(order.symbol, 0.0) - fill_qty

        logger.info(
            f"Order {order_id} filled: {fill_qty:.6f} @ ${fill_price:.2f} " f"(fee: ${fee:.2f})"
        )

        return fill

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.

        Args:
            order_id: Order to cancel

        Returns:
            True if cancelled, False otherwise

        Raises:
            ValueError: If order doesn't exist
        """
        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")

        order = self.orders[order_id]

        if order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
            logger.warning(f"Cannot cancel order {order_id} with status {order.status}")
            return False

        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now(timezone.utc)

        logger.info(f"Order {order_id} cancelled")
        return True

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self.orders.get(order_id)

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """
        Get all open orders.

        Args:
            symbol: Filter by symbol (optional)

        Returns:
            List of open orders
        """
        open_statuses = {OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED}
        orders = [order for order in self.orders.values() if order.status in open_statuses]

        if symbol:
            orders = [o for o in orders if o.symbol == symbol]

        return orders

    def get_position(self, symbol: str) -> float:
        """Get current position for symbol."""
        return self.positions.get(symbol, 0.0)

    def get_balance(self) -> float:
        """Get current balance."""
        return self.balance

    def get_equity(self, market_prices: Dict[str, float]) -> float:
        """
        Calculate total equity (balance + position values).

        Args:
            market_prices: Current market prices for each symbol

        Returns:
            Total equity value
        """
        position_value = sum(
            qty * market_prices.get(symbol, 0.0) for symbol, qty in self.positions.items()
        )

        return self.balance + position_value

    def get_pnl(self, market_prices: Dict[str, float]) -> float:
        """
        Calculate profit/loss.

        Args:
            market_prices: Current market prices

        Returns:
            Total PnL
        """
        return self.get_equity(market_prices) - self.initial_balance

    def get_trade_history(self) -> List[Fill]:
        """Get all fills."""
        return self.fills.copy()

    def get_statistics(self) -> Dict:
        """
        Get trading statistics.

        Returns:
            Dictionary with execution statistics
        """
        total_orders = len(self.orders)
        filled_orders = sum(1 for o in self.orders.values() if o.status == OrderStatus.FILLED)
        cancelled_orders = sum(1 for o in self.orders.values() if o.status == OrderStatus.CANCELLED)
        rejected_orders = sum(1 for o in self.orders.values() if o.status == OrderStatus.REJECTED)

        total_fees = sum(fill.fee for fill in self.fills)
        total_volume = sum(fill.quantity * fill.price for fill in self.fills)

        return {
            "total_orders": total_orders,
            "filled_orders": filled_orders,
            "cancelled_orders": cancelled_orders,
            "rejected_orders": rejected_orders,
            "total_fills": len(self.fills),
            "total_fees": total_fees,
            "total_volume": total_volume,
            "current_balance": self.balance,
            "active_positions": len([p for p in self.positions.values() if p != 0]),
        }
