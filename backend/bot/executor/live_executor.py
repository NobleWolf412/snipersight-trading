"""
Live Trading Executor

Sends real orders to Phemex via CCXT. Drop-in replacement for PaperExecutor —
all public method signatures are identical so PositionManager and all upstream
risk management work without modification.
"""

from typing import Dict, List, Optional
from datetime import datetime, timezone
import logging
import ccxt

from backend.bot.executor.paper_executor import (
    Order, Fill, OrderType, OrderStatus, OrderSide
)
from backend.data.adapters.phemex import PhemexAdapter

logger = logging.getLogger(__name__)


class LiveExecutor:
    """
    Live trading executor — sends real orders to Phemex via CCXT.

    Implements the identical public interface as PaperExecutor. All safety
    checks (position caps, balance floors, exposure limits) are applied
    before any order reaches the exchange.
    """

    def __init__(
        self,
        adapter: PhemexAdapter,
        fee_rate: float = 0.001,
        max_position_size_usd: float = 100.0,
        max_total_exposure_usd: float = 500.0,
        min_balance_usd: float = 50.0,
        dry_run: bool = False,
    ):
        if not adapter.supports_trading() and not dry_run:
            raise ValueError(
                "PhemexAdapter has no API keys configured. "
                "Set PHEMEX_API_KEY and PHEMEX_API_SECRET env vars."
            )

        self._adapter = adapter
        self.fee_rate = fee_rate
        self.max_position_size_usd = max_position_size_usd
        self.max_total_exposure_usd = max_total_exposure_usd
        self.min_balance_usd = min_balance_usd
        self.dry_run = dry_run

        # Internal state
        self._orders: Dict[str, Order] = {}
        self._exchange_order_map: Dict[str, str] = {}   # internal_id → exchange_id
        self._reverse_order_map: Dict[str, str] = {}    # exchange_id → internal_id
        self._fills: List[Fill] = []
        self._positions: Dict[str, float] = {}
        self._position_avg_price: Dict[str, float] = {}
        self._cached_balance: float = 0.0
        self._initial_balance: float = 0.0
        self._order_counter: int = 0

        # Fetch initial balance
        self._cached_balance = self._fetch_balance_from_exchange()
        self._initial_balance = self._cached_balance
        logger.info(
            f"LiveExecutor initialized — balance=${self._cached_balance:.2f} "
            f"dry_run={dry_run}"
        )

    def _generate_order_id(self) -> str:
        self._order_counter += 1
        return f"LIVE_{self._order_counter:08d}"

    def _fetch_balance_from_exchange(self) -> float:
        if self.dry_run:
            return 0.0
        try:
            balance = self._adapter.fetch_balance()
            usdt_free = balance.get("free", {}).get("USDT", 0.0) or 0.0
            return float(usdt_free)
        except Exception as e:
            logger.error(f"Failed to fetch balance from exchange: {e}")
            return 0.0

    def _total_exposure_usd(self) -> float:
        """Estimate total open exposure in USD based on current positions."""
        total = 0.0
        for symbol, qty in self._positions.items():
            if abs(qty) < 1e-9:
                continue
            avg = self._position_avg_price.get(symbol, 0.0)
            total += abs(qty) * avg
        return total

    # ------------------------------------------------------------------
    # Public interface (identical signatures to PaperExecutor)
    # ------------------------------------------------------------------

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
        Place an order on Phemex (or log it in dry_run mode).

        Runs pre-flight safety checks before sending to the exchange.
        Returns an Order with status=REJECTED if any check fails.
        """
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        try:
            order_side = OrderSide(side.upper())
            order_type_enum = OrderType(order_type.upper())
        except ValueError:
            raise ValueError(f"Invalid order side '{side}' or type '{order_type}'")

        if order_type_enum == OrderType.LIMIT and price is None:
            raise ValueError("Limit orders require a price")

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
        self._orders[order_id] = order

        # Safety checks — reject without touching the exchange
        ref_price = price or self._position_avg_price.get(symbol, 0.0)
        if ref_price > 0:
            position_usd = quantity * ref_price
            if position_usd > self.max_position_size_usd:
                logger.warning(
                    f"Order REJECTED: position size ${position_usd:.2f} exceeds cap "
                    f"${self.max_position_size_usd:.2f}"
                )
                order.status = OrderStatus.REJECTED
                return order

            if self._total_exposure_usd() + position_usd > self.max_total_exposure_usd:
                logger.warning(
                    f"Order REJECTED: total exposure would exceed "
                    f"${self.max_total_exposure_usd:.2f}"
                )
                order.status = OrderStatus.REJECTED
                return order

        if self._cached_balance < self.min_balance_usd:
            logger.warning(
                f"Order REJECTED: balance ${self._cached_balance:.2f} below "
                f"minimum ${self.min_balance_usd:.2f}"
            )
            order.status = OrderStatus.REJECTED
            return order

        if self.dry_run:
            logger.info(
                f"[DRY RUN] Order would send: {order_id} {side} {quantity} "
                f"{symbol} @ {price}"
            )
            return order

        # Send to exchange
        ccxt_type = order_type_enum.value.lower()
        if order_type_enum in (OrderType.STOP_LOSS, OrderType.TAKE_PROFIT):
            ccxt_type = "market"  # Phemex handles SL/TP as market exits

        ccxt_side = order_side.value.lower()

        try:
            exchange_order = self._adapter.create_order(
                symbol=symbol,
                order_type=ccxt_type,
                side=ccxt_side,
                amount=quantity,
                price=price,
            )
            exchange_id = str(exchange_order.get("id", ""))
            self._exchange_order_map[order_id] = exchange_id
            self._reverse_order_map[exchange_id] = order_id
            logger.info(
                f"Order sent: {order_id} → exchange_id={exchange_id} "
                f"{side} {quantity} {symbol} @ {price}"
            )
        except ccxt.InsufficientFunds:
            logger.error(f"Insufficient funds for {order_id}")
            order.status = OrderStatus.REJECTED
        except ccxt.InvalidOrder as e:
            logger.error(f"Invalid order {order_id}: {e}")
            order.status = OrderStatus.REJECTED
        except Exception as e:
            logger.error(f"Failed to send order {order_id} to exchange: {e}")
            order.status = OrderStatus.REJECTED

        return order

    def execute_market_order(self, order_id: str, current_price: float) -> Optional[Fill]:
        """
        Poll the exchange for a market order fill. Returns Fill if filled, None if pending.
        The current_price arg is accepted for interface compatibility but fill price
        comes from the exchange.
        """
        if order_id not in self._orders:
            raise ValueError(f"Order {order_id} not found")

        order = self._orders[order_id]
        if order.status == OrderStatus.FILLED:
            return None
        if order.status == OrderStatus.REJECTED:
            return None

        if self.dry_run:
            # Simulate immediate fill at current_price
            fill = self._record_fill(order, order.quantity, current_price)
            order.status = OrderStatus.FILLED
            return fill

        exchange_id = self._exchange_order_map.get(order_id)
        if not exchange_id:
            logger.warning(f"No exchange ID for order {order_id}")
            return None

        try:
            ex_order = self._adapter.fetch_order(exchange_id, order.symbol)
            return self._process_exchange_order(order, ex_order)
        except Exception as e:
            logger.error(f"Failed to poll market order {order_id}: {e}")
            return None

    def execute_limit_order(self, order_id: str, current_price: float) -> Optional[Fill]:
        """
        Poll the exchange for a limit order fill. Returns Fill if (partially) filled, None otherwise.
        """
        if order_id not in self._orders:
            return None

        order = self._orders[order_id]
        if order.status in (OrderStatus.FILLED, OrderStatus.REJECTED, OrderStatus.CANCELLED):
            return None

        if self.dry_run:
            # Simulate fill if price hit the limit
            if order.price is None:
                return None
            if order.side == OrderSide.BUY and current_price > order.price:
                return None
            if order.side == OrderSide.SELL and current_price < order.price:
                return None
            fill = self._record_fill(order, order.quantity, order.price)
            order.status = OrderStatus.FILLED
            return fill

        exchange_id = self._exchange_order_map.get(order_id)
        if not exchange_id:
            return None

        try:
            ex_order = self._adapter.fetch_order(exchange_id, order.symbol)
            return self._process_exchange_order(order, ex_order)
        except Exception as e:
            logger.error(f"Failed to poll limit order {order_id}: {e}")
            return None

    def _process_exchange_order(self, order: Order, ex_order: Dict) -> Optional[Fill]:
        """Map a CCXT order response to our internal Order/Fill state."""
        ex_status = ex_order.get("status", "open")
        ex_filled = float(ex_order.get("filled", 0.0) or 0.0)
        ex_avg_price = float(ex_order.get("average", 0.0) or ex_order.get("price", 0.0) or 0.0)

        # How much was filled since we last checked
        new_qty = ex_filled - order.filled_quantity
        if new_qty < 1e-9:
            return None

        fill_price = ex_avg_price if ex_avg_price > 0 else (order.price or 0.0)
        fill = self._record_fill(order, new_qty, fill_price)

        if ex_status in ("closed", "filled"):
            order.status = OrderStatus.FILLED
        elif ex_filled > 0:
            order.status = OrderStatus.PARTIALLY_FILLED

        return fill

    def _record_fill(self, order: Order, qty: float, price: float) -> Fill:
        """Record a fill, update order state, positions, and balance."""
        fee = qty * price * self.fee_rate
        self._cached_balance -= fee

        fill = Fill(order_id=order.order_id, quantity=qty, price=price, fee=fee)
        self._fills.append(fill)

        # Update order average fill price
        total_filled = order.filled_quantity + qty
        if order.average_fill_price == 0:
            order.average_fill_price = price
        else:
            order.average_fill_price = (
                order.average_fill_price * order.filled_quantity + price * qty
            ) / total_filled
        order.filled_quantity = total_filled
        order.updated_at = datetime.now(timezone.utc)

        # Update position accounting (same logic as PaperExecutor)
        self._update_position(order.symbol, order.side, qty, price)

        return fill

    def _update_position(self, symbol: str, side: OrderSide, qty: float, price: float) -> None:
        """Mirror of PaperExecutor margin accounting logic."""
        current_pos = self._positions.get(symbol, 0.0)
        current_avg = self._position_avg_price.get(symbol, 0.0)
        is_buy = side == OrderSide.BUY
        trade_qty = qty if is_buy else -qty

        if (current_pos == 0) or (current_pos > 0 and is_buy) or (current_pos < 0 and not is_buy):
            new_pos = current_pos + trade_qty
            total_cost = abs(current_pos) * current_avg + qty * price
            self._position_avg_price[symbol] = total_cost / abs(new_pos)
            self._positions[symbol] = new_pos
        else:
            close_qty = min(qty, abs(current_pos))
            if current_pos > 0 and not is_buy:
                realized_pnl = (price - current_avg) * close_qty
            else:
                realized_pnl = (current_avg - price) * close_qty
            self._cached_balance += realized_pnl
            new_pos = current_pos + trade_qty
            if (current_pos > 0 and new_pos < 0) or (current_pos < 0 and new_pos > 0):
                self._position_avg_price[symbol] = price
            self._positions[symbol] = new_pos
            if abs(self._positions[symbol]) < 1e-9:
                self._positions[symbol] = 0.0
                self._position_avg_price[symbol] = 0.0

    def cancel_order(self, order_id: str) -> bool:
        if order_id not in self._orders:
            raise ValueError(f"Order {order_id} not found")

        order = self._orders[order_id]
        if order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
            logger.warning(f"Cannot cancel order {order_id} with status {order.status}")
            return False

        if not self.dry_run:
            exchange_id = self._exchange_order_map.get(order_id)
            if exchange_id:
                try:
                    result = self._adapter.cancel_order(exchange_id, order.symbol)
                    # If the exchange says it was already filled, update accordingly
                    if result.get("status") in ("closed", "filled"):
                        logger.info(f"Order {order_id} was already filled on exchange")
                        order.status = OrderStatus.FILLED
                        return False
                except Exception as e:
                    logger.error(f"Failed to cancel {order_id} on exchange: {e}")
                    return False

        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now(timezone.utc)
        logger.info(f"Order {order_id} cancelled")
        return True

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        open_statuses = {OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED}
        orders = [o for o in self._orders.values() if o.status in open_statuses]
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders

    def get_position(self, symbol: str) -> float:
        return self._positions.get(symbol, 0.0)

    def get_balance(self) -> float:
        return self._cached_balance

    def get_equity(self, market_prices: Dict[str, float]) -> float:
        unrealized_pnl = 0.0
        for symbol, qty in self._positions.items():
            if abs(qty) < 1e-9:
                continue
            current_price = market_prices.get(symbol, 0.0)
            avg_price = self._position_avg_price.get(symbol, 0.0)
            if qty > 0:
                unrealized_pnl += (current_price - avg_price) * qty
            else:
                unrealized_pnl += (avg_price - current_price) * abs(qty)
        return self._cached_balance + unrealized_pnl

    def get_pnl(self, market_prices: Dict[str, float]) -> float:
        return self.get_equity(market_prices) - self._initial_balance

    def get_trade_history(self) -> List[Fill]:
        return self._fills.copy()

    def get_statistics(self) -> Dict:
        total_orders = len(self._orders)
        filled_orders = sum(1 for o in self._orders.values() if o.status == OrderStatus.FILLED)
        cancelled_orders = sum(1 for o in self._orders.values() if o.status == OrderStatus.CANCELLED)
        rejected_orders = sum(1 for o in self._orders.values() if o.status == OrderStatus.REJECTED)
        total_fees = sum(f.fee for f in self._fills)
        total_volume = sum(f.quantity * f.price for f in self._fills)
        return {
            "total_orders": total_orders,
            "filled_orders": filled_orders,
            "cancelled_orders": cancelled_orders,
            "rejected_orders": rejected_orders,
            "total_fills": len(self._fills),
            "total_fees": total_fees,
            "total_volume": total_volume,
            "current_balance": self._cached_balance,
            "active_positions": len([p for p in self._positions.values() if p != 0]),
        }

    # ------------------------------------------------------------------
    # Live-only methods (not in PaperExecutor)
    # ------------------------------------------------------------------

    def reconcile_balance(self) -> float:
        """Fetch balance from exchange and update local cache."""
        new_balance = self._fetch_balance_from_exchange()
        if abs(new_balance - self._cached_balance) > 1.0:
            logger.warning(
                f"Balance discrepancy: local=${self._cached_balance:.2f} "
                f"exchange=${new_balance:.2f}"
            )
        self._cached_balance = new_balance
        return new_balance

    def reconcile_positions(self) -> Dict[str, float]:
        """Fetch positions from exchange and log discrepancies."""
        if self.dry_run:
            return self._positions.copy()
        try:
            ex_positions = self._adapter.fetch_positions()
            for pos in ex_positions:
                symbol = pos.get("symbol", "")
                ex_qty = float(pos.get("contracts", 0.0) or 0.0)
                local_qty = self._positions.get(symbol, 0.0)
                if abs(ex_qty - abs(local_qty)) > 1e-6:
                    logger.warning(
                        f"Position discrepancy for {symbol}: "
                        f"local={local_qty:.6f} exchange={ex_qty:.6f}"
                    )
        except Exception as e:
            logger.error(f"Failed to reconcile positions: {e}")
        return self._positions.copy()

    def preflight_check(self) -> Dict:
        """Run connectivity + balance + position check before session start."""
        issues = []
        result: Dict = {"ok": False, "balance": 0.0, "open_positions": [], "issues": issues}

        if not self._adapter.supports_trading() and not self.dry_run:
            issues.append("No API keys configured")
            return result

        try:
            balance = self.reconcile_balance()
            result["balance"] = balance
            if balance < self.min_balance_usd:
                issues.append(
                    f"Balance ${balance:.2f} is below minimum ${self.min_balance_usd:.2f}"
                )
        except Exception as e:
            issues.append(f"Balance check failed: {e}")

        if not self.dry_run:
            try:
                positions = self._adapter.fetch_positions()
                open_pos = [
                    {"symbol": p.get("symbol"), "size": p.get("contracts")}
                    for p in positions
                    if float(p.get("contracts", 0) or 0) != 0
                ]
                result["open_positions"] = open_pos
                if open_pos:
                    issues.append(
                        f"Exchange has {len(open_pos)} existing open position(s) — "
                        "review before starting"
                    )
            except Exception as e:
                issues.append(f"Position check failed: {e}")

        result["ok"] = len(issues) == 0
        return result
