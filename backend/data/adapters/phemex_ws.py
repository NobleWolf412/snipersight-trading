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
    ):
        self._api_key = api_key
        self._api_secret = api_secret
        self._ws_url = TESTNET_WS_URL if testnet else MAINNET_WS_URL
        self._on_order_update = on_order_update
        self._running = False
        self._msg_id = 0

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
        while self._running:
            try:
                await self._connect_and_receive()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(
                    f"Phemex WS disconnected ({exc!r}) — "
                    f"reconnecting in {_RECONNECT_DELAY}s"
                )
                if self._running:
                    await asyncio.sleep(_RECONNECT_DELAY)

    async def stop(self) -> None:
        self._running = False

    async def _connect_and_receive(self) -> None:
        timeout = aiohttp.ClientTimeout(total=None, connect=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.ws_connect(
                self._ws_url,
                heartbeat=30,
                max_msg_size=0,
            ) as ws:
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
                            self._dispatch(msg.data.decode("utf-8", errors="ignore"))
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
            except Exception:
                break

    def _dispatch(self, raw: str) -> None:
        """Parse an incoming message and call the order update callback if appropriate."""
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return

        msg_type = msg.get("type")

        # aop_p channel messages carry order arrays
        if msg_type != "aop_p":
            # Log any non-trivial message so format changes are visible in debug logs
            if msg_type and msg_type not in ("pong",):
                logger.debug("Unhandled WS message type=%r id=%s", msg_type, msg.get("id"))
            return

        orders = msg.get("orders") or msg.get("data", {}).get("orders", [])
        for order in orders:
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
