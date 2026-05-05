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
        target_leverage: int = 1,
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
        self.target_leverage = max(1, int(target_leverage))

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
        self._leverage_confirmed: set = set()  # symbols with leverage already set this session
        self._hedge_mode: bool = False  # True if account is in hedge mode (needs positionSide)

        # Switch to one-way position mode at startup.
        # Phemex TE_ERR_INCONSISTENT_POS_MODE fires when the account is in hedge mode
        # but orders don't include positionSide. The bot uses one-way mode exclusively.
        if not dry_run:
            one_way_ok = self._adapter.set_position_mode_one_way()
            if not one_way_ok:
                # Could not switch — account may already have open positions.
                # Flag hedge mode so every order includes positionSide as fallback.
                self._hedge_mode = True
                logger.warning(
                    "Could not confirm one-way position mode — will include positionSide "
                    "in all orders to handle hedge-mode accounts."
                )

        # Fetch initial balance
        self._cached_balance = self._fetch_balance_from_exchange()
        self._initial_balance = self._cached_balance
        logger.info(
            f"LiveExecutor initialized — balance=${self._cached_balance:.2f} "
            f"dry_run={dry_run} hedge_mode={self._hedge_mode}"
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
                msg = f"Position size ${position_usd:.2f} exceeds cap ${self.max_position_size_usd:.2f}"
                logger.warning(f"Order REJECTED: {msg}")
                order.status = OrderStatus.REJECTED
                order.rejection_reason = msg
                return order

            if self._total_exposure_usd() + position_usd > self.max_total_exposure_usd:
                msg = f"Total exposure would exceed ${self.max_total_exposure_usd:.2f}"
                logger.warning(f"Order REJECTED: {msg}")
                order.status = OrderStatus.REJECTED
                order.rejection_reason = msg
                return order

        if self._cached_balance < self.min_balance_usd:
            msg = f"Balance ${self._cached_balance:.2f} below minimum ${self.min_balance_usd:.2f}"
            logger.warning(f"Order REJECTED: {msg}")
            order.status = OrderStatus.REJECTED
            order.rejection_reason = msg
            return order

        if self.dry_run:
            logger.info(
                f"[DRY RUN] Order would send: {order_id} {side} {quantity} "
                f"{symbol} @ {price} leverage={self.target_leverage}x"
            )
            return order

        # Ensure margin mode and leverage are set correctly before the first order
        # per symbol. Phemex persists these settings per symbol on the account,
        # so we only need to set them once per session.
        if symbol not in self._leverage_confirmed:
            self._adapter.set_margin_mode(symbol, mode="isolated")
            try:
                self._adapter.set_leverage(self.target_leverage, symbol)
                self._leverage_confirmed.add(symbol)
            except Exception as e:
                # Phemex refuses set_leverage when an open position already exists.
                # Abort the order rather than silently placing it at the account's
                # current leverage, which may be very different from target.
                logger.error(
                    f"LEVERAGE MISMATCH: Cannot set {self.target_leverage}x for {symbol}: {e}. "
                    f"Order BLOCKED — close any existing {symbol} position first."
                )
                order.status = OrderStatus.REJECTED
                return order

        # Send to exchange
        ccxt_type = order_type_enum.value.lower()
        if order_type_enum in (OrderType.STOP_LOSS, OrderType.TAKE_PROFIT):
            ccxt_type = "market"  # Phemex handles SL/TP as market exits

        ccxt_side = order_side.value.lower()

        # In hedge mode, Phemex requires positionSide on every order.
        # For entry orders: BUY=Long, SELL=Short.
        # For exit/reduce orders: use reduceOnly instead (simpler and mode-agnostic).
        extra_params: dict = {}
        if self._hedge_mode:
            extra_params["positionSide"] = "Long" if ccxt_side == "buy" else "Short"

        def _send_order(params: dict) -> dict:
            return self._adapter.create_order(
                symbol=symbol,
                order_type=ccxt_type,
                side=ccxt_side,
                amount=quantity,
                price=price,
                params=params if params else None,
            )

        try:
            exchange_order = _send_order(extra_params)
            exchange_id = str(exchange_order.get("id", ""))
            self._exchange_order_map[order_id] = exchange_id
            self._reverse_order_map[exchange_id] = order_id
            logger.info(
                f"Order sent: {order_id} → exchange_id={exchange_id} "
                f"{side} {quantity} {symbol} @ {price}"
            )
        except ccxt.InsufficientFunds as e:
            logger.error(f"Insufficient funds for {order_id}")
            order.status = OrderStatus.REJECTED
            order.rejection_reason = f"Insufficient funds: {e}"
        except ccxt.InvalidOrder as e:
            logger.error(f"Invalid order {order_id}: {e}")
            order.status = OrderStatus.REJECTED
            order.rejection_reason = f"Invalid order: {e}"
        except Exception as e:
            err_str = str(e)
            # Phemex 20004 TE_ERR_INCONSISTENT_POS_MODE: the account is in hedge mode
            # despite our startup switch (startup may have silently failed if positions
            # were open at that time). Retry with positionSide and flag hedge mode.
            if "20004" in err_str or "INCONSISTENT_POS_MODE" in err_str:
                logger.warning(
                    f"TE_ERR_INCONSISTENT_POS_MODE on {symbol} — account is in hedge mode. "
                    f"Retrying with positionSide and switching to hedge-mode operation."
                )
                hedge_params = dict(extra_params)
                hedge_params["positionSide"] = "Long" if ccxt_side == "buy" else "Short"
                try:
                    exchange_order = _send_order(hedge_params)
                    exchange_id = str(exchange_order.get("id", ""))
                    self._exchange_order_map[order_id] = exchange_id
                    self._reverse_order_map[exchange_id] = order_id
                    self._hedge_mode = True  # all future orders will include positionSide
                    logger.info(
                        f"Order sent (hedge-mode retry): {order_id} → {exchange_id} "
                        f"{side} {quantity} {symbol} @ {price}"
                    )
                except Exception as retry_e:
                    logger.error(f"Failed to send {order_id} after hedge-mode retry: {retry_e}")
                    order.status = OrderStatus.REJECTED
                    order.rejection_reason = str(retry_e)
            else:
                logger.error(f"Failed to send order {order_id} to exchange: {e}")
                order.status = OrderStatus.REJECTED
                order.rejection_reason = str(e)

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

    def check_fill_via_positions(self, order_id: str) -> Optional[Fill]:
        """
        Secondary fill confirmation using exchange positions.

        Phemex's fetch_order can return stale data (status="open", filled=0) for
        an already-filled limit order. This method cross-checks by fetching the
        actual position for the symbol — if a non-zero position exists, the order
        must have filled. Called only after the primary poll has failed for ≥2 minutes
        to avoid unnecessary round-trips.
        """
        if order_id not in self._orders:
            return None
        order = self._orders[order_id]
        if order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
            return None
        if self.dry_run:
            return None

        try:
            ex_positions = self._adapter.fetch_positions([order.symbol])
            for pos in ex_positions:
                if pos.get("symbol", "") != order.symbol:
                    continue
                ex_qty = float(pos.get("contracts", 0.0) or 0.0)
                if ex_qty < 1e-9:
                    continue
                # Live position confirmed — the order filled on the exchange.
                entry_price = (
                    float(pos.get("entryPrice", 0.0) or 0.0)
                    or float(pos.get("entry_price", 0.0) or 0.0)
                    or order.price
                    or 0.0
                )
                fill_qty = ex_qty - order.filled_quantity
                if fill_qty < 1e-9:
                    # Already accounted for in a prior poll — just sync status.
                    order.status = OrderStatus.FILLED
                    return None
                logger.info(
                    f"Position-fill recovery: {order_id} {order.symbol} "
                    f"qty={ex_qty:.6f} @ {entry_price:.5f} — confirmed via fetch_positions"
                )
                fill = self._record_fill(order, fill_qty, entry_price)
                order.status = OrderStatus.FILLED
                return fill
        except Exception as e:
            logger.debug(f"check_fill_via_positions failed for {order_id}: {e}")
        return None

    def _process_exchange_order(self, order: Order, ex_order: Dict) -> Optional[Fill]:
        """Map a CCXT order response to our internal Order/Fill state."""
        ex_status = ex_order.get("status", "open")
        ex_filled = float(ex_order.get("filled", 0.0) or 0.0)
        ex_avg_price = float(ex_order.get("average", 0.0) or ex_order.get("price", 0.0) or 0.0)

        # Phemex sometimes reports filled=0/null on a closed order (uses cumQty internally,
        # CCXT normalization may not catch it). When the exchange says the order is done but
        # filled qty is still zero, treat the full order quantity as filled.
        if ex_status in ("closed", "filled") and ex_filled < 1e-9:
            ex_filled = order.quantity
            if ex_avg_price <= 0:
                ex_avg_price = order.price or 0.0
            logger.info(
                f"Order {order.order_id} closed on exchange with filled=0 — "
                f"assuming full fill of {ex_filled:.6f} @ {ex_avg_price}"
            )

        # How much was filled since we last checked
        new_qty = ex_filled - order.filled_quantity
        if new_qty < 1e-9:
            # Fully accounted for — keep status in sync
            if ex_status in ("closed", "filled"):
                order.status = OrderStatus.FILLED
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
                    # If the exchange says it was already filled, record the fill so the
                    # caller can open the position. Without this, the fill is lost when
                    # get_open_orders() excludes FILLED orders from future poll cycles.
                    if result.get("status") in ("closed", "filled"):
                        logger.info(f"Order {order_id} was filled on exchange — recording fill")
                        self._process_exchange_order(order, result)
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

    def place_stop_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_price: float,
    ) -> Order:
        """
        Place a reduce-only stop-market order on Phemex.

        This is the exchange-side guardian — it fires even if our server goes
        down. Complement to PositionManager's software polling, not a replacement.
        Side should be the CLOSING side: SELL for a LONG, BUY for a SHORT.
        """
        order_id = self._generate_order_id()
        try:
            order_side = OrderSide(side.upper())
        except ValueError:
            raise ValueError(f"Invalid stop order side '{side}'")

        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=order_side,
            order_type=OrderType.STOP_LOSS,
            quantity=quantity,
            price=stop_price,
            stop_price=stop_price,
            status=OrderStatus.OPEN,
        )
        self._orders[order_id] = order

        if self.dry_run:
            logger.info(
                f"[DRY RUN] Exchange stop would place: {order_id} {side} {quantity} "
                f"{symbol} trigger @ {stop_price}"
            )
            return order

        try:
            # "stop_market" is the CCXT unified type for a stop-triggered market order.
            # price= is the trigger level; reduceOnly ensures it only closes the position.
            stop_params: dict = {"reduceOnly": True}
            if self._hedge_mode:
                # In hedge mode, the stop's positionSide is the position being closed:
                # SELL stop closes a LONG → positionSide=Long
                # BUY stop closes a SHORT → positionSide=Short
                stop_params["positionSide"] = "Long" if side.upper() == "SELL" else "Short"
            exchange_order = self._adapter.create_order(
                symbol=symbol,
                order_type="stop_market",
                side=side.lower(),
                amount=quantity,
                price=stop_price,
                params=stop_params,
            )
            exchange_id = str(exchange_order.get("id", ""))
            self._exchange_order_map[order_id] = exchange_id
            self._reverse_order_map[exchange_id] = order_id
            logger.info(
                f"Exchange stop placed: {order_id} → exchange_id={exchange_id} "
                f"{side} {quantity} {symbol} trigger @ {stop_price}"
            )
        except Exception as e:
            logger.warning(
                f"Exchange stop placement failed for {symbol} @ {stop_price} — "
                f"software monitoring remains active. Error: {e}"
            )
            order.status = OrderStatus.REJECTED

        return order

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

    def reconcile_positions(self) -> set:
        """
        Fetch positions from exchange, sync local state, and return the set of symbols
        with open positions on the exchange.

        Callers use the returned set to detect positions that were closed natively on the
        exchange (e.g., exchange-native stop fired, liquidation) but are still OPEN in
        the position manager — so they can be marked closed in software.
        """
        if self.dry_run:
            return {sym for sym, qty in self._positions.items() if abs(qty) > 1e-9}
        ex_open_symbols: set = set()
        try:
            ex_positions = self._adapter.fetch_positions()
            for pos in ex_positions:
                symbol = pos.get("symbol", "")
                ex_qty = float(pos.get("contracts", 0.0) or 0.0)
                local_qty = self._positions.get(symbol, 0.0)
                if abs(ex_qty - abs(local_qty)) > 1e-6:
                    logger.warning(
                        f"Position discrepancy for {symbol}: "
                        f"local={local_qty:.6f} exchange={ex_qty:.6f} — syncing"
                    )
                    # Sync: adjust local quantity to match exchange reality
                    if ex_qty > 1e-9:
                        # Preserve direction sign from local state
                        self._positions[symbol] = ex_qty if local_qty >= 0 else -ex_qty
                    else:
                        self._positions[symbol] = 0.0
                        self._position_avg_price[symbol] = 0.0
                if ex_qty > 1e-9:
                    ex_open_symbols.add(symbol)
        except Exception as e:
            logger.error(f"Failed to reconcile positions: {e}")
        return ex_open_symbols

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
                # Existing positions are informational — not a blocker.
                # The bot will track and manage them alongside new ones.
            except Exception as e:
                issues.append(f"Position check failed: {e}")

        result["ok"] = len(issues) == 0
        return result
