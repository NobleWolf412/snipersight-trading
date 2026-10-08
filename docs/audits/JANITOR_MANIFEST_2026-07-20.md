REPO-JANITOR INVENTORY
======================
Date: 2026-07-20
Scope: Full repo minus off-limits list; git-tracked files only unless noted
Prior manifest: docs/audits/JANITOR_MANIFEST_2026-07-06.md
Off-limits respected: YES — .live_trading/, .coverage, .git/, .github/, .storybook/, .cursor/,
  CLAUDE.md, LICENSE, Dockerfile.*, .dockerignore, .claude/agents/*.md, .claude/skills/,
  .claude/worktrees/, backend/diagnostics/*.py (§12 iterate-loop scripts), backend/diagnostics/decisions/,
  backend/diagnostics/phase_archive/, standing-fix surface (scorer.py, orchestrator.py, regime_*.py,
  scanner_modes.py, smc_*.py, smc_service.py, regime_policies.py) — all KEEP per CLAUDE.md §10.

Activity since 2026-07-06 (2 commits):
  4200ef2 feat(diag): retroactive CVD edge test (Binance dumps) — VERDICT: NOISE (5th strike)
           → Added backend/diagnostics/cvd_historical_edge.py (KEEP §12) + decisions log update.
  f548b2f fix(ui): allow Session Duration 0 = run until manually stopped (long-capture)
           → src/pages/training/RangeBot.tsx slider min 1→0 (KEEP, active UI).
  Net new clutter: ZERO.

ZERO TRANCHE-1 ITEMS ACTIONED since 2026-07-06. All 51 items from that pass carry forward.
The diagnostics/*.txt files have now been flagged in FIVE consecutive passes (May-07, May-20,
Jun-22, Jul-06, Jul-20) with zero action. This is the longest-running unresolved item in the
repo's janitor history.

Total candidates: 56  (51 carry-forward + 5 newly surfaced SUSPECT-SCRIPTs)
By tranche:
  Tranche 1 (zero-risk delete):          35 items  (unchanged from Jul-06)
  Tranche 2 (low-risk archive moves):     2 groups  (unchanged from Jul-06)
  Tranche 3 (quarantine first):           2 items  (unchanged from Jul-06)
  Tranche 4 (review-only):              17 items  (12 carry-forward + 5 NEW this pass)

---

SHORT SUMMARY
=============

Total candidates by category:
  LOG-ARTIFACT        29 items  (diagnostics/*.txt — raw run-output dumps, pre-Phase-5 era)
  UNREF-BLOB           4 items  (3 archive zips + 1 docs docx, git-tracked)
  BACKUP-FILE          2 items  (TopBarLite.tsx.bak + telemetry.db 0-byte + .spark-initial-sha)
  HISTORICAL-MOVE      1 group  (prototype/ → archive/prototype/)
  ORPHAN-TEST          2 items  (test_backend.py + test_orchestrator_imports.py)
  DOC-STALE-CURRENT    7 items  (ARCHITECTURE.md, PROJECT_STRUCTURE.md, QUICKSTART.md,
                                  SETUP_INSTRUCTIONS.md, docs/SMC_PIPELINE_REFACTOR.md,
                                  docs/INTEGRATION_GUIDE.md, docs/API_ADDITIONS.md)
  DOC-SUSPECT          1 item   (docs/WALLET_AUTHENTICATION.md)
  CONFIG-DRIFT         1 item   (react-day-picker in package.json)
  SUSPECT-STUB         2 items  (backend/examples/ + backend/devtools/ — __init__.py only)
  SUSPECT-SCRIPT       6 items  (janitor_tranche1_3c.sh carry-forward + 5 NEW backtest scripts)

NOTE: telemetry.db (0B) and .spark-initial-sha (41B) are listed under Tranche 1 as BACKUP-FILE
  rather than a separate category. The count above groups them as 2 of the 35 Tranche-1 items.

Top 5 highest-confidence DELETE / quarantine recommendations:

  1. diagnostics/*.txt (29 files, ~324 KB) — Raw run-output dumps from March 2026,
     pre-Phase-5 era (pre-BOS/CHOCH structure rewrite, pre-P/D anchoring, pre-heart-change
     execution). Git-tracked. Zero references in any .py, .md, .yml, .bat, or .ts outside
     the janitor manifests that flagged them. Now flagged in FIVE CONSECUTIVE PASSES (May-07,
     May-20, Jun-22, Jul-06, Jul-20) with zero action. Highest-confidence delete in the repo.

  2. archive/files.zip (33.8 KB) + archive/files (2).zip (8.8 KB) +
     archive/snipersight-chart-fixes.zip (46.8 KB) — Pre-rebuild binary blobs, git-tracked,
     zero grep hits in any active code or config, no descriptive metadata. Flagged in
     2026-05-20, 2026-06-22, 2026-07-06. Not actioned in any of them.

  3. telemetry.db (0 bytes) + .spark-initial-sha (41 bytes) — telemetry.db is an empty
     SQLite placeholder (real DB generated at runtime). .spark-initial-sha is a Spark.ai
     deployment artifact (hardcoded SHA: 3e6a499...) not referenced in package.json, CI,
     Dockerfiles, or any .py. Both proposed for deletion in scripts/janitor_tranche1_3c.sh
     (2026-05-07) and flagged twice more since. Not actioned.

  4. tests/test_backend.py + tests/test_orchestrator_imports.py — Both use "recon" as a
     live scanner-mode argument (not asserting its absence). ORPHAN-TEST since Jul-06 pass.
     test_backend.py calls get_signals(..., sniper_mode="recon", ...) as a live API call;
     test_orchestrator_imports.py calls ScanConfig(profile="recon") and expects a live
     Orchestrator. Both would fail in any CI run that exercises them.

  5. src/_archive/components/TopBar/TopBarLite.tsx.bak (2.5 KB) — .bak file inside an
     already-archived component subtree. No active import from any live src/ code. Backup
     of a backup. Flagged in Jun-22 and Jul-06 passes; not actioned.

NEW CLUTTER SINCE 2026-07-06:
  None in Tranche 1-3.
  + 5 SUSPECT-SCRIPT items surfaced this pass (see Tranche 4 for detail):
    scripts/backtest_scanner.py     — hardcoded profile='recon' at 4 call sites
    scripts/backtest_modes.py       — recon+ghost in modes_to_test list
    scripts/backtest_full_pipeline.py — RECON/GHOST enum constants in argparse flow
    scripts/backtest_from_csv.py    — RECON enum constant defined
    scripts/debug/debug_arm_scanner.py — profile="recon", sniper_mode="recon" at 2 sites

CONFIRMED ACTIVE (not clutter, observed for completeness):
  + docs/TF_RESPONSIBILITY_FLOW.txt — ASCII diagram documenting TF enforcement for Surgical
    mode. References current 4-mode design (no recon/ghost). Created in d2bd736. ACTIVE, KEEP.
  + backend/tests/unit/test_fade_threshold_rsi_symmetry.py (ghost/recon refs at lines 120-155)
    — Asserting that unknown modes trigger §11 loud warning. ACTIVE, KEEP.
  + backend/tests/unit/test_ob_freshness_gate_authority.py (ghost ref at line 60)
    — Asserting that ValueError fires on unknown mode_profile. ACTIVE, KEEP.
  + backend/tests/integration/test_orchestrator_workflow.py.skip + test_smc_detection.py.skip
    — Already intentionally disabled via .skip extension (operator decision). Leave as-is.

---

TRANCHE 1 — Build artifacts, log outputs, backup files, root detritus
----------------------------------------------------------------------
(All git-tracked. Proposed action: git rm after operator approval.)

[LOG-ARTIFACT]  diagnostics/cycle_reversal_diagnostic_report.txt           7.0 KB
  Reason: Pre-Phase-5 raw reversal diagnostic. Zero imports. Not referenced outside janitor manifests.
[LOG-ARTIFACT]  diagnostics/cycle_reversal_diagnostic_report.utf8.txt       7.0 KB
  Reason: UTF-8 duplicate of the above.
[LOG-ARTIFACT]  diagnostics/diag.txt                                         3.0 KB
  Reason: One-shot diagnostic dump. No references outside this directory.
[LOG-ARTIFACT]  diagnostics/fvg_diag_1d.txt                                11.7 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_1h.txt                                11.2 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_1m.txt                                11.9 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_1w.txt                                11.8 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_4h.txt                                11.6 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_5m.txt                                11.8 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_doge.txt                              11.8 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_eth.txt                               11.8 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_sol.txt                               11.8 KB
[LOG-ARTIFACT]  diagnostics/fvg_diagnostic_report.txt                      11.8 KB
  Reason (fvg_diag_* group x10): FVG diagnostic outputs from pre-Phase-5 detection layer.
    Zero imports. Not referenced in any config, .py, or .yml. Engine has been substantially
    rewritten since (OB freshness gate, BOS/CHOCH structure, P/D anchoring, heart-change).
[LOG-ARTIFACT]  diagnostics/indicator_diagnostic_report.txt                 7.8 KB
  Reason: Indicator diagnostic from early 2026. Zero references outside janitor manifests.
[LOG-ARTIFACT]  diagnostics/ob_diag_15m.txt                                11.3 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_15m_final.txt                          11.3 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_15m_final2.txt                         11.3 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_1d.txt                                  7.8 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_1h.txt                                 11.6 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_1m.txt                                 11.6 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_1w.txt                                  7.8 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_4h.txt                                 11.6 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_5m.txt                                 11.6 KB
  Reason (ob_diag_* group x9): OB diagnostic outputs from pre-Phase-5 era. Same classification
    as fvg_diag above. OB scoring rewritten since (freshness gate authority, §15 precision merge).
[LOG-ARTIFACT]  diagnostics/output.txt                                       7.8 KB
  Reason: Generic output dump. Zero references in any active code.
[LOG-ARTIFACT]  diagnostics/reversal_diagnostic_report.txt                 23.0 KB
  Reason: Reversal diagnostic. Stale relative to direction-authority rewrite (2026-06-02).
[LOG-ARTIFACT]  diagnostics/smc_service_diagnostic_report.txt               7.8 KB
  Reason: SMC service diagnostic. Service has been reworked multiple times since.
[LOG-ARTIFACT]  diagnostics/sweep_diag_15m.txt                              3.5 KB
[LOG-ARTIFACT]  diagnostics/sweep_diag_all.txt                             14.8 KB
[LOG-ARTIFACT]  diagnostics/sweep_diagnostic_report.txt                    14.8 KB
  Reason (sweep_diag* group x3): Sweep diagnostic outputs. Engine has changed substantially.

[BACKUP-FILE]   telemetry.db (root)                                          0 bytes
  Reason: Empty SQLite placeholder. Live telemetry DB is runtime-generated at a separate path.
    Proposed in janitor_tranche1_3c.sh (May 2026), re-flagged three times. Two signals:
    (1) 0-byte, non-functional as DB; (2) not referenced in any backend startup or config.
[BACKUP-FILE]   .spark-initial-sha (root)                                    41 bytes
  Reason: Spark.ai deployment artifact. Content: hardcoded SHA. Not referenced in package.json,
    CI, Dockerfiles, or any .py. Two signals: (1) no code references; (2) Spark.ai is not
    part of the current build/deploy pipeline.
[BACKUP-FILE]   src/_archive/components/TopBar/TopBarLite.tsx.bak           2.5 KB
  Reason: .bak file inside an already-archived component subtree. No active import from
    live src/ code. Flagged Jun-22 and Jul-06. Two signals:
    (1) .bak extension; (2) zero imports from live src/ (confirmed by grep).

[UNREF-BLOB]    archive/files.zip                                           33.8 KB
[UNREF-BLOB]    archive/files (2).zip                                        8.8 KB
[UNREF-BLOB]    archive/snipersight-chart-fixes.zip                         46.8 KB
  Reason (archive zips x3): Pre-rebuild binary blobs. Git-tracked. No imports or references
    in any .py, .md, .yml, or .bat outside the prior janitor manifests. No descriptive README.
    First flagged May-20; re-flagged Jun-22 and Jul-06.

  Subtotal — Tranche 1: 35 items, ~457 KB git-tracked disk weight

---

TRANCHE 2 — Documentation moves (archive only, content unchanged)
-----------------------------------------------------------------
(Proposed action: git mv to archive path. Content rewrite is NOT in scope for this tranche.)

[HISTORICAL-MOVE]  prototype/  (entire directory, ~1.1 MB)
  → proposed destination: archive/prototype/
  Evidence: Pre-implementation HTML+JSX prototypes (Scanner.html, Bot.html, Intel.html,
    training.jsx, landing.jsx etc.) from the Blueprint era. The React HUD is now fully built
    and live. The prototype/ directory is an origin-story artifact, not a working reference.
    prototype/baseline-screenshots/ contains 1 screenshot file. No active code imports
    from prototype/. Prior manifest (Jul-06) proposed this move; not actioned.

[HISTORICAL-MOVE]  docs/Phemex API OHLCV Data Breakdown.docx               6.1 MB
  → proposed destination: archive/docs/Phemex API OHLCV Data Breakdown.docx
  Evidence: External API reference document. Content is a reference artifact, not active
    engineering documentation. The Phemex adapter (backend/data/adapters/phemex.py) and
    exchange_profiles.md already document live behavior. Not referenced in any .py or .md.
    Prior manifest (Jul-06) flagged as UNREF-BLOB (archive move, not delete). 6.1 MB is the
    heaviest single tracked file in the repo.

---

TRANCHE 3 — Quarantine (one-week soak, then delete)
---------------------------------------------------
(Proposed action: git mv to tests/_quarantine/. Review after one week.)

[ORPHAN-TEST]  tests/test_backend.py
  references-missing: sniper_mode="recon" (removed mode — CLAUDE.md §4)
  Signals:
    (1) Uses "recon" as a live sniper_mode argument (line 16), not asserting its absence.
        Call: get_signals(..., sniper_mode="recon", exchange="phemex", ...). Would fail at
        runtime since scanner_modes.py has no "recon" mode.
    (2) Not collected by pytest.ini / conftest.py in backend/tests/; sits in root tests/
        but backend API imports suggest it was written for the old module layout.
  Note: First flagged Jul-06. Still unactioned.

[ORPHAN-TEST]  tests/test_orchestrator_imports.py
  references-missing: ScanConfig(profile="recon"), hardcoded /workspaces/ path
  Signals:
    (1) Calls ScanConfig(profile="recon") (line 18) — profile no longer exists in scanner_modes.py.
    (2) sys.path.append('/workspaces/snipersight-trading') (line 7) — hardcoded container path,
        not the live repo path (/home/user/snipersight-trading). Double stale signal.
  Note: First flagged Jul-06. Still unactioned.

---

TRANCHE 4 — Review-only (do not touch without further analysis)
---------------------------------------------------------------

── Carry-forward from 2026-07-06 ──

[DOC-STALE-CURRENT]  ARCHITECTURE.md  (62.9 KB)
  Drift detected:
    - Describes "Scanner Mode (Recon)" as a live mode (line 11, 18-20 etc.)
    - References PRD.md (removed — now PRODUCT.md)
    - Pipeline diagrams predate the SniperContext-based design (backend/engine/context.py)
    - Header banner acknowledges staleness but doc is 62.9 KB of active-looking technical prose
  Recommended: flag-for-rewrite. Not a move.

[DOC-STALE-CURRENT]  PROJECT_STRUCTURE.md  (26.8 KB)
  Drift detected:
    - Header acknowledges: "described a future Python-only project; the live tree has both
      backend/ (FastAPI) and src/ (React HUD)"
    - Package paths no longer match live tree structure
  Recommended: flag-for-rewrite.

[DOC-STALE-CURRENT]  QUICKSTART.md  (14.9 KB)
  Drift detected:
    - Setup instructions may reference old startup paths or port assumptions
    - CLAUDE.md is authoritative for startup (start-sniper.bat). QUICKSTART may lag behind.
  Recommended: cross-check against CLAUDE.md §2 (STACK), then rewrite or supersede.

[DOC-STALE-CURRENT]  SETUP_INSTRUCTIONS.md  (1.0 KB)
  Drift detected:
    - Minimal doc (1 KB). Likely redundant with QUICKSTART.md and README.md §Setup.
  Recommended: verify content, fold into README if redundant, delete if superseded.

[DOC-STALE-CURRENT]  docs/SMC_PIPELINE_REFACTOR.md  (24.4 KB)
  Drift detected:
    - Header: "Status: Mostly Complete (Grading implemented, mode consolidation done)"
    - Written December 2025. Pipeline has had substantial rework since (Phase-4/5 series,
      BOS/CHOCH structure, P/D anchoring, direction-authority rewrite, heart-change).
    - Still describes the pre-Phase-4 ATR-threshold rejection problem as the target to fix.
    - The "game plan" items described are now complete or superseded.
  Classification: HISTORICAL (completed refactor doc) but not yet in archive/.
  Recommended: git mv to archive/reports/SMC_PIPELINE_REFACTOR.md (historical, not stale-current).

[DOC-STALE-CURRENT]  docs/INTEGRATION_GUIDE.md  (8.3 KB)
  Drift detected:
    - References port 5173 (old Vite default). Live frontend is port 5000 (CLAUDE.md §2).
  Recommended: flag-for-rewrite (port update minimum).

[DOC-STALE-CURRENT]  docs/API_ADDITIONS.md  (9.7 KB)
  Drift detected:
    - Written as a prescriptive "add these endpoints" stub (imperative, future-tense throughout).
    - Endpoints described (/api/market/symbol-cycles etc.) are now wired in api_server.py.
    - Purpose fulfilled. Doc reads as live spec but is now a historical implementation note.
  Classification: HISTORICAL (fulfilled prescription doc).
  Recommended: git mv to archive/reports/API_ADDITIONS.md OR delete (zero reference value remaining).

[DOC-SUSPECT]  docs/WALLET_AUTHENTICATION.md  (7.1 KB)
  Why suspect: Describes a fully-wired wallet auth flow but WalletContext.tsx indicates
    WalletConnect is "coming soon." Single signal (content vs. implementation gap).
    Could be aspirational spec or could be stale — needs code cross-check to confirm.
  Recommended: cross-check WalletContext.tsx implementation depth before reclassifying.

[CONFIG-DRIFT]  package.json — react-day-picker: "^9.6.7"
  Issue: react-day-picker is listed as a dependency but grep across src/ finds no active
    import. The 2026-05-22 dep eject removed 44 packages; react-day-picker survived that
    pass (not on the explicit eject list). Single signal (no active import found).
  Recommended: grep -r 'react-day-picker\|DayPicker\|DatePicker' src/ to confirm before
    adding to next eject batch.

[SUSPECT-STUB]  backend/examples/  (only __init__.py, 0 bytes)
  Why suspect: Stub directory with no content other than __init__.py. Not referenced
    in Dockerfile.backend or any Python entrypoint. Single signal.

[SUSPECT-STUB]  backend/devtools/  (only __init__.py, 0 bytes)
  Why suspect: Same as backend/examples/. Empty stub. Single signal.

[SUSPECT-SCRIPT]  scripts/janitor_tranche1_3c.sh  (6.1 KB)
  Why suspect: One-time cleanup script generated 2026-05-07. Most targets it listed
    have since been deleted from the build context (e.g. debug-587019.log). The remaining
    targets (diagnostics/*.txt, telemetry.db etc.) are still present — but the script itself
    is now a historical artifact of an unexecuted cleanup, not a live tool.
  Carry-forward from Jul-06.

── NEW this pass (2026-07-20) ──

[SUSPECT-SCRIPT]  scripts/backtest_scanner.py  (7.8 KB)
  Why suspect: profile='recon' hardcoded at four call sites (lines 104–105, 171–172).
    get_mode('recon') will return None or raise — scanner_modes.py has no recon entry.
    The script appears mode-locked to recon (not parameterized via argparse).
    Signal 1: removed mode hardcoded at all execution paths.
    Signal 2: not invoked from run_backtest.sh, package.json scripts, or CI.
  Recommended: Operator reviews whether this script is still useful; if so, update to a
    valid mode (overwatch/strike/surgical/stealth) or add --mode argparse flag.

[SUSPECT-SCRIPT]  scripts/backtest_modes.py  (13.3 KB)
  Why suspect: modes_to_test = ['overwatch', 'recon', 'strike', 'surgical', 'ghost'] (line 361)
    and profile='recon' at line 200. recon+ghost entries will fail when get_mode() is called.
    The other three modes would still execute correctly — partially broken, not fully dead.
    Signal 1: removed modes in modes_to_test list → KeyError/None on execution.
  Recommended: Remove 'recon' and 'ghost' from modes_to_test; update line 200 profile.
    One-line fix, not a quarantine. Included here for operator awareness.

[SUSPECT-SCRIPT]  scripts/backtest_full_pipeline.py  (37.4 KB)
  Why suspect: Defines RECON = "recon" and GHOST = "ghost" in a mode enum (lines 60, 63).
    argparse --mode help text uses "recon" as the example. Running with --mode recon or
    --mode ghost will invoke get_mode() and fail.
    Signal 1: removed mode names in argparse choices → runtime KeyError for those paths.
  Recommended: Remove RECON/GHOST from the enum; update --mode help text and any branch
    that switches on these. Remaining modes fully valid.

[SUSPECT-SCRIPT]  scripts/backtest_from_csv.py  (25.6 KB)
  Why suspect: Defines RECON = "recon" at line 54. Usage across the file may pass this
    as a mode to the engine.
    Signal 1: removed mode name in constant → runtime failure when used.
  Recommended: Replace RECON constant with a valid mode default (e.g. OVERWATCH).

[SUSPECT-SCRIPT]  scripts/debug/debug_arm_scanner.py
  Why suspect: Uses profile="recon" (line 58) and sniper_mode="recon" (line 95) as live
    arguments to the orchestrator/API. Would fail at runtime.
    Signal 1: removed mode passed as live argument to two call sites.
  Recommended: Update to a valid mode before use. Low-risk one-line fix.

---

Off-limits items observed (for your awareness — NOT proposed for action)
------------------------------------------------------------------------
- .live_trading/           (off-limits, leave entirely alone)
- .git/, .github/          (off-limits)
- .cursor/, .storybook/    (off-limits)
- CLAUDE.md                (off-limits — constitution file)
- LICENSE                  (off-limits)
- Dockerfile.backend, Dockerfile.frontend, .dockerignore (off-limits)
- .claude/agents/*.md      (tooling, not docs)
- .claude/skills/          (off-limits)
- .claude/worktrees/       (assume active)
- backend/diagnostics/*.py (§12 iterate-loop scripts — KEEP: confluence_diagnostic.py,
    sweep_diagnostic.py, fetch_diagnostics.py, get_diagnostics.py, cvd_historical_edge.py, etc.)
- backend/diagnostics/decisions/ (decisions log — all KEEP, audit trail)
- backend/tests/unit/test_fade_threshold_rsi_symmetry.py lines 120–155 (ghost/recon refs)
    — Asserting §11 loud-failure for unknown modes. ACTIVE, KEEP.
- backend/tests/unit/test_ob_freshness_gate_authority.py line 60 (ghost ref)
    — Asserting ValueError on unknown mode_profile. ACTIVE, KEEP.
- backend/tests/integration/test_orchestrator_workflow.py.skip
    — Already intentionally disabled via .skip extension. Operator decision. Leave as-is.
- backend/tests/integration/test_smc_detection.py.skip
    — Already intentionally disabled via .skip extension. Leave as-is.
- docs/TF_RESPONSIBILITY_FLOW.txt
    — ASCII diagram documenting current 4-mode TF enforcement. No stale references. ACTIVE.
- All standing-fix surface files (scorer.py, orchestrator.py, regime_*.py, scanner_modes.py,
    smc_*.py, smc_service.py, regime_policies.py) — KEEP per CLAUDE.md §10.

---

Proposed Tranche-1 Command (DO NOT RUN until operator approves)
---------------------------------------------------------------

# Step A — Remove diagnostics/*.txt (29 files, ~324 KB)
git rm diagnostics/cycle_reversal_diagnostic_report.txt \
       diagnostics/cycle_reversal_diagnostic_report.utf8.txt \
       diagnostics/diag.txt \
       diagnostics/fvg_diag_1d.txt \
       diagnostics/fvg_diag_1h.txt \
       diagnostics/fvg_diag_1m.txt \
       diagnostics/fvg_diag_1w.txt \
       diagnostics/fvg_diag_4h.txt \
       diagnostics/fvg_diag_5m.txt \
       diagnostics/fvg_diag_doge.txt \
       diagnostics/fvg_diag_eth.txt \
       diagnostics/fvg_diag_sol.txt \
       diagnostics/fvg_diagnostic_report.txt \
       diagnostics/indicator_diagnostic_report.txt \
       diagnostics/ob_diag_15m.txt \
       diagnostics/ob_diag_15m_final.txt \
       diagnostics/ob_diag_15m_final2.txt \
       diagnostics/ob_diag_1d.txt \
       diagnostics/ob_diag_1h.txt \
       diagnostics/ob_diag_1m.txt \
       diagnostics/ob_diag_1w.txt \
       diagnostics/ob_diag_4h.txt \
       diagnostics/ob_diag_5m.txt \
       diagnostics/output.txt \
       diagnostics/reversal_diagnostic_report.txt \
       diagnostics/smc_service_diagnostic_report.txt \
       diagnostics/sweep_diag_15m.txt \
       diagnostics/sweep_diag_all.txt \
       diagnostics/sweep_diagnostic_report.txt

# Step B — Remove root detritus (telemetry.db, .spark-initial-sha, archive zips)
git rm telemetry.db .spark-initial-sha
git rm "archive/files.zip" "archive/files (2).zip" "archive/snipersight-chart-fixes.zip"

# Step C — Remove .bak file
git rm src/_archive/components/TopBar/TopBarLite.tsx.bak

# Verify before committing
git status
# Expected: 35 deletions, no other changes

---

Proposed Tranche-2 Command (DO NOT RUN until operator approves)
---------------------------------------------------------------

# Archive prototype/
git mv prototype archive/prototype

# Archive docx
mkdir -p archive/docs
git mv "docs/Phemex API OHLCV Data Breakdown.docx" "archive/docs/Phemex API OHLCV Data Breakdown.docx"

---

Proposed Tranche-3 Command (DO NOT RUN until operator approves)
---------------------------------------------------------------

mkdir -p tests/_quarantine
git mv tests/test_backend.py tests/_quarantine/test_backend.py
git mv tests/test_orchestrator_imports.py tests/_quarantine/test_orchestrator_imports.py
# One-week soak. If no objections, git rm the quarantine dir.

---

Recommended Next Step
---------------------
1. Operator: approve or strike items from Tranche 1, then run the proposed git rm command
   above (or ask an agent to run it after explicit approval). PRIORITY: The 29 diagnostics/*.txt
   files have been flagged FIVE TIMES. These are the single highest-confidence delete in the repo.

2. Tranche 1 actioned → run repo-janitor again to detect cascade orphans.

3. Tranche 2 archive moves: prototype/ + docx. Low-risk, independently stageable.

4. Tranche 3 quarantine: test_backend.py + test_orchestrator_imports.py. One-line git mv.
   Zero risk to the live test suite (neither is collected by backend/tests/).

5. Tranche 4 — recommended sub-priorities:
   a. scripts/backtest_scanner.py: one-line mode-name fix (highest-risk of the 5 new suspects
      — the script appears fully mode-locked to 'recon', not just partially broken).
   b. react-day-picker: grep src/ to confirm zero imports; if confirmed, add to next dep eject.
      (2026-05-22 dep eject removed 44 packages; react-day-picker survived that pass.)
   c. SETUP_INSTRUCTIONS.md: 1 KB, likely redundant — fold into README or delete.
   d. docs/SMC_PIPELINE_REFACTOR.md → archive/reports/ (historical completed-refactor doc,
      not a stale-current doc; archive move is lower risk than rewrite).
   e. docs/API_ADDITIONS.md → archive/reports/ (fulfilled prescription doc).
   f. ARCHITECTURE.md, PROJECT_STRUCTURE.md, QUICKSTART.md — full rewrite needed; invoke
      engineering:documentation skill when capacity allows. High effort, non-urgent.

6. Dep eject queue (separate decision track): react-day-picker is the only surviving
   candidate from the 2026-05-22 pass. Confirm usage, then eject if zero-use confirmed.

7. backend/examples/ + backend/devtools/ stubs: single-signal only. Do not delete without
   confirming they're not used by any plugin or import hook outside the visible code tree.

NOTE: This manifest exceeds 50 candidates (~56 items). Per repo-janitor protocol, the
  engineering:tech-debt skill is recommended for prioritization across tranches when capacity
  allows. Tranche 1 is zero-risk and should be actioned first regardless.

auditor track unblocks when operator reviews this manifest in claude.ai/code
