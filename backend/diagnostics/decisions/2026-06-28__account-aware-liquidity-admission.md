# Account-aware liquidity admission — Gate 1 (2026-06-28)

§15/§9-A threshold change on the shared universe-selection path. The liquidity rule ("don't trade
illiquid pairs", regime-strategy-router §9-A — operator's #1 named rule) used a single fixed
`min_24h_volume_usdt = 5_000_000` for every account. This replaces it (flag-gated) with a floor
scaled to the account's market FOOTPRINT. Operator-approved 2026-06-28 ("$500k hard-min, 0.5%
participation, paper-only first").

## Why
Slippage and stop-blowthrough risk — the thing the floor guards against — scale with POSITION
NOTIONAL, not account capital. And leverage multiplies notional: **"$1k at 20× IS a $20k position"**
to the order book. A $20 order can't move a $2M book, so a fixed $5M floor needlessly starves a
small account of tradeable pairs, while it could be too loose for a leveraged/large one. Phemex is a
small venue — its alt perps run $1–3M/24h (AVAX $2.67M, ARB $1.25M, OP $1.94M) vs BTC $166M — so the
fixed floor cut the universe to ~9–10 symbols regardless of who's trading.

## Formula (Gate 1)
```
floor = max(hard_min, (balance × leverage) / participation_rate)
```
- `participation_rate` default **0.005** (position ≤ 0.5% of 24h volume).
- `hard_min` default **$500,000** — absolute floor so NO account trades a dead/wash market (a stop
  can't fill there at any size). For small/unleveraged accounts the hard-min governs.
- Degenerate inputs (balance/leverage/participation ≤ 0) fail safe to `hard_min` (never "trade all").
- Direction-agnostic (admission is a universe filter applied identically to long/short theses).

## Baseline (measured — `account_aware_liquidity_diagnostic.py`, live Phemex 2026-06-28)
Account **$1,000 × 1×** → notional $1,000 → derived floor **$500,000** (hard_min clamp):
- fixed $5M admits **10**; account-aware admits **17** (+7: AVAX, DOT, INJ, OP, ARB, APT, TRX).
- only TON dropped (zero Phemex perp volume).

Account **$1,000 × 20×** → notional $20,000 → derived floor **$4,000,000** (formula governs):
- tightens to BTC/ETH/SOL/majors + ADA/NEAR (>$4M); drops AVAX/INJ/OP/ARB — same footprint as a
  $20k×1× account, by design.

## Flag-gating (regression-safety)
New `PaperTradingConfig` fields: `liquidity_mode` (default **"fixed"**), `participation_rate`,
`hard_min_volume_usdt`, `min_order_stop_pct_assumption` (Gate 2), `thin_book_liq_buffer_mult`
(Gate 3). With `liquidity_mode="fixed"` the call site computes the SAME `_liq_floor =
mode.min_24h_volume_usdt` as before and `filter_illiquid_symbols` is unchanged → **byte-identical**.
Proof: `pipeline_smoke.py` vs `golden_scan.json` + `capture_contracts diff` must stay clean.

## §15 statement
- Does NOT modify `min_confluence_score` or any pre-scoring gate threshold.
- The fixed $5M value is preserved as the default and fallback.
- PAPER-ONLY: only `paper_trading_service.py` is wired. `live_trading_service.py` is DEFERRED to a
  second decisions entry after paper telemetry validates the floors (live = §15 hard boundary).

## Scope / phasing
- **Phase A (this entry):** config + Gate 1 (notional-scaled floor) + diagnostic + tests.
- **Phase B:** Gate 2 — min-order risk guard (`min_order_notional × stop% > balance × risk%` → drop
  `min_order_risk`), leverage-independent.
- **Phase C:** Gate 3 — liquidation-safety (stop inside liq price + thin-book buffer; reject
  `liquidation_unsafe`), extends the existing `_adjust_stop_for_leverage` / `high_liquidation_risk`.

## Adversarial-review findings (gate, 2026-06-28) — HARD live prerequisite
adversarial-review verdict CHALLENGE (land Gate 1 — it's regression-safe, flag-gated, paper-only —
but the Phase B/C → live trigger is NOT met and NOT measurable by the current harness). Two findings
recorded as binding constraints:

1. **24h volume ≠ instantaneous order-book depth.** The floor guards against slippage/stop-blowthrough,
   which are functions of book DEPTH at the moment a stop fires — not 24h volume. On a small venue a
   pair can print $2M/24h with a near-empty book at 03:00 UTC / funding flips / cascades. The $500k
   hard-min filters DEAD markets but gives no protection against a GAPPY/WICKY one. The volume floor
   is a necessary-not-sufficient screen; the decisions claim "a stop can't fill at any sane price"
   overstated what a volume number can do.
2. **The paper executor slippage model is BLIND to the thin tier** (`paper_executor._calculate_slippage`:
   binary — BTC/ETH 10 bps, ALL other alts flat 35 bps). So the newly-admitted thin pairs (TRX $837k,
   APT $659k, DOT $960k) are simulated at the SAME 35 bps as a $40M alt. **Therefore paper telemetry
   CANNOT validate thin-book safety** — calibrating floors forward from paper P&L would produce a
   confidently-wrong green light.

**BINDING:** `account_aware` must NOT be promoted past the §15 paper boundary on paper-P&L evidence
alone. Before any live extension, EITHER (a) make the paper slippage model depth/volume-aware for the
thin tier (real >35 bps penalty on sub-$1M books), OR (b) add an order-book depth + spread probe on
the admitted universe and gate the live decision on THAT, not on paper P&L. UNVERIFIED until measured:
real spread/depth of AVAX/OP/ARB/DOT/TRX/APT on Phemex during dead-session + cascades; whether any
carry inorganic/wash volume; whether the pullback-probability gate (calibrated on the prior ~10-symbol
liquid universe) holds on sub-$1M books.

Partial mitigation shipped this phase: the diagnostic now prints a per-symbol **spread (bps)** column
so wide-spread admitted pairs are at least VISIBLE (spread is the cheap leading indicator of thin-book
fill quality). Full depth probe + slippage-model fix = the gate before live (own follow-up entry).

Secondary (noted): the floor uses CONFIG leverage, not per-trade effective leverage; if they diverge,
the notional is computed off the wrong number. In-scope only if the planner ever overrides config lev.

## Depth-aware admission (path 1, shipped 2026-06-28) — addresses the adversarial finding directly
Operator chose "1 → 2 → 3": fix the metric the review discredited FIRST. Within `account_aware` mode,
after the cheap volume floor cuts the universe, the BOUNDED survivor set is checked against the LIVE
order book (the thing volume only proxies):
- `phemex.get_book_quality(symbols, band_bps)` — per-symbol `fetch_order_book`, returns
  `{spread_bps, depth_usd}` where depth = MIN(bid-side, ask-side) resting notional within `band_bps`
  of mid (MIN = the thinner side governs → direction-agnostic). Per-symbol fetch failure →
  `{spread_bps: inf, depth_usd: 0}` = fail-safe DROP. Runs only for volume-survivors (not raw
  universe), only in `account_aware` mode → bounded fetch count on a 2-min scan.
- `pair_selection.filter_by_book_quality(...)` — pure partition: KEEP iff `spread_bps <=
  max_spread_bps` (15 default) AND `depth_usd >= position_notional × min_depth_mult` (3.0 default).
  Mass-conservation asserted. Missing/sentinel book → drop.
- New config: `depth_aware_admission` (True), `max_spread_bps` (15), `min_depth_mult` (3.0),
  `depth_band_bps` (10). With `liquidity_mode="fixed"` (default) NONE of this runs.

Why this is the real fix (measured): the diagnostic shows the depth gate is DYNAMIC — it cut INJ
($2,797 depth < $3k needed at $1k×1×) on one snapshot; NEAR read ~$2 depth on an earlier snapshot
(would be cut) and ~$10k on a later one (admitted). A live per-scan depth check catches whatever is
thin AT THAT MOMENT — strictly better than the static volume floor, which admitted NEAR at $5M-vol /
$2-depth. This is the adversarial reviewer's alternative #1, implemented.

NOTE the depth gate does NOT fully close the §15 live-gate prerequisite: the PAPER SLIPPAGE MODEL is
still flat-35bps-blind (the validation-instrument gap). Depth-aware ADMISSION + a depth-aware
SLIPPAGE model are both needed before live. Admission is done; the slippage-model fix remains the
binding live prerequisite.

## Gate 2 (path 2, shipped 2026-06-28) — min-order risk guard, NEAR-INERT on Phemex (measured)
Drop a pair whose SMALLEST allowed order, sized at a conservative stop%, would force more risk than
the per-trade budget (`min_notional × stop_pct > balance × risk%`). Leverage-INDEPENDENT (risk =
notional×stop%, not margin). Direction-agnostic.

**Fundamentals-first finding (measured, do not assume):** ccxt leaves Phemex
`market['limits']['amount'/'cost']['min']` EMPTY (all None). The real floor is in the raw market info:
`info['minOrderValueRv']` = a **$1** absolute floor, plus the lot step `precision['amount'] ×
contractSize × price`. Measured effective minimums: **BTC ~$59.67** (lot step binds), **ETH ~$15.73**,
**cheap alts ~$1** (the $1 floor binds). So at any realistic account size the guard barely fires — at
$150 × 2% ($3 budget) you'd need a >5% stop to block even BTC. This is the honest answer to "can I
trade with $150": YES — Phemex minimums are $1–60, tiny vs your positions. Gate 2 is therefore a thin
SAFETY NET (and future-proofs other venues / large-min pairs), not a frequent gate.

- `phemex.get_min_order_specs(symbols) -> {sym: min_notional|None}` (reads the real info fields; total
  ticker failure -> {} so the caller SKIPS, never nukes the universe; per-symbol unknown -> None).
- `pair_selection.filter_by_min_order_risk(...)` — pure, fail-safe DROP on None, mass-conservation assert.
- Call site: account_aware-only, after the depth gate; uses `min_order_stop_pct_assumption` (1%).
  DROP-ALL guard: if the gate would drop every survivor (a spec-data glitch, since Phemex always has
  minOrderValueRv), it SKIPS loudly rather than trading nothing (volume+depth already vetted them).
- Config: `min_order_risk_guard` (True). The precise per-plan check (real stop%) is DEFERRED — given
  the tiny measured mins it adds marginal value over the coarse universe gate.

## Gate 3 (path 3, shipped 2026-06-28) — liquidation-safety guard, ADMISSION-LEVEL (covers all leverage)
"All edge cases covered" (operator): some users trade leverage, some don't. Gate 3 covers both — at the
ADMISSION level, so it did NOT require editing the §15 planner/risk_engine.

**Scoping finding (measured):** plan-time liquidation safety ALREADY EXISTS —
`risk_engine._adjust_stop_for_leverage` (entry×(1±mmr∓1/lev), 30% cushion, long/short symmetric) +
`high_liquidation_risk` reject. And at **leverage ≤ 1 liquidation is mathematically impossible**
(liq_price = entry×(1+mmr−1/lev) → entry×0.004 at 1×). So Gate 3 is a leverage-driven ADMISSION
pre-screen that complements (does not replace) the existing plan-time backstop:

- `pair_selection.filter_by_liquidation_safety(symbols, leverage, book, position_notional, *,
  min_stop_pct, mmr=0.004, base_cushion_pct=30, thin_cushion_pct=50, thin_depth_mult=10)`:
  - leverage ≤ 1 → keep ALL (inert; the no-leverage user).
  - else KEEP iff `min_stop_pct <= (1/leverage − mmr) × (1 − cushion/100)` — the tightest plausible stop
    must fit inside the liquidation cushion. Cushion = base, bumped to thin_cushion for THIN books
    (depth < notional × thin_depth_mult — wick-liquidation; unknown book → treated thin, conservative).
  - `1/leverage − mmr ≤ 0` (absurd leverage) → drop all. Direction-agnostic (the liq-distance magnitude
    is identical long/short). Mass-conservation asserted.
- Reuses the SAME `_book` fetch as the depth gate (call-site hoisted: fetch once if depth OR liquidation
  active). Config: `liquidation_safety_guard` (True), `liquidation_min_stop_pct` (0.015).

Edge cases covered: (1) no leverage → inert/keep-all; (2) leverage + deep book → kept, plan-time 30%
cushion backstops; (3) leverage + thin book → dropped pre-plan (wick-liquidation); (4) leverage so high
no stop is viable → dropped. Two layers (admission exclusion + plan-time tighten) = all angles.

## Open / forward
- `participation_rate` (0.5%), `hard_min` ($500k), `max_spread_bps` (15), `min_depth_mult` (3.0) are
  initial values — calibrate from the depth/spread telemetry, not paper P&L.
- Order-book fetch adds ~N calls/scan (N = volume-survivors, ~16) — acceptable at 2-min cadence with
  ccxt rate-limiting; graceful-degrades (DEPTH gate SKIPPED, volume floor alone) if the book lookup
  returns nothing.
- Rollback: `liquidity_mode="fixed"` (default) — zero behavior change; or `depth_aware_admission=False`
  to keep the volume floor without the book gate.
