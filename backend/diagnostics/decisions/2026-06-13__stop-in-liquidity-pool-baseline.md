# 2026-06-13 — Stop-in-liquidity-pool: Phase 1 measure-first baseline

**Track:** EXIT/stop half of the loss problem (orthogonal to entry scoring).
**Thesis (operator, UNCONFIRMED):** stops placed inside / within ~0.3 ATR of known SMC
liquidity pools (PWL/PWH prior-week, PDH/PDL prior-day, EQH/EQL equal highs/lows) get
systematically swept — price reaches for the liquidity, hits the stop, then reverses the
intended way. risk_engine already has a 0.3-ATR liquidity buffer
(`_buffer_stop_from_liquidity`); the real question was whether that buffer is *sufficient*.

**Status:** Phase 1 (read-only measure) COMPLETE. **No stop logic changed.** Phase 2 is
GATED (§15 risk-guard, design-first).

Diagnostic: `backend/diagnostics/stop_in_pool_audit.py`
(`python -m backend.diagnostics.stop_in_pool_audit`).

---

## Method

- Source: `logs/paper_trading/session_*/trades.jsonl`, 48 sessions.
- Window: `entry_time >= 2026-06-01` (post-clamp era, avoids the wide-stop confound). **n = 123** closed trades.
- Buffer-fire detection: `stop_loss_rationale` contains `"Buffered 0.3 ATR from liquidity pool @ <level>"` — the only liquidity-pool datum that survives into stored data.
- Sweep = `exit_reason == "stop_loss"`. `session_stopped` (open at session end) is NOT a sweep.
- ATR reconstructed per trade as `|entry - stop| / stop_distance_atr`.
- Mass-conservation asserted in the diagnostic body (buffered + non == total; exit-reason counts == total).

---

## Findings

### 1. The buffer almost never engages — and never on longs
- Buffer fired on **6 / 123 (4.9%)** post-clamp trades.
- **All 6 are SHORT. 0 / 20 longs** buffered. (Book is short-skewed: 103 SHORT / 20 LONG.)

### 2. Sweep-rate cohort split is UNDERPOWERED — no verdict
| cohort | n | swept | sweep% | exit_reasons |
|---|---|---|---|---|
| BUFFERED | 6 | 2 | 33.3% | session_stopped 2, stop_loss 2, target 2 |
| NON-BUFFERED | 117 | 46 | 39.3% | stop_loss 46, target 24, session_stopped 38, stagnation 9 |

n(buffered)=6 is far below the n>=30 power floor (same floor that deferred the Phase-4
gate recal). The 33% vs 39% gap is noise. **The thesis cannot be confirmed or denied from
the buffer cohort.**

### 3. ROOT CAUSE of the 4.9% fire rate — a confirmed §15 risk-guard DEFECT (runtime-proven)
The buffer's static **PWL/PWH/PDH/PDL branch is dead code in production.**
`_buffer_stop_from_liquidity` (risk_engine.py:1898) does:
```python
lvl = getattr(key_levels, attr, None)            # attr in ("pwl","pdl") / ("pwh","pdh")
if lvl and isinstance(lvl, (int, float)) and ...
```
But the production `key_levels` is `SMCSnapshot.key_levels` (smc.py:482), typed
`Optional[dict]` = `KeyLevels.to_dict()`. `getattr(dict, "pwl")` -> **None**. And even a
raw `KeyLevels` dataclass would fail: `.pwl` is a `KeyLevel` *object*, so
`isinstance(lvl, (int, float))` is **False**. The diagnostic's reachability probe places a
PWL 0.1 ATR inside the 0.3-ATR window and confirms **neither the dict path nor the object
path moves the stop**. Only the `_find_eqh_eql_zones` (equal-high/low, from `multi_tf_data`)
scan can ever fire the buffer.

**Implication:** the prior-week / prior-day pools — the exact PWL sweep that founded this
investigation (PEPE/USDT 2026-05-24, `[[project-stop-placement-pwl-proximity]]`) — are
**never buffered at all.** The thesis assumed the buffer protects against PWL/PDH; it does
not. The correct dict access would be `key_levels["pwl"]["price"]` (keys: pwh/pwl/pdh/pdl,
each `{"price","swept"}` or None).

### 4. Even when the buffer fires, final stops sit < 0.3 ATR from the logged pool (flag, not verdict)
All 6 buffered trades' final stop sits **0.11–0.24 ATR** from the logged (EQH/EQL) pool,
inside the 0.3 ATR the buffer intends to enforce. Most likely an ATR-reconstruction
mismatch (reconstructed ATR != buffer-time ATR) and/or a downstream min-distance/cap clamp
re-tightening the stop after buffering (BNB row shows a `floored to 0.15% min distance`
note alongside the buffer note). **Flagged for Phase-2 trace; not concluded at n=6.**

---

## Data gaps (why the thesis is not fully testable from stored data)
1. **Full pool set at entry is persisted nowhere** — not in trades.jsonl, paper
   signals.jsonl, nor telemetry `signal_generated` (keys: confidence_score, direction,
   entry_price, pre_dir_tie_break, risk_reward_ratio, setup_type, symbol_regime_trend).
   So we cannot count stops sitting in pools the buffer *missed* (incl. the dead branch).
2. **Post-stop reversal is unmeasurable** — no durable OHLCV cache (`ohlcv_cache.py` is a
   TTL in-memory cache). Journal `max_favorable/max_adverse` are DURING-trade excursions
   only. "Swept then reversed the intended way" needs candle replay we do not have.
3. **n(buffered)=6 << 30** — no statistically valid sweep-rate comparison.

---

## Verdict
- **Thesis: NOT CONFIRMED** (underpowered + key data not stored). Do **not** widen/tune the
  0.3-ATR buffer on this evidence.
- **But a concrete defect surfaced:** the static PWL/PWH/PDH/PDL liquidity branch is inert.
  This is a §15 risk-guard correctness issue (a sophisticated-but-inert guard, exactly the
  failure mode CLAUDE.md §FUNDAMENTALS warns about), independent of whether 0.3 ATR is the
  right width.

## Recommended Phase 2 (design-first, GATED — not started)
Order matters; do not jump to width-tuning:
1. **Fix the dead static branch** (the genuine bug): dict access `key_levels["pwl"]["price"]`
   for pwl/pdl (long) and pwh/pdh (short), preserving bull/bear symmetry. This *enables* the
   PWL/PDH protection the thesis assumed already exists. Needs a design entry + symmetry-guard
   + §16 audit + a regression test proving the buffer fires on BOTH directions and respects
   the RR cap. Blast radius: `planner_service.py:330` (caller) -> `risk_engine` (logic) ->
   `position_manager.py:415` / paper journal (consumers of `stop_loss_level`).
2. **Instrument to make the thesis measurable** (read-additive, owned by the journal thread —
   NOT this thread): persist `key_levels` + nearest-same-side-pool distance (ATR) into the
   journal at entry. Without this, no Phase-2 width decision can ever be validated.
3. **Only after (1)+(2) and >=30 setups across >=2 regimes:** evaluate whether 0.3 ATR is
   sufficient or needs a capped widen (explicit RR-floor cap so stop distance / RR does not
   blow out). Re-run this diagnostic as the VERIFY gate — in-pool stop rate should drop, the
   swept cohort should shrink, RR must not collapse.

## Files (this entry)
- `backend/diagnostics/stop_in_pool_audit.py` — read-only diagnostic (new).
- No logic touched. risk_engine.py unchanged.
