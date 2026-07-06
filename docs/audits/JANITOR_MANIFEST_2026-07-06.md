REPO-JANITOR INVENTORY
======================
Date: 2026-07-06
Scope: Full repo minus off-limits list; git-tracked files only unless noted
Prior manifest: docs/audits/JANITOR_MANIFEST_2026-06-22.md (zero tranches actioned since)
Off-limits respected: YES — .live_trading/, .coverage, .git/, .github/, .storybook/, .cursor/,
  CLAUDE.md, LICENSE, Dockerfile.*, .dockerignore, .claude/agents/*.md, .claude/skills/,
  .claude/worktrees/, backend/diagnostics/*.py (§12 iterate-loop scripts), backend/diagnostics/decisions/,
  backend/diagnostics/phase_archive/, standing-fix surface (scorer.py, orchestrator.py, regime_*.py,
  scanner_modes.py, smc_*.py, smc_service.py, regime_policies.py) — all KEEP per CLAUDE.md §10.

Activity since 2026-06-22: 30 commits — heart-change implementation chunks 1-5b, Form-A/B execution
  geometry, P&L fixes, account-aware admission gates 1-3, CVD capture Phase A, trailing-stop
  activation tune. No new root-level clutter introduced. New canonical tests landed in
  backend/tests/unit/ (test_account_aware_liquidity, test_cvd_tracker, test_decision_core,
  test_executor_realized_matches_balance, test_fresh_entry_guard, test_liquidity_floor,
  test_pnl_no_double_count, test_reachability_decline_boundary, test_rr_bounded_snap) — ACTIVE.
  New diagnostics (cvd_capture_health.py, cvd_historical_edge.py, account_aware_liquidity_diagnostic.py)
  — KEEP per §12.

Total candidates: 51
By tranche:
  Tranche 1 (zero-risk delete):         35 items (diagnostics txts x29 + archive zips x3
                                                   + .bak x1 + root artifacts x2)
  Tranche 2 (low-risk archive moves):    2 logical groups (prototype/ + docx)
  Tranche 3 (quarantine first):          2 items (orphan test files)
  Tranche 4 (review-only):             12 items (stale docs x7 + config-drift x1
                                                   + suspect stubs x2 + suspect scripts x2)

---

SHORT SUMMARY
=============

Total candidates by category:
  LOG-ARTIFACT       31 items  (29 root diagnostics/*.txt + telemetry.db 0-byte + .spark-initial-sha)
  UNREF-BLOB          4 items  (3 archive zips + 1 docs docx — move, not delete)
  BACKUP-FILE         1 item   (TopBarLite.tsx.bak inside _archive)
  HISTORICAL-MOVE     1 group  (prototype/ -> archive/prototype/)
  ORPHAN-TEST         2 items  (NEW: test_backend.py + test_orchestrator_imports.py)
  DOC-STALE-CURRENT   7 items  (ARCHITECTURE.md, PROJECT_STRUCTURE.md, QUICKSTART.md,
                                SETUP_INSTRUCTIONS.md, docs/SMC_PIPELINE_REFACTOR.md,
                                docs/INTEGRATION_GUIDE.md, docs/API_ADDITIONS.md)
  DOC-SUSPECT         1 item   (docs/WALLET_AUTHENTICATION.md)
  CONFIG-DRIFT        1 item   (react-day-picker in package.json)
  SUSPECT-STUB        2 items  (backend/examples/, backend/devtools/ — carry-forward)
  SUSPECT-SCRIPT      1 item   (scripts/janitor_tranche1_3c.sh)

Top 5 highest-confidence DELETE / quarantine recommendations:

  1. diagnostics/*.txt (29 files, 328 KB) — Raw run-output dumps from March 2026, pre-Phase-5
     era. Git-tracked. Zero references in any .py, .md, .yml, .bat, or .ts outside the prior
     janitor manifests that flagged them. 4+ months stale vs. current engine (Phase-5 P/D anchoring,
     BOS/CHOCH structure rework, full heart-change execution). Flagged in all three prior passes;
     no action taken. Highest-confidence delete in the repo.

  2. archive/files.zip + archive/files (2).zip + archive/snipersight-chart-fixes.zip (96 KB
     combined) — Pre-rebuild binary blobs, git-tracked, zero references, no descriptive metadata.
     Flagged in 2026-05-20 and 2026-06-22 passes. Not actioned in either. Two signals: zero
     grep hits + pre-rebuild creation date.

  3. telemetry.db (0 bytes) + .spark-initial-sha (root level) — Both git-tracked. telemetry.db
     is an empty SQLite placeholder; the live telemetry DB is generated at runtime and was
     explicitly proposed for deletion in scripts/janitor_tranche1_3c.sh (2026-05-07). .spark-initial-sha
     is a Spark.ai deployment artifact (hardcoded SHA: 3e6a499...) not referenced in package.json,
     CI, Dockerfiles, or any .py. Both proposed in the 2026-05-07 script but never actioned.

  4. src/_archive/components/TopBar/TopBarLite.tsx.bak (2.5 KB) — .bak file inside an already-
     archived component subtree. No active import from any live src/ code. Backup of a backup.
     Flagged in 2026-06-22 pass; not actioned.

  5. tests/test_backend.py + tests/test_orchestrator_imports.py — NEW this pass. Both use "recon"
     as a live scanner-mode argument (not asserting its absence). test_backend.py calls
     get_signals(..., sniper_mode="recon", ...) as a live API call; test_orchestrator_imports.py
     calls ScanConfig(profile="recon") and expects a live Orchestrator to initialize. Both
     qualify as ORPHAN-TEST: "Tests reference removed scanner modes (recon, ghost) and aren't
     asserting their absence." Recommend quarantine-first to tests/_quarantine/.

NEW CLUTTER SINCE 2026-06-22 (items not in prior manifest):
  + tests/test_backend.py (ORPHAN-TEST — recon mode as live arg)
  + tests/test_orchestrator_imports.py (ORPHAN-TEST — recon mode + hardcoded /workspaces/ path)
  + telemetry.db (root 0-byte DB — now explicitly confirmed git-tracked; missed in June pass)
  + .spark-initial-sha (root Spark artifact — now explicitly confirmed git-tracked; missed in June pass)
  + docs/INTEGRATION_GUIDE.md (DOC-STALE-CURRENT — port 5173 vs. actual 5000 drift)
  + docs/API_ADDITIONS.md (DOC-STALE-CURRENT/HISTORICAL — prescriptive stub doc whose endpoints
    are now wired; purpose fulfilled)
  + docs/WALLET_AUTHENTICATION.md (DOC-SUSPECT — describes fully-wired wallet auth but
    WalletContext.tsx shows WalletConnect as "coming soon"; partial implementation)
  + scripts/janitor_tranche1_3c.sh (SUSPECT-SCRIPT — May 2026 one-time cleanup script,
    most targets already gone from prior passes)
CARRY-FORWARD (all 33 Tranche-1 items from 2026-06-22 still unactioned):
  diagnostics/*.txt x29, archive zips x3, TopBarLite.tsx.bak x1 — unchanged since June 22.

---

TRANCHE 1 — Build artifacts, log outputs, backup files, root detritus
----------------------------------------------------------------------
(All git-tracked. Proposed action: git rm after operator approval.)

[LOG-ARTIFACT]  diagnostics/cycle_reversal_diagnostic_report.txt          7.0 KB
[LOG-ARTIFACT]  diagnostics/cycle_reversal_diagnostic_report.utf8.txt     7.0 KB
[LOG-ARTIFACT]  diagnostics/diag.txt                                       1.2 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_1d.txt                              12.0 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_1h.txt                              11.0 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_1m.txt                              12.0 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_1w.txt                              12.0 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_4h.txt                              12.0 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_5m.txt                              12.0 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_doge.txt                            12.0 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_eth.txt                             12.0 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_sol.txt                             12.0 KB
[LOG-ARTIFACT]  diagnostics/fvg_diagnostic_report.txt                    12.0 KB
[LOG-ARTIFACT]  diagnostics/indicator_diagnostic_report.txt               5.6 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_15m.txt                               8.4 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_15m_final.txt                         8.4 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_15m_final2.txt                        8.5 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_1d.txt                                8.2 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_1h.txt                                8.5 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_1m.txt                                8.7 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_1w.txt                                8.1 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_4h.txt                                8.3 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_5m.txt                                8.6 KB
[LOG-ARTIFACT]  diagnostics/output.txt                                     6.8 KB
[LOG-ARTIFACT]  diagnostics/reversal_diagnostic_report.txt                21.9 KB
[LOG-ARTIFACT]  diagnostics/smc_service_diagnostic_report.txt              6.6 KB
[LOG-ARTIFACT]  diagnostics/sweep_diag_15m.txt                             1.8 KB
[LOG-ARTIFACT]  diagnostics/sweep_diag_all.txt                            12.7 KB
[LOG-ARTIFACT]  diagnostics/sweep_diagnostic_report.txt                   12.7 KB
  All 29 files: git-tracked (verified git ls-files). Oldest content timestamp: "Generated:
  2026-03-22 19:42:24" (fvg_diag_1d.txt). Run-output dumps from FVG/OB/sweep investigation
  era — pre-Phase-5, pre-BOS/CHOCH rework, pre-structure-anchored P/D, pre-heart-change.
  Zero references in any .py, .md, .bat, .yml, or .ts (grep confirmed).
  Signals: content-timestamp March 2026 + zero code/config references found.
  Recommended: DELETE (git rm -r diagnostics/). Root diagnostics/ dir becomes empty — remove it.
  Status: CARRY-FORWARD from 2026-06-22 (zero action taken across two prior passes).

[UNREF-BLOB]    archive/files.zip                                         36 KB
[UNREF-BLOB]    archive/files (2).zip                                     12 KB
[UNREF-BLOB]    archive/snipersight-chart-fixes.zip                       48 KB
  Git-tracked (verified). No .py, .md, .bat, .yml, or .ts references these paths. Pre-rebuild
  binary blobs with opaque names. Zero grep hits for "files.zip", "files (2)", "chart-fixes.zip"
  across entire repo.
  Signals: zero references + pre-rebuild creation date (pre-2026-05).
  Recommended: DELETE (git rm).
  Status: CARRY-FORWARD from 2026-05-20 and 2026-06-22 (never actioned in two prior passes).

[BACKUP-FILE]   src/_archive/components/TopBar/TopBarLite.tsx.bak         2.5 KB
  Git-tracked. .bak extension inside src/_archive/ — an already-archived subtree not imported
  by any live src/ code. Backup of an archived file (TopBarLite.tsx also exists alongside it).
  Signals: .bak extension + zero active imports from src/ (excluding _archive/).
  Recommended: DELETE (git rm).
  Status: CARRY-FORWARD from 2026-06-22 (new in June, not actioned).

[LOG-ARTIFACT]  telemetry.db                                               0 bytes
  Git-tracked (verified). Empty SQLite placeholder at repo root. The live telemetry DB is
  generated at runtime by backend/bot/telemetry/. Explicitly listed for git rm in
  scripts/janitor_tranche1_3c.sh (2026-05-07) but never actioned. Confirmed 0-byte, empty file.
  Signals: 0-byte file + git-tracked placeholder with no runtime source feeding it + prior
  deletion proposal in scripts/janitor_tranche1_3c.sh.
  Recommended: DELETE (git rm telemetry.db).
  Note: NEW explicit confirmation this pass (missed in 2026-06-22 manifest).

[BUILD-ARTIFACT] .spark-initial-sha                                       41 bytes
  Git-tracked (verified). Contains a single SHA: 3e6a4991ab1112f4aee99d05b93bca79b9f93496.
  No reference to this file in package.json, pyproject.toml, Dockerfiles, .github/workflows,
  or any script. Identified as a Spark.ai platform deployment artifact. Listed for git rm in
  scripts/janitor_tranche1_3c.sh (2026-05-07). Not referenced by any active tooling.
  Signals: zero code/config references + explicitly targeted by prior deletion script.
  Recommended: DELETE (git rm .spark-initial-sha).
  Note: NEW explicit confirmation this pass (missed in 2026-06-22 manifest).

---

TRANCHE 2 — Documentation moves (archive, content unchanged)
-------------------------------------------------------------

[DOC-HISTORICAL -> MOVE]  prototype/  (1.1 MB, 24 files)  ->  archive/prototype/
  Evidence: Pre-React prototype era (standalone HTML/JSX files — app.jsx, scanner.jsx, intel.jsx,
  bot-shell.jsx, gauntlet.jsx, landing.jsx, journal.jsx, setup.jsx, training.jsx, tweaks-panel.jsx
  + 8 rendered HTML snapshots). README.md confirms "baseline prototype for UI design reference."
  No imports from backend or src/. baseline-screenshots/ contains PNG reference shots — historical.
  Not referenced from any active .ts/.tsx/.py.
  Proposed: git mv prototype archive/prototype
  Status: CARRY-FORWARD from 2026-06-22 (proposed but not actioned).

[UNREF-BLOB -> MOVE]  docs/Phemex API OHLCV Data Breakdown.docx  (6.0 MB)  ->  archive/docs/
  Git-tracked (verified). Heavy binary artifact in a text-only docs/ directory. No references
  from any active .py, .md, .ts, or .bat. Content superseded by backend/data/adapters/phemex.py
  and backend/diagnostics/contracts/.
  Proposed: git mv "docs/Phemex API OHLCV Data Breakdown.docx" "archive/docs/"
  Status: CARRY-FORWARD from 2026-06-22 (proposed but not actioned).

---

TRANCHE 3 — Quarantine (one-week soak, then delete)
----------------------------------------------------

[ORPHAN-TEST]  tests/test_backend.py  (1.2 KB)
  References-missing: scanner mode "recon" (removed; CLAUDE.md §SCANNER-MODES, scanner_modes.py)
  Content: Calls get_signals(..., sniper_mode="recon", ...) as a live function call with
  "recon" as the mode argument — not asserting its absence. This will route through
  scanner_modes.py which only defines OVERWATCH/STRIKE/SURGICAL/STEALTH and would reject "recon"
  as an unknown mode. Not collected by backend/tests/ conftest.
  Signals: (1) uses removed mode as live call argument (not asserting absence);
           (2) no pytest runner collects this file from tests/ root (not in backend/tests/).
  Recommended: quarantine-after-confirm -> tests/_quarantine/test_backend.py (one-week soak).
  Note: NEW this pass — missed in 2026-06-22 manifest.

[ORPHAN-TEST]  tests/test_orchestrator_imports.py  (830 bytes)
  References-missing: scanner mode "recon" + hardcoded /workspaces/ path
  Content: Calls ScanConfig(profile="recon") — not asserting its absence. Also hardcodes
  sys.path.append('/workspaces/snipersight-trading') (a Codespaces-era path, not the current
  /home/user/ container path). Both confirm stale dev-environment script, not active regression guard.
  Signals: (1) uses removed mode as live argument (not asserting absence);
           (2) hardcoded /workspaces/snipersight-trading path — wrong in current environment.
  Recommended: quarantine-after-confirm -> tests/_quarantine/test_orchestrator_imports.py.
  Note: NEW this pass — missed in 2026-06-22 manifest.

---

TRANCHE 4 — Review-only (do not touch without further analysis)
---------------------------------------------------------------

[DOC-STALE-CURRENT — CARRY-FORWARD]  ARCHITECTURE.md  (62 KB)
  Status banner added 2026-05-22. 9+ "Recon Mode" references remain below banner. Full rewrite
  (estimated 1-2h, decisions/2026-05-22__docs-rewrite-blueprint-to-built.md) has not shipped
  in 3 successive passes. Current risk: LOW (banner warns readers).
  Drift detected: "Recon Mode" throughout; pipeline diagrams predate SniperContext; PRD.md
  references (file removed); "two modes" framing vs. four-mode reality.
  Recommended: No new action — rewrite is on the backlog. Carry forward (fourth pass).

[DOC-STALE-CURRENT — CARRY-FORWARD]  PROJECT_STRUCTURE.md  (27 KB)
  Status banner added 2026-05-22. Tree below banner references snipersight_cli.py at root,
  contracts/ at root, shared/ at root — all wrong vs. actual layout.
  Recommended: Carry forward; rewrite contingent on ARCHITECTURE.md rewrite completing.

[DOC-STALE-CURRENT — CARRY-FORWARD]  QUICKSTART.md  (15 KB)
  Status banner + real quickstart section added 2026-05-22. Stale PRD.md references persist
  below the banner (lines 428, 467). Risk is VERY LOW (real quickstart precedes historical).
  Recommended: Carry forward; clean historical section after ARCHITECTURE.md lands.

[DOC-STALE-CURRENT — CARRY-FORWARD]  SETUP_INSTRUCTIONS.md  (1 KB)
  Generic Windows install guide for Git/Node/Python with no SniperSight-specific content.
  Not referenced from any .py, .md, .bat, or .yml. No reference to venv, requirements.txt,
  uvicorn, or C:\start-sniper.bat.
  Recommended: Either rewrite to cover actual setup or delete (QUICKSTART.md covers same ground).
  Status: Carry-forward from 2026-06-22.

[DOC-STALE-CURRENT]  docs/SMC_PIPELINE_REFACTOR.md
  Header: "Date: December 2025 / Status: Mostly Complete." Body contains TODO items for
  "Merge RECON + GHOST -> STEALTH" at lines 104, 128-129, 541, 585. These are completed work
  per CLAUDE.md §STANDING-FIXES and scanner_modes.py (only four modes exist).
  Drift detected: recon/ghost TODOs that are now resolved; "Mostly Complete" planning status
  on a completed migration.
  Recommended: Reclassify as HISTORICAL (planning artifact, intentionally frozen), move to
  archive/reports/2025-12-SMC_PIPELINE_REFACTOR.md. The WHY context is worth preserving;
  the imperative language is confusing in-place.

[DOC-STALE-CURRENT — NEW]  docs/INTEGRATION_GUIDE.md
  Drift detected: Line 29 states "Frontend will be available at: http://localhost:5173" but
  CLAUDE.md and vite.config.ts configure port 5000. Also references wallet_address query
  params in API examples — partial feature, with WalletConnect showing "coming soon" in
  WalletContext.tsx (line 94).
  Recommended: flag-for-rewrite. Port 5173 -> 5000 is a one-line fix; wallet_address
  sections need a "partial implementation" note.

[DOC-STALE-CURRENT — NEW]  docs/API_ADDITIONS.md
  Content: Imperative planning stub — "Add these endpoints after the four-year-cycle endpoint:"
  The symbol_cycle_detector module is implemented and wired in api_server.py (verified at
  lines 2347, 2608, 2684). Prescriptive purpose is fulfilled; doc now reads as an active task
  when it's actually a historical planning artifact.
  Recommended: Reclassify as HISTORICAL, move to archive/reports/. If moved, note fulfillment date.

[DOC-SUSPECT — NEW]  docs/WALLET_AUTHENTICATION.md
  Content: Describes wallet-based authentication in present tense as fully implemented.
  src/context/WalletContext.tsx line 94: throw new Error('WalletConnect integration coming soon').
  Partial wiring exists (wallet_address query params, WebSocket paths) but frontend auth flow
  is explicitly incomplete.
  Recommended: flag-for-review. Add "partial implementation" banner or update to describe
  what's actually live vs. what's planned.

[CONFIG-DRIFT — CARRY-FORWARD]  package.json -> react-day-picker dep
  react-day-picker still in package.json and package-lock.json. Only reference in src/ is
  src/_archive/components/ui/calendar.tsx (archived Radix-era component — not live). Zero
  hits in active src/ (excluding _archive/). Missed in the 44-dep May eject.
  Recommended: npm uninstall react-day-picker + lockfile regeneration. Low risk.

[SUSPECT-STUB — CARRY-FORWARD]  backend/examples/__init__.py  (0 bytes)
[SUSPECT-STUB — CARRY-FORWARD]  backend/devtools/__init__.py  (0 bytes)
  Both directories contain only an empty __init__.py with no other content. Single-signal
  only (empty stub namespace). Could be reserved namespace packages or forgotten.
  Recommended: operator intent check — if planned namespace packages, leave; if forgotten
  stubs, remove in same commit as a Tranche-1 cleanup.

[SUSPECT-SCRIPT]  scripts/janitor_tranche1_3c.sh  (9 KB)
  Generated 2026-05-07 by the repo-janitor agent as a one-time cleanup script. Its target
  list (47 debug-output files, telemetry.db, .spark-initial-sha, 11 root test scripts) is
  now partially executed (root test scripts gone from prior pass actions). Remaining live
  targets (telemetry.db, .spark-initial-sha, diagnostics/*.txt) are in Tranche-1 above.
  Single-signal flag (generated one-time utility, superseded by three janitor passes).
  Recommended: flag-for-review. If operator approves Tranche-1, this script becomes moot
  and can be removed in the same commit.

---

Off-limits items observed (for your awareness — NOT proposed for action)
------------------------------------------------------------------------
- .live_trading/ — hard off-limits per agent rules; not walked
- .coverage (root file) — off-limits per agent rules
- .git/, .github/, .storybook/ — off-limits
- CLAUDE.md — read-only reference
- LICENSE — never touch
- Dockerfile.backend, Dockerfile.frontend, .dockerignore — load-bearing deployment configs
- .claude/agents/*.md — tooling, not documentation
- .claude/skills/ — tooling, not documentation
- backend/diagnostics/*.py — ALL protected per CLAUDE.md §12 (iterate-loop diagnostic scripts)
  (including the new cvd_capture_health.py, cvd_historical_edge.py, account_aware_liquidity_diagnostic.py)
- backend/diagnostics/decisions/ — HISTORICAL+ACTIVE, correctly placed, no action needed
- backend/diagnostics/phase_archive/ — HISTORICAL, correctly placed
- backend/tests/unit/ new files (test_account_aware_liquidity.py, test_cvd_tracker.py,
  test_decision_core.py, test_executor_realized_matches_balance.py, test_fresh_entry_guard.py,
  test_liquidity_floor.py, test_pnl_no_double_count.py, test_reachability_decline_boundary.py,
  test_rr_bounded_snap.py) — ALL ACTIVE tests for heart-change implementation; not touched
- src/_archive/ (all components excluding TopBarLite.tsx.bak) — intentionally archived
- tests/visual/__baselines__/ (PNG regression baselines) — ACTIVE test fixtures
- Standing-fix surface: scorer.py, orchestrator.py, regime_*.py, scanner_modes.py, smc_*.py,
  smc_service.py, regime_policies.py — KEEP per §10; no clutter found in any of these
- backend/bot/cvd/ (new CVD tracker) — ACTIVE, freshly landed in heart-change stack
- DESIGN.md — ACTIVE brand/design-token specification (not a stale architectural doc)
- docs/CYCLE_TRANSLATION_SYSTEM.md — ACTIVE reference for the cycle translation implementation
- docs/TELEMETRY_GUIDE.md, docs/exchange_profiles.md, docs/indicator_validation.md,
  docs/sniper_ui_theme.md, docs/security.md — all ACTIVE reference material

---

Proposed Tranche-1 Command (DO NOT RUN until operator approves)
---------------------------------------------------------------
# Step 1: diagnostic txt dumps (29 files) + empty directory
git rm -r diagnostics/

# Step 2: archive binary blobs (3 files)
git rm archive/files.zip "archive/files (2).zip" archive/snipersight-chart-fixes.zip

# Step 3: backup file inside archived component
git rm src/_archive/components/TopBar/TopBarLite.tsx.bak

# Step 4: root zero-byte and deployment artifacts (NEW this pass)
git rm telemetry.db .spark-initial-sha

Proposed Tranche-2 Command (DO NOT RUN until operator approves)
---------------------------------------------------------------
# Move prototype to archive
git mv prototype archive/prototype

# Move heavy docx to archive
mkdir -p archive/docs
git mv "docs/Phemex API OHLCV Data Breakdown.docx" "archive/docs/Phemex API OHLCV Data Breakdown.docx"

Proposed Tranche-3 Command (DO NOT RUN until operator approves)
---------------------------------------------------------------
# Quarantine orphan tests (one-week soak, then delete)
mkdir -p tests/_quarantine
git mv tests/test_backend.py tests/_quarantine/test_backend.py
git mv tests/test_orchestrator_imports.py tests/_quarantine/test_orchestrator_imports.py

Config-Drift Fix (separate from tranches)
-----------------------------------------
# Run in repo root with node installed (same gates as May eject)
npm uninstall react-day-picker
# Verify: npx tsc --noEmit && vite build && python -m backend.diagnostics.capture_contracts diff

---

RAW EVIDENCE
============

root diagnostics/ file count and total size:
  29 files, 328 KB total
  Oldest content: "Generated: 2026-03-22 19:42:24" (fvg_diag_1d.txt — BTC/USDT 1d FVG run)
  git ls-files diagnostics/ | wc -l -> 29 (all tracked)

archive/ zip sizes and tracking:
  archive/files.zip          36 KB  (git-tracked — confirmed git ls-files)
  archive/files (2).zip      12 KB  (git-tracked)
  archive/snipersight-chart-fixes.zip  48 KB (git-tracked)
  Total: 96 KB

root artifact sizes:
  telemetry.db:       0 bytes  (git-tracked — confirmed)
  .spark-initial-sha: 41 bytes (git-tracked — confirmed)

prototype/ size: 1.1 MB (24 tracked files)
docs/Phemex API OHLCV Data Breakdown.docx: 6.0 MB (git-tracked)
src/_archive/ size: 1.5 MB

Orphan-test evidence:
  tests/test_backend.py line 16:
    result = await get_signals(limit=3, min_score=70, sniper_mode="recon", ...)
    # comment above: "Use a valid sniper_mode defined in scanner_modes (e.g., 'recon')"
    # "recon" has been invalid since the four-mode fix; comment is itself stale
  tests/test_orchestrator_imports.py line 6:
    sys.path.append('/workspaces/snipersight-trading')
  tests/test_orchestrator_imports.py line 18:
    config = ScanConfig(profile="recon")

  Ghost/recon tests that ARE asserting absence (NOT orphan — confirmed active):
    backend/tests/unit/test_fade_threshold_rsi_symmetry.py -> tests rejection of ghost
    backend/tests/unit/test_ob_freshness_gate_authority.py -> pytest.raises(ValueError) on ghost

react-day-picker evidence:
  package.json: "react-day-picker": "^9.6.7"
  Active src/ hits (excl. _archive): 0
  Archive hit: src/_archive/components/ui/calendar.tsx line 4 (archived Radix-era component)

docs/INTEGRATION_GUIDE.md port drift:
  Line 29: "Frontend will be available at: http://localhost:5173"
  Actual: CLAUDE.md §STACK -> port 5000; vite.config.ts confirms port 5000

docs/API_ADDITIONS.md fulfillment evidence:
  backend/api_server.py lines 2347, 2608, 2684 — symbol_cycle_detector imported and wired
  backend/strategy/smc/symbol_cycle_detector.py — module exists and is live

docs/WALLET_AUTHENTICATION.md partial-impl evidence:
  src/context/WalletContext.tsx line 94:
    throw new Error('WalletConnect integration coming soon')
  backend/api_server.py: wallet_address WebSocket path exists (line 282) — backend partial

scripts/janitor_tranche1_3c.sh: generated 2026-05-07, remaining live targets:
  - diagnostics/*.txt (still present -> now in Tranche 1 above)
  - telemetry.db (still present -> now in Tranche 1 above)
  - .spark-initial-sha (still present -> now in Tranche 1 above)
  - 11 root test_*.py scripts (GONE from prior pass actions)

Recent commits since 2026-06-22 janitor (all in backend/ or src/ — no new root clutter):
  4200ef2 feat(diag): retroactive CVD edge test — VERDICT: NOISE
  f548b2f fix(ui): Session Duration 0
  b657e17 feat(cvd): order-flow forward-capture Phase A
  [... 27 more backend/src commits, zero new root-level file additions]

STATUS OF PRIOR MANIFEST ITEMS (2026-06-22):
  Tranche 1 (33 items): NOT ACTIONED — all still present; 2 new items added (telemetry.db,
    .spark-initial-sha) missed in prior pass.
  Tranche 2 (prototype/ + docx): NOT ACTIONED — both still in original locations.
  Orphan tests: MISSED in prior pass — caught this pass (test_backend.py,
    test_orchestrator_imports.py).
  Config-drift (react-day-picker): NOT ACTIONED — still in package.json.
  ARCHITECTURE/PROJECT_STRUCTURE/QUICKSTART stale docs: Status banners still in place; full
    rewrites still outstanding. Risk level unchanged (LOW due to banners).
  backend/examples/ and backend/devtools/ SUSPECT-STUB: NOT ACTIONED — operator intent
    still unknown.

---

Recommended Next Step
---------------------
1. Approve Tranche 1 (29 diagnostic txts + 3 zips + 1 .bak + telemetry.db + .spark-initial-sha
   = 35 files, ~430 KB). Zero-risk, all git-recoverable. This is the FOURTH pass — these
   items have been unactioned across three prior manifests. Proposed command above.
2. Approve Tranche 3 (quarantine 2 orphan tests). Low-risk: move to tests/_quarantine/,
   soak one week, then delete. Both are verifiably stale (recon mode refs + wrong sys.path).
3. Approve Tranche 2 moves (prototype/ + docx). Cosmetic relocations, no content changes.
4. Fix react-day-picker CONFIG-DRIFT (npm uninstall, 5-minute task). Same verification
   gates as May eject.
5. Review docs/INTEGRATION_GUIDE.md port drift (5173 -> 5000 is a one-line fix).
6. Classify docs/API_ADDITIONS.md — if endpoints are fully wired, move to archive/reports/
   as historical planning artifact.
7. Add "partial implementation" banner to docs/WALLET_AUTHENTICATION.md.
8. Schedule ARCHITECTURE.md rewrite — fourth carry-forward. Highest-leverage remaining
   doc item; actively misleads anyone who skips the status banner.
9. Cross-check docs/TF_RESPONSIBILITY_FLOW.txt against live orchestrator.py (carry-forward
   from June 22 pass — still unverified; Phase-5 HTF gate changes may have drifted it).
10. Re-run repo-janitor after Tranche 1 + 3 land to detect cascade orphans.

Note: 51 candidates exceeds the ~50-item threshold for engineering:tech-debt skill invocation.
Recommend running that skill in parallel with the Tranche 1 cleanup to prioritize the remaining
Tranche 4 doc rewrites against active engineering work.
