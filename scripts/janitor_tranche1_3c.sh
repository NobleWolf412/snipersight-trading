#!/usr/bin/env bash
# janitor_tranche1_3c.sh — SniperSight repo cleanup, Tranche 1 + 3C + root tests
# Generated 2026-05-07 by repo-janitor agent
#
# Run from repo root in Git Bash (or WSL) on Windows.
# This script does NOT commit. Review with `git status` before committing.
#
# WHAT THIS DELETES
#   Tranche 1 (untracked, gitignored — disk-only):
#     - all __pycache__/ dirs in main tree (NOT inside .claude/worktrees/)
#     - .pytest_cache/
#     - debug-587019.log (78MB)
#
#   Tranche 3C (tracked — git rm, recoverable from history):
#     - 47 debug-output files (act/activity/status/diag/fvg/ob/sweep/cycle_reversal/
#       indicator/smc_service diagnostics + tmp_* + output.txt + typescript-errors.txt)
#     - test_data.csv, paper_trading.db (0B), telemetry.db (0B)
#     - theme.json (2B), spark.meta.json, .spark-initial-sha
#
#   Stale root test scripts (tracked — git rm):
#     - 11 test_*.py files at repo root (single-batch Mar 22, all stale debug scratch)
#
# WHAT THIS DOES NOT TOUCH (deliberately)
#   .live_trading/                                          # off-limits
#   .claude/worktrees/priceless-wing/  (claude/hud-rebuild) # active UI refactor
#   .claude/worktrees/<all others>                          # assume active until told otherwise
#   .coverage                                               # off-limits
#   logs/confluence_breakdown.log                           # used by rebuild Phase 1c
#   dist/                                                   # active frontend rebuild
#   tailwind.config.js, postcss.config.js, components.json  # rebuild Phase 2 owns these
#   src/lib/utils.ts                                        # rebuild Phase 2 owns this
#   confluence_diagnostic.py, sweep_diagnostic.py,
#     fetch_diagnostics.py, get_diagnostics.py              # canonical iterate-loop tools
#
# USAGE
#   bash scripts/janitor_tranche1_3c.sh --dry-run   # preview only, modifies nothing
#   bash scripts/janitor_tranche1_3c.sh             # execute (still does NOT commit)

set -euo pipefail

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN=1
    echo "=== DRY RUN MODE — no files will be modified ==="
    echo ""
fi

run() {
    if [ "$DRY_RUN" = "1" ]; then
        echo "WOULD: $*"
    else
        eval "$*"
    fi
}

# Sanity: must be at repo root
if [ ! -f CLAUDE.md ] || [ ! -f package.json ]; then
    echo "ERROR: must be run from repo root (CLAUDE.md and package.json expected)" >&2
    exit 1
fi

# Sanity: priceless-wing worktree must NOT be touched
if [ ! -d .claude/worktrees/priceless-wing ]; then
    echo "WARN: .claude/worktrees/priceless-wing not found — proceeding anyway, but verify nothing about your active rebuild has moved." >&2
fi

# Sanity: index lock check
if [ -f .git/index.lock ]; then
    echo "ERROR: .git/index.lock exists — another git process is active. Close it before running this script." >&2
    exit 1
fi

echo "=== TRANCHE 1: Caches and untracked detritus (disk-only) ==="

# __pycache__ in main tree only (NOT inside .claude/worktrees/)
PYCACHE_BEFORE=$(find backend tests src -type d -name __pycache__ 2>/dev/null | wc -l | tr -d ' ')
echo "main-tree __pycache__ dirs before: $PYCACHE_BEFORE"
run "find backend tests src -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true"
if [ "$DRY_RUN" = "0" ]; then
    PYCACHE_AFTER=$(find backend tests src -type d -name __pycache__ 2>/dev/null | wc -l | tr -d ' ')
    echo "main-tree __pycache__ dirs after:  $PYCACHE_AFTER"
fi

echo "Removing .pytest_cache/..."
run "rm -rf .pytest_cache"

echo "Removing debug-587019.log..."
run "rm -f debug-587019.log"

echo ""
echo "=== TRANCHE 3C: 47 tracked debug-output files (git rm) ==="

DEBUG_FILES=(
    act.json
    activity.json activity2.json activity3.json activity4.json
    status.json status2.json
    diag.json diag.txt diag_now.json
    tmp_git_recent.txt tmp_status.json
    typescript-errors.txt
    output.txt output_utf8.txt
    fvg_diag_1d.txt fvg_diag_1h.txt fvg_diag_1m.txt fvg_diag_1w.txt
    fvg_diag_4h.txt fvg_diag_5m.txt
    fvg_diag_doge.txt fvg_diag_eth.txt fvg_diag_sol.txt
    fvg_diagnostic_gaps.csv fvg_diagnostic_report.txt
    ob_diag_15m.txt ob_diag_15m_final.txt ob_diag_15m_final2.txt
    ob_diag_1d.txt ob_diag_1h.txt ob_diag_1m.txt ob_diag_1w.txt
    ob_diag_4h.txt ob_diag_5m.txt
    ob_diagnostic_blocks.csv
    sweep_diag_15m.txt sweep_diag_all.txt sweep_diagnostic_report.txt
    cycle_reversal_diagnostic_report.txt
    cycle_reversal_diagnostic_report.utf8.txt
    cycle_reversal_rolling.csv
    indicator_diagnostic_report.txt
    smc_service_diagnostic_report.txt
    test_data.csv
    paper_trading.db
    telemetry.db
    theme.json
    spark.meta.json
    .spark-initial-sha
)

DELETED=0
SKIPPED=0
for f in "${DEBUG_FILES[@]}"; do
    if [ -e "$f" ]; then
        run "git rm --quiet -- \"$f\""
        DELETED=$((DELETED + 1))
    else
        SKIPPED=$((SKIPPED + 1))
    fi
done
echo "3C summary: $DELETED staged for deletion, $SKIPPED already absent"

echo ""
echo "=== ROOT TESTS: 11 stale debug scripts (git rm) ==="

ROOT_TESTS=(
    test_daterange.py
    test_overwatch.py
    test_pair_selection.py
    test_parallel.py
    test_phemex.py
    test_phemex_limit.py
    test_price.py
    test_relative.py
    test_score_breakdown.py
    test_stacktrace.py
    test_weight_bug.py
)

DELETED_T=0
SKIPPED_T=0
for f in "${ROOT_TESTS[@]}"; do
    if [ -e "$f" ]; then
        run "git rm --quiet -- \"$f\""
        DELETED_T=$((DELETED_T + 1))
    else
        SKIPPED_T=$((SKIPPED_T + 1))
    fi
done
echo "Root-test summary: $DELETED_T staged for deletion, $SKIPPED_T already absent"

echo ""
echo "=== DONE ==="
if [ "$DRY_RUN" = "1" ]; then
    echo "Dry run complete. Re-run without --dry-run to execute."
else
    echo "Cleanup applied. NOTHING is committed yet."
    echo ""
    echo "Review:"
    echo "  git status"
    echo "  git diff --cached --stat"
    echo ""
    echo "If satisfied:"
    echo "  git commit -m 'chore(janitor): Tranche 1 + 3C + root-test cleanup'"
    echo ""
    echo "If anything looks wrong:"
    echo "  git reset HEAD"
    echo "  git checkout ."
fi
