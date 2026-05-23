# Archived Files

Generated: 2026-05-09 (last updated end of Phase 7)
Pre-rebuild branch tag: `pre-hud-rebuild`
Replacement design source: `prototype/`
Scope: Phase 6 + Phase 7 of the HUD rebuild (peppy-sniffing-owl plan).

This manifest tracks every frontend file that was relocated under
`src/_archive/` during the HUD rebuild. The `_archive/` tree is excluded
from `tsconfig.json` (`"exclude": ["src/_archive"]`) so it is not
typechecked, and Vite's import-graph traversal never reaches it from any
active entry point — so it is not bundled either. Files retain their
original git history via `git mv`.

## How to recover an archived file

1. `git mv src/_archive/<path> src/<original-path>` (filename and
   subdirectory under `_archive/` mirror the original location).
2. Rewire any consumers — most archived files imported from
   `@/components/ui/*` or `@/lib/utils`, both of which are also archived.
   You will likely need to either (a) restore the relevant `ui/` files
   too, or (b) replace shadcn primitives with the new `@/components/hud/*`
   chrome.

## Format

`Original path → Archived to · Reason · Replaced by · Phase`

---

## Pages (8 archived)

- `src/pages/MarketOverview.tsx` → `src/_archive/pages/MarketOverview.tsx` · Orphan, no equivalent in HUD · (none — not folded in) · Phase 6 sub-step 2
- `src/pages/HTFOpportunities.tsx` → `src/_archive/pages/HTFOpportunities.tsx` · Orphan · (none) · Phase 6 sub-step 2
- `src/pages/ScanResults.tsx` → `src/_archive/pages/ScanResults.tsx` · Scanner page absorbs results · `src/pages/Scanner.tsx` · Phase 6 sub-step 2
- `src/pages/ScannerSetup.tsx` → `src/_archive/pages/ScannerSetup.tsx` · Setup folded into Scanner · `src/pages/Scanner.tsx` · Phase 6 sub-step 2
- `src/pages/ScannerStatus.tsx` → `src/_archive/pages/ScannerStatus.tsx` · Scanner page hosts status · `src/pages/Scanner.tsx` · Phase 6 sub-step 2
- `src/pages/ScanResults.stories.tsx` → `src/_archive/pages/ScanResults.stories.tsx` · Story for archived page · — · Phase 6 sub-step 2
- `src/pages/ScannerSetup.stories.tsx` → `src/_archive/pages/ScannerSetup.stories.tsx` · Story for archived page · — · Phase 6 sub-step 2
- `src/pages/MarketIntelPage.jsx` → `src/_archive/pages/MarketIntelPage.jsx` · Orphan, never routed · (none) · Phase 6 sub-step 4a

## Components — pre-rebuild HUD chrome

### TopBar (6)
- `src/components/TopBar/BTCPricePill.tsx` → `src/_archive/components/TopBar/BTCPricePill.tsx` · Replaced by HUD topbar · `src/components/hud/Topbar.tsx` · Phase 6 sub-step 3
- `src/components/TopBar/CycleStatusStrip.tsx` → `src/_archive/components/TopBar/CycleStatusStrip.tsx` · Replaced · `src/components/hud/Topbar.tsx` · Phase 6 sub-step 3
- `src/components/TopBar/TopBar.tsx` → `src/_archive/components/TopBar/TopBar.tsx` · Replaced · `src/components/hud/Topbar.tsx` · Phase 6 sub-step 3
- `src/components/TopBar/TopBarV2.tsx` → `src/_archive/components/TopBar/TopBarV2.tsx` · Replaced · `src/components/hud/Topbar.tsx` · Phase 6 sub-step 3
- `src/components/TopBar/TopBarLite.tsx.bak` → `src/_archive/components/TopBar/TopBarLite.tsx.bak` · Backup file · — · Phase 6 sub-step 3
- `src/components/TopBar/index.ts` → `src/_archive/components/TopBar/index.ts` · Barrel · — · Phase 6 sub-step 3

### Navigation (1)
- `src/components/Navigation/Navigation.tsx` → `src/_archive/components/Navigation/Navigation.tsx` · Replaced by HUD topbar · `src/components/hud/Topbar.tsx` · Phase 6 sub-step 3

