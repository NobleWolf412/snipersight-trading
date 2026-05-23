# REPO-JANITOR INVENTORY — 2026-05-20

**Status:** Reviewed by operator, no tranches actioned this session.

**Operator decisions:**
- **PRD.md:** move to `archive/reports/PRD.md` when Tranche 1 runs (not deleted outright; dangling refs from README/QUICKSTART/ARCHITECTURE remain until those docs are rewritten).
- **Tranches 1/2/3:** skipped this session — pending later approval.
- **Follow-ups tracked:** documentation rewrite (README/ARCHITECTURE/QUICKSTART/PROJECT_STRUCTURE) and `package.json` orphan-dependency eject. Both noted in MEMORY.md.

---

## Short Summary

| Tranche | Count | Disk impact | Risk |
|---|---|---|---|
| 1. CONFIRM DELETE — operator's already-queued tree | 89 root files | ~25 MB on disk (most empty/tiny) | None — all mirrored elsewhere |
| 2. NEW DELETE — additional clutter | ~9 items + 697 `__pycache__` dirs | ~3-22 MB | Zero (caches/builds) to low |
| 3. MOVE — relocate to canonical homes | 4 directories | Cosmetic | Low |
| 4. KEEP, DOCUMENT — load-bearing, not orphan | 12 items | n/a | Critical — do NOT delete next pass |
| 5. STALE BUT HISTORICAL — preserve for record | 12 docs | ~150 KB | Low (history loss if wrong) |
| 6. STALE-CURRENT — flag for rewrite (review-only) | 4 root docs | n/a | High value, manual decision |

**Headline findings:**

1. **The 80 queued root deletions are SAFE TO CONFIRM** — every script/diagnostic/log file is byte-identical to its mirror in `scripts/`, `diagnostics/`, or `archive/logs/` (verified via `diff` and presence check). The operator already did a re-org; this just finishes the move by removing the source-location duplicates. **One exception**: `PRD.md` has no replacement — see CONFIRM DELETE notes.
2. **Major hidden orphan: ~30 frontend dependencies** in `package.json` (`@radix-ui/*`, `cmdk`, `vaul`, `class-variance-authority`, `cva`, `input-otp`, `embla-carousel-react`, `react-day-picker`, `react-hook-form`, `react-resizable-panels`, `recharts`, `sonner`, `clsx`, `tailwind-merge`) are ONLY referenced from `src/_archive/`. The active app uses zero Radix and zero Tailwind. Phase 7 eject completed in code but never propagated to `package.json`.
3. **Documentation drift is severe and deceptive.** `README.md` calls this repo "a documentation viewer." `ARCHITECTURE.md`, `PROJECT_STRUCTURE.md`, `QUICKSTART.md` all reference legacy "Recon Mode" (removed per CLAUDE.md §4 + §10) and the deleted `PRD.md`. These actively mislead.
4. **Root-level `tests/` directory contains legacy tests** using `sniper_mode="recon"` (removed mode). Mixed with the active visual-snapshot framework in `tests/visual/` — needs surgical separation, not bulk action.
5. **`.coverage` and `.live_trading/` were touched only to verify presence** — both off-limits per agent rules and respected.
6. **3 worktrees** exist (`.claude/worktrees/{angry-kapitsa, beautiful-williamson, priceless-wing}` + duplicate `.claire/worktrees/priceless-wing`). Per scope rules, listed but not walked.

---

## Structured Detail

### TRANCHE 1 — CONFIRM DELETE (operator's already-queued deletions)

All 89 queued deletions are safe: scripts moved to `scripts/`, diagnostic dumps moved to `diagnostics/`, reports moved to `archive/reports/`, logs/snapshots moved to `archive/logs/`. Spot-checked byte-identical via `diff <(git show :path) archive_or_scripts/path` — zero differences.

