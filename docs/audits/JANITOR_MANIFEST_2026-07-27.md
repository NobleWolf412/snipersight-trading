REPO-JANITOR INVENTORY
======================
Date: 2026-07-27
Scope: Full repo minus off-limits list; git-tracked files only unless noted
Prior manifest: docs/audits/JANITOR_MANIFEST_2026-07-20.md
Off-limits respected: YES — .live_trading/, .coverage, .git/, .github/, .storybook/, .cursor/,
  CLAUDE.md, LICENSE, Dockerfile.*, .dockerignore, .claude/agents/*.md, .claude/skills/,
  .claude/worktrees/, backend/diagnostics/*.py (§12 iterate-loop scripts), backend/diagnostics/decisions/,
  backend/diagnostics/phase_archive/, standing-fix surface (scorer.py, orchestrator.py, regime_*.py,
  scanner_modes.py, smc_*.py, smc_service.py, regime_policies.py) — all KEEP per CLAUDE.md §10.

Activity since 2026-07-20 (1 commit):
  5c4dbed docs(janitor): weekly repo-janitor inventory manifest 2026-07-20 (the manifest itself)
  Net new clutter from code activity: ZERO.

RESOLUTION — diagnostics/*.txt saga CLOSED:
  The 29 backend/diagnostics/*.txt files flagged across FIVE previous consecutive passes
  (May-07, May-20, Jun-22, Jul-06, Jul-20) are NOT in git. `git ls-files backend/diagnostics/
  | grep '\.txt$'` returns zero hits. Fresh container clone confirms absence. These were always
  local dev-machine artifacts, never committed. The `git rm` commands proposed in prior manifests
  would have been no-ops. Recommended corrective: add `backend/diagnostics/*.txt` to .gitignore
  as a preventive forward measure (single-line, zero-blast-radius action). The saga closes here.
  This reclassification also invalidates scripts/janitor_tranche1_3c.sh's primary function (the
  3C git-rm block targeting these files is now a no-op against the canonical git tree).

ZERO TRANCHE-1 ITEMS ACTIONED since 2026-07-20. All 8 carry-forward Tranche-1 items remain.
TWO NEW Tranche-1 items surfaced (src/assets/documents/ — missed by two prior passes).

Total candidates: 29  (27 carry-forward + 2 newly surfaced)
By tranche:
  Tranche 1 (zero-risk delete/remove):   8 items  (6 carry-forward + 2 NEW)
  Tranche 2 (low-risk archive moves):    1 group  (carry-forward)
  Tranche 3 (quarantine first):          2 items  (carry-forward)
  Tranche 4 (review-only):             18 items  (all carry-forward)

---

SHORT SUMMARY
=============

Total candidates by category:
  UNREF-BLOB           3 items  (archive/*.zip — binary blobs, git-tracked, zero code refs)
  BACKUP-FILE          3 items  (telemetry.db + .spark-initial-sha + TopBarLite.tsx.bak)
  PERSONAL-SCRATCH     2 items  NEW — src/assets/documents/ (codeconvey.com download artifact)
  HISTORICAL-MOVE      1 group  (prototype/ → archive/prototype/ — visual spec HTML snapshots)
  ORPHAN-TEST          2 items  (test_backend.py + test_orchestrator_imports.py — recon mode ref)
  DOC-STALE-CURRENT    7 items  (ARCHITECTURE.md, PROJECT_STRUCTURE.md, QUICKSTART.md,
                                  SETUP_INSTRUCTIONS.md, docs/SMC_PIPELINE_REFACTOR.md,
                                  docs/INTEGRATION_GUIDE.md, docs/API_ADDITIONS.md)
  DOC-SUSPECT          1 item   (docs/WALLET_AUTHENTICATION.md — live components archived)
  CONFIG-DRIFT         1 item   (react-day-picker in package.json — dep eject DONE except this one)
  SUSPECT-STUB         2 items  (backend/examples/ + backend/devtools/ — __init__.py only)
  STALE-SCRIPT         6 items  (backtest scripts + debug scripts with live recon/ghost mode refs)
  SUSPECT-SCRIPT       1 item   (scripts/janitor_tranche1_3c.sh — generated May-07, references
                                  files now confirmed never-git-tracked)

Top 5 highest-confidence DELETE / quarantine recommendations:

  1. src/assets/documents/info.txt (98 B) + src/assets/documents/index.html (3.4 KB) — NEW
     Missed by the Jun-22, Jul-06, and Jul-20 passes. Git-tracked (confirmed via git ls-files).
     info.txt body: "For more awesome CSS / HTML/ Javascript Code Examples & scripts visit now:
     https://codeconvey.com". index.html: a third-party HTML template (<!DOCTYPE html><html...>)
     with codeconvey.com provenance. Both were committed in ee0a842 (Phase 4F diagnostics commit,
     June 2026). Not referenced in any .tsx, .ts, .py, .yml, or Dockerfile. Clearly a personal
     scratch download that got accidentally staged and committed. Two signals: (1) no import or
     reference in any active source file; (2) content is explicitly third-party promotional material
     with no SniperSight connection. Highest-confidence NEW delete in the repo.

  2. archive/files.zip (33.8 KB) + archive/files (2).zip (8.8 KB) +
     archive/snipersight-chart-fixes.zip (46.8 KB) — Flagged in May-20, Jun-22, Jul-06, Jul-20.
     Pre-rebuild binary blobs, git-tracked, zero grep hits in any active code or config, no
     metadata. Four consecutive passes with zero action. Combined 89.2 KB of binary dead weight
     in git history.

  3. telemetry.db (0 bytes) + .spark-initial-sha (41 bytes) — Flagged in May-07, May-20, Jun-22,
     Jul-06, Jul-20. telemetry.db is a 0-byte placeholder (real SQLite generated at runtime).
     .spark-initial-sha is a Spark.ai deployment artifact (SHA: 3e6a499...) not referenced in
     package.json, CI, Dockerfiles, or any .py. Git-tracked. Five passes, zero action.

  4. tests/test_backend.py + tests/test_orchestrator_imports.py — ORPHAN-TEST since Jul-06.
     test_backend.py calls get_signals(..., sniper_mode="recon") as a live API path.
     test_orchestrator_imports.py calls ScanConfig(profile="recon") against live Orchestrator.
     "recon" is a removed mode (CLAUDE.md §4: "never reintroduce recon or ghost"). Both tests
     would fail in any CI run exercising them. Two signals: (1) reference removed scanner mode;
     (2) not asserting absence — treating "recon" as a live valid value.

  5. src/_archive/components/TopBar/TopBarLite.tsx.bak (2.5 KB) — .bak inside an already-archived
     component tree. Git-tracked. No active import from any live src/. Backup of a backup.
     Flagged Jun-22, Jul-06, Jul-20. Three passes, zero action.

---

TRANCHE 1 — Build artifacts, caches, backup files, personal scratch
--------------------------------------------------------------------

[UNREF-BLOB]      archive/files.zip                        33.8 KB   Git-tracked binary blob; zero refs in code/config/docs; pre-rebuild era. Flagged 4x.
[UNREF-BLOB]      "archive/files (2).zip"                   8.8 KB   Git-tracked binary blob; same — duplicate of above with parenthetical suffix.
[UNREF-BLOB]      archive/snipersight-chart-fixes.zip      46.8 KB   Git-tracked binary blob; label suggests chart-fix debugging snapshot; zero refs; 4x.
[BACKUP-FILE]     telemetry.db                              0 bytes   0-byte SQLite placeholder; real DB generated at runtime; git-tracked. Flagged 5x.
[BACKUP-FILE]     .spark-initial-sha                          41 B    Spark.ai deployment artifact; SHA: 3e6a499; no refs in package.json/CI/Docker. 5x.
[BACKUP-FILE]     src/_archive/components/TopBar/           2.5 KB   .bak extension inside an already-archived tree; no live import; backup of a backup.
                  TopBarLite.tsx.bak
[PERSONAL-SCRATCH] src/assets/documents/info.txt            98 B   NEW. Third-party reference bookmark (codeconvey.com). Committed in ee0a842; no refs.
[PERSONAL-SCRATCH] src/assets/documents/index.html          3.4 KB  NEW. Downloaded HTML template (codeconvey.com). Same commit; no refs anywhere.

Tranche-1 size total: ~96 KB

---

TRANCHE 2 — Documentation moves (archive only, content unchanged)
-----------------------------------------------------------------

[DOC-HISTORICAL]  prototype/ (directory — 8 HTML files + JSX + CSS, ~950 KB total)
  -> archive/prototype/
  Evidence: Pre-build-era visual specification snapshots (Bot.html, Intel.html, Journal.html,
  Landing.html, Scanner.html, Settings.html, Training.html + app.jsx/shared.jsx etc.).
  Last touched in ee0a842 (Phase 4F, June 2026) — no functional changes, timestamp artifact.
  prototype/README.md confirms "static HTML prototypes for visual reference." Not referenced by
  any active src/, build config, Dockerfile, or test. Carry-forward from Jun-22 manifest.
  Action: git mv prototype/ archive/prototype/ (no content change, purely a relocation).

---

TRANCHE 3 — Quarantine (one-week soak, then delete)
---------------------------------------------------

[ORPHAN-TEST]  tests/test_backend.py   1.2 KB   references-missing-mode: "recon" (line 14)
  Signals: (1) calls get_signals(..., sniper_mode="recon", ...) as live API — "recon" removed
  per CLAUDE.md §4; (2) not asserting absence of the mode — treating it as valid live config.
  Would fail in any CI that exercises the live API path.

[ORPHAN-TEST]  tests/test_orchestrator_imports.py   830 B   references-missing: "recon" (lines 15, 21)
  Signals: (1) ScanConfig(profile="recon") + Orchestrator instantiation with removed profile;
  (2) not asserting absence — expecting "recon" to work as a live valid profile.
  Both tests import real production modules (not mocks). Either would raise on execution.

---

TRANCHE 4 — Review-only (do not touch without further analysis)
---------------------------------------------------------------

[DOC-STALE-CURRENT]  ARCHITECTURE.md
  Drift detected: Self-annotated "Pre-implementation blueprint (partially stale)." Still describes
  "Scanner Mode (Recon)" as a live mode; pipeline diagrams pre-date SniperContext design; references
  PRD.md (removed). Has a staleness warning at top but body remains misleading for anyone who scrolls.
  Recommended: rewrite top-level mode table and pipeline diagram; remove PRD.md refs.

[DOC-STALE-CURRENT]  PROJECT_STRUCTURE.md
  Drift detected: Self-annotated "Pre-implementation blueprint (partially stale)." Describes
  Python-only project layout (no src/ React tree, no FastAPI). Actual repo has backend/ + src/.
  Recommended: rewrite module map from `tree -L 3 backend src` output.

[DOC-STALE-CURRENT]  QUICKSTART.md
  Drift detected: Top section self-annotates stale framing ("Spark application / documentation
  viewer"). Current content section appears accurate (uvicorn port 8000, Vite port 5000). Historical
  blueprint reference section at bottom not marked for removal. Partial update in place; the
  historical blueprint section should be extracted to docs/archive/ or deleted.

[DOC-STALE-CURRENT]  SETUP_INSTRUCTIONS.md
  Drift detected: Windows-targeted manual install guide generated from a failed automated installer
  ("The automated installation of required tools failed. Please manually install the following").
  Likely accurate for one-time Windows setup but not a maintained operational doc. No connection
  to current Docker/uvicorn/Vite launch path documented in CLAUDE.md.
  Recommended: fold into QUICKSTART.md Prerequisites section or move to docs/archive/.

[DOC-STALE-CURRENT]  docs/SMC_PIPELINE_REFACTOR.md
  Drift detected: Documents the recon→stealth / ghost→stealth migration (lines 128-129). Those
  mode names appear as migration history (intentional) but the broader doc describes the SMC
  pipeline pre-Phase-5 anchoring and pre-heart-change execution. Content may misrepresent current
  scoring and regime logic. Flagged Jul-06.
  Recommended: retain migration table (lines 128-129) as historical; audit rest against current
  orchestrator for content drift before marking as current-state doc.

[DOC-STALE-CURRENT]  docs/INTEGRATION_GUIDE.md
  Drift detected: Describes integration contracts and API endpoints that may have changed since
  the heart-change refactor (commits 8498cf9 onwards). No recon/ghost refs but API surface
  has evolved. Flagged Jul-06.
  Recommended: compare against backend/diagnostics/contracts/ and current api_server.py routes.

[DOC-STALE-CURRENT]  docs/API_ADDITIONS.md
  Drift detected: Documents API additions in chronological addition order; the admission gate
  (Gates 1-3, commits 7c44595, a5728c4, 6c3bd86) and trailing-stop endpoints are not reflected.
  Flagged Jul-06.
  Recommended: extend with post-Jun-28 additions or convert to auto-generated contract diff output.

[DOC-SUSPECT]  docs/WALLET_AUTHENTICATION.md
  Why suspect: Documents Web3 wallet auth via MetaMask as a live feature. But
  src/_archive/components/WalletConnect/ and src/_archive/components/WalletGate/ are both in
  _archive (archived components = feature removed or deferred). Single signal (wallet code
  archived) — needs second confirmation (e.g., grep api_server.py for /auth/wallet routes)
  before reclassifying as STALE-CURRENT. Flagged Jul-06, Jul-20.

[CONFIG-DRIFT]  package.json — react-day-picker residual
  Issue: react-day-picker ^9.6.7 remains in dependencies after the 2026-05-22 dep eject (44
  packages removed). This was the one package NOT ejected in that pass (decision doc
  2026-05-22__package-json-eject-44-deps.md). Still present as of this pass. Not referenced in
  active src/ (unverified this pass — carry-forward from Jul-06 where grep returned zero hits).
  Recommended: verify zero-use with `grep -r "react-day-picker" src/ --include="*.ts" --include="*.tsx"
  | grep -v _archive` then eject if clean.

[SUSPECT-STUB]  backend/examples/  (contains __init__.py only, 0 bytes)
  Why suspect: Directory exists with no content beyond an empty __init__.py. Not referenced by
  any test, Dockerfile, or import in active code. Single signal — could be a placeholder for
  planned examples. Needs import-search confirmation before quarantine.

[SUSPECT-STUB]  backend/devtools/  (contains __init__.py only, 0 bytes)
  Why suspect: Same pattern as backend/examples/. Empty __init__.py only. No active imports.
  devtools/ has a generic name suggesting it was scaffolded but never populated.

[STALE-SCRIPT]  scripts/backtest_from_csv.py
  Stale-mode refs: RECON = "recon" (line 54). Two signals: (1) enumerates removed scanner mode
  as a valid enum value; (2) CLAUDE.md §4 explicitly bans reintroduction of "recon". Script
  would silently use fallback or raise if the mode string is passed to get_mode().
  Last touched: ee0a842 (Phase 4F, June 2026 — timestamp artifact, not functional touch).

[STALE-SCRIPT]  scripts/backtest_full_pipeline.py
  Stale-mode refs: RECON = "recon" (line 60), GHOST = "ghost" (line 63), CLI help text lists
  "overwatch/recon/strike/surgical/ghost" (line 1050). Two signals: (1) enumerates two removed
  modes; (2) CLI --mode arg would accept "recon"/"ghost" and pass them to engine.

[STALE-SCRIPT]  scripts/backtest_modes.py
  Stale-mode refs: profile='recon' (line 200), modes_to_test = ['overwatch', 'recon', 'strike',
  'surgical', 'ghost'] (line 361). Two signals: (1) hardcodes removed modes in test matrix;
  (2) loop would attempt live engine calls with invalid profiles.

[STALE-SCRIPT]  scripts/backtest_scanner.py
  Stale-mode refs: ScanConfig(profile='recon') (lines 104, 171), get_mode('recon') (lines 105,
  172). Two signals: (1) directly constructs live ScanConfig with removed profile; (2) calls
  get_mode() which would raise or return fallback on unknown profile.

[STALE-SCRIPT]  scripts/debug/debug_arm_scanner.py
  Stale-mode refs: profile="recon" (line 58), sniper_mode="recon" (line 95). Two signals:
  (1) passes removed mode to live scanner config; (2) sniper_mode param to API endpoint.

[STALE-SCRIPT]  scripts/debug/debug_trade_type_changes.py
  Stale-mode refs: ghost = get_mode("ghost") (lines 72-76), tests ghost.expected_trade_type.
  Two signals: (1) calls get_mode() with removed mode string; (2) asserts behavioral property
  of a mode that no longer exists — assertion would pass only if get_mode() has a silent fallback,
  which would itself be a standing-fix violation (CLAUDE.md §10: "Pre-scoring gate failure skips
  scoring entirely; soft penalties cannot compensate for a failed gate").

[SUSPECT-SCRIPT]  scripts/janitor_tranche1_3c.sh
  Why suspect: Generated 2026-05-07 by a prior repo-janitor agent. Primary purpose was to `git rm`
  the 47 debug-output .txt files in backend/diagnostics/ — now confirmed NEVER git-tracked (this
  pass). The git-rm block would be a no-op against the canonical tree. Secondary targets
  (telemetry.db, .spark-initial-sha) remain valid action candidates but those can be issued as
  direct git rm commands without this stale wrapper script. Single signal: script's primary target
  class (diagnostics/*.txt) has been resolved as not-in-git. Needs second-source confirmation that
  ALL listed targets are either already gone or better handled directly before quarantine.

---

Off-limits items observed (for your awareness — NOT proposed for action)
------------------------------------------------------------------------
- backend/diagnostics/ (§12 iterate-loop scripts; all .py files are KEEP)
- backend/diagnostics/decisions/ (79 entries; all KEEP — calibration history)
- backend/shared/config/scanner_modes.py (standing-fix surface per CLAUDE.md §10)
- backend/engine/orchestrator.py (standing-fix surface)
- src/_archive/ (intentionally archived component tree; managed by operator; not proposed)
- .claude/agents/*.md (tooling — off-limits per protocol)
- archive/reports/ (11 files — all DOC-HISTORICAL; audit trail; no action proposed)
- docs/audits/JANITOR_MANIFEST_*.md (5 files including this one — audit trail; no action)

---

Proposed Tranche-1 Command (DO NOT RUN until operator approves)
---------------------------------------------------------------
# Approved items only — strike any line to skip:

git rm "archive/files.zip" "archive/files (2).zip" archive/snipersight-chart-fixes.zip
git rm telemetry.db .spark-initial-sha
git rm "src/_archive/components/TopBar/TopBarLite.tsx.bak"
git rm src/assets/documents/info.txt src/assets/documents/index.html

# Optional .gitignore addition (prevents future *.txt commits from backend/diagnostics/):
# echo "backend/diagnostics/*.txt" >> .gitignore && git add .gitignore

# After approval and git rm commands, stage + commit:
# git commit -m "chore(janitor): Tranche-1 cleanup 2026-07-27"

Proposed Tranche-3 Command (DO NOT RUN until operator approves — quarantine first)
----------------------------------------------------------------------------------
git mv tests/test_backend.py tests/_quarantine/test_backend.py
git mv tests/test_orchestrator_imports.py tests/_quarantine/test_orchestrator_imports.py
# One-week soak in _quarantine, then:
# git rm tests/_quarantine/test_backend.py tests/_quarantine/test_orchestrator_imports.py

---

Recommended Next Step
---------------------
1. Operator reviews Tranche 1 (8 items) — strike any line to skip — and runs the proposed
   git rm command block. Highest-confidence items: src/assets/documents/ (NEW, clearly accidental)
   and the archive/*.zip blobs (4-pass history, zero refs). telemetry.db + .spark-initial-sha
   have been pending since May-07 — nine weeks.
2. Optionally add `backend/diagnostics/*.txt` to .gitignore (closes the saga that ran 5 passes).
3. Operator reviews Tranche 3 (2 orphan tests) and approves quarantine move.
4. For Tranche 4 stale-script items: update the 6 backtest/debug scripts to use only the four
   live modes (OVERWATCH / STRIKE / SURGICAL / STEALTH). This is a low-risk find-and-replace on
   scripts only — no engine code touched.
5. For Tranche 4 stale-current docs: invoke the engineering:documentation skill or manual rewrite
   pass, prioritized: ARCHITECTURE.md first (most-cited by new session bootstraps).
6. Re-run repo-janitor after Tranche-1 actioning to detect any cascading orphans.
7. Reference engineering:tech-debt skill for cross-tranche prioritization if needed.
