# Chapter 6 — Confluence Scoring

> **Backend ground truth**: `backend/strategy/confluence/scorer.py` (esp. `MODE_FACTOR_WEIGHTS:539-685`, pre-scoring gates `run_pre_scoring_gates`)
> **Phase 1 widget**: `<WeightSliderPanel />` (HUD-tier primitive) on a fixture signal
> **Phase 2 widgets**: Factor correlation heatmap, Pre-scoring gate funnel, Overfit demonstration, Mode profile comparator

## Core concept

Confluence scoring is a weighted-sum signal model: each "factor" (HTF alignment, BTC impulse, SMC structure, momentum, etc.) emits a sub-score in [0, 1], a weight vector that sums to 1.0 maps those factors to a single composite score, and a mode-specific threshold decides if the signal passes. The model is not just additive — modern implementations layer **pre-scoring gates** (hard binary filters that fail-fast before the weighted sum runs) on top of **soft scoring** (the weighted sum itself with synergy bonuses and conflict penalties).

The interesting failure mode is not "score too low" — it is *correlated factors voting twice* and *threshold passes that don't actually correspond to higher win rates*.

## Why it matters — the math

A weighted-sum scorer is a linear classifier in disguise. If factors are independent and each carries genuine predictive information, adding factors *should* monotonically improve signal-to-noise ratio (the entire premise of Fama-French / Carhart factor stacking). Three things break that promise:

1. **Correlated factors double-count the same information.** If RSI(14), Stoch(14,3), and Williams%R all read "overbought," you have not stacked three signals — you have stacked *one* signal with a 3× weight. The Carhart literature explicitly documents that momentum is positively correlated with market beta.
2. **More factors = more degrees of freedom = more overfit.** López de Prado's central thesis: the more candidate strategies/factors you screen, the higher the expected Sharpe of the winner *purely by chance*. He formalizes this with the **Deflated Sharpe Ratio**: if you tested 100 weight vectors and picked the best, you need to discount its Sharpe by selection bias before believing it.
3. **Passing a higher threshold ≠ higher win rate.** Tightening the threshold shrinks the sample, and small-sample win-rate estimates are noisy. A 75-score signal at n=12 telling you "80% historical win rate" is statistically indistinguishable from coin-flipping.

**Expectancy formula** makes the bad-weighting damage concrete:

```
E = (W × avgWin) − (L × avgLoss)
```

If a bad weight vector boosts the *score* of low-edge setups (because they ring three correlated bells) and demotes the *score* of high-edge setups (whose signal is concentrated in one underweighted factor), the system's expectancy *drops* even though the average score *rises*. You are now confidently betting on noise.

## Canonical visual / worked example — factor stack waterfall

X-axis: factors in order. Y-axis: cumulative contribution to score. Each bar shows how much that factor added (green) or removed (red). Final bar: threshold line drawn in cyan. If cumulative sits above the line, signal passes; if below, fails — and the bar that pushed it under is highlighted.

**Worked example** (STEALTH mode, 5 illustrative factors):

| Factor | Sub-score | Weight | Contribution |
|---|---|---|---|
| HTF alignment | 0.85 | 0.30 | 0.255 |
| SMC structure | 0.70 | 0.25 | 0.175 |
| BTC impulse | 0.60 | 0.20 | 0.120 |
| Momentum | 0.40 | 0.15 | 0.060 |
| Volume confirm | 0.55 | 0.10 | 0.055 |
| **Composite** | | **1.00** | **0.665 → 66.5** |

Threshold for STEALTH = 70. **Fails by 3.5 points.** Drop momentum weight to 0.10 and raise HTF to 0.35: composite becomes 71.0 → passes. That single re-weight is the entire story of why mode profiles matter, and why mode profiles must be calibrated against out-of-sample data, not curve-fit.

## Common mistakes (flip-card material)

1. **"Higher score = higher win rate."** No — higher score = higher *historical agreement among your factors*. If those factors are correlated or curve-fit, your win rate at score=80 can be *lower* than score=72.
2. **"Stack more indicators for safety."** Adding a 4th momentum oscillator after RSI/Stoch/MACD adds zero independent signal; it just makes momentum dominate the score. Diminishing returns set in fast.
3. **"Soft penalties compensate for failed gates."** They don't, and shouldn't. A failed structural-anchor or conflict-density gate means the signal is *categorically* invalid, not "directionally weaker." Pre-scoring gates exist because some failures are nominal-scale (yes/no), not ordinal (more/less).
4. **"Weights are universal."** They're regime-conditional. A weight vector that works in trend regime over-weights momentum; the same vector in chop will fire on every retracement. This is why `MODE_FACTOR_WEIGHTS` exists (OVERWATCH/STRIKE/SURGICAL/STEALTH).
5. **"Pass threshold = trade."** Pass threshold = signal is *eligible*. Position sizing, risk gates, and regime gates still get the last word. The score is necessary, not sufficient.

## Edge cases & nuance

