# Chapter 7 — Regime Detection (Percentage ATR)

> **Backend ground truth**: `backend/analysis/regime_detector.py` (percentage ATR — §10 standing fix), `backend/analysis/regime_policies.py` (per-mode `RegimePolicy`)
> **Phase 1 widget**: `<RegimeQuadrant />` (HUD-tier primitive — live 2D plot)
> **Phase 2 widgets**: Volatility clustering visualizer, Indicator showdown, Markov transition simulator, ATR%-vs-absolute toggle

## Core concept

Markets cycle between trending, ranging, and chop regimes, and between volatility-expansion and volatility-contraction phases. Regime detection is the discipline of classifying *which one you're in right now* before applying any strategy, because trend-following bleeds in chop and mean-reversion blows up in trends.

Key tools: **ATR-as-percentage-of-price** (normalized volatility), **ADX** (trend strength, direction-agnostic), **Choppiness Index** (range vs trend), **Hurst exponent** (persistence), and at the academic tier, **Hamilton-style Markov regime-switching models**.

## Why it matters — the underlying mechanic

Volatility clusters. Mandelbrot's empirical finding — confirmed across every liquid market — is that large price changes are followed by more large price changes, small by small. This is not a statistical curiosity; it's the reason regime exists at all. If volatility were i.i.d., there would be no regimes to detect.

The percentage-ATR specifically matters because absolute ATR is price-dependent — an ATR of $200 on BTC at $100k is calm; that same $200 on a $5,000 alt would be a meltdown. The bot uses ATR% precisely to make regimes comparable across symbols. **This is a §10 standing fix — never reintroduce absolute-ATR comparisons.**

## Canonical visual example — 2D regime quadrant

X-axis: trend strength (ADX 0-60 or Hurst 0-1). Y-axis: normalized volatility (ATR% 0-5%). Four labeled cells:

```
              LOW VOL                HIGH VOL
TRENDING   | Quiet Trend          | Volatile Trend (markup/markdown)
RANGING    | Compression / Coil   | Chop (volatile range, news-driven)
```

A live dot for the current symbol moves through the quadrant as 4h bars print. Underneath: a sparkline strip showing ATR% over the last 200 bars with a horizontal mean line, so the operator can see the cluster they're in vs the historical baseline.

## Common mistakes (flip-card material)

1. **"ADX tells me direction."** It doesn't. ADX is a magnitude — +DI and −DI carry the direction. ADX > 25 = strong trend, but you still need price-action to know which way.
2. **"Absolute ATR comparison."** Comparing BTC's ATR to SOL's ATR in dollar terms is meaningless. Percentage-ATR normalization is the correct treatment, and CLAUDE.md flags absolute ATR as a regression to never reintroduce.
3. **"Choppiness Index is direction."** It isn't — it's range-vs-trend only. Below ~38.2 = trending efficiently. Above ~61.8 = ranging. The 38.2–61.8 band is transitional and the source of most false signals.
4. **"News breaks the regime instantly."** Single-bar news spikes can drop CHOP fast but the regime hasn't actually shifted — the indicator lags or whipsaws. Pair with multi-bar confirmation.
5. **"Volatility expansion = trend."** Expansion just means range widened. It can be a trending breakout *or* a volatile chop. Trend strength (ADX/Hurst) must agree before you call it.

## Edge cases & nuance

- **Regime is timeframe-dependent.** A symbol can be trending on 1d and chopping on 15m. The bot's mode-aware critical-TF system exists for this reason: STEALTH's 4h/1h vs STRIKE's 15m disagree intentionally.
- **Hurst exponent gives a persistence read but is sample-hungry.** H > 0.5 = trending/persistent, H = 0.5 = random walk, H < 0.5 = mean-reverting. Most retail implementations are noisy under ~200 bars; treat single-symbol Hurst with skepticism.
- **Markov regime-switching is the academic upgrade.** Hamilton (1989) is the foundational paper; recent Bitcoin work using HMM/MS-GARCH consistently identifies 2-4 latent regimes (bull-low-vol, bear-high-vol, plus a calm state). These models capture *transition probabilities* — "given we're in high-vol bear, what's the probability we flip to low-vol bull next bar?" — which heuristic indicators don't.
- **Crypto-specific ATR% benchmarks**: Majors (BTC/ETH) 4h ATR% sits 0.8-2% in normal times. Large caps 1.5-3%, mid caps 2-5%, small caps 3-10%, spiking above 20% in flushes. These are the empirical baselines a regime detector should be calibrated against.