| File | Reason code | Confirmation |
|---|---|---|
| `analyze_weights.py`, `check.py`, `check_activity.py`, `check_scan.py`, `check_sig_filter.py`, `confluence_diagnostic.py`, `debug_imports.py`, `fetch_diagnostics.py`, `get_diagnostics.py`, `normalize_all_weights.py`, `run_bot_test.py`, `sweep_diagnostic.py` | `superseded-by:scripts/<same-name>` | duplicate exists, byte-identical (3 sampled) |
| `test_daterange.py`, `test_overwatch.py`, `test_pair_selection.py`, `test_parallel.py`, `test_phemex.py`, `test_phemex_limit.py`, `test_price.py`, `test_relative.py`, `test_score_breakdown.py`, `test_stacktrace.py`, `test_weight_bug.py` | `superseded-by:scripts/<same-name>` | duplicate exists |
| All `fvg_diag_*.txt` (9), `ob_diag_*.txt` (10), `sweep_diag_*.txt` (2), `cycle_reversal_diagnostic_report.*.txt` (2), `indicator_diagnostic_report.txt`, `output.txt`, `reversal_diagnostic_report.txt`, `smc_service_diagnostic_report.txt`, `fvg_diagnostic_report.txt`, `sweep_diagnostic_report.txt`, `diag.txt` | `superseded-by:diagnostics/<same-name>` | duplicate exists |
| `ARCHIVE.md`, `CONFLUENCE_REJECTION_REPORT.md`, `DEAD_CODE_REPORT.md`, `FIXES_APPLIED.md`, `HOW_TO_GET_CONFLUENCE_BREAKDOWN.md`, `SMC_ENGINE_REPORT.md`, `SNIPERSIGHT_DEBUG_REPORT.md` | `superseded-by:archive/reports/<same-name>` | duplicate exists, byte-identical (all 7) |
| `act.json`, `activity.json`, `activity2.json`, `activity3.json`, `activity4.json`, `diag.json`, `diag_now.json`, `output_utf8.txt`, `paper_trading.db`, `pr35_diff.patch`, `runtime.config.json`, `spark.meta.json`, `status.json`, `status2.json`, `telemetry.db`, `tmp_git_recent.txt`, `tmp_status.json`, `typescript-errors.txt`, `test_data.csv`, `cycle_reversal_rolling.csv`, `fvg_diagnostic_gaps.csv`, `ob_diagnostic_blocks.csv` | `superseded-by:archive/logs/<same-name>` | duplicate exists |
| `scripts/backtest_trades.csv` | `superseded-by:archive/logs/backtest_trades.csv` | duplicate exists |
| `.github/copilot-instructions.md`, `.github/copilot-instructions.md.backup` | `one-off-diagnostic` removed | No mirror, operator removed outright. Safe IF GitHub Copilot integration is no longer used (verify intent). |
| **`PRD.md`** | **NO REPLACEMENT, OPERATOR DECISION: move to `archive/reports/PRD.md`** | Referenced by `README.md:25`, `QUICKSTART.md:36`, `ARCHITECTURE.md` (multiple lines). Move preserves content; dangling refs remain until referrer docs are rewritten (Tranche 6 follow-up). |

**Verdict on Tranche 1:** Approve `git rm` for the 88 mirrored files. **`PRD.md` becomes `git mv PRD.md archive/reports/PRD.md`** per operator decision.

---

### TRANCHE 2 — NEW DELETE (clutter operator hasn't flagged)

| Item | Reason | Size | Notes |
|---|---|---|---|
| 697 `__pycache__/` dirs (28 in `backend/`, 669 inside `backend/venv/`) | `build-artifact` | ~tens of MB | Not tracked. Safe to `find . -name __pycache__ -exec rm -rf {} +` excluding `.claude/worktrees/` and `.git/`. |
| `.pytest_cache/` | `build-artifact` | 28 KB | Not tracked. Regenerable. |
| `dist/` (full directory) | `build-artifact` | 3.1 MB | Not tracked. Regenerable from `vite build`. |
| `logs/confluence_breakdown.log` | `log-output`, 0 bytes | 0 B | Empty stub; not referenced. Safe to delete. |
| `logs/paper_trading/` session dirs older than current | `log-output` | ~4.8 MB total | Cycle-output runtime artifacts. `analyze_session.py` (`scripts/analyze_session.py`) consumes them, so verify with operator which sessions are still needed for analysis before bulk-delete. Default action: `SUSPECT, review which sessions can be pruned`. |
| `logs/live_trading/` | `log-output` | ~14 MB | Live-trade journal output. **Off-limits per spirit of `.live_trading/` rule.** Flag only, do NOT propose deletion. |
| `archive/files.zip`, `archive/files (2).zip`, `archive/snipersight-chart-fixes.zip` | `unreferenced` | ~91 KB | Mar 17 2026, pre-rebuild artifacts. Not referenced anywhere. Candidate for delete OR `archive/_legacy/`. |
| `archive/logs/debug-587019.log` | `log-output`, 0 bytes | 0 B | Empty file. (Prior 78MB version already cleaned per old janitor manifest.) Safe to delete. |
| `archive/logs/act.json`, `archive/logs/activity.json`, `archive/logs/paper_trading.db`, `archive/logs/telemetry.db` | `log-output`, 0 bytes each | 0 B | Empty stubs that survived the move. Quarantine candidates. |
| `tests/visual/__pending__/` (if exists) | `build-artifact` | n/a | Per `.gitignore`. Not currently present. |