- **Conflict density** — when multiple factors fire in opposite directions simultaneously, the right move is to fail the signal, not average them. SniperSight enforces this as a pre-scoring gate with mode-aware thresholds (5 for OVERWATCH/macro, 3 elsewhere) — calibrated from session win-rate data. This is a §10 standing fix.
- **Synergy bonuses** are double-edged. They reward factor *combinations* that historically over-performed the sum of their parts — but if not regularized, amount to memorizing past coincidences. Use sparingly with documented baselines.
- **Bull/bear symmetry** — if your scorer treats short setups asymmetrically (shorts need score 75 but longs only need 70), you have a structural directional bias. Either justify with regime asymmetry (crypto longs have positive drift) or fix it. §10 standing fix.
- **HTF composite collapse** — when you have three HTF factors (1w, 1d, 4h) that are mechanically correlated, collapse them into one HTF composite *before* the main weighted sum. Otherwise HTF mathematically dominates.

## Authoritative sources

- **Primary**: [Kelly 1956 — A New Interpretation of Information Rate](https://www.princeton.edu/~wbialek/rome/refs/kelly_56.pdf) — entropy-based view of information stacking
- **Primary**: [López de Prado — Advances in Financial ML (SSRN Ch. 1)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3104847); summary at [Reasonable Deviations](https://reasonabledeviations.com/notes/adv_fin_ml/)
- **Primary**: [Bailey & López de Prado — Deflated Sharpe Ratio (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551); [Wikipedia DSR](https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio)
- **Primary**: [López de Prado — 10 Reasons Most ML Funds Fail (GARP)](https://www.garp.org/hubfs/Whitepapers/a1Z1W0000054x6lUAA.pdf)
- **Primary**: [Carhart four-factor model — Wikipedia](https://en.wikipedia.org/wiki/Carhart_four-factor_model); [StableBread analysis](https://stablebread.com/fama-french-carhart-multifactor-models/)
- **Vendor-neutral practitioner**: [Robot Wealth — Quant Signal Trade-Offs](https://robotwealth.com/quant-signal-trade-offs-in-the-real-world/); [IBKR Quant mirror](https://www.interactivebrokers.com/campus/ibkr-quant-news/quant-signal-trade-offs-in-the-real-world/)
- **Supplementary**: [LuxAlgo — Trading Indicators Without Clutter](https://www.luxalgo.com/blog/multiple-indicators-without-overcomplicating-chart/); [NinjaTrader — Probability Stacking](https://ninjatrader.com/futures/blogs/the-potential-of-probability-stacking/)

## Interactive treatments (Phase 2)

1. **Weight Slider Playground** *(Phase 1 hero — `<WeightSliderPanel />`)* — fixed signal fixture (real telemetry payload) renders as a row of factor tiles with sub-scores. Vertical slider per factor. Drag a weight up/down and watch: (a) waterfall chart re-stacks, (b) composite score ticks in real time, (c) threshold line stays fixed, (d) pass/fail chip flips cyan→red as you cross it. Slider rail shows *current* weight as amber tick; baseline weights for STEALTH/SURGICAL/STRIKE/OVERWATCH visible as ghost ticks. Auto-renormalizes to 1.0 so the user feels the *trade-off*.
2. **Factor Correlation Heatmap** — N×N matrix of factors, cells colored by Pearson correlation. Hover a high-correlation cell → tooltip says "RSI(14) and Stoch(14,3) co-fire 87% of the time — stacking both gives you 1.87× momentum weight, not 2×." Click a row to dim everything except that factor's correlations.
3. **Pre-Scoring Gate Funnel** — vertical pipeline. Signal "drop" enters at top, falls through 4 gate stations (structural anchor → BTC impulse → regime → conflict density). Each gate animates green tick + glow if passed, red X + drop dissolves if failed. Click any gate to see the actual code-level check. Side counter shows aggregated stats per cycle. Mass-conservation assertion visible.
4. **Overfit Demonstration** — Strategy A (Sharpe 1.8, 1 weight vector tested) vs Strategy B (Sharpe 2.4, 200 vectors tested). User guesses which has higher out-of-sample expectancy; reveal shows DSR collapsing B to 1.3 while A stays at 1.7. Histogram of "Sharpe under the null" with both backtest Sharpes plotted; threshold slides right as multiple-testing count rises.
5. **Mode Profile Comparator** — four-column layout, one per mode. Each shows mode's weight vector as a donut chart with factor names. Hover a factor segment → highlights same factor across all four modes — instantly shows "STEALTH weights HTF heavily, STRIKE weights momentum heavily." A "load fixture signal" button: same signal scored under all four profiles, side-by-side.

## Implementation notes

- **Phase 1**: prose + `<WeightSliderPanel />`. This is a **HUD-tier primitive** — it also belongs in the Scanner setup page as a calibration tool. Build once, reuse.
- **Phase 2**: Gate Funnel is the second-highest priority because it's also reusable in Scanner forensics for "why didn't this signal fire" debugging.
- **Cross-chapter ties**: directly references Ch 8 (sizing) via the expectancy formula; ties to Ch 7 (regime) via "weights are regime-conditional"; the Gate Funnel pre-figures the whole scoring pipeline visualization in the cross-chapter Tri-Layer chart.
- **Numbers to sync** *(critical)*: `MODE_FACTOR_WEIGHTS` values from `scorer.py:539-685`. Any numeric example in the chapter `.tsx` must carry a `// SYNC: backend/strategy/confluence/scorer.py:539-685` comment so the `tune-confluence-weights` skill knows to re-check on weight edits. Also: conflict-density thresholds (5 OVERWATCH / 3 elsewhere) are §10 standing-fix values.
