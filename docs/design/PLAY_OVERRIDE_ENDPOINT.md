# Play override endpoint (design)

Status: proposed 2026-10-10, not implemented. Implements the "Editing a
bot-planned or open play" requirement in [PRODUCT.md](../../PRODUCT.md#editing-a-bot-planned-or-open-play)
for the [Play Inspector](../../src/components/hud/PlayInspector.tsx). Mechanics
cited here were read from source on 2026-10-10; re-read them before building.

## Goal

The operator can change a bot-planned play from the chart. If they touch
nothing, the bot executes exactly as planned.

| Play | Editable | Not editable |
|---|---|---|
| Pending entry (resting limit, plan in `_pending_plans[order_id]`) | entry price, stop, targets | side, symbol |
| Open position (`PositionState`) | stop, targets | entry, quantity, side |

Guardrails (identical for paper, testnet and live): risk within the session
budget and free margin; a stop always exists; LIVE requires explicit
confirmation; every override is journaled beside the bot's original plan.

## Constraints found in the current code

1. **No amend API.** The Phemex adapter and both executors only create and
   cancel orders. A pending-entry edit is cancel → confirmed → place new, which
   yields a new `order_id` and races with a fill of the old order.
   `LiveExecutor.cancel_order` can return unconfirmed, or flip a partially
   filled order to FILLED.
2. **Live entries carry an inline position stop.** `place_order(..., sl_price=)`
   sets Phemex `stopLossPrice`/`slTrigger=ByMarkPrice` on the entry
   (`live_executor.py`, `_place_order` extra params). Nothing updates it after
   the fill. If it persists as a position-level stop, widening a live stop is
   ineffective: the original inline stop still fires first.
3. **Native protection is place-new-then-cancel-old.**
   `LiveTradingService._ensure_exchange_stop`, driven by
   `_sync_exchange_stops` once a second, converges the native stop to
   `pos.stop_loss`. Retries are throttled to 5s. The native TP1 order and the
   native trailing stop are **not** resynced after open.
4. **Bot paths that can silently undo an edit:**
   - the scan replacing a pending plan (direction flip, or higher confluence
     in legacy mode);
   - pending TTL expiry;
   - breakeven and trailing, whose R geometry is anchored to
     `initial_stop_loss`;
   - wrong-side target stripping in `_check_targets_hit`.
5. **No shared mutation lock.** The monitor loop, the scan task and API
   handlers interleave at `await asyncio.to_thread(...)`. `PositionManager._lock`
   guards open/close, but not breakeven/trailing writes.
6. **Sizing differs by service.**
   - Paper `_calculate_position_size`: adapted risk %, regime multiplier, and a
     cap of 50% of free margin × leverage.
   - Live `_process_signal`: raw `risk_per_trade` plus `max_position_size_usd`,
     with no margin cap.

## API

Two routes per service (`/api/paper-trading/...` and `/api/live-trading/...`),
backed by one shared pure validator, `backend/bot/play_override.py`.

### `POST /api/{service}/plays/{kind}/{id}/preview`

Dry run. Returns exactly what an apply would do, using the service's own
sizer, exchange precision and current account evidence. The UI recomputes R:R
locally with `playMetrics` on every drag, and calls preview (debounced) for the
authoritative risk, size and any violations. Preview never mutates anything.

### `POST /api/{service}/plays/{kind}/{id}/override`

`kind` is `pending` or `position`; `id` is `order_id` or `position_id`.

```json
{
  "revision": "c41f…",
  "entry": 98.1,
  "stop": 95.2,
  "targets": [{ "level": 101.5, "percentage": 50 }, { "level": 103.9, "percentage": 50 }],
  "confirm_live": "I_CONFIRM_LIVE_OVERRIDE"
}
```

- `revision` is required: optimistic concurrency against the play's state.
- `entry` is only allowed for `kind=pending`.
- `confirm_live` is required on live and ignored on paper/testnet, mirroring
  the existing `I_ACCEPT_LIVE_TRADING_RISK` start gate.

Response:

