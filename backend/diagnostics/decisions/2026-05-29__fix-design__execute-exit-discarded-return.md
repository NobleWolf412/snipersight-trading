# 2026-05-29 — FIX DESIGN (§15 live-execution): `_execute_exit` discards executor return → stranded position

**Status:** DESIGN — awaiting operator approval. NO CODE WRITTEN.
**Bug:** Hot-path audit #1 (1_BROKEN). See [[2026-05-29__hotpath-robustness-audit]].
**Boundary:** Touches the live execution path (`position_manager.py`) → CLAUDE.md §15 requires this documented design entry + approval before code.

---

## ROOT CAUSE (verified against HEAD, not the dirty-tree line numbers)

`PositionManager._execute_exit` (`position_manager.py:1354-1377`) and `_execute_partial_exit` (`1379-1397`):
```python
await executor(symbol=..., side=..., quantity=..., price=...)   # return DISCARDED
...
return True                                                      # always True unless exception
```
The function returns `True` on every path except a raised exception. But the `order_executor` providers **do not raise on a failed close — they return `False`:**

- **Live** `_execute_exit_order` (`live_trading_service.py:1474-1520`): returns `False` on `None` order (1492), on a REJECTED order where the position is *still open on the exchange* (1515), on a `None` fill (1517), and on exception (1520). It correctly returns `True` only on a confirmed fill, or on a benign rejection where the exchange shows the position already closed (native stop fired / liquidation, 1497-1512).
- **Paper** `_execute_exit_order` (`paper_trading_service.py:3577-3636`): returns `True` on fill, `False` on any failure. Its docstring (3583-3587) **explicitly states the position manager is supposed to check the return value** — the wrapper was hardened for exactly this, but the consumer was never updated.

`place_order` returns a REJECTED `Order` object (truthy) rather than raising (`live_executor.py:203/210/217/247/294/298/324/328`), so the live wrapper's `False` is real and reachable — and then thrown away by `_execute_exit`.

**Consequence:** on a rejected reduce-only close, `_execute_exit` returns `True` → `_monitor_position` settles the PositionState to `STOPPED_OUT`/`CLOSED`, zeroes `remaining_quantity`, drops it from monitoring. The exchange-native stop was already cancelled at `live_trading_service.py:1484` *before* the market exit. Net: **live Phemex position stays open, naked (no native stop), with no software monitoring** until `_startup_reconcile` on next process start. `_execute_partial_exit` books `realized_pnl` on a failed partial the same way.

## WHY THE FIX IS SMALL AND LOW-RISK
- All **four** call sites in `_monitor_position` already guard the bool: STOP_LOSS (621-623), MAX_HOURS_OPEN (662-664), TIME_STAGNATION (774-776), partial/target (823-825) — each does `if not success: return`. They are already built to retry next cycle on `False`.
- Both `order_executor` providers already return an accurate, consistent `bool`. This is **not a new contract** — it is an existing, documented contract the consumer fails to honor.
- The wrapper already does the "is it actually closed on the exchange?" verification, so propagating its bool preserves correct settlement of benign rejections (no false "stranded" on a position the native stop legitimately closed).

## PROPOSED FIX (for approval — not yet applied)
`position_manager.py`:
```python
async def _execute_exit(self, position, price, reason) -> bool:
    executor = self.order_executor
    if not executor:
        logger.warning("No order executor configured - simulating exit")
        return True
    try:
        order_side = "SELL" if position.direction == "LONG" else "BUY"
        ok = await executor(symbol=position.symbol, side=order_side,
                            quantity=position.remaining_quantity, price=price)
        if not ok:
            logger.error(                       # LOUD failure (§11) — exit did not confirm
                f"Exit NOT confirmed for {position.position_id} | {reason} | "
                f"executor returned falsy; position left OPEN for retry"
            )
            return False
        logger.info(f"Exit executed: {position.position_id} | {reason} | "
                    f"Qty: {position.remaining_quantity} @ {price}")
        return True
    except Exception as e:
        logger.error(f"Failed to execute exit for {position.position_id}: {e}")
        return False
```
Identical shape for `_execute_partial_exit` (capture `ok`, loud-log + `return False` when falsy).
- Keep the `if not executor: return True` simulation branch (tests / no-executor) unchanged.
- Add a one-line docstring note to both: order_executor contract = `async (symbol, side, quantity, price) -> truthy on confirmed fill, falsy on failure`.
- **Net diff: ~10 lines across 2 functions, 1 file.** No caller changes (they already guard).

## BLAST RADIUS (§20)
- **Upstream callers of `_execute_exit` / `_execute_partial_exit`:** only `_monitor_position` (4 sites, all guard the bool). grep-confirmed no other callers.
- **`order_executor` providers (downstream of the contract):** live `_execute_exit_order` (bool ✓), paper `_execute_exit_order` (bool ✓). Both conform; no provider change needed.
- **Behavior change:** the ONLY change is that a falsy executor return now blocks settlement (the documented-intended behavior) instead of being ignored. On success paths, behavior is identical to today.
- **Contract diff:** no API/telemetry/DB/pipeline schema touched → `capture_contracts diff` expected clean. (Will run to confirm.)

## REGRESSION DIAGNOSTIC (lands in the SAME diff — §18)
New `position_manager` unit test(s):
1. **Negative (full exit):** stub `order_executor` returns `False` on a STOP_LOSS path → assert PositionState NOT settled (status stays OPEN, `remaining_quantity` unchanged) AND still in `get_open_positions()`.
2. **Negative (partial):** stub returns `False` on a target hit → assert `realized_pnl` NOT booked and `remaining_quantity` NOT reduced; target stays active.
3. **Positive (no regression):** stub returns `True` → assert position settles exactly as today (STOPPED_OUT/CLOSED, qty 0, removed from open).
4. **Symmetry:** run negative+positive for BOTH `LONG` and `SHORT` (direction-aware exit side).

## OPEN SUB-DECISION FOR OPERATOR
- The `logger.error` loud-failure line on a non-confirmed exit (above) is a small scope add beyond the literal one-line return fix — included because a silently-failing exit retrying forever with no log is itself a §11 diagnosability gap. **Approve the loud log, or keep the fix to the bare return propagation?**
- A repeated-failure escalation (telemetry event / alert after N failed exit attempts on the same position) is a **separate follow-up**, not in this diff. Flagged, not bundled.

## VERIFICATION PLAN (post-code, before commit)
symmetry-guard N/A (no scoring/regime/SMC) · §16 audit subagent (live-execution change → mandatory) · backend-integrity blast-radius + `capture_contracts diff` + `pipeline_smoke` · new unit tests green.
