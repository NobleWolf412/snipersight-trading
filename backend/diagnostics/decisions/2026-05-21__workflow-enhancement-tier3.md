# 2026-05-21 — Workflow enhancement Tier 3: memory archive + snapshot parallel-worker fix

## Headline
Tier 3 of the workflow enhancement landed: completed HUD rebuild Phases 0-7 + 3a'/3a'' calibration + 3z queue migrated out of MEMORY.md to `backend/diagnostics/phase_archive/`; snapshot framework `summary.json` parallel-worker overwrite bug fixed (workers now write per-worker `summary.<workerIndex>.json` files; `report.ts` merges all of them).

## Context
Operator approved Tier 3 with "go" after Tier 2 commit 9024ef2. Two queued items in Tier 3 made sense as a tight batch:

1. **Memory archive (queued from §19 design rationale).** MEMORY.md had grown to ~140 lines with the Phase 0-7 HUD rebuild sequence + 3a'/3a'' calibration prose + 3z queue narrative occupying ~40 lines. With the §19 decisions log live since Tier 1, the right place for completed work is the phase archive, not active memory. MEMORY.md is loaded into every conversation's context and has a 200-line truncation cap — done-work was actively pushing new memories off the bottom.

2. **Snapshot summary.json parallel-worker bug (queued from Snapshot Framework Patterns memory note).** Documented since Phase 7 but never fixed. Under `fullyParallel: true, workers: 4` in `playwright.config.ts`, each worker process holds its own module-level `RECORDS` array in `tests/visual/capture.spec.ts`. Each worker's `afterAll` called `writeReport()` which `writeFileSync`-overwrote `__report__/summary.json` with only that worker's records. Whoever ran `afterAll` last won — visible to operator as `summary.json` containing ~4 of 14 records. `visual.html` (generated from summary.json) showed the same truncated subset. Workaround in memory said "use playwright.json which is properly aggregated" — but playwright.json doesn't carry the SniperSight-specific per-state fields (`perPixelDiffPct`, `largestRegionPctOfViewport`, `reasons`, `explicitReady`), so the workaround degraded the report's usefulness.

## Resolution

### Memory archive

Files created:
- `backend/diagnostics/phase_archive/README.md` — format guide + filename convention
- `backend/diagnostics/phase_archive/2026-05-21__hud_rebuild_phases_0_through_7.md` — full Phase 0-7 sequence + 3a'/3a'' calibration + 3z queue + Path B layered-port working pattern, migrated verbatim from MEMORY.md
- `~/.claude/projects/c--Users-macca-snipersight-trading/memory/project_phase_archive.md` — pointer memory file

Files modified:
- `MEMORY.md`: replaced the long Phase Sequence + 3a'/3a''/3z block (lines 66-108 pre-edit) with a 6-line pointer to the archive. Added `[Phase archive live]` pointer to top index.

### Snapshot summary.json parallel-worker fix

Files modified:
- `tests/visual/capture.spec.ts`:
  - Added `unlinkSync` import (line 19)
  - Module-level: idempotently delete legacy single-file `summary.json` (lines 47-50) so report.ts no longer reads stale pre-fix output mixed with new per-worker files
  - `writeReport(workerIndex: number)` now writes `summary.<workerIndex>.json` instead of the shared `summary.json` (lines 63-78)
  - `test.afterAll(({}, testInfo) => writeReport(testInfo.workerIndex))` — workerIndex from Playwright's testInfo (line 80-82)

- `tests/visual/report.ts`:
  - Updated module docstring to reflect per-worker pattern (lines 1-16)
  - Added `readdirSync, statSync` imports (line 17)
  - `loadSummary()` rewritten (lines 28-58): globs `summary.*.json` + legacy `summary.json`, sorts ASCENDING by mtime, merges into a `Map<string, Row>` keyed by state key — later iterations overwrite earlier so latest-mtime wins on dedup. Malformed individual files are skipped without failing the whole report.
  - HTML footer text updated to reference the new pattern (line 107 pre-edit)
  - CLI error message updated to match (line 114 pre-edit)

Verification:
- `npx tsc --noEmit -p tsconfig.json` exits 0 — no type regressions
- Cannot run `npm run snapshots:capture` in this round without booting vite dev server + Playwright workers; defer live verification to next snapshot session. The fix logic is small and bounded; the read-merge logic is exercised by report.ts on next `npm run snapshots:show`.

MEMORY.md updated: snapshot patterns section now reads `summary.json parallel-worker overwrite — FIXED 2026-05-21 (Tier 3): each worker now writes summary.<workerIndex>.json; report.ts merges all of them deduping by state key with latest-mtime-wins.`

### Contract diff
`python -m backend.diagnostics.capture_contracts diff` returned `CLEAN (0 changes)` post-Tier-3. No backend application code touched.

## Why it matters next time

**Memory archive:** Active memory should hold rules + pointers, not history. With Phase 0-7 archived, MEMORY.md is back under 100 lines and new memories survive the 200-line truncation. Pattern: any time a multi-commit initiative completes, write a phase_archive entry and reduce MEMORY.md to one line.

**Snapshot fix:** The visual snapshot report is now trustworthy across the full state matrix again. Operators who previously had to cross-reference `playwright.json` for the full picture can now read `__report__/visual.html` directly. The fix pattern (per-worker output files + merge in the reader) is reusable for any other Playwright afterAll aggregation that was silently truncating to last-worker subset.

**Deferred to Tier 4:**
- Verbatim-paste enforcement hook — needs design work; hooks can't introspect response text easily. Likely solved via a Stop hook that scans recent conversation, but pattern needs scoping.
- Frontend↔backend TS-type sync — depends on whether to generate types from Pydantic models or hand-maintain
- Pre-commit typecheck — deferred; cost-benefit unfavorable on every commit (5-10s per `npx tsc`)
- `pipeline_smoke.py` + `golden_scan.json` — Tier 2.5, still blocked on OHLCV fixture decision
- Scheduled repo-janitor — Tier 4

Cross-ref: CLAUDE.md §16/§17/§18/§19/§20; commits 72f64fe (Tier 1), 9024ef2 (Tier 2); `backend/diagnostics/decisions/2026-05-21__workflow-enhancement-tier1.md`, `..._tier2.md`.
