"""
Live Trading Executor

Sends real orders to Phemex via CCXT. Drop-in replacement for PaperExecutor —
all public method signatures are identical so PositionManager and all upstream
risk management work without modification.
"""

from typing import Dict, List, Optional
from datetime import datetime, timezone
import logging
import math
import time
import uuid
from threading import RLock
import ccxt

from backend.bot.executor.paper_executor import (
    Order, Fill, OrderType, OrderStatus, OrderSide
)
from backend.data.adapters.phemex import PhemexAdapter
from backend.bot.executor.execution_journal import (
    ExecutionJournal, JournalError, credential_binding, default_store,
)

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
        journal: Optional[ExecutionJournal] = None,
        owner: str = "live",
        generation: Optional[str] = None,
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
        self._journal = None
        self._journal_error = None
        self._journaled_ids = set()
        self._restored_ids = set()
        self._recovery_only = False
        self._inflight_mutations = 0
        self._execution_owner = owner
        self._execution_generation = generation or uuid.uuid4().hex

        # Serialize admission and fill accounting so reservations move atomically.
        self._state_lock = RLock()
        self._entry_admission_enabled = True
        self._execution_revision = 0
        self._reduce_only_order_ids: set = set()
        self._unacknowledged_orders: Dict[str, str] = {}
        self._cancel_requested_orders: set = set()
        self._last_order_recovery_at = 0.0
        self._order_id_prefix = uuid.uuid4().hex[:16]

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

        # Balance-fetch failures used to silently return 0.0, which made the risk
        # manager believe the account was empty. Track the failure state so callers
        # (and /healthz) can distinguish "balance is zero" from "we don't know".
        self.balance_known: bool = False
        self.last_balance_error: Optional[str] = None
        self.last_balance_observed_at: Optional[float] = None
        self.last_equity_error: Optional[str] = None

        # Fill-source counters for /api/integrations/phemex/healthz. Retain the
        # legacy position-check key at zero for compatibility; positions cannot
        # attribute execution to an individual order.
        self.metrics: Dict[str, int] = {
            "fills_recorded_via_ws": 0,
            "fills_recorded_via_rest": 0,
            "fills_recovered_via_position_check": 0,
            "balance_fetch_failures": 0,
        }

        # Acquire ownership and restore identities before any account mutation.
        # Position mode is initialized only after complete flat reconciliation.
        if not dry_run:
            self._journal = journal or ExecutionJournal(
                default_store(adapter.testnet), credential_binding(adapter.testnet, adapter.exchange.apiKey))
            try:
                self._restore_execution()
            except BaseException:
                self._journal.close()
                raise
            self._entry_admission_enabled = False

        # Fetch initial balance
        self._cached_balance = self._fetch_balance_from_exchange()
        self._initial_balance = self._cached_balance
        logger.info(
            f"LiveExecutor initialized — balance=${self._cached_balance:.2f} "
            f"dry_run={dry_run} hedge_mode={self._hedge_mode}"
        )

    def _generate_order_id(self) -> str:
        with self._state_lock:
            self._order_counter += 1
            return f"LIVE_{self._order_id_prefix}_{self._order_counter:08d}"

    def _restore_execution(self):
        self._recovery_only = not self._journal.was_clean
        for intent, state in self._journal.records():
            oid = intent["order_id"]
            order = Order(oid, intent["symbol"], OrderSide(intent["side"]),
                          OrderType(intent["order_type"]), intent["quantity"],
                          price=intent["price"], stop_price=intent["stop_price"],
                          status=OrderStatus(state["status"]), filled_quantity=state["filled_quantity"],
                          average_fill_price=state["average_fill_price"],
                          rejection_reason=state["rejection_reason"],
                          created_at=datetime.fromisoformat(state["created_at"]),
                          updated_at=datetime.fromisoformat(state["updated_at"]))
            self._orders[oid] = order
            self._journaled_ids.add(oid)
            self._restored_ids.add(oid)
            if intent["purpose"] == "exit":
                self._reduce_only_order_ids.add(oid)
            if state["exchange_id"]:
                self._exchange_order_map[oid] = state["exchange_id"]
                self._reverse_order_map[state["exchange_id"]] = oid
            if state["cancel_requested"]:
                self._cancel_requested_orders.add(oid)
            if order.status in (OrderStatus.OPEN, OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED):
                self._unacknowledged_orders[oid] = state["unknown_reason"] or "Restored request requires exchange observation"
                self._recovery_only = True

    def _durable_state(self, order):
        return {"status": order.status.value, "filled_quantity": order.filled_quantity,
                "average_fill_price": order.average_fill_price,
                "exchange_id": self._exchange_order_map.get(order.order_id),
                "cancel_requested": order.order_id in self._cancel_requested_orders,
                "unknown_reason": self._unacknowledged_orders.get(order.order_id),
                "rejection_reason": order.rejection_reason,
                "created_at": order.created_at.isoformat(), "updated_at": order.updated_at.isoformat()}

    def _storage_failure(self, exc):
        self._journal_error = str(exc)
        self._entry_admission_enabled = False
        self._recovery_only = True
        logger.error("EXECUTION_STORAGE_BLOCKED: %s", exc)

    def _require_storage(self, new_request=False):
        if self.dry_run:
            return
        journal = getattr(self, "_journal", None)
        if journal is None:
            raise JournalError("Real execution requires a durable journal")
        journal.assert_writable()
        if getattr(self, "_journal_error", None):
            raise JournalError(self._journal_error)
        if new_request and getattr(self, "_recovery_only", False):
            raise JournalError("Restart recovery cannot submit new orders or resume strategy positions")

    def _persist_order(self, order, source="local", kind="observation"):
        if self.dry_run or order.order_id not in getattr(self, "_journaled_ids", set()):
            return
        try:
            self._require_storage()
            self._journal.observe(order.order_id, self._durable_state(order), source, kind)
        except Exception as exc:
            self._storage_failure(exc)
            raise JournalError(str(exc)) from exc

    def _send_journaled_order(self, order, **wire):
        with self._state_lock:
            try:
                self._require_storage(new_request=True)
                purpose = ("exit" if order.order_id in self._reduce_only_order_ids else
                           "entry" if order.order_type in (OrderType.LIMIT, OrderType.MARKET) else "protection")
                intent = {"order_id": order.order_id, "symbol": order.symbol, "side": order.side.value,
                          "order_type": order.order_type.value, "quantity": order.quantity,
                          "price": order.price, "stop_price": order.stop_price, "purpose": purpose,
                          "reduce_only": purpose != "entry", "owner": self._execution_owner,
                          "generation": self._execution_generation, "wire": wire}
                self._journal.submit_intent(intent, self._durable_state(order))
                self._journaled_ids.add(order.order_id)
                self._inflight_mutations = getattr(self, "_inflight_mutations", 0) + 1
            except Exception as exc:
                self._storage_failure(exc)
                raise JournalError(str(exc)) from exc
        try:
            return self._adapter.create_order(**wire)
        finally:
            with self._state_lock:
                self._inflight_mutations -= 1

    def initialize_trading(self):
        """Caller must first verify a complete flat account; no writes in preflight."""
        if not self.dry_run:
            self._require_storage(new_request=True)
            self._hedge_mode = not self._adapter.set_position_mode_one_way()

    def verify_flat_account(self):
        """Read a complete account snapshot for the shared paper-testnet owner."""
        revision = self.recovery_snapshot()["revision"]
        snapshot = self._adapter.fetch_account_snapshot()
        if (not isinstance(snapshot, dict) or snapshot.get("complete") is not True
                or snapshot.get("scope") != "phemex:swap:USDT"
                or not isinstance(snapshot.get("orders"), list)
                or not isinstance(snapshot.get("positions"), list)):
            raise JournalError("Complete USDT account snapshot unavailable")
        if snapshot["orders"]:
            raise JournalError("Existing exchange orders require recovery")
        for row in snapshot["positions"]:
            if not isinstance(row, dict) or not isinstance(row.get("symbol"), str) or not row["symbol"]:
                raise JournalError("Invalid account position")
            qty = row.get("contracts")
            if type(qty) not in (int, float) or not math.isfinite(qty) or qty != 0:
                raise JournalError("Account exposure unknown or present; recovery required")
        with self._state_lock:
            if revision != self.recovery_snapshot()["revision"]:
                raise JournalError("Execution changed during account observation")
            self._flat_snapshot_revision = revision
        return datetime.now(timezone.utc).isoformat()

    def checkpoint_flat(self, observed_at, expected_revision=None):
        with self._state_lock:
            if not self.dry_run:
                self._require_storage()
                if expected_revision is None:
                    expected_revision = getattr(self, "_flat_snapshot_revision", None)
                snap = self.recovery_snapshot()
                if (expected_revision != snap["revision"] or snap["requests"]
                        or snap["inflight_mutations"]):
                    raise JournalError("Execution changed or remains unresolved after flat account observation")
                try:
                    self._journal.mark_flat(observed_at)
                except Exception as exc:
                    self._storage_failure(exc)
                    raise

    def close(self):
        with self._state_lock:
            self.set_entry_admission(False)
            if getattr(self, "_inflight_mutations", 0):
                raise JournalError("Cannot release execution ownership during a transport call")
            if getattr(self, "_journal", None):
                self._journal.close()

    def set_entry_admission(self, enabled: bool) -> None:
        """Freeze new entry risk; already admitted requests still need recovery."""
        with self._state_lock:
            self._entry_admission_enabled = bool(enabled) and not (
                getattr(self, "_recovery_only", False) or getattr(self, "_journal_error", None))

    def recovery_snapshot(self) -> Dict:
        with self._state_lock:
            ids = {o.order_id for o in self.get_open_orders()}
            ids.update(self._unacknowledged_orders)
            ids.update(self._cancel_requested_orders)
            return {
                "revision": getattr(self, "_execution_revision", 0),
                "recovery_only": getattr(self, "_recovery_only", False),
                "storage_error": getattr(self, "_journal_error", None),
                "inflight_mutations": getattr(self, "_inflight_mutations", 0),
                "entry_admission_enabled": getattr(self, "_entry_admission_enabled", True),
                "requests": [{
                    "order_id": oid, "exchange_id": self._exchange_order_map.get(oid),
                    "symbol": self._orders[oid].symbol, "status": self._orders[oid].status.value,
                    "quantity": self._orders[oid].quantity,
                    "filled_quantity": self._orders[oid].filled_quantity,
                    "purpose": ("exit" if oid in self._reduce_only_order_ids else
                                "entry" if self._orders[oid].order_type in (OrderType.LIMIT, OrderType.MARKET)
                                else "protection"),
                    "reason": self._unacknowledged_orders.get(oid, "cancellation pending" if oid in self._cancel_requested_orders else "working order"),
                } for oid in sorted(ids)],
            }

    def _submission_unknown(self, order: Order, reason: str, log_level: int = logging.ERROR) -> None:
        """Retain exposure until an identified exchange observation resolves it."""
        with self._state_lock:
            self._execution_revision = getattr(self, "_execution_revision", 0) + 1
            if order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
                return
            self._unacknowledged_orders[order.order_id] = reason
            order.status = OrderStatus.PARTIALLY_FILLED if order.filled_quantity > 0 else OrderStatus.PENDING
            self._persist_order(order, kind="outcome_unknown")
        logger.log(log_level, "ORDER_OUTCOME_UNKNOWN %s %s: %s", order.order_id, order.symbol, reason)

    def _accept_submission(self, order: Order, response: Dict, require_client_id: bool = False) -> Optional[Fill]:
        if not isinstance(response, dict):
            raise ValueError("Order acknowledgment is not an object")
        exchange_id = response.get("id")
        client_id = response.get("clientOrderId")
        if not isinstance(exchange_id, str) or not exchange_id.strip():
            raise ValueError("Order acknowledgment has no exchange ID")
        if (require_client_id and client_id != order.order_id) or (client_id and client_id != order.order_id):
            raise ValueError("Order acknowledgment has a different client ID")
        with self._state_lock:
            existing_id = self._exchange_order_map.get(order.order_id)
            if existing_id and existing_id != exchange_id:
                raise ValueError("Order acknowledgment changed the exchange identity")
            existing_owner = self._reverse_order_map.get(exchange_id)
            if existing_owner and existing_owner != order.order_id:
                raise ValueError("Exchange identity already belongs to another request")
            self._exchange_order_map[order.order_id] = exchange_id
            self._reverse_order_map[exchange_id] = order.order_id
            # A create response with an ID establishes acceptance, not a fill.
            if response.get("status") is None:
                if require_client_id:
                    raise ValueError("Recovery response has no order status")
                response = {**response, "status": "open"}
            return self._process_exchange_order(order, response)

    def refresh_order(self, order_id: str) -> Optional[Fill]:
        """Recover by client ID when the submission response did not provide an ID."""
        order = self._orders.get(order_id)
        if order is None or self.dry_run or order.status in (
                OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
            return None
        try:
            exchange_id = self._exchange_order_map.get(order_id)
            if not exchange_id:
                response = self._adapter.fetch_order_by_client_id(order_id, order.symbol)
                return self._accept_submission(order, response, require_client_id=True)
            response = self._adapter.fetch_order(exchange_id, order.symbol)
            if not isinstance(response, dict) or response.get("id", exchange_id) != exchange_id:
                raise ValueError("Order lookup returned a different identity")
            return self._process_exchange_order(order, response)
        except Exception as exc:
            # OrderNotFound is not proof of rejection: history can lag acceptance.
            self._submission_unknown(order, str(exc))
            return None

    def _recover_uncertain_protection(self, symbol: str, side: str, order_type: OrderType) -> Optional[Order]:
        with self._state_lock:
            pending = next((self._orders[oid] for oid in self._unacknowledged_orders
                            if self._orders[oid].symbol == symbol
                            and self._orders[oid].side.value == side.upper()
                            and self._orders[oid].order_type == order_type), None)
        if pending is not None:
            self.refresh_order(pending.order_id)
        return pending

    def recover_uncertain_orders(self) -> None:
        """Poll unresolved entries/exits/protection even without an active entry plan."""
        now = time.monotonic()
        if now - self._last_order_recovery_at < 5:
            return
        self._last_order_recovery_at = now
        with self._state_lock:
            order_ids = list(self._unacknowledged_orders.keys() | self._cancel_requested_orders)
        for order_id in order_ids:
            self.refresh_order(order_id)
            if order_id in self._cancel_requested_orders:
                if (getattr(self, "_recovery_only", False)
                        and self._orders[order_id].order_type not in (OrderType.LIMIT, OrderType.MARKET)):
                    continue  # Observe an old cancellation, but preserve native protection on restart.
                self.cancel_order(order_id)

    def _reject_submission(self, order: Order, reason: str) -> None:
        with self._state_lock:
            if order.filled_quantity > 0 or order.status == OrderStatus.FILLED:
                logger.error("REJECTION_AFTER_FILL %s: %s", order.order_id, reason)
                return
            self._unacknowledged_orders.pop(order.order_id, None)
            self._cancel_requested_orders.discard(order.order_id)
            order.status = OrderStatus.REJECTED
            order.rejection_reason = reason
            self._persist_order(order, kind="rejection")


    def _fetch_balance_from_exchange(self) -> float:
        if self.dry_run:
            self.balance_known = True
            self.last_balance_observed_at = time.monotonic()
            return 0.0
        try:
            balance = self._adapter.fetch_balance()
            raw_free = balance["free"]["USDT"]
            if isinstance(raw_free, bool):
                raise ValueError("Invalid USDT free balance")
            usdt_free = float(raw_free)
            if not math.isfinite(usdt_free) or usdt_free < 0:
                raise ValueError("Invalid USDT free balance")
            self.balance_known = True
            self.last_balance_error = None
            self.last_balance_observed_at = time.monotonic()
            return float(usdt_free)
        except Exception as e:
            # Returning 0.0 here makes the risk manager think the account is empty,
            # which silently disables every new entry. Surface the failure via flags
            # so callers and /healthz can react instead of trading on phantom zero.
            self.metrics["balance_fetch_failures"] += 1
            self.balance_known = False
            self.last_balance_error = str(e)
            logger.error(f"Failed to fetch balance from exchange: {e}")
            # Preserve the previously-known balance so a single transient error
            # doesn't trip the floor; only the flag changes so the caller knows
            # this number is stale.
            return self._cached_balance if self._cached_balance else 0.0

    def _total_exposure_usd(self, exclude_order_id: Optional[str] = None) -> float:
        """Open entry-cost exposure plus unfilled, non-reduce-only entry commitments."""
        with self._state_lock:
            total = 0.0
            for symbol, qty in self._positions.items():
                if isinstance(qty, bool) or not isinstance(qty, (int, float)) or not math.isfinite(qty):
                    raise ValueError(f"Invalid position quantity for {symbol}")
                if abs(qty) < 1e-9:
                    continue
                avg = self._position_avg_price.get(symbol)
                if (isinstance(avg, bool) or not isinstance(avg, (int, float))
                        or not math.isfinite(avg) or avg <= 0):
                    raise ValueError(f"Unknown position cost for {symbol}")
                total += abs(qty) * avg
            for order_id, order in self._orders.items():
                if (order_id == exclude_order_id or order_id in self._reduce_only_order_ids
                        or order.order_type not in (OrderType.LIMIT, OrderType.MARKET)
                        or order.status not in (OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED)):
                    continue
                if (any(isinstance(v, bool) or not isinstance(v, (int, float))
                        for v in (order.quantity, order.filled_quantity))
                        or not math.isfinite(order.quantity) or not math.isfinite(order.filled_quantity)
                        or order.quantity <= 0 or order.filled_quantity < 0):
                    raise ValueError(f"Invalid pending quantity for {order_id}")
                remaining = max(0.0, order.quantity - order.filled_quantity)
                if remaining <= 1e-9:
                    continue
                price = order.price
                if (isinstance(price, bool) or not isinstance(price, (int, float))
                        or not math.isfinite(price) or price <= 0):
                    raise ValueError(f"Unknown pending entry price for {order_id}")
                total += remaining * price
            if not math.isfinite(total):
                raise ValueError("Nonfinite exposure")
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
        sl_price: Optional[float] = None,
        tp_price: Optional[float] = None,
        reduce_only: bool = False,
    ) -> Order:
        """
        Place an order on Phemex (or log it in dry_run mode).

        sl_price / tp_price: when provided, attached inline to the entry order
        as position-level SL/TP per Phemex conditional order spec. This is atomic —
        protection exists the moment the entry fills, not in a separate API call.
        _place_exchange_stop() still fires after fill as a belt-and-suspenders backup;
        Phemex auto-cancels the redundant order via closeOnTrigger.

        Runs pre-flight safety checks before sending to the exchange.
        Returns an Order with status=REJECTED if any check fails.
        """
        if (isinstance(quantity, bool) or not isinstance(quantity, (int, float))
                or not math.isfinite(quantity) or quantity <= 0):
            raise ValueError("Quantity must be positive")

        try:
            order_side = OrderSide(side.upper())
            order_type_enum = OrderType(order_type.upper())
        except ValueError:
            raise ValueError(f"Invalid order side '{side}' or type '{order_type}'")

        if order_type_enum == OrderType.LIMIT and price is None:
            raise ValueError("Limit orders require a price")
        if not self.dry_run and getattr(self, "_recovery_only", False):
            self._require_storage(new_request=True)

        with self._state_lock:
            order_id = self._generate_order_id()
            order = Order(
                order_id=order_id, symbol=symbol, side=order_side,
                order_type=order_type_enum, quantity=quantity, price=price,
                stop_price=stop_price, status=OrderStatus.OPEN,
            )
            self._orders[order_id] = order
            if reduce_only:
                self._reduce_only_order_ids.add(order_id)
            else:
                # Reserve this request before releasing the lock / sending it.
                # The candidate is excluded from existing exposure to count it once.
                try:
                    if not getattr(self, "_entry_admission_enabled", True):
                        raise ValueError("Session stopping; new entry blocked")
                    if self._unacknowledged_orders:
                        raise ValueError("Unresolved exchange order outcome; new entry blocked")
                    if not self.balance_known or not math.isfinite(self._cached_balance):
                        raise ValueError("Balance unavailable; new entry blocked")
                    ref_price = price
                    if (ref_price is None or isinstance(ref_price, bool)
                            or not math.isfinite(ref_price) or ref_price <= 0):
                        raise ValueError("Entry price unavailable for exposure checks")
                    position_usd = quantity * ref_price
                    if (not math.isfinite(position_usd)
                            or not math.isfinite(self.max_position_size_usd)
                            or self.max_position_size_usd <= 0
                            or position_usd > self.max_position_size_usd):
                        raise ValueError(f"Position size exceeds cap ${self.max_position_size_usd:.2f}")
                    total = self._total_exposure_usd(exclude_order_id=order_id) + position_usd
                    if (not math.isfinite(self.max_total_exposure_usd)
                            or self.max_total_exposure_usd <= 0
                            or total > self.max_total_exposure_usd):
                        raise ValueError(f"Total committed exposure ${total:.2f} would exceed ${self.max_total_exposure_usd:.2f}")
                    if self._cached_balance < self.min_balance_usd:
                        raise ValueError(f"Balance ${self._cached_balance:.2f} below minimum ${self.min_balance_usd:.2f}")
                except (ValueError, TypeError) as exc:
                    order.status = OrderStatus.REJECTED
                    order.rejection_reason = str(exc)
                    logger.warning("Order REJECTED: %s", exc)
                    return order

        if self.dry_run:
            logger.info(
                f"[DRY RUN] Order would send: {order_id} {side} {quantity} "
                f"{symbol} @ {price} leverage={self.target_leverage}x"
                + (" | reduceOnly" if reduce_only else "")
                + (f" | inline SL={sl_price}" if sl_price else "")
                + (f" TP={tp_price}" if tp_price else "")
            )
            return order

        # Ensure margin mode and leverage are set correctly before the first order
        # per symbol. Phemex persists these settings per symbol on the account,
        # so we only need to set them once per session.
        self._require_storage(new_request=True)
        if symbol not in self._leverage_confirmed:
            self._adapter.set_margin_mode(symbol, mode="isolated")
            try:
                self._adapter.set_leverage(self.target_leverage, symbol)
                self._leverage_confirmed.add(symbol)
            except Exception as e:
                # Phemex refuses set_leverage when an open position already exists.
                # Abort the order rather than silently placing it at the account's
                # current leverage, which may be very different from target.
                # Record the reason on the order (audit #7, CLAUDE.md "never destroy a
                # rejection reason") — every sibling reject path sets rejection_reason;
                # this one previously left it None, so the cause was lost on the
                # persisted JSONL record and only lived in this transient log.
                msg = (
                    f"Leverage mismatch: cannot set {self.target_leverage}x for {symbol} "
                    f"(close any existing {symbol} position first): {e}"
                )
                logger.error(f"LEVERAGE MISMATCH: {msg}. Order BLOCKED.")
                order.status = OrderStatus.REJECTED
                order.rejection_reason = msg
                return order

        # Send to exchange
        ccxt_type = order_type_enum.value.lower()
        if order_type_enum in (OrderType.STOP_LOSS, OrderType.TAKE_PROFIT):
            ccxt_type = "market"  # Phemex handles SL/TP as market exits

        ccxt_side = order_side.value.lower()

        # In hedge mode, Phemex requires positionSide on every order.
        # For entry orders: BUY=Long, SELL=Short.
        # For exit/reduce orders: use reduceOnly instead (simpler and mode-agnostic).
        extra_params: dict = {"clientOrderId": order_id}
        if reduce_only:
            extra_params["reduceOnly"] = True
        if self._hedge_mode:
            # CCXT Phemex reads posSide (not positionSide) — see ccxt/phemex.py line 2660.
            extra_params["posSide"] = "Long" if ccxt_side == "buy" else "Short"
        if sl_price and sl_price > 0:
            extra_params["stopLossPrice"] = sl_price
            extra_params["slTrigger"] = "ByMarkPrice"
        if tp_price and tp_price > 0:
            extra_params["takeProfitPrice"] = tp_price
            extra_params["tpTrigger"] = "ByMarkPrice"

        def _send_order(params: dict) -> dict:
            return self._send_journaled_order(order,
                symbol=symbol,
                order_type=ccxt_type,
                side=ccxt_side,
                amount=quantity,
                price=price,
                params=params if params else None,
            )

        with self._state_lock:
            # Margin/leverage setup may have yielded to a shutdown in another thread.
            if not reduce_only and not getattr(self, "_entry_admission_enabled", True):
                self._reject_submission(order, "Session stopping; new entry blocked")
                return order
            self._submission_unknown(order, "Awaiting submission acknowledgment", log_level=logging.DEBUG)
        try:
            exchange_order = _send_order(extra_params)
            self._accept_submission(order, exchange_order)
            exchange_id = self._exchange_order_map.get(order_id, "")
            logger.info(
                f"Order sent: {order_id} → exchange_id={exchange_id} "
                f"{side} {quantity} {symbol} @ {price}"
            )
        except ccxt.InsufficientFunds as e:
            logger.error(f"Insufficient funds for {order_id}")
            self._reject_submission(order, f"Insufficient funds: {e}")
        except ccxt.InvalidOrder as e:
            logger.error(f"Invalid order {order_id}: {e}")
            self._reject_submission(order, f"Invalid order: {e}")
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
                hedge_params["posSide"] = "Long" if ccxt_side == "buy" else "Short"
                try:
                    exchange_order = _send_order(hedge_params)
                    self._accept_submission(order, exchange_order)
                    exchange_id = self._exchange_order_map.get(order_id, "")
                    self._hedge_mode = True  # all future orders will include positionSide
                    logger.info(
                        f"Order sent (hedge-mode retry): {order_id} → {exchange_id} "
                        f"{side} {quantity} {symbol} @ {price}"
                    )
                except Exception as retry_e:
                    logger.error(f"Failed to send {order_id} after hedge-mode retry: {retry_e}")
                    self._submission_unknown(order, str(retry_e))
            else:
                logger.error(f"Failed to send order {order_id} to exchange: {e}")
                self._submission_unknown(order, str(e))

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

        return self.refresh_order(order_id)

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

        return self.refresh_order(order_id)

    def check_fill_via_positions(self, order_id: str) -> Optional[Fill]:
        """Legacy entry point: recover only through the original order identity.

        Account positions can include unrelated/manual activity and cannot prove
        this order's quantity, price or completion. When order history lags, keep
        its unresolved state and reservation. Restored requests use the same
        identity recovery without replaying local cash or position accounting.
        """
        return self.refresh_order(order_id)

    def _process_exchange_order(self, order: Order, ex_order: Dict, source: str = "rest") -> Optional[Fill]:
        """Apply explicit cumulative execution facts; incomplete terminal data stays unresolved."""
        with self._state_lock:
            self._execution_revision = getattr(self, "_execution_revision", 0) + 1
            if order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
                return None
            try:
                status = ex_order.get("status")
                if status not in ("open", "new", "partiallyfilled", "closed", "filled",
                                  "canceled", "cancelled", "rejected"):
                    raise ValueError(f"Unrecognized order status: {status}")
                raw_filled = ex_order.get("filled")
                if raw_filled is None:
                    if status not in ("open", "new"):
                        raise ValueError("Terminal/partial order response lacks filled quantity")
                    # An accepted resting order is not evidence of execution.
                    filled = order.filled_quantity
                else:
                    if isinstance(raw_filled, bool):
                        raise ValueError("Invalid filled quantity")
                    filled = float(raw_filled)
                if (not math.isfinite(filled) or filled < order.filled_quantity - 1e-9
                        or filled < 0 or filled > order.quantity + 1e-9):
                    raise ValueError("Invalid or regressing cumulative filled quantity")
                if status in ("closed", "filled") and filled <= 1e-9:
                    raise ValueError("Closed order has no confirmed fill")
                incremental = filled - order.filled_quantity
                raw_price = ex_order.get("average")
                if raw_price is None:
                    raw_price = ex_order.get("price")
                price = float(raw_price) if raw_price is not None and not isinstance(raw_price, bool) else 0.0
                if incremental > 1e-9 and (not math.isfinite(price) or price <= 0):
                    raise ValueError("Execution price unavailable")
            except (ValueError, TypeError, AttributeError) as exc:
                self._submission_unknown(order, str(exc))
                return None

            fill = None
            if incremental > 1e-9:
                if (order.order_type in (OrderType.LIMIT, OrderType.MARKET)
                        and order.order_id not in getattr(self, "_restored_ids", set())):
                    fill = self._record_fill(order, incremental, price)
                    self.metrics[f"fills_recorded_via_{source}"] += 1
                else:
                    # Native protection is reflected in position reconciliation.
                    order.filled_quantity = filled
                    order.average_fill_price = price
            if status in ("canceled", "cancelled", "rejected"):
                order.status = (OrderStatus.FILLED if filled > 1e-9 else
                                OrderStatus.REJECTED if status == "rejected" else OrderStatus.CANCELLED)
            elif status in ("closed", "filled"):
                order.status = OrderStatus.FILLED
            else:
                order.status = OrderStatus.PARTIALLY_FILLED if filled > 1e-9 else OrderStatus.OPEN
            order.updated_at = datetime.now(timezone.utc)
            if order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
                self._cancel_requested_orders.discard(order.order_id)
            if self._unacknowledged_orders.pop(order.order_id, None) is not None:
                logger.info("ORDER_OUTCOME_RESOLVED %s status=%s filled=%.8f",
                            order.order_id, order.status.value, order.filled_quantity)
            self._persist_order(order, source=source)
            return fill

    def _record_fill(self, order: Order, qty: float, price: float) -> Fill:
        """Record a fill, update order state, positions, and balance."""
        with self._state_lock:
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
            with self._state_lock:
                self._require_storage()
                if order_id not in getattr(self, "_journaled_ids", set()):
                    raise JournalError("Cannot cancel an order without durable request identity")
                self._execution_revision = getattr(self, "_execution_revision", 0) + 1
                self._cancel_requested_orders.add(order_id)
                self._persist_order(order, kind="cancel_intent")
            exchange_id = self._exchange_order_map.get(order_id)
            if not exchange_id:
                self.refresh_order(order_id)
                exchange_id = self._exchange_order_map.get(order_id)
                if not exchange_id or order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
                    return False
            if exchange_id:
                try:
                    with self._state_lock:
                        self._require_storage()
                        self._inflight_mutations = getattr(self, "_inflight_mutations", 0) + 1
                    try:
                        result = self._adapter.cancel_order(exchange_id, order.symbol)
                    finally:
                        with self._state_lock:
                            self._inflight_mutations -= 1
                    status = result.get("status")
                    if status not in ("closed", "filled", "canceled", "cancelled", "rejected"):
                        self._submission_unknown(order, f"Cancellation unconfirmed: {status}")
                        return False
                    self._process_exchange_order(order, result)
                    return order.status in (OrderStatus.CANCELLED, OrderStatus.REJECTED)
                except Exception as e:
                    self._submission_unknown(order, f"Cancellation failed: {e}")
                    return False

        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now(timezone.utc)

        if order.filled_quantity > 1e-9:
            # Part of this order filled before cancellation (TTL expiry, manual cancel, etc.).
            # Surface it as FILLED so the caller opens a position with the partial qty rather
            # than silently discarding fills that already landed on the exchange.
            order.status = OrderStatus.FILLED
            logger.info(
                f"Order {order_id} had partial fill of {order.filled_quantity:.6f} before cancel — "
                f"treating as final fill so position opens with reduced size"
            )
            return False  # Caller checks order.status == FILLED on False return

        logger.info(f"Order {order_id} cancelled")
        return True

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        open_statuses = {OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED}
        with self._state_lock:
            orders = [o for o in self._orders.values() if o.status in open_statuses]
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders

    def get_position(self, symbol: str) -> float:
        return self._positions.get(symbol, 0.0)

    def get_open_entry_orders(self) -> List[Order]:
        with self._state_lock:
            return [order for order in self.get_open_orders()
                    if order.order_type in (OrderType.LIMIT, OrderType.MARKET)
                    and order.order_id not in self._reduce_only_order_ids]

    def get_balance(self) -> float:
        return self._cached_balance

    def get_open_position_symbols(self) -> set:
        """Include exchange-reconciled exposure even without a PositionManager entry."""
        with self._state_lock:
            return {symbol for symbol, qty in self._positions.items() if qty != 0}

    def get_equity(self, market_prices: Dict[str, float]) -> Optional[float]:
        """Return unavailable rather than valuing an unpriced position at zero.

        Price freshness belongs to the caller; the live service supplies only
        recent successful observations. The existing balance basis is unchanged.
        """
        with self._state_lock:
            try:
                if not self.balance_known or not math.isfinite(self._cached_balance):
                    raise ValueError("Balance unavailable")
                unrealized_pnl = 0.0
                for symbol, qty in self._positions.items():
                    if isinstance(qty, bool) or not isinstance(qty, (int, float)) or not math.isfinite(qty):
                        raise ValueError(f"Invalid position quantity for {symbol}")
                    if abs(qty) < 1e-9:
                        continue
                    current = market_prices.get(symbol)
                    average = self._position_avg_price.get(symbol)
                    for value in (current, average):
                        if (isinstance(value, bool) or not isinstance(value, (int, float))
                                or not math.isfinite(value) or value <= 0):
                            raise ValueError(f"Valuation price unavailable for {symbol}")
                    unrealized_pnl += (current - average) * qty
                equity = self._cached_balance + unrealized_pnl
                if not math.isfinite(equity):
                    raise ValueError("Nonfinite equity")
            except (ValueError, TypeError) as exc:
                self.last_equity_error = str(exc)
                return None
            self.last_equity_error = None
            return equity

    def get_pnl(self, market_prices: Dict[str, float]) -> Optional[float]:
        equity = self.get_equity(market_prices)
        return None if equity is None else equity - self._initial_balance

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
        pending = self._recover_uncertain_protection(symbol, side, OrderType.STOP_LOSS)
        if pending is not None:
            return pending
        if not self.dry_run:
            self._require_storage(new_request=True)
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
        with self._state_lock:
            self._orders[order_id] = order

        if self.dry_run:
            logger.info(
                f"[DRY RUN] Exchange stop would place: {order_id} {side} {quantity} "
                f"{symbol} trigger @ {stop_price}"
            )
            return order

        self._submission_unknown(order, "Awaiting protective-order acknowledgment", log_level=logging.DEBUG)
        try:
            # Phemex stop-market via CCXT:
            #   order_type="market" + params["stopPrice"] → CCXT sets ordType="Stop" + stopPxRp
            #   triggerDirection is required by CCXT's Phemex adapter when a stopPrice is present:
            #     SELL stop (close LONG): price must fall to trigger → "descending"
            #     BUY  stop (close SHORT): price must rise to trigger → "ascending"
            #   triggerType=ByMarkPrice prevents wick-hunt triggers on last-price spikes.
            #   closeOnTrigger: when this stop fires, Phemex auto-cancels other
            #   closeOnTrigger orders (e.g. trailing stop) on the same position.
            trigger_dir = "descending" if side.upper() == "SELL" else "ascending"
            stop_params: dict = {
                "clientOrderId": order_id,
                "stopPrice": stop_price,
                "triggerDirection": trigger_dir,
                "triggerType": "ByMarkPrice",
                "reduceOnly": True,
                "closeOnTrigger": True,
            }
            if self._hedge_mode:
                # CCXT Phemex reads posSide (not positionSide) at line 2660 of ccxt/phemex.py.
                # SELL stop closes a LONG → posSide=Long; BUY stop closes SHORT → posSide=Short.
                stop_params["posSide"] = "Long" if side.upper() == "SELL" else "Short"
            exchange_order = self._send_journaled_order(order,
                symbol=symbol,
                order_type="market",    # CCXT converts to "Stop" ordType when stopPrice is set
                side=side.lower(),
                amount=quantity,
                price=None,             # No limit price for a stop-market
                params=stop_params,
            )
            self._accept_submission(order, exchange_order)
            exchange_id = self._exchange_order_map.get(order_id, "")
            logger.info(
                f"Exchange stop placed: {order_id} → exchange_id={exchange_id} "
                f"{side} {quantity} {symbol} trigger @ {stop_price}"
            )
        except (ccxt.InsufficientFunds, ccxt.InvalidOrder) as exc:
            self._reject_submission(order, str(exc))
            logger.warning("Protective order rejected: %s", exc)
        except Exception as e:
            logger.warning(
                f"Exchange stop placement failed for {symbol} @ {stop_price} — "
                f"software monitoring remains active. Error: {e}"
            )
            self._submission_unknown(order, str(e))

        return order

    def place_take_profit_order(
        self,
        symbol: str,
        side: str,      # closing side: SELL for LONG, BUY for SHORT
        quantity: float,
        tp_price: float,
    ) -> Order:
        """
        Place a reduce-only limit order as an exchange-native take profit.

        Using a limit order (not take_profit_market) so the TP shows in the
        position card's TP/SL section on Phemex and fills at the exact price
        rather than market-slipping through it.
        """
        pending = self._recover_uncertain_protection(symbol, side, OrderType.TAKE_PROFIT)
        if pending is not None:
            return pending
        if not self.dry_run:
            self._require_storage(new_request=True)
        order_id = self._generate_order_id()
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=OrderSide(side.upper()),
            order_type=OrderType.TAKE_PROFIT,
            quantity=quantity,
            price=tp_price,
            stop_price=tp_price,
            status=OrderStatus.OPEN,
        )
        with self._state_lock:
            self._orders[order_id] = order

        if self.dry_run:
            logger.info(
                f"[DRY RUN] TP would place: {order_id} {side} {quantity} "
                f"{symbol} @ {tp_price}"
            )
            return order

        self._submission_unknown(order, "Awaiting protective-order acknowledgment", log_level=logging.DEBUG)
        try:
            # TP is a plain reduce-only limit order. closeOnTrigger is only meaningful
            # on Phemex conditional orders (Stop, StopLimit) — on a resting limit it is
            # silently ignored. reduceOnly alone is sufficient to ensure it only closes.
            tp_params: dict = {
                "clientOrderId": order_id,
                "reduceOnly": True,
            }
            if self._hedge_mode:
                tp_params["posSide"] = "Long" if side.upper() == "SELL" else "Short"
            exchange_order = self._send_journaled_order(order,
                symbol=symbol,
                order_type="limit",
                side=side.lower(),
                amount=quantity,
                price=tp_price,
                params=tp_params,
            )
            self._accept_submission(order, exchange_order)
            exchange_id = self._exchange_order_map.get(order_id, "")
            logger.info(
                f"TP placed: {order_id} → {exchange_id} "
                f"{side} {quantity} {symbol} @ {tp_price}"
            )
        except (ccxt.InsufficientFunds, ccxt.InvalidOrder) as exc:
            self._reject_submission(order, str(exc))
            logger.warning("Protective order rejected: %s", exc)
        except Exception as e:
            logger.warning(
                f"TP placement failed for {symbol} @ {tp_price} — "
                f"software monitoring remains active. Error: {e}"
            )
            self._submission_unknown(order, str(e))

        return order

    def place_trailing_stop_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        activation_price: float,
        callback_rate: float,   # percentage, e.g. 1.5 for 1.5%
    ) -> Order:
        """
        Place an exchange-native trailing stop on Phemex.

        orderType = TrailingStopMarket per Phemex spec.
        activationPrice: absolute price at which trailing begins tracking.
        callbackRate: trailing distance as a percentage of peak price
                      (e.g. 1.5 means stop trails 1.5% below the highest price).

        Phemex manages the moving stop on their servers — survives server restarts.
        Placed alongside the fixed SL; closeOnTrigger ensures only one fires.
        """
        pending = self._recover_uncertain_protection(symbol, side, OrderType.TRAILING_STOP)
        if pending is not None:
            return pending
        if not self.dry_run:
            self._require_storage(new_request=True)
        order_id = self._generate_order_id()
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=OrderSide(side.upper()),
            order_type=OrderType.TRAILING_STOP,
            quantity=quantity,
            price=activation_price,
            stop_price=activation_price,
            status=OrderStatus.OPEN,
        )
        with self._state_lock:
            self._orders[order_id] = order

        if self.dry_run:
            logger.info(
                f"[DRY RUN] Trailing stop would place: {order_id} {side} {quantity} "
                f"{symbol} activation={activation_price:.5f} callback={callback_rate:.2f}%"
            )
            return order

        self._submission_unknown(order, "Awaiting protective-order acknowledgment", log_level=logging.DEBUG)
        try:
            # Phemex trailing stop parameters (NOT Binance's callbackRate API):
            #   pegPriceType="TrailingStopPeg" enables server-managed trailing.
            #   pegOffsetValueRp: absolute offset from the peak price. Sign convention:
            #     SELL trail (close LONG): stop trails BELOW price → negative offset
            #     BUY  trail (close SHORT): stop trails ABOVE price → positive offset
            #   stopPrice: activation price — trailing begins tracking once touched.
            #   triggerDirection: "descending" for SELL, "ascending" for BUY.
            offset = round(activation_price * callback_rate / 100, 8)
            trigger_dir = "descending" if side.upper() == "SELL" else "ascending"
            peg_offset = -offset if side.upper() == "SELL" else offset
            trail_params: dict = {
                "clientOrderId": order_id,
                "stopPrice": activation_price,
                "triggerDirection": trigger_dir,
                "pegPriceType": "TrailingStopPeg",
                "pegOffsetValueRp": str(peg_offset),
                "reduceOnly": True,
                "closeOnTrigger": True,
            }
            if self._hedge_mode:
                trail_params["posSide"] = "Long" if side.upper() == "SELL" else "Short"
            exchange_order = self._send_journaled_order(order,
                symbol=symbol,
                order_type="market",    # CCXT converts to trailing stop ordType via pegPriceType
                side=side.lower(),
                amount=quantity,
                price=None,
                params=trail_params,
            )
            self._accept_submission(order, exchange_order)
            exchange_id = self._exchange_order_map.get(order_id, "")
            logger.info(
                f"Trailing stop placed: {order_id} → {exchange_id} "
                f"{side} {quantity} {symbol} "
                f"activation={activation_price:.5f} callback={callback_rate:.2f}%"
            )
        except (ccxt.InsufficientFunds, ccxt.InvalidOrder) as exc:
            self._reject_submission(order, str(exc))
            logger.warning("Protective order rejected: %s", exc)
        except Exception as e:
            logger.warning(
                f"Trailing stop placement failed for {symbol} "
                f"(activation={activation_price:.5f}, callback={callback_rate:.2f}%) — "
                f"fixed stop remains active. Error: {e}"
            )
            self._submission_unknown(order, str(e))

        return order

    # ------------------------------------------------------------------
    # Live-only methods (not in PaperExecutor)
    # ------------------------------------------------------------------

    def apply_ws_fill(
        self, exchange_id: str, client_order_id: str, status: str, filled_qty: float, avg_price: float
    ) -> None:
        """Recover order identity and apply only explicit WebSocket execution facts."""
        with self._state_lock:
            order_id = self._reverse_order_map.get(exchange_id)
            if not order_id and client_order_id in self._orders:
                order_id = client_order_id
            if not order_id:
                return
            if client_order_id and client_order_id != order_id:
                logger.error("WS_ORDER_ID_MISMATCH %s %s", order_id, client_order_id)
                return
            order = self._orders[order_id]
            if exchange_id:
                existing_id = self._exchange_order_map.get(order_id)
                if existing_id and existing_id != exchange_id:
                    self._submission_unknown(order, "WebSocket exchange identity mismatch")
                    return
                self._exchange_order_map[order_id] = exchange_id
                self._reverse_order_map[exchange_id] = order_id
            self._process_exchange_order(order, {
                "status": status.lower(), "filled": filled_qty, "average": avg_price,
            }, source="ws")

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

    def reconcile_positions(self) -> Optional[set]:
        """Sync a complete validated snapshot; return None when state is unknown.

        A valid empty set means the exchange reported no open positions. Fetch,
        parsing and unsupported multi-position failures must not clear local state
        or be interpreted by callers as evidence that a position closed.
        """
        if self.dry_run:
            return {sym for sym, qty in self._positions.items() if abs(qty) > 1e-9}
        try:
            rows = self._adapter.fetch_positions()
            if not isinstance(rows, list):
                raise ValueError("Position snapshot must be a list")

            quantities: Dict[str, float] = {}
            prices: Dict[str, float] = {}
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError("Position snapshot contains a non-object row")
                symbol = row.get("symbol")
                if not isinstance(symbol, str) or not symbol or symbol != symbol.strip():
                    raise ValueError("Position snapshot contains an invalid symbol")
                raw_qty = row["contracts"]
                if isinstance(raw_qty, bool):
                    raise ValueError(f"Invalid position quantity for {symbol}")
                qty = float(raw_qty)
                if not math.isfinite(qty) or qty < 0:
                    raise ValueError(f"Invalid position quantity for {symbol}")
                if qty <= 1e-9:
                    continue
                side = row.get("side")
                if not isinstance(side, str) or side.lower() not in ("long", "short"):
                    raise ValueError(f"Unknown position side for {symbol}")
                raw_price = row["entryPrice"]
                if isinstance(raw_price, bool):
                    raise ValueError(f"Invalid position entry price for {symbol}")
                entry_price = float(raw_price)
                if not math.isfinite(entry_price) or entry_price <= 0:
                    raise ValueError(f"Invalid position entry price for {symbol}")
                if symbol in quantities:
                    raise ValueError(f"Multiple open positions for {symbol} cannot be reconciled")
                quantities[symbol] = qty if side.lower() == "long" else -qty
                prices[symbol] = entry_price
        except Exception as e:
            logger.error("Position reconciliation unavailable; preserving local state: %s", e)
            return None

        # Publish only after every row validates, including clearing symbols that
        # are absent from this successful full snapshot.
        with self._state_lock:
            for symbol in self._positions.keys() | quantities.keys():
                old_qty = self._positions.get(symbol, 0.0)
                qty = quantities.get(symbol, 0.0)
                if abs(qty - old_qty) > 1e-6:
                    logger.warning(
                        "Position discrepancy for %s: local=%.6f exchange=%.6f — syncing",
                        symbol, old_qty, qty,
                    )
                self._positions[symbol] = qty
                self._position_avg_price[symbol] = prices.get(symbol, 0.0)
            return set(quantities)

    def preflight_check(self) -> Dict:
        """Run connectivity + balance + position check before session start."""
        import time as _time
        issues = []
        result: Dict = {"ok": False, "balance": 0.0, "open_positions": [], "issues": issues}

        if not self._adapter.supports_trading() and not self.dry_run:
            issues.append("No API keys configured")
            return result

        # Phemex requires request timestamps within ±60 s of server time.
        # A skewed local clock causes signed REST requests and WS auth tokens to
        # be rejected silently. Warn early so the operator can fix NTP before trading.
        if not self.dry_run:
            try:
                server_ms = self._adapter.exchange.fetch_time()   # ms since epoch
                local_ms = _time.time() * 1000
                skew_s = abs(server_ms - local_ms) / 1000
                result["clock_skew_seconds"] = round(skew_s, 2)
                if skew_s > 10:
                    msg = (
                        f"Local clock is {skew_s:.1f}s off from Phemex server time. "
                        f"Sync with NTP (sudo ntpdate -u pool.ntp.org) — "
                        f"Phemex rejects requests with >60 s skew."
                    )
                    if skew_s > 30:
                        issues.append(msg)
                    else:
                        logger.warning(f"CLOCK SKEW WARNING: {msg}")
            except Exception as e:
                logger.debug(f"Clock skew check failed (non-blocking): {e}")

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
