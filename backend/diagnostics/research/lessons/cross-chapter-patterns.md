# Cross-Chapter Patterns

These ideas weave multiple chapters together. Aesthetic invariant: every cross-chapter widget feels like one HUD readout, not three stacked components — single cyan/amber palette, single mono typeface, shared timeline scrubber across all of them where possible.

## 1. Master Fixture — the "Genesis Chart"

**The single highest-leverage cross-chapter idea in the entire library.**

One curated 60-bar BTC chart, stored as a JSON fixture at `src/content/lessons/_fixtures/master-btc.json`. The same chart is re-annotated as the operator navigates Chapters 1→4 (and referenced in 5, 7, 9):

- **Chapter 1**: highlights the OB candle in cyan
- **Chapter 2**: shades the FVG above it in amber
- **Chapter 3**: labels the BOS arrow that confirmed both
- **Chapter 4**: marks the EQH liquidity that got swept just before the OB formed
- **Chapter 5**: overlays Wyckoff Spring + SOS labels on the same sequence
- **Chapter 7**: highlights the regime-band transition during the impulse
- **Chapter 9**: overlays kill-zone vertical stripes showing the move happened inside London open

**Pedagogical payoff**: forces the realization that all the lenses are the same event viewed from different angles. The operator stops thinking of OBs, FVGs, sweeps, Wyckoff phases, and kill zones as separate concepts and starts seeing them as facets of one underlying mechanic.

**Build cost**: ~2 hours to curate the perfect 60-bar BTC fixture (must have clean BOS, clear FVG, refined OB, single sweep at EQH, and ideally land inside a kill zone). Pays off across 7 chapters.

**Component**: `<ChartFixture />` in `src/components/lessons/primitives/`. Accepts `lens` prop: `'ob' | 'fvg' | 'bos' | 'sweep' | 'wyckoff' | 'regime' | 'killzone'`. Each lens is a separate annotation overlay; the underlying candle data is shared.

## 2. The "Anatomy Stack" sidebar

Persistent right-rail vertical timeline showing each event on the Master Fixture in order:

```
Sweep → CHoCH → OB → FVG → Mitigation → Continuation BOS
```

Each stage is clickable: scrolls the chart to that exact bar, shows the bot's actual telemetry (confluence score contribution, grade). Functions as both pedagogy and a future-trade-recipe.

**Phase**: ships with Phase 2 (after Master Fixture is in place).

## 3. The "Now" Cockpit Tile

A small persistent dashboard widget showing, for the currently watched symbol:

- Current ICT session (with countdown to next kill-zone boundary)
- Current regime classification (trending/ranging/chop + ATR% number)
- Wyckoff-phase best-guess (with a confidence chip — "Phase B (medium)")

Updates each bar close. Tactical glance-value, like a fuel gauge — three numbers, three labels.

**Phase**: Phase 2; could be promoted to the HUD topbar later as a persistent readout.

## 4. Confluence Stacker

Empty chart starts as a candle skeleton. Toggle 4 buttons (OB / FVG / BOS / Sweep). Each toggle overlays its annotation in a unique color. As more lenses turn on, a "Confluence Score" gauge ticks up in the corner. At 4/4 lenses agreeing, score hits max and the gauge does a celebratory pulse.

Teaches the bot's actual confluence philosophy: stacked SMC signals > any single one.

**Phase**: Phase 2; reuses Master Fixture.

## 5. Tri-Layer Chart

A single 4h candle stream with three independently togglable overlays:

- **Wyckoff phase bands** (cyan-tinted backgrounds: PS-SC-AR shading, Phase B chop, Phase C/D markup)
- **Regime band colors** (green = quiet trend, amber = volatile trend, dim cyan = compression, red = chop)
- **Kill-zone vertical stripes** (semi-transparent amber bands for NY/London windows)

Operator toggles each layer with a hotkey. Reveals correlations the operator might not see staring at any single dimension — e.g., "does this symbol's Phase E markup typically launch inside the NY AM kill zone?"

Single chart, three dimensions, one cyan-glow reveal.

**Phase**: Phase 2.

