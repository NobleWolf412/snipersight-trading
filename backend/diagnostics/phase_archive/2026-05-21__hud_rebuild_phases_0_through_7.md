# HUD Rebuild — Phases 0 through 7 (peppy-sniffing-owl plan)

Archived from MEMORY.md on 2026-05-21 as part of the Tier 3 memory-hygiene round (see `2026-05-21__workflow-enhancement-tier3.md`). MEMORY.md now keeps a one-line pointer to this file.

## Phase sequence

- ✅ **Phase 0–2:** Branch, backend endpoints, theme/chrome foundation
- ✅ **Phase 3a:** Landing
- ✅ **Phase 3b:** Journal (Path B — keep backend wiring, restyle chrome)
- ✅ **Phase 3c:** Settings (CREATE — local state, no backend calls)
- ✅ **Phase 3d:** Training (commit eaaafea)
- ✅ **Phase 3e:** Intel (commit 146224f)
- ✅ **Phase 3f sub-step 0:** assertSymmetricDirectionalKeys (commit 3b32e79)
- ✅ **Phase 3f:** Scanner sub-steps 1+2 (commits 98dccd7, f45558e)
- ✅ **Phase 3g:** Bot (3g.i.a-c + 3g.ii.a-g all shipped)
  - 3g.i.a/b/c: BotSetup + BotStatus + PhemexStatusPill
  - 3g.ii.a/b/c/d/e/f/g: directional pair, GauntletBreakdown, PipelineTracer, ConfluenceBreakdown, UniversePanel, DiagnoseWizard, mode-delta strip
- ✅ **Phase 4:** Restyle kept components — CLOSED. Confirmed `src/components/ui/` empty + zero non-archive files use Tailwind utility classes (78 matches all under `_archive`). All "kept components" turned out to be orphans and were archived in Phase 6. No active restyle work remains.
- ✅ **Phase 5:** Polish items — COMPLETE (all backend gaps closed; useFlash subsumed by Phase 7 sonner-eject)
  - **5.2:** ActiveModeBadge in topbar (commit 668856b — reads selectedMode + scanConfig fallback, four-modes-only chip mapping)
  - DiagnosticWizard (already done as 3g.ii.f)
  - **Kill-zone overlay** (commit b9560e9) — real backend gap closed: new GET /api/sessions/kill-zone endpoint wraps `get_current_kill_zone` + `KILL_ZONE_TIMES_EST`. Server-side EST→UTC projection so HUD renders directly on 24h UTC scale. New `<KillZoneStrip />` polls every 30s, shows all four zones as bands with active one glowing + countdown caption. Direction-agnostic, StrictMode-safe. Mounted on Intel directly under SessionStrip. New kill-zone.json fixture + ROUTE_MOCKS entry. intel__default baseline grew 54px taller (real layout addition).
  - **Macro-score widget** ✅ SHIPPED (commit 8bfc971) — was NOT a backend gap; `/api/market/regime` already exposes composite `score` + `composite` label. New `<MacroScoreTile />` single-fetch on mount (backend caches 60s); tone buckets ≥75 green / ≥50 blue / ≥30 amber / <30 red mirror useMarketRegime visibility cutoffs. Mounted on Intel (replaces 4-tile-grid placeholder) + Scanner SCAN-CONTROL row. New market-regime.json fixture + ROUTE_MOCKS entry.
  - **Trade-type chips** ✅ SHIPPED (commit d8dd968) — was NOT a backend gap; convertSignalToScanResult already mapped `setup_type`→`classification` into scan-history. HUD Scanner now reads `classification`/`trade_type`/`setup_type` aliases via `normalizeTradeType()` + renders SWING=blue / INTRADAY=cyan / SCALP=amber chip on each card.
  - **Convergence/conflict mini-bar** ✅ SHIPPED (commit d2d0abf) — was NOT a backend gap; ConfluenceBreakdown already had the fields, convertSignalToScanResult already passed them through. New `ConvergenceConflictBar` component reads via `r.confluence_breakdown ?? r` alias so both nested + top-level shapes work.
  - **Cooldown timer** ✅ SHIPPED (commit 951d50f) — real backend gap closed: new `CooldownManager.list_active()` thread-safe snapshot + GET /api/cooldowns endpoint (returns active[], count, next_expiry_seconds). New `<CooldownsTile />` polls every 15s (24h locks; per-second precision unnecessary), shows count (red ≥1, muted when 0) + soonest TTL via fmtRemaining(). Mounted on Scanner SCAN-CONTROL row alongside MacroScoreTile. Direction-agnostic at tile level. StrictMode-safe (cancelled+setTimeout). Snapshot framework note: scanner__default test passed sub-threshold (new tile is row2-col2 of `2fr 1fr 1fr 1fr` grid; framework accepted as a small visual change).
  - **Cycle heartbeat strip** ✅ SHIPPED (commit 649c983) — `<CycleHeartbeat />` polls /api/cycles/last every 5s, mounted on Scanner (between PageHead+ScannerModePicker) and BotStatus (between PageHead+error banners). Direction-agnostic, StrictMode-safe (cancelled+setTimeout pattern from UniversePanel). Tone-based: ok/running/stale(>120s)/failed/idle. Stale-placeholder bar in Scanner SCAN-CONTROL panel removed.
  - useFlash banner — folded into Phase 7 (sonner eject is a Phase 7 task)
