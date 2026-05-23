# SniperSight — Bot Page UI Audit

**Date:** 2026-05-05
**Scope:** All frontend files for the live trading bot UI, cross-referenced against backend status schema
**Files audited:** `BotStatus.tsx`, `BotSetup.tsx`, `PositionsPanel.tsx`, `GauntletBreakdown.tsx`, `WatchlistRadar.tsx`, `liveTradingService.ts`

---

## Integration Status: SOLID

The core data flow is correctly wired:

- `BotStatus.tsx` polls `liveTradingService.getStatus()` every **10 seconds** — good cadence
- Trade history loaded via `liveTradingService.getHistory(50)` on the same interval
- `LivePosition` interface matches the backend `_get_active_positions()` schema exactly
- `LiveTradingStatus` interface matches `get_status()` return schema
- `CompletedLiveTrade` interface matches `CompletedTrade.to_dict()` output
- All API endpoints (`/api/live-trading/status`, `/start`, `/stop`, `/kill-switch`, `/reset`, `/history`, `/preflight`, `/analyze-session`) are correctly mapped
- `BotSetup.tsx` runs preflight, checks if bot is already running (redirects to status), and correctly builds the config request

---

## Issues Found

### I1: `PositionsPanel.tsx` is dead code — never imported anywhere

The component exists at `src/components/bot/PositionsPanel.tsx` with its own 5-second poll loop against `getStatus()`, but it's never used. `BotStatus.tsx` has its own inline `PositionCard` component that renders positions directly from the shared status poll.

**Impact:** Dead code bloat. Two position-fetching implementations to maintain. The standalone `PositionsPanel` also has a simpler design (no progress bar, no R-multiple, no chart modal, no scale ladder) which could confuse future devs.

**Fix:** Delete `PositionsPanel.tsx` or repurpose it as a lightweight widget for other pages (e.g., a dashboard sidebar).

---

### I2: `WatchlistRadar.tsx` is dead code — never imported anywhere

Fully built component (247+ lines) showing per-symbol setup health (READY/DEVELOPING/WATCHING/NOISE states, convergence scores, veto status). It's designed to consume `status.signal_log` and `status.config.symbols` but is never rendered on the BotStatus page.

**Impact:** This is actually a useful component that would add real value to the bot dashboard. It gives visibility into what the scanner is seeing across the watchlist — which pairs are building toward setups vs. pure noise.

**Fix:** Import and render it on BotStatus, likely between the Active Positions section and Trade History:
```tsx
import { WatchlistRadar } from '@/components/bot/WatchlistRadar';
// ... inside the status render:
{status && <WatchlistRadar status={status} />}
```

---

### I3: 10-second poll interval with no fast-poll on position change

The status poll runs every 10 seconds unconditionally. When a position opens, the SL moves, or a fill occurs, the user has to wait up to 10 seconds to see the update.

**Fix:** Add a fast-poll mode that drops to 2-second intervals when positions are active or a scan is running, then reverts to 10 seconds when idle:
```tsx
const pollInterval = (status?.positions?.length || status?.pending_orders?.length ||
                      status?.current_scan?.status === 'running') ? 2000 : 10000;
```

---

### I4: "Phantom Scale Ladder" is hardcoded placeholder

The scale ladder in `PositionCard` (lines 317–329) shows static "Fill: 100% (L1)" with fixed 3 segments. It doesn't reflect actual partial exits or scale levels. If a position has hit TP1 and the remaining quantity is 60%, this still shows 100%.

**Fix:** Derive scale state from `position.targets_hit` and `position.targets_remaining`:
```tsx
const totalTargets = (position.targets_hit ?? 0) + (position.targets_remaining ?? 0);
const filled = position.targets_hit ?? 0;
```
Then render each segment as filled/unfilled based on actual target hits.

---

### I5: TP1 fallback calculation can mislead

Line 192: `const tp1 = position.tp1 ?? (isLong ? entry * 1.015 : entry * 0.985);`

When the backend doesn't send `tp1`, the UI fabricates a 1.5% target. This fake TP1 is used in the progress bar calculation and the chart level modal, making it look like the system placed a target when it didn't.

**Fix:** Use `null` when `tp1` is missing and adjust the progress bar to work without TP:
```tsx
const tp1 = position.tp1 ?? null;
// Only show TP in chart levels if it's real
...(tp1 !== null ? [{ label: 'TP1', price: tp1, ... }] : []),
```

---

### I6: Session P&L is computed from trade history, not from `balance.pnl`

Lines 854–855: `const pnl = trades.reduce((s, t) => s + t.pnl, 0)` — the hero P&L number is summed from the `trades` array fetched via `/history`. But the backend already computes `balance.pnl` which includes unrealized P&L.

