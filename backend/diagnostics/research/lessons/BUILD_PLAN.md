# Lessons Module — Build Plan (Path B, Phased)

Supersedes the original Plan-agent output (conversation, 2026-05-25). This plan reflects the operator's selections: **Path B (phased)**, **Master Fixture: yes**, two-tier component organization, CME-gap content skipped, dossier at `backend/diagnostics/research/lessons/`.

## Phase boundary

**Phase 1 — ship the read.** 9 chapters with prose + one hero widget each (7 of which are reusable primitives). Lessons card on Training Ground flips live. Progress persists. Snapshot framework integrated. Operator can read every chapter and play with one anchor widget per chapter.

**Phase 2 — ship the lab.** Add the cross-chapter overlays (Master Fixture re-annotation across chapters, Anatomy Stack sidebar, Tri-Layer chart, Composite-Operator narration), the secondary interactive widgets per chapter (Monte Carlo, ergodicity demo, gate funnel, correlation heatmap), and the quiz framework. Paced separately, not gated on Phase 1.

## Repo layout

```
src/
├── components/
│   ├── hud/                                  # cross-page primitives
│   │   ├── KellyCurve/                       # NEW — promoted day-1
│   │   ├── RegimeQuadrant/                   # NEW — promoted day-1
│   │   ├── GateFunnel/                       # NEW (Phase 1 if time, else Phase 2)
│   │   ├── WeightSliderPanel/                # NEW — promoted day-1
│   │   ├── RiskOfRuinGauge/                  # NEW (Phase 1 if time, else Phase 2)
│   │   └── ...existing primitives
│   └── lessons/
│       ├── primitives/                       # reused across ≥2 chapters
│       │   ├── ChapterShell/                 # NEW — layout shell
│       │   ├── FlipCard/                     # NEW
│       │   ├── SourceList/                   # NEW
│       │   ├── ChartFixture/                 # NEW — Master Fixture renderer
│       │   └── Quiz/                         # NEW (Phase 2)
│       └── widgets/                          # chapter-specific
│           ├── FvgBuilder/                   # Chapter 2 hero
│           ├── WickVsCloseDemo/              # Chapter 3 hero
│           ├── SweepVsBreakoutTwin/          # Chapter 4 hero
│           ├── WyckoffSchematic/             # Chapter 5 hero
│           ├── KillZoneClock/                # Chapter 9 hero
│           ├── EquityCurveMonteCarlo/        # (lessons-scoped, promote later)
│           └── ...
├── content/
│   └── lessons/
│       ├── index.ts                          # chapter manifest (metadata only)
│       ├── _fixtures/
│       │   └── master-btc.json               # Master Fixture data
│       ├── 01-order-blocks.tsx
│       ├── 02-fvg.tsx
│       ├── 03-bos-choch.tsx
│       ├── 04-liquidity-sweeps.tsx
│       ├── 05-wyckoff.tsx
│       ├── 06-confluence.tsx
│       ├── 07-regime.tsx
│       ├── 08-position-sizing.tsx
│       └── 09-kill-zones.tsx
├── hooks/
│   └── useLessonsProgress.ts                 # NEW — localStorage progress
└── pages/training/
    └── Lessons.tsx                            # NEW — page shell
```

## Phase 1 step sequence

### Step 1 — Master Fixture curation *(blocker for Steps 2-5)*

- Hand-pick a 60-bar BTC chart from existing market data (or fetch fresh) that has: clean BOS, refined OB candle, valid 3-candle FVG, equal-highs cluster swept just before the OB formed, and falls inside a kill zone.
- Serialize to `src/content/lessons/_fixtures/master-btc.json` (OHLCV + ATR per bar).
- Document the annotation coordinates for each lens in a sibling `master-btc.annotations.json` so chapters consume position data without re-deriving.
- **Estimated effort**: 2 hours (search + curate + annotate).

### Step 2 — Lesson primitives

Build the four foundational primitives in `src/components/lessons/primitives/`:
- `<ChapterShell />` — layout: PageHead + left nav + right body + SourceList footer + progress chip
- `<FlipCard />` — front/back flip animation; localStorage `viewed` state
- `<SourceList />` — color-tiered source-list footer
- `<ChartFixture />` — renders Master Fixture; accepts `lens` prop for annotations