### Layout shells (4)
- `src/components/layout/HomeButton.tsx` → `src/_archive/components/layout/HomeButton.tsx` · Replaced by `<Link to="/">` in HUD topbar · `src/components/hud/Topbar.tsx` · Phase 6 sub-step 3
- `src/components/layout/PageContainer.tsx` → `src/_archive/components/layout/PageContainer.tsx` · Replaced by HUD page surfaces · `src/components/hud/PageHead.tsx` · Phase 6 sub-step 3
- `src/components/layout/PageLayout.tsx` → `src/_archive/components/layout/PageLayout.tsx` · Replaced · `src/components/hud/*` · Phase 6 sub-step 3
- `src/components/layout/PageShell.tsx` → `src/_archive/components/layout/PageShell.tsx` · Replaced · `src/App.tsx` shell · Phase 6 sub-step 3

### Legacy `hud/` (4)
- `src/components/hud/HudPanel.tsx` → `src/_archive/components/hud-legacy/HudPanel.tsx` · Replaced · `src/components/hud/SectionHead.tsx` + `panel` CSS class · Phase 6 sub-step 3
- `src/components/hud/MissionBrief.tsx` → `src/_archive/components/hud-legacy/MissionBrief.tsx` · Replaced · — · Phase 6 sub-step 3
- `src/components/hud/TacticalCard.tsx` → `src/_archive/components/hud-legacy/TacticalCard.tsx` · Replaced · `panel` CSS class · Phase 6 sub-step 3
- `src/components/hud/TargetReticleOverlay.tsx` → `src/_archive/components/hud-legacy/TargetReticleOverlay.tsx` · Replaced · `src/components/hud/Reticle.tsx` · Phase 6 sub-step 3

## Components — landing (13)
- `src/components/landing/ArsenalVisuals.tsx` → archive · Replaced · `src/pages/Landing.tsx` · 3
- `src/components/landing/CycleGraphics.tsx` → archive · Replaced · `src/pages/Landing.tsx` · 3
- `src/components/landing/FeatureTabs.tsx` → archive · Replaced · `src/pages/Landing.tsx` · 3
- `src/components/landing/HTFOpportunities.tsx` → archive · Replaced · `src/pages/Landing.tsx` · 3
- `src/components/landing/HeroSection.tsx` → archive · Replaced · `src/pages/Landing.tsx` · 3
- `src/components/landing/LandingLoader.tsx` → archive · Replaced · `src/pages/Landing.tsx` · 3
- `src/components/landing/MarketCyclesBrief.tsx` → archive · Replaced · `src/pages/Landing.tsx` · 3
- `src/components/landing/MetricsGrid.tsx` → archive · Replaced · `src/pages/Landing.tsx` · 3
- `src/components/landing/ModuleCard.tsx` → archive · Replaced · `src/pages/Landing.tsx` · 3
- `src/components/landing/StatsBar.tsx` → archive · Replaced · `src/pages/Landing.tsx` · 3
- `src/components/landing/SystemStatus.tsx` → archive · Replaced · `src/pages/Landing.tsx` · 3
- `src/components/landing/TacticalBriefing.tsx` → archive · Replaced · `src/pages/Landing.tsx` · 3
- `src/components/landing/TacticalDivider.tsx` → archive · Replaced · `src/pages/Landing.tsx` · 3

## Components — scanner (legacy 3D, 7)
- `src/components/scanner/HolographicGlobe.tsx` · Replaced · `src/pages/Scanner.tsx` (vanilla CSS panels) · 3
- `src/components/scanner/ModeVisuals.tsx` · Replaced · `src/components/hud/ScannerModePicker.tsx` · 3
- `src/components/scanner/ScannerModeTabs.tsx` · Replaced · `src/components/hud/ScannerModePicker.tsx` · 3
- `src/components/scanner/SceneContainer.tsx` · Replaced · — · 3
- `src/components/scanner/SystemVitals.tsx` · Replaced · `src/pages/Scanner.tsx` · 3
- `src/components/scanner/TacticalRadar.tsx` · Replaced · `src/pages/Scanner.tsx` · 3
- `src/components/scanner/WaveformMonitor.tsx` · Replaced · `src/pages/Scanner.tsx` · 3

