# 2026-05-31 — Cascade scalp-monoculture root cause: global "compressed" regime saturation

## Trigger
Operator observed the bot "only triggers scalp trades." Asked whether this is by design or
whether intraday/swing are being overshadowed. Diagnose-deeper requested (no gate changes yet).

## Evidence (37 sessions, ~96k signals, logs/{live,paper}_trading/*/signals.jsonl)

- **Regime label is `*_compressed` ~98% of the time**: up_compressed 92%, down_compressed 6%,
  up_normal 0.6%. `normal`/`elevated`/`volatile`/`chaotic` effectively never appear as the
  composite regime label across weeks and many symbols.
- **Executed by trade_type: scalp 188 / intraday 10 / swing 3** (93.5% scalp). Swing ≈ 0.
- **Counter-trend intraday/swing blocks: 951** (reason_type=`regime_counter_trend`).
- **BUT the symbols' own logged `atr_percent` (n=10,955) is median 1.03%**: 26.4% < 0.8%
  (compressed band), **60.5% in 0.8–1.5% (normal band)**, 12% elevated, 1.1% volatile.
  → The symbols are mostly in *normal* volatility; the `compressed` regime label contradicts
  the symbol-level ATR%.

## Mechanism (code, confirmed)

1. **Volatility classifier** `analysis/regime_detector.py:719` — `atr_pct < 0.8% → "compressed"`.
2. **Swing cap** `engine/orchestrator.py:2347-2358` — double-bind:
   - `_is_compressed = symbol_vol in ("compressed","low")`, AND
   - if symbol reads non-compressed, it is **overridden by the GLOBAL (BTC) regime**
     (`orchestrator.py:2350-2356`): global compressed/low ⇒ `_is_compressed=True` regardless.
   - `if _is_compressed and "swing" in cascade_types: cascade_types.remove("swing")` (2358-2366).
   - Net: swing survives only when BOTH symbol AND global volatility are non-compressed.
3. **Counter-trend gate** `bot/paper_trading_service.py:2119-2132` — in any directional regime
   (up/down/up_compressed/down_compressed) counter-trend **intraday & swing are blocked; scalp
   is exempt** (allowed ≥70%, half-sized). 951 blocks across the corpus.
4. **Cascade ranking is NOT the cause** — `orchestrator.py:3446` bonuses (swing +6 / intraday +3
   / scalp +0), winner = `max(effective_score)` (`:3645`). Swing/intraday win when they produce a
   *valid* plan; they are eliminated upstream by (2) and (3), not out-scored.

## Conclusion
Scalp monoculture is an **emergent property of two regime gates**, dominated by (2). The global
BTC volatility label is `compressed` ~98% of the time and is allowed to override a symbol's own
`normal` label, removing swing from the cascade on ~74% of symbols that are NOT actually
compressed (median symbol ATR% 1.03%). It is **not a cascade-selection bug and not a one-session
fluke** — it is systemic across the entire 37-session history.

## OPEN QUESTION — RESOLVED 2026-05-31: timeframe-selection BUG (not quiet markets)
The classifier under-reports because it computes "structural" volatility on the WRONG timeframe.
`RegimeDetector._detect_volatility` picks the "primary" TF with
`sorted(by_timeframe.keys(), reverse=True)[0]` (regime_detector.py:668, comment "Get highest
timeframe indicator"). (NOTE: only `_detect_volatility` had this bug — `_detect_trend` already
uses an explicit `preferred_order` list and was always correct; left untouched by the fix.)
But the keys are TF strings; lexical reverse-sort of
('1W','1D','4H','1H','15m','5m') returns **'5m'** (because '5' > '4' > '1' as the leading char),
i.e. the LOWEST timeframe, not the highest.

Empirical (live BTC, 2026-05-31, ATR-14 %-of-price — see
`backend/diagnostics/regime_tf_selection_diagnostic.py`):
  5m 0.144% · 15m 0.189% · 1h 0.308% · 4h 0.787%  → all "compressed"
  1d 2.504% → "volatile"      (1w fails to fetch on Phemex — NaN)
So the global label is mathematically pinned to "compressed" (anything ≤4h is sub-0.8%), while the
real structural read (1D) is "volatile". Not quiet markets — a sort bug.

Blast radius of fixing the sort (duration-order the TFs): affects the MULTI-TF callers —
global regime (→ swing-cap orchestrator.py:2347-2358, the scalp-monoculture cause), symbol regime,
`entry_engine` get_atr_regime, AND the planner TP-ladder.

CORRECTION (Plan agent, 2026-05-31): my earlier claim that the planner ladder is NOT affected was
a WRONG, un-traced premise (the exact failure mode 2026-05-29__regime-label-premise-miss.md warns
about). Only the STOP-LOSS buffer is out of scope — `risk_engine.py:821` (_calculate_stop_loss)
passes a single IndicatorSnapshot wrapped as `_primary`, so the sort is a no-op there. But the
TP-LADDER is in scope: `planner_service.py:404` (_calculate_targets) and `entry_engine.py:795`
pass the FULL IndicatorSet, so the fix flips the regime feeding `_MAX_RR_BY_REGIME` (cap 3R→6-12R),
`atr_regime_multipliers` (0.9×→1.0-1.5×), and the entry-zone offset. That is a ladder-wide
behavioral change touching the recently-tuned reachability logic (2026-05-24/30) — the top risk.
Operator decision pending: accept the wider-ladder change, OR isolate it by switching those two
call sites to a single primary-TF snapshot so only the swing-cap consumes the multi-TF label.

COUPLED DESIGN CHOICE (operator decision pending): the thresholds (0.8/1.5/2.5/4.0) were never
meaningfully exercised on 5m (always <0.8). Re-pointing to 1D needs threshold recalibration +
a baseline, else 1D's ~2.5% normal daily range mislabels as "volatile/chaotic". Fix = Plan-gated,
symmetry-guard + §16 audit, baseline before/after. Do NOT tune in isolation.

## Status / next
- No code changed. Operator chose: diagnose-deeper (done, here), FYC → UI-only, build macro-band
  Cycle Compass UI.
- FYC (`strategy/smc/four_year_cycle.py`, `get_fyc_confluence_modifier`) confirmed **dead in live
  path** — referenced only by `api_server.py` `/api/market/btc-cycle-context`. Staying UI-only.
- DCL/WCL short-term cycle (`strategy/smc/symbol_cycle_detector.py`) IS live in the confluence
  scorer (~4791-5093).
- Deferred design (NOT approved): cycle-aware exemption to the swing cap + counter-trend gate so a
  confirmed DCL/WCL accumulation can rescue counter-trend intraday/swing. Needs §15 entry + baseline.
