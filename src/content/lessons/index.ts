import { lazy, type ComponentType, type LazyExoticComponent } from 'react';
import type { SourceRef } from '@/components/lessons/primitives';

export interface ChapterEntry {
  id: string;
  num: number;
  title: string;
  color: string;
  summary: string;
  sourceRefs: string[];
  sources: SourceRef[];
  Body: LazyExoticComponent<ComponentType>;
}

export const CHAPTERS: ChapterEntry[] = [
  {
    id: 'order-blocks',
    num: 1,
    title: 'Order Blocks',
    color: '#22d3ee',
    summary:
      'Last opposite-color candle before a structural break — institutional inventory marker.',
    sourceRefs: ['backend/strategy/smc/order_blocks.py'],
    sources: [
      { tier: 'primary',     title: 'ICT — Order Block tutorial',                  url: 'https://innercircletrader.net/tutorials/ict-order-block/' },
      { tier: 'primary',     title: 'ICT — Breaker Block',                          url: 'https://innercircletrader.net/tutorials/ict-breaker-block-trading/' },
      { tier: 'primary',     title: 'ICT — Mitigation Block',                       url: 'https://innercircletrader.net/tutorials/ict-mitigation-block-explained/' },
      { tier: 'vendor',      title: 'Bookmap — iceberg orders microstructure',     url: 'https://bookmap.com/blog/how-to-read-and-trade-iceberg-orders-hidden-liquidity-in-plain-sight' },
      { tier: 'vendor',      title: 'Liquidity Finder — Anatomy of a valid OB',    url: 'https://liquidityfinder.com/news/anatomy-of-a-valid-order-block-in-smart-money-concepts-67221' },
      { tier: 'supplementary', title: 'Daily Price Action — 3 OB rules',           url: 'https://dailypriceaction.com/blog/order-blocks/' },
    ],
    Body: lazy(() => import('./01-order-blocks')),
  },
  {
    id: 'fvg',
    num: 2,
    title: 'Fair Value Gaps',
    color: '#fbbf24',
    summary:
      'Three-candle imbalance — one-sided delivery leaves a band price returns to fill.',
    sourceRefs: ['backend/strategy/smc/fvg.py'],
    sources: [
      { tier: 'primary',     title: 'ICT — Fair Value Gap strategy',                 url: 'https://innercircletrader.net/tutorials/fair-value-gap-trading-strategy/' },
      { tier: 'primary',     title: 'ICT — Inversion FVG (IFVG)',                    url: 'https://innercircletrader.net/tutorials/ict-inversion-fair-value-gap/' },
      { tier: 'primary',     title: 'ICT — Balanced Price Range (BPR)',              url: 'https://innercircletrader.net/tutorials/ict-balanced-price-range-bpr/' },
      { tier: 'vendor',      title: 'TrendSpider — FVG learning center',             url: 'https://trendspider.com/learning-center/fair-value-gap-trading-strategy/' },
      { tier: 'vendor',      title: 'FluxCharts — Inversion FVG',                    url: 'https://www.fluxcharts.com/articles/Trading-Concepts/Price-Action/Inversion-Fair-Value-Gaps' },
      { tier: 'vendor',      title: 'QuestDB — Order book imbalance glossary',       url: 'https://questdb.com/glossary/order-book-imbalance/' },
    ],
    Body: lazy(() => import('./02-fvg')),
  },
  {
    id: 'bos-choch',
    num: 3,
    title: 'BOS / CHoCH',
    color: '#a78bfa',
    summary:
      'Break of Structure (continuation) vs Change of Character (reversal) — body close decides.',
    sourceRefs: ['backend/strategy/smc/bos_choch.py'],
    sources: [
      { tier: 'primary',     title: 'ICT — MSS vs CHoCH',                            url: 'https://innercircletrader.net/tutorials/mss-vs-choch/' },
      { tier: 'primary',     title: 'ICT — Internal & External Liquidity',           url: 'https://innercircletrader.net/tutorials/ict-internal-external-liquidity/' },
      { tier: 'vendor',      title: 'Mind Math Money — BOS vs CHoCH deep dive',      url: 'https://www.mindmathmoney.com/articles/break-of-structure-bos-and-change-of-character-choch-trading-strategy' },
      { tier: 'vendor',      title: 'Daily Price Action — SMC market structure',      url: 'https://dailypriceaction.com/blog/smc-market-structure/' },
      { tier: 'vendor',      title: 'FluxCharts — BOS explained',                    url: 'https://www.fluxcharts.com/articles/Trading-Concepts/Price-Action/Break-of-Structures' },
    ],
    Body: lazy(() => import('./03-bos-choch')),
  },
  {
    id: 'liquidity-sweeps',
    num: 4,
    title: 'Liquidity Sweeps',
    color: '#f472b6',
    summary:
      'Brief excursion past a swing to trigger stops, then closes back — failed = LRLR.',
    sourceRefs: ['backend/strategy/smc/liquidity_sweeps.py'],
    sources: [
      { tier: 'primary',     title: 'ICT — Liquidity Sweep vs Liquidity Run',        url: 'https://innercircletrader.net/tutorials/ict-liquidity-sweep-vs-liquidity-run/' },
      { tier: 'primary',     title: 'ICT — HRLR & LRLR',                             url: 'https://innercircletrader.net/tutorials/ict-hrlr-lrlr/' },
      { tier: 'primary',     title: 'ICT — Asian Range',                              url: 'https://innercircletrader.net/tutorials/ict-asian-range/' },
      { tier: 'vendor',      title: 'Bookmap — order flow phenomena',                url: 'https://bookmap.com/blog/order-flow-phenomena' },
      { tier: 'vendor',      title: 'Equiti — Liquidity sweeps explained',           url: 'https://www.equiti.com/sc-en/news/trading-ideas/liquidity-sweeps-explained-how-to-identify-and-trade-them/' },
      { tier: 'vendor',      title: 'FXNX — London Judas swing',                      url: 'https://fxnx.com/en/blog/ict-asian-range-liquidity-trading-london-judas-swing-trap' },
    ],
    Body: lazy(() => import('./04-liquidity-sweeps')),
  },
  {
    id: 'wyckoff',
    num: 5,
    title: 'Wyckoff Cycle',
    color: '#34d399',
    summary:
      'Accumulation → markup → distribution → markdown. Composite operator runs the campaign.',
    sourceRefs: ['backend/strategy/smc/cycle_detector.py', 'backend/strategy/smc/bos_choch.py:722'],
    sources: [
      { tier: 'primary',     title: 'Wyckoff Analytics — the method',                url: 'https://www.wyckoffanalytics.com/wyckoff-method/' },
      { tier: 'primary',     title: 'Wyckoff Schematics PDF',                         url: 'https://www.wyckoffanalytics.com/wp-content/uploads/2019/09/WyckoffSchematics-VisualTemplatesForMarketTimingDecisions.pdf' },
      { tier: 'primary',     title: 'StockCharts — Wyckoff Method tutorial',          url: 'https://chartschool.stockcharts.com/table-of-contents/market-analysis/wyckoff-analysis-articles/the-wyckoff-method-a-tutorial' },
      { tier: 'primary',     title: 'StockCharts — Distribution or Re-Accumulation', url: 'https://stockcharts.com/articles/wyckoff/2022/03/distribution-or-reaccumulation-699.html' },
      { tier: 'vendor',      title: 'Trading Wyckoff — phases & spring',              url: 'https://tradingwyckoff.com/en/wyckoff-method/' },
      { tier: 'vendor',      title: 'Anna Coulling — Wyckoff cycles (crypto)',        url: 'https://www.annacoulling.com/stock-trader-tips/the-wyckoff-cycles-explained/' },
    ],
    Body: lazy(() => import('./05-wyckoff')),
  },
  {
    id: 'confluence',
    num: 6,
    title: 'Confluence Scoring',
    color: '#22d3ee',
    summary:
      'Weighted-sum scorer with hard pre-scoring gates — more factors ≠ better unless they are independent.',
    sourceRefs: ['backend/strategy/confluence/scorer.py:539-694'],
    sources: [
      { tier: 'primary',     title: 'López de Prado — Advances in Financial ML (SSRN)', url: 'https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3104847' },
      { tier: 'primary',     title: 'Bailey & López de Prado — Deflated Sharpe',        url: 'https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551' },
      { tier: 'primary',     title: 'Carhart four-factor model',                         url: 'https://en.wikipedia.org/wiki/Carhart_four-factor_model' },
      { tier: 'vendor',      title: 'Robot Wealth — Quant signal trade-offs',           url: 'https://robotwealth.com/quant-signal-trade-offs-in-the-real-world/' },
      { tier: 'vendor',      title: 'StableBread — Fama-French / Carhart analysis',     url: 'https://stablebread.com/fama-french-carhart-multifactor-models/' },
      { tier: 'supplementary', title: 'LuxAlgo — Trading indicators without clutter',   url: 'https://www.luxalgo.com/blog/multiple-indicators-without-overcomplicating-chart/' },
    ],
    Body: lazy(() => import('./06-confluence')),
  },
  {
    id: 'regime',
    num: 7,
    title: 'Regime Detection',
    color: '#60a5fa',
    summary:
      'Trend × volatility quadrant. Percentage-ATR normalizes across symbols; absolute ATR misleads.',
    sourceRefs: ['backend/analysis/regime_detector.py', 'backend/analysis/regime_policies.py'],
    sources: [
      { tier: 'primary',     title: 'Hamilton — Regime-Switching Models (Palgrave)',    url: 'https://econweb.ucsd.edu/~jhamilto/palgrav1.pdf' },
      { tier: 'primary',     title: 'Bitcoin Bayesian HMM (arXiv 2011.03741)',          url: 'https://arxiv.org/pdf/2011.03741' },
      { tier: 'primary',     title: 'Mandelbrot — Fractal Markets overview',            url: 'https://accountend.com/understanding-mandelbrots-fractal-market-hypothesis-a-new-perspective-on-financial-markets/' },
      { tier: 'primary',     title: 'ADX — Wikipedia',                                  url: 'https://en.wikipedia.org/wiki/Average_directional_movement_index' },
      { tier: 'vendor',      title: 'QuantifiedStrategies — Choppiness Index',          url: 'https://www.quantifiedstrategies.com/choppiness-index/' },
      { tier: 'vendor',      title: 'Macrosynergy — Hurst exponent in finance',         url: 'https://macrosynergy.com/research/detecting-trends-and-mean-reversion-with-the-hurst-exponent/' },
      { tier: 'vendor',      title: 'Marketlab — ATR & ATR%',                            url: 'https://marketlab-academy.org/en/library/atr-and-atr-percent/' },
    ],
    Body: lazy(() => import('./07-regime')),
  },
  {
    id: 'position-sizing',
    num: 8,
    title: 'Position Sizing',
    color: '#fbbf24',
    summary:
      'Kelly criterion, fractional Kelly, ergodicity. Past 2·f* the geometric growth rate flips negative.',
    sourceRefs: ['backend/strategy/risk_engine.py', 'backend/analysis/regime_policies.py'],
    sources: [
      { tier: 'primary',     title: 'Kelly 1956 — A New Interpretation of Information Rate', url: 'https://www.princeton.edu/~wbialek/rome/refs/kelly_56.pdf' },
      { tier: 'primary',     title: 'Ed Thorp — Understanding the Kelly Criterion',           url: 'https://rybn.org/halloffame/PDFS/2008_Understanding_Kelly_New.pdf' },
      { tier: 'primary',     title: 'MacLean, Thorp, Ziemba — Good/Bad Properties of Kelly',   url: 'https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf' },
      { tier: 'primary',     title: 'Peters — Optimal leverage from non-ergodicity',           url: 'https://arxiv.org/pdf/0902.2965' },
      { tier: 'primary',     title: 'Taleb — Logic of risk-taking',                            url: 'https://medium.com/incerto/the-logic-of-risk-taking-107bf41029d3' },
      { tier: 'vendor',      title: 'Van Tharp R-multiples (TraderLion)',                     url: 'https://traderlion.com/risk-management/r-and-r-multiples/' },
      { tier: 'vendor',      title: 'Naval — Kelly Criterion: avoid ruin',                    url: 'https://nav.al/kelly-criterion' },
    ],
    Body: lazy(() => import('./08-position-sizing')),
  },
  {
    id: 'kill-zones',
    num: 9,
    title: 'Kill Zones',
    color: '#fbbf24',
    summary:
      'Session windows where institutional flow concentrates. London Open and NY AM dominate.',
    sourceRefs: ['backend/strategy/smc/sessions.py'],
    sources: [
      { tier: 'primary',     title: 'ICT — Master Kill Zones',                          url: 'https://innercircletrader.net/tutorials/master-ict-kill-zones/' },
      { tier: 'primary',     title: 'ICT Killzone times & DST',                         url: 'https://icttrading.org/ict-kill-zone-time/' },
      { tier: 'primary',     title: 'ICT — Asian Range',                                url: 'https://innercircletrader.net/tutorials/ict-asian-range/' },
      { tier: 'primary',     title: 'Periodicity in crypto volatility (arXiv 2109.12142)', url: 'https://arxiv.org/pdf/2109.12142' },
      { tier: 'vendor',      title: 'Liquidity Finder — stop hunting at session levels', url: 'https://liquidityfinder.com/news/stop-hunting-101-how-swing-highs-and-lows-become-liquidity-traps-b599c' },
      { tier: 'vendor',      title: 'FXNX — London Judas swing pattern',                 url: 'https://fxnx.com/en/blog/ict-asian-range-liquidity-trading-london-judas-swing-trap' },
    ],
    Body: lazy(() => import('./09-kill-zones')),
  },
];

export const CHAPTER_BY_ID: Record<string, ChapterEntry> = Object.fromEntries(
  CHAPTERS.map((c) => [c.id, c]),
);
