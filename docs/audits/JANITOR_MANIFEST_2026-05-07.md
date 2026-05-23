# Repo-Janitor Inventory — 2026-05-07

**Scope:** Repo root + `backend/` + `tests/` + `docs/`
**Off-limits respected:** yes (`.live_trading/`, `.coverage`, `.git/`, `.github/`, `.cursor/`, `.storybook/`, `.claude/`, `LICENSE`, `CLAUDE.md`, Dockerfiles, the four canonical root diagnostics)
**Note on `.claude/worktrees/priceless-wing/`:** Treated as off-limits — full sibling tree, assumed active. Confirm before any cleanup applies there.

## Headline Numbers

| Tranche | Risk | Count | Disk impact |
|---------|------|-------|-------------|
| 1 — gitignored detritus (delete on disk) | Zero | ~720 dirs + 1 huge log | **~80MB+** |
| 2 — historical doc moves (archive only) | Low | 7 files | Cosmetic |
| 3 — orphan tests / dead-tracked artifacts (quarantine) | Medium | 11 root tests + 47 root debug-output files + 4 recon-referencing tests | Significant |
| 4 — review-only (rewrite or decide) | Manual | 8 stale-current docs + 7 helper scripts + a few configs | High value |

---

## TRANCHE 1 — Build artifacts / caches / unstaged logs (zero-risk delete)

All of these are matched by `.gitignore` and **not tracked**. Deletion is on-disk only — no git operation needed, no history affected. Recoverable on next build/run.

```
[BUILD-CACHE]    ./backend/**/__pycache__       28 dirs in main tree (excluding worktrees)
[BUILD-CACHE]    ./.pytest_cache/                tracked-by .gitignore, safe
[BUILD-CACHE]    ./dist/                          frontend build output, regeneratable
[LOG-ARTIFACT]   ./debug-587019.log               78,768,075 bytes — 78MB single file, not tracked
[LOG-ARTIFACT]   ./logs/confluence_breakdown.log  0 bytes — empty stub
[BUILD-CACHE]    ./node_modules/                  not tracked, npm install regenerates (only delete if doing fresh install)
```

**`.coverage` (94KB) at root** — explicitly off-limits per agent rules and per `.gitignore`. Not in this manifest.
**`.live_trading/`** — off-limits. Not in this manifest.

**Proposed Tranche 1 command (DO NOT RUN until you approve):**

```bash
# Caches and pytest cache (off-disk only, not tracked)
find . -type d -name __pycache__ \
  -not -path "./.git/*" \
  -not -path "./.claude/*" \
  -not -path "./.live_trading/*" \
  -not -path "./node_modules/*" \
  -exec rm -rf {} + 2>/dev/null

rm -rf .pytest_cache

# The 78MB log file
rm -f debug-587019.log

# Dist/ (will rebuild on next vite/npm build)
rm -rf dist
```

**Stop short of `node_modules` removal** unless you're doing a fresh `npm install` anyway — it's slow to rebuild.

---

## TRANCHE 2 — Documentation archive moves (low risk, high signal)

These are **HISTORICAL** — point-in-time audit/session reports. Per your decision: archive, never delete. Move to `docs/archive/` with date prefix. Content unchanged.

