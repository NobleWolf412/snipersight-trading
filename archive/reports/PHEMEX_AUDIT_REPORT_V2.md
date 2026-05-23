# SniperSight — Phemex Integration Audit Report v2

**Date:** 2026-05-05
**Scope:** Every file touching Phemex exchange, cross-referenced against CCXT source (`ccxt/phemex.py`) and Phemex API v2 documentation
**Audited files:** `phemex.py`, `phemex_ws.py`, `live_executor.py`, `live_trading_service.py`, `position_manager.py`, `live_trading_config.py`, `api_server.py`, frontend services

---

## 🔴 CRITICAL — Will cause order rejection or silent failure

### C1: `place_stop_order()` — Invalid order type + missing trigger price

**File:** `live_executor.py`, lines 680–687
**Impact:** Every exchange-native stop-loss order is rejected by Phemex. Positions have NO exchange-side SL protection after entry.

**Root cause:**
```python
exchange_order = self._adapter.create_order(
    symbol=symbol,
    order_type="stop_market",      # ← CCXT capitalizes this to "Stop_market" (INVALID)
    side=side.lower(),
    amount=quantity,
    price=stop_price,              # ← Goes to limit price field (priceRp), NOT trigger (stopPxRp)
    params=stop_params,            # ← Missing: stopPrice/triggerPrice, triggerDirection
)
```

CCXT's Phemex adapter does `type = self.capitalize(type)` at line 2579 and sets `request['ordType'] = type`. Capitalizing `"stop_market"` produces `"Stop_market"`, which is **not** a valid Phemex ordType. Valid types are: `Market`, `Limit`, `Stop`, `StopLimit`, `MarketIfTouched`, `LimitIfTouched`.

Additionally, CCXT reads the trigger price from `params['stopPx']`, `params['stopPrice']`, or `params['triggerPrice']` — **not** from the `price` positional argument. Since none of these exist in `stop_params`, CCXT never sets `stopPxRp` in the request, and the entire trigger-direction/ordType override logic (lines 2676–2694 of `ccxt/phemex.py`) is **skipped**.

**Fix:**
```python
# Option A: Use CCXT's built-in helper (recommended)
exchange_order = self._adapter.exchange.create_stop_market_order(
    symbol=symbol,
    side=side.lower(),
    amount=quantity,
    triggerPrice=stop_price,
    params={
        "clientOrderId": order_id,
        "reduceOnly": True,
        "closeOnTrigger": True,
        "triggerType": "ByMarkPrice",
        "triggerDirection": "descending" if side.upper() == "SELL" else "ascending",
    },
)

# Option B: Use create_order with correct params
exchange_order = self._adapter.create_order(
    symbol=symbol,
    order_type="market",              # "Market" → CCXT converts to "Stop" when triggerPrice present
    side=side.lower(),
    amount=quantity,
    price=None,                       # No limit price for stop-market
    params={
        "stopPrice": stop_price,      # Trigger price → CCXT maps to stopPxRp
        "triggerDirection": "descending" if side.upper() == "SELL" else "ascending",
        "clientOrderId": order_id,
        "reduceOnly": True,
        "closeOnTrigger": True,
        "triggerType": "ByMarkPrice",
    },
)
```

**Why `triggerDirection` is required:** CCXT's Phemex adapter line 2682–2683 raises `ArgumentsRequired` if `triggerDirection` is missing when a trigger price is set. For a stop-loss:
- **SELL stop** (closing a LONG): price is currently above the stop → price must descend to trigger → `"descending"`
- **BUY stop** (closing a SHORT): price is currently below the stop → price must ascend to trigger → `"ascending"`

**Severity note:** Inline SL via `stopLossPrice` on entry orders DOES work correctly (see OK-1 below), providing atomic crash protection the moment the entry fills. But the belt-and-suspenders stop placed by `_place_exchange_stop()` after fill FAILS silently, and the stop update logic in `_sync_exchange_stops()` also FAILS for the same reason. If the inline SL is cancelled or modified by Phemex (e.g., after partial TP fill changes position size), there is no fallback.

---

### C2: `place_trailing_stop_order()` — Invalid order type + wrong parameters

**File:** `live_executor.py`, lines 823–829
**Impact:** Every exchange-native trailing stop is rejected. The `callbackRate` parameter doesn't exist in Phemex's API.

**Root cause:**
```python
exchange_order = self._adapter.create_order(
    symbol=symbol,
    order_type="trailing_stop_market",  # ← "Trailing_stop_market" (INVALID ordType)
    side=side.lower(),
    amount=quantity,
    price=activation_price,             # ← Goes to priceRp, not stopPxRp
    params=trail_params,                # ← Contains "callbackRate" (not a Phemex param)
)
```

