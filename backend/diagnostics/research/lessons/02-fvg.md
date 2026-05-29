# Chapter 2 — Fair Value Gaps (FVGs / Imbalances)

> **Backend ground truth**: `backend/strategy/smc/fvg.py` (esp. detector `:122`, overlap check `:360`, merge logic `:562`)
> **Phase 1 widget**: Animated 3-candle FVG builder
> **Phase 2 widgets**: IFVG flip animator, BPR overlap visualizer, Fill-mechanics dual-meter, Find-the-FVG speed quiz, Stacked-FVG merge demo

## Core mechanic

A three-candle pattern where candle 1's wick and candle 3's wick fail to overlap, leaving an unfilled price band created by the displacement of candle 2.

- **Bullish FVG**: `candle[0].high < candle[2].low` — gap sits between those two levels
- **Bearish FVG**: `candle[0].low > candle[2].high`

The gap represents one-sided delivery — buy and sell orders did not overlap during the move.

**What the bot does**: exactly the three-candle test above, with two additional gates: (1) middle-candle overlap with the gap must be ≤10% (filters partial overlaps), and (2) gap size in ATR units must clear a mode-specific threshold (`0.06` SURGICAL → `0.45` OVERWATCH). Grading: A if `gap_atr ≥ 2.5×` the mode minimum, B if `≥ 1.5×`, C otherwise. Fill is measured from the entry side per direction — an important nuance most retail traders miss.

## Why it works (microstructure)

An FVG is the chart-visible footprint of an **order-flow imbalance** — one side of the book got exhausted faster than the other could refresh quotes. Market makers running mean-reversion books are short-gamma at gap formation: they need price to retrace to rebalance inventory and unwind hedges. Combine with:

- The displacement candle ran past resting limit orders that were never filled
- Algos programmed to fade gaps produce a deterministic pull

Order book imbalance literature treats this as a measurable predictor of mean reversion within microstructure horizons.

The retest probability sits around **60–70% on most timeframes** based on retail backtests. But the 30–40% that *don't* fill are the highest-momentum continuation moves. An unfilled FVG is not a failure — it's a tell.

## Canonical visual example

Three consecutive green candles forming a bullish stair-step:

1. **Candle 0** — normal green; high 100.00
2. **Candle 1 (displacement)** — large green body; high 103.50, body 100.50→103.20, body and wicks entirely above candle 0's high
3. **Candle 2** — green; low 101.00, well above candle 0's high

FVG = shaded rectangle from 100.00 to 101.00. Price moves up further, then retraces back into the shaded zone. Tap of upper edge (101.00) = entry; mid-gap (100.50) = consequent encroachment; lower edge (100.00) = invalidation.

**SVG treatment**: animate the third candle's appearance, then snap the shaded rectangle into existence with a soft cyan fill and dashed top/middle/bottom lines.

## Common mistakes (flip-card material)

1. **Counting any three-candle gap as an FVG without checking middle-candle overlap.** If candle 1's body intrudes deep into the gap region, the imbalance is half-filled at formation. Bot rejects via `max_overlap = 0.1`.
2. **Treating wick fills the same as body fills.** A wick into the FVG = mitigation; a body close *through* the far edge = invalidation.
3. **Trading every FVG in sight.** Lower-TF gaps in a strong trend are continuation tells, not entries. Bot per-mode size filter exists exactly for this.
4. **Ignoring direction symmetry.** Bullish FVG fill is measured top-down; bearish FVG fill bottom-up. Wrong reference inverts freshness math.
5. **Confusing FVG with BPR (Balanced Price Range).** A BPR is two **opposite-direction** FVGs overlapping at the same price band — *both* sides have unfinished business. Much sharper reaction than a single FVG.

## Edge cases & nuance

