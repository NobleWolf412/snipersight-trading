# Chapter 9 — Kill Zones / Session Timing

> **Backend ground truth**: `backend/strategy/smc/sessions.py`; HUD reuses `KillZoneStrip` primitive
> **Phase 1 widget**: 24h tactical clock-ring
> **Phase 2 widgets**: Asian range simulator, DST drift slider, Volume-by-hour ring overlay, Kill-zone backtest strip

## Core concept

ICT kill zones are specific intraday windows when institutional order flow concentrates — primarily the London open, the New York AM open, the New York PM session, and the London close. Combined with the **Asian range** (overnight low-volatility consolidation), they form a daily rhythm where most volume, volatility, and liquidity-seeking moves cluster.

In 24/7 crypto these windows still matter because traditional finance desks anchor crypto liquidity to TradFi hours.

## Why it matters — the underlying mechanic

Session opens have higher volume because that's when desks at major financial centers arrive, hedge overnight risk, and execute orders that accumulated while their book was offline. London open is the largest forex injection of the day; NY open layers US equity-correlated flows on top.

Crypto isn't structurally tied to these hours, but empirically **Bitcoin volume and volatility peak during US/European business hours** and trough in the Asia gap between the NY close and the Tokyo open — confirmed by published intraday studies.

## Canonical visual — 24-hour clock-face

A 24-hour clock-face rendered as a glowing ring, segmented into arcs:

| Window | NY time (ET) | Glow tier |
|---|---|---|
| Asian Kill Zone | 20:00 – 00:00 | Dim cyan |
| London Open | 02:00 – 05:00 | **Bright cyan (primary)** |
| NY AM Open | 08:30 – 11:00 | **Bright amber (primary)** |
| London Close | 10:00 – 12:00 (overlaps NY AM) | Amber, secondary |
| NY PM Session | 13:30 – 16:00 | Amber, secondary |

Brightness of each arc is modulated by *historical volume-by-hour* for the displayed symbol — kill zones literally glow brighter than the dead hours. Underneath: a sparkline of average true range bucketed by hour-of-day across the last 90 days.

## Common mistakes (flip-card material)

1. **"Kill zone times are GMT."** They aren't — ICT defines them in New York local time (ET). If you live elsewhere, your local equivalents shift twice a year as US and UK DST schedules drift out of phase. There's a ~1-week window in late October/early November where NY is on EDT and London is on GMT, making the time gap 4h instead of 5h.
2. **"Highest volume = best entries."** Highest volume usually means widest stops are required. Kill zones produce *opportunities*, not *certainties*. Without confluence, an entry inside a kill zone is just an entry inside higher volatility.
3. **"Asian session is dead."** It's lower-volatility *for forex majors*, but for JPY pairs and Asia-domiciled altcoins it's the primary session. And the Asian range itself is the setup for the London-open breakout that hunts its highs and lows.
4. **"London open = London breakout."** The classic London-open behavior is *first* to sweep the Asian range high *or* low (a liquidity grab on overnight stops), *then* reverse and run in the opposite direction. Naive breakout entries get caught in the sweep — the **London Judas swing**.
5. **"Crypto doesn't care about TradFi hours."** Empirically false. Crypto volume and realized volatility peak during US/EU business hours; the Asia gap between NY close (~17:00 ET) and Tokyo open (~19:00-20:00 ET) is consistently the quietest period.

## Edge cases & nuance

- **24/7 markets and session anchors.** CME Bitcoin futures move to 24/7 trading on **2026-05-29** — the weekend-gap era ends. Historically, the Friday-Sunday CME futures close created predictable Monday gaps that filled ~70-80% of the time. The session-anchor *concept* survives the CME change (TradFi desks still operate on business hours); the gap-fill pattern does not. Cite as historical context, do not teach as live edge.
- **Day-of-week effects.** Monday open often sees outsized moves from weekend news absorption; Friday late-NY drifts on position closing; mid-week (Tue-Thu) is typically the highest-conviction trading window in TradFi-anchored crypto flow.
- **Funding-rate timing on perps.** Phemex (and most exchanges) settle funding every 8 hours, on a clock aligned to UTC 00:00/08:00/16:00. Funding flips don't coincide with kill zones but create their own micro-volatility spikes — relevant context for any kill-zone visualization that overlays perp data.
- **Liquidity grabs cluster at session boundaries.** The most reliable sweep targets on BTC/ETH are previous-day high/low, previous-week high/low, and the Asian range extremes — all raided in the first hour of London or NY. This is the mechanical reason kill zones produce reversals, not just breakouts.

## Authoritative sources

