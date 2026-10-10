# Architecture changelog

Dated checkpoint notes moved verbatim from [the architecture index](../ARCHITECTURE_INDEX.md)
on 2026-10-10, when the index became a current-state map. Links were rewritten for this
location; the text is unchanged. Entries describe what was known at the time and may be
superseded by later entries or by the index. Append new entries at the bottom.

## Index header and follow-ups, 2026-10-09

Reviewed 2026-10-09. Local work builds on commit
`ace4bc3d9923d31f252ef9710b5f425ee26ba79d`, branch
`claude/decision-core-heart`. This document describes that **working tree**, not
a deployed release. Source hashes and inspection boundaries are in the
[coverage ledger](SYSTEM_DISCOVERY_2026-10-07_coverage.json).
The initial discovery commit and earlier checkpoints remain historical evidence.

Restart follow-up (2026-10-09): the [UTC handoff correction](../../backend/diagnostics/decisions/2026-10-09__utc-candle-handoff.md)
normalizes exchange timestamps before ingestion gap filling and publication.
The first real restart exposed a naive/aware boundary missed by earlier synthetic
fixtures. The dominance provider also now requires an API key; unavailable mode
advice remains an explicit runtime limitation until that source is configured.

The offline review and bounded repair pass are complete. This is a navigation
map of the product's critical paths, not a claim that every inventoried file,
strategy branch, exchange protocol or historical trade has been certified.
Start with the [current findings and next work](SYSTEM_DISCOVERY_2026-10-07.md#current-disposition-and-follow-up-plan).

## Workflow integration follow-up — 2026-10-09

The [workflow pass](WORKFLOW_PASS_2026-10-09.md) supersedes the earlier
CryptoCompare availability limitation above. CoinGecko now owns a versioned global
BTC/USDT+USDC/remainder snapshot, with source-specific cache/history and provider
expiry. The changed denominator is not a calibration claim.

Browser [scan ownership](../../src/services/scanRunService.ts) persists identity,
acknowledgment and stop intent across routes/reload; [ScannerService](../../backend/services/scanner_service.py)
reuses retained identities and publishes JSON-safe complete responses. Results/history
use completion time and actual plan provenance. Backend jobs remain memory/retention
bounded. [Replay ownership](../../src/services/replaySessionController.ts) serializes
cursor moves and generation-fences replacement/cleanup. Historical signals remain
unavailable without historical macro/configuration inputs.

[FreshFeed](../../src/services/freshFeed.ts) owns per-feed display expiry and retry;
Settings owns implemented browser appearance only and links to scanner/session
configuration. Paper shutdown recovery remains visible and cannot be reset away.
The journal supports filtered pagination and complete heterogeneous CSV export.
Recorded result summaries replace demo counts, charts, connections and performance.
See the [verification record](WORKFLOW_PASS_2026-10-09.json) for tests and
runtime boundaries, including the browser-discovered NumPy serialization failure.

Bot-status follow-up: the [active-session serialization correction](BOT_STATUS_JSON_2026-10-09.json)
extends JSON-safe publication to paper/live `get_status`. A NumPy boolean in
active scan evidence broke paper status even while the process and scan loop
remained healthy. The earlier idle browser checks did not exercise this payload.
Runtime evidence records the preserved stopped simulation and replacement run.

Development footprint: [Vite watcher exclusions](../../vite.config.ts) keep backend
stores, logs, agent worktrees and generated graphs outside frontend file watching.
[Before/after measurements](RUNTIME_FOOTPRINT_2026-10-09.json) record the
reduced watch/handle counts with the same paper session continuing. Disk cleanup
candidates are recorded separately; the telemetry database is historical data.

Intel mobile follow-up: [FundingTable](../../src/components/FundingTable.tsx) owns
per-field availability and responsive funding cards. A failed exchange request
does not hide other valid fields or print raw provider errors into the page.
The [phone-layout evidence](INTEL_MOBILE_2026-10-09.json) records Phemex's
delisted TON markets, viewport checks and the compact mobile session shortcut.
Backend market selection and the running paper session were unchanged.

Scanner chart follow-up: [Review setup](../../src/components/ScannerSetupModal.tsx)
opens real candles with both saved entry boundaries, stop and all recorded targets.
[The display projection](../../src/services/scannerSetup.ts) retains contract identity
and semantic near/far values, including SHORT plans. New scan receipts retain
exchange/market provenance; older missing sources require an explicitly labeled
viewing selection. Chart timeframe changes do not recalculate a saved plan.
[Verification](SCANNER_CHART_2026-10-09.json) includes a real LIT scan,
desktop/mobile chart checks, 81 frontend tests and independent source review.


## Mode and regime integration — 2026-10-09

The [implementation decision](../../backend/diagnostics/decisions/2026-10-09__mode-regime-integration.md)
supersedes earlier descriptions of separate weekly recommendation analysis, forced
STEALTH bots, fusion, cascade and bot presets bypassing mode minimums. Daily
OHLCV validity is shared by core and advice. ADX uses one Wilder implementation;
structural trend confirmation advances on increasing daily closes while current
risk/volatility remains visible. Advice is a versioned hypothesis, not an estimate
of win probability. Fixed profiles retain some existing planner heuristics and
intraday volatility bands whose market calibration is still unverified.

Scanner: choose a mode (optionally apply the fresh suggestion), scan, inspect and
manually trade. Bot: choose a fixed mode, or opt into simulated-paper adaptive
selection with allowed modes. Each new scan resolves a complete playbook; pending
and open trades retain their originating mode. Live/testnet adaptive is disabled.
The [integration evidence](MODE_REGIME_INTEGRATION_2026-10-09.json) records
checks, intentional contract drift and forward-paper limitations.

## UI simplification foundation — 2026-10-09

The [UI audit and structure proposal](UI_REFACTOR_2026-10-09.md) records
screen intent, current owners, a bounded implementation and remaining migrations.
The [development dashboard](UI_REFACTOR_2026-10-09.html) is an offline
progress artifact backed by the [evidence ledger](UI_REFACTOR_2026-10-09.json).
It adds no product polling or trading reward behavior.

[Topbar](../../src/components/hud/Topbar.tsx) now owns native-dialog navigation,
keyboard restoration and active-page semantics. [App](../../src/App.tsx) imports
shell components directly and owns the unique workspace skip target.
[Workspace styles](../../src/styles/workspace.css) supply quiet product surfaces,
shared focus visibility and touch sizing. Browser appearance defaults are quiet;
explicit saved preferences remain authoritative. Journal filters have accessible
names and wrapping pagination; diagnostic links use actual BrowserRouter routes.

Root wallet/query providers were retired after consumer checks. Four orphan
modules and two direct dependencies were removed with a
[hashed manifest](UI_REFACTOR_2026-10-09_removals.json). Archive-dependent
providers, authored lessons, generated contracts and runtime records remain.
Scanner/session/replay/accounting owners and backend trading configuration did
not change in this pass. Whole-app accessibility, unused-code elimination and
proposed screen/feature migrations remain open; the dashboard credits only the
scoped checkpoints actually verified.

Product intent follow-up: [PRODUCT.md](../../PRODUCT.md) owns users, tone and design
principles; this index remains the map of implemented mechanics. The dashboard's
[scoring correction](UI_REFACTOR_2026-10-09.md#scoring-correction-after-the-productmd-refresh)
counts four verified fixes from commit `68ea669` once each, for 40 points. The
original 70-point calculation is retained as historical evidence in the ledger.
Feature-directory moves are optional and require a concrete maintenance problem;
split screens in place first. These rules affect development tracking only.

## UI simplification follow-through, 2026-10-09

This append supersedes the foundation's remaining-migration and 40-point status, without changing its historical evidence. The [current audit](UI_REFACTOR_2026-10-09.md), [ledger](UI_REFACTOR_2026-10-09.json) and [dashboard](UI_REFACTOR_2026-10-09.html) record ten implementation commits, 315 weighted outcome points and six of seven bounded levels cleared. A08/A09 and complete journey verification remain open; no full-screen acceptance points were awarded.

- [BotStatus controller](../../src/pages/useBotStatusController.ts) owns the existing session polls, generation fences and selected-service commands. Private refs remain inside it. [View model](../../src/pages/botStatusViewModel.ts), [leaf views](../../src/pages/BotStatusViews.tsx) and [positions](../../src/pages/BotPositions.tsx) separate pure presentation. No new session service or cache was introduced.
- [Scanner signals](../../src/pages/scannerSignals.ts) holds the pure card builder, re-exported from Scanner for its existing test seam. ScannerContext, ScanController and scanRunService remain lifecycle/configuration owners; recommendations remain manually applied.
- [Journal filters](../../src/pages/JournalFilters.tsx) and [views](../../src/pages/TradeJournalViews.tsx) contain presentation. Research handlers moved to [ResearchPanel](../../src/pages/training/ResearchPanel.tsx), under Drills; ML behavior was not changed or exercised. Accounting and export/filter scopes retain their services.
- [Live controls](../../src/pages/BotSetupControls.tsx), [paper views](../../src/pages/training/RangeBotViews.tsx) and [Replay views](../../src/pages/training/ReplayViews.tsx) sit beside their routes. ReplaySessionController retains serialized mutations/fences/cleanup errors; paper/live transports stay separate. BotSetup's existing request is LIVE (testnet false), not a testnet selector.
- [Lessons](../../src/pages/training/Lessons.tsx) now loads nine authored chapters lazily. Existing hash links and browser-storage key are retained; [progress normalization](../../src/hooks/lessonsProgressState.ts) guards saved IDs and persistence failures are visible. Historical teaching examples do not define current engine policy.
- [Modal](../../src/components/hud/Modal.tsx) and Topbar use native dialogs and a [shared scroll lock](../../src/components/hud/dialogScrollLock.ts), preserving nested close/focus behavior. Replay hotkeys ignore open dialogs. [Toggle](../../src/components/hud/Toggle.tsx) is the shared native execution switch.
- [tokens.css](../../src/styles/tokens.css) owns the palette and aliases; no generic UI state/context consolidation accompanied the style refactor. Presentation CSS beyond palette ownership is still being reviewed.
- [apiBase](../../src/services/apiBase.ts) supplies the shared VITE_API_BASE or /api resolver, including the legacy archive adapter. [request](../../src/utils/api.ts) defaults to no retry; only GET/HEAD opt in. POST/PUT/PATCH/DELETE never automatically retry. FreshFeed and session services retain their expiry, recovery and request ownership.

Active Storybook and Vitest roots exclude archived checkouts. The final compiler, 177 active unit tests, frontend build and Storybook build passed. [Independent fixtures](UI_REFACTOR_2026-10-09_browser.json) cover responsive route samples, LONG/SHORT/paper/recovery/unavailable sessions, expanded setup, shared dialogs and keyboard switches using intercepted APIs with zero mutations. Initial failures and final retests are recorded separately. Safari, native 200% zoom, full WCAG, every state/provenance/contrast permutation and exchange operations remain unverified. No backend execution, strategy or training code was changed by these UI commits.

Final release review adds native keyboard actions for pipeline evidence and paper history, linked advanced live-setup fields, shared focus/touch fixes and readable journal/lesson states. State and financial owners are unchanged. The [release evidence](UI_REFACTOR_2026-10-09_release.json) retains the responsive/lesson matrix and targeted retests. A08/A09 and the full native cross-browser journey gate remain partial; score stays315.

## Tactical appearance restoration, 2026-10-10

This append supersedes the foundation's quiet appearance description. [HUD styles](../../src/styles/hud.css) again supply tactical gradients, scanlines, glow and display typography; [workspace styles](../../src/styles/workspace.css) retain responsive/focus/touch rules. [Browser preferences](../../src/services/browserPreferences.ts) default tactical background and reticle on, with existing saved booleans authoritative. Reduced motion disables decorative animation; pointer reticles are hidden on coarse-pointer/reduced-motion surfaces.

[Scanner mode cards](../../src/components/hud/ScannerModePicker.tsx) use existing manual selection above 700px; phones keep the compact native selector. Limits come from mode definitions and missing values stay explicit. [Landing](../../src/pages/Landing.tsx) restores the brand layout with labeled static examples and implemented claims. No session/scan/feed/replay/accounting ownership, policy thresholds, commands or backend behavior changes. The [restoration evidence](UI_HUD_RESTORE_2026-10-10.json) records compiler, 177 unit tests, both builds and bounded responsive/reduced-motion/keyboard review. Earlier progress score 315 and partial A08/A09/Level 07 scope are unchanged.

## Scanner setup presentation correction, 2026-10-10

This append supersedes the compact phone selector in the preceding appearance checkpoint. [ScannerModePicker](../../src/components/hud/ScannerModePicker.tsx) renders a leading recommendation panel, visible requirements in every mode card at every width and optional native help dialogs. The existing recommendation hook remains the freshness owner; applying advice stays manual and checks expiry. [ScannerInputs](../../src/components/hud/ScannerInputs.tsx) renders its existing fields and busy-disable behavior directly. [Scanner](../../src/pages/Scanner.tsx) supplies the existing scan controller through a presentation slot, uses a native dialog for existing result filters and guards incomplete mode metadata in its header. ScanController, ScannerContext, scanRunService and receipt/filter owners are unchanged; no mode policy, session or backend changes. [Evidence](SCANNER_SETUP_2026-10-10.json) records compiler,180 unit tests, frontend build and bounded independent review; score remains315.

## Play Inspector, 2026-10-10

`PlayInspector` replaces `ScannerSetupModal`, `PositionDetailModal` and
`TradeHistoryDetailModal`, and `src/services/playInspector.ts` replaces
`scannerSetup.ts`; the old files were deleted. Paper and live status now
publish the same pending-plan view (`backend/bot/plan_view.py`): live pending
entries gained stop, targets, timeframe, score and strategy; paper's missing
stop and current price changed from `0.0` to `null`. Saved-setup direction now
uses the strict `readDirection` parser, so a saved SHORT no longer defaults to
LONG. Verification: compiler, 191 Vitest tests, frontend build, guarded backend
suite (2482 passed; one execution-journal failure reproduces on the base
commit), and browser checks at 1440px and 390px against intercepted APIs.
