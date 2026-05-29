# Interactive Primitives — Reusable Widget Specs

Six widgets that span multiple chapters (and survive into future quant chapters). Five of the six earn promotion to **HUD-tier** (`src/components/hud/`) because they have non-lesson consumers. One is lesson-scoped (`src/components/lessons/primitives/`).

## Tier policy

- **HUD-tier** (`src/components/hud/`) — widget has a non-lesson consumer right now (or has a credible one within 1-2 sprints). Exposed in `src/components/hud/index.ts` barrel.
- **Lesson primitive** (`src/components/lessons/primitives/`) — widget is reused across ≥2 chapters but has no non-lesson consumer.
- **Chapter widget** (`src/components/lessons/widgets/`) — widget appears in exactly one chapter. Promote when a second consumer emerges.

Promotion is one-way and compile-safe (TypeScript catches orphan refs).

---

## 1. `<KellyCurve />` — HUD-tier

Renders the inverted-U log-growth curve as an SVG.

**Props**:
```ts
{
  winRate: number;            // 0–1
  payoffRatio: number;        // avgWin / avgLoss
  bettingFraction?: number;   // 0–1, optional vertical marker
  showZones?: boolean;        // shade cyan/amber/red
  compact?: boolean;          // inline mini-chart vs hero
  className?: string;
}
```

**Computes internally**: `f*`, `g(f)`, 2×f* boundary.

**Consumers**:
- **Lesson Chapter 8** (Position Sizing) — hero widget
- **Bot Setup** risk dialog (post-Phase 1) — show operator where their current risk-per-trade lands on the curve

**Lives at**: `src/components/hud/KellyCurve/`

---

## 2. `<EquityCurveMonteCarlo />` — HUD-tier (eventually) / starts in lessons

Generates N simulated equity curves given trade statistics.

**Props**:
```ts
{
  winRate: number;
  avgWinR: number;
  avgLossR: number;
  riskPerTrade: number;       // 0–1
  numTrades: number;          // default 200
  numSimulations: number;     // default 100
  seed?: number;              // reproducibility for snapshot tests
  onStats?: (stats: McStats) => void;
}
```

Renders N overlaid semi-transparent SVG paths; median bolded amber, 5th-percentile bolded red. Emits `{ medianFinal, worst5DD, ruinProbability }` via callback.

**Consumers**:
- **Lesson Chapter 8** (Position Sizing) — playground widget
- **Bot Setup** — "what does this risk-per-trade do to long-run paths" preview (Phase 2)
- **Trade Journal** lifetime aggregate page — "extrapolate forward" Monte Carlo (Phase 2+)

**Lives at**: Start in `src/components/lessons/primitives/EquityCurveMonteCarlo/`; promote to `src/components/hud/` when the second consumer ships.

---

## 3. `<WeightSliderPanel />` — HUD-tier

N sliders, one per factor, constrained so weights sum to 1.0 (auto-renormalize on drag).

**Props**:
```ts
{
  factors: Array<{ name: string; subScore: number; baseWeight: number }>;
  threshold: number;
  comparisonProfiles?: Array<{ name: string; weights: Record<string, number> }>;
  onChange?: (weights: Record<string, number>, composite: number, passes: boolean) => void;
}
```

Renders slider rail with current value (amber tick) and baseline (ghost tick). Composite score + pass/fail chip emitted live.

**Consumers**:
- **Lesson Chapter 6** (Confluence) — hero widget
- **Scanner Setup** — calibration tool for tuning live weights (Phase 2 — would replace manual `tune-confluence-weights` skill UX)
- **Bot Setup** — preview pane for mode profile selection

**Lives at**: `src/components/hud/WeightSliderPanel/`

---

## 4. `<GateFunnel />` — HUD-tier

Vertical pipeline visualization for filter chains with surviving/rejected counts.

**Props**:
```ts
{
  gates: Array<{
    name: string;
    predicate: string;          // human-readable description
    threshold?: string | number;
    sourceRef?: string;         // backend file:line reference
  }>;
  flow: Array<{
    gateIndex: number;
    survived: number;
    rejected: number;
    rejectReasons?: Record<string, number>;
  }>;
  initialCount: number;
  animateDrops?: boolean;
}
```

Animates signals as drops falling through each gate. Click any gate to expand the predicate detail. **Mass-conservation assertion** baked in: sum of survivors at gate N + sum of rejected at all gates ≤ N must equal `initialCount`. Asserted at render and displayed as small green tick.

**Consumers**:
- **Lesson Chapter 6** (Confluence) — pre-scoring gate visualizer
- **Scanner forensics** (Phase 2) — "why didn't this signal fire" debugger; reuses rejection-forensics agent output
- **Bot Status** (Phase 3) — live cycle gate-funnel readout

