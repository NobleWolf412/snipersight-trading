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

## Open / forward
- `participation_rate` (0.5%) and `hard_min` ($500k) NOT yet calibratable from paper P&L (see above) —
  calibrate from a depth/spread probe, not paper fills.
- Rollback: set `liquidity_mode="fixed"` (the default) — zero behavior change.