```
[DOC-HISTORICAL] ./CONFLUENCE_REJECTION_REPORT.md  -> docs/archive/2026-03-22-CONFLUENCE_REJECTION_REPORT.md
  Evidence: dated body, threshold table superseded by current scanner_modes.py

[DOC-HISTORICAL] ./SNIPERSIGHT_DEBUG_REPORT.md     -> docs/archive/2026-03-21-SNIPERSIGHT_DEBUG_REPORT.md
  Evidence: overnight audit dated 2026-03-21, lists bugs since partially addressed

[DOC-HISTORICAL] ./FIXES_APPLIED.md                -> docs/archive/2026-03-22-FIXES_APPLIED.md
  Evidence: session log with session ID b23bf405, 2026-03-22

[DOC-HISTORICAL] ./DEAD_CODE_REPORT.md             -> docs/archive/2026-03-22-DEAD_CODE_REPORT.md
  Evidence: 2026-03-22 audit; this manifest supersedes

[DOC-HISTORICAL] ./SMC_ENGINE_REPORT.md            -> docs/archive/2026-03-22-SMC_ENGINE_REPORT.md
  Evidence: 2026-03-22 dated, single-snapshot report

[DOC-HISTORICAL] ./PHEMEX_INTEGRATION_DEBUG_REPORT.md -> docs/archive/2026-05-04-PHEMEX_INTEGRATION_DEBUG_REPORT.md
  Evidence: dated debug report; superseded by PHEMEX_AUDIT_REPORT_V2 (2026-05-05)

[DOC-HISTORICAL] ./BOT_UI_AUDIT.md                 -> docs/archive/2026-05-05-BOT_UI_AUDIT.md
  Evidence: audit dated 2026-05-05 — keep at root if you treat it as active rolling, otherwise archive
```

**Important downstream:** After this move, `CLAUDE.md` §14 references and the two existing agent files (`symmetry-guard.md`, `rejection-forensics.md`) need their bare-filename references updated to `docs/archive/<dated>.md`. I'll batch those as a single follow-up edit.

**Active (KEEP at root or move to `docs/audits/`):**
- `PHEMEX_AUDIT_REPORT_V2.md` (2026-05-05) — newest Phemex audit, treat as active
- `HOW_TO_GET_CONFLUENCE_BREAKDOWN.md` (2026-03-22) — runbook, content static, **propose move to `docs/runbooks/`** but content stays

---

## TRANCHE 3 — Quarantine candidates (one-week soak before delete)

### 3A — Orphan tests referencing removed modes (`recon`/`ghost`)

CLAUDE.md §10 states only four modes exist. These tests reference `recon`:

```
[ORPHAN-TEST]    tests/test_backend.py
  Line 16: sniper_mode="recon"
  Verdict: tests a removed mode — quarantine

[ORPHAN-TEST]    tests/test_orchestrator_imports.py
  Line 18: profile="recon"
  Verdict: same — quarantine

[ORPHAN-TEST]    tests/test_reversal_all_modes.py
  Line 9: docstring lists "Recon" as a mode under test
  Verdict: stale spec — quarantine until rewritten

[NOTE]           backend/tests/integration/test_orchestrator_workflow.py.skip
  Already has .skip extension — already disabled. Confirm intent: archive or delete.
```

### 3B — Tracked test scripts at repo root (belong in `tests/`)

All 11 are git-tracked. Move to `tests/` (or quarantine if they reference removed code paths). Per your policy: quarantine first, soak, then delete or move-to-tests.

```
[ORPHAN-TEST?]   ./test_daterange.py
[ORPHAN-TEST?]   ./test_overwatch.py
[ORPHAN-TEST?]   ./test_pair_selection.py
[ORPHAN-TEST?]   ./test_parallel.py
[ORPHAN-TEST?]   ./test_phemex.py
[ORPHAN-TEST?]   ./test_phemex_limit.py
[ORPHAN-TEST?]   ./test_price.py
[ORPHAN-TEST?]   ./test_relative.py
[ORPHAN-TEST?]   ./test_score_breakdown.py
[ORPHAN-TEST?]   ./test_stacktrace.py
[ORPHAN-TEST?]   ./test_weight_bug.py
```

These are SUSPECT until you tell me whether they're scratch debug or actual unit tests that just landed in the wrong dir. If they're scratch, quarantine then delete. If real, `git mv` to `tests/` and update any pytest config.

### 3C — Tracked debug-output dumps at repo root (47 files)

All git-tracked. All Mar 22 22:45 (single-batch commit). Output captures from a debugging session. Definitely not source code; question is whether you want them as historical artifacts or gone.

