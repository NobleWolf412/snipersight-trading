"""
Test suite for Paper Trading Executor.

Tests simulated order execution and balance management.
"""

import pytest
from backend.bot.executor.paper_executor import (
    PaperExecutor,
    Order,
    OrderType,
    OrderStatus,
    OrderSide,
    Fill
)


def test_paper_executor_initialization():
    """Test PaperExecutor initialization."""
    executor = PaperExecutor(initial_balance=10000, fee_rate=0.001)
    
    assert executor.balance == 10000
    assert executor.initial_balance == 10000
    assert executor.fee_rate == 0.001
    assert len(executor.orders) == 0
    assert len(executor.fills) == 0
    
    # Invalid balance
    with pytest.raises(ValueError, match="balance must be positive"):
        PaperExecutor(initial_balance=0)
    
    # Invalid fee rate
    with pytest.raises(ValueError, match="Fee rate must be"):
        PaperExecutor(initial_balance=10000, fee_rate=1.5)
    
    # Invalid slippage
    with pytest.raises(ValueError, match="Slippage must be"):
        PaperExecutor(initial_balance=10000, slippage_bps=-1)


def test_place_market_order():
    """Test placing market orders."""
    executor = PaperExecutor(initial_balance=10000)
    
    order = executor.place_order(
        symbol="BTC/USDT",
        side="BUY",
        order_type="MARKET",
        quantity=0.1
    )
    
    assert order.symbol == "BTC/USDT"
    assert order.side == OrderSide.BUY
    assert order.order_type == OrderType.MARKET
    assert order.quantity == 0.1
    assert order.status == OrderStatus.OPEN
    assert order.order_id in executor.orders


def test_place_limit_order():
    """Test placing limit orders."""
    executor = PaperExecutor(initial_balance=10000)
    
    order = executor.place_order(
        symbol="BTC/USDT",
        side="BUY",
        order_type="LIMIT",
        quantity=0.1,
        price=50000
    )
    
    assert order.order_type == OrderType.LIMIT
    assert order.price == 50000
    
    # Limit order without price should fail
    with pytest.raises(ValueError, match="Limit orders require a price"):
        executor.place_order(
            symbol="BTC/USDT",
            side="BUY",
            order_type="LIMIT",
            quantity=0.1
        )


def test_place_order_validation():
    """Test order validation."""
    executor = PaperExecutor(initial_balance=10000)
    
    # Invalid quantity
    with pytest.raises(ValueError, match="Quantity must be positive"):
        executor.place_order(
            symbol="BTC/USDT",
            side="BUY",
            order_type="MARKET",
            quantity=0
        )
    
    # Invalid side
    with pytest.raises(ValueError, match="Invalid order side"):
        executor.place_order(
            symbol="BTC/USDT",
            side="INVALID",
            order_type="MARKET",
            quantity=0.1
        )
    
    # Invalid order type
    with pytest.raises(ValueError, match="Invalid order side"):
        executor.place_order(
            symbol="BTC/USDT",
            side="BUY",
            order_type="INVALID_TYPE",
            quantity=0.1
        )


def test_execute_market_buy_order():
    """Test executing market buy order."""
    executor = PaperExecutor(
        initial_balance=10000,
        fee_rate=0.001,
        slippage_bps=5,
        enable_partial_fills=False
    )
    
    # Place order
    order = executor.place_order(
        symbol="BTC/USDT",
        side="BUY",
        order_type="MARKET",
        quantity=0.1
    )
    
    # Execute at $50,000
    fill = executor.execute_market_order(order.order_id, 50000)
    
    assert fill is not None
    assert fill.quantity == 0.1
    assert fill.price > 50000  # Slippage should increase buy price
    
    # Check order status
    assert order.status == OrderStatus.FILLED
    assert order.filled_quantity == 0.1
    
    # Check balance deducted
    cost = fill.quantity * fill.price + fill.fee
    assert executor.balance == pytest.approx(10000 - cost, rel=1e-6)
    
    # Check position created
    assert executor.get_position("BTC/USDT") == 0.1


def test_execute_market_sell_order():
    """Test executing market sell order."""
    executor = PaperExecutor(
        initial_balance=10000,
        fee_rate=0.001,
        slippage_bps=5,
        enable_partial_fills=False
    )
    
    # First buy to create position
    buy_order = executor.place_order(
        symbol="BTC/USDT",
        side="BUY",
        order_type="MARKET",
        quantity=0.1
    )
    executor.execute_market_order(buy_order.order_id, 50000)
    
    initial_balance = executor.balance
    
    # Now sell
    sell_order = executor.place_order(
        symbol="BTC/USDT",
        side="SELL",
        order_type="MARKET",
        quantity=0.1
    )
    
    fill = executor.execute_market_order(sell_order.order_id, 51000)
    
    assert fill is not None
    assert fill.price < 51000  # Slippage should decrease sell price
    
    # Check position closed
    assert executor.get_position("BTC/USDT") == pytest.approx(0, abs=1e-9)
    
    # Check balance increased
    revenue = fill.quantity * fill.price - fill.fee
    assert executor.balance == pytest.approx(initial_balance + revenue, rel=1e-6)