- ✅ **Phase 6:** Archive replaced files to `src/_archive/` (148 files, sub-steps 1-5 shipped a3cfed4..a83d171; `ARCHIVE.md` at repo root is the manifest)
- ✅ **Phase 7:** Tailwind + shadcn-primitive eject COMPLETE (sub-steps 2-7 shipped 56cc164..26a7c1f)
  - **7.2:** sonner Toaster ejected (commit 56cc164) — archived sonner.tsx, dropped `<Toaster />` mount; useFlash deferred until real consumer
  - **7.3:** SniperReticle + ActiveScanBeacon Tailwind→inline-styles (commit d5d2415); custom keyframe classes (scope-reticle/scope-marker/beacon-*) preserved in hud-effects.css + index.css
  - **7.4:** Archived 3 orphan Tailwind-using modules — MissionStats.tsx, TacticalPanel.tsx, utils/scannerValidation.ts (commit 769d36c)
  - **7.5:** CSS-side eject (commit 8f9efdd) — removed `@import "tailwindcss"` + `@theme` block from index.css; main.css → pure 3-import barrel; vite.config.ts dropped `@tailwindcss/vite` plugin
  - **7.6:** Package + config eject (commit 8867010) — removed 7 deps + 3 devDeps; deleted tailwind.config.js, postcss.config.js, components.json, theme.json; build verified `npx vite build` 5.46s 4673 modules
  - **7.7:** ARCHIVE.md Phase 7 section (commit 26a7c1f)
  - Intentionally retained orphan-but-not-Tailwind: class-variance-authority, cmdk, vaul (out of Phase 7 scope)
- ✅ **Post-Phase-7 baseline cleanup:** 4 "cyan" ChipKind tsc errors fixed (commit f0bda83) — added `.chip-cyan` rule to hud.css mirroring blue/purple pattern, extended ChipKind union to include 'cyan'. Tsc now clean.

## Phase 3 follow-up 3a' / 3a'' (commit d225f1a)

Scanner rejection panel restoration + filter polish. Backend extensions: orchestrator.py adds `build_features_breakdown(diagnostics)` module-level helper + parallel `features_breakdown` field on rejection_summary + cross-check assertion (indicator+smc+data == legacy `by_reason["features"]`); observability.py /api/cycles/last accepts `include_audit=true` mirroring /cycles/history.

Frontend: api.ts double-prefix fix on getUniverse/getLastCycle + include_audit passthrough; scanHistoryService.ts retains `rejectionSummary` + `universeSnapshot` per-run; new `<RejectionPanel />` with 6 chips (UNIVERSE/DATA/CRITICAL_TF/FEATURES/CONFLUENCE/PLANNER) + click-expand samples + zero-candidates state; new `<CycleAuditStrip />` polling /cycles/last?include_audit=true + history-median (prior-5 relative metric per rubric 5).

Filter polish: TF chips dim when not in selectedMode.timeframes; min-score slider 0-10 → 0-100 to match backend min_confluence_score; filter scope label. 11 backend tests added (7 features_breakdown + 4 cycles/last include_audit). §16 audit all 12 rubrics ✅ on second pass.

### 3a' / 3a'' calibration outcome

Three rounds of §16 invocation rule 4 violations (coder summarizing instead of pasting raw subagent output) before the operator's third demand finally landed verbatim. Procedural lesson: subagent output must be pasted into the response message body unedited; coder-authored summary tables and "open items #1/#2/..." references do NOT satisfy rule 4. The audit IS its raw output, not a description of it. Formalized as `2026-05-21__verbatim-paste-rule.md` decision entry and CLAUDE.md §16 "Verbatim-paste enforcement" subsection.

## 3z queue (prior-conversation work stashed for individual audits)

- **3z.a:** BotIndex.tsx + App.tsx /bot route
- **3z.b:** Settings.tsx save bar
- **3z.c:** Landing.tsx TickerRail + api.ts funding/fear-greed/btc-ticker double-prefix hunks

**C.1 disclosure precedent:** ScanController.tsx is a prior-conversation new file but a hard dependency of 3a' (Scanner.tsx mounts it; persistCompleted is the rejection-bundle persistence path) — rolled into 3a' commit with explicit disclosure paragraph in commit body. Audit subagent #1 covered its code across rubrics 1, 7, 11 so the inclusion is audited despite the provenance flag.

## Working pattern through the rebuild

**Path B layered port** — keep ALL backend wiring (services/hooks), replace ONLY visual chrome with HUD prototype design.

## Repo / worktree state at archive time

- Currently active: `priceless-wing` worktree on branch `claude/hud-rebuild`
- Main: `claude/hud-rebuild` is FF-merged to `main` after each sub-step
- Pre-rebuild tag: `pre-hud-rebuild` (rollback marker)

(As of 2026-05-21 the workflow shifted to direct-on-main per Tier 1/2 commits 72f64fe and 9024ef2 — the worktree pattern remains available but is no longer the default flow.)