```
[DEBUG-OUTPUT]   ./act.json                        0 bytes (empty)
[DEBUG-OUTPUT]   ./activity.json, activity2.json, activity3.json, activity4.json
[DEBUG-OUTPUT]   ./status.json, status2.json
[DEBUG-OUTPUT]   ./diag.json, diag.txt, diag_now.json
[DEBUG-OUTPUT]   ./tmp_git_recent.txt, tmp_status.json
[DEBUG-OUTPUT]   ./typescript-errors.txt
[DEBUG-OUTPUT]   ./output.txt, output_utf8.txt
[DEBUG-OUTPUT]   ./fvg_diag_{1d,1h,1m,1w,4h,5m,doge,eth,sol}.txt   (9 files)
[DEBUG-OUTPUT]   ./fvg_diagnostic_gaps.csv, fvg_diagnostic_report.txt
[DEBUG-OUTPUT]   ./ob_diag_{15m,15m_final,15m_final2,1d,1h,1m,1w,4h,5m}.txt   (9 files, note "_final" then "_final2")
[DEBUG-OUTPUT]   ./ob_diagnostic_blocks.csv
[DEBUG-OUTPUT]   ./sweep_diag_15m.txt, sweep_diag_all.txt, sweep_diagnostic_report.txt
[DEBUG-OUTPUT]   ./cycle_reversal_diagnostic_report.txt, .utf8.txt (dupe), cycle_reversal_rolling.csv
[DEBUG-OUTPUT]   ./indicator_diagnostic_report.txt, smc_service_diagnostic_report.txt
[DEBUG-OUTPUT]   ./test_data.csv (root-level data file)
[DEBUG-OUTPUT]   ./paper_trading.db (0 bytes), telemetry.db (0 bytes), theme.json (2 bytes)
[DEBUG-OUTPUT]   ./spark.meta.json, .spark-initial-sha
```

**Recommended action: `git mv` the keepers to `docs/audits/2026-03-22-debug-captures/` and `git rm` the rest.** Two-signal evidence: (a) all single-batch Mar 22, (b) zero subsequent edits — they're abandoned scratch.

**The `_final` then `_final2` pair is a tell:** that's classic "I'll clean this up later" workflow. Six weeks later — this is later.

---

## TRANCHE 4 — Review-only (do not auto-action)

### 4A — Stale-current docs (require rewrite, not move)

These purport to describe current state and are 6+ weeks behind code. **Do not archive — that's lying about their status. Schedule rewrite.**

```
[DOC-STALE-CURRENT] ./ARCHITECTURE.md          64KB, Mar 22 22:45
  Drift risk: high — predates May refactors, almost certainly references old mode list / pipeline

[DOC-STALE-CURRENT] ./README.md                Mar 22 22:45
  Drift risk: high — entry-point doc, must match current setup

[DOC-STALE-CURRENT] ./PRD.md                   Mar 22 22:45
  Drift risk: medium — product-level, may still hold

[DOC-STALE-CURRENT] ./PROJECT_STRUCTURE.md     27KB, Mar 22 22:45
  Drift risk: very high — describes file layout that this manifest is about to change

[DOC-STALE-CURRENT] ./QUICKSTART.md            Mar 22 22:45
  Drift risk: high — onboarding path

[DOC-STALE-CURRENT] ./SETUP_INSTRUCTIONS.md    Mar 22 22:45
  Drift risk: high — overlap with QUICKSTART, possible consolidation candidate

[DOC-STALE-CURRENT] ./SECURITY.md              Mar 22 22:45
  Drift risk: medium — review for accuracy

[DOC-STALE-CURRENT] ./HOW_TO_GET_CONFLUENCE_BREAKDOWN.md  Mar 22 22:45
  Drift risk: low (runbook content stable) — propose move to docs/runbooks/
```

**Recommended approach for 4A:** invoke `engineering:documentation` skill once per file, regenerate against verified current code surface. `PROJECT_STRUCTURE.md` should be regenerated *last*, after structural reorg lands.

### 4B — Root-level helper scripts (review for relevance)

All git-tracked. None of these are in the canonical-diagnostic list (CLAUDE.md §12). Likely one-shot dev helpers from March that may or may not still work.

