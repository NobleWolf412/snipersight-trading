# SniperSight Lessons — Research Pack

Source-of-truth research dossier for the in-app `/training/lessons` strategy library. One file per chapter, plus cross-cutting files for shared widgets and the build plan.

**Created**: 2026-05-25
**Source agents**: three parallel general-purpose research agents, run 2026-05-25 (see conversation transcript)

## Index

| # | Chapter | File | Hero widget (Phase 1) |
|---|---------|------|------------------------|
| 1 | Order Blocks | [01-order-blocks.md](01-order-blocks.md) | Master Fixture w/ OB lens |
| 2 | Fair Value Gaps | [02-fvg.md](02-fvg.md) | Animated 3-candle FVG builder |
| 3 | BOS / CHoCH | [03-bos-choch.md](03-bos-choch.md) | Wick-vs-close break demo |
| 4 | Liquidity Sweeps | [04-liquidity-sweeps.md](04-liquidity-sweeps.md) | Sweep-vs-breakout twin |
| 5 | Wyckoff cycle phases | [05-wyckoff.md](05-wyckoff.md) | Scrubbable schematic timeline |
| 6 | Confluence scoring | [06-confluence.md](06-confluence.md) | `<WeightSliderPanel />` (HUD-tier) |
| 7 | Regime detection (% ATR) | [07-regime.md](07-regime.md) | `<RegimeQuadrant />` (HUD-tier) |
| 8 | Position sizing + risk | [08-position-sizing.md](08-position-sizing.md) | `<KellyCurve />` (HUD-tier) |
| 9 | Kill zones / session timing | [09-kill-zones.md](09-kill-zones.md) | 24h tactical clock-ring |

## Cross-cutting

- [cross-chapter-patterns.md](cross-chapter-patterns.md) — Master Fixture, tri-layer chart, Anatomy Stack sidebar, "Now" cockpit tile, Composite-Operator overlay
- [interactive-primitives.md](interactive-primitives.md) — six reusable widget specs (Kelly curve, Monte Carlo, Gate Funnel, Weight Sliders, Correlation heatmap, Risk-of-Ruin gauge)
- [BUILD_PLAN.md](BUILD_PLAN.md) — phased implementation (Path B), updated component organization, sub-step sequencing

## Add / remove / update model

- **Add a chapter** — drop a new `NN-<slug>.md` file here; add a `src/content/lessons/NN-<slug>.tsx` content module; append to manifest and snapshot states.
- **Remove a chapter** — delete from manifest. The research file stays as historical context unless explicitly archived.
- **Update a chapter** — edit one `.md` file here, then update the matching `.tsx` content module. Diff is per-chapter.
- **Re-research** — spawn the research agent again with a tighter brief; replace or append to the chapter file with a dated section header.

## Aesthetic invariants (apply to every chapter)

- Dark mono-font palette. Cyan/amber/green/red accents. Bloomberg-terminal × sci-fi cockpit.
- Animations ease in/out under 250ms, no bounce, no overshoot.
- Color semantics: cyan = active/bullish lens, amber = warning/transition, red = invalidated, dim grey = stale, green = bot success, white = operator-pinned.
- Never use Tailwind utility classes in HUD/lesson pages (memory standing fix).

## Source quality flag convention

When a chapter cites a source, it is one of three tiers:

- **Primary** — original or canonical (ICT tutorials, Wyckoff Analytics, academic papers, Kelly 1956, Thorp, Peters, López de Prado).
- **Vendor-neutral practitioner** — Bookmap, Equiti, broker education, StockCharts. Quality content, no upsell, useful for code-detectable definitions.
- **Popular pedagogy (supplementary)** — YouTuber/course sites. Content often correct but framed for upsell; cite alongside the primary, never standalone.

Every URL in this dossier was returned by a research agent that searched live; treat as accurate as of 2026-05-25 but expect link rot over 6+ months.