**Tranche 2 proposed commands (DO NOT RUN until approved):**

```bash
# Pure on-disk cleanup (no git involvement, none of these are tracked)
find . -type d -name __pycache__ \
  -not -path "./.git/*" \
  -not -path "./.claude/worktrees/*" \
  -not -path "./.claire/worktrees/*" \
  -not -path "./node_modules/*" \
  -not -path "./backend/venv/*" \
  -exec rm -rf {} +
rm -rf .pytest_cache dist
rm -f logs/confluence_breakdown.log
rm -f archive/logs/debug-587019.log archive/logs/act.json archive/logs/paper_trading.db archive/logs/telemetry.db

# Tracked files, git rm
git rm archive/files.zip "archive/files (2).zip" archive/snipersight-chart-fixes.zip
```

---

### TRANCHE 3 — MOVE (relocate to canonical homes)

| Item | Current location | Proposed | Reason |
|---|---|---|---|
| `prototype/` (1.1 MB of design-prototype HTML/JSX from May 7) | repo root | `archive/prototype/` OR `src/_archive/prototype/` | `superseded-by:src/components/hud/*`, prototype was source material for Phase 2-7 port; not imported by any active code. Phase 6 ARCHIVE.md is the related historical-record. |
| Pending stray test `backend/tests/unit/test_doge_regression_session_64cf1cea.py` | untracked but in canonical test dir | leave in place, `git add` it | Session-specific regression test for a real bug. Belongs in `backend/tests/unit/`. Note for operator: stage it, not delete. |
| `docs/Phemex API OHLCV Data Breakdown.docx` (6.2 MB binary) | `docs/` | `archive/docs/` or `docs/_history/` | Not referenced by any text file. Heavy binary cluttering docs/ which should be text-only architecture material. |
| `.claire/worktrees/priceless-wing` | `.claire/` (note: NOT `.claude/`) | suspect duplicate / leftover | The `.claire/` directory mirrors `.claude/worktrees/priceless-wing`. Listed as a single item per scope rules (don't walk). Likely a typo'd directory, confirm with operator whether `.claire/` is legitimate. |

---

### TRANCHE 4 — KEEP, DOCUMENT (load-bearing, looks orphan but isn't)

These are at risk of being deleted in a future pass. Document so next janitor knows.

| Item | Why it stays | Reference |
|---|---|---|
| `data/cooldowns.json` | Runtime state file written/read by `backend/engine/cooldown_manager.py` | imports detected |
| `runtime.config.json` (the one in `archive/logs/`) | Janitor flagged a potential ref from `symbol_classifier.py`. Verified: only hit was a log string `"runtime configuration"`, not a file reference. Safe. | verified 2026-05-20 |
| `.coverage` (root) | off-limits per agent rules | rules |
| `.live_trading/last_trade_sync.json` (33 bytes) | off-limits per agent rules, live-trading state | rules |
| `.dockerignore`, `Dockerfile.backend`, `Dockerfile.frontend`, `docker-compose.yml`, `Procfile` | active deployment configs; `Procfile` runs `npm run dev:frontend` + `uvicorn backend.api_server:app` | grep + file inspection |
| `requirements.txt`, `pyproject.toml`, `pyrightconfig.json`, `.pyre_configuration`, `.flake8`, `.swcrc`, `.gitattributes`, `.env.local.example` | active tooling configs | standard build setup |
| `.spark-initial-sha` (42 bytes) | Spark template provenance marker | static value |
| `backend/scripts/{test_indicator_validation.py, test_validation.py}` | NOT pytest-collected (`testpaths = ["backend/tests"]`), but may be referenced as standalone diagnostic. Keep until proven orphan. | `pyproject.toml` |
| `backend/diagnostics/*.py` | one-shot diagnostic scripts per CLAUDE.md §12, never propose deletion | CLAUDE.md §12 |
| `scripts/{analyze_session.py, backtest_*.py, run_backtest.py, fetch_historical_data.py, diagnostic_backtest.py, test_smc_detection.py, verify_tf_responsibility.py, start_dev.sh, kill_dev.sh, auto_sync.sh, safe_sync.sh, check-a11y.sh, run_backtest.sh, browser_notification_test.js}` | Pre-existing operational scripts (Mar 22). `analyze_session.py` reads `logs/paper_trading/`, keystone of the workflow loop per CLAUDE.md §12. | mtime + content |
| `scripts/janitor_tranche1_3c.sh` | Operator's own helper for executing the prior janitor's tranche-1; keep alongside the manifest history | filename pattern |
| `src/{ErrorFallback.tsx, version.ts, services/scanHistoryService.{test.ts,verify.js}}` | ErrorFallback used by `main.tsx`, version used by `useTelemetry`, `.test.ts` is the vitest suite (`test: "vitest run"`), `.verify.js`, **no found references; SUSPECT, single signal, do not delete without re-verification** | grep |

---

### TRANCHE 5 — STALE BUT HISTORICAL (preserve as record)

These are already correctly placed in `archive/reports/`, `archive/logs/`, or `diagnostics/`. **No move needed**, flagging so a future janitor doesn't treat them as fresh clutter.

| File | Classification | Reason |
|---|---|---|
| `archive/reports/ARCHIVE.md` | HISTORICAL | Phase 6 archive manifest, audit trail |
| `archive/reports/FIXES_APPLIED.md` | HISTORICAL | Per CLAUDE.md §10 / §14, referenced |
| `archive/reports/CONFLUENCE_REJECTION_REPORT.md` | HISTORICAL | Per CLAUDE.md §14, referenced |
| `archive/reports/SNIPERSIGHT_DEBUG_REPORT.md` | HISTORICAL | Per CLAUDE.md §14, referenced |
| `archive/reports/SMC_ENGINE_REPORT.md` | HISTORICAL | Engine state snapshot |
| `archive/reports/DEAD_CODE_REPORT.md` | HISTORICAL | Prior cleanup record |
| `archive/reports/HOW_TO_GET_CONFLUENCE_BREAKDOWN.md` | HISTORICAL | One-shot runbook from a debug session |
| `archive/reports/BOT_UI_AUDIT.md`, `PHEMEX_AUDIT_REPORT_V2.md`, `PHEMEX_INTEGRATION_DEBUG_REPORT.md`, `CONFLUENCE_AUDITOR_PROMPT.md` | HISTORICAL | Session-specific audit reports |
| `docs/audits/JANITOR_MANIFEST_2026-05-07.md` | HISTORICAL | Prior janitor inventory, keep |
| `.claude/autopsy-reports/*.md` (4 files) | HISTORICAL | Session autopsies, paste-friendly trade post-mortems. Already in `.claude/`. Keep. |
| `backend/diagnostics/audit_halts/` (referenced by CLAUDE.md §16, directory may not exist yet) | HISTORICAL when populated | per CLAUDE.md §16 spec |

---

### TRANCHE 6 — STALE-CURRENT (FLAG-FOR-REWRITE, review-only)

These purport to describe the **current** system but actively mislead. **DO NOT MOVE**, they need content rewrites.

| File | Drift detected | Recommendation |
|---|---|---|
| `README.md` (line 1-26+) | Calls repo "an architectural blueprint" and "interactive documentation viewer" (Spark template). References `PRD.md` which is queued for deletion. Self-describes as "type=documentation", repo is now a working trading system. | Rewrite. Engage `engineering:documentation` skill. |
| `ARCHITECTURE.md` (64 KB, 9+ "Recon Mode" references in lines 9, 16, 18, 387, 439, 560, 1196, 1305, 1380) | Describes legacy "Scanner Mode (Recon)" and "Recon UI", both removed per CLAUDE.md §4/§10 ("Only four scanner modes exist, do not reintroduce `recon` or `ghost`"). Doc claims 2 modes (Scanner+SniperBot); current system has 4 (OVERWATCH/STRIKE/SURGICAL/STEALTH). | Rewrite. Highest-priority drift, actively misleads new contributors. |
| `PROJECT_STRUCTURE.md` (27 KB) | Top-level layout describes pre-`backend/`-prefix tree (`contracts/` at root, `shared/` at root, etc.). Actual tree has `backend/contracts/`, `backend/shared/`. References `sniper_sight_cli.py` at root (doesn't exist; actual is `backend/cli.py`). | Rewrite. Path drift is mechanical. |
| `QUICKSTART.md` (12 KB) | Same "documentation viewer" framing as README. References deleted `PRD.md`. | Rewrite alongside README. |
| `SETUP_INSTRUCTIONS.md` (1 KB) | Generic Windows install-Git-Node-Python instructions; no SniperSight-specific content; says "automated installation failed" with no context. Possibly orphan. | Review, keep if `C:\start-sniper.bat` (CLAUDE.md §2) references it; otherwise candidate for deletion. |
| `SECURITY.md` | GitHub's stock `SECURITY.md` template ("Thanks for helping make GitHub safe..."), not actually SniperSight-specific. | Either rewrite or delete (LICENSE-adjacent boilerplate, low signal). |
| `docs/api_contract.md`, `docs/SMC_PIPELINE_REFACTOR.md`, `docs/TELEMETRY_GUIDE.md`, `docs/CYCLE_TRANSLATION_SYSTEM.md`, `docs/INTEGRATION_GUIDE.md`, `docs/TF_RESPONSIBILITY_FLOW.txt`, `docs/exchange_profiles.md`, `docs/indicator_validation.md`, `docs/WALLET_AUTHENTICATION.md`, `docs/sniper_ui_theme.md`, `docs/security.md`, `docs/API_ADDITIONS.md` | All mtime Mar 22 (older than CLAUDE.md May 19). Not cross-checked against current code surface. SUSPECT, possibly stale-current, possibly archival reference. | Review individually. `engineering:documentation` skill could verify drift per file. |

---

### Additional finding: package.json orphan dependencies (HIGH VALUE)

**Active src/ outside `_archive/` has ZERO imports of:** `@radix-ui/*` (all 30 packages), `class-variance-authority`, `clsx`, `cmdk`, `embla-carousel-react`, `input-otp`, `react-day-picker`, `react-hook-form`, `react-resizable-panels`, `recharts`, `sonner`, `tailwind-merge`, `vaul`, `@hookform/resolvers`.

Verified by `grep -rln @radix-ui src --include=*.tsx --include=*.ts | grep -v _archive` → **0 hits** (33 hits inside `_archive/` only).

Memory comment says "Intentionally retained orphan-but-not-Tailwind: class-variance-authority, cmdk, vaul (out of Phase 7 scope)", but they're equally orphan, just not Tailwind-coupled. Could be tackled as a Phase 7-followup.

**Off-limits items observed (NOT proposed for action):**
- `.live_trading/last_trade_sync.json`, live trading state, off-limits
- `.coverage` (root), off-limits
- `.git/`, `.github/`, `.storybook/`, `.cursor/`, off-limits
- `CLAUDE.md` (root), off-limits
- `LICENSE`, `Dockerfile.backend`, `Dockerfile.frontend`, `.dockerignore`, never propose moves
- `.claude/agents/*.md`, `.claude/skills/`, `.claude/launch.json`, `.claude/settings.local.json`, tooling
- `.claude/worktrees/{angry-kapitsa, beautiful-williamson, priceless-wing}`, 3 active worktrees; not walked
- `.claire/worktrees/priceless-wing`, possible duplicate worktree dir; flagged in Tranche 3 for clarification

---

## Recommended Next Steps

1. **Approve Tranche 1 as-is** with `PRD.md` moved (operator decision) instead of deleted.
2. **Run Tranche 2** (caches + empty stubs + zip blobs), zero risk.
3. **Tranche 3 moves**, prototype/ to archive/, docx to archive/docs/, resolve `.claire/` ambiguity.
4. **Tranche 6 (stale-current docs)** is the highest-leverage item remaining. Invoke `engineering:documentation` skill for the rewrite pass after Tranche 1 lands (so PRD.md is in its final home).
5. **Package.json dependency eject**, separate sub-step under "Phase 7 follow-up"; flagged here so it doesn't keep slipping.
6. **Stage `backend/tests/unit/test_doge_regression_session_64cf1cea.py`**, it's untracked but lives in the right dir and is a real regression test.
7. **Re-run repo-janitor after Tranche 1+2 land**, to detect cascade orphans.