def test_insufficient_balance_rejection():
    """Test order rejection due to insufficient balance."""
    executor = PaperExecutor(initial_balance=1000, enable_partial_fills=False)
    
    # Try to buy 1 BTC at $50k (need $50k but only have $1k)
    order = executor.place_order(
        symbol="BTC/USDT",
        side="BUY",
        order_type="MARKET",
        quantity=1.0
    )
    
    fill = executor.execute_market_order(order.order_id, 50000)
    
    assert fill is None
    assert order.status == OrderStatus.REJECTED


def test_insufficient_position_rejection():
    """Test order rejection due to insufficient position."""
    executor = PaperExecutor(initial_balance=10000, enable_partial_fills=False)
    
    # Try to sell without position
    order = executor.place_order(
        symbol="BTC/USDT",
        side="SELL",
        order_type="MARKET",
        quantity=0.1
    )
    
    fill = executor.execute_market_order(order.order_id, 50000)
    
    assert fill is None
    assert order.status == OrderStatus.REJECTED


def test_partial_fills():
    """Test partial fill simulation."""
    executor = PaperExecutor(
        initial_balance=10000,
        enable_partial_fills=True,
        max_fill_pct=0.5  # Max 50% per fill
    )
    
    order = executor.place_order(
        symbol="BTC/USDT",
        side="BUY",
        order_type="MARKET",
        quantity=0.1
    )
    
    # Execute first fill
    fill1 = executor.execute_market_order(order.order_id, 50000)
    
    # Should be partial fill
    assert fill1.quantity <= 0.1
    assert order.status == OrderStatus.PARTIALLY_FILLED
    assert order.remaining_quantity > 0
    
    # Execute remaining fills until complete
    max_iterations = 10
    fills = 0
    for _ in range(max_iterations):
        if order.is_filled:
            break
        fill = executor.execute_market_order(order.order_id, 50000)
        if fill:
            fills += 1
    
    # Check order eventually filled (within floating point precision)
    assert order.filled_quantity >= 0.1 - 1e-6
    assert fills >= 1  # At least one additional fill occurred


def test_cancel_order():
    """Test order cancellation."""
    executor = PaperExecutor(initial_balance=10000)
    
    order = executor.place_order(
        symbol="BTC/USDT",
        side="BUY",
        order_type="MARKET",
        quantity=0.1
    )
    
    # Cancel order
    result = executor.cancel_order(order.order_id)
    
    assert result is True
    assert order.status == OrderStatus.CANCELLED
    
    # Try to cancel again
    result = executor.cancel_order(order.order_id)
    assert result is False


def test_cancel_filled_order():
    """Test that filled orders cannot be cancelled."""
    executor = PaperExecutor(initial_balance=10000, enable_partial_fills=False)
    
    order = executor.place_order(
        symbol="BTC/USDT",
        side="BUY",
        order_type="MARKET",
        quantity=0.1
    )
    
    executor.execute_market_order(order.order_id, 50000)
    
    # Try to cancel filled order
    result = executor.cancel_order(order.order_id)
    assert result is False


def test_get_open_orders():
    """Test getting open orders."""
    executor = PaperExecutor(initial_balance=10000)
    
    # Place multiple orders
    order1 = executor.place_order("BTC/USDT", "BUY", "MARKET", 0.1)
    order2 = executor.place_order("ETH/USDT", "BUY", "MARKET", 1.0)
    order3 = executor.place_order("BTC/USDT", "BUY", "MARKET", 0.05)
    
    # Get all open orders
    open_orders = executor.get_open_orders()
    assert len(open_orders) == 3
    
    # Get open orders for BTC/USDT
    btc_orders = executor.get_open_orders(symbol="BTC/USDT")
    assert len(btc_orders) == 2
    
    # Fill one order (disable partial fills to ensure complete fill)
    executor.enable_partial_fills = False
    executor.execute_market_order(order1.order_id, 50000)
    
    # Should now have 2 open orders
    open_orders = executor.get_open_orders()
    assert len(open_orders) == 2


def test_fee_calculation():
    """Test trading fee calculation."""
    executor = PaperExecutor(
        initial_balance=10000,
        fee_rate=0.001,  # 0.1%
        enable_partial_fills=False
    )
    
    order = executor.place_order(
        symbol="BTC/USDT",
        side="BUY",
        order_type="MARKET",
        quantity=0.1
    )
    
    fill = executor.execute_market_order(order.order_id, 50000)
    
    # Fee should be ~0.1% of notional
    expected_fee = fill.quantity * fill.price * 0.001
    assert fill.fee == pytest.approx(expected_fee, rel=1e-6)


