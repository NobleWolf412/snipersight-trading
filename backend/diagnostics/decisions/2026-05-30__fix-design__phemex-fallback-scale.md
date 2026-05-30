# 2026-05-30 — FIX DESIGN (data-correctness, money-adjacent): phemex Direct-REST fallback guesses price scale → 1e8× corruption

**Status:** DESIGN — awaiting operator decision (recover-vs-reject fork). NO CODE WRITTEN.
**Bug:** Hot-path audit #4 (1_BROKEN, was 2-1 — mitigant now verified absent). See [[2026-05-29__hotpath-robustness-audit]].
**Gate:** `backend/data/adapters/phemex.py` is a data adapter → backend-integrity gated. Feeds sizing/liquidation via `current_price`, so money-adjacent (handled with §15-level care) but does NOT touch order/risk/persistence code → not strictly §15.

---

## ROOT CAUSE (verified against HEAD)

`PhemexAdapter.fetch_ohlcv` Direct-REST fallback (`phemex.py:221`):
```python
scale = 100000000.0 if (rows and rows[0][1] > 1000000) else 1.0
```
Phemex returns prices in scaled "Ep" integer form; the true scale is **per-contract**, not a function
of magnitude. For a sub-$0.01 coin (PEPE/SHIB/BONK/FLOKI), the raw Ep value of the first bar can be
`<= 1,000,000`, so the heuristic picks `scale = 1.0` and leaves the price **1e8× inflated**
(e.g. PEPE $0.000012 → 1200.0). The frame passes `normalize_and_validate` (all 5 OHLC fields scaled
identically, so OHLC relationships still hold) and the mis-scaled `volume` rides along on the same line.

## VERIFICATION OF THE 2-1 MITIGANT (the reason this was 2-1) — MITIGANT ABSENT
The dissenting lens claimed the independent-ticker 15% drift gate would reject the inflated price.
Traced and **refuted**:
- The drift gate lives in `OHLCVCache.get()` (`ohlcv_cache.py:285`): it evicts a **cached** entry when
  `entry.is_stale_by_price(current_price, max_price_drift_pct)`. It is a cache-staleness check, not a
  validation of a freshly-fetched frame.
- Same-cycle path: cache miss → fallback builds the corrupt frame → it is `set()` AND returned for use
  **this cycle**; sizing/liquidation consume it before any `get()` drift check runs.
- Even next cycle, the `current_price` passed to the drift check is derived from `timeframes[-1]` close
  (the same corrupt frame), so it compares corrupt-vs-corrupt and passes. There is no independent
  ticker cross-check on the fetch path.
**Conclusion:** #4 is a genuine 1_BROKEN. A corrupt 1e8× `current_price` can reach position sizing and
liquidation math on the cycle the fallback fires (CCXT throw + sub-$0.01 symbol in the universe).

## THE FORK (operator decision)

### Option A — Verify-or-reject (simplest, safest)
After building the fallback frame, fetch an independent `fetch_ticker(symbol)` price. If the frame's
last close is within tolerance (e.g. ±10%) of the ticker, accept; else **reject** (return empty df →
symbol dropped this cycle) with a loud `logger.error`. Never feeds an unverified price to sizing.
- Pro: dead simple, fail-loud, zero chance of a wrong-scale price reaching money math.
- Con: drops the symbol for the cycle even when the scale was merely guessable.

### Option B — Derive the scale from the ticker, then verify (recommended)
Fetch `fetch_ticker(symbol)` for the real price; compute `scale = nearest_power_of_10(raw_ep_close /
ticker_price)` and apply it; then verify the scaled close is within tolerance of the ticker — if not
(or ticker unavailable), fall back to Option A's reject. Recovers the symbol with a correct,
data-driven scale instead of a magnitude guess.
- Pro: correct scale for any contract (not just sub-$0.01); still fail-loud-reject when unverifiable.
- Con: one extra ticker call on the (already-degraded, rare) fallback path; slightly more code.

### Option C — Use CCXT market precision metadata
Pull the proper price scale from the CCXT market object (`self.exchange.market(symbol)` priceScale /
precision) instead of guessing. Cleanest IF reliably exposed for Phemex perps.
- Pro: authoritative scale, no extra network call.
- Con: depends on CCXT exposing the scale for the contract; needs verification it's populated when the
  CCXT OHLCV path itself just failed (the exchange object may still hold market metadata even when a
  data call throws — to confirm during implementation). Recommend B as the primary with C as an
  optimization if the metadata proves reliable.

## RECOMMENDATION
**Option B** (derive scale from an independent ticker, reject if unverifiable). It is correct for all
contracts, fail-loud on the money path, and the extra ticker call is on a rare degraded path. If the
operator prefers minimal change under the de-risking posture, **Option A** (reject-only) is the safe
floor — it never recovers a symbol but never feeds a bad price either.

## BLAST RADIUS (§20)
- **Upstream:** `fetch_ohlcv` callers — `IngestionPipeline` / `_refresh_price_cache` / scan data fetch.
- **Downstream:** the frame → indicators, SMC, `_get_current_price` → confluence, planner geometry,
  **position sizing + liquidation** (the money-critical consumers). `fetch_ticker` (the new cross-check
  dependency) — confirm it does not itself route through the same broken scaling.
- **Contract:** no API/telemetry/DB/SniperContext schema change (internal adapter logic).
  `capture_contracts diff` expected clean (modulo the unrelated replay drift).
- **Symmetry:** direction-agnostic (price scaling); not bull/bear specific.

## REGRESSION DIAGNOSTIC (same diff — §18)
- Feed the fallback parser a captured Phemex `/md/kline` payload for a sub-$0.01 symbol with
  `rows[0][1] <= 1e6` + a stubbed `fetch_ticker` returning the real price; assert the returned close
  matches the ticker within tolerance (NOT 1e8× off), and `volume` scaling parity (spot vs perp).
- Negative: ticker unavailable / disagrees by orders of magnitude → assert the frame is rejected
  (empty df) and a loud error logged, NOT a corrupt frame returned.
- Positive (no regression): a normal-priced coin (BTC) still parses to the correct scale.

## VERIFICATION PLAN
backend-integrity blast-radius + `capture_contracts diff` + (pipeline_smoke if it exercises ingestion) ·
§16 14-point audit · new regression test green. symmetry-guard N/A (no scoring/SMC/regime code).
