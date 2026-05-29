# Chapter 8 — Position Sizing + Risk

> **Backend ground truth**: `backend/strategy/risk_engine.py`, `backend/bot/executor/position_manager.py` (max_hours_open, stagnation), per-mode `RegimePolicy.position_size_multiplier`
> **Phase 1 widget**: `<KellyCurve />` (HUD-tier primitive — inverted-U log-growth chart)
> **Phase 2 widgets**: `<EquityCurveMonteCarlo />`, Leverage trap visualizer, Ergodicity demonstration, R-multiple journal replay, Kelly calculator quiz

## Core concept

Position sizing is the lever that converts a positive edge into long-run wealth — or destroys it. There are three families of sizing rule (fixed-fractional, Kelly-based, volatility-normalized/ATR), and they all answer the same question: *given my edge and my equity, how much should I risk?*

The subtlety operators miss is that this is **not a return-maximization problem in arithmetic mean** — it is a **log-growth maximization problem under non-ergodic compounding**, where over-sizing past Kelly guarantees ruin even with a real edge.

## Why it matters — the math

**Kelly criterion** (binary outcome, asymmetric payoff):

```
f* = (bp - q) / b
```

where `b` = net odds (avgWin / avgLoss), `p` = win probability, `q` = 1 − p. Derived by maximizing `E[log(W)]`, the expected log-wealth after each bet.

**Expectancy** (per-trade, in R units after Van Tharp):

```
E = (W × avgWinR) − (L × avgLossR)
```

where W and L are win/loss probabilities and R is the unit risk (entry − stop, sized so initial risk = 1R). A positive E in R-units is a necessary condition for sizing to even make sense.

**Geometric vs arithmetic return / volatility drag**:

```
g ≈ μ − σ²/2
```

The geometric (compounded) growth rate `g` is the arithmetic mean `μ` minus half the variance. Volatility *itself* is a drag on compounded returns — and leverage scales volatility super-linearly, which is why a 3× leveraged ETF on a flat-ish underlying decays even when the underlying is unchanged.

**The deep result — ergodicity.** A non-ergodic process has time-average return ≠ ensemble-average return. Trading a single account is non-ergodic — you cannot run 1000 parallel lives and average them. Ole Peters and Nassim Taleb formalize this: optimizing for expected (arithmetic) value is a *category error* if you're a single agent compounding through time. You must optimize for *time-average* growth rate, which is exactly `E[log(W)]`, which is exactly Kelly.

**Risk of ruin** closes the loop. Probability of N consecutive losses = `(1 − W)^N`. Doubling your risk-per-trade doesn't double ruin probability — it scales exponentially. A 52% / 1.1R-payoff trader risking 2% has ~7% ruin probability; the same trader risking 4% has ~30%.

**Past Kelly, you don't just give back gains — you bleed.** Past `f*`, the inverted-U log-growth curve crosses zero and goes *negative* — meaning you are guaranteed to lose money geometrically, even with a positive edge in arithmetic mean. At `2 × f*` exactly, long-run growth rate is *zero*; past that, it's negative.

## Canonical visual — the Kelly curve (HERO chart)

The most important chart in this entire library: **log-growth rate g(f) plotted against bet fraction f**. It's an inverted U.

- X-axis: bet fraction `f`, from 0 to ~ 2×f* (e.g., 0 to 0.5 if f* = 0.25)
- Y-axis: long-run geometric growth rate per trade

Three annotated zones:

- **Cyan: 0 < f < f*** — "under-Kelly" — sub-optimal growth, but you survive.
- **Amber: f* < f < 2f*** — "over-Kelly" — growth is still positive but variance balloons; drawdowns become brutal. Half-Kelly lives in the cyan zone deliberately.
- **Red: f > 2f*** — "ruin zone" — geometric growth is *negative* despite positive edge. The cliff. This zone is where most blown accounts die.

**Worked example**, binary bet: edge of 55% win rate at 1:1 payoff.

- `f* = (1·0.55 − 0.45) / 1 = 0.10` → full Kelly says risk 10% per bet
- Half-Kelly: 5% per bet — gives up ~25% of growth rate, cuts drawdown roughly in half
- 2× Kelly: 20% per bet — long-run growth = 0
- 3× Kelly: 30% per bet — guaranteed ruin in finite time

This is the chart that, once a trader internalizes it, changes how they size *forever*. Make it the loudest thing on the page.

## Common mistakes (flip-card material)