- **IFVG (Inversion FVG)**: when price closes through an FVG in the opposite direction with a candle body, the gap **flips polarity**. A broken bullish FVG becomes resistance on retest; a broken bearish FVG becomes support. IFVG is the earliest microstructure tell of a momentum shift on LTF.
- **Consecutive FVG merging**: three FVGs in close succession in the same direction → bot merges them into one larger zone. Multiple stacked imbalances act as one big mean-reversion magnet.
- **FVGs during news**: less likely to fill — the imbalance was *informationally* driven, not microstructural.
- **Decay**: 5m FVG hits ~50% freshness in 8 candles (~40 min); daily FVG holds ~20 candles. Stale FVGs are context, not entries.

## Authoritative sources

- **Primary**: [ICT Fair Value Gap (FVG) — 6-Step Strategy](https://innercircletrader.net/tutorials/fair-value-gap-trading-strategy/)
- **Primary**: [ICT Inversion FVG (IFVG)](https://innercircletrader.net/tutorials/ict-inversion-fair-value-gap/)
- **Primary**: [ICT Balanced Price Range (BPR)](https://innercircletrader.net/tutorials/ict-balanced-price-range-bpr/)
- **Vendor-neutral**: [TrendSpider Learning Center — FVG](https://trendspider.com/learning-center/fair-value-gap-trading-strategy/)
- **Vendor-neutral**: [Alchemy Markets FVG](https://alchemymarkets.com/education/strategies/fair-value-gap/)
- **Vendor-neutral**: [Inversion FVG (FluxCharts)](https://www.fluxcharts.com/articles/Trading-Concepts/Price-Action/Inversion-Fair-Value-Gaps)
- **Microstructure**: [Order Book Imbalance — QuestDB](https://questdb.com/glossary/order-book-imbalance/)
- **Supplementary** (treat as illustrative, primary is ICT): [edgeful.com — FVG win rates with real data](https://www.edgeful.com/blog/posts/fair-value-gap-best-practices-guide), [Mastering FVGs — fxnx.com](https://fxnx.com/en/blog/mastering-fair-value-gaps-trading-high-probability)

## Interactive treatments (Phase 2)

1. **Animated 3-candle FVG builder** *(Phase 1 hero)* — Press a button, three candles draw one by one; on third candle's appearance, shaded gap rectangle snaps in with a satisfying glow. Price line animates back into the gap and either bounces (fill from edge) or pierces (invalidation), randomized per click.
2. **IFVG flip animator** — Start with a fresh bullish FVG, slider drags price downward; as slider passes FVG bottom, rectangle flips cyan→amber. Hover shows "now resistance on retest".
3. **BPR overlap visualizer** — Two-panel chart: top shows bullish FVG forming on way up, bottom shows bearish FVG forming on way down. Drag panels together; where they overlap, a brighter "BPR" zone lights up.
4. **Fill-mechanics dual-meter** — Single FVG with two live gauges: "Wick mitigation %" and "Body close %". Drag price through the gap and watch gauges diverge — teaches wick-vs-body distinction viscerally.
5. **Find-the-FVG speed-quiz** — 5-second chart flash, 4 candidate gap rectangles overlaid; tap the real one. Wrong answers reveal *why* (overlap too high / not a true 3-candle gap / already filled).
6. **Stacked-FVG merge demo** — Three small FVGs forming in sequence; press "Merge" and watch them collapse into one larger zone with the bot's actual merge logic.

## Implementation notes

- **Phase 1**: prose + animated 3-candle builder. This is the highest-impact widget in the chapter; pulls double duty as the hero.
- **Phase 2**: IFVG flip is second highest impact — the polarity-flip is counterintuitive and animation makes it click.
- **Cross-chapter ties**: shares Master Fixture (the same FVG appears in Ch 1 above the bullish OB); `<FlipCard />` and `<SourceList />` primitives.
- **Numbers to sync**: mode-specific ATR thresholds (`0.06` SURGICAL → `0.45` OVERWATCH) must match `fvg.py:122`. Add `// SYNC` comment.
