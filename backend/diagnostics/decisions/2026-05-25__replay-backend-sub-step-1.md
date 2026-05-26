# Replay feature — backend sub-step 1 (engine + orchestrator hooks)

## Headline
Added scanner-only candle-by-candle replay engine without forking `_process_symbol`. Used a `replay_mode` flag + capture hook pattern instead of the literal duplication the original plan proposed.

## Context
Plan file: `~/.claude/plans/theres-a-feature-called-staged-teapot.md`. The approved plan proposed forking `_process_symbol` into `_process_symbol_for_replay` to isolate the replay path from the live scan hot path. On reading the actual code, `_process_symbol` is ~1300 lines with ~12 early-return sites — literal duplication would have been a maintenance disaster and violated §13 ("targeted diffs, no scope creep").

## Resolution
Three surgical edits to `backend/engine/orchestrator.py` instead of a fork:

1. **Constructor flag** — `replay_mode: bool = False` kwarg, exposed via a read-only `@property` backed by name-mangled `__replay_mode` (sticky for instance lifetime, symmetry-guard SCOPE-SUSPECT fix).
2. **Capture hook** at L1146 (right after `SniperContext` is created) — when `self.replay_mode`, stash the context reference on `self._last_replay_context` and stamp `playback_index` + `replay_session_id` into `context.metadata` so every early-return path is auto-instrumented.
3. **Cooldown skip** at L1268 — wrap the early-cooldown loop in `if not self.replay_mode:`. Cooldown is a live-trading concept; in historical replay every bar must run regardless of whether a hypothetical trade fired earlier.

Plus a new public method `process_symbol_for_replay()` at L2557 that wires the regime detector to sliced BTC data (keep-last-good policy — symmetry-guard FIX-02 fix), runs the pipeline, and returns the captured context alongside the existing `(plan, rejection)` tuple.

Replay engine: `backend/engine/replay_engine.py` (NEW). Pre-fetches multi-TF window + BTC. Slices each TF using bar-close semantics (`bar_open + tf_seconds <= current_ts`) — the audit's #1 concern was that bar-open semantics would silently break bull/bear symmetry on flip bars. Mass-conservation assert (`len(sliced) == int(mask.sum())`) and bar-close invariant assert (`retained_close <= current_ts`) run on every slice to catch silent row loss + mask drift at runtime.

Diagnostic: `backend/diagnostics/replay_diagnostic.py` (NEW). 9 end-to-end checks including paired negatives (the bar 1s before close MUST be excluded; the active session MUST survive GC).

## Why it matters next time

**Bar-close slicing semantics is non-negotiable.** Bar-open slicing leaks not-yet-closed bar data into indicators. On a flip bar (price crosses RSI 50 or MACD signal mid-bar), the bullish path reads the cross using leaked data, the bearish path doesn't — asymmetric scoring without any error. The negative slice test in the diagnostic (`check_slicing_boundary_negative`) is the only thing standing between a future refactor and that bug.

**`_process_symbol` is the wrong size to fork.** 1300 lines, 12 early returns, scattered telemetry side effects. Future replay-adjacent features (e.g. "what-if regime override") should follow the same pattern: instance flag + capture hook at context creation, surgical guards on side-effect-heavy gates, dedicated per-session orchestrator. NEVER duplicate the function body.

**Replay orchestrator must be its own instance.** The process-pool worker at `orchestrator.py:4626` caches `_WORKER_ORCHESTRATOR` at module level and reuses it across symbols. A `replay_mode=True` orchestrator there would race the `_last_replay_context` / `_next_replay_*` capture state across parallel symbol scans. The dedicated per-session orchestrator in `replay_engine.py::_build_orchestrator` sidesteps this. Comment landed at the worker site explicitly forbidding `replay_mode=True` there.

**Mass-conservation asserts must be non-tautological.** Audit round 2 caught a `mask.sum() + (~mask).sum() == N` assert that's trivially true for any boolean mask. Real invariants: `len(downstream_output) == int(mask.sum())` (catches indexing drift) and a re-derivation assert on the output that proves the original filter condition still holds.

**Verbatim-paste rule fires for clean passes too** (calibrated on 3z.h, per `2026-05-21__verbatim-paste-rule.md`). This sub-step paste-dumped 3 subagent reports verbatim in the message body even though backend-integrity returned CLEAN and round 3 of the audit returned 14/14 ✅. Don't summarize subagent output even when it's good news.

## Subagent results (summarized for indexing — full output is in the conversation transcript)

- **§16 audit round 1:** 9 ✅ / 5 🟡. Open items: six-concern table, mass-conservation assert, negative tests, bull/bear rationale, blast-radius paste, _serialize_smc silent catch.
- **symmetry-guard:** PASS. 4 SUSPECT items: macro_context not per-step in replay, regime flicker, capture-hook silent, replay_mode not sticky.
- **backend-integrity:** CLEAN. Contracts + pipeline smoke 0 changes.
- **§16 audit round 2:** 13 ✅ / 1 🟡 (mass-conservation assert tautological — coder pre-flagged exact concern at spawn time).
- **§16 audit round 3:** 14 ✅ / 0 🟡. "Safe to commit."

## Files

Modified:
- `backend/engine/orchestrator.py`

Created:
- `backend/engine/replay_engine.py`
- `backend/diagnostics/replay_diagnostic.py`
- `backend/diagnostics/decisions/2026-05-25__replay-backend-sub-step-1.md` (this file)

Untouched (downstream consumers, verified by grep):
- `backend/strategy/confluence/scorer.py` — unchanged
- `backend/analysis/regime_detector.py` — unchanged
- `backend/strategy/smc/bos_choch.py` — unchanged
- `backend/shared/config/scanner_modes.py` — unchanged
