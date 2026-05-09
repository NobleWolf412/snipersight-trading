# Archived Files

Generated: 2026-05-09
Pre-rebuild branch tag: `pre-hud-rebuild`
Replacement design source: `prototype/`
Scope: Phase 6 of the HUD rebuild (peppy-sniffing-owl plan).

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

## shadcn `ui/` primitives (52) — Phase 6 sub-step 4b

Every file under `src/components/ui/` archived EXCEPT `sonner.tsx` (still
mounted as `<Toaster />` in `src/App.tsx` until Phase 7 replaces it with
the HUD `useFlash` banner).

Archived: `accordion`, `alert`, `alert-dialog`, `aspect-ratio`, `avatar`,
`badge`, `breadcrumb`, `button`, `calendar`, `card`, `carousel`, `chart`,
`checkbox`, `collapsible`, `command`, `context-menu`, `dialog`, `drawer`,
`dropdown-menu`, `form`, `hover-card`, `input`, `input-otp`, `label`,
`menubar`, `navigation-menu`, `pagination`, `popover`, `progress`,
`radio-group`, `resizable`, `scroll-area`, `select`, `separator`, `sheet`,
`sidebar`, `skeleton`, `slider`, `switch`, `table`, `tabs`, `textarea`,
`toggle`, `toggle-group`, `tooltip`, `CircularProgress`, `SystemTerminal`,
`TacticalBackground`, `TacticalBorders`, `TacticalComponents`,
`TacticalInputs`, `TacticalReturnButton`.

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

## Tailwind / Build (deferred to Phase 7)
- `tailwind.config.js` · still active until Phase 7 ejects Tailwind
- `postcss.config.js` · still active until Phase 7
- `components.json` (shadcn config) · still on disk; will be deleted in Phase 7

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
