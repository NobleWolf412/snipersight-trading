REPO-JANITOR INVENTORY
======================
Date: 2026-08-31
Scope: Full repo minus off-limits list; git-tracked files only unless noted
Prior manifest: docs/audits/JANITOR_MANIFEST_2026-08-17.md
Off-limits respected: YES — .live_trading/, .coverage, .git/, .github/, .storybook/, .cursor/,
  CLAUDE.md, LICENSE, Dockerfile.*, .dockerignore, .claude/agents/*.md, .claude/skills/,
  .claude/worktrees/, backend/diagnostics/*.py (§12 iterate-loop scripts),
  backend/diagnostics/decisions/, backend/diagnostics/phase_archive/,
  standing-fix surface (scorer.py, orchestrator.py, regime_*.py, scanner_modes.py, smc_*.py,
  smc_service.py, regime_policies.py) — all KEEP per CLAUDE.md §10.
  DESIGN.md — ACTIVE (referenced by live src/components/); excluded from candidates.
  .claude/skills/ui-ux-pro-max/scripts/core.py — tooling script; false-positive of core.*
  pattern for core dumps; skipped per off-limits rule on .claude/skills/.

Activity since 2026-08-17 (1 commit):
  ed60227 docs(janitor): weekly repo-janitor inventory manifest 2026-08-17 (the manifest itself)
  Net new clutter from code activity: ZERO.
  Net new candidates this pass: ZERO.

RESOLUTION TRACKER — carry-forward aging (weeks since first flagged → weeks since last manifest):
  telemetry.db + .spark-initial-sha:     16 weeks (first 2026-05-07; 8 passes; ZERO action) ⚠ CRITICAL
  archive/*.zip (3 blobs):               14 weeks (first 2026-05-20; 7 passes; ZERO action) ⚠ CRITICAL
  src/_archive/TopBarLite.tsx.bak:        10 weeks (first 2026-06-22; 6 passes; ZERO action) ⚠ ESCALATE
  prototype/ → archive/prototype/:        10 weeks (first 2026-06-22; 6 passes; ZERO action) ⚠ ESCALATE
  Phemex OHLCV docx:                      10 weeks (first 2026-06-22; 6 passes; ZERO action)
  orphan tests (2):                        8 weeks (first 2026-07-06; 6 passes; ZERO action) ⚠ ESCALATE
  src/assets/documents/{info,index}:       5 weeks (first 2026-07-27; 3 passes; ZERO action)
  SECURITY.md vs docs/security.md:         4 weeks (new 2026-08-03; 2 passes; ZERO action)

ESCALATIONS this pass:
  telemetry.db + .spark-initial-sha → 16 weeks / 8 passes. CRITICAL. These are zero-byte / 41B
    files. No operational reason to retain. If this reaches 20 weeks it will have appeared in
    every single janitor pass since the first one. Operator action required.
  archive/*.zip (3 blobs) → 14 weeks / 7 passes. CRITICAL. 89.2 KB of binary blobs with zero
    code references, zero provenance. Git history carries the weight. Operator action required.
  src/_archive/TopBarLite.tsx.bak → 10 weeks / 6 passes. A .bak inside an _archive directory.
    Escalating from standard carry-forward to ESCALATE tier.
  orphan tests → 8 weeks / 6 passes. These fail on any CI run (reference removed "recon" mode).
    Escalating: quarantine is low blast radius and overdue.

NEW ITEMS this pass: NONE

Total candidates: 31 (all carry-forward; zero new items)
By tranche:
  Tranche 1 (zero-risk delete):          8 items  (all carry-forward; 5–16 weeks unactioned)
  Tranche 2 (low-risk archive moves):    2 items  (prototype/ + Phemex docx; 10 weeks)
  Tranche 3 (quarantine first):          2 items  (orphan tests — recon mode refs; 8 weeks)
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

Top 5 highest-confidence DELETE / quarantine recommendations (CRITICAL tier first):

  1. telemetry.db (0 B) + .spark-initial-sha (41 B)
     16 consecutive weeks / 8 passes flagged. CRITICAL escalation. telemetry.db is a 0-byte
     placeholder (real SQLite generated at runtime). .spark-initial-sha is a Spark.ai deploy
     artifact (SHA: 3e6a499; not referenced in package.json, CI, Dockerfiles, or any .py).
     Zero operational reason to keep either. Operator action long overdue.

  2. archive/files.zip (33.8 KB) + "archive/files (2).zip" (8.8 KB) +
     archive/snipersight-chart-fixes.zip (46.8 KB) = 89.2 KB combined
     14 consecutive weeks / 7 passes. CRITICAL escalation. Git-tracked binary blobs. Zero grep
     hits in any active code, config, or doc. No provenance metadata in any commit message.
     Combined 89.2 KB lives in git history forever on every clone.

  3. tests/test_backend.py + tests/test_orchestrator_imports.py (orphan tests)
     8 weeks / 6 passes. Both call removed scanner mode "recon" as a live valid config.
     Will raise/fail on any CI run. ESCALATE tier. Quarantine is lowest blast radius option.
     Two signals each: (1) invalid mode name; (2) no assertion of absence.

  4. src/_archive/components/TopBar/TopBarLite.tsx.bak (2.5 KB)
     10 weeks / 6 passes. ESCALATE tier. .bak file inside an already-archived directory.
     A backup of a backup. No live import path. Two signals: (1) no live import; (2) .bak in _archive.

  5. src/assets/documents/info.txt (98 B) + src/assets/documents/index.html (3.4 KB)
     5 weeks / 3 passes. Third-party promotional bookmark content (codeconvey.com). Git-tracked.
     Zero references in live src, build config, or Dockerfile.

---

STRUCTURED DETAIL
=================

TRANCHE 1 — Build artifacts, caches, backup files, personal scratch
--------------------------------------------------------------------

Pass 1 (Build Artifacts) yielded ZERO hits:
  - No __pycache__ directories tracked by git (git ls-files | grep __pycache__: empty)
  - No .pyc / .pyo files
  - No .pytest_cache, .mypy_cache, .ruff_cache
  - No .coverage.* files (bare .coverage not tracked; htmlcov/ absent)
  - No dist/, build/, .next/, .parcel-cache/
  Status: repo tree is clean of build artifacts. Confirmed by git ls-files scan this pass.

Pass 2 (Log & Trace):
  - .claude/skills/ui-ux-pro-max/scripts/core.py — false-positive on core.* pattern; off-limits.
  Status: no actionable log/trace artifacts in repo.

Pass 3 (Backup / Temp / Personal):
  All items from prior manifest confirmed still present. Aging updated.

[UNREF-BLOB]   archive/files.zip                    33.8 KB   Binary blob; zero refs; 7 passes.
               Reason: No import, no reference, no metadata. Pre-rebuild era artifact.
               Signals: (1) zero grep hits in *.py, *.ts, *.tsx, *.md, *.yml, Dockerfiles;
               (2) git log --follow shows no version history explaining provenance.
               Disposition: DELETE (git rm "archive/files.zip")

[UNREF-BLOB]   "archive/files (2).zip"               8.8 KB   Same provenance; 7 passes.
               Reason: Parenthetical suffix = ad-hoc duplicate. Zero refs.
               Signals: (1) zero grep hits; (2) parenthetical name = manual duplicate artifact.
               Disposition: DELETE (git rm "archive/files (2).zip")

[UNREF-BLOB]   archive/snipersight-chart-fixes.zip  46.8 KB   Chart-fix snapshot; 7 passes.
               Reason: Zero refs in any code/config/doc. No provenance commit context.
               Signals: (1) zero grep hits; (2) no code file references the zip path.
               Disposition: DELETE (git rm "archive/snipersight-chart-fixes.zip")

[BACKUP-FILE]  telemetry.db                           0 bytes  0-byte SQLite placeholder; 8 passes.
               Reason: Real DB generated at runtime. 0-byte commit is dead weight.
               Signals: (1) 0 bytes — not a real DB; (2) no test or Dockerfile references it as
               a fixture path. Runtime generates the real file at startup, never reads this path.
               Disposition: DELETE (git rm telemetry.db)

[BACKUP-FILE]  .spark-initial-sha                      41 B    Spark.ai deploy artifact; 8 passes.
               Reason: SHA 3e6a499; zero references in package.json, CI (.github/), Dockerfiles,
               or any .py file. Not in .gitignore either. Orphan deploy artifact from Spark.ai era.
               Signals: (1) no code reference anywhere; (2) .spark-* prefix = deploy tooling
               artifact that was never cleaned up post-migration.
               Disposition: DELETE (git rm .spark-initial-sha)

[BACKUP-FILE]  src/_archive/components/TopBar/        2.5 KB   .bak inside _archive; 6 passes.
               TopBarLite.tsx.bak
               Reason: No live import of TopBarLite anywhere in active src/. .bak extension
               inside a directory already named _archive = backup of a backup.
               Signals: (1) no live import in active src/; (2) .bak file inside _archive dir.
               Disposition: DELETE (git rm "src/_archive/components/TopBar/TopBarLite.tsx.bak")

[PERSONAL-SCRATCH] src/assets/documents/info.txt      98 B    Third-party content; 3 passes.
               Reason: Content is codeconvey.com promotional bookmark text.
               Signals: (1) zero refs in live src/, build config, or Dockerfile; (2) content
               is third-party marketing text with no connection to SniperSight. Committed ee0a842.
               Disposition: DELETE (git rm "src/assets/documents/info.txt")

[PERSONAL-SCRATCH] src/assets/documents/index.html  3.4 KB   Third-party template; 3 passes.
               Reason: Downloaded HTML template. Same commit and provenance as info.txt.
               Signals: (1) zero refs anywhere; (2) same third-party origin, no SniperSight content.
               Disposition: DELETE (git rm "src/assets/documents/index.html")

Tranche-1 size total: ~96 KB | 8 items

---

TRANCHE 2 — Documentation moves (archive only, content unchanged)
-----------------------------------------------------------------

[DOC-HISTORICAL]  prototype/  (~1.1 MB; 6 passes; 10 weeks)
  -> archive/prototype/
  Evidence: Pre-build-era visual specification snapshots (Bot.html, Intel.html, Journal.html,
  Landing.html, Scanner.html, Settings.html, baseline-screenshots/). prototype/README.md
  self-describes as "static HTML prototypes for visual reference." Not referenced by any
  active src/, build config, Dockerfile, or test file. Six consecutive passes unactioned.
  Content is intentionally frozen — not stale-current, not misleading. Archive move preserves
  the snapshot and cleans the root tree.
  Action: git mv prototype/ archive/prototype/

[UNREF-BLOB]  docs/Phemex API OHLCV Data Breakdown.docx  6.0 MB  (6 passes; 10 weeks)
  -> archive/docs/
  Evidence: 6 MB binary .docx in text-centric docs/. Zero references in active .py, .ts,
  .tsx, .md, .yml, or Dockerfile. Content is Phemex OHLCV data format reference —
  potentially useful if exchange integration is revisited; archive (not delete) is correct.
  Action: git mv "docs/Phemex API OHLCV Data Breakdown.docx" "archive/docs/Phemex API OHLCV Data Breakdown.docx"

---

TRANCHE 3 — Quarantine (one-week soak, then delete)
---------------------------------------------------

[ORPHAN-TEST]  tests/test_backend.py  (6 passes; 8 weeks)
  references-missing-mode: "recon" (line 16)
  Signals:
    1. Line 16: get_signals(..., sniper_mode="recon", ...) — "recon" is a removed scanner
       mode per CLAUDE.md §4. scanner_modes.py confirms zero recon/ghost entries.
    2. Line 15 comment: "Use a valid sniper_mode defined in scanner_modes (e.g., 'recon')"
       — the example contradicts the actual scanner_modes.py surface (4 modes: OVERWATCH,
       STRIKE, SURGICAL, STEALTH).
    3. Not asserting absence of the mode — calls it as if valid live config.
    4. Would raise on any CI execution (invalid mode string reaches backend validation).
  Action: git mv tests/test_backend.py tests/_quarantine/test_backend.py

[ORPHAN-TEST]  tests/test_orchestrator_imports.py  (6 passes; 8 weeks)
  references-missing: profile="recon" (line 18)
  Signals:
    1. Line 18: ScanConfig(profile="recon") — "recon" profile removed from scanner_modes.py.
    2. Imports real production modules (not mocks) — would fail on execution with invalid profile.
    3. Not asserting absence of the profile.
  Action: git mv tests/test_orchestrator_imports.py tests/_quarantine/test_orchestrator_imports.py

---

TRANCHE 4 — Review-only (do not touch without further analysis)
---------------------------------------------------------------

[DOC-STALE-CURRENT]  ARCHITECTURE.md  (62.9 KB / ~1762 lines)
  Drift detected:
    - Banner at line 1 acknowledges staleness (added 2026-05-22), but body still contains
      nine "Recon mode" prose locations (confirmed via grep) post-banner.
    - Sections still describe removed mode as live architecture.
    - Pipeline diagrams pre-date SniperContext design (backend/engine/context.py).
    - References PRD.md (removed; replaced by PRODUCT.md).
  Recommended: rewrite mode table and pipeline diagram; remove PRD.md refs. Content rewrite,
  not relocation. Most misleading doc in repo — live "Recon mode" sections in body.

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
  No recon/ghost refs, but endpoint contracts likely drifted from current api_server.py.
  Recommended: diff against backend/diagnostics/contracts/ and current api_server.py routes.

[DOC-STALE-CURRENT]  docs/API_ADDITIONS.md  (9.7 KB)
  Drift detected: Admission gates (Gates 1–3: 7c44595, a5728c4, 6c3bd86), trailing-stop
  endpoints, and CVD observability endpoints (b657e17) not reflected. ~6 weeks behind
  current API surface.
  Recommended: extend with post-Jun-28 additions, or convert to auto-generated contract diff.

[DOC-STALE-CURRENT]  docs/WALLET_AUTHENTICATION.md  (7.1 KB)  [ESCALATED — second pass]
  Drift confirmed — two signals:
    1. WalletConnect/ and WalletGate/ components are both in src/_archive/ (confirmed this pass).
    2. grep of backend/api_server.py finds zero wallet auth routes (exit 0 for any wallet keyword).
  Describes decommissioned functionality. No active consumer anywhere in the codebase.
  Recommended: reclassify DOC-HISTORICAL; archive at docs/archive/WALLET_AUTHENTICATION.md.
  Confirm with operator whether wallet feature is permanently shelved before deleting.

[CONFIG-DRIFT]  package.json — react-day-picker residual
  Issue: react-day-picker ^9.6.7 remains in dependencies after 2026-05-22 dep eject.
  Confirmed zero usage: active src/ grep returns no hits; only reference is
  src/_archive/components/ui/calendar.tsx (archived code). Package is dead weight.
  Recommended: npm uninstall react-day-picker; verify no runtime breakage post-remove.

[CONFIG-DRIFT]  package.json — class-variance-authority orphan (carry-forward from May-22 decision)
  Issue: class-variance-authority ^0.7.1 retained per prior decision ("zero src/ hits but
  retained per prior decision"). Zero active src/ imports confirmed again this pass.
  Status: intentional orphan-but-retained per 2026-05-22__package-json-eject-44-deps.md.
  Not a new finding; flagging for operator re-evaluation as it has been 14 weeks since the
  retain decision. No new CVA consumer has materialized.
  Recommended: re-evaluate eject; npm uninstall class-variance-authority if still unused.

[CONFIG-DRIFT]  root SECURITY.md (1.7 KB) vs docs/security.md (15.1 KB)
  Issue: Root SECURITY.md is GitHub-default security disclosure boilerplate (31 lines).
  docs/security.md (508 lines) is the actual SniperSight security architecture doc.
  Root SECURITY.md is OFF-LIMITS (controls GitHub security advisory workflow — do not delete).
  Recommended: Add redirect comment at top of root SECURITY.md pointing to docs/security.md
  for operational security architecture; or rename docs/security.md → docs/SECURITY_ARCH.md.

[SUSPECT-STUB]  backend/examples/  (contains __init__.py only, 0 bytes)
  Why suspect: Directory with no content beyond empty __init__.py (confirmed: only file).
  Not referenced by any test, Dockerfile, or active import. Single signal — could be a
  placeholder for planned examples. Needs second-source confirmation before quarantine proposal.

[SUSPECT-STUB]  backend/devtools/  (contains __init__.py only, 0 bytes)
  Why suspect: Same pattern as backend/examples/. Empty __init__.py only (confirmed this pass).
  devtools/ was likely scaffolded but never populated. Single signal — awaiting second source.

[STALE-SCRIPT]  scripts/backtest_from_csv.py
  Stale-mode refs: references "recon" as a valid enum value (grep confirmed this pass).
  Signals: (1) enumerates removed scanner mode as valid; (2) CLAUDE.md §4 bans recon reintro.
  Note: scripts/ diagnostic tools are NOT flagged per §12 rule, but stale-mode references
  in backtest utilities are a correctness hazard for any operator re-running them.

[STALE-SCRIPT]  scripts/backtest_full_pipeline.py
  Stale-mode refs confirmed this pass. Same recon/ghost ref pattern.

[STALE-SCRIPT]  scripts/backtest_modes.py
  Stale-mode refs confirmed this pass. Same recon/ghost ref pattern.

[STALE-SCRIPT]  scripts/backtest_scanner.py
  Stale-mode refs confirmed this pass. Same recon/ghost ref pattern.

[STALE-SCRIPT]  scripts/debug/debug_trade_type_changes.py
  New this pass: grep hit for recon/ghost refs in scripts/debug/ subdirectory.
  Signals: (1) contains recon/ghost mode reference; (2) in debug/ subdirectory which
  was noted in prior manifests as containing stale-mode refs.

[STALE-SCRIPT]  scripts/debug/debug_arm_scanner.py
  New this pass: same grep hit pattern as debug_trade_type_changes.py.
  Signals: (1) contains recon/ghost mode reference; (2) debug/ subdirectory pattern.

[SUSPECT-SCRIPT]  scripts/janitor_tranche1_3c.sh
  Why suspect: Script was generated 2026-05-07 to clean Tranche 1 + 3C items. Its primary
  target classes (pyc, pytest_cache, debug-*.log) are already gone. However, it also targets
  telemetry.db and .spark-initial-sha which ARE still present — so the script is partially
  still relevant. Not a clean quarantine candidate; operator should decide whether to fold its
  remaining useful targets into the manual tranche-1 command or retire the script.

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
- scripts/confluence_diagnostic.py, sweep_diagnostic.py, fetch_diagnostics.py,
  get_diagnostics.py — §12 iterate-loop scripts; do not flag per protocol

---

RAW EVIDENCE
============

Carry-forward confirmation (all items verified present this pass):
  telemetry.db:                   stat → 0 bytes, EXISTS
  .spark-initial-sha:             stat → 41 bytes, EXISTS
  archive/files.zip:              stat → 34576 bytes, EXISTS
  archive/files (2).zip:          EXISTS (size not separated from other zips)
  archive/snipersight-chart-fixes.zip: stat → 47902 bytes, EXISTS
  src/_archive/components/TopBar/TopBarLite.tsx.bak: stat → 2565 bytes, EXISTS
  src/assets/documents/info.txt:  stat → 98 bytes, EXISTS
  src/assets/documents/index.html: stat → 3440 bytes, EXISTS
  tests/test_backend.py:          EXISTS
  tests/test_orchestrator_imports.py: EXISTS
  prototype/:                     EXISTS (directory)
  docs/Phemex API OHLCV Data Breakdown.docx: EXISTS

Build artifact scan (git ls-files | grep __pycache__|.pyc|.pyo|.pytest_cache):
  Output: EMPTY — no tracked build artifacts

Config drift scan:
  grep react-day-picker package.json → "react-day-picker": "^9.6.7"  ← STILL PRESENT
  grep class-variance-authority package.json → "class-variance-authority": "^0.7.1"  ← STILL PRESENT

Wallet auth decommission confirmation:
  grep -c "wallet" backend/api_server.py → 0
  find src -name "WalletConnect*" → src/_archive/components/WalletConnect/WalletConnect.tsx (archived)
  find src -name "WalletGate*" → src/_archive/components/WalletGate/WalletGate.tsx (archived)
  ∴ docs/WALLET_AUTHENTICATION.md describes fully decommissioned feature

Stale-script recon/ghost refs confirmed:
  scripts/backtest_from_csv.py         ← grep hit: recon
  scripts/backtest_full_pipeline.py    ← grep hit: recon/ghost
  scripts/backtest_modes.py            ← grep hit: recon/ghost
  scripts/backtest_scanner.py          ← grep hit: recon/ghost
  scripts/debug/debug_trade_type_changes.py ← grep hit: recon/ghost (NEW named this pass)
  scripts/debug/debug_arm_scanner.py        ← grep hit: recon/ghost (NEW named this pass)

Git log (recent 20):
  ed60227 docs(janitor): weekly repo-janitor inventory manifest 2026-08-17
  565d85f docs(janitor): weekly repo-janitor inventory manifest 2026-08-03
  7b9a7d9 docs(janitor): weekly repo-janitor inventory manifest 2026-07-27
  5c4dbed docs(janitor): weekly repo-janitor inventory manifest 2026-07-20
  9c1d4f6 docs(janitor): weekly repo-janitor inventory manifest 2026-07-06
  4200ef2 feat(diag): retroactive CVD edge test (Binance dumps) — VERDICT: NOISE (5th strike)
  f548b2f fix(ui): allow Session Duration 0 = run until manually stopped (long-capture)
  b657e17 feat(cvd): order-flow forward-capture (Phase A — OBSERVATIONAL, zero decision-path)
  cc6d6e9 tune(paper): trailing activation 1.5R -> 1.0R (PAPER only; measured)
  ffab8d7 feat(observability): journal trailing-stop activation + final stop level
  37b8668 fix(ui): trailing-activation slider mislabeled '%' — it's R-multiples
  f605a02 feat(ui): expose account-aware admission toggle + params in the paper setup (API + UI)
  6c3bd86 feat(admission): Gate 3 — liquidation-safety guard (path 3, admission-level, all leverage)
  a5728c4 feat(admission): Gate 2 — min-order risk guard (path 2, near-inert on Phemex)
  1efc265 feat(admission): depth-aware admission (path 1) — order-book spread/depth gate
  7c44595 feat(admission): account-aware liquidity floor — Phase A / Gate 1 (flag-gated, paper-only)
  8bc9d66 feat(ui): alts ON by default + demote (not delete) snap_taker & macro overlay
  8498cf9 feat(ui): correct paper-bot defaults to the heart-change strategy (rest_maker + macro off)
  6e1307a feat(ui): reflect thesis-mode in the paper bot setup (confluence gate demoted)
  efcde4c refactor(thesis): demote 4 leftover score/ML gates in thesis mode (heart-change consistency)

Size totals:
  Tranche 1 (zero-risk delete): ~96 KB across 8 items
  Tranche 2 (archive moves): ~7.1 MB across 2 items (dominated by Phemex .docx at 6.0 MB)
  Tranche 4 (review-only stale docs): ~154 KB across 8 doc items

---

Proposed Tranche-1 Command (DO NOT RUN until operator approves)
---------------------------------------------------------------
# Verify each with: git ls-files <path> to confirm git-tracked before git rm
git rm telemetry.db
git rm .spark-initial-sha
git rm "archive/files.zip"
git rm "archive/files (2).zip"
git rm "archive/snipersight-chart-fixes.zip"
git rm "src/_archive/components/TopBar/TopBarLite.tsx.bak"
git rm "src/assets/documents/info.txt"
git rm "src/assets/documents/index.html"
# Then: git commit -m "chore(janitor): tranche-1 cleanup 2026-08-31"

Proposed Tranche-2 Command (DO NOT RUN until operator approves)
---------------------------------------------------------------
mkdir -p archive/docs
git mv prototype/ archive/prototype/
git mv "docs/Phemex API OHLCV Data Breakdown.docx" "archive/docs/Phemex API OHLCV Data Breakdown.docx"
# Then: git commit -m "chore(janitor): tranche-2 archive moves 2026-08-31"

Proposed Tranche-3 Command (DO NOT RUN until operator approves — one-week soak)
-------------------------------------------------------------------------------
mkdir -p tests/_quarantine
git mv tests/test_backend.py tests/_quarantine/test_backend.py
git mv tests/test_orchestrator_imports.py tests/_quarantine/test_orchestrator_imports.py
# Then: git commit -m "chore(janitor): quarantine orphan recon-mode tests 2026-08-31"
# After one week: git rm tests/_quarantine/test_backend.py tests/_quarantine/test_orchestrator_imports.py

---

Recommended Next Step
---------------------
1. CRITICAL: Tranche 1 is 16 weeks old for the oldest items. telemetry.db + .spark-initial-sha
   are the safest deletes in the entire manifest — 0 bytes and 41 bytes respectively. Approve.
2. CRITICAL: archive/*.zip — 89.2 KB of git-tracked binary blobs at 14 weeks. Approve.
3. ESCALATE: Tranche 3 (orphan tests) — 8 weeks / 6 passes. These will fail any CI run.
   Quarantine them: one-line git mv per test, one-week soak, then delete. Low blast radius.
4. ESCALATE: prototype/ move to archive/prototype/ — 10 weeks. Root tree cleanup. Safe git mv.
5. CONFIG-DRIFT: react-day-picker and class-variance-authority — both zero src/ usage.
   Consider npm uninstall for both (one session, one verification gate).
6. docs/WALLET_AUTHENTICATION.md — confirm with operator: feature permanently shelved → archive.
7. For Tranche 4 stale-current docs: invoke the engineering:documentation skill for a rewrite
   pass, starting with ARCHITECTURE.md (most misleading — live "Recon mode" sections in body).

NOTE: Manifest has 31 candidates (same count as Aug-17). Per protocol: consider invoking the
engineering:tech-debt skill for prioritization before actioning Tranche 4 items.
NOTE: The 2 stale-script debug/ hits (debug_trade_type_changes.py, debug_arm_scanner.py) are
newly named this pass but not newly found — they were included in the "scripts/debug/ (subdirectory)"
carry-forward from prior manifests. Count remains stable at 31.

auditor track unblocks when operator reviews this manifest in claude.ai/code/routines/<this-routine-id>