## Components — intel (7)
- `src/components/intel/CycleTheoryExplainer.tsx` · Replaced · `src/pages/Intel.tsx` · 3
- `src/components/intel/DailyBriefing.tsx` · Replaced · `src/pages/Intel.tsx` · 3
- `src/components/intel/DominanceRadar.tsx` · Replaced · `src/pages/Intel.tsx` (HUD chrome) · 3
- `src/components/intel/IntelHeader.tsx` · Replaced · `src/components/hud/PageHead.tsx` · 3
- `src/components/intel/MarketEditorial.tsx` · Replaced · `src/pages/Intel.tsx` · 3
- `src/components/intel/NarrativeTracker.tsx` · Replaced · `src/pages/Intel.tsx` · 3
- `src/components/intel/NewsTicker.tsx` · Replaced · `src/pages/Intel.tsx` · 3

## Components — bot (3)
- `src/components/bot/PhemexStatusPill.tsx` · Replaced · `src/components/hud/PhemexStatusPill/` · Phase 6 sub-step 3
- `src/components/bot/WatchlistRadar.tsx` · Replaced · `src/pages/BotStatus.tsx` · Phase 6 sub-step 3
- `src/components/bot/GauntletBreakdown.tsx` (legacy) · Replaced · `src/components/hud/GauntletBreakdown.tsx` · Phase 6 sub-step 3

## Components — ScanResults (4)
- `src/components/ScanResults/IntelDossier.tsx` · Replaced · — · 3
- `src/components/ScanResults/RejectionCard.tsx` · Replaced · — · 3
- `src/components/ScanResults/ResultCard.tsx` · Replaced · `src/pages/Scanner.tsx` cards · 3
- `src/components/ScanResults/ScanResultsTable.tsx` · Replaced · `src/pages/Scanner.tsx` · 3

## Components — orphan singletons archived in sub-step 3 + 4a

### Sub-step 3 (post route + page archive)
- `src/components/ScannerConsole.tsx` · Replaced · `src/pages/Scanner.tsx` · 3
- `src/components/RejectionSummary.tsx` · Replaced · `src/pages/Scanner.tsx` · 3

### Sub-step 4a — orphan kept-components (every consumer was already archived)
- `src/components/PriceDisplay.tsx`
- `src/components/PaperTradingConfig.tsx`
- `src/components/NotificationSettings.tsx`
- `src/components/NotificationStatus.tsx`
- `src/components/PriceCard.tsx`
- `src/components/PriceCard.stories.tsx`
- `src/components/TierBadge.tsx`
- `src/components/WarningsContext.tsx`
- `src/components/ScanHistory.tsx`
- `src/components/MarkdownViewer.tsx`
- `src/components/BackendStatusPill.tsx`
- `src/components/RegimeIndicator.tsx`
- `src/components/LiveTicker.tsx`

### Whole-dir orphan archives (4a)
- `src/components/risk/` (1 file: `RiskSummary.tsx`)
- `src/components/market/` (4 files: `BTCCycleIntel`, `FourYearCycleGauge`, `MarketRegimeLens`, `index.ts`)
  - **Note:** `useMarketRegime.ts` originally type-imported `MarketRegimeLensProps` from `MarketRegimeLens.tsx`. The type was inlined into `src/hooks/useMarketRegime.ts` lines 4-22 to keep the hook self-contained.
- `src/components/telemetry/` (1 file: `ActivityFeed.tsx`)
- `src/components/TargetIntelScorecard/` (1 file)
- `src/components/WalletConnect/` (2 files)
- `src/components/WalletGate/` (2 files)
- `src/components/ChartModal/` (5 files)
- `src/components/charts/` (5 files: `HTFBiasChart`, `LightweightChart`, `MultiTimeframeChartGrid`, `TacticalGauge`, `TimeframeLegend`)
- `src/components/htf/` (1 file: `HTFOpportunityCard.tsx`)
- `src/components/SessionIndicator/` (1 file)

## shadcn `ui/` primitives (53) — Phase 6 sub-step 4b + Phase 7 sub-step 2

