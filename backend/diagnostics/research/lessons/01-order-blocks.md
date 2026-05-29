# Chapter 1 — Order Blocks

> **Backend ground truth**: `backend/strategy/smc/order_blocks.py` (esp. `detect_obs_from_bos:808`, `_has_bos_confirmation:72`, freshness calc `:619`)
> **Phase 1 widget**: Master Fixture chart with OB annotation lens active
> **Phase 2 widgets**: Mark-the-OB mini-game, Refinement slider, Lifecycle animator, Spot-the-fake, Freshness-decay graph

## Core mechanic

An order block is the **last opposite-color candle before a displacement move that breaks structure**. Bullish OB = last red/down candle before a bullish impulse that takes out the prior swing high. Bearish OB = last green/up candle before a bearish impulse that takes out the prior swing low. The zone is the candle's range — often refined to body or 50% midpoint (the "Consequent Encroachment").

**What the bot actually does**: scans backward from each detected BOS, looking for the last opposite-color candle within a TF-scaled lookback (~7 bars). Uses the LuxAlgo-style **median range** (high→median for bearish, low→median for bullish) — tighter than full candle, matches what serious traders mark in practice. Parallel wick-rejection detector requires `wick/body ≥ 2.0` AND `displacement ≥ X·ATR`, with structure-context gating for Grade C blocks.

## Why it works (microstructure)

Institutional inventory is not filled in one print — it's sliced into iceberg child orders. The OB candle marks where a large counterparty accepted price one final time before being forced to chase the new equilibrium. The unfilled portion sits as resting bids (bullish OB) or offers (bearish OB). Price returns because:

- Market makers warehoused inventory at the OB and need to unload partials at break-even
- Stop-loss orders parked just beyond the OB extreme are the explicit liquidity target
- The post-OB displacement created an FVG that price will reach back to rebalance

This is the modern, microstructure-grounded version of Wyckoff's Composite Operator accumulating from fear-driven sellers (bullish OB) or distributing into euphoric buyers (bearish OB).

## Canonical visual example (SVG-buildable)

Five-bar minimum sequence, left-to-right:

1. **Down impulse** — three red bars trending lower
2. **OB candle** — final red bar, large lower wick, closes near the low
3. **Engulfing bull bar** — opens inside OB range, closes above prior swing high (displacement)
4. **Continuation bull bar** — extends the move; FVG opens between candle 2 and candle 4
5. **Retrace bar** — pulls back toward the OB high (entry zone)

**SVG treatment**: shade OB candle's body/median region in soft cyan, draw dashed horizontal line at OB's 50% (CE), arrow from OB → displacement high marked "BOS", price-return arrow from the high back into cyan zone marked "mitigation tap".

## Common mistakes (flip-card material)

1. **Marking the engulfing candle as the OB.** Wrong direction. The OB is the *last opposite-color candle BEFORE* the impulse, not the impulse itself.
2. **Marking an OB without a BOS.** A wick rejection alone is just a wick — without structural confirmation it's a supply/demand zone, not an OB. Bot enforces via `_has_bos_confirmation`.
3. **Using mitigated OBs.** First tap consumes unfilled inventory. Second-tap setups are statistically weaker.
4. **Confusing breakers with mitigation blocks.** Breaker = OB *failed* (price closed through, polarity flipped). Mitigation = OB held, price retests in original direction.
5. **Treating every wick into the zone as "tested".** A wick is mitigation; only a **body close beyond the OB extreme** is invalidation.

## Edge cases & nuance

- **Refined vs unrefined**: large-body momentum candle → refine to body or 50% (CE). Small-body long-wick rejection → use full range. Bot's median rule biases toward refined.
- **Freshness decay**: even untapped OBs decay. Bot half-life scales with TF — 4h on 1m, 4 days on 4H, 1 week on Daily. A 3-week-old 5m OB has effectively zero edge.
- **Breaker upgrade**: a breaker block formed *after* a liquidity sweep is the highest-probability OB-family pattern — the sweep already cleared opposite-side stops.
- **Structure context for Grade C**: bot rejects weak OBs (small displacement) unless they sit within 1.5·ATR of a recent swing — without structural anchoring they're noise.

## Authoritative sources

- **Primary**: [ICT Order Block — innercircletrader.net](https://innercircletrader.net/tutorials/ict-order-block/) — closest to original Huddleston curriculum
- **Primary**: [ICT Breaker Block](https://innercircletrader.net/tutorials/ict-breaker-block-trading/) and [ICT Mitigation Block](https://innercircletrader.net/tutorials/ict-mitigation-block-explained/)
- **Vendor-neutral**: [ATAS: ICT Order Blocks & Breaker Blocks](https://atas.net/blog/what-are-ict-order-blocks-and-breaker-blocks-in-trading/)
- **Vendor-neutral**: [Anatomy of a Valid Order Block (Liquidity Finder)](https://liquidityfinder.com/news/anatomy-of-a-valid-order-block-in-smart-money-concepts-67221)
- **Microstructure**: [Bookmap — iceberg orders](https://bookmap.com/blog/how-to-read-and-trade-iceberg-orders-hidden-liquidity-in-plain-sight)
- **Wyckoff origin**: [Wyckoff Analytics — method](https://www.wyckoffanalytics.com/wyckoff-method/)
- **Supplementary**: [Daily Price Action — 3 OB rules](https://dailypriceaction.com/blog/order-blocks/)
- **Supplementary**: [eplanetbrokers — mitigation blocks](https://eplanetbrokers.com/en-US/training/what-is-mitigation-block)

## Interactive treatments (Phase 2)

1. **Mark-the-OB mini-game** — 12-bar chart with clean BOS; user clicks the candle they think is the OB; correct = last opposite-color before impulse. Three difficulty levels: clean → engulfing → impulse with internal wick noise.
2. **Refinement slider** — single OB candle, slider drags between "full range" / "body only" / "50% CE". Live overlay shows zone shrinking with historical tap statistics ("Tighter = fewer touches but higher reaction quality").
3. **Lifecycle animation** — Fresh → Tapped → Mitigated → Breaker → Invalidated, with the OB zone changing color (cyan → amber → red → grey) as price plays through on a loop. Pause buttons at each transition.
4. **Spot-the-fake** — three side-by-side micro-charts: valid OB / wick-rejection-without-BOS / engulfing-mismarked-as-OB. Click the real one.
5. **OB freshness decay graph** — interactive plot of half-life curves per TF; user drags a "candle age" slider and watches freshness score collapse. Anchored to bot's actual `calculate_freshness` math.

## Implementation notes

- **Phase 1**: prose + Master Fixture annotated with OB lens. No bespoke widget yet.
- **Phase 2**: lifecycle animator is the highest-impact widget here (visceral teaching of fresh→breaker progression).
- **Cross-chapter ties**: Master Fixture (shared with Ch 2/3/4); flip-cards use `<FlipCard />` primitive; sources rendered via `<SourceList />`.
- **Numbers to sync**: freshness half-lives must match `order_blocks.py:619` constants. Add `// SYNC: backend/strategy/smc/order_blocks.py` comment in chapter `.tsx`.