- **Primary**: [Inner Circle Trader — official kill zones tutorial](https://innercircletrader.net/tutorials/master-ict-kill-zones/) (Huddleston)
- **Primary**: [ICT Killzone times & DST guide](https://icttrading.org/ict-kill-zone-time/)
- **Primary**: [ICT Asian Range](https://innercircletrader.net/tutorials/ict-asian-range/)
- **Academic**: [Bitcoin intraday dynamics paper (University of Reading)](https://centaur.reading.ac.uk/81745/3/2.R&R.Manuscript.pdf)
- **Academic**: [Time-of-Day Periodicities of Bitcoin Trading Volume (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S1544612319301904)
- **Academic**: [Periodicity in Cryptocurrency Volatility and Liquidity (arXiv 2109.12142)](https://arxiv.org/pdf/2109.12142)
- **Vendor-neutral**: [Liquidity Finder — stop hunting at session highs/lows](https://liquidityfinder.com/news/stop-hunting-101-how-swing-highs-and-lows-become-liquidity-traps-b599c)
- **Vendor-neutral**: [Phemex — funding-rate explainer](https://phemex.com/academy/what-is-funding-rate-in-crypto-futures)
- **Vendor-neutral**: [Trading Finder — ICT Asian range strategy](https://tradingfinder.com/education/forex/ict-asian-range-trading-strategy/)
- **Historical context** (post-2026-05-29 obsolete): [Phemex CME gap explainer](https://phemex.com/academy/cme-futures-gap); [CME 24/7 announcement](https://phemex.com/blogs/cme-crypto-24-7-bitcoin-futures)
- **Supplementary**: [Trading Rage](https://tradingrage.com/learn/ict-killzone-explained); [Complete Trader's Edge](https://completetradersedge.com/ict-kill-zones-trading-hours/); [EBC Financial](https://www.ebc.com/forex/what-are-ict-killzone-times-simple-trading-hours-guide). Many are course-promotion sites — content correct, framed for upsells.

## Interactive treatments (Phase 2)

1. **24h tactical clock-ring** *(Phase 1 hero)* — polar SVG clock with four kill-zone arcs glowing at their ET times. Pulsing "NOW" indicator sweeps continuously, brighter when inside a kill zone. Hover any arc to expand a panel showing that zone's historical ATR%, average volume multiple vs daily mean, and top three liquidity-sweep targets typically hit. Aesthetic: B-2 cockpit timer.
2. **Asian range simulator** — operator drags Asian session high and low markers on sandbox candle chart. As London opens, simulator runs procedural London-sweep based on historical sweep direction probabilities for that symbol. Candle stream replays, sweep tags one of operator's lines, reverses. Visceral way to learn "first sweep then reverse" pattern.
3. **DST drift slider** — timeline strip across the year showing UTC equivalents of all four kill zones for each calendar day. 1-week DST-mismatch window in late October highlighted in amber. Operator scrubs through year and watches kill zones shift in their *local* timezone — drives home that windows are anchored to NY, not "clock on the wall."
4. **Volume-by-hour ring overlay** — two overlaid polar plots: outer ring = ICT kill-zone definitions; inner ring = empirical hourly volume curve for displayed symbol over last 30/60/90 days. Operator toggles symbols (BTC, ETH, mid-cap alt) to see which respect TradFi sessions and which run on Asia-dominant flow. Reveals when theory matches reality and when it doesn't.
5. **Kill-zone vs no-kill-zone backtest strip** — long horizontal strip showing every 4h candle for last 90 days, color-coded by whether its open fell inside any kill zone. Side panel shows aggregate stats (win rate, avg move size) for entries in vs out. Pure data-driven kill-zone validation.

## Implementation notes

- **Phase 1**: prose + 24h tactical clock-ring. The clock is iconic enough to anchor the chapter; volume modulation on the arcs gives it data backing.
- **Phase 2**: Asian range simulator is the most teachable — the London Judas swing is counterintuitive and animation makes it click.
- **CME-gap content**: included only as historical context in "Edge cases" — not a Phase 2 widget. The 2026-05-29 24/7 switch decommissions the pattern. Do not build the CME-gap radar widget originally suggested by the research agent.
- **Cross-chapter ties**: Asian range simulator references Ch 4 (Liquidity Sweeps); clock-ring feeds the cross-chapter Tri-Layer chart (kill-zone vertical stripes); session-volatility math references Ch 7 (Regime).
- **Implementation invariants**: kill-zone times in code must be stored in ET with explicit DST handling, not UTC offsets. Use `date-fns-tz` with the `America/New_York` zone; never hard-code `-5` or `-4`.
