# Chapter 5 — Wyckoff Cycle Phases

> **Backend ground truth**: `backend/strategy/smc/cycle_detector.py` (phase detection, DCL/WCL anchors); cross-references in `bos_choch.py:722` (cycle-bypass)
> **Phase 1 widget**: Scrubbable schematic timeline (accumulation)
> **Phase 2 widgets**: Spring-vs-breakdown quiz, Re-accumulation/distribution coin-flip, Cause-and-effect calculator, Composite-operator narration mode

## Core concept

The Wyckoff cycle describes how a single hypothetical "composite operator" moves price through four macro stages — **accumulation, markup, distribution, markdown** — by absorbing supply at lows and offloading it at highs. Each accumulation and distribution range is itself sub-divided into five micro-phases (A → E) marked by named events (PS, SC, AR, ST, Spring/UTAD, SOS/SOW, LPS/LPSY). The framework treats every range as a campaign with intent, not noise.

## Why it works (the underlying mechanic)

Institutional inventory cannot be built or sold in a single trade without moving price against the buyer/seller. So a campaign must span weeks — Phase B is long because **absorption is physically slow**. Springs and UTADs exist because the last block of supply (or demand) lives in retail stop-loss clusters just outside the range; the cheapest way to harvest it is to briefly trip them. This is why the structure is repeatable: it's a logistics problem, not a psychology one.

## Canonical visual example (SVG-buildable schematic)

**Accumulation**, left-to-right:

```
Down-trend → PS → SC → AR → ST → [Phase B chop, narrowing range]
          → Spring (poke below SC low) → Test (lower-vol retest of Spring low)
          → SOS (wide-spread up-bar through Creek) → BU / LPS (pullback to creek edge)
          → JAC (Jump Across the Creek) → Phase E markup
```

**Distribution** mirrors it:

```
Up-trend → PSY → BC → AR → ST → [Phase B chop]
        → UTAD (poke above range high) → ST_after_UTAD
        → SOW (wide-spread down-bar through Ice) → LPSY (weak rally back to ice)
        → Phase E markdown
```

**Event glossary** (16 symbols — frontend needs an icon glyph for each):

| Code | Meaning |
|------|---------|
| PS | Preliminary Support |
| SC | Selling Climax |
| AR | Automatic Rally |
| ST | Secondary Test |
| Spring | False breakdown below SC |
| Test | Low-vol retest of Spring |
| SOS | Sign of Strength |
| LPS | Last Point of Support |
| BU / BUEC | Back-Up to the Edge of the Creek |
| JAC | Jump Across the Creek |
| Creek / Ice | Range resistance / support metaphor |
| PSY | Preliminary Supply |
| BC | Buying Climax |
| UT / UTAD | Upthrust / Upthrust After Distribution |
| SOW | Sign of Weakness |
| LPSY | Last Point of Supply |

## Common mistakes (flip-card material)

1. **"The Spring always works."** No — a Spring that doesn't close back inside the range, or that prints on rising sell volume, is a *failed* Spring and signals continuation lower. A real Spring needs the *Test* afterward on dried-up volume.
2. **Calling Phase E early.** Operators see SOS and skip past the LPS / BU pullback. The pullback is what gives the markup its low-risk entry — without it you're chasing the wide-spread bar.
3. **Confusing re-accumulation with distribution.** Same shape, same Phase B chop, same Spring-or-UTAD test. The differentiator is the *prior trend direction* plus volume behavior. Until Phase C resolves, you genuinely cannot tell.
4. **Treating SC as "the bottom."** SC is where panic peaks, not where price bottoms. Final low usually prints later at the Spring, which can be a meaningful percentage below SC. Buying at SC and getting stopped out at Spring is the classic retail loss pattern.
5. **Looking for clean schematics on every chart.** The textbook accumulation rarely prints clean; what's testable is *which named events did appear* and in what order. Treat the schematic as a checklist, not a stencil.

## Edge cases & nuance