1. **"High win rate means I can bet bigger."** False. A 90% / 0.1:1 system has the same Kelly as a 10% / 9:1 system. Sizing is governed by *expectancy and variance*, not win rate alone.
2. **"Full Kelly is optimal so I should use it."** Theoretically yes, practically catastrophic. Full Kelly assumes you know your edge *precisely*. You don't. Thorp's documented practice is fractional Kelly — typically half — because real-world edge estimates are noisy upward (you overestimate). Half-Kelly costs ~25% of growth rate to buy a ~50% drawdown reduction.
3. **"Leverage is free if my edge is real."** Volatility drag scales with leverage². At 5× leverage in a 3% daily-vol market, you bleed ~1.1% per day to drag *before* the edge fights back.
4. **"My average return justifies the size."** Average (arithmetic) return is meaningless to a single-account compounding trader. The relevant quantity is *time-average geometric* return — the ergodicity argument. Two strategies can have identical arithmetic expected returns and one of them ruins you.
5. **"Risk-per-trade alone is enough."** No — you also need *risk-per-day* and *correlated-position* caps. Five 1%-risk trades that all go wrong on the same BTC dump is a 5% day; if those positions are correlated longs into a regime flip it's effectively a single 5% bet. SniperSight's position-caps stage exists exactly here.

## Edge cases & nuance

- **Ergodicity and single-account survival** — the paradigm shift. Casinos can use ensemble-average expected value because they run thousands of bets simultaneously. You cannot. Your single equity path either compounds or it doesn't, and the path matters. Taleb's "never cross a river that's on average four feet deep" captures it.
- **ATR-based sizing as volatility normalization** — fixed % stop across symbols means you risk identical dollars but *very different* probabilities. BTC's 1% stop is noise and a low-cap alt's 1% stop is signal. ATR-based stops: stop distance = k × ATR, position size = riskDollars / (stopDistance × pointValue). Makes 1R *mean the same thing* across assets and regimes.
- **Edge uncertainty → bet smaller** — clean theorem: if edge estimate has standard error σ_edge, effective Kelly should be discounted roughly by (1 − σ_edge²/edge²). High uncertainty → fractional Kelly approaches zero.
- **Risk-per-trade vs risk-per-day vs max-drawdown gating** — three different time horizons of the same concept. Per-trade caps individual bet size, per-day caps correlated-loss days, max-DD halts trading after equity drawdowns regardless of trade-level discipline.
- **Kelly bound on leverage** — Peters' result: for a log-normal asset with drift μ and volatility σ, the Kelly-optimal leverage is μ/σ². Past that, over-Kelly zone — guaranteed long-run loss even with positive drift.

## Authoritative sources

