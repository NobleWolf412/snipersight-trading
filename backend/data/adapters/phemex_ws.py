"""
Phemex WebSocket Client

Subscribes to the AOP (Account Order Position) channel for perpetual contracts.
Delivers real-time order fill notifications to LiveExecutor, replacing the
once-per-second REST poll for entry order fills.

Protocol:
  wss://ws.phemex.com  (mainnet)
  wss://testnet-api.phemex.com/ws  (testnet)

Auth:
  method=user.auth, params=["API", api_key, hmac_token, expiry_seconds]
  token = HMAC-SHA256(api_key + str(expiry), api_secret).hexdigest()

Channel:
  aop_p.subscribe — perpetual AOP, pushes order/position/balance snapshots
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from typing import Callable, Optional

import aiohttp

logger = logging.getLogger(__name__)

MAINNET_WS_URL = "wss://ws.phemex.com"
TESTNET_WS_URL = "wss://testnet-api.phemex.com/ws"

_HEARTBEAT_INTERVAL = 20    # seconds between server.ping messages
_RECONNECT_DELAY = 5        # seconds to wait before reconnect attempt
_AUTH_TIMEOUT = 10.0        # seconds to wait for auth response


class PhemexWebSocketClient:
    """
    Phemex WebSocket client for real-time AOP order updates.

    Calls on_order_update(exchange_id, client_order_id, status, filled_qty, avg_price)
    whenever an order status changes.  The callback is synchronous — it updates the
    executor's in-memory order state so the monitor loop can open positions within its
    next 1-second tick without issuing an extra REST poll.

    Usage:
        client = PhemexWebSocketClient(api_key, api_secret, testnet, callback)
        task = asyncio.create_task(client.run())
        ...
        await client.stop()
        task.cancel()
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = False,
        on_order_update: Optional[Callable] = None,
        on_raw_order: Optional[Callable] = None,
        on_invalidate: Optional[Callable] = None,
        on_pending: Optional[Callable] = None,
        on_complete: Optional[Callable] = None,
    ):
        self._api_key = api_key
        self._api_secret = api_secret
        self._ws_url = TESTNET_WS_URL if testnet else MAINNET_WS_URL
        self._on_order_update = on_order_update
        self._on_raw_order = on_raw_order
        self._on_invalidate = on_invalidate
        self._on_pending = on_pending
        self._on_complete = on_complete
        self._queue = asyncio.Queue(maxsize=256)
        self._worker = None
        self._ws = None
        self._stop_lock = asyncio.Lock()
        self._running = False
        self._msg_id = 0

        # Lightweight observability — read by /api/integrations/phemex/healthz so
        # operators can see WS state without rummaging through logs.
        self.metrics = {
            "connected": False,
            "connect_ts": None,
            "disconnect_ts": None,
            "last_frame_ts": None,
            "frames_in_total": 0,
            "frames_aop_total": 0,
            "frames_other_total": 0,
            "parse_errors_total": 0,
            "auth_errors_total": 0,
            "disconnects_total": 0,
            "heartbeat_failures_total": 0,
            "order_events_total": 0,
            "queue_overflows_total": 0,
            "callback_failures_total": 0,
        }

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    def _make_auth_token(self) -> tuple:
        """Return (token, expiry) for a user.auth message valid for 60 seconds."""
        expiry = int(time.time()) + 60
        message = self._api_key + str(expiry)
        token = hmac.new(
            self._api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return token, expiry

    async def run(self) -> None:
        """Connect, authenticate, subscribe, and receive until stop() is called."""
        self._running = True
        if self._on_raw_order:
            self._worker = asyncio.create_task(self._consume_orders())
        try:
            while self._running:
                try:
                    self._invalidate('WS_RECONNECT_RECONCILIATION_REQUIRED')
                    await self._connect_and_receive()
                except asyncio.CancelledError:
                    await self.stop()
                    break
                except Exception as exc:
                    self.metrics["disconnects_total"] += 1
                    self._invalidate('WS_DISCONNECTED')
                    self.metrics["connected"] = False
                    self.metrics["disconnect_ts"] = int(time.time() * 1000)
                    logger.warning(
                        f"Phemex WS disconnected ({exc!r}) — "
                        f"reconnecting in {_RECONNECT_DELAY}s"
                    )
                    if self._running:
                        await asyncio.sleep(_RECONNECT_DELAY)
                else:
                    self._invalidate('WS_STREAM_ENDED')
                    if self._running:
                        await asyncio.sleep(_RECONNECT_DELAY)
        finally:
            await self.stop()

    async def stop(self) -> None:
        async with self._stop_lock:
            self._running = False
            if self._ws is not None:
                await self._ws.close()
            if self._worker is not None:
                # Never release ownership while a thread is still committing evidence.
                await asyncio.shield(self._queue.join())
                await self._queue.put(None)
                await asyncio.shield(self._worker)
                self._worker = None

    def _invalidate(self, reason):
        if self._on_invalidate:
            self._on_invalidate(reason)

    async def _consume_orders(self):
        while True:
            order = await self._queue.get()
            try:
                if order is None:
                    return
                await asyncio.to_thread(self._on_raw_order, order)
            except Exception:
                self.metrics['callback_failures_total'] += 1
                self._invalidate('WS_CALLBACK_FAILED')
                logger.exception('WS_CALLBACK_FAILED; REST reconciliation required')
            finally:
                if order is not None and self._on_complete:
                    self._on_complete()
                self._queue.task_done()

    async def _connect_and_receive(self) -> None:
        timeout = aiohttp.ClientTimeout(total=None, connect=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.ws_connect(
                self._ws_url,
                heartbeat=30,
                max_msg_size=4 * 1024 * 1024,
            ) as ws:
                self._ws = ws
                self.metrics["connected"] = True
                self.metrics["connect_ts"] = int(time.time() * 1000)
                logger.info(f"Phemex WS connected: {self._ws_url}")

                # --- Authenticate ---
                token, expiry = self._make_auth_token()
                await ws.send_str(json.dumps({
                    "method": "user.auth",
                    "params": ["API", self._api_key, token, expiry],
                    "id": self._next_id(),
                }))
                auth_msg = await asyncio.wait_for(ws.receive(), timeout=_AUTH_TIMEOUT)
                if auth_msg.type not in (
                    aiohttp.WSMsgType.TEXT, aiohttp.WSMsgType.BINARY
                ):
                    logger.error(f"Phemex WS: unexpected auth response type {auth_msg.type}")
                    return
                auth_data = json.loads(auth_msg.data)
                if auth_data.get("error"):
                    self.metrics["auth_errors_total"] += 1
                    logger.error(f"Phemex WS auth failed: {auth_data['error']}")
                    return
                logger.info("Phemex WS authenticated")

                # --- Subscribe to perpetual AOP channel ---
                await ws.send_str(json.dumps({
                    "method": "aop_p.subscribe",
                    "params": [],
                    "id": self._next_id(),
                }))
                logger.info("Phemex WS subscribed to aop_p (perpetual orders)")

                # Heartbeat runs concurrently with the receive loop
                heartbeat_task = asyncio.create_task(self._heartbeat_loop(ws))
                try:
                    async for msg in ws:
                        if not self._running:
                            break
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            self._dispatch(msg.data)
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            self._dispatch(msg.data.decode("utf-8"))
                        elif msg.type in (
                            aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR
                        ):
                            logger.warning(f"Phemex WS stream ended: {msg.type}")
                            break
                finally:
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        pass

    async def _heartbeat_loop(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        """Sends server.ping every _HEARTBEAT_INTERVAL seconds."""
        while True:
            await asyncio.sleep(_HEARTBEAT_INTERVAL)
            try:
                await ws.send_str(json.dumps({
                    "method": "server.ping",
                    "params": [],
                    "id": self._next_id(),
                }))
            except Exception as e:
                self.metrics["heartbeat_failures_total"] += 1
                logger.warning(f"Phemex WS heartbeat send failed: {e!r}")
                break

    def _dispatch(self, raw: str) -> None:
        """Parse an incoming message and call the order update callback if appropriate."""
        self.metrics["frames_in_total"] += 1
        self.metrics["last_frame_ts"] = int(time.time() * 1000)
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as e:
            # Don't crash on bad JSON, but make it visible — silently dropping frames
            # masks malformed-message bugs and protocol drift.
            self.metrics["parse_errors_total"] += 1
            self._invalidate('WS_FRAME_INVALID')
            logger.warning(
                "Phemex WS JSON parse error: %s (raw_len=%d, head=%r)",
                e, len(raw), raw[:120],
            )
            return

        if not isinstance(msg, dict):
            self._invalidate('WS_FRAME_INVALID')
            return
        msg_type = msg.get("type")

        if self._on_raw_order:
            if msg_type not in ('snapshot', 'incremental', 'aop_p'):
                return
            self.metrics['frames_aop_total'] += 1
            self._invalidate('WS_ACCOUNT_CHANGED')
            orders = msg.get('orders_p', msg.get('orders'))
            if orders is None and isinstance(msg.get('data'), dict):
                orders = msg['data'].get('orders_p', msg['data'].get('orders'))
            if orders is None:
                return  # Account/position notification still invalidates valuation.
            if not isinstance(orders, list) or any(not isinstance(o, dict) for o in orders):
                self._invalidate('WS_ORDER_COLLECTION_INVALID')
                return
            for order in orders:
                try:
                    self._queue.put_nowait(order)
                except asyncio.QueueFull:
                    self.metrics['queue_overflows_total'] += 1
                    self._invalidate('WS_QUEUE_OVERFLOW')
                    logger.error('WS_QUEUE_OVERFLOW; REST reconciliation required')
                    break
                if self._on_pending:
                    self._on_pending()
                self.metrics['order_events_total'] += 1
            return

        # aop_p channel messages carry order arrays
        if msg_type != "aop_p":
            # Log any non-trivial message so format changes are visible in debug logs
            if msg_type and msg_type not in ("pong",):
                self.metrics["frames_other_total"] += 1
                logger.debug("Unhandled WS message type=%r id=%s", msg_type, msg.get("id"))
            return

        self.metrics["frames_aop_total"] += 1
        orders = msg.get("orders") or msg.get("data", {}).get("orders", [])
        for order in orders:
            self.metrics["order_events_total"] += 1
            self._handle_order_event(order)

    def _handle_order_event(self, order: dict) -> None:
        if not self._on_order_update:
            return

        exchange_id = str(order.get("orderID", "") or "")
        client_id = str(order.get("clOrdID", "") or "")
        if not exchange_id:
            return

        status = str(order.get("ordStatus", "") or "")

        # Phemex v2 perpetual uses Rq suffix for plain-decimal quantities/prices.
        # Fall back to unscaled legacy fields when Rq variants are absent.
        filled_qty = _parse_float(order.get("cumQtyRq") or order.get("cumQty"))
        avg_price = _parse_float(
            order.get("avgPriceRp")
            or order.get("avgPx")
            or order.get("priceRp")
            or order.get("price")
        )

        logger.debug(
            "WS order event: exchange_id=%s client_id=%s status=%s "
            "filled=%.6f avg_price=%.5f",
            exchange_id, client_id, status, filled_qty, avg_price,
        )

        self._on_order_update(exchange_id, client_id, status, filled_qty, avg_price)


def _parse_float(value) -> float:
    """Safely convert a value to float, returning 0.0 on failure."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
