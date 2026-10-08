REPO-JANITOR INVENTORY
======================
Date: 2026-08-17
Scope: Full repo minus off-limits list; git-tracked files only unless noted
Prior manifest: docs/audits/JANITOR_MANIFEST_2026-08-03.md
Off-limits respected: YES — .live_trading/, .coverage, .git/, .github/, .storybook/, .cursor/,
  CLAUDE.md, LICENSE, Dockerfile.*, .dockerignore, .claude/agents/*.md, .claude/skills/,
  .claude/worktrees/, backend/diagnostics/*.py (§12 iterate-loop scripts),
  backend/diagnostics/decisions/, backend/diagnostics/phase_archive/,
  standing-fix surface (scorer.py, orchestrator.py, regime_*.py, scanner_modes.py, smc_*.py,
  smc_service.py, regime_policies.py) — all KEEP per CLAUDE.md §10.
  DESIGN.md — ACTIVE (referenced by live src/components/); excluded from candidates.
  .claude/skills/ui-ux-pro-max/scripts/core.py — tooling script; false-positive of core.* 
  pattern for core dumps; skipped per off-limits rule on .claude/skills/.

Activity since 2026-08-03 (0 code commits):
  565d85f docs(janitor): weekly repo-janitor inventory manifest 2026-08-03 (the manifest itself)
  Net new clutter from code activity: ZERO.
  Net new candidates this pass: ZERO.

RESOLUTION TRACKER — carry-forward aging (weeks since first flagged → weeks since last manifest):
  telemetry.db + .spark-initial-sha:     15 weeks (first 2026-05-07; 7 passes; ZERO action) ⚠ ESCALATE
  archive/*.zip (3 blobs):               13 weeks (first 2026-05-20; 6 passes; ZERO action) ⚠ ESCALATE
  src/_archive/TopBarLite.tsx.bak:        8 weeks (first 2026-06-22; 5 passes; ZERO action)
  prototype/ → archive/prototype/:        8 weeks (first 2026-06-22; 5 passes; ZERO action)
  orphan tests (2):                       6 weeks (first 2026-07-06; 5 passes; ZERO action)
  docs/Phemex API OHLCV Data Breakdown.docx:  2 passes (re-surfaced 2026-08-03; unactioned)
  src/assets/documents/{info,index}:      3 weeks (first 2026-07-27; 2 passes; ZERO action)
  SECURITY.md vs docs/security.md:        2 passes (new 2026-08-03; unactioned)

ESCALATIONS this pass:
  telemetry.db + .spark-initial-sha → 15 weeks / 7 passes is past "accumulating" — now chronic.
    These are pure zero-risk deletes. Recommend operator action in next session.
  archive/*.zip (3 blobs) → 13 weeks / 6 passes. Largest T1 size item (89.2 KB). Same status.

NEW ITEMS this pass: NONE

Total candidates: 31 (all carry-forward; zero new items)
By tranche:
  Tranche 1 (zero-risk delete):          8 items  (all carry-forward; all 7+ passes unactioned)
  Tranche 2 (low-risk archive moves):    2 items  (prototype/ + Phemex docx)
  Tranche 3 (quarantine first):          2 items  (orphan tests — recon mode refs)
  Tranche 4 (review-only):             19 items  (stale docs + config drift + suspect stubs + stale scripts)

---

SHORT SUMMARY
=============

Total candidates by category:
  UNREF-BLOB           3 items  (archive/*.zip — binary blobs, git-tracked, zero code refs)
  BACKUP-FILE          3 items  (telemetry.db + .spark-initial-sha + TopBarLite.tsx.bak)
  PERSONAL-SCRATCH     2 items  (src/assets/documents/ — third-party bookmark artifact)
  HISTORICAL-MOVE      2 items  (prototype/ — HTML snapshots; Phemex .docx — ref doc)
  ORPHAN-TEST          2 items  (test_backend.py + test_orchestrator_imports.py — recon mode ref)
  DOC-STALE-CURRENT    8 items  (ARCHITECTURE.md, PROJECT_STRUCTURE.md, QUICKSTART.md,
                                  SETUP_INSTRUCTIONS.md, docs/SMC_PIPELINE_REFACTOR.md,
                                  docs/INTEGRATION_GUIDE.md, docs/API_ADDITIONS.md,
                                  docs/WALLET_AUTHENTICATION.md)
  CONFIG-DRIFT         2 items  (react-day-picker in package.json; SECURITY.md dual-purpose)
  SUSPECT-STUB         2 items  (backend/examples/ + backend/devtools/ — __init__.py only)
  STALE-SCRIPT         6 items  (backtest/debug scripts with live recon/ghost mode refs)
  SUSPECT-SCRIPT       1 item   (scripts/janitor_tranche1_3c.sh — primary target class gone)

Top 5 highest-confidence DELETE / quarantine recommendations:

  1. telemetry.db (0 B) + .spark-initial-sha (41 B)
     15 consecutive weeks / 7 passes flagged. Both git-tracked. telemetry.db is a 0-byte
     placeholder (real SQLite generated at runtime). .spark-initial-sha is a Spark.ai deploy
     artifact (SHA: 3e6a499; not referenced in package.json, CI, Dockerfiles, or any .py).
     Chronic T1. Operator review long overdue.

  2. archive/files.zip (33.8 KB) + "archive/files (2).zip" (8.8 KB) +
     archive/snipersight-chart-fixes.zip (46.8 KB) = 89.2 KB combined
     13 consecutive weeks / 6 passes. Git-tracked binary blobs. Zero grep hits in any active
     code, config, or doc. No provenance metadata. Combined 89.2 KB in git history.

  3. src/assets/documents/info.txt (98 B) + src/assets/documents/index.html (3.4 KB)
     Third-party bookmark content (codeconvey.com). Git-tracked (commit ee0a842). Zero references
     in any live src, build config, or Dockerfile. 3 passes unactioned.

  4. tests/test_backend.py + tests/test_orchestrator_imports.py (orphan tests)
     Both call removed scanner mode "recon" as a live valid config, not asserting absence.
     Would fail on any CI run. 6 passes / 6 weeks unactioned. Lowest blast radius quarantine.

  5. src/_archive/components/TopBar/TopBarLite.tsx.bak (2.5 KB)
     .bak file inside an already-archived directory. A backup of a backup. No live import.
     8 passes / 8 weeks unactioned.

---

STRUCTURED DETAIL
=================

TRANCHE 1 — Build artifacts, caches, backup files, personal scratch
--------------------------------------------------------------------

Pass 1 (Build Artifacts) yielded ZERO hits this pass:
  - No __pycache__ directories tracked by git
  - No .pyc / .pyo files
  - No .pytest_cache, .mypy_cache, .ruff_cache
  - No .coverage.* files (bare .coverage not tracked)
  - No dist/, build/, .next/, .parcel-cache/
  Status: repo tree is clean of build artifacts. (Historical ones in janitor_tranche1_3c.sh
  scope were actioned in the 2026-05-07 era.)

Pass 2 (Log & Trace) yielded ONE false positive:
  - .claude/skills/ui-ux-pro-max/scripts/core.py matched the core.* glob — this is a skill
    script, not a core dump. Off-limits per .claude/skills/ rule. Dropped from candidates.
  Status: no actionable log/trace artifacts in repo.

Pass 3 (Backup / Temp / Personal):
  All items from prior manifests confirmed still present.

[UNREF-BLOB]   archive/files.zip                    33.8 KB   Binary blob; zero refs; 6 passes.
               Reason: No import, no reference, no metadata. Pre-rebuild era artifact.
               Disposition: DELETE (git rm archive/files.zip)

[UNREF-BLOB]   "archive/files (2).zip"               8.8 KB   Same provenance; 6 passes.
               Reason: Parenthetical suffix = ad-hoc duplicate. Zero refs.
               Disposition: DELETE (git rm "archive/files (2).zip")

[UNREF-BLOB]   archive/snipersight-chart-fixes.zip  46.8 KB   Chart-fix snapshot; 6 passes.
               Reason: Zero refs in any code/config/doc. No provenance.
               Disposition: DELETE (git rm archive/snipersight-chart-fixes.zip)

[BACKUP-FILE]  telemetry.db                           0 bytes  0-byte SQLite placeholder; 7 passes.
               Reason: Real DB generated at runtime (not committed). git-tracked 0-byte file
               is dead weight. Not referenced by any test or Dockerfile as a fixture path.
               Disposition: DELETE (git rm telemetry.db)

[BACKUP-FILE]  .spark-initial-sha                      41 B    Spark.ai deploy artifact; 7 passes.
               Reason: SHA 3e6a499; zero references in package.json, CI (.github/), Dockerfiles,
               or any .py file. Not in .gitignore either. Orphan deploy artifact.
               Disposition: DELETE (git rm .spark-initial-sha)

[BACKUP-FILE]  src/_archive/components/TopBar/       2.5 KB   .bak inside _archive; 5 passes.
               TopBarLite.tsx.bak
               Reason: (1) No live import of TopBarLite anywhere in active src/; (2) .bak file
               inside a directory already named _archive = backup of a backup.
               Disposition: DELETE (git rm src/_archive/components/TopBar/TopBarLite.tsx.bak)

[PERSONAL-SCRATCH] src/assets/documents/info.txt      98 B    Third-party content; 3 passes.
               Reason: (1) Content is codeconvey.com promotional bookmark; (2) zero refs in
               live src/, build config, or Dockerfile. Committed in ee0a842.
               Disposition: DELETE (git rm src/assets/documents/info.txt)

[PERSONAL-SCRATCH] src/assets/documents/index.html  3.4 KB   Third-party template; 3 passes.
               Reason: Same commit and provenance as info.txt. Downloaded HTML template with
               zero connection to SniperSight codebase. Zero refs anywhere.
               Disposition: DELETE (git rm src/assets/documents/index.html)

Tranche-1 size total: ~96 KB | 8 items

---

TRANCHE 2 — Documentation moves (archive only, content unchanged)
-----------------------------------------------------------------

[DOC-HISTORICAL]  prototype/  (~1.1 MB; 5 passes)
  -> archive/prototype/
  Evidence: Pre-build-era visual specification snapshots (Bot.html, Intel.html, Journal.html,
  Landing.html, Scanner.html, Settings.html, baseline-screenshots/). prototype/README.md
  self-describes as "static HTML prototypes for visual reference." Not referenced by any
  active src/, build config, Dockerfile, or test file. Five consecutive passes unactioned.
  Content is intentionally frozen — not stale-current, not misleading. Archive move preserves
  the snapshot and cleans the root tree.
  Action: git mv prototype/ archive/prototype/

[UNREF-BLOB]  docs/Phemex API OHLCV Data Breakdown.docx  6.0 MB  (2 passes)
  -> archive/docs/
  Evidence: 6 MB binary .docx in text-centric docs/. Git-tracked (confirmed via find).
  Zero references in active .py, .ts, .tsx, .md, .yml, or Dockerfile. Re-surfaced from
  May-20 + Jun-22 manifests where it was classified DOC-HISTORICAL. Content is a Phemex
  OHLCV data format reference — potentially useful if exchange integration is revisited,
  so archive (not delete) is the right disposition.
  Action: git mv "docs/Phemex API OHLCV Data Breakdown.docx" "archive/docs/Phemex API OHLCV Data Breakdown.docx"

---

TRANCHE 3 — Quarantine (one-week soak, then delete)
---------------------------------------------------

[ORPHAN-TEST]  tests/test_backend.py  (6 passes; 6 weeks)
  references-missing-mode: "recon" (line 16)
  Signals:
    1. Line 16: get_signals(..., sniper_mode="recon", ...) — "recon" is a removed scanner
       mode per CLAUDE.md §4. scanner_modes.py confirms zero recon/ghost entries.
    2. Line 15 comment: "Use a valid sniper_mode defined in scanner_modes (e.g., 'recon')"
       — the example contradicts the actual scanner_modes.py surface.
    3. Not asserting absence of the mode — calls it as if valid live config.
    4. Would raise on any CI execution (invalid mode string reaches backend validation).
  Action: git mv tests/test_backend.py tests/_quarantine/test_backend.py

[ORPHAN-TEST]  tests/test_orchestrator_imports.py  (6 passes; 6 weeks)
  references-missing: profile="recon" (line 18)
  Signals:
    1. Line 18: ScanConfig(profile="recon") — "recon" profile removed from scanner_modes.py.
    2. Imports real production modules (not mocks) — would fail on execution.
    3. Not asserting absence of the profile.
  Action: git mv tests/test_orchestrator_imports.py tests/_quarantine/test_orchestrator_imports.py

---

TRANCHE 4 — Review-only (do not touch without further analysis)
---------------------------------------------------------------

[DOC-STALE-CURRENT]  ARCHITECTURE.md  (62.9 KB / ~1762 lines)
  Drift detected:
    - Banner at line 1 acknowledges staleness (added 2026-05-22), but body still contains
      nine "Recon mode" prose locations (confirmed via grep) post-banner.
    - Line 18 heading: "Scanner Mode (Recon / Manual)" — describes removed mode as live.
    - Line 389: "Scanner Flow (Recon Mode)" — section header using dead mode name.
    - Line 441: "Frontend: Scanner Mode UI ('Recon UI')" — same.
    - Pipeline diagrams pre-date SniperContext design (backend/engine/context.py).
    - References PRD.md (removed; replaced by PRODUCT.md).
  Recommended: rewrite mode table and pipeline diagram; remove PRD.md refs; nine "Recon mode"
  prose locations remain in body post-banner. Content rewrite, not relocation.

[DOC-STALE-CURRENT]  PROJECT_STRUCTURE.md  (26.8 KB)
  Drift detected: Has status banner (2026-05-22). Describes Python-only project layout with
  no src/ React tree, no FastAPI detail, no .claude/ tooling tree, no tests/visual/, no
  backend/diagnostics/ subtree. Current repo is substantially broader.
  Recommended: regenerate from `tree -L 3 backend src` + live module map.

[DOC-STALE-CURRENT]  QUICKSTART.md  (14.9 KB)
  Drift detected: "Historical blueprint reference" section at bottom retained but not marked
  for removal. References PRD.md (removed) with parenthetical note at line ~115.
  Recommended: delete "Historical blueprint reference" section once ARCHITECTURE.md is
  rewritten; update launch commands against current start-sniper.bat / Docker paths.

[DOC-STALE-CURRENT]  SETUP_INSTRUCTIONS.md  (1.0 KB)
  Drift detected: Generated from a failed automated installer
  ("The automated installation of required tools failed. Please manually install the
  following"). No connection to current Docker/uvicorn/Vite/start-sniper.bat launch path.
  Not maintained as an operational doc. Accurate for one-time Windows setup only.
  Recommended: fold into QUICKSTART.md Prerequisites section, or archive.

[DOC-STALE-CURRENT]  docs/SMC_PIPELINE_REFACTOR.md  (24.4 KB)
  Drift detected: Documents the recon→stealth / ghost→stealth migration. Migration table is
  intentionally historical (KEEP as record). Broader pipeline description pre-dates Phase-5
  anchoring and heart-change execution path — may misrepresent current scoring and regime logic.
  Recommended: audit body against current orchestrator; retain migration table as historical;
  reclassify surrounding prose as history with a status banner.

[DOC-STALE-CURRENT]  docs/INTEGRATION_GUIDE.md  (8.3 KB)
  Drift detected: Documents integration contracts and API endpoints. API surface evolved
  significantly since heart-change refactor (8498cf9+) and admission gates (7c44595–6c3bd86).
  No recon/ghost refs, but endpoint contracts likely drifted.
  Recommended: diff against backend/diagnostics/contracts/ and current api_server.py routes.

[DOC-STALE-CURRENT]  docs/API_ADDITIONS.md  (9.7 KB)
  Drift detected: Admission gates (Gates 1–3: 7c44595, a5728c4, 6c3bd86), trailing-stop
  endpoints, and CVD observability endpoints (b657e17) not reflected. ~6 weeks behind
  current API surface.
  Recommended: extend with post-Jun-28 additions, or convert to auto-generated contract diff.

[DOC-STALE-CURRENT]  docs/WALLET_AUTHENTICATION.md  (7.1 KB)  [ESCALATED from SUSPECT]
  Drift confirmed — two signals:
    1. WalletConnect/ and WalletGate/ components are both in src/_archive/ (feature archived).
    2. grep of backend/ finds zero wallet auth routes in api_server.py or backend/api/*.py.
  Describes decommissioned functionality. No active consumer anywhere in the codebase.
  Recommended: reclassify DOC-HISTORICAL; archive at docs/archive/WALLET_AUTHENTICATION.md.
  (Or delete if wallet feature is permanently shelved — confirm with operator.)

[CONFIG-DRIFT]  package.json — react-day-picker residual
  Issue: react-day-picker ^9.6.7 remains in dependencies after 2026-05-22 dep eject (44
  packages removed). This package was intentionally deferred per decision doc. Confirmed zero
  usage: active src/ grep returns no hits; only reference is src/_archive/components/ui/calendar.tsx
  (archived code). Package is dead weight in package.json and lockfile.
  Recommended: npm uninstall react-day-picker; verify no runtime breakage post-remove.

[CONFIG-DRIFT]  root SECURITY.md (1.7 KB) vs docs/security.md (15.1 KB)
  Issue: Root SECURITY.md is a GitHub-default security disclosure boilerplate (31 lines;
  "GitHub takes the security of our software products and services seriously...").
  docs/security.md (508 lines) is the actual SniperSight security architecture doc
  (Core Security Principles, Zero Client-Side Secrets, API key handling, threat model).
  Root SECURITY.md is OFF-LIMITS (controls GitHub security advisory workflow — do not delete).
  Recommended: Add redirect comment at top of root SECURITY.md pointing to docs/security.md
  for operational security architecture; or rename docs/security.md → docs/SECURITY_ARCH.md
  to distinguish the two purposes.

[SUSPECT-STUB]  backend/examples/  (contains __init__.py only, 0 bytes)
  Why suspect: Directory with no content beyond empty __init__.py. Not referenced by any
  test, Dockerfile, or active import. Single signal — could be a placeholder for planned
  examples. Needs second-source confirmation before quarantine proposal.

[SUSPECT-STUB]  backend/devtools/  (contains __init__.py only, 0 bytes)
  Why suspect: Same pattern as backend/examples/. Empty __init__.py only. No active imports.
  devtools/ was likely scaffolded but never populated.

[STALE-SCRIPT]  scripts/backtest_from_csv.py
  Stale-mode refs: references "recon" as a valid enum value (confirmed via grep).
  Signals: (1) enumerates removed scanner mode as valid; (2) CLAUDE.md §4 bans recon reintro.
  Note: scripts/ diagnostic tools are NOT flagged per §12 rule, but stale-mode references
  in backtest utilities are a correctness hazard for any operator re-running them.

[STALE-SCRIPT]  scripts/backtest_full_pipeline.py
  Carry-forward from prior manifests. Stale-mode refs confirmed. See Aug-03 manifest detail.

[STALE-SCRIPT]  scripts/backtest_modes.py
  Carry-forward. Stale-mode refs confirmed.

[STALE-SCRIPT]  scripts/backtest_scanner.py
  Carry-forward. Stale-mode refs confirmed.

[STALE-SCRIPT]  scripts/debug/ (subdirectory)
  Carry-forward. Ghost/recon refs confirmed in prior manifests.

[STALE-SCRIPT]  scripts/tests_standalone/ (subdirectory)
  Carry-forward. Stale-mode refs confirmed in prior manifests.

[SUSPECT-SCRIPT]  scripts/janitor_tranche1_3c.sh
  Why suspect: Script was generated 2026-05-07 to clean Tranche 1 + 3C items. Many of its
  primary target classes (47 debug-output files, __pycache__, .pytest_cache, debug-587019.log)
  are already gone — cleaned in the 2026-05-07 era. The items it lists that are still present
  (telemetry.db, .spark-initial-sha, paper_trading.db) are already in the current T1 manifest.
  Running the script now would be a no-op or near-no-op for most operations.
  Second signal needed before quarantine proposal — verify which targets still exist.

---

Off-limits items observed (for awareness — NOT proposed for action)
-------------------------------------------------------------------
- .claude/skills/ui-ux-pro-max/scripts/core.py — off-limits per .claude/skills/ rule;
  matched core.* pattern for core dumps (false positive)
- backend/diagnostics/ (all contents) — one-shot by design; do not flag
- backend/diagnostics/decisions/ — calibration history; do not flag
- backend/diagnostics/phase_archive/ — historical; do not flag
- All files in standing-fix surface — KEEP per CLAUDE.md §10
- DESIGN.md — ACTIVE (live design system reference); excluded from candidates

---

Proposed Tranche-1 Command (DO NOT RUN until operator approves)
---------------------------------------------------------------
# Verify first with: git ls-files <path> to confirm each is git-tracked before git rm
git rm telemetry.db
git rm .spark-initial-sha
git rm "archive/files.zip"
git rm "archive/files (2).zip"
git rm "archive/snipersight-chart-fixes.zip"
git rm "src/_archive/components/TopBar/TopBarLite.tsx.bak"
git rm "src/assets/documents/info.txt"
git rm "src/assets/documents/index.html"
# Then: git commit -m "chore(janitor): tranche-1 cleanup 2026-08-17"

Proposed Tranche-2 Command (DO NOT RUN until operator approves)
---------------------------------------------------------------
mkdir -p archive/docs
git mv prototype/ archive/prototype/
git mv "docs/Phemex API OHLCV Data Breakdown.docx" "archive/docs/Phemex API OHLCV Data Breakdown.docx"
# Then: git commit -m "chore(janitor): tranche-2 archive moves 2026-08-17"

Proposed Tranche-3 Command (DO NOT RUN until operator approves — one-week soak)
-------------------------------------------------------------------------------
mkdir -p tests/_quarantine
git mv tests/test_backend.py tests/_quarantine/test_backend.py
git mv tests/test_orchestrator_imports.py tests/_quarantine/test_orchestrator_imports.py
# Then: git commit -m "chore(janitor): quarantine orphan recon-mode tests 2026-08-17"
# After one week: git rm tests/_quarantine/test_backend.py tests/_quarantine/test_orchestrator_imports.py

---

Recommended Next Step
---------------------
1. PRIORITY: Tranche 1 is 15 weeks old for the oldest items. Review and approve/strike items.
   telemetry.db + .spark-initial-sha are the safest deletes in the entire manifest.
2. Tranche 3 (orphan tests) — 6 weeks / 6 passes. These will fail any CI run. Low blast radius.
   Quarantine them this session.
3. For Tranche 4 stale-current docs: invoke the engineering:documentation skill for a rewrite
   pass, starting with ARCHITECTURE.md (most misleading — live "Recon mode" sections in body).
4. react-day-picker CONFIG-DRIFT: one-liner npm uninstall. Lowest-effort CONFIG-DRIFT resolution.
5. docs/WALLET_AUTHENTICATION.md: confirm with operator whether wallet feature is permanently
   shelved, then either archive or delete.
6. Re-run repo-janitor after any tranche is actioned to detect cascading orphans.

Note: Manifest exceeds 30 candidates (31 total). Per protocol, consider invoking the
engineering:tech-debt skill for prioritization before actioning Tranche 4.