- **Re-accumulation vs distribution is structurally identical until Phase C.** The single biggest trap. Re-accumulations occur inside ongoing uptrends, repeatedly. The only reliable separator is the spring-vs-UTAD outcome plus volume on the breakout attempt.
- **Cause & Effect (Wyckoff's second law) gives a target.** Horizontal P&F count across the range projects how far Phase E should run. A small cause = small effect — a 3-day Phase B should not be expected to produce a multi-week markup.
- **Effort vs Result (third law) is your absorption tell.** Heavy volume + narrow range = supply or demand is being absorbed by the opposite side. This is the diagnostic for spotting Phase B turning into Phase C without waiting for the Spring.
- **Crypto-specific framing.** 24/7 markets, retail-heavy participation, and exchange-segmented liquidity make crypto unusually Wyckoff-friendly — the composite-operator narrative is more literal because the few large players genuinely do dominate flow on majors. But crypto compresses timeframes: a Phase B that took a stock market three months can complete in a week on BTC, and intraday charts (1h/4h) frequently print full schematics that traditional equity Wyckoff would only see on weeklies.

## Authoritative sources

- **Primary**: [Wyckoff Analytics — the method](https://www.wyckoffanalytics.com/wyckoff-method/) (Hank Pruden's institution)
- **Primary**: [Wyckoff Analytics — Schematics PDF](https://www.wyckoffanalytics.com/wp-content/uploads/2019/09/WyckoffSchematics-VisualTemplatesForMarketTimingDecisions.pdf) (canonical visual templates)
- **Primary**: [StockCharts ChartSchool — Wyckoff Method tutorial](https://chartschool.stockcharts.com/table-of-contents/market-analysis/wyckoff-analysis-articles/the-wyckoff-method-a-tutorial)
- **Primary**: [StockCharts — Distribution or Re-Accumulation? (2022)](https://stockcharts.com/articles/wyckoff/2022/03/distribution-or-reaccumulation-699.html)
- **Primary**: [StockCharts — Laws of Wyckoff](https://stockcharts.com/articles/wyckoff/2015/12/the-laws-of-wyckoff.html)
- **Vendor-neutral**: [Trading Wyckoff (Villahermosa) — phases, spring/shakeout, cause & effect, distribution](https://tradingwyckoff.com/en/wyckoff-method/)
- **Crypto-specific**: [Anna Coulling — Wyckoff cycles](https://www.annacoulling.com/stock-trader-tips/the-wyckoff-cycles-explained/) (primary crypto-Wyckoff voice)
- **Print primary**: Hank Pruden, *The Three Skills of Top Trading* — Pruden phase framework and nine-test method
- **Supplementary**: [Margex](https://margex.com/en/blog/wyckoff-chart-patterns-explained/), [Mind Math Money](https://www.mindmathmoney.com/articles/wyckoff-trading-method-complete-guide-to-smart-money-trading-2025), [TrendSpider](https://trendspider.com/learning-center/chart-patterns-wyckoff-accumulation/)

## Interactive treatments (Phase 2)

1. **Scrubbable schematic timeline** *(Phase 1 hero)* — horizontal SVG of full accumulation schematic with vertical "playhead" operator drags left to right. Each named event (PS, SC, AR, ST, Spring, Test, SOS, LPS) lights up cyan as head crosses it, with side panel narrating *composite operator's intent at that moment* — at SC: "absorb panicked retail supply at the bottom tick"; at Spring: "tag the obvious stop cluster, scoop the inventory shorts just dumped." Treat playhead as tactical scrubber, not media player.
2. **"Spring vs Breakdown" inline quiz** — three blind 4h candle snippets. Operator picks valid Spring, failed Spring, straight continuation. On submit, wrong picks reveal the diagnostic the operator missed — usually volume signature on the test bar. Score persists in localStorage; flip-card reveals *Effort vs Result* explanation.
3. **Re-accumulation / Distribution coin-flip** — two identical Phase B chops shown side-by-side with all labels stripped. Operator hovers each to reveal prior trend and volume curve, then commits a guess. Reveal shows Phase C resolution that disambiguated them.
4. **Cause-and-effect calculator** — operator draws horizontal P&F count across an accumulation range with the mouse; schematic projects Phase E's expected markup distance as a translucent cyan target box on the chart. Drag the count to shrink/extend the box.
5. **Composite operator narration mode** — toggle that overlays the chart with first-person voiceover-style captions ("I bought 40% of my position here…", "I'll let this drop to grab the rest of the stops…"). Cyan caption boxes float above the bars. Wows because the schematic *speaks*.

## Implementation notes

- **Phase 1**: prose + scrubbable schematic timeline. The schematic is iconic; making it interactive is the chapter's signature move.
- **Phase 2**: composite-operator narration is the prestige feature — it turns a static schematic into a story. Pair with cross-chapter overlay (`cross-chapter-patterns.md`).
- **Cross-chapter ties**: ties directly to Ch 4 (Springs = liquidity sweeps with extra structure context); Ch 3 (CHoCH off Spring = bot's cycle-bypass logic); the Composite Operator framing feeds the Master Fixture narration overlay.
- **Icon sheet required**: 16 named-event glyphs (PS, SC, AR, ST, Spring, Test, SOS, LPS, BU, JAC, UT, UTAD, SOW, LPSY, PSY, BC) plus Creek/Ice symbols. Treat as a deliverable for the lessons primitives layer.
