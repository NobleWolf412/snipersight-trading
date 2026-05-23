# Phemex Integration Debug Report
**Date:** 2026-05-04
**Scope:** Phemex send/receive, order placement, stop/TP logic, active trades UI data flow

---

## Executive Summary

The OHLCV pipeline and authentication are solid. The active trades UI (BotStatus page) is correctly wired to the right data. But there are **two critical bugs** that silently break every exchange-native stop order the bot tries to place — meaning Phemex never has a real stop protecting your positions — plus several secondary issues affecting data accuracy.

---

## BUG 1 — CRITICAL: Stop Orders Are Sent With Wrong CCXT Params

**File:** `backend/bot/executor/live_executor.py` — `place_stop_order()` (~line 619)

### What is broken

Three separate problems combine to make every exchange stop order fail silently:

**Problem A — Wrong order type string**

```python
# Current:
exchange_order = self._adapter.create_order(
    order_type="stop_market",   # CCXT capitalize() turns this into 'Stop_market'
    ...
)
```

Phemex only accepts `Stop`, `StopLimit`, `MarketIfTouched`, `LimitIfTouched` as ordType values. `Stop_market` is not valid and gets rejected. CCXT's own `create_stop_market_order()` helper internally calls `create_order()` with type `'market'` — that is the intended path for this.

**Problem B — Trigger price is in the wrong argument**

```python
# Current:
price=stop_price,           # CCXT Phemex ignores this for trigger detection
params={"reduceOnly": True} # no stopPrice key here
```

CCXT's Phemex implementation (line 2621 of `ccxt/phemex.py`) reads the trigger price only from `params['stopPx']`, `params['stopPrice']`, or `params['triggerPrice']`. It does not read it from the `price` positional argument. Because `params` has no stop price key, `triggerPrice` resolves to `None`, and no `stopPxRp` ever gets sent to Phemex.

**Problem C — Missing required `triggerDirection`**

When `triggerPrice` IS set in params, CCXT Phemex (line 2682) raises `ArgumentsRequired` unless `params['triggerDirection']` is also provided (`'ascending'` or `'descending'`). The bot never provides this.

### What actually happens

All three problems combine so the order fails. The `except Exception` block in `place_stop_order()` catches the error and logs:

```
Exchange stop placement failed for {symbol} — software monitoring remains active.
```

Software monitoring keeps running so positions are not totally unprotected while the server is alive. But **if your process dies, restarts, or loses connectivity, there is zero stop protection sitting on Phemex**. The exchange-native stop — your last line of defense — never got placed.

### The fix

```python
# In live_executor.py, place_stop_order() — replace the create_order call:

# SELL stop closes a LONG (triggers when price falls) → descending
# BUY  stop closes a SHORT (triggers when price rises) → ascending
trigger_dir = "descending" if side.upper() == "SELL" else "ascending"

stop_params: dict = {
    "reduceOnly": True,
    "stopPrice": stop_price,         # CCXT reads trigger from params, not price arg
    "triggerDirection": trigger_dir, # Required by CCXT Phemex — without this it throws
}
if self._hedge_mode:
    stop_params["positionSide"] = "Long" if side.upper() == "SELL" else "Short"

exchange_order = self._adapter.create_order(
    symbol=symbol,
    order_type="market",   # Must be 'market', not 'stop_market'
    side=side.lower(),
    amount=quantity,
    price=None,            # None for market — trigger is in params
    params=stop_params,
)
```

---

## BUG 2 — CRITICAL: Trailing Stop Updates Also Broken

**File:** `backend/bot/live_trading_service.py` — `_sync_exchange_stops()` (~line 1185)

`_sync_exchange_stops()` calls `self.executor.place_stop_order()` every time the position manager moves a trailing stop. Since `place_stop_order()` is broken (Bug 1), every trailing stop update also silently fails. The stop on Phemex — if it somehow got placed initially — never moves with the trailing stop. It sits at the original price forever, or more accurately, it was never placed at all.

**Fix:** Automatically resolved once Bug 1 is fixed — `_sync_exchange_stops` calls the same method.

---

## BUG 3 — MEDIUM: Stop Update Window Has No Exchange Protection

**File:** `backend/bot/live_trading_service.py` — `_sync_exchange_stops()` (~line 1177)

When a trailing stop level changes, the sequence is:

1. Cancel the old exchange stop order
2. Place the new exchange stop order

Between steps 1 and 2 there is a brief window (network round-trip, ~100–500ms) where no exchange-side stop exists. A server crash or network failure in this window means no protection.

**Fix — reverse the order, place new first:**

```python
# Place new stop first
order = self.executor.place_stop_order(
    symbol=pos.symbol,
    side=stop_side,
    quantity=qty,
    stop_price=current_stop,
)
# Only after new stop is confirmed, cancel the old one
if order.status.value != "REJECTED":
    if old_order_id:
        try:
            self.executor.cancel_order(old_order_id)
        except Exception as e:
            logger.warning(f"Could not cancel old exchange stop {old_order_id}: {e}")
    self._exchange_stop_orders[pid] = order.order_id
    self._exchange_stop_levels[pid] = current_stop
```

