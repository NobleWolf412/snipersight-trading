# UI simplification audit, 2026-10-09

The follow-through is implemented in ten bounded commits, with the olive dark theme preserved. Current evidence is in the [ledger](UI_REFACTOR_2026-10-09.json), [development dashboard](UI_REFACTOR_2026-10-09.html), [baseline](UI_REFACTOR_2026-10-09_baseline.json), [current inventory](UI_REFACTOR_2026-10-09_inventory.json), [removal manifest](UI_REFACTOR_2026-10-09_removals.json), [unit results](UI_REFACTOR_2026-10-09_tests.json) and [browser fixtures](UI_REFACTOR_2026-10-09_browser.json).

The [foundation report](UI_REFACTOR_2026-10-09_foundation.md) and [foundation ledger](UI_REFACTOR_2026-10-09_foundation.json) preserve earlier claims and scoring. The supplied zero-score checkpoint was stale: foundation changes already existed in commit68ea669. New outcome claims reference committed implementation hashes, validated by the dashboard generator.

## Direction and scope

One primary task per screen. Keep olive surfaces, mono numbers and explicit PAPER/TESTNET/LIVE state. Rejection and attention causes stay visible; supporting ledgers and diagnostics may collapse. Unknown financial values remain unknown. Static examples are visibly examples. Development rewards stay in the offline dashboard, never in the trading product.

Read current architecture, PRODUCT.md, DESIGN.md, the audit rubric, implementation, callers and configuration owners. Browser evidence covers thirteen routes at320/390/768/1280px with intercepted data, fifteen session-state cases, expanded setup retests, all shared-dialog callers and keyboard switches. The earlier selected real-app review observed an existing paper session only. No session was started, stopped or reset; no orders or ML training actions ran. Backend execution, strategy and training code were unchanged by these UI commits.

## Findings

| ID | Priority | Result | Evidence or remaining action |
|---|---|---|---|
| A01 | P1 | Fixed | Native navigation dialog, inert background, current route and focus restore |
| A02 | P1 | Fixed | Gauntlet action uses the actual BrowserRouter route |
| A03 | P1 | Fixed | Named journal filters, focus and wrapping phone pagination |
| A04 | P1 | Fixed | Native shared dialog, six callers plus Replay help; nested StrictMode close, keyboard, scroll and restore checked |
| A05 | P1 truth | Fixed | Short landing, implemented claims and labeled static example; retired styling removed |
| A06 | P1 truth | Fixed | Live executor health explicitly scoped; paper status separate; failed/partial health and unknown counters visible |
| A07 | P2 | Fixed | Compact manual mode selector and Run Scan before optional inputs/filters; critical requirements visible |
| A08 | P2 | Partial | Shared controls, dialogs, journal sort and setup switches improved; full state/control matrix still open |
| A09 | P2 | Partial | One canonical palette; quieter surfaces and clearer muted text. Per-state contrast and remaining legacy presentation CSS still need review |
| A10 | P2 | Fixed | Record list first; ML controls moved unchanged to research |
| A11 | P2 | Fixed | Nine lazy chapters, resume/read progress, invalid chapter and persistence/load error states |
| A12 | P2 | Fixed, bounded | Six oversized routes split in place; controller contract private, pure view models separate, duplicated switches unified. Inline-style retirement remains A09 |
| A13 | P2 | Fixed, bounded | Canonical API base; explicit GET/HEAD retry only, commands never retried. Archive compatibility retained |
| A14 | P2 | Fixed | Active Storybook roots exclude archive; build passed |
| A15 | P2 | Fixed | Proven cleanup items, grouped once for scoring |
| A16 | P3 | Fixed | Running task links only; ambient navigation animation and duplicated training scaffolds removed |
| A17 | P1 truth | Fixed | Removed stop-independent position/exposure estimate. Display configured risk budget; engine owns sizing |
| A18 | P2 | Fixed | Unit discovery rooted in active files; historical checkouts and separate Playwright runner excluded |
| A19 | P1 | Fixed | Phone live preflight formerly757px wide at320px; single-column/action-first layout passes expanded retests |

