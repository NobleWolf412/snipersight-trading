# Chapter 3 — Break of Structure / Change of Character

> **Backend ground truth**: `backend/strategy/smc/bos_choch.py` (esp. detector `:203`, 4-swing validator `:129`, volume gating `:446` `:511`, cycle bypass `:722`)
> **Phase 1 widget**: Wick-vs-close break demo
> **Phase 2 widgets**: Side-by-side BOS vs CHoCH toggle, Swing-depth slider, 4-swing pattern matcher, Internal/external highlighter, Cycle bypass demo

## Core mechanic

- **Swing high** = a 3-bar pattern where the middle bar's high exceeds both neighbors. **Swing low** = symmetric.
- **BOS** = a candle **closes** beyond the most recent swing in the trend direction (uptrend → close above last swing high; downtrend → close below last swing low).
- **CHoCH** = a candle closes beyond the most recent swing **against** the trend direction (uptrend → close below last swing low; downtrend → close above last swing high).

**Mnemonic**: BOS = continuation (with trend), CHoCH = reversal (against trend).

**What the bot does** (two-mode detection):

- **Simple mode** (STRIKE, SURGICAL): state-machine — track last swing high/low, fire when close clears by ≥ `min_break_distance_atr` (default 0.5 ATR).
- **4-swing mode** (OVERWATCH, STEALTH): demands a confirmed alternating swing sequence `[-1, 1, -1, 1]` (Low-High-Low-High) for bullish BOS, with ascending levels (`LL < HL < LH < HH`). Filters noise but slower.

Volume gating mode-aware: OVERWATCH requires 1.5× avg volume on BOS; STEALTH requires 1.3× on both; STRIKE skips volume entirely. Critically, **the trend flip is unconditional** even if the volume gate suppresses the *signal* — the structure broke whether or not the bot trades it.

## Why it works (microstructure)

Structure is the cleanest expression of who's in control. A BOS confirms the dominant cohort still has inventory to push; a CHoCH confirms the opposite cohort has accumulated enough size to absorb continuation attempts and reverse. This is the modern restatement of **Dow Theory** plus Wyckoff's phase transitions: accumulation → markup is signaled by the first bullish CHoCH off a range low; distribution → markdown by the first bearish CHoCH off a range high.

A wick through a swing without a close is a **liquidity sweep**, not a break. This is the single most important pedagogical distinction in SMC structure.

## Canonical visual example

Twelve-bar uptrend then reversal:

- Bars 1–6: clean LH-HL-LH-HH-HL-HH sequence (canonical uptrend)
- Bar 7: price tags last swing high but closes inside → no BOS yet
- Bar 8: closes above last swing high → **BOS bullish, continuation**
- Bars 9–10: pullback making a new HL (still uptrend)
- Bar 11: closes below the bar-9 HL → **CHoCH bearish, structure broken**
- Bar 12: continuation lower confirming new downtrend

**SVG treatment**: dynamic labels on each swing point (HH/HL/LH/LL), green "BOS" tag pops on bar 8, amber "CHoCH" tag pops on bar 11. Highlight broken levels with horizontal dashed lines that pulse when crossed.

## Common mistakes (flip-card material)

1. **Calling a wick-through a BOS.** Body close is required. Bot enforces this; most retail SMC indicators don't.
2. **Marking swings on every micro-pivot.** A "3-bar swing" is the minimum, but on lower TFs you need a higher fractal depth (bot scales `swing_lookback` per TF). Otherwise every candle is a swing and BOS fires constantly.
3. **Confusing BOS with CHoCH direction.** Mnemonic again: BOS = continuation (with trend), CHoCH = reversal (against trend). CHoCH in an uptrend means "turning bearish".
4. **Treating internal-range BOS the same as external-range BOS.** Break of an *internal* (minor) swing inside a larger range is much weaker than breaking the *external* (range-boundary) swing. ICT calls these IRL and ERL; the dealing range rotates external→internal→external.
5. **Single-TF structure analysis.** A 5m CHoCH inside a 4h uptrend is a pullback opportunity, not a reversal. Bot's HTF alignment check (`_check_choch_htf_alignment`) is the algorithmic version of this discipline.

