# 2026-06-13 — Phase 2 design: revive the dead PWL/PWH/PDH/PDL liquidity-buffer branch

**Gate:** §15 HARD BOUNDARY (stop placement = risk guard on the shared paper/live path).
Design-first, recorded BEFORE code. Baseline: `2026-06-13__stop-in-liquidity-pool-baseline.md`.

## Problem (confirmed in Phase 1, runtime-proven)
`_buffer_stop_from_liquidity` (risk_engine.py:1898) intends to buffer stops away from
static prior-week/prior-day pools, but its branch reads `getattr(key_levels, "pwl")` while
the production `key_levels` is a **dict** (`SMCSnapshot.key_levels = KeyLevels.to_dict()`,
smc.py:482). `getattr(dict, "pwl")` -> None, so the branch contributes **zero** pools. A raw
`KeyLevels` dataclass also fails (`.pwl` is a `KeyLevel` object, not a float, rejected by the
`isinstance(lvl,(int,float))` guard). Net: PWL/PWH/PDH/PDL are **never buffered** — only the
EQH/EQL `_find_eqh_eql_zones` scan fires. This is a silently-inert risk guard.

## Goal (surgical — fix the bug, do NOT tune width or add features)
Make the static branch read pool prices from BOTH representations (dict + dataclass), so the
guard does what its code/comment already claims. **No change** to: the 0.3-ATR buffer width,
the EQH/EQL path, the planner integration, the downstream pct-stop cap, or trade selection
beyond pools now correctly entering the existing buffer logic.

## Change (single function, risk_engine.py)
Add a private `_pool_price(key_levels, attr) -> Optional[float]` helper that resolves a pool
price from either:
- dict form: `key_levels[attr]["price"]` (to_dict shape `{"price","swept"}|None`), tolerating a
  flat `{attr: float}` too;
- object form: `getattr(key_levels, attr).price`, or a raw float.
Returns None on anything malformed (loud-failure-resistant — cannot silently die again).

Replace the static-branch body to call `_pool_price`; the long/short structure, the
`< entry_ref` / `> entry_ref` side guards, and the `0.3*atr` push are **unchanged** (mirror
symmetry preserved). Add a one-line WARNING if `key_levels` is present but yields no parseable
pools for a side where it structurally should (observability; not a failure).

Scope note (deliberately OUT): `swept` flag filtering. A swept pool is arguably spent
liquidity, but the original intent ignored `swept` and the EQH/EQL path does too — filtering
would be a new behavior. Logged here as a future consideration, not done now.

## Symmetry (standing fix — hard gate)
LONG buffers off `pwl`/`pdl` (below entry), SHORT off `pwh`/`pdh` (above entry); both via the
same `_pool_price` helper and the same `±0.3*atr` push. Regression test exercises BOTH and
asserts mirror behavior.

## Bounded / RR safety (why this can't blow out RR)
- The buffer pushes the stop to exactly `pool ∓ 0.3*atr` — **bounded** (0.3 ATR beyond the
  nearest in-window pool), never unbounded.
- Integration (planner_service.py:326-358) runs the buffer BEFORE the percentage-stop cap
  (scalp 3% / intraday 5% / swing 10%, :370-377). A buffered stop exceeding the cap is
  **rejected**, not silently accepted (existing valve, comment :327-328). Degenerate-stop
  guard at :341 still applies. So newly-eligible pools either widen the stop within cap or get
  the trade rejected — no RR blow-out path.

## Blast radius
- Upstream caller: `planner_service.generate_trade_plan` :331 (only caller of the buffer).
- Downstream of `stop_loss.level`: `position_manager.py:415` (SL order), paper journal
  (`paper_trading_service.py` — NOT edited; consumes the value only), replay/signal_transform.
- Behavior delta: some trades (mostly SHORT, given the 103/20 book) that previously had a
  PWL/PDH pool near the stop will now widen 0.3 ATR beyond it OR be rejected by the pct cap.
  Magnitude is **not predictable from stored data** (key_levels not persisted) — see VERIFY.
- Contracts: no API/telemetry/DB/pipeline schema touched -> `capture_contracts diff` expected
  clean.

## Tests (regression, backend/tests/unit/test_liquidity_buffer_symmetry.py)
1. LONG dict-form: pwl 0.1 ATR below stop -> stop moves to `pwl - 0.3*atr` (the bug case).
2. SHORT dict-form: pwh 0.1 ATR above stop -> stop moves to `pwh + 0.3*atr` (mirror).
3. Object-form KeyLevels also fires (both dirs) — robust to representation.
4. Bounded: push is exactly 0.3 ATR beyond the pool (not unbounded).
5. Negative: pool > 0.3 ATR away -> stop unchanged (no false fire).
6. Negative: key_levels None / empty / malformed -> stop unchanged, no raise.

## VERIFY (cannot fully close without instrumentation — flagged)
Re-run `stop_in_pool_audit.py` on the NEXT paper session (after a hard backend restart):
the reachability probe must flip to "static branch LIVE", and buffer-fire rate should rise
above 4.9% with longs now able to buffer. True sweep-reduction VERIFY remains BLOCKED until
the journal thread persists `key_levels` + nearest-pool distance at entry (read-additive;
owned by the paper_trading_service thread, NOT this one). Requested separately.

## Audit gates before commit
symmetry-guard (risk path) + §16 14-point + backend-integrity (blast radius + contract diff),
all pasted verbatim.