No P0 found. Fixed refers to the named bounded issue, not full-route or whole-system acceptance.

## Screen intent and resulting structure

| Route | Primary task/action | Result |
|---|---|---|
| / | Explain tool; open scanner | Short introduction, illustrative setup, four actual tool links |
| /scanner | Choose mode; run scan | Mode, critical requirements and run action first; filters and optional inputs secondary; results/rejections retained |
| /bot | Route to session owner | Existing recovery-priority routing retained |
| /bot/setup | Review risk; explicitly start LIVE | Preflight and disclosures first; phone layout fits. Testnet is supported by service but is not selectable here |
| /bot/status | Monitor/control session | Attention and recovery visible; positions/pending before optional statistics; commands retain selected session owner |
| /training/range | Configure/start PAPER | Start and risk summary before optional execution fields; existing paper owner retained |
| /journal | Filter/inspect/export records | List before summaries, visible field labels, keyboard/mobile sort, labeled phone rows; no model controls |
| /intel | Read context/mode advice | Existing source/freshness/unavailable behavior retained; reviewed at four widths |
| /training | Choose learning/research tool | Four concise links: lessons, replay, paper and research |
| /training/lessons | Read/resume chapter | Nine chapters wired; progress belongs to browser; teaching examples labeled historical |
| /training/replay | Load tape; step history | Setup separated from playback, help uses native modal; serialized replay owner unchanged |
| /training/drills | Explicit research actions | Journal model controls live here; research disclosure; behavior unchanged |
| /settings | Browser preferences | Preferences first; links lead to actual configuration owners; footer attribution retained |
| Unknown | Recover | Existing recovery links retained |

Nav remains Scanner, Bot, Journal, Intel, Training, Settings. Bookmarks and redirects are preserved. No feature/shared directory migration or paper-route alias was introduced.

Split responsibilities where the screens live:

- BotStatus: useBotStatusController, botStatusViewModel, BotStatusViews, BotPositions. Private generation refs stay in the controller; the page receives only its used composition contract.
- Journal: JournalFilters and TradeJournalViews; ResearchPanel belongs under training.
- Scanner: pure scannerSignals builder re-exported from the old test seam; ScannerContext and ScanController still own lifecycle/configuration.
- BotSetup, paper RangeBot and Replay: leaf views/controls extracted beside each route. Shared Toggle is a native keyboard switch.
- Shared: Modal and Topbar coordinate scroll locks; tokens.css owns the palette; apiBase.ts owns base-URL resolution. Feed/session transports retain their own lifecycle and error semantics.

## Cleanup and retained debt

Seven obsolete modules removed: four from the foundation, plus landingConfig, assetPresets and scannerFieldHelp. Each has reference/provenance proof and a hashed manifest. Gross removal:561 source lines,17,257 bytes. The retired Landing CSS section adds188 lines/10,640 bytes separately, bundled into A05. Two root providers and two direct dependencies were retired; node_modules disk savings were not measured.

Current literal import inventory:163 active JS/TS files,153 archive files,18 unreachable candidates,1,026 inline style objects. Added leaf files and reachable lessons explain the larger active-file count. Candidates are retained pending proof: archive consumers, generated API contracts and externally invoked verification/packaging sources are not disposable merely because main.tsx cannot reach them. Authored lessons and historical records are preserved.

The earlier archive report's query-client exception is superseded: queryClient is retired after its root provider lost all active consumers. The old report remains historical evidence. Remaining debt is primarily A08/A09 and strict journey verification, not an invitation to delete all graph candidates.

## Levels and score

| Level | Gate | State |
|---|---|---|
| 01 Map | Routes, owners, inventories and evidence committed | Cleared |
| 02 Shell | A01-A03 compiler, browser and review checks | Cleared |
| 03 Cleanup | Reference/provenance proof, builds, tests and independent review | Cleared |
| 04 Truthful state | Known false claims corrected; shared dialog keyboard/caller checks | Cleared, bounded to audited issues |
| 05 Focus screens | Primary-task rows inspected on desktop and phone | Cleared; exhaustive state acceptance remains07 |
| 06 Split in place | Existing owners/contracts preserved; unit tests/build/review pass | Cleared |
| 07 Verify journeys | Complete state, keyboard, contrast, native zoom and Safari matrix | Open |

