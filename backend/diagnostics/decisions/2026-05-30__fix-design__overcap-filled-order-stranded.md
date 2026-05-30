# 2026-05-30 — FIX DESIGN (§15 live-execution): over-cap filled entry dropped → stranded unmonitored position

**Status:** DESIGN — awaiting operator decision (an architectural fork, below). NO CODE WRITTEN.
**Bug:** Hot-path audit #2 (1_BROKEN). See [[2026-05-29__hotpath-robustness-audit]].
**Boundary:** Live execution path (`live_trading_service.py`) → CLAUDE.md §15 design entry + approval before code.

---

## ROOT CAUSE (verified against HEAD)

`_get_active_positions` (`live_trading_service.py:1752-1792`) counts ONLY `position_manager.positions` with status OPEN/PARTIAL — it does **not** count `_pending_plans` (the in-flight limit entries). `_pending_plans` is populated at `:1352`, *after* an entry order is placed. Therefore:

- **Over-subscription (root):** the placement-time cap gate (`:1192-1194`, `active_count >= config.max_positions`) ignores pending orders. Between placing entry N and its fill, that pending order is invisible to the next signal's cap check, so the bot can place MORE pending limit entries than `max_positions`. When several fill, the later fills exceed cap.

- **Stranding site A — primary fill path (`:909-915`):**
  ```python
  order_done = fill or order.status == OrderStatus.FILLED
  if order_done and order.order_id in self._pending_plans:
      ...
      if active_count >= cap:
          executor.cancel_order(order.order_id)   # NO-OP on a FILLED order (returns False, live_executor.py:565)
          self._pending_plans.pop(order.order_id, None)
  ```
  The order has **already filled** (`order_done` is True). `cancel_order` on a filled order does nothing; the plan is popped. `open_position` / `_place_exchange_stop` never run → **real Phemex position with no PositionManager entry, no native stop/TP, no software exit.** Invisible to in-session reconcile (it scans `get_open_positions()`, which never held it). Only `_startup_reconcile` on next process restart adopts it.

- **Stranding site B — expiry path (`:974-999`):** an expired-but-FILLED order checks `if active_count < cap and entry_px > 0:` then opens; if over cap it falls through to the `pop` at `:998` **without adopting** → same stranding.

Note: site A had its inline entry SL placed at order submission? No — the exchange-native stop is only placed in `_place_exchange_stop`, which is skipped here. So the stranded position is genuinely naked.

## ARCHITECTURAL FORK (operator decision required)

The filled order is a **real position on the exchange** — it cannot be made to vanish. Two valid resolutions at fill time:

### Option A — ADOPT + MONITOR (recommended)
Open the position into PositionManager and place the exchange-native stop **regardless of cap**, with a loud over-cap warning + telemetry. Treat `max_positions` as a *placement-time* control, not a settlement-time one.
- **Pro:** never strands; the real position gets a stop + full software monitoring immediately. Safest for capital.
- **Con:** cap can be transiently exceeded by the number of simultaneously-in-flight fills. Bounded by Part 2 below.

### Option B — FORCE-FLAT
Fire a reduce-only market close to flatten the unwanted fill, honoring the cap strictly.
- **Pro:** strict cap adherence.
- **Con:** an unwanted round-trip (taker fees + slippage on entry *and* exit) on every over-cap fill; and the close itself can fail (the bug #1 class — now loud + retried, but until it succeeds the position is naked and unmonitored, so Option B must STILL fall back to adopt-on-close-failure). Strictly more fragile and more expensive than A.

**Recommendation: Option A.** Adopting a real position under monitoring strictly dominates leaving it naked, and B's force-flat reduces to A anyway whenever the close fails. Both stranding sites (A and B in root cause) get the same adopt treatment.

## PART 2 — pending-aware cap (recommended, addresses the root)
Count `len(self._pending_plans)` toward the cap at the placement gate (`:1193`) and the fill-time check (`:911`), so the bot stops over-subscribing in the first place. This bounds Option A's transient overage to (at most) the orders that fill within a single monitor tick.
- **Behavioral change (RISKY-tier):** slightly fewer concurrent in-flight entries — correct, since pending entries are committed capital. This touches signal-acceptance counting, so it is called out explicitly (Rubric 9). Operator may scope this in or defer it.

## PROPOSED CHANGE (pending decision)
- **Fill-time (both sites A + B):** replace the silent drop with the chosen resolution (A: adopt+stop+warn; B: reduce-only close with adopt-fallback). Factor the over-cap branch into a small helper so it is unit-testable without driving the whole `_monitor_loop`.
- **Placement-time (if Part 2 approved):** `active_count = len(self._get_active_positions()) + len(self._pending_plans)` at `:1192` and `:911` (or a dedicated `_committed_slot_count()` helper used in all three places for consistency).

## BLAST RADIUS (§20)
- **Upstream:** `_monitor_loop` (the two fill sites), `_process_signal` placement gate (`:1192`).
- **Downstream:** `position_manager.open_position`, `_place_exchange_stop`, `_log_activity("trade_opened")`, `stats.signals_taken`. Option B additionally: `_execute_exit_order` / executor reduce-only path.
- **Contract:** no API/telemetry-enum/DB/SniperContext schema change expected (internal loop logic). `_log_activity`/`_log_signal` reason strings may gain an "over_cap_adopted" value — additive, not a schema break. `capture_contracts diff` expected clean (modulo the unrelated replay drift).
- **Symmetry:** direction-agnostic (cap logic is not bull/bear specific); tests still cover LONG+SHORT entries for completeness.

## REGRESSION DIAGNOSTIC (same diff — §18)
Integration test with a fake executor + real PositionManager:
1. **Negative (the bug):** a pending limit order reports FILLED while `active_count >= cap` → assert the position IS adopted (`position_manager.get_open_positions()` contains it) and a stop was placed (Option A); OR a reduce-only close was issued (Option B). Must NOT silently vanish.
2. **Expiry site:** same assertion for the expired-but-filled-over-cap path.
3. **Part 2 (if approved):** with K pending orders and cap K, the next signal's placement gate rejects (counts pending) — assert `_log_signal(..., reason_type="max_positions")` fires and no new order is placed.
4. **Positive (no regression):** under cap, a filled order opens exactly as today.

## VERIFICATION PLAN
symmetry-guard N/A (no scoring/regime/SMC) · §16 14-point audit (live-execution → mandatory) · backend-integrity blast-radius + `capture_contracts diff` + `pipeline_smoke` · new integration test green.