- **Primary**: [Kelly 1956 — A New Interpretation of Information Rate](https://www.princeton.edu/~wbialek/rome/refs/kelly_56.pdf); [Wikipedia](https://en.wikipedia.org/wiki/Kelly_criterion)
- **Primary**: [Ed Thorp — Understanding the Kelly Criterion](https://rybn.org/halloffame/PDFS/2008_Understanding_Kelly_New.pdf)
- **Primary**: [MacLean, Thorp, Ziemba — Good and Bad Properties of Kelly (Berkeley)](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf)
- **Primary**: [Matthew Downey — Why Fractional Kelly (with uncertainty simulations)](https://matthewdowney.github.io/uncertainty-kelly-criterion-optimal-bet-size.html)
- **Primary**: [Poundstone — Fortune's Formula](https://us.macmillan.com/books/9780374707088/fortunesformula/)
- **Primary**: [Ergodicity economics — Wikipedia](https://en.wikipedia.org/wiki/Ergodicity_economics); [Peters — Optimal leverage from non-ergodicity (arXiv)](https://arxiv.org/pdf/0902.2965)
- **Primary**: [Taleb — Logic of Risk Taking (Incerto)](https://medium.com/incerto/the-logic-of-risk-taking-107bf41029d3); [ergodicity tag](https://nassimtaleb.org/tag/ergodicity/); [Kelly explanation](https://nassimtaleb.org/2020/02/kelly-criterion/)
- **Primary**: [Naval — Kelly Criterion: Avoid Ruin](https://nav.al/kelly-criterion)
- **Vendor-neutral**: [Van Tharp R-multiples — TraderLion](https://traderlion.com/risk-management/r-and-r-multiples/); [Van Tharp Institute](https://vantharpinstitute.com/tharp-think-trading-concepts/)
- **Vendor-neutral**: [ATR-based stop placement — QuantVPS](https://www.quantvps.com/blog/using-average-true-range-for-stop-loss-placement); [Trader Sentiments ATR](https://tradersentiments.com/technical-analysis/average-true-range)
- **Vendor-neutral**: [Risk of Ruin — newtraderu](https://www.newtraderu.com/2021/03/13/risk-of-ruin-formula/); [Arca Labs](https://thearcalabs.com/en/insights/risk-of-ruin-trading/)
- **Vendor-neutral**: [Volatility drag in LETFs — Aptus Capital](https://aptuscapitaladvisors.com/leveraged-etfs-the-hidden-costs-of-volatility-drag/); [arXiv 2504.20116](https://arxiv.org/html/2504.20116v1)

## Interactive treatments (Phase 2)

1. **Kelly Curve Playground** *(Phase 1 hero — `<KellyCurve />`)* — inverted-U chart in dark cyan, full width. Two sliders: win rate (50–80%) and avg win/loss ratio (0.5–4×). Curve redraws live. Three regions shaded (cyan/amber/red), f* mark glows, 2×f* "zero growth" line is amber-dashed. Hover anywhere on the curve to see (a) geometric growth rate at that f, (b) estimated max drawdown over 1000 trades, (c) ruin probability over 1000 trades. Toggle overlays "Full Kelly" vs "Half Kelly" vs "Quarter Kelly" as labelled crosshairs.
2. **Monte Carlo Equity Curve Simulator** — three sliders: win rate, avg R, risk-per-trade %. On click, 100 simulated 200-trade equity curves render as semi-transparent cyan lines overlaid. Median curve solid amber, 5th-percentile worst curve solid red. Drag risk-per-trade up → curves fan out, variance balloons while median rises *and then collapses*. Live "% of paths that hit ruin" counter.
3. **Leverage Trap Visualizer** — slider for leverage (1× to 20×). Two side-by-side panels: underlying asset path (known volatile fixture, e.g., real BTC week) vs leveraged position path with vol drag baked in (`g = μL − (σL)²/2`). At 1× they track. At 3×, leveraged path lags. At 10×, collapses to zero on a flat-but-volatile sideways week. Counter shows "drag per day" and "expected days to halving."
4. **Ergodicity Demonstration** — Peters coin-flip experiment, animated. Two panels: "Ensemble (100 traders, 1 round each)" and "Time (1 trader, 100 rounds)." Same coin: +50% on heads, −40% on tails. Press button, both run. Ensemble: traders fan out, average wealth grows because lucky few skew mean. Time-series: single trader grinds toward zero. After 100 rounds, both means displayed. Same coin, opposite verdicts. Label: "this is why expected value lies to a single trader."
5. **R-Multiple Trade Journal Replay** — pulls real closed-trade data from bot's `trade_journal.jsonl`. Each trade is a vertical bar in chronological order, height = R-multiple result (+2R green up, −1R red down). Below: running expectancy (mean R) updated trade by trade with confidence band. Side panel computes Kelly fraction from realized W and avgWin/avgLoss — and compares to bot's *actual* risk-per-trade setting. If bot is overbetting realized Kelly, indicator turns red.
6. **Quiz / Calculator Hybrid** — three scenarios with pre-loaded sliders: "55% win rate, 1.5R avg win, 1R loss. What's full Kelly? Half?"; "Your edge estimate has ±20% uncertainty. How should you discount Kelly?"; "Your stop is 1×ATR but BTC's ATR just doubled. What happens to dollar risk if you don't adjust?" User submits, page reveals correct formula application step-by-step, then user drags inputs to play. Every answer ends with: "and here's where you'd land on the Kelly curve."

## Implementation notes

- **Phase 1**: prose + `<KellyCurve />`. **HUD-tier primitive** — also belongs in Bot Setup risk dialog. Build once, reuse.
- **Phase 2**: ergodicity demo is the prestige feature — it's the single most underappreciated concept in retail trading and the demo makes it visceral. Build it; the wow factor is enormous.
- **Cross-chapter ties**: directly references Ch 6 (expectancy formula); references Ch 7 (ATR-based sizing as regime normalization); R-multiple replay pulls from same telemetry the autopsy skill uses.
- **Numbers to sync**: per-mode `RegimePolicy.position_size_multiplier` values from `regime_policies.py`. Add `// SYNC` comment.