```
[SUSPECT]  ./analyze_weights.py              1083 bytes, Mar 22 22:45
[SUSPECT]  ./check.py                        355 bytes, Mar 22 22:45
[SUSPECT]  ./check_activity.py               191 bytes, Mar 22 22:45
[SUSPECT]  ./check_scan.py                   353 bytes, Mar 22 22:45
[SUSPECT]  ./check_sig_filter.py             313 bytes, Mar 22 22:45
[SUSPECT]  ./debug_imports.py                669 bytes, Mar 22 22:45
[SUSPECT]  ./normalize_all_weights.py        3506 bytes, Mar 22 22:45
```

These are all small, all same-batch, all named like throwaway. **Recommend:** read each in 2 minutes, decide keep / quarantine. If keeping, move to `scripts/dev/` or fold into `backend/diagnostics/`.

### 4C — Configuration / lockfile drift

```
[CONFIG-REVIEW] ./.flake8                       Confirm not duplicated by [tool.flake8] in pyproject (no pyproject.toml found at root — verify)
[CONFIG-REVIEW] ./status.json + status2.json    Two near-identical names — keep one or delete both
[CONFIG-REVIEW] ./Procfile                      Heroku-style — confirm still relevant to your deployment story
[CONFIG-REVIEW] ./.spark-initial-sha            Spark/scaffolding artifact — likely safe to delete if not building from a Spark template anymore
[CONFIG-REVIEW] ./spark.meta.json               Same as above
[CONFIG-REVIEW] ./.swcrc                        SWC config (2 bytes) — likely empty/unused
[CONFIG-REVIEW] ./theme.json                    2 bytes, root level — duplicate of frontend theme?
[CONFIG-REVIEW] ./archive/files.zip + files (2).zip + snipersight-chart-fixes.zip
                                                Zip files at repo root in archive/ — almost certainly old. Read once, decide.
```

---

## Off-limits items observed (FYI only — NOT proposed for action)

- `.live_trading/` — runtime data, untouched per your directive
- `.coverage` (file) — coverage report, off-limits
- `.git/`, `.github/`, `.cursor/`, `.storybook/` — tooling
- `.claude/agents/` — the three agents we just shipped
- `.claude/worktrees/priceless-wing/` — full sibling repo tree, assumed active
- `LICENSE`, `Dockerfile.backend`, `Dockerfile.frontend`, `.dockerignore` — never touch
- Root-level canonical diagnostics: `confluence_diagnostic.py`, `sweep_diagnostic.py`, `fetch_diagnostics.py`, `get_diagnostics.py` — iterate-loop tools per CLAUDE.md §12
- `logs/live_trading/`, `logs/paper_trading/` — runtime data; **flagged for awareness** because of name overlap with `.live_trading/`. Confirm before touching.

---

## Recommended Execution Order

1. **Tranche 1 first.** Zero risk. Frees ~80MB. Run, then re-run janitor against the cleaned tree to surface anything that was previously hidden.
2. **Tranche 3B (root tests)** next — highest signal-to-noise. You either move them or delete; either way, root gets cleaner immediately.
3. **Tranche 3A (recon-referencing tests)** — quick edit-or-remove decision per test.
4. **Tranche 3C (debug-output dumps)** — bulk decision: archive-or-purge as a group, since they're all from the same March 22 session.
5. **Tranche 2 (doc archive moves)** — paired with the CLAUDE.md / agent file reference updates as a single PR.
6. **Tranche 4A (stale-current rewrites)** — `engineering:documentation` skill, one doc at a time, against verified current code. `PROJECT_STRUCTURE.md` last, after structural reorg.
7. **Tranche 4B/4C** — manual review pass at your pace.

## What This Manifest Does NOT Cover

- **Pass 4 — true dead Python inside `backend/`.** Not run yet. The `find` calls timed out earlier; running it scoped to `backend/` only is the next step.
- **Frontend dead code in `src/`.** Same reason. Needs a TypeScript-aware unused-export pass.
- **Lockfile vs. manifest drift on `package-lock.json` (389KB) and Python deps.** Out of scope for first pass; flag-only candidate.

These should run on the second janitor pass after Tranche 1 reduces the noise floor.
