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

## OPEN QUESTION (instrumentation gap — unresolved)
Is the global regime genuinely compressed (BTC truly sub-0.8% ATR% for the whole period — then
the *design choice* "global compressed suppresses swing on every alt" is the lever), OR is the
global volatility classifier underreporting (TF/period/stale-cache — note global_regime_cache
TTL at `regime_detector.py:87-91`)? The signals log the *symbol* atr_percent, not the global
regime's atr_percent/TF. To resolve: log `global_regime.volatility`, its source ATR%, and TF per
scan. Until then, do NOT tune the 0.8% threshold or the cap — would be threshold tampering without
a baseline (CLAUDE.md §15).

## Status / next
- No code changed. Operator chose: diagnose-deeper (done, here), FYC → UI-only, build macro-band
  Cycle Compass UI.
- FYC (`strategy/smc/four_year_cycle.py`, `get_fyc_confluence_modifier`) confirmed **dead in live
  path** — referenced only by `api_server.py` `/api/market/btc-cycle-context`. Staying UI-only.
- DCL/WCL short-term cycle (`strategy/smc/symbol_cycle_detector.py`) IS live in the confluence
  scorer (~4791-5093).
- Deferred design (NOT approved): cycle-aware exemption to the swing cap + counter-trend gate so a
  confirmed DCL/WCL accumulation can rescue counter-trend intraday/swing. Needs §15 entry + baseline.