```json
{
  "applied": true,
  "override_id": "ovr_…",
  "kind": "pending",
  "id": "LIVE_…_00000007",
  "previous_id": "LIVE_…_00000004",
  "revision": "9a20…",
  "quantity": 2.4,
  "risk": { "amount": 9.84, "budget": 10.0, "pct_of_equity": 0.98 },
  "protection": "converging",
  "bot_plan": { "entry": 98.1, "stop": 95.8, "targets": [101.5, 103.9] },
  "warnings": []
}
```

- `previous_id` is set when a pending edit re-placed the order.
- `protection` is reported for live positions: `synced` or `converging` until
  the native stop matches.

| Status | Meaning |
|---|---|
| 400 | Invalid levels: missing stop, stop or target on the wrong side, stop already breached by mark, target percentages over 100, precision rejected |
| 404 | No such pending entry or open position in this session |
| 409 | Stale `revision`; play busy (exit pending, stop replacement in flight, cancel unconfirmed); session not running or in recovery |
| 422 | Risk breach. Body carries `risk`, `budget`, `free_margin` and the limiting rule |
| 428 | Live confirmation missing |

`LifecycleConflict` maps to 409, as on start/stop. Nothing is clamped
silently: a breach is rejected with numbers, and the operator adjusts.

### Status payload additions

Each pending entry and open position in `get_status()` gains:
- `revision`: a hash of the levels, quantity and order state;
- `editable: { allowed, reasons[] }`, so the Inspector can disable editing
  with a visible reason;
- `override`: present only when edited, carrying `bot_plan` and `history`.

Pending entries already publish their plan through
[`pending_plan_view`](../../backend/bot/plan_view.py).

## Validation (shared, pure, direction-symmetric)

`validate_override(direction, current, proposed, quantity, account, budget) -> Result`:

- **Stop required.** It must be on the loss side of entry. On an open
  position, mark must not have crossed it (stopping out is "close", not "edit").
- **Targets** must be on the profit side, unique, ordered nearest-first, and
  their percentages must sum to at most 100% of the remaining quantity. Zero
  targets is allowed, with the existing NO TP warning.
- **Pending risk:** re-run the owning service's sizer with the edited entry
  and stop. Quantity comes from the budget, so risk ≤ budget by construction.
  Reject if quantity floors to zero or the margin cap binds below the minimum
  lot.
- **Open-position risk:** quantity is fixed.
  `remaining_qty × |entry − new_stop| ≤ equity × effective_risk_pct / 100`.
  Tightening is always allowed. Widening is allowed only within budget.
- **Precision:** apply `price_to_precision` to every level. Reject when rounding
  moves a level to the wrong side.
- **Pairs:** every rule gets a LONG and a SHORT test.

## Apply semantics

Each service gets `self._play_lock = asyncio.Lock()`. The override handler, the
monitor loop's pending-adoption section, `_sync_exchange_stops` and the scan's
pending-replacement path all acquire it. Edits are refused (409) while any of
these is set for the play:
- `exchange_close_pending`;
- `pending_exit_reason`;
- `pending_target`;
- an in-flight `_pending_stop_orders` entry;
- an `_pending_exit_orders` entry;
- the symbol is in `_exit_callbacks_active`.

### Pending entry

1. Validate, size and precision-round.
2. If only the stop or targets change (entry unchanged, quantity unchanged):
   mutate the stored plan in place.
   - Paper simulated: done.
   - Live/testnet: the resting order's inline SL still holds the old stop, so
     treat it as a re-place (step 3).
3. Re-place:
   - `cancel_order(old)` and wait for confirmation. The plan stays keyed to
     the old order until the cancel is confirmed.
   - If the old order filled or partly filled meanwhile, abort with 409
     `filled_before_edit`. The fill adopts the **bot's** plan, and the operator
     edits the position instead.
   - Otherwise place the new limit with the edited `sl_price`, and move the
     plan, `_pending_placed_at` and placed-price maps to the new key in one
     locked step.
4. Mark the plan operator-owned: `plan.metadata["override"] = {bot_plan, history}`.
   The scan must not replace an operator-owned plan.
   `PositionManager.open_position` copies `override` onto the position.

### Open position