### Step 3 — HUD-tier primitives (the three Phase 1 heroes)

Build in `src/components/hud/`:
- `<KellyCurve />` — Chapter 8 hero; the inverted-U log-growth chart
- `<WeightSliderPanel />` — Chapter 6 hero; auto-renormalizing weight sliders
- `<RegimeQuadrant />` — Chapter 7 hero; 2D regime plot with live dot

Add exports to `src/components/hud/index.ts`.

### Step 4 — Chapter-specific widgets (Phase 1 only)

Build in `src/components/lessons/widgets/`:
- `<FvgBuilder />` — Chapter 2 hero; animated 3-candle FVG builder
- `<WickVsCloseDemo />` — Chapter 3 hero; sweep vs BOS distinction
- `<SweepVsBreakoutTwin />` — Chapter 4 hero; twin chart with diverging outcomes
- `<WyckoffSchematic />` — Chapter 5 hero; scrubbable accumulation timeline
- `<KillZoneClock />` — Chapter 9 hero; 24h polar clock-ring

Chapters 1, 6, 7, 8 reuse `<ChartFixture lens="ob" />`, `<WeightSliderPanel />`, `<RegimeQuadrant />`, `<KellyCurve />` respectively for their heroes — no chapter-specific widget needed.

### Step 5 — Progress hook

`src/hooks/useLessonsProgress.ts`:

```ts
useLessonsProgress(): {
  readChapterIds: string[];
  lastOpenedChapterId: string | null;
  markRead(id: string): void;
  markUnread(id: string): void;
  setLastOpened(id: string): void;
  reset(): void;
  counts: { done: number; total: number; nextChapter: ChapterMeta | null };
}
```

Backed by `useLocalStorage` at key `sniper.lessons.v1`, schema `{ readChapterIds, lastOpenedChapterId }`. Mirrors `sniper.settings.v1` pattern.

### Step 6 — Chapter manifest + content modules

`src/content/lessons/index.ts` exports `CHAPTERS`:

```ts
export const CHAPTERS: ChapterMeta[] = [
  { id: 'order-blocks', num: 1, title: 'Order Blocks', color: '#22d3ee',
    summary: '…', Body: lazy(() => import('./01-order-blocks')),
    sourceRefs: ['backend/strategy/smc/order_blocks.py'] },
  // …8 more
];
```

Bodies are lazy-imported so the manifest stays cheap for the TrainingGround card consumer (which only needs `{ id, num, title }`).

Write each chapter body `.tsx` as straight prose + the hero widget + flip-cards + source-list footer. Each chapter contains a `// SYNC: <backend-file>` comment header for any numeric reference (the `tune-confluence-weights` skill and any future weight changer must grep these).

### Step 7 — Page shell

`src/pages/training/Lessons.tsx`: two-column layout (left chapter nav, right body), hash-routed (`#ch-{id}`), wraps content in `<ChapterShell />`. Hash-change → `setLastOpened(currentChapterId)`. Snapshot-ready handshake (`data-snapshot-ready="true"` on mount).

### Step 8 — Route + TrainingGround flip

- `src/App.tsx`: lazy import `Lessons` after `Drills`; add `<Route path="/training/lessons" element={<Lessons />} />`.
- `src/pages/TrainingGround.tsx` lines 107-122: flip card from disabled → live; populate stats (`Chapters / Done / Next`) from `useLessonsProgress` counts in a `useEffect` (NOT in `useMemo`).

### Step 9 — Snapshot states

`tests/visual/states.ts`: add three Lessons states — `default`, `chapter-open` (hash navigation), `all-read` (init-script populated localStorage).

### Step 10 — §16 audit + commit

Per CLAUDE.md §16: spawn audit subagent, paste verbatim output, address gaps, commit + push to `origin/main`, advance.

## Phase 2 step sequence (paced separately)

Each is a separate sub-step with its own audit cycle:

- **2a**: Build `<GateFunnel />` HUD-tier primitive. Wire into Chapter 6.
- **2b**: Build `<RiskOfRuinGauge />` HUD-tier primitive. Wire into Chapter 8.
- **2c**: Build `<EquityCurveMonteCarlo />` lesson primitive (promotion candidate). Wire into Chapter 8 playground.
- **2d**: Build `<Quiz />` lesson primitive. Wire into Chapters 1, 2, 5, 8 (spot-the-OB, find-the-FVG, spring-vs-breakdown, Kelly calculator).
- **2e**: Cross-chapter — Anatomy Stack sidebar reuses Master Fixture across chapters.
- **2f**: Cross-chapter — Tri-Layer chart, Composite Operator narration overlay.
- **2g**: Build `<FactorCorrelationHeatmap />` lesson primitive. Wire into Chapter 6.
- **2h**: Build chapter-specific Phase 2 widgets per chapter (lifecycle animators, IFVG flippers, Asian range simulators, etc.) as discrete sub-steps. Each pulls its spec from the chapter research file.

## Constraints checklist (apply to every step)

- **CLAUDE.md §10 standing fixes**:
  - Chapter 7 prose says "percentage ATR", not "ATR threshold"
  - Chapter 6 numeric examples match `MODE_FACTOR_WEIGHTS` (cite source line)
  - Conflict-density thresholds (5 OVERWATCH / 3 elsewhere) appear correctly in Chapter 6
  - No mock data anywhere; bot telemetry pulls are real
- **CLAUDE.md §17 task router**: every step declares Task type / Skills / Agent line
- **CLAUDE.md §18 pre-flight**: Phase 1 steps 7-9 (new route, new page, new content) → Plan agent already ran (this document supersedes); symmetry-guard not needed (no scoring/regime/SMC file edits in lessons code); §16 audit fires per sub-step
- **CLAUDE.md §20 backend integrity**: NO backend changes in Phase 1 or Phase 2; contract diff trivially clean
- **No Tailwind utility classes** in any new component (use `hud.css` classes + inline styles, matching RangeBot/Drills)
- **Snapshot handshake**: every page sets `body[data-snapshot-ready="true"]` after first content load resolves
- **Lazy import** in `App.tsx` for the page
- **Commit trailer**: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`

## Open questions for operator (defer to runtime — none block Phase 1)

- Cross-chapter Master Fixture lens count: I've designed for 7 (OB, FVG, BOS, sweep, Wyckoff, regime, killzone). Confirm or trim during Phase 2 planning.
- Quiz progress: track per-chapter accuracy in localStorage, or aggregate into a single "Lessons Progress" stat? Defer to Phase 2.
- Anatomy Stack sidebar: persistent across chapters, or per-chapter? Defer to Phase 2.

## Implementation files affected (Phase 1)

| Action | File | Notes |
|---|---|---|
| New | `src/content/lessons/_fixtures/master-btc.json` | Master Fixture data |
| New | `src/content/lessons/_fixtures/master-btc.annotations.json` | Per-lens annotation coords |
| New | `src/content/lessons/index.ts` | Chapter manifest |
| New | `src/content/lessons/01-order-blocks.tsx` … `09-kill-zones.tsx` | 9 chapter modules |
| New | `src/components/lessons/primitives/{ChapterShell,FlipCard,SourceList,ChartFixture}/` | 4 primitives |
| New | `src/components/lessons/widgets/{FvgBuilder,WickVsCloseDemo,SweepVsBreakoutTwin,WyckoffSchematic,KillZoneClock}/` | 5 chapter-specific heroes |
| New | `src/components/hud/{KellyCurve,WeightSliderPanel,RegimeQuadrant}/` | 3 HUD-tier heroes |
| New | `src/hooks/useLessonsProgress.ts` | localStorage hook |
| New | `src/pages/training/Lessons.tsx` | page shell |
| Edit | `src/App.tsx` | lazy import + route |
| Edit | `src/pages/TrainingGround.tsx` | flip card, populate stats |
| Edit | `src/components/hud/index.ts` | export 3 new HUD primitives |
| Edit | `tests/visual/states.ts` | 3 new lesson states |

Phase 1 surface: ~30 new files, 3 edits.

## Sequencing recommendation

Steps 1 → (2 + 3 parallel) → 4 → 5 → 6 → 7 → 8 → 9 → 10.

Steps 2 and 3 can run in parallel because they touch different directories. Step 6 (content) is the largest single chunk and can be split if needed — content for chapters 1-5 first (SMC primitives + Wyckoff, sharing Master Fixture), then 6-9 (the quant/regime/kill-zones chapters).