## 6. Failure Mode Gallery

A horizontal scroller of 10 charts: each shows a "looks like an OB but isn't" / "looks like a sweep but is a breakout" / "looks like CHoCH but is internal noise" failure pattern. Hover reveals the bot's specific rejection reason from the actual codebase logs.

Builds anti-pattern intuition. Reuses fixture data from the rejection-survey skill.

**Phase**: Phase 2.

## 7. Time-Lapse "What the Bot Saw" Replay

Scrubber bar across a 4-hour window. As you drag, the chart reveals candle-by-candle the exact moment each SMC element fires. OB candle gets a cyan flash, displacement candle a green flash, FVG appears with a shimmer, BOS arrow draws itself. Mode picker top-left lets you replay the same data in OVERWATCH vs STRIKE vs SURGICAL — visibly different thresholds means visibly different patterns surface.

This single demo makes the bot's "mode is a configuration, not a process" mantra (CLAUDE.md §4) feel obvious.

**Phase**: Phase 2 (advanced — requires fixture replay infrastructure).

## 8. The Counterfactual Slider

A trade-replay tool: pick any historical trade the bot took. Three sliders at top: regime threshold, Wyckoff phase requirement, kill-zone strictness. Drag any slider and the chart re-renders showing whether this trade would have fired under the new gates.

The operator builds intuition for how each layer contributes — does kill-zone gating alone kill 60% of trades? Does Wyckoff-phase gating kill the right ones?

**Phase**: Phase 2 (advanced — requires journal replay).

## 9. Session-Phase Crosstab

A 5×5 matrix: rows = Wyckoff phase (A/B/C/D/E), columns = active session (Asia/London/NY-AM/NY-PM/Dead). Each cell shows empirical statistics for the chosen symbol over a chosen lookback: count of phase transitions in that session, average forward 24h return, hit-rate of spring/UTAD events. Reveals patterns like "Springs on BTC almost always print during London open" if true. If not true, equally valuable.

**Phase**: Phase 2 (data-heavy — needs aggregation pipeline).

## 10. Composite Operator Overlay (Long-Form)

A toggle that combines Ch 5's narration mode with kill-zone vertical stripes and regime band coloring. When ON, the operator gets a guided walkthrough of a historical campaign:

> "Composite operator accumulates through the Asian range… Spring printed at London open into low-vol regime… SOS during NY AM expansion… markup phase coincides with NY PM session."

A single chart that tells the entire story across all three frameworks. Bloomberg-style ticker captions at the bottom rotate through the narrative.

**Phase**: Phase 2 — the chapter's wow finale.

## 11. "Grade Lab" Interactive Grader

Drop any candle on the chart; the bot's grading logic runs live and returns Grade A/B/C with the actual scorer breakdown ("OB grade B: displacement_atr=0.7 [meets B], no_BOS_confirmation [downgrade A→B], near_swing=True [maintains B]"). Demystifies the bot's internal logic — operator sees exactly what tips a B to an A.

Uses the actual scoring functions from `order_blocks.py / fvg.py / bos_choch.py` so the lab is real, not simulated.

**Phase**: Phase 2 (requires Python→TS interop or backend endpoint).

## Aesthetic notes for implementation

- Color semantics (uniform across all cross-chapter widgets):
  - **Cyan** = active/bullish lens
  - **Amber** = warning/transition/secondary
  - **Red** = invalidated/ruin
  - **Dim grey** = stale
  - **Green** = bot success / target hit
  - **White** = operator-pinned

- SMC concepts are *built* for vector annotation — boxes for zones, dashed lines for levels, arrows for breaks. Avoid color-coding *meaning* with green/red (already overloaded by candles).

- Avoid Coursera/Lottie playfulness. Tactical, restrained, glow-pulse vocabulary. The chapters should feel like a Bloomberg "Education" tab inside the same cockpit, not a tutorial overlay on a kids' game.

- The HUD already speaks this dialect — see `src/styles/hud.css` chip classes (`chip-cyan`, `chip-amber`, etc.) and inline-style patterns in `src/pages/training/RangeBot.tsx`.