def test_slippage_calculation():
    """Test slippage application."""
    executor = PaperExecutor(
        initial_balance=10000,
        slippage_bps=10,  # 10 basis points = 0.1%
        enable_partial_fills=False
    )
    
    # Buy order - slippage should increase price
    buy_order = executor.place_order("BTC/USDT", "BUY", "MARKET", 0.1)
    buy_fill = executor.execute_market_order(buy_order.order_id, 50000)
    
    expected_buy_price = 50000 * (1 + 0.001)  # 0.1% slippage
    assert buy_fill.price == pytest.approx(expected_buy_price, rel=1e-6)
    
    # Sell order - slippage should decrease price
    sell_order = executor.place_order("BTC/USDT", "SELL", "MARKET", 0.1)
    sell_fill = executor.execute_market_order(sell_order.order_id, 51000)
    
    expected_sell_price = 51000 * (1 - 0.001)  # 0.1% slippage
    assert sell_fill.price == pytest.approx(expected_sell_price, rel=1e-6)


def test_get_equity():
    """Test equity calculation."""
    executor = PaperExecutor(initial_balance=10000, enable_partial_fills=False)
    
    # Buy BTC
    order = executor.place_order("BTC/USDT", "BUY", "MARKET", 0.1)
    executor.execute_market_order(order.order_id, 50000)
    
    # Calculate equity
    market_prices = {"BTC/USDT": 51000}
    equity = executor.get_equity(market_prices)
    
    # Equity = balance + position value
    position_value = 0.1 * 51000
    expected_equity = executor.balance + position_value
    
    assert equity == pytest.approx(expected_equity, rel=1e-6)


def test_get_pnl():
    """Test PnL calculation."""
    executor = PaperExecutor(initial_balance=10000, enable_partial_fills=False)
    
    # Buy at 50k
    buy_order = executor.place_order("BTC/USDT", "BUY", "MARKET", 0.1)
    executor.execute_market_order(buy_order.order_id, 50000)
    
    # Calculate PnL at 51k (profit)
    market_prices = {"BTC/USDT": 51000}
    pnl = executor.get_pnl(market_prices)
    
    assert pnl > 0  # Should have profit
    
    # Calculate PnL at 49k (loss)
    market_prices = {"BTC/USDT": 49000}
    pnl = executor.get_pnl(market_prices)
    
    assert pnl < 0  # Should have loss


def test_get_statistics():
    """Test trading statistics."""
    executor = PaperExecutor(initial_balance=10000, enable_partial_fills=False)
    
    # Place and execute orders
    order1 = executor.place_order("BTC/USDT", "BUY", "MARKET", 0.1)
    executor.execute_market_order(order1.order_id, 50000)
    
    order2 = executor.place_order("ETH/USDT", "BUY", "MARKET", 1.0)
    executor.cancel_order(order2.order_id)
    
    stats = executor.get_statistics()
    
    assert stats['total_orders'] == 2
    assert stats['filled_orders'] == 1
    assert stats['cancelled_orders'] == 1
    assert stats['total_fills'] == 1
    assert stats['total_fees'] > 0
    assert stats['total_volume'] > 0
    assert stats['active_positions'] == 1


def test_order_properties():
    """Test Order dataclass properties."""
    executor = PaperExecutor(initial_balance=100000, enable_partial_fills=False)
    
    order = executor.place_order("BTC/USDT", "BUY", "MARKET", 1.0)
    
    # Initially unfilled
    assert order.remaining_quantity == 1.0
    assert order.is_filled is False
    assert order.fill_percentage == 0
    
    # Execute
    executor.execute_market_order(order.order_id, 50000)
    
    # Now filled
    assert order.remaining_quantity == 0
    assert order.is_filled is True
    assert order.fill_percentage == 100


def test_average_fill_price():
    """Test average fill price calculation with partial fills."""
    executor = PaperExecutor(
        initial_balance=100000,
        enable_partial_fills=True,
        max_fill_pct=0.5
    )
    
    order = executor.place_order("BTC/USDT", "BUY", "MARKET", 1.0)
    
    # Fill at different prices
    fill1 = executor.execute_market_order(order.order_id, 50000)
    fill2 = executor.execute_market_order(order.order_id, 51000)
    
    # Average should be weighted by quantities
    expected_avg = (
        (fill1.quantity * fill1.price + fill2.quantity * fill2.price) /
        (fill1.quantity + fill2.quantity)
    )
    
    assert order.average_fill_price == pytest.approx(expected_avg, rel=1e-6)


def test_multiple_positions():
    """Test managing multiple positions."""
    executor = PaperExecutor(initial_balance=100000, enable_partial_fills=False)
    
    # Buy BTC
    btc_order = executor.place_order("BTC/USDT", "BUY", "MARKET", 0.5)
    executor.execute_market_order(btc_order.order_id, 50000)
    
    # Buy ETH
    eth_order = executor.place_order("ETH/USDT", "BUY", "MARKET", 10)
    executor.execute_market_order(eth_order.order_id, 3000)
    
    assert executor.get_position("BTC/USDT") == 0.5
    assert executor.get_position("ETH/USDT") == 10
    
    stats = executor.get_statistics()
    assert stats['active_positions'] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