**Lives at**: `src/components/hud/GateFunnel/`

---

## 5. `<FactorCorrelationHeatmap />` — Lesson primitive

N×N grid SVG, cells colored on a red→black→cyan diverging scale.

**Props**:
```ts
{
  factors: string[];
  correlationMatrix: number[][];   // NxN, values in [-1, 1]
  highlightFactor?: string;         // dim all but this row/col
  onCellHover?: (i: number, j: number, value: number) => void;
}
```

Symmetry enforced (`matrix[i][j] === matrix[j][i]`) with a runtime assertion.

**Consumers**:
- **Lesson Chapter 6** (Confluence) — factor correlation
- **Lesson Chapter 7** (Regime) — indicator correlation across regimes (potential)
- **Lesson Chapter 8** (Position Sizing) — correlated-position risk visualization (potential)

**Lives at**: `src/components/lessons/primitives/FactorCorrelationHeatmap/`. No HUD consumer yet — keep lesson-scoped until one emerges.

---

## 6. `<RiskOfRuinGauge />` — HUD-tier

Single semi-circular gauge with needle position computed from trade stats.

**Props**:
```ts
{
  winRate: number;
  avgWinR: number;
  avgLossR: number;
  riskPerTrade: number;
  targetDrawdownPct?: number;    // default 50%
  numTrades?: number;            // default 1000
  compact?: boolean;
}
```

Gauge zones: 0–5% cyan ("safe"), 5–20% amber ("acceptable"), 20%+ red ("over-betting"). Numerical readout in mono font. Tooltip on hover explains the formula.

**Consumers**:
- **Lesson Chapter 8** (Position Sizing) — inline beside Kelly curve
- **Bot Setup** — live readout next to risk-per-trade slider (Phase 2)
- **Trade Journal** — "current config carries X% ruin risk over next 1000 trades" (Phase 2)

**Lives at**: `src/components/hud/RiskOfRuinGauge/`

---

## 7. `<RegimeQuadrant />` — HUD-tier (not in original 6, but earns the tier)

2D plot (X = trend strength, Y = normalized volatility) with live moving dot.

**Props**:
```ts
{
  symbol: string;
  trendStrength: number;     // ADX 0–60 or Hurst 0–1
  volatility: number;        // ATR% 0–5
  trail?: Array<{ t: number; trend: number; vol: number }>;
  comparison?: { symbol: string; trendStrength: number; volatility: number };  // e.g., BTC ghost dot
  metric?: 'adx' | 'hurst';
}
```

Four labeled cells (Quiet Trend / Volatile Trend / Compression / Chop). Trail leaves fading cyan track.

**Consumers**:
- **Lesson Chapter 7** (Regime) — hero widget
- **`/intel`** page — persistent regime readout (Phase 2)
- **Bot Status** — live regime classifier next to cycle heartbeat (Phase 2)

**Lives at**: `src/components/hud/RegimeQuadrant/`

---

## Lesson-only primitives (shared across chapters, no HUD consumer)

These live in `src/components/lessons/primitives/` and stay there:

### `<ChapterShell />`

Layout shell: `PageHead` + left-rail nav + right-pane body + sources footer + chapter-progress chip. Eliminates the layout boilerplate from each chapter's `.tsx`.

### `<FlipCard />`

Front: "Common Mistake — '[claim]'". Back: explanation + diagnostic. Used in every chapter's "Common mistakes" section. Tap/click to flip; persists "viewed" state in localStorage so the chapter progress meter can credit it.

### `<SourceList />`

Renders the "// SOURCE" footer block. Props: `sources: Array<{ tier: 'primary' | 'vendor' | 'supplementary'; title: string; url: string }>`. Color-codes tier with a small chip.

### `<Quiz />`

Multi-option mini-game. Props: `question`, `options[]` (each with `correct` flag and `explanation`), `onComplete`. Stores answer history in localStorage.

### `<ChartFixture />`

Renders the Master Fixture with a lens prop (see `cross-chapter-patterns.md` §1). Bundles fixture JSON; lens annotations are separate React components composed over the chart layer.

---

## Build sequencing recommendation

**Phase 1 must ship**: `<KellyCurve />`, `<WeightSliderPanel />`, `<RegimeQuadrant />`, `<ChapterShell />`, `<FlipCard />`, `<SourceList />`, `<ChartFixture />`. These three HUD-tier + four lesson primitives are the foundation. Without them, Phase 1 cannot land its hero widgets.

**Phase 1 may ship deferred** (chapter hero swapped to a static SVG placeholder): `<GateFunnel />`, `<RiskOfRuinGauge />`, `<EquityCurveMonteCarlo />`. These are nice-to-have but not blocking.

**Phase 2 unlocks**: `<FactorCorrelationHeatmap />`, `<Quiz />`, and all the cross-chapter overlays.