1. Validate against fixed quantity.
2. Under `_play_lock` and `PositionManager._lock`, set `stop_loss` and
   `targets`, and append to `override_history`.
3. Paper simulated: done. The software monitor enforces it.
4. Live/testnet stop: `_sync_exchange_stops` converges the native stop. The
   response reports `converging` until `_exchange_stop_levels[pid]` equals the
   new stop.
5. Live targets: cancel the native TP1 order and native trailing stop
   (`_cancel_exchange_tp`, `_cancel_exchange_trailing`), then re-place them
   from the edited plan with a new helper. Until that helper exists, target
   edits on live are rejected with a clear reason.
6. **R anchor:** add `PositionState.r_anchor_stop`, used by breakeven,
   trailing and stagnation in place of `initial_stop_loss`. An override sets
   it to the new stop. `initial_stop_loss` keeps meaning "bot's original" for
   the journal.

## Journal

- **Activity event `play_override_applied`:** override id, kind, ids, account
  (PAPER/TESTNET/LIVE), `bot_plan`, previous and new levels, quantity and risk
  before/after, budget, live confirmation flag, timestamp.
- **Durable state:**
  - `PositionState.override_history: list` (paper `_save_state` uses `asdict`,
    so it must be a dataclass field);
  - `plan.metadata["override"]` for pending entries.
- **Completed trades:** add `bot_plan` (entry, stop, targets) and
  `operator_overrides` (list) to `CompletedTrade` and the trade journal row.
  Historical rows stay unchanged (fields absent means "unknown", not "none").
  This gives the bot-plan-vs-override comparison PRODUCT.md asks for, and the
  discipline signals the deferred rank system will need.

## Phasing

| Phase | Scope | Exchange calls | Blocker |
|---|---|---|---|
| A | Shared validator, preview route, status `revision`/`editable`, journal fields, `r_anchor_stop`. Paper simulated: open-position stop/target edits | None | None |
| B | Paper simulated pending-entry edits (in-place plus re-place); operator-owned plan exempt from scan replacement | None (paper executor) | TTL decision (below) |
| C | Testnet/live open-position **stop tightening** via existing native stop convergence | Native stop place/cancel | `_play_lock` around `_sync_exchange_stops` |
| D | Live/testnet pending re-place with confirmed cancel and fill-race abort | Cancel and place | Fill-race tests against a scripted transport |
| E | Live stop widening and target edits (TP1/trailing resync helper) | Cancel and place native TP/trail | **Verify on testnet whether the entry's inline `stopLossPrice` persists as a position stop and how to remove it** |

Frontend work (Inspector edit state, drag lines, preview call, ghost line of
the bot plan, risk meter) can land with phase A against the paper service.

## Verification plan

- Validator: LONG/SHORT pairs for every rule, precision edge cases, budget
  boundary (equal passes, epsilon over fails).
- Service: revision conflict, busy-state 409s, lock contention between the
  override and the monitor tick, an operator-owned plan surviving a scan, TTL
  behavior, `r_anchor_stop` driving breakeven/trailing after an edit.
- Live (scripted transport, as in `test_live_lifecycle.py`):
  - cancel unconfirmed → no re-place;
  - fill during cancel → abort and the bot plan is adopted;
  - native stop converges;
  - a live call without confirmation → 428.
- Guarded runner only; no real exchange calls.

## Open decisions (operator)

1. **TTL on edited pending entries:** keep the bot's expiry, or make
   operator-edited entries operator-owned with no TTL?
2. **Breakeven/trailing after a stop edit:** rebase on the new stop (proposed
   `r_anchor_stop`), or stop auto-management once the operator edits?
3. **Live stop widening** stays disabled until the inline-stop semantics are
   verified on testnet (phase E). Acceptable?

## Related defect found during research

`DELETE /api/paper-trading/orders/{order_id}` cancels through the executor but
does not remove `_pending_plans`, `_pending_placed_at` and related entries, and
does not journal the cancel. It also ignores the case where a partial fill was
flipped to FILLED during the cancel. Fix it before the Inspector's cancel action
uses it. There is no live equivalent route yet.