The `trades` array only contains completed (closed) trades. During an active session with open positions, the hero P&L will show $0 even if you're up $50 unrealized. The "BALANCE" section in the Performance card does show `balance.pnl` correctly, but the big hero number is misleading during active trading.

**Fix:** Show `balance.pnl` as the primary P&L (including unrealized), and show `trades.reduce(...)` as "Realized P&L" separately:
```tsx
const totalPnl = balance?.pnl ?? 0;  // includes unrealized
const realizedPnl = trades.reduce((s, t) => s + t.pnl, 0);
```

---

### I7: No leverage display on position cards

The backend tracks `target_leverage` on the executor, but the position cards don't show it. For a leveraged perp trade, knowing you're running 3x or 5x is critical context.

**Fix:** Add leverage to the `LivePosition` interface and display it as a badge next to the trade type:
- Backend: Add `leverage` to the dict returned by `_get_active_positions()`
- Frontend: Show as `<Badge>3×</Badge>` next to the trade type pill

---

### I8: No time-in-trade on position cards

The `opened_at` field is available in `LivePosition` but isn't rendered on the `PositionCard` component. The standalone `PositionsPanel.tsx` (dead code) uses `formatDistanceToNow(position.opened_at)`, but the live `PositionCard` in BotStatus doesn't show it.

**Fix:** Add a small timer display using `opened_at`:
```tsx
const openedAgo = formatDistanceToNow(new Date(position.opened_at), { addSuffix: true });
// Show as: "12m ago" or "2h 15m"
```

---

### I9: Kill switch says "close all positions at market price" but doesn't

Line 718: The UI promises "Immediately cancel all orders and close all positions at market price." But as noted in the Phemex audit (H3/H4), the backend's `kill_switch()` only cancels open orders and marks positions closed in software — it does NOT send market exit orders to the exchange.

**Fix:** Either fix the backend kill switch to actually flatten positions (recommended), or update the UI copy to be accurate: "Cancel all orders and stop monitoring. Exchange-native stops remain active."

---

### I10: `max_adverse` displayed with wrong sign

Line 464: `<span className="text-red-400/80">{formatPct(trade.max_adverse)}</span>` — `formatPct` prepends `+` for positive values, so MAE (which is always positive) shows as "+2.30%" in red, which reads like a positive number. MAE should display as "-2.30%" since it represents drawdown.

**Fix:**
```tsx
<span className="text-red-400/80">-{trade.max_adverse.toFixed(2)}%</span>
```

---

### I11: Connection error threshold too aggressive

Line 516: `if (fetchFailCount.current >= 3) setConnectionError(...)` — at a 10-second poll interval, 3 failures = 30 seconds of downtime shows the error. For a bot trading real money, the user should know sooner.

**Fix:** Reduce to 2 failures (20 seconds) and add a visual indicator on the first failure (e.g., subtle yellow pulse on the status orb).

---

## Improvements Worth Building

### P1: WebSocket for real-time UI updates

Currently the UI polls every 10 seconds. The backend already has a WebSocket feed for Phemex order events. Adding a frontend WebSocket connection (or SSE stream) from the backend would give instant position updates, fill notifications, and stop triggers without polling lag.

### P2: Per-position expandable detail view

The position card shows summary data. Clicking it opens a chart modal with price levels. Add an expanded view that shows the full trade thesis — confluence score, which SMC factors fired, regime at entry, time in trade, and a mini candlestick chart (via TradingView widget or lightweight chart library).

### P3: Sound/notification alerts

For a live trading bot, the user should get browser notifications (or audio alerts) on key events: position opened, target hit, stop triggered, kill switch activated, scan completed with a signal. The `recent_activity` data is already there — just needs a notification layer on top.

### P4: Quick manual exit button per position

Add a "Close" button on each position card that sends a market exit order via a new `/api/live-trading/close-position` endpoint. Currently the only way to manually exit is the kill switch (closes everything) or going directly to Phemex.

### P5: Integrate the WatchlistRadar

As noted in I2 — the component is fully built and would add significant value. It shows what the scanner sees across all watchlist pairs in real time. This is the kind of situational awareness that makes SniperSight's UI actually useful during live trading, not just a passive monitor.

### P6: Equity curve with real-time unrealized overlay

The current `EquitySparkline` only plots realized trade P&L. Overlay the current unrealized equity as a dotted extension of the line, updating on each poll. This gives an instant read on whether the session is trending up or down in real time, not just after trades close.

### P7: Mobile responsiveness audit

The grid layouts use `grid-cols-2 sm:grid-cols-4` and `lg:grid-cols-2` which is reasonable, but the position cards have small text (`text-[9px]`, `text-[10px]`) that's hard to read on mobile. The config pills overflow horizontally. Worth a pass on a phone viewport.