Committed implementation score: **315**. P1/P2/P3 fixes earn20/10/5; cleanup items earn10 each, module/provider/dependency grouped once. Foundation110 plus follow-through205. A15 is represented only by cleanup items; no extra finding award. A08/A09 score zero while partial. No screen25-point awards, line/move points or trading points. The dashboard validates implementation commits as HEAD ancestors; it does not watch CI or award itself points.

### Scoring correction after the PRODUCT.md refresh

The earlier70-point calculation and40-point correction remain in the foundation ledger. The supplied weighted outcome policy supersedes both. This is a policy correction and verified follow-through, not additional points for editing documentation or historical measurements.

## Verification and practical limits

- Final TypeScript no-emit compiler passed.
- All177 active unit tests in15 files passed. Added meaningful progress-normalization and mutation-retry regressions. Existing active tests were unchanged; archived checkouts and Playwright specs use their own runners.
- Frontend Vite build passed:4,714 transformed modules. Storybook build passed:348 modules, with non-failing unmatched-story/metadata/chunk warnings.
- Exact asset bytes: main JS488,224→287,240; all JS824,406→862,598; all CSS70,546→68,105. Total JS now includes nine reachable lazy lesson chapters and intervening committed scanner fixes. These measurements do not establish latency or per-route total download savings.
- Independent rubric review found no remaining verified P1/P2 issue in this batch. Initial nested-dialog/portal-target and phone preflight defects were corrected and retested. AST checks confirmed BotStatus poll/action semantics, generation fences, ten view helpers and the Scanner builder contract.
- Intercepted browser evidence retains initial results and final retests separately:13 routes×4 widths, five CSS zoom/reduced-motion samples,15 session states,12 expanded layout cases, shared dialog callers and keyboard switches. Zero mutation requests. BODY focus while cycling browser chrome is recorded separately from background-control blocking.

**Not established:** mobile Safari, native200% browser zoom, full WCAG, every route/state/provenance/contrast permutation, exchange behavior or whole-system correctness. No unrestricted backend imports/tests ran. Level07 and A08/A09 remain open; no perfect-on-every-device or all-unused-code claim is made.

Rebuild evidence:

~~~powershell
node scripts/audit_frontend.mjs --output docs/audits/UI_REFACTOR_2026-10-09_inventory.json
node scripts/build_refactor_dashboard.mjs
~~~

Next work is the remaining control/contrast/CSS review and native cross-browser journey matrix. Reopen a cleared level if later evidence invalidates its bounded gate.

## Final release review before main publication

The final review corrected inherited keyboard, target and contrast defects: native paper-history and pipeline-evidence actions, visible focus, linked advanced live-setup labels, 44px journal/position/replay/dialog targets, muted journal calendar backgrounds and readable percentages/subtitles. Lesson cards expose only the active face. Regime diagrams show a static observed point with readable inactive labels. Duplicate shell rules were consolidated. Financial calculations, commands, strategy and existing state owners did not change.

[Final release evidence](UI_REFACTOR_2026-10-09_release.json) retains the initial candidates, 92-case responsive/lesson matrix, targeted keyboard checks and final setup/journal retests separately. The scoped independent review applies the current rubric. TypeScript and both builds pass;177 active unit tests in15 files pass. Final assets: main JS 287,240 bytes, all JS 863,216 bytes, all CSS 68,085 bytes. These append the earlier checkpoint rather than rewriting its measurements.

Final inventory:163 active files,153 archive files,18 retained candidates and1,028 inline style objects; this supersedes the preceding checkpoint's1,026 count. The additional four-width clock retest passes with opaque label backplates.

Implementation commit: 8e7bdf00e920bdaba8f72e19fbc98def571994f4. Score remains315: this closes concrete issues within partial A08/A09, with no duplicate awards. Level07 remains open for the complete native cross-browser and state matrix. Safari, native200% zoom and full WCAG remain unverified.
