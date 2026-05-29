# Chapter 4 — Liquidity Sweeps

> **Backend ground truth**: `backend/strategy/smc/liquidity_sweeps.py` (esp. four-filter gate `:48`, double-sweep check `check_double_sweep`, structure validation `validate_sweep_with_structure`)
> **Phase 1 widget**: Sweep-vs-breakout twin
> **Phase 2 widgets**: Stop-cluster heatmap, Wick-size threshold slider, Asian range animator, Double-sweep highlight, HRLR-vs-LRLR diagnostic

## Core mechanic

A sweep is a price excursion that **briefly trades through a swing high or low to trigger resting stop orders, then closes back on the original side**. Four hallmarks:

1. A real wick beyond the level
2. A body close back inside
3. A reversal of measurable magnitude within a small number of bars
4. Often (not always) a volume spike

**What the bot does** — four-filter gate:

- **Range-position filter**: only sweeps levels in the top/bottom 35% of the rolling 50-bar range — sweeps in the middle are noise
- **Level-age filter**: target level must be ≥ 10 bars old (recent levels haven't accumulated real liquidity)
- **Wick-size filter**: upper/lower wick must clear `0.15 × ATR` — body-pokes don't count as raids
- **Reversal-distance filter**: post-sweep, price must travel back through the level by ≥ `min_reversal_atr` within a mode-specific window (SURGICAL=3 bars, STRIKE=4, STEALTH=6, OVERWATCH=12)

Confirmation level (0–3) tiers off volume × reversal-pattern: climactic volume (3×+) = level 3; strong (2×+) with engulfing/hammer = level 3; pattern only = level 1. Also detects **double sweeps** (same level swept twice) — strongest reversal signal in the family.

## Why it works (microstructure)

Stops are explicit liquidity. Every cluster of equal highs has stop-buys parked above and breakout-buy limit orders right at the line. When an institution needs to **enter a short with size**, the cheapest way to find counterparties is to push price *above* the cluster — every buy stop becomes a market buy that gets filled into the institution's short. The reversal is mechanical:

- The buying that drove the sweep was forced and exhausted
- The resting offer above (and the now-trapped breakout longs about to puke) supplies the down-move

This is Wyckoff's **spring** (sweep below accumulation low → reverse up) and **upthrust** (sweep above distribution high → reverse down), 100 years old, microstructure-grounded.

## Canonical visual example

**Pre-sweep**: a 30-bar consolidation with three equal highs at 50,200 (visible as a horizontal cluster).

**Sweep bar**: opens at 50,150, wicks to 50,280 (clearly above the EQHs), closes at 50,170 (back below). Large red body relative to the wick.

**Confirmation bars** (next 1–3): close progressively lower; bar +3 closes at 49,950.

**SVG treatment**: highlight three EQH touches with cyan dots, draw horizontal dashed line through them, animate sweep bar with upper wick poking through line (line pulses red), then bar body retracts back below (line goes amber "swept"), then 3 follow-through bars draw downward with reversal-distance measured by vertical arrow.

## Common mistakes (flip-card material)

1. **Confusing a sweep with a breakout.** Same first move, opposite implication. The difference is whether the candle **closes** beyond the level. Close beyond = acceptance (breakout); close back inside = sweep.
2. **Trading sweeps with no level-age.** Sweeping a high that formed 3 bars ago means almost no stops have parked there. Bot enforces `min_level_age_bars=10` for this reason.
3. **Calling a body-poke a "sweep".** Without a real wick (≥ 0.15 ATR), no stop-cluster was meaningfully tested.
4. **Ignoring range position.** A sweep of a mid-range high is noise. Sweeps that matter are at range extremes. Bot's `range_position_threshold=0.35` codifies this.
5. **Treating every sweep as bidirectional.** Asia-session sweep mechanics are direction-conditioned: in a bullish daily bias, the **Asian-range low** gets swept (London Judas swing) to fuel the rally.

## Edge cases & nuance

- **HRLR vs LRLR**: ICT distinguishes **High-Resistance Liquidity Run** (level deeply respected; needs a real sweep) from **Low-Resistance Liquidity Run** (failure-swing-style level price runs through with little friction). LRLR doesn't reverse — it continues. Confusing them is the most common live-trading mistake.
- **Equal highs/lows tolerance**: bot scales tolerance by TF (`scale_eqhl_tolerance`) and prefers ATR-based over percentage when ATR is available. Loose tolerance creates false EQH clusters; tight tolerance misses real ones — tuning problem with no universal answer.
- **Double sweeps**: two consecutive sweeps at the same level often signal exhaustion — the second sweep is "they tried twice and failed".
- **Sweep + structure-break combo**: a sweep that's followed within 10 bars by a BOS/CHoCH in the opposite direction is the highest-probability setup in the SMC stack — bot has `validate_sweep_with_structure` for exactly this.
- **Volume-light sweeps in crypto**: crypto often produces "sweep" patterns without volume confirmation (thin books, weekend liquidity). STRIKE mode skips volume requirements for this reason.

## Authoritative sources

- **Primary**: [ICT Liquidity Sweep vs Liquidity Run](https://innercircletrader.net/tutorials/ict-liquidity-sweep-vs-liquidity-run/) — canonical taxonomy
- **Primary**: [ICT HRLR & LRLR](https://innercircletrader.net/tutorials/ict-hrlr-lrlr/) — resistance-tier distinction
- **Primary**: [ICT Asian Range](https://innercircletrader.net/tutorials/ict-asian-range/)
- **Primary**: [ICT Liquidity (buy-side/sell-side)](https://innercircletrader.net/tutorials/liquidity-in-forex-trading/)
- **Microstructure**: [Bookmap — order flow phenomena](https://bookmap.com/blog/order-flow-phenomena)
- **Microstructure**: [Bookmap — iceberg orders](https://bookmap.com/blog/how-to-read-and-trade-iceberg-orders-hidden-liquidity-in-plain-sight)
- **Vendor-neutral**: [Equiti — liquidity sweeps explained](https://www.equiti.com/sc-en/news/trading-ideas/liquidity-sweeps-explained-how-to-identify-and-trade-them/)
- **Vendor-neutral**: [London Judas Swing — FXNX](https://fxnx.com/en/blog/ict-asian-range-liquidity-trading-london-judas-swing-trap)
- **Wyckoff origin (Springs/Upthrusts)**: [market-bulls Wyckoff schematics](https://market-bulls.com/wyckoff-trading-method-accumulation-distribution-schematics/)

## Interactive treatments (Phase 2)

1. **Sweep-vs-breakout twin** *(Phase 1 hero)* — two charts side-by-side, identical first 5 bars; on bar 6 one closes beyond the level (breakout, green), one closes back inside (sweep, amber). Slider to scrub through and watch next 10 bars play out — sweep reverses, breakout continues.
2. **Stop-cluster heatmap overlay** — chart with EQHs/EQLs visible; toggle a "show liquidity" button and watch stop-cluster glow accumulate above each equal-high cluster (intensity ~ touches). Sweep animation "consumes" the glow as wick punctures.
3. **Wick-size threshold slider** — drag a slider that raises "minimum wick ATR" threshold from 0 to 1.0; chart highlights which candles now qualify as sweeps. At low threshold, every body-poke counts; at high, only real raids remain.
4. **Asian range animator** — chart with 24-hour session bands (Asia=blue, London=amber, NY=green); animate classic Asian-low sweep → London reversal pattern; pause-points explain each leg.
5. **Double-sweep highlight** — chart with level swept once (amber pulse) → consolidation → swept again (red pulse). Level then "breaks" downward with "exhaustion confirmed" callout.
6. **HRLR-vs-LRLR diagnostic** — two micro-charts; user classifies each ("this level has been respected 4 times = HRLR" vs "this is a failure swing with no prior touches = LRLR"). Drives home the most common operator mistake.

## Implementation notes

- **Phase 1**: prose + sweep-vs-breakout twin. Highest-leverage demo in the chapter — same first move, opposite outcome.
- **Phase 2**: stop-cluster heatmap is the visual wow — makes invisible stop liquidity visible.
- **Cross-chapter ties**: Master Fixture (the EQH that gets swept on the Master Fixture is the trigger for the Ch 1 OB formation); HRLR/LRLR diagnostic is the inverse of Ch 3's BOS-vs-sweep distinction; Asian range animator pre-figures Ch 9 (Kill Zones).
- **Numbers to sync**: `range_position_threshold=0.35`, `min_level_age_bars=10`, `wick_atr_min=0.15`, per-mode reversal windows from `liquidity_sweeps.py:48`. Add `// SYNC` comment.