The shadcn primitive set was first archived en masse in 6.4b, leaving
`sonner.tsx` mounted as `<Toaster />` in `src/App.tsx`. Phase 7 sub-step
2 confirmed sonner had **zero active consumers** in the post-Phase-6
tree (the only known consumer, `use-require-wallet`, was an orphan
hook), so `sonner.tsx` was archived alongside the orphan hooks
(`use-toast.ts`, `use-require-wallet.ts`) and the `<Toaster />` mount
removed from `App.tsx`. The HUD `useFlash` banner mentioned in the
plan is deferred until a real consumer appears — there is no point
mounting a no-op toast layer.

Archived: `accordion`, `alert`, `alert-dialog`, `aspect-ratio`, `avatar`,
`badge`, `breadcrumb`, `button`, `calendar`, `card`, `carousel`, `chart`,
`checkbox`, `collapsible`, `command`, `context-menu`, `dialog`, `drawer`,
`dropdown-menu`, `form`, `hover-card`, `input`, `input-otp`, `label`,
`menubar`, `navigation-menu`, `pagination`, `popover`, `progress`,
`radio-group`, `resizable`, `scroll-area`, `select`, `separator`, `sheet`,
`sidebar`, `skeleton`, `slider`, `sonner` (Phase 7), `switch`, `table`,
`tabs`, `textarea`, `toggle`, `toggle-group`, `tooltip`,
`CircularProgress`, `SystemTerminal`, `TacticalBackground`,
`TacticalBorders`, `TacticalComponents`, `TacticalInputs`,
`TacticalReturnButton`.

Replaced by `src/components/hud/*` primitives: `Chip`, `Mini`, `Modal`,
`PageHead`, `FooterStatus`, `Reticle`, `RiskBar`, `SectionHead`,
`TacticalBgDom`, `Topbar`, `PhemexStatusPill`, `ScannerModePicker`,
`GauntletBreakdown`, `PipelineTracer`, `ConfluenceBreakdown`,
`UniversePanel`, `DiagnoseWizard` and the corresponding HUD CSS classes
(`panel`, `chip`, `chip-cyan`, `chip-green`, `chip-red`, `btn`, `btn-cyan`,
`btn-red`, `mono`, `tab-switch`, `metric-tile`, `metric-label`,
`metric-value`, `sec-head`, `sec-title`).

## `lib/` (1)
- `src/lib/utils.ts` (`cn` helper) → `src/_archive/lib/utils.ts` · No active code imports it after sub-step 4b · Phase 6 sub-step 4b
- `src/lib/queryClient.ts` is **NOT archived** — still imported by `src/main.tsx` for React Query.

## Phase 7 — Tailwind eject

Phase 7 fully removed Tailwind from CSS, build pipeline, and npm
graph. Sub-step ordering kept the working tree bootable between
sub-steps (CSS-side changes shipped before Vite-plugin removal,
Vite-plugin removal shipped before npm package removal).

### Hooks archived (Phase 7 sub-step 2)
- `src/hooks/use-toast.ts` → `src/_archive/hooks/use-toast.ts` · Orphan;
  zero active callers. Tightly coupled to `sonner.tsx`. · Phase 7 sub-step 2
- `src/hooks/use-require-wallet.ts` → `src/_archive/hooks/use-require-wallet.ts` ·
  Orphan; zero active callers. · Phase 7 sub-step 2

### Active components restyled in place (Phase 7 sub-step 3) — NOT archived
- `src/components/SniperReticle.tsx` — Tailwind utilities replaced with
  inline styles using `var(--destructive)` + `color-mix` opacity blends;
  custom classes `scope-reticle` and `scope-marker` (live in
  `src/styles/hud-effects.css`) preserved.
- `src/components/ActiveScanBeacon/ActiveScanBeacon.tsx` — Tailwind
  utilities replaced with inline styles; `group-hover:` replaced with
  local `useState(hovered)` + `onMouseEnter/Leave`; custom keyframe
  classes (`beacon-pill-slide-in`, `beacon-glow-breathe`, `beacon-float`,
  `beacon-sonar-ring`, `beacon-radar-sweep`, all in `src/index.css`)
  preserved.