Phemex allows multiple open stop orders per position. A brief overlap of two stops is far safer than a brief gap with none.

---

## BUG 4 — MEDIUM: `reconcile_positions` Doesn't Sync Average Entry Price

**File:** `backend/bot/executor/live_executor.py` — `reconcile_positions()` (~line 720)

```python
# Current — syncs quantity but NOT avg entry price:
self._positions[symbol] = ex_qty if local_qty >= 0 else -ex_qty
# _position_avg_price[symbol] stays at whatever it was (or 0.0 on fresh start)
```

If the bot restarts and `reconcile_positions()` fires, the quantity gets synced from Phemex but `_position_avg_price[symbol]` stays at `0.0`. Equity and unrealized PnL calculations then use `avg=0.0`, computing wildly wrong values. This can trigger spurious risk rejections on the next order placement (position size cap calculates against $0 entry).

**Fix — pull entry price from the exchange position data during reconcile:**

```python
entry_px = float(pos.get("entryPrice", 0.0) or 0.0)
if entry_px > 0 and ex_qty > 1e-9:
    self._position_avg_price[symbol] = entry_px
```

---

## BUG 5 — MEDIUM: TP1 Quantity Not Rounded to Lot Size

**File:** `backend/bot/live_trading_service.py` — `_place_exchange_stop()` (~line 1146)

```python
tp1_qty = round((tp1.percentage / 100.0) * quantity, 8)  # arbitrary 8 decimal places
```

Entry orders correctly use `round_to_lot(quantity, lot_size)`. TP1 quantity does not. For symbols with lot sizes like `0.001` (BTC/USDT:USDT), a quantity like `0.00312847` will be rejected by Phemex with an invalid quantity error.

**Fix:**

```python
market_info = self._adapter.get_market_info(plan.symbol) if self._adapter else {}
lot_size = market_info.get("lot_size", 0.0)
tp1_qty = round((tp1.percentage / 100.0) * quantity, 8)
if lot_size > 0:
    tp1_qty = round_to_lot(tp1_qty, lot_size)
```

(`round_to_lot` is already imported at the top of `live_trading_service.py`.)

---

## BUG 6 — LOW: `PositionsPanel.tsx` Calls Wrong Endpoint

**File:** `src/components/bot/PositionsPanel.tsx`

`PositionsPanel` calls `api.getPositions()` which hits `/api/bot/positions` — the legacy paper executor endpoint that always returns zeroed-out data (`entry_price=0`, `pnl=0`, `opened_at=now()`).

**Current status:** This component is not imported or mounted anywhere in the app right now, so it doesn't affect the live UI. The `BotStatus.tsx` page correctly uses `liveTradingService.getStatus()` → `/api/live-trading/status` and gets real position data.

**Fix (if this component gets used):** Change the fetch to `liveTradingService.getStatus()` and read `status.positions`, or change the URL to `/api/live-trading/positions`.

---

## What IS Working Correctly

```
BotStatus.tsx
  └── liveTradingService.getStatus()
        └── GET /api/live-trading/status          ✅ correct endpoint
              └── LiveTradingService.get_status()
                    ├── _get_active_positions()    ✅ real entry/pnl/sl/tp1/tp2 data
                    ├── balance from executor      ✅ reconciled from Phemex
                    ├── pending_orders             ✅ real pending limit orders
                    └── statistics                 ✅ accurate trade stats

LiveTradingService._monitor_loop()
  ├── _refresh_price_cache()            ✅ fetches live price per open symbol
  ├── executor.execute_limit_order()    ✅ polls fills via fetch_order
  ├── check_fill_via_positions()        ✅ secondary confirmation via fetch_positions
  ├── position_manager.open_position()  ✅ opens position after confirmed fill
  ├── _place_exchange_stop()            ❌ BROKEN — wrong CCXT params
  ├── _sync_exchange_stops()            ❌ BROKEN — same root cause as above
  └── _sync_closed_positions()          ✅ correctly archives completed trades

PhemexAdapter
  ├── fetch_ohlcv()       ✅ CCXT primary + direct REST fallback
  ├── create_order()      ✅ works for entry and TP limit orders
  ├── fetch_order()       ✅ used for fill polling
  ├── fetch_positions()   ✅ used for fill confirmation and reconcile
  └── fetch_balance()     ✅ used for balance reconcile
```

---

## Priority Fix Order

1. **Fix `place_stop_order()` in `live_executor.py`** — change `order_type` to `'market'`, move `stop_price` into `params['stopPrice']`, add `params['triggerDirection']`. Single change fixes stop placement AND all trailing stop updates simultaneously.

2. **Fix `reconcile_positions()` entry price sync** — add entry price pull from exchange position data during reconcile to prevent $0 avg price after restart.

3. **Reverse stop-update order in `_sync_exchange_stops`** — place new before cancelling old to eliminate the protection gap window.

4. **Fix TP1 lot-size rounding** — apply `round_to_lot` to `tp1_qty` before placing the TP order.

5. **Clean up or redirect** `/api/bot/positions` so it doesn't return zeroed garbage if ever hit.