Phemex trailing stops use `pegPriceType` + `pegOffsetValueRp`, not `callbackRate` (that's Binance). Per Phemex API docs and CCXT source (line 2603–2604):
- `pegPriceType: "TrailingStopPeg"` (or `"TrailingTakeProfitPeg"`)
- `pegOffsetValueRp: "<offset>"` — negative for longs, positive for shorts
- The trigger is set via `stopPxRp` (the activation price)

**Fix:**
```python
# Calculate absolute trailing offset from callback_rate percentage
if side.upper() == "SELL":  # closing a LONG
    peg_offset = str(-round(activation_price * callback_rate / 100, 8))
    trigger_dir = "descending"
else:  # closing a SHORT
    peg_offset = str(round(activation_price * callback_rate / 100, 8))
    trigger_dir = "ascending"

exchange_order = self._adapter.create_order(
    symbol=symbol,
    order_type="market",
    side=side.lower(),
    amount=quantity,
    price=None,
    params={
        "stopPrice": activation_price,
        "triggerDirection": trigger_dir,
        "pegPriceType": "TrailingStopPeg",
        "pegOffsetValueRp": peg_offset,
        "clientOrderId": order_id,
        "reduceOnly": True,
        "closeOnTrigger": True,
        "triggerType": "ByMarkPrice",
    },
)
```

---

### C3: `_sync_exchange_stops()` inherits C1 bug

**File:** `live_trading_service.py`, lines 1243–1247
**Impact:** Every stop-level update (breakeven moves, trailing stop adjustments) fails silently because it calls `place_stop_order()` which has the C1 bug.

When PositionManager moves the stop (breakeven activation, trailing), `_sync_exchange_stops()` detects the level change and attempts to place a new stop-market order. This goes through `place_stop_order()` which fails per C1. The old stop gets cancelled (line 1253), the new one is rejected → **the position loses ALL exchange-side stop protection**.

The place-before-cancel ordering (lines 1238–1257) is correct in principle, but since the new order always fails, the cancel still executes → **net result: no stop on exchange**.

**Fix:** Fix C1 and this is automatically resolved.

---

## 🟠 HIGH — Functional issue, degraded behavior

### H1: Hedge-mode fallback uses wrong parameter name

**File:** `live_executor.py`, lines 232–236, 282
**Impact:** When the account is in hedge mode, orders are placed with `positionSide` in params, but CCXT's Phemex adapter only reads `posSide` (line 2660). The parameter passes through to Phemex as an unknown field, while CCXT auto-sets `posSide: 'Merged'` (one-way mode) — causing `TE_ERR_INCONSISTENT_POS_MODE`.

```python
# Current (wrong):
extra_params["positionSide"] = "Long" if ccxt_side == "buy" else "Short"

# Correct:
extra_params["posSide"] = "Long" if ccxt_side == "buy" else "Short"
```

CCXT Phemex line 2660: `posSide = self.safe_string_lower(params, 'posSide')` — only checks this exact key. If not found, defaults to `'Merged'`.

**Mitigation:** The bot sets one-way mode at startup, so hedge mode is only a fallback. But when the fallback triggers (open positions prevent mode switch), it's completely broken — the retry loop on line 276–296 will also fail with the same error.

---

### H2: `reconcile_positions()` direction sign logic is fragile

**File:** `live_executor.py`, line 975
**Impact:** Position direction may be wrong after reconciliation.

```python
self._positions[symbol] = ex_qty if local_qty >= 0 else -ex_qty
```

This preserves direction from local state, but if local state is wrong (e.g., stale from a previous session), the reconciled direction will be wrong too. The exchange position has a `side` field (`long`/`short`) that should be used as the source of truth.

**Fix:**
```python
ex_side = pos.get("side", "long").lower()
self._positions[symbol] = ex_qty if ex_side == "long" else -ex_qty
```

---

### H3: `_close_all_positions()` only marks positions closed in software

**File:** `live_trading_service.py`, lines 1480–1487
**Impact:** When the bot stops normally via `stop()`, it calls `_close_all_positions()` which calls `position_manager.close_position()` — this only updates software state. It does NOT send market-sell/buy orders to the exchange to actually close the positions. Positions remain open on Phemex with their exchange-native stops still active.

This may be intentional (let exchange stops manage the exit), but it's worth calling out because:
1. If the user expects the bot to flatten all positions on stop, this doesn't happen
2. The exchange-native stops may have been cancelled during the session and not replaced (due to C1/C3)

**Fix (if flattening is desired):**
```python
async def _close_all_positions(self, reason: str):
    if not self.position_manager or not self.executor:
        return
    for pos in self.position_manager.get_open_positions():
        close_side = "SELL" if pos.direction == "LONG" else "BUY"
        qty = getattr(pos, "remaining_quantity", None) or pos.quantity
        await self._execute_exit_order(pos.symbol, close_side, qty,
                                        self._price_cache.get(pos.symbol, pos.entry_price))
```

---

### H4: `kill_switch()` cancels orders but doesn't flatten positions on exchange

**File:** `live_trading_service.py`, lines 315–344
**Impact:** The kill switch cancels open orders and calls `emergency_close_all()` on the position manager, but `emergency_close_all()` doesn't send exit orders to the exchange — it just marks positions as closed in software. Positions remain open on Phemex.

Note: the `_execute_exit_order` callback registered with PositionManager should handle this, but `emergency_close_all()` may bypass that callback.

---

## 🟡 MEDIUM — Correctness concern, not immediately dangerous

### M1: TP1 `closeOnTrigger` on a limit order may behave unexpectedly

**File:** `live_executor.py`, lines 739–755
**Impact:** `closeOnTrigger: True` on a standard limit order (not a conditional/stop order) is documented for conditional orders on Phemex. On a resting limit order, Phemex may ignore it or reject it. The intent (cancel other same-direction orders when TP fills) may not fire.

The TP1 is placed as `order_type="limit"` with `reduceOnly: True`. This is correct for the limit order itself, but `closeOnTrigger` only has meaning on conditional orders (Stop, StopLimit, MarketIfTouched). Phemex likely ignores it silently on a plain limit.

**Fix:** Remove `closeOnTrigger` from the TP limit order params. When TP1 fills, use the software monitor to cancel the corresponding SL and trailing stop explicitly (which `_sync_closed_positions()` already does via cleanup on position close).

---

### M2: Inline SL + post-fill SL = duplicate stops (if C1 is fixed)

**File:** `live_trading_service.py`, lines 984–997 and 1133–1160
**Impact:** Entry orders attach an inline SL via `stopLossPrice`. After fill, `_place_exchange_stop()` places a second stop-market at the same level. Once C1 is fixed, Phemex will have TWO stops for the same position.

The code comment at line 138 says "Phemex auto-cancels the redundant order via closeOnTrigger" — but `closeOnTrigger` on the inline SL triggers when the entry fills, not when another stop exists. The inline SL becomes the position-level SL/TP bracket order, and the manually-placed stop is a separate conditional order.

**Fix after C1:** After the entry fills, either:
- Don't place a separate stop (rely on the inline SL) and only update it via Phemex's amend-order endpoint when breakeven/trailing kicks in
- OR cancel the inline SL bracket first, then place the standalone stop (which you can cancel/replace freely)

---

### M3: `_startup_reconcile()` cancels ALL open orders including active SL/TP

**File:** `live_trading_service.py`, lines 460–495
**Impact:** On restart, the startup reconcile cancels every open order on the account — including exchange-native stops protecting orphaned positions. This means a position from a prior session loses its SL protection the moment the bot restarts.

Line 482: `if o.get("type", "").lower() not in ("limit", "stop_market", "stop", "trailing_stop_market")` — this condition skips orders NOT in this list, meaning it DOES cancel limit, stop_market, stop, and trailing_stop_market orders. That's backwards from the intent.

**Fix:** Either (a) don't cancel stops on symbols that have open positions, or (b) invert the logic so stops are preserved:
```python
# Only cancel non-protective orders (limit entries without matching position)
if o.get("type", "").lower() in ("limit",) and not symbol_has_position:
    # cancel orphaned limit entry
```

---

### M4: WebSocket AOP message structure assumption

**File:** `phemex_ws.py`, lines 185–188
**Impact:** The dispatch function expects `msg.get("type") == "aop_p"` and `msg.get("orders", [])`. If Phemex changes their AOP message format (e.g., uses `"orders_p"` key or wraps in a `"data"` envelope), fills will be silently missed.

Phemex AOP messages have been observed in two formats:
1. `{"type": "aop_p", "orders": [...]}` (current assumption)
2. `{"orders_p": {"orders": [...], ...}}` (alternate format seen in some API versions)

**Fix:** Add logging for unrecognized message types to aid debugging:
```python
if msg.get("type") not in ("aop_p", None):
    logger.debug(f"Unhandled WS message type: {msg.get('type')}")
    return
```

---

### M5: `fetch_ohlcv` REST fallback hardcodes mainnet URL

**File:** `phemex.py`, line 175
**Impact:** When CCXT fetch fails and the REST fallback triggers, it always hits `https://api.phemex.com/exchange/public/md/kline` — even if the adapter is in testnet mode. Testnet should use `https://testnet-api.phemex.com/...`.

**Fix:**
```python
base_url = "https://testnet-api.phemex.com" if testnet else "https://api.phemex.com"
url = f"{base_url}/exchange/public/md/kline"
```
(Requires storing `self.testnet = testnet` in `__init__`.)

---

### M6: Price scaling heuristic in REST fallback is fragile

**File:** `phemex.py`, lines 204
**Impact:** `scale = 100000000.0 if (rows and rows[0][1] > 1000000) else 1.0` — this heuristic determines if prices are Ep-scaled (legacy) or Rp-scaled (v2 USDT pairs). It breaks for assets that legitimately have prices above 1,000,000 in Rp format (unlikely today but possible for future denominations or index contracts).

---

## 🟢 LOW — Minor issues, improvements

### L1: `balance_reconcile_interval` is 60 seconds but monitor loop runs every 1 second

**File:** `live_trading_service.py`, line 682
**Impact:** Balance and position reconciliation happens every 60 seconds. If an exchange-native stop fires, the bot won't detect it for up to 60 seconds (relying on the WS feed instead). The WS feed should handle this, but if WS disconnects, detection lag is 60s.

Consider reducing to 15–30 seconds for faster detection when WS is down.

---

### L2: `order_timeout_seconds` config field is never used

**File:** `live_trading_config.py`, line 52
**Impact:** The config defines `order_timeout_seconds: int = 30` but no code reads it. Market orders could hang indefinitely if the exchange doesn't fill them.

---

### L3: No rate limiting on `_refresh_price_cache()` ticker fetches

**File:** `live_trading_service.py`, lines 1337–1351
**Impact:** Every 1-second monitor cycle calls `_fetch_price()` for each open position and pending order. With 3 positions + 3 pending orders, that's 6 ticker calls per second. CCXT's rate limiter helps but the bot could still hit Phemex's per-minute limits during busy periods.

Consider batching via `fetch_tickers()` for all symbols at once.

---

### L4: `_detect_exchange_closed_positions` may use stale stop level as exit price

**File:** `live_trading_service.py`, lines 1281–1282
**Impact:** When a position is detected as closed on exchange, the exit price is taken from `_exchange_stop_levels` (the last software-known stop level). But if the exchange-native stop was never successfully placed (due to C1), this level may be the initial SL from the inline bracket. Or if the position was liquidated, the actual exit price could be the liquidation price, not the stop level.

---

## ✅ CONFIRMED WORKING

### OK-1: Inline SL/TP on entry orders
`stopLossPrice` and `takeProfitPrice` in params are correctly handled by CCXT (lines 2737–2743 of `ccxt/phemex.py`). Atomic crash protection exists from the moment the entry fills.

### OK-2: TP1 limit order placement
`place_take_profit_order()` uses `order_type="limit"` with `reduceOnly: True` — standard CCXT path, correctly sets `priceRp` and `ordType: Limit`.

### OK-3: Entry order placement (limit/market)
`place_order()` correctly handles limit and market entries, including inline SL attachment, `clientOrderId`, leverage/margin mode setup, and hedge-mode retry.

### OK-4: PhemexAdapter core methods
`fetch_ohlcv`, `fetch_ticker`, `fetch_balance`, `fetch_positions`, `set_leverage`, `set_margin_mode`, `set_position_mode_one_way` — all use standard CCXT unified API correctly.

### OK-5: WebSocket authentication
`hmac.new()` is valid Python 3. The HMAC-SHA256 token generation matches Phemex's documented auth spec.

### OK-6: Position Manager lifecycle
`PositionState` tracking, breakeven logic, trailing stop software monitoring, stagnation detection, and P&L calculations are all Phemex-agnostic and correctly implemented.

### OK-7: Lot-size rounding
`round_to_lot()` is applied to TP1 quantity and position sizing, preventing `TE_QTY_INVALID` rejections.

---

## Priority Fix Order

1. **C1 + C3** — Fix `place_stop_order()` first. This is the single most dangerous bug — positions have no reliable exchange-side stop protection after entry.
2. **C2** — Fix `place_trailing_stop_order()`. Without this, trailing stops are purely software-managed.
3. **H1** — Fix hedge-mode `posSide` parameter name. Quick one-liner.
4. **M2** — After C1 is fixed, resolve the duplicate-stop situation (inline SL + standalone stop).
5. **M3** — Fix startup reconcile to preserve protective stops on orphaned positions.
6. **H2** — Use exchange `side` field in reconcile instead of local state direction.
7. **H3/H4** — Decide whether stop/kill_switch should flatten positions on exchange.
8. **Everything else** — Medium and low items as time allows.