### Orphans archived (Phase 7 sub-step 4)
- `src/components/MissionStats.tsx` → `src/_archive/components/MissionStats.tsx` ·
  Heavy framer-motion + Tailwind component; only consumed by archived
  ScanResults / scanner pages. · Phase 7 sub-step 4
- `src/components/TacticalPanel.tsx` → `src/_archive/components/TacticalPanel.tsx` ·
  Wrapper component (`metal-panel rounded-2xl`); no active callers.
  Replaced by `.panel` class. · Phase 7 sub-step 4
- `src/utils/scannerValidation.ts` → `src/_archive/utils/scannerValidation.ts` ·
  `getSeverityColor()` returns Tailwind class strings; only consumed by
  archived `ScannerSetup.tsx`. · Phase 7 sub-step 4

### CSS / build directives removed (Phase 7 sub-step 5)
- `src/index.css` — removed `@import "tailwindcss"` directive +
  `@theme` block (~32 lines of `--color-*` aliases). All `:root`
  design tokens preserved.
- `src/main.css` — removed `@config '../tailwind.config.js'` line.
- `vite.config.ts` — removed `import tailwindcss from "@tailwindcss/vite"`
  and the `tailwindcss()` plugin invocation.

### Build configs deleted (Phase 7 sub-step 6)
| File | Recovery |
|---|---|
| `tailwind.config.js` | `git show pre-hud-rebuild:tailwind.config.js` (or any pre-Phase-7 commit) |
| `postcss.config.js` | same |
| `components.json` (shadcn primitive generator) | same |
| `theme.json` (only consumed by `tailwind.config.js`) | same |

### npm packages removed (Phase 7 sub-step 6)
**dependencies:** `@radix-ui/colors`, `@tailwindcss/container-queries`,
`@tailwindcss/vite`, `clsx`, `tailwind-merge`, `tailwind-variants`,
`tw-animate-css` (7 removed).

**devDependencies:** `@tailwindcss/postcss`, `tailwindcss`,
`tailwindcss-animate` (3 removed).

`npm install` reported "removed 31 packages" — the 10 direct + 21
transitive. `npx vite build` succeeds in ~5s post-removal.

`class-variance-authority`, `cmdk`, `vaul` are intentionally retained
for now — they are orphan but not Tailwind-specific so they were left
out of the declared sub-step 6 scope. Future cleanup pass.

## Code edits required to archive cleanly

| File | Edit | Phase |
|---|---|---|
| `src/App.tsx` | dropped legacy routes (ScannerSetup, ScannerStatus, ScanResults, MarketOverview, HTFOpportunities) and 5 lazy imports | 6.1 |
| `src/pages/Landing.tsx` | rewrote 2 stale `to="/scanner/setup"` links to `/scanner` | 6.1 |
| `src/components/ActiveScanBeacon/ActiveScanBeacon.tsx` | rewrote `route: '/scanner/status'` to `/scanner` | 6.1 |
| `src/components/hud/Topbar.tsx` | trimmed stale `matchPrefixes` for `/scanner` | 6.1 |
| `src/pages/Scanner.tsx` | reworded empty-state hint that referenced `/scanner/setup` | 6.1 |
| `src/utils/notifications.ts` | rewrote stale `window.location.hash = '/results'` to `/scanner` | 6.1 |
| `tsconfig.json` | added `"exclude": ["src/_archive"]` | 6.2 |
| `src/components/hud/index.ts` | removed 4 dead re-exports for archived legacy hud files | 6.3 |
| `src/hooks/useMarketRegime.ts` | inlined `MarketRegimeLensProps` after `MarketRegimeLens.tsx` archived | 6.4a |
| `src/ErrorFallback.tsx` | rewrote with vanilla HUD chrome after shadcn `ui/alert` + `ui/button` archived | 6.4b |

## How to recover

- **Files under `src/_archive/`:** `git mv` back to original path (filename and subdirectory mirror the original).
- **Pre-rebuild snapshot:** `git checkout pre-hud-rebuild -- <path>`.
- **Whole-tree rollback:** `git reset --hard pre-hud-rebuild` (destructive — only use for full rollback).
