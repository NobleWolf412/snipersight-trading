
REPO-JANITOR INVENTORY
======================
Date: 2026-06-22
Scope: Full repo minus off-limits list; git-tracked files only where noted
Off-limits respected: YES — .live_trading/, .coverage, .git/, .github/, .storybook/, .cursor/,
  CLAUDE.md, LICENSE, Dockerfile.*, .dockerignore, .claude/agents/*.md, .claude/skills/,
  .claude/worktrees/ all untouched and not proposed for action.
Prior manifest: docs/audits/JANITOR_MANIFEST_2026-05-20.md (operator reviewed, no tranches actioned)
Since last pass:  commit 6f2bad0 landed (docs rewrite + status banners on ARCHITECTURE/PROJECT_STRUCTURE/QUICKSTART);
  44 npm deps ejected (decisions/2026-05-22__package-json-eject-44-deps.md).

Total candidates: 47
By tranche:
  Tranche 1 (zero-risk delete):        33 items (5 logical groups)
  Tranche 2 (low-risk archive moves):   2 items (prototype/ + docx)
  Tranche 3 (quarantine / suspect):     2 items (stub namespace dirs — SUSPECT only)
  Tranche 4 (review-only):             10 items

---

SHORT SUMMARY
=============

Total candidates by category:
  LOG-ARTIFACT      29 items  (root diagnostics/*.txt — old run outputs from March 2026)
  BACKUP-FILE        1 item   (TopBarLite.tsx.bak inside _archive)
  UNREF-BLOB         3 items  (archive/*.zip pre-rebuild binaries)
  HISTORICAL-MOVE    2 items  (prototype/ → archive; docx → archive/docs)
  SUSPECT-STUB       2 items  (backend/examples/, backend/devtools/ empty namespace dirs)
  DOC-STALE-CURRENT  5 items  (SECURITY.md, SETUP_INSTRUCTIONS.md + 3 docs/ files)
  DOC-CARRY-FWD      3 items  (ARCHITECTURE.md, PROJECT_STRUCTURE.md, QUICKSTART.md — banners in
                               place since 2026-05-22, rewrites still pending)
  CONFIG-DRIFT       1 item   (react-day-picker missed in May eject, zero active src usage)
  DOC-ACTIVE         1 item   (docs/TF_RESPONSIBILITY_FLOW.txt — noted, not actioned)

Top 5 highest-confidence DELETE recommendations:
  1. diagnostics/*.txt (29 files, ~324 KB) — raw diagnostic output dumps from March 2026, pre-
     Phase-5 era, git-tracked, no code, fully superseded by current backend/diagnostics/ outputs.
  2. archive/files.zip + archive/files (2).zip + archive/snipersight-chart-fixes.zip (96 KB
     combined) — unreferenced pre-rebuild binary blobs, flagged in prior pass, still unactioned.
  3. src/_archive/components/TopBar/TopBarLite.tsx.bak (2.5 KB) — .bak file inside an already-
     archived component subtree; even the parent files are not live code.
  4. react-day-picker from package.json — zero hits in active src/; missed in the 44-dep May eject;
     simple npm uninstall + lockfile update (not a git rm but a dep removal).
  5. docs/Phemex API OHLCV Data Breakdown.docx (6.2 MB) — heavy binary artifact polluting the
     text-only docs/ space; move to archive/docs/ first, then delete when no longer needed.

NEW CLUTTER SINCE 2026-05-20:
  - src/_archive/components/TopBar/TopBarLite.tsx.bak (new .bak file, not in prior manifest)
  - react-day-picker dep (missed in the 44-dep eject that shipped 2026-05-22)
  Everything else below is a carry-forward from the prior unactioned pass.

---

TRANCHE 1 — Build artifacts, caches, backup files
-------------------------------------------------
(Proposed action: git rm after explicit operator approval)

[LOG-ARTIFACT]  diagnostics/cycle_reversal_diagnostic_report.txt           ~18 KB
[LOG-ARTIFACT]  diagnostics/cycle_reversal_diagnostic_report.utf8.txt      ~18 KB
[LOG-ARTIFACT]  diagnostics/diag.txt                                        ~4 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_1d.txt                                ~12 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_1h.txt                                ~12 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_1m.txt                                ~12 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_1w.txt                                ~12 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_4h.txt                                ~12 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_5m.txt                                ~12 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_doge.txt                              ~12 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_eth.txt                               ~12 KB
[LOG-ARTIFACT]  diagnostics/fvg_diag_sol.txt                               ~12 KB
[LOG-ARTIFACT]  diagnostics/fvg_diagnostic_report.txt                      ~12 KB
[LOG-ARTIFACT]  diagnostics/indicator_diagnostic_report.txt                ~12 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_15m.txt                                ~12 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_15m_final.txt                          ~12 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_15m_final2.txt                         ~12 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_1d.txt                                 ~12 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_1h.txt                                 ~12 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_1m.txt                                 ~12 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_1w.txt                                 ~12 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_4h.txt                                 ~12 KB
[LOG-ARTIFACT]  diagnostics/ob_diag_5m.txt                                 ~12 KB
[LOG-ARTIFACT]  diagnostics/output.txt                                       ~1 KB
[LOG-ARTIFACT]  diagnostics/reversal_diagnostic_report.txt                 ~12 KB
[LOG-ARTIFACT]  diagnostics/smc_service_diagnostic_report.txt              ~12 KB
[LOG-ARTIFACT]  diagnostics/sweep_diag_15m.txt                             ~12 KB
[LOG-ARTIFACT]  diagnostics/sweep_diag_all.txt                             ~12 KB
[LOG-ARTIFACT]  diagnostics/sweep_diagnostic_report.txt                    ~12 KB
  Git-tracked: YES (verified via git ls-files)
  Oldest content: "Generated: 2026-03-22 19:42:24" (BTC/USDT 1d FVG diagnostic)
  Rationale: Raw run-output dumps from the early FVG/OB/sweep investigation era (pre-Phase 5,
    pre-BOS/CHOCH rework, pre-Phase 5c structure-anchored P/D). The current backend/diagnostics/
    Python scripts (also protected per §12) generate fresh output on demand. These static dumps
    are 3 months stale vs. the engine that produced them and 6 phases behind current strategy code.
    Two signals: (1) content timestamped March 2026; (2) no import or reference from any .py,
    .bat, .yml, or .md except the prior janitor manifest which itself flagged them.
  Signals: content-timestamp March 2026 + zero code/config references found.
  Recommended disposition: DELETE after confirm (git rm -r diagnostics/).
  Note: The root-level diagnostics/ directory itself would become empty after this; remove it.

[UNREF-BLOB]    archive/files.zip                                           36 KB
[UNREF-BLOB]    archive/files (2).zip                                       12 KB
[UNREF-BLOB]    archive/snipersight-chart-fixes.zip                         48 KB
  Git-tracked: YES (verified via git ls-files)
  Rationale: Pre-rebuild binary blobs; no .py, .md, .bat, .yml, or .ts references them. Named
    without dates or descriptive context. Flagged in prior pass (2026-05-20 Tranche 2); not
    actioned. Zero downstream consumers found (grep -r "files.zip\|chart-fixes.zip" → 0 hits).
  Signals: zero references in codebase + pre-rebuild creation date (Mar 2026).
  Recommended disposition: DELETE after confirm (git rm archive/files.zip
    "archive/files (2).zip" archive/snipersight-chart-fixes.zip).

[BACKUP-FILE]   src/_archive/components/TopBar/TopBarLite.tsx.bak          2.5 KB
  Git-tracked: YES
  Rationale: .bak file inside src/_archive/ — an already-archived component subtree that is
    itself not imported by any active code. The non-.bak siblings (TopBar.tsx, TopBarV2.tsx,
    TopBarLite.tsx) are also archived. This is a backup of a backup.
  Signals: .bak extension + no import of this path in any active .ts/.tsx outside _archive/.
  Recommended disposition: DELETE after confirm (git rm
    src/_archive/components/TopBar/TopBarLite.tsx.bak).
  Note: NEW since 2026-05-20 manifest.

---

TRANCHE 2 — Documentation moves (archive only, content unchanged)
-----------------------------------------------------------------
(Proposed action: git mv to canonical archive home; content NOT rewritten)

[DOC-HISTORICAL]  prototype/  (1.1 MB, 24 files) → archive/prototype/
  Evidence: Contains .jsx/.html prototype files for "Scanner.html", "Bot.html", "Journal.html",
    "Landing.html", etc. These are design-prototype artifacts from the Phase 2-7 HUD rebuild
    source material. The live HUD is in src/components/hud/. No active import of prototype/
    from any .ts/.tsx or build config (vite.config.*, package.json, tsconfig.json). 24 files
    git-tracked.
  Classification: HISTORICAL — pre-implementation design artifact intentionally frozen.
  Carry-forward from 2026-05-20 Tranche 3 (operator noted as "Tranche 3 move" but did not act).
  Proposed: git mv prototype archive/prototype
  Why not delete: Historical design record; low risk to preserve; the Phase 6 ARCHIVE.md
    references prototypes as source material.

[DOC-HISTORICAL]  docs/Phemex API OHLCV Data Breakdown.docx → archive/docs/
  Size: 6.2 MB (binary, non-text)
  Evidence: Not referenced in any .py, .md, .bat, .yml, or .ts file. docs/ is otherwise all
    text — this .docx is an outlier. Prior manifest flagged it as "heavy binary cluttering docs/."
  Classification: HISTORICAL — research/reference artifact, not current documentation.
  Carry-forward from 2026-05-20 Tranche 3.
  Proposed: mkdir -p archive/docs && git mv "docs/Phemex API OHLCV Data Breakdown.docx"
    "archive/docs/Phemex API OHLCV Data Breakdown.docx"

---

TRANCHE 3 — Quarantine (one-week soak before delete)
-----------------------------------------------------
(No confirmed DEAD-PYTHON or ORPHAN-TEST items meet the two-signal minimum)

[*-SUSPECT]  backend/examples/  (empty — only __init__.py, 0 bytes)
  Single signal only: directory has no content beyond the namespace marker.
  Counter-signal: __init__.py is explicitly excluded from dead-code flagging per janitor rules.
  Why suspect: The examples/ namespace was never populated (no .py files of substance committed
    alongside __init__.py). Not imported by any module outside the directory.
  Recommended: flag-for-review. Ask operator: is this a planned-but-never-started examples
    package, or a namespace stub that can be removed?
  Action: DO NOT quarantine or delete without second signal. Surface for operator intent check.

[*-SUSPECT]  backend/devtools/  (empty — only __init__.py, 0 bytes)
  Single signal only: same pattern as examples/.
  Counter-signal: __init__.py protected per rules.
  Recommended: same as above — ask operator intent before any action.

ORPHAN-TESTS NOTE:
  test_fade_threshold_rsi_symmetry.py:120 and test_ob_freshness_gate_authority.py:60 both
  reference "ghost" mode. Verified: both are ASSERTING ABSENCE (testing that ghost/recon cause
  a ValueError/warning — i.e., the mode was correctly removed). Per janitor rules, tests
  asserting *absence* of removed modes are not orphans. These tests PASS the protocol check.
  No action required.

---

TRANCHE 4 — Review-only (do not touch without further analysis)
---------------------------------------------------------------

[DOC-STALE-CURRENT]  SECURITY.md  (1.7 KB)
  Drift detected: Verbatim GitHub stock "Thanks for helping make GitHub safe for everyone"
    template. Zero SniperSight-specific content. Contact address is
    opensource-security[@]github.com (GitHub's security team, not SniperSight). References
    GitHub's own bug bounty scope, not this repository's security posture.
  Flagged in 2026-05-20 pass. Still unchanged.
  Recommended: Rewrite with SniperSight-specific security posture (live-trading API keys,
    exchange credential handling, no-public-issue rule), or delete as empty boilerplate.
  Priority: LOW (no one relies on this as operational guidance).

[DOC-STALE-CURRENT]  SETUP_INSTRUCTIONS.md  (1 KB)
  Drift detected: Generic Windows install guide for Git/Node/Python with "The automated
    installation failed" note. No SniperSight-specific content (no reference to venv,
    requirements.txt, backend start, or C:\start-sniper.bat). Reads like an early Spark
    onboarding artifact, not a working-scanner guide.
  Flagged in 2026-05-20 pass with caveat: "keep if C:\start-sniper.bat references it."
  Verified: C:\start-sniper.bat is not in the git tree (Windows-only launcher, not committed).
    No .py, .md, or .yml references SETUP_INSTRUCTIONS.md.
  Recommended: Either rewrite to cover the actual setup (uvicorn, npm, venv, start-sniper.bat)
    or delete — QUICKSTART.md now covers the same ground with SniperSight-specific commands.

[DOC-STALE-CURRENT]  docs/SMC_PIPELINE_REFACTOR.md  (December 2025)
  Drift detected: Header says "Date: December 2025 / Status: Mostly Complete." Body contains
    TODOs for merging "recon → stealth" and "ghost → stealth" (lines 128-129, 539-541). These
    are completed work per CLAUDE.md §10 standing fix #6 ("only four modes, never reintroduce
    recon or ghost") and scanner_modes.py (verified: only OVERWATCH/STRIKE/SURGICAL/STEALTH
    exist). The doc is a planning artifact that predates the current pipeline and scanner-mode
    model. "Mostly Complete" is a planning status note, not a doc update.
  Recommended: Classify as HISTORICAL (planning doc, intentionally frozen), move to
    archive/reports/ as 2025-12-SMC_PIPELINE_REFACTOR.md, or rewrite as current-state guide.
    The content has residual reference value for WHY the pipeline was designed this way.

[DOC-STALE-CURRENT]  docs/TF_RESPONSIBILITY_FLOW.txt  (11 KB)
  Observation: ASCII-art diagram describing timeframe responsibility enforcement flow.
    Content reads as current documentation (uses present tense, no "historical" or "blueprint"
    framing). Not cross-checked against the live orchestrator for drift — would need a content
    audit vs. backend/engine/orchestrator.py to confirm accuracy. Not referenced from any other
    .md, .py, or .ts file.
  Recommended: flag-for-review. If the TF responsibility flow is still accurate vs. the current
    SniperContext pipeline, it's ACTIVE reference material and should be kept. If it drifted
    (especially around Phase 5 HTF-gate / structure-anchored P/D changes), flag for rewrite.
    A cross-check against orchestrator.py is warranted before next janitor pass.

[DOC-STALE-CURRENT — CARRY-FORWARD]  ARCHITECTURE.md  (62 KB)
  Status: Status banner added 2026-05-22 (commit 6f2bad0). 9+ "Recon Mode" references remain
    below the banner; banner contextualizes them as historical. The full rewrite was deferred
    (decisions/2026-05-22__docs-rewrite-blueprint-to-built.md: "estimated 1-2 hour rewrite").
  Current risk level: LOW (banner is clear; readers are warned). But the doc is actively
    misleading for someone who skips the banner (63 KB of blueprint-era prose).
  Recommended: no new action until operator schedules the rewrite. Carry forward.

[DOC-STALE-CURRENT — CARRY-FORWARD]  PROJECT_STRUCTURE.md  (27 KB)
  Status: Status banner added 2026-05-22. Pre-backend/ tree persists below banner (references
    snipersight_cli.py at root, contracts/ at root, shared/ at root — all wrong).
  Current risk level: LOW (banner in place). Carry forward.

[DOC-STALE-CURRENT — CARRY-FORWARD]  QUICKSTART.md  (15 KB)
  Status: Status banner + real quickstart section added 2026-05-22. Historical section preserved
    below (contains stale PRD.md references at lines 428, 467 — mitigated by inline note).
  Current risk level: VERY LOW (real quickstart now precedes historical content). The plan to
    delete the historical section after ARCHITECTURE.md is rewritten is documented. Carry forward.

[CONFIG-DRIFT]  package.json — react-day-picker dependency
  Issue: react-day-picker still present in package.json (confirmed via current package.json
    scan). NOT included in the 44-dep eject (2026-05-22__package-json-eject-44-deps.md does
    not list it in "Removed"). Zero hits in active src/ excluding _archive/:
    grep -rln "react-day-picker\|DayPicker" src/ --include="*.ts" --include="*.tsx"
    | grep -v _archive → 0 results.
  Hits only in src/_archive/components/ui/calendar.tsx (Radix-era calendar component,
    archived in Phase 7).
  Recommended: npm uninstall react-day-picker + npm install (regenerates lockfile). Low risk —
    same verification gates as the May eject apply (tsc --noEmit, vite build, capture_contracts diff).
  Note: NEW since 2026-05-20 manifest (missed in the eject).

[DOC-ACTIVE (noted, no action)]  docs/TF_RESPONSIBILITY_FLOW.txt
  (Detailed under stale-current above; defer until content-verified against live orchestrator.)

---

Off-limits items observed (for your awareness — NOT proposed for action)
------------------------------------------------------------------------
- .live_trading/ — live trading state, hard off-limits per agent rules; not walked
- .coverage (root) — off-limits per agent rules
- .git/, .github/, .storybook/ — off-limits
- CLAUDE.md — read-only reference; not proposed for action
- LICENSE — never touch
- Dockerfile.backend, Dockerfile.frontend, .dockerignore — load-bearing deployment configs
- .claude/agents/*.md — tooling, not documentation
- .claude/skills/ — tooling, not documentation
- backend/diagnostics/*.py — protected per CLAUDE.md §12 (iterate-loop diagnostic scripts)
- backend/diagnostics/decisions/ — all HISTORICAL, correctly placed, no action needed
- backend/diagnostics/phase_archive/ — HISTORICAL, correctly placed
- Standing-fix surface (scorer.py, orchestrator.py, regime_*.py, scanner_modes.py, smc_*.py,
  smc_service.py, regime_policies.py) — all KEEP per CLAUDE.md §10; no clutter found in these

---

Proposed Tranche-1 Command (DO NOT RUN until operator approves)
---------------------------------------------------------------
# Step 1: diagnostic txt dumps (29 files)
git rm -r diagnostics/

# Step 2: archive binary blobs (3 files)
git rm archive/files.zip "archive/files (2).zip" archive/snipersight-chart-fixes.zip

# Step 3: backup file inside archived component
git rm src/_archive/components/TopBar/TopBarLite.tsx.bak

Proposed Tranche-2 Command (DO NOT RUN until operator approves)
---------------------------------------------------------------
# Step 1: move prototype to archive
git mv prototype archive/prototype

# Step 2: move binary docx to archive/docs
mkdir -p archive/docs
git mv "docs/Phemex API OHLCV Data Breakdown.docx" "archive/docs/Phemex API OHLCV Data Breakdown.docx"

Proposed Config-Drift Fix (separate from tranches, low risk)
-----------------------------------------------------------
# Run in repo root with venv active + node installed
npm uninstall react-day-picker
# Then verify: npx tsc --noEmit && python -m backend.diagnostics.capture_contracts diff

---

RAW EVIDENCE
============

diagnostics/ file count and total size:
  29 files, ~324 KB total (du -sh diagnostics/*.txt)
  Oldest timestamp: content "Generated: 2026-03-22 19:42:24" (fvg_diag_1d.txt)

archive/ zip sizes:
  archive/files.zip:                 36K (git-tracked)
  archive/files (2).zip:             12K (git-tracked)
  archive/snipersight-chart-fixes.zip: 48K (git-tracked)
  Total: 96K

prototype/ size:
  du -sh prototype/ → 1.1M, 24 tracked files

docs/ binary:
  docs/Phemex API OHLCV Data Breakdown.docx: 6,212,484 bytes (6.2 MB)

react-day-picker grep result (active src):
  grep -rln "react-day-picker|DayPicker" src/ --include=*.ts --include=*.tsx | grep -v _archive
  → 0 results
  grep -rln "react-day-picker|DayPicker" src/_archive/
  → src/_archive/components/ui/calendar.tsx (Radix-era archived component)

backend/ml/ import chain (NOT dead):
  backend/api_server.py:196   → from backend.ml.model_store import get_model_store
  backend/api_server.py:1448  → from backend.ml.signal_dataset_builder import ...
  backend/bot/paper_trading_service.py:2264 → from backend.ml.model_store import get_model_store
  Conclusion: backend/ml/ is live. Do NOT flag.

Ghost/recon test references (asserting absence — NOT orphan tests):
  test_fade_threshold_rsi_symmetry.py:120 → _ModeConfig(name="ghost") → tests rejection
  test_ob_freshness_gate_authority.py:60  → filter_obs_by_mode(mode_profile="ghost") → pytest.raises(ValueError)
  Conclusion: both tests assert absence of removed modes. PASS per janitor protocol.

package.json dep count post-eject:
  Total deps: 55 (dependencies + devDependencies combined)
  Orphan deps still present: class-variance-authority (intentionally retained per
    decisions/2026-05-22__package-json-eject-44-deps.md), react-day-picker (missed, new flag)

Recent commits relevant to this pass (git log --oneline -20):
  a157929 docs(decisions): decision-core heart-change spec
  107e2fc feat(rules): liquidity admission filter
  7c9a7ad fix(journal): snapshot regime at ENTRY, not close (bug #1)
  7c181c0 feat(cascade): cut swing tier from STEALTH
  [... 16 more commits since May 20, all in backend/ — no new root-level files introduced]

---

STATUS OF PRIOR MANIFEST ITEMS (2026-05-20):
  Tranche 1 (root file duplicates, 89 items): COMPLETED — root-level duplicate scripts/dumps
    are gone; verified not present at repo root.
  Tranche 2 (caches, zips, logs): PARTIALLY DONE — __pycache__, .pytest_cache, dist/ are gone;
    archive zips STILL PRESENT (not actioned).
  Tranche 3 (moves): NOT ACTIONED — prototype/ and docx still in original locations.
  Tranche 6 (stale-current docs): PARTIALLY DONE — README.md fully rewritten; ARCHITECTURE.md,
    PROJECT_STRUCTURE.md, QUICKSTART.md got status banners (commit 6f2bad0). Full rewrites
    of ARCHITECTURE.md and PROJECT_STRUCTURE.md still outstanding.
  Package.json eject: DONE (44 deps ejected, 2026-05-22). react-day-picker missed — new flag.
  .claire/ directory: RESOLVED — directory no longer exists.

---

Recommended Next Step
---------------------
1. **Approve Tranche 1** (29 diagnostic txts + 3 zips + 1 .bak = 33 files, ~420 KB). Lowest-
   risk, no code impact, fully reversible via git. Proposed command above.
2. **Approve Tranche 2 moves** (prototype/ + docx). Cosmetic relocations, no content changes.
3. **Fix react-day-picker CONFIG-DRIFT** (npm uninstall, 5-minute task). Run verification gates.
4. **Operator intent check on backend/examples/ and backend/devtools/** stub dirs. If planned
   namespace packages, leave. If forgotten stubs, clean up in same commit as Tranche 1.
5. **Schedule ARCHITECTURE.md rewrite** (estimated 1-2h per decisions/2026-05-22). Highest-
   leverage remaining doc item — actively misleads until rewritten.
6. **Cross-check docs/TF_RESPONSIBILITY_FLOW.txt** against current orchestrator.py before next
   pass. If accurate: keep as active reference. If drifted: flag for rewrite.
7. Re-run repo-janitor after Tranche 1 + 2 land to detect cascade orphans.
   (Per janitor protocol: re-run after any tranche is actioned.)

Note: manifest candidate count is ~47 items. The engineering:tech-debt skill is recommended
for prioritization when the manifest exceeds ~50 candidates — we're just under that threshold,
but if the ARCHITECTURE.md rewrite surfaces additional clutter, invoke it next pass.