## Authoritative sources

- **Primary academic**: [Hamilton — Regime-Switching Models (Palgrave entry, 2005)](https://econweb.ucsd.edu/~jhamilto/palgrav1.pdf) — foundational
- **Primary academic**: [Bitcoin Bayesian HMM paper (arXiv 2011.03741)](https://arxiv.org/pdf/2011.03741); [MS-GARCH Bitcoin paper](https://www.researchgate.net/publication/328655448_Volatility_regime_analysis_of_Bitcoin_price_dynamics_using_Markov_switching_GARCH_models)
- **Primary**: [Mandelbrot — Fractal Markets Hypothesis overview](https://accountend.com/understanding-mandelbrots-fractal-market-hypothesis-a-new-perspective-on-financial-markets/) — volatility clustering origin
- **Primary**: [J. Welles Wilder ADX — Wikipedia](https://en.wikipedia.org/wiki/Average_directional_movement_index); [StockCharts ChartSchool ADX](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-directional-index-adx)
- **Primary**: [Bill Dreiss Choppiness Index](https://gocharting.com/docs/charting/technical-indicator/oscillators/choppines-index); [QuantifiedStrategies treatment](https://www.quantifiedstrategies.com/choppiness-index/)
- **Vendor-neutral**: [Macrosynergy on Hurst exponent in finance](https://macrosynergy.com/research/detecting-trends-and-mean-reversion-with-the-hurst-exponent/); [Samara Alpha](https://www.samara-am.com/insights/hurst-exponent)
- **Vendor-neutral**: [Cryptoanalysis — ATR% for crypto](https://www.cryptoanalysis.ai/blog/what-is-atr-indicator); [Marketlab — ATR & ATR%](https://marketlab-academy.org/en/library/atr-and-atr-percent/)
- **Vendor-neutral**: [TrendSpider — Choppiness Index](https://trendspider.com/learning-center/choppiness-index/)

## Interactive treatments (Phase 2)

1. **Live regime quadrant** *(Phase 1 hero — `<RegimeQuadrant />`)* — 2D plot (ATR% × ADX). Current symbol's dot moves bar-by-bar; trail leaves fading cyan track. Operator can rewind last N bars by dragging slider; each quadrant lights up amber when dot enters and surfaces "what strategies fit here" callout. Bonus: ghost dot for BTC alongside symbol so correlation jumps out.
2. **Volatility clustering visualizer** — 365-day strip of |daily return|² rendered as a heatmap row. Operator hovers any cell to see surrounding 30-day cluster lit in cyan. Reveals Mandelbrot's clustering empirically — large bars are *not* uniformly distributed. Side panel toggles between BTC and a Gaussian-shuffled control so the difference is impossible to miss.
3. **Indicator showdown** — same chart, three rows underneath: ADX, CHOP, Hurst. Operator can mute/solo each. Highlights where they agree (high-confidence regime) and where they diverge (low-confidence — wait). Frames regime detection as a confluence problem, mirroring the bot's own architecture.
4. **Markov transition simulator** — simplified 3-state Markov model (bull-quiet, bear-volatile, calm) with editable transition probabilities. Operator slides probabilities; simulator runs 500-bar Monte Carlo path live. Demonstrates *why* regimes persist and how transition probabilities shape next-bar expectations. Pure wow.
5. **ATR%-vs-absolute toggle** — same chart, two symbols (BTC + a $5 alt). Toggle between absolute ATR and ATR%. Absolute view makes BTC look like the only volatile asset; the % view shows the alt is actually wilder. Drives the standing-fix lesson home in one click.

## Implementation notes

- **Phase 1**: prose + `<RegimeQuadrant />`. **HUD-tier primitive** — also belongs as a persistent readout on `/intel`. Build once, reuse.
- **Phase 2**: ATR%-vs-absolute toggle is the second priority because it doubles as a standing-fix inoculation for any future dev reading the code.
- **Cross-chapter ties**: directly anchors Ch 6 ("weights are regime-conditional"); Wyckoff Phase B chop (Ch 5) aligns with the "Compression/Coil" quadrant; ties to cross-chapter Tri-Layer chart (regime band colors).
- **Numbers to sync**: per-mode `RegimePolicy.min_regime_score` from `regime_policies.py`. Use percentage-ATR examples only; no absolute-ATR numbers anywhere in the chapter. Add `// SYNC: backend/analysis/regime_detector.py` comment to enforce the standing-fix invariant.