## Edge cases & nuance

- **MSS vs BOS terminology**: Strict ICT calls trend reversals an **MSS (Market Structure Shift)**; SMC ecosystem calls them **CHoCH**. Same thing, different lineage.
- **Internal vs external structure**: Internal = swings *within* the current dealing range; External = the range boundaries themselves. Internal BOS is part of rotation; external BOS is regime change. Bot doesn't yet distinguish these explicitly — open enhancement.
- **Cycle-aware CHoCH bypass**: at a confirmed Wyckoff DCL/WCL (Daily/Weekly Cycle Low), bullish CHoCH is valid even without HTF alignment — the cycle itself is the alignment (`bos_choch.py:722`). Powerful and unusual edge.
- **Failed BOS = strong CHoCH signal**: if the bullish BOS candle fails to follow through and the next candle closes back below the broken swing, that's a fake breakout *and* a high-probability bearish CHoCH setup.

## Authoritative sources

- **Primary**: [ICT MSS vs CHoCH](https://innercircletrader.net/tutorials/mss-vs-choch/) — terminology origin
- **Primary**: [ICT IRL & ERL](https://innercircletrader.net/tutorials/ict-internal-external-liquidity/) — internal vs external structure
- **Vendor-neutral**: [Mind Math Money — BOS vs CHoCH comprehensive guide](https://www.mindmathmoney.com/articles/break-of-structure-bos-and-change-of-character-choch-trading-strategy)
- **Vendor-neutral**: [Daily Price Action — SMC Market Structure](https://dailypriceaction.com/blog/smc-market-structure/)
- **Vendor-neutral**: [FluxCharts — BOS Explained](https://www.fluxcharts.com/articles/Trading-Concepts/Price-Action/Break-of-Structures)
- **Wyckoff origin**: [Mind Math Money Wyckoff Guide](https://www.mindmathmoney.com/articles/wyckoff-trading-method-complete-guide-to-smart-money-trading-2025)

## Interactive treatments (Phase 2)

1. **Side-by-side BOS vs CHoCH on same chart** — toggle button at top; same 12-bar fixture re-annotates with different swing labels and break markers depending on which definition is active.
2. **Wick-vs-close break demo** *(Phase 1 hero)* — single swing high level, drag price up; bar 1 wicks above and closes below (label: "sweep — no break"), bar 2 wicks above and closes above (label: "BOS confirmed"). Live counters tick.
3. **Swing-depth slider** — same chart, slider for `swing_lookback = 1..20`. Watch how many swings get detected. At lookback=1, every candle is a swing.
4. **4-swing pattern matcher** — show 8 alternating swings; only the last 4 matter; user slides a "window" along the sequence and watches bot's `[-1,1,-1,1]` validator light up green only when ascending structure is satisfied.
5. **Internal vs external highlight** — chart with a clearly bounded range; click "show internal" → all minor swings shade grey; click "show external" → range high/low pulse cyan. BOS markers tagged "internal break" vs "external break".
6. **Cycle bypass demo** — load Wyckoff accumulation example; on spring low, fire bullish CHoCH and show bot's bypass logic with a green "cycle bypass active" indicator overriding the HTF check.

## Implementation notes

- **Phase 1**: prose + wick-vs-close demo. This is the single most-misunderstood SMC distinction; the demo earns the hero slot for its leverage.
- **Phase 2**: side-by-side BOS-vs-CHoCH toggle is second most impactful (same chart, different lens — pure pedagogy).
- **Cross-chapter ties**: Master Fixture (BOS arrow on it is the same arrow that confirms Ch 1 OB and Ch 2 FVG); shares `<FlipCard />`, `<SourceList />`.
- **Numbers to sync**: `min_break_distance_atr=0.5`, volume gates (1.5× OVERWATCH / 1.3× STEALTH) from `bos_choch.py`. Add `// SYNC` comment.
