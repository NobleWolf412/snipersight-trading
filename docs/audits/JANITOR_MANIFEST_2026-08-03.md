REPO-JANITOR INVENTORY
======================
Date: 2026-08-03
Scope: Full repo minus off-limits list; git-tracked files only unless noted
Prior manifest: docs/audits/JANITOR_MANIFEST_2026-07-27.md
Off-limits respected: YES — .live_trading/, .coverage, .git/, .github/, .storybook/, .cursor/,
  CLAUDE.md, LICENSE, Dockerfile.*, .dockerignore, .claude/agents/*.md, .claude/skills/,
  .claude/worktrees/, backend/diagnostics/*.py (§12 iterate-loop scripts), backend/diagnostics/decisions/,
  backend/diagnostics/phase_archive/, standing-fix surface (scorer.py, orchestrator.py, regime_*.py,
  scanner_modes.py, smc_*.py, smc_service.py, regime_policies.py) — all KEEP per CLAUDE.md §10.
  DESIGN.md — ACTIVE (referenced by live src/components/ and src/pages/); excluded from candidates.

Activity since 2026-07-27 (1 commit):
  7b9a7d9 docs(janitor): weekly repo-janitor inventory manifest 2026-07-27 (the manifest itself)
  Net new clutter from code activity: ZERO.

RESOLUTION TRACKER — carry-forward aging:
  telemetry.db + .spark-initial-sha:    13 weeks (first flagged 2026-05-07, 6 passes, unactioned)
  archive/*.zip (3 blobs):              11 weeks (first flagged 2026-05-20, 5 passes, unactioned)
  orphan tests (2):                      4 weeks (first flagged 2026-07-06, 4 passes, unactioned)
  src/_archive/TopBarLite.tsx.bak:       6 weeks (first flagged 2026-06-22, 4 passes, unactioned)
  src/assets/documents/{info,index}:     1 week  (first flagged 2026-07-27, 1 pass, unactioned)
  prototype/ → archive/prototype/:       6 weeks (first flagged 2026-06-22, 4 passes, unactioned)

ESCALATIONS this pass:
  docs/WALLET_AUTHENTICATION.md: SUSPECT → DOC-STALE-CURRENT (two signals now confirmed; see T4)

NEW ITEMS this pass:
  docs/Phemex API OHLCV Data Breakdown.docx — re-surfaced (in May-20 + Jun-22 manifests, then
    silently dropped from Jul-06/Jul-20/Jul-27 without being resolved). Still git-tracked at 6 MB.
  SECURITY.md root vs docs/security.md — new CONFIG-DRIFT item (content-purpose collision).

Zero Tranche-1 items actioned since 2026-07-27.

Total candidates: 31  (29 carry-forward + 2 new/re-surfaced)
By tranche:
  Tranche 1 (zero-risk delete):         8 items  (all carry-forward; no new T1 items)
  Tranche 2 (low-risk archive moves):   2 items  (prototype/ carry-forward + Phemex docx re-surfaced)
  Tranche 3 (quarantine first):         2 items  (carry-forward orphan tests)
  Tranche 4 (review-only):             19 items  (17 carry-forward + 1 escalated + 1 new)

---

SHORT SUMMARY
=============

Total candidates by category:
  UNREF-BLOB           3 items  (archive/*.zip — binary blobs, git-tracked, zero code refs)
  BACKUP-FILE          3 items  (telemetry.db + .spark-initial-sha + TopBarLite.tsx.bak)
  PERSONAL-SCRATCH     2 items  (src/assets/documents/ — codeconvey.com download artifact)
  HISTORICAL-MOVE      2 items  (prototype/ — HTML snapshots; Phemex .docx — re-surfaced)
  ORPHAN-TEST          2 items  (test_backend.py + test_orchestrator_imports.py — recon mode ref)
  DOC-STALE-CURRENT    8 items  (ARCHITECTURE.md, PROJECT_STRUCTURE.md, QUICKSTART.md,
                                  SETUP_INSTRUCTIONS.md, docs/SMC_PIPELINE_REFACTOR.md,
                                  docs/INTEGRATION_GUIDE.md, docs/API_ADDITIONS.md,
                                  docs/WALLET_AUTHENTICATION.md [escalated from SUSPECT])
  CONFIG-DRIFT         2 items  (react-day-picker in package.json; root SECURITY.md vs docs/security.md)
  SUSPECT-STUB         2 items  (backend/examples/ + backend/devtools/ — __init__.py only)
  STALE-SCRIPT         6 items  (backtest scripts + debug scripts with live recon/ghost mode refs)
  SUSPECT-SCRIPT       1 item   (scripts/janitor_tranche1_3c.sh — primary target class gone)

Top 5 highest-confidence DELETE / quarantine recommendations (unchanged from 2026-07-27):

  1. src/assets/documents/info.txt (98 B) + src/assets/documents/index.html (3.4 KB)
     Git-tracked, committed in ee0a842. Content is a third-party promotional bookmark
     (codeconvey.com). Zero references in any live src, build config, or Dockerfile.
     Two signals: (1) no import or reference in any active source; (2) explicitly third-party
     material with no SniperSight connection. Now 2 passes unactioned.

  2. archive/files.zip (33.8 KB) + "archive/files (2).zip" (8.8 KB) +
     archive/snipersight-chart-fixes.zip (46.8 KB)
     Git-tracked binary blobs. Zero grep hits in any active code, config, or doc.
     No metadata. Combined 89.2 KB of binary dead weight in git history.
     Five consecutive passes unactioned. Longest-running T1 group after telemetry.db.

  3. telemetry.db (0 bytes) + .spark-initial-sha (41 bytes)
     telemetry.db is a 0-byte placeholder (real SQLite is generated at runtime, never committed).
     .spark-initial-sha is a Spark.ai deployment artifact; SHA: 3e6a499; not referenced in
     package.json, CI, Dockerfiles, or any .py. Both git-tracked. SIX passes, 13 weeks, zero action.

  4. tests/test_backend.py + tests/test_orchestrator_imports.py
     test_backend.py: calls get_signals(..., sniper_mode="recon") as a live API path (line 16).
     test_orchestrator_imports.py: ScanConfig(profile="recon") against live Orchestrator.
     "recon" is a removed mode (CLAUDE.md §4). Both tests would fail in any CI run.
     Two signals each: (1) reference removed scanner mode; (2) treating it as valid live config.
     Four passes unactioned.

  5. src/_archive/components/TopBar/TopBarLite.tsx.bak (2.5 KB)
     .bak file inside an already-archived component tree. No active import. Backup of a backup.
     Four passes unactioned.

---

TRANCHE 1 — Build artifacts, caches, backup files, personal scratch
--------------------------------------------------------------------

[UNREF-BLOB]      archive/files.zip                        33.8 KB   Git-tracked binary blob; zero refs in code/config/docs; pre-rebuild era. Flagged 5x.
[UNREF-BLOB]      "archive/files (2).zip"                   8.8 KB   Git-tracked binary blob; same provenance; parenthetical suffix suggests ad-hoc duplicate. 5x.
[UNREF-BLOB]      archive/snipersight-chart-fixes.zip      46.8 KB   Git-tracked binary blob; label suggests chart-fix debugging snapshot; zero refs. 5x.
[BACKUP-FILE]     telemetry.db                              0 bytes   0-byte SQLite placeholder; real DB generated at runtime; git-tracked. 6 passes, 13 weeks.
[BACKUP-FILE]     .spark-initial-sha                          41 B    Spark.ai deployment artifact; not referenced in package.json/CI/Docker. 6 passes, 13 weeks.
[BACKUP-FILE]     src/_archive/components/TopBar/           2.5 KB   .bak extension inside an already-archived tree; no live import; backup of a backup. 4x.
                  TopBarLite.tsx.bak
[PERSONAL-SCRATCH] src/assets/documents/info.txt            98 B    Third-party reference bookmark (codeconvey.com). Committed ee0a842; no refs. 2x.
[PERSONAL-SCRATCH] src/assets/documents/index.html          3.4 KB  Downloaded HTML template (codeconvey.com). Same commit; no refs anywhere. 2x.

Tranche-1 size total: ~96 KB

---

TRANCHE 2 — Documentation moves (archive only, content unchanged)
-----------------------------------------------------------------

[DOC-HISTORICAL]  prototype/ (directory — 24 files: HTML/JSX/CSS, ~1.1 MB total)
  -> archive/prototype/
  Evidence: Pre-build-era visual specification snapshots (Bot.html, Intel.html, Journal.html,
  Landing.html, Scanner.html, Settings.html, Training.html, app.jsx, shared.jsx, landing.css,
  etc.). prototype/README.md confirms "static HTML prototypes for visual reference." Not referenced
  by any active src/, build config, Dockerfile, or test. Baseline screenshots subdirectory also
  present. Four passes unactioned.
  Action: git mv prototype/ archive/prototype/ (no content change — relocation only).

[UNREF-BLOB]      docs/Phemex API OHLCV Data Breakdown.docx    6.0 MB
  -> archive/docs/
  Evidence: 6 MB binary .docx in a text-centric docs/ directory. Git-tracked (confirmed via
  git ls-files). Zero references in any active .py, .ts, .tsx, .md, .yml, or Dockerfile.
  Re-surfaced: was in May-20 and Jun-22 manifests (classified DOC-HISTORICAL in Jun-22), then
  silently dropped from Jul-06/Jul-20/Jul-27 without being resolved. Now back with explicit
  re-surface notice. Not a delete candidate — it's a reference breakdown of Phemex OHLCV data;
  binary content may be useful if exchange integration is revisited.
  Two signals: (1) no reference in any active source; (2) 6 MB binary pollutes text-only docs/.
  Action: git mv "docs/Phemex API OHLCV Data Breakdown.docx" "archive/docs/Phemex API OHLCV Data Breakdown.docx"

---

TRANCHE 3 — Quarantine (one-week soak, then delete)
---------------------------------------------------

[ORPHAN-TEST]  tests/test_backend.py   1.2 KB   references-missing-mode: "recon" (line 16)
  Signals: (1) calls get_signals(..., sniper_mode="recon", ...) as live API — "recon" removed
  per CLAUDE.md §4; (2) not asserting absence of the mode — treating it as valid live config.
  Line 15 comment: "Use a valid sniper_mode defined in scanner_modes (e.g., 'recon')" —
  the comment now contradicts the actual scanner_modes.py content. Would fail in any CI run.
  Four passes unactioned.

[ORPHAN-TEST]  tests/test_orchestrator_imports.py   830 B   references-missing: "recon" (lines 15, 21)
  Signals: (1) ScanConfig(profile="recon") + Orchestrator instantiation with removed profile;
  (2) not asserting absence — expecting "recon" to work as a live valid profile.
  Both tests import real production modules (not mocks). Either would raise on execution.
  Four passes unactioned.

---

TRANCHE 4 — Review-only (do not touch without further analysis)
---------------------------------------------------------------

[DOC-STALE-CURRENT]  ARCHITECTURE.md                (1762 lines)
  Drift detected: Has status banner (added 2026-05-22 decisions entry). Still describes
  "Scanner Mode (Recon)" as a live mode; pipeline diagrams pre-date SniperContext design;
  references PRD.md (removed — now PRODUCT.md). Banner contextualizes staleness but body
  remains misleading for anyone who scrolls past the header.
  Recommended: rewrite mode table and pipeline diagram; remove PRD.md refs; nine "Recon mode"
  prose locations remain in body post-banner.

[DOC-STALE-CURRENT]  PROJECT_STRUCTURE.md            (953 lines)
  Drift detected: Has status banner (2026-05-22). Describes Python-only project layout (no
  src/ React tree, no FastAPI). Actual repo has backend/ + src/ + tests/visual/ + .claude/ etc.
  Recommended: rewrite module map from `tree -L 3 backend src` output.

[DOC-STALE-CURRENT]  QUICKSTART.md
  Drift detected: Has status banner + real quick-start section (added 2026-05-22). "Historical
  blueprint reference" section at bottom retained but not marked for removal. References PRD.md
  (removed) in historical section at line 115 with parenthetical noting the removal.
  Recommended: delete "Historical blueprint reference" section once ARCHITECTURE.md is rewritten.

[DOC-STALE-CURRENT]  SETUP_INSTRUCTIONS.md
  Drift detected: Windows-targeted manual install guide generated from a failed automated installer
  ("The automated installation of required tools failed. Please manually install the following").
  No connection to current Docker/uvicorn/Vite/start-sniper.bat launch path in CLAUDE.md.
  Not maintained as an operational doc. Likely accurate for one-time Windows setup only.
  Recommended: fold into QUICKSTART.md Prerequisites section, or move to docs/archive/.

[DOC-STALE-CURRENT]  docs/SMC_PIPELINE_REFACTOR.md
  Drift detected: Documents the recon→stealth / ghost→stealth migration. Migration table is
  intentionally historical (keep). Broader doc describes the SMC pipeline pre-Phase-5 anchoring
  and pre-heart-change execution. May misrepresent current scoring and regime logic.
  Recommended: audit body against current orchestrator; retain migration table as historical.

[DOC-STALE-CURRENT]  docs/INTEGRATION_GUIDE.md
  Drift detected: Documents integration contracts and API endpoints. API surface has evolved
  significantly since heart-change refactor (8498cf9 onwards) and admission gates (7c44595–6c3bd86).
  No recon/ghost refs, but endpoint contracts likely drifted.
  Recommended: diff against backend/diagnostics/contracts/ and current api_server.py routes.

[DOC-STALE-CURRENT]  docs/API_ADDITIONS.md
  Drift detected: Documents API additions in chronological order. Admission gates (Gates 1–3,
  commits 7c44595, a5728c4, 6c3bd86), trailing-stop endpoints, and CVD observability endpoints
  (b657e17) are not reflected. Now ~6 weeks behind the current API surface.
  Recommended: extend with post-Jun-28 additions or convert to auto-generated contract diff output.

[DOC-STALE-CURRENT]  docs/WALLET_AUTHENTICATION.md        (ESCALATED from DOC-SUSPECT)
  Drift confirmed — two signals now in: (1) WalletConnect/ and WalletGate/ components are both
  in src/_archive/ (archived = feature removed or deferred); (2) grep of backend/ finds zero
  wallet auth routes in api_server.py or any backend/api/*.py file. The Web3 wallet auth feature
  this doc describes has been decommissioned. The doc now describes dead functionality.
  Two signals: (1) all frontend components archived; (2) no backend route.
  Recommended: reclassify to DOC-HISTORICAL and archive at docs/archive/WALLET_AUTHENTICATION.md,
  or delete if the wallet feature is permanently shelved.

[CONFIG-DRIFT]  package.json — react-day-picker residual
  Issue: react-day-picker ^9.6.7 remains in dependencies after the 2026-05-22 dep eject (44
  packages removed per decision 2026-05-22__package-json-eject-44-deps.md). This was the one
  package intentionally deferred. Zero usage confirmed: grep of live src/ (excluding _archive)
  returns no hits for "react-day-picker". Package is dead weight.
  Recommended: `npm uninstall react-day-picker` then verify no runtime breakage.

[CONFIG-DRIFT]  root SECURITY.md vs docs/security.md — content-purpose collision    (NEW this pass)
  Issue: Root SECURITY.md (31 lines) is a GitHub default security disclosure template ("GitHub
  takes the security of our software products and services seriously, including all of the open
  source code repositories..."). It is NOT SniperSight-specific. The actual SniperSight security
  architecture doc (Core Security Principles, Zero Client-Side Secrets, API key handling, threat
  mitigation) is docs/security.md (508 lines). A reader looking for "security" will find the
  GitHub boilerplate first. Root SECURITY.md is off-limits per GitHub convention (it controls
  the repo's security advisory disclosure workflow) — do NOT delete. But the collision is worth
  noting: any cross-reference to SECURITY.md will reach the wrong doc.
  Recommended: Add a redirect comment at top of root SECURITY.md pointing to docs/security.md
  for operational security architecture; or rename docs/security.md to docs/SECURITY_ARCH.md
  to distinguish the two purposes clearly.

[SUSPECT-STUB]  backend/examples/  (contains __init__.py only, 0 bytes)
  Why suspect: Directory exists with no content beyond an empty __init__.py. Not referenced by
  any test, Dockerfile, or import in active code. Single signal — could be a placeholder for
  planned examples. Needs import-search confirmation before quarantine proposal.

[SUSPECT-STUB]  backend/devtools/  (contains __init__.py only, 0 bytes)
  Why suspect: Same pattern as backend/examples/. Empty __init__.py only. No active imports.
  devtools/ has a generic name suggesting it was scaffolded but never populated.

[STALE-SCRIPT]  scripts/backtest_from_csv.py
  Stale-mode refs: RECON = "recon" (line 54). Two signals: (1) enumerates removed scanner mode
  as a valid enum value; (2) CLAUDE.md §4 explicitly bans reintroduction of "recon".

[STALE-SCRIPT]  scripts/backtest_full_pipeline.py
  Stale-mode refs: RECON = "recon" (line 60), GHOST = "ghost" (line 63), CLI help text lists
  "overwatch/recon/strike/surgical/ghost" (line 1050). Two signals: two removed modes, CLI
  --mode arg would accept "recon"/"ghost" and pass them to engine.

[STALE-SCRIPT]  scripts/backtest_modes.py
  Stale-mode refs: profile='recon' (line 200), modes_to_test = ['overwatch', 'recon', 'strike',
  'surgical', 'ghost'] (line 361). Two signals: hardcodes removed modes in test matrix; loop
  would attempt live engine calls with invalid profiles.

[STALE-SCRIPT]  scripts/backtest_scanner.py
  Stale-mode refs: ScanConfig(profile='recon') (lines 104, 171), get_mode('recon') (lines 105,
  172). Two signals: directly constructs live ScanConfig with removed profile; get_mode() would
  raise or return fallback on unknown profile.

[STALE-SCRIPT]  scripts/debug/debug_arm_scanner.py
  Stale-mode refs: profile="recon" (line 58), sniper_mode="recon" (line 95). Two signals:
  passes removed mode to live scanner config; sniper_mode param to API endpoint.

[STALE-SCRIPT]  scripts/debug/debug_trade_type_changes.py
  Stale-mode refs: ghost = get_mode("ghost") (lines 72-76), tests ghost.expected_trade_type.
  Two signals: calls get_mode() with removed mode string; asserts behavioral property of a mode
  that no longer exists. A silent fallback here would itself be a §10 standing-fix violation.

[SUSPECT-SCRIPT]  scripts/janitor_tranche1_3c.sh   (6.1 KB)
  Why suspect: Generated 2026-05-07 by prior repo-janitor agent. Primary purpose was to
  `git rm` 47 debug-output .txt files in backend/diagnostics/ — confirmed NEVER git-tracked
  (resolved in 2026-07-27 pass). Secondary targets (telemetry.db, .spark-initial-sha) remain
  valid action candidates but are better handled as direct `git rm` commands than through this
  stale wrapper. Single confirmed signal: primary target class is non-existent in git tree.
  Second signal needed: verify ALL secondary targets in the script are either still valid git rm
  targets OR already handled before proposing quarantine.

---

Off-limits items observed (for your awareness — NOT proposed for action)
------------------------------------------------------------------------
- backend/diagnostics/ (§12 iterate-loop scripts; all .py files are KEEP)
- backend/diagnostics/decisions/ (100+ entries; all KEEP — calibration history)
- backend/shared/config/scanner_modes.py (standing-fix surface per CLAUDE.md §10)
- backend/engine/orchestrator.py (standing-fix surface)
- src/_archive/ (intentionally archived component tree; managed by operator; not proposed)
- .claude/agents/*.md (tooling — off-limits per protocol)
- archive/reports/ (11 files — all DOC-HISTORICAL; audit trail; no action proposed)
- docs/audits/JANITOR_MANIFEST_*.md (6 files including this one — audit trail; no action)
- DESIGN.md — ACTIVE (referenced by live src/components/hud/PositionDetailModal.tsx and
  src/pages/BotStatus.tsx as the design token source of truth; do not propose for action)
- PRODUCT.md — ACTIVE (referenced in README.md + ARCHITECTURE.md; has "register: product"
  frontmatter; used as a product-framing reference for session bootstraps)
- docs/TF_RESPONSIBILITY_FLOW.txt — classified DOC-ACTIVE in Jun-22 manifest; carry-forward
  classification unchanged (ASCII TF enforcement diagram, still a reference document)

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
# git commit -m "chore(janitor): Tranche-1 cleanup 2026-08-03"

Proposed Tranche-2 Command (DO NOT RUN until operator approves — relocation only)
----------------------------------------------------------------------------------
mkdir -p archive/docs
git mv prototype/ archive/prototype/
git mv "docs/Phemex API OHLCV Data Breakdown.docx" "archive/docs/Phemex API OHLCV Data Breakdown.docx"
# git commit -m "chore(janitor): Tranche-2 archive moves 2026-08-03"

Proposed Tranche-3 Command (DO NOT RUN until operator approves — quarantine first)
----------------------------------------------------------------------------------
git mv tests/test_backend.py tests/_quarantine/test_backend.py
git mv tests/test_orchestrator_imports.py tests/_quarantine/test_orchestrator_imports.py
# One-week soak in _quarantine, then:
# git rm tests/_quarantine/test_backend.py tests/_quarantine/test_orchestrator_imports.py

---

Recommended Next Step
---------------------
1. Operator reviews Tranche 1 (8 items, ~96 KB) and runs the proposed git rm block.
   telemetry.db + .spark-initial-sha have been unactioned for 13 weeks (6 consecutive passes).
   archive/*.zip blobs have been unactioned for 11 weeks (5 consecutive passes).
   src/assets/documents/ items are clearly accidental — 2 passes unactioned.
   These are zero-risk; continued deferral has no upside.

2. Operator reviews Tranche 2 (2 archive moves):
   prototype/ → archive/prototype/ has been pending 6 weeks; 6 MB of binary .docx similarly
   has been pending since May-20. Both are relocation-only, no content change.

3. Operator reviews Tranche 3 (2 orphan tests). The orphan tests have been pending 4 weeks.
   They would fail in any CI run that exercises the live API path. Quarantine is recoverable
   (one-week soak); deletion is one command away. Highest-urgency Tranche-3 call of this run.

4. Tranche 4 — stale scripts: update the 6 backtest/debug scripts to use only the four live
   modes (OVERWATCH / STRIKE / SURGICAL / STEALTH). Low-risk find-and-replace on scripts only.

5. Tranche 4 — docs/WALLET_AUTHENTICATION.md: now confirmed STALE-CURRENT (two signals). This
   should be reclassified as DOC-HISTORICAL and archived, or deleted, depending on whether the
   wallet auth feature is permanently shelved. Operator decision required.

6. Tranche 4 — react-day-picker: `npm uninstall react-day-picker` is a safe one-liner once the
   dep eject decision (2026-05-22__package-json-eject-44-deps.md) is formally closed on this item.

7. Re-run repo-janitor after Tranche-1/Tranche-2 actioning to detect cascading orphans.

Aging alert: The longest-running Tranche-1 items (telemetry.db, .spark-initial-sha) have now been
in the manifest for 13 weeks across 6 passes. Continued deferral erodes the manifest's credibility
as a live signal. Recommend committing to Tranche-1 this week.
