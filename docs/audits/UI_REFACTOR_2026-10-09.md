# UI simplification audit and refactor proposal

Reviewed 2026-10-09 against the current working tree. This pass delivers an audit,
an executable first refactor, and a development progress dashboard. It does not
claim completion of the proposed screen migrations or removal of every unused
module in the repository.

Open the [progress dashboard](UI_REFACTOR_2026-10-09.html).
Its source is the [evidence and task ledger](UI_REFACTOR_2026-10-09.json).
The [initial inventory](UI_REFACTOR_2026-10-09_baseline.json),
[current inventory](UI_REFACTOR_2026-10-09_inventory.json) and
[deletion manifest](UI_REFACTOR_2026-10-09_removals.json) retain the baseline.

## Direction

An operator checking a scanner and a running session on a desktop under dim
light, then reviewing status on a phone, needs legible evidence and quick actions.
Keep olive-tinted dark surfaces, monospace numeric data, and explicit paper/live
state. Remove ornament that implies activity without a corresponding event.
Use one primary task per screen, with secondary evidence arranged around it.
Warnings, incomplete financial outcomes, rejection causes and freshness stay visible.

The requested game belongs to development progress. Reward confirmed cleanup and
verified milestones. Trading activity, order counts, scores and profits earn no points.

## Inspection boundary

Started with ARCHITECTURE_INDEX.md, the current rubric, PRODUCT.md and DESIGN.md.
Used the existing graph as navigation, then current imports, route definitions,
configuration owners and consumers as evidence. Serena's Python service cannot
index TSX here; frontend inspection used source and the installed TypeScript parser.

Browser inspection covered Scanner, Intel, Settings, Bot Status, Journal and Training,
using desktop, tablet and phone viewports. Additional routes received source inspection.
Views show an existing paper session; no session was started, stopped, reset or traded
by this audit. Existing backend/runtime edits and historical records were preserved.

This is a broad frontend architecture audit and selected browser review, not a
backend dead-code certification, a full WCAG assessment, or a live execution test.
Backend scanner/replay symbol inventories and browser state owners were inspected;
backend implementation/training and strategy calibration were not changed.

## Initial health assessment

These are heuristic judgments of the starting interface, not measured compliance
scores or post-refactor claims. The fixes below improve selected paths; the
remaining findings prevent calling the app fully polished.

| Dimension | Initial score / 4 | Evidence |
|---|---:|---|
| Accessibility | 1 | Closed drawer exposed; generic Modal lacks dialog/focus semantics; journal filters unnamed |
| Performance | 2 | Lazy routes already exist; root providers and broad shell imports add avoidable work |
| Responsive design | 2 | Phone layouts exist; shared targets small; journal pagination clips; several inline grids remain |
| Theming | 1 | Multiple token layers and hard-coded page styles compete; unusually dim small labels |
| Visual restraint | 1 | Scanlines, text glow, animated background, cursor reticle and persistent beacon compete with evidence |
| Total | 7 / 20 | Significant work needed |

The visual issue is specific: repeated gauges, nested panels, small uppercase labels
and glowing inactive surfaces dominate the initial reading order. Removing these
does more for usability than choosing a new accent palette.

## Findings, ordered by consequence

| ID | Priority | Finding and evidence | User impact / next action | Disposition |
|---|---|---|---|---|
| A01 | P1 | Topbar's translated closed aside retained dialog semantics and focusable links | Closed navigation appeared in the accessibility tree. Use native dialog with focus restoration, inert background and explicit current-page state. | Fixed |
| A02 | P1 | GauntletBreakdown rendered `#${bottleneck.href}` under BrowserRouter | “Inspect Scanner evidence” stayed on Bot Status. Use the actual route. | Fixed |
| A03 | P1 | TradeJournal filter inputs/selects lacked names and disabled focus outlines | Screen-reader and keyboard filtering were difficult. Added five names, restored focus visibility and wrapped pagination. | Fixed |
| A04 | P1 | components/hud/Modal.tsx is two divs with backdrop-click handling | No shared Escape, focus containment/restoration or dialog label contract. Replace after auditing every caller, including nested health/position dialogs. | Open |
| A05 | P1 | Landing.tsx static SignalProof rows are under “LIVE SIGNAL FEED / STREAMING” | Examples appear current; claims include unestablished alerts, backtests and “zero drift.” Label examples clearly and replace claims with implemented capabilities. | Open |
| A06 | P1 | PhemexStatusPill probes the live service; observed running PAPER screen still shows PHEMEX IDLE | Health owner is unclear. Label this as live-executor health; show paper session status separately. Do not infer paper-feed health from live status. | Open |
| A07 | P2 | Scanner.tsx: recommendation, four large mode cards, inputs and duplicated metrics precede results | The primary Run Scan action sits far below the phone fold. Show selected mode + compact change control alongside the action; retain critical setup requirements. | Open |
| A08 | P2 | Shared nav links measured 32px, hamburger 36px; other page controls remain bespoke | Shared buttons/menu and journal fields now reach 44px. Inspect remaining filters, sliders, row actions and full clickable labels individually. | Partial |
| A09 | P2 | hud.css/index.css/effect layers and inline page styles mix tokens, dim text and ornament | Workspace layer now quiets panels, removes common text glow and raises muted-token lightness; fresh preferences disable background/reticle. Full per-state contrast/motion review remains. | Partial |
| A10 | P2 | TradeJournal.tsx mixes trade review with MLPanel model training/reset/clear controls | Review history should be a single task. Move experimental tools to an explicitly labeled research destination; no ML behavior change in this pass. | Open |
| A11 | P2 | Lessons.tsx renders only a scaffold; content/lessons/index.ts defines nine lazy chapters | Authored educational content is unreachable. Wire the library and progress, or mark the entry unavailable. Keep authored content rather than deleting it as “unused.” | Open |
| A12 | P2 | Six page files exceed 1,100 lines; baseline has 1,266 JSX style attributes | Layout, data orchestration and diagnostics are coupled. Extract by owner and responsibility, with feature-local CSS and selectors. | Open |
| A13 | P2 | Legacy services/api.ts uses a different base resolver; telemetry and landing scaffolds retain archive callers | A blind API consolidation risks retrying mutations or changing endpoints. Remove the unused journal import now; retire remaining legacy graph as a coordinated follow-up. | Partial |
| A14 | P2 | .storybook/main.ts includes src/**/*.stories, including _archive | TypeScript exclusion does not exclude archived stories. Separate active stories from historical examples before retiring archive dependencies. Storybook build not certified here. | Open |
| A15 | P2 | Four orphan modules, two mounted providers with no active consumers | Fake telemetry hook, unconsumed notification polling, unused numeral facade and query client removed. Wallet source retained for archived consumers. | Fixed, bounded |
| A16 | P3 | ActiveScanBeacon adds a training shortcut to unrelated screens; subtitle/title/chips repeat context | Preserve genuine active scan/session shortcuts, remove navigation-only ambient animation and duplicated labels. Coordinate with its existing edits. | Open |

No P0 was established. Six P1, nine P2 and one P3 findings were recorded.
WCAG concerns include keyboard operation/focus, name-role-value, and text contrast;
44px is the chosen touch-target quality goal, not a claim that every smaller control
automatically violates WCAG AA.

## Intent per screen

| Current route | Singular purpose | Primary action | Proposed simplification |
|---|---|---|---|
| / | Explain the tool and choose a workflow | Open scanner | One short introduction; clearly labeled examples; remove duplicate chrome and unsupported promises |
| /scanner | Run a scan and review its setups | Run scan | Compact mode/input summary, action, receipt, results; visible failure summary; optional evidence detail |
| /bot | Resolve the current session owner | Automatic routing | Preserve recovery/partial-status behavior, with a clear unavailable state |
| /bot/setup | Review and start a live session | Review preflight, then explicit start | Risk summary first; advanced fields grouped; persistent LIVE disclosure; retain start boundary |
| /bot/status | Monitor and control the selected session | Stop or inspect attention state | Positions/pending/recovery first; summary second; diagnostics on demand; no hiding active failure causes |
| /training/range | Configure or inspect a paper session | Start paper or inspect session | Proposed /bot/paper alias, using the existing paper owner; retain old URL and all paper disclosures |
| /journal | Review completed execution records | Filter, inspect, export | Record list first; secondary summaries; remove research controls from the main task |
| /intel | Understand current market context | Refresh or open scanner | Compact freshness/source row, regime and shares; optional derivatives detail; retain unavailable fields |
| /settings | Change browser preferences | Change preference | Preference controls first; relevant configuration links; move duplicated status/export panels to their owners |
| /training | Choose an available learning/research tool | Open lessons or replay | Two clear destinations; no advertised quizzes until implemented; paper entry redirects to bot owner |
| /training/lessons | Read a chapter and retain progress | Resume chapter | Wire nine existing chapters; show implemented progress; remove internal file-path copy |
| /training/replay | Inspect historical candles and causal evidence | Load tape, then navigate | Setup separated from playback; preserve serialized cursor, cleanup errors and missing macro evidence |
| /training/drills | Inspect experimental model tools | Explicit research action | Secondary research destination; no training implementation or promotion work in this scope |
| Unknown route | Recover navigation | Open scanner | Keep direct task recovery links |

Desktop navigation now orders Scanner → Bot → Journal → Intel → Training → Settings.
The proposed next stage groups the first four as operating destinations, with Training
and Settings secondary. Keep existing bookmarks and redirect obsolete aliases.
Do not collapse scanner configuration into bot-session configuration.

### Responsive contract

Use a content-driven shell breakpoint at 1120px, not six squeezed navigation links.
Phone content uses one column; no document-level clipping to disguise overflow.
At 320/390px, keep the primary action reachable early, status text wrapping, labeled
inputs >=44px, and visible next/retry controls. Dense financial tables can scroll
inside a labeled region or become labeled rows. At 768px use the same compact
navigation and a two-column layout only where each column remains readable.
At 1280px keep task + evidence side by side. At 200% zoom, preserve names and actions.

Support idle/loading/error/partial/stale/recovery states, long symbols, absent
provenance, zero records and mobile safe areas. Verify keyboard order and
reduced-motion behavior on each composed screen. These are acceptance criteria;
they are not all satisfied by the current foundation pass.

## Architecture: current ownership to preserve

| Owner | Current implementation | Preserve during migration |
|---|---|---|
| Browser scan lifecycle | scanRunService + ScannerContext + ScanController | One run identity; resume/cancel semantics across route/reload; receipt provenance |
| Autonomous session | activeSession + paperTradingService/liveTradingService | Distinct paper/testnet/live paths, recovery priority, one selected service for commands |
| Feed lifecycle | FreshFeed + useFreshFeed + useMarketRegime | Expiry, source times, partial availability and retry |
| Replay lifecycle | ReplaySessionController + replay routes/engine | Serialized mutations, generation fences, cleanup failures; no present-day substitution |
| Financial display | accounting + tradeJournalService | Unknown quantities/fees/P&L remain unknown; filtered pagination and export scopes remain explicit |
| Trading engine | ScannerService and independent paper/live engines | Configuration precedence, gates, sizing and journal ownership stay backend responsibilities |

Removing fake telemetry and unused providers does not justify replacing these
owners with generic context, one giant query cache or a shared auto-retrying client.

### Proposed structure

```text
src/
  app/                    # router, shell, navigation, route error/loading states
  features/
    scanner/              # page, compact setup, results, evidence, selectors
    bot/                  # setup/status; paper/live transports remain separate
    journal/              # record list, filters, detail, summaries
    intel/                # source-aware context and funding
    learning/             # lesson library and replay presentation
    research/             # explicitly experimental UI, no ML implementation change
    preferences/          # browser appearance
  shared/
    ui/                   # Button, Field, Dialog, Status, Section, EmptyState
    styles/               # one token owner, primitives, accessibility, motion
    transport/            # base URL, timeout, error parsing; mutation retry is opt-in
    formatting/           # finite-value formatting with explicit unavailable values
  types/                  # generated API contracts retained
  _archive/               # historical reference, separate from active build/story roots
docs/audits/               # evidence, levels, deletion manifests and dashboard
```

First move a leaf component and its CSS; re-export from its old path while updating
callers. Then move one feature presentation at a time. Existing state owners can
keep their paths until migration tests prove identity, subscriptions and cleanup.
Do not introduce folders merely to rename existing abstractions.

Bot Status should split into a session-controller hook, pure session/account view
model, attention/recovery block, position/pending list, and diagnostics. Journal
should split filters/list/detail from summaries. Scanner should split pure
buildCardSignals/filters from result presentation, retaining its exported test seam.
Consolidate transport after feature ownership, keeping read retry separate from commands.

## Cleanup evidence and limits

The installed TypeScript parser follows literal imports, dynamic imports and
re-exports from main.tsx, active tests and stories. It found 153 active JS/TS files
and 153 archived JS/TS files at baseline; generated API types are included.
These are file counts, not application-module or deletion counts.

The remaining unreachable list is a triage inventory. It includes authored
lessons, generated contracts, archive-dependent providers and scripts whose
execution roots are outside src. All require provenance/reference checks.
No candidate count is credited as a removal.

Confirmed deletions: useTelemetry.ts (fake metrics), notificationPolling.ts
(no consumers), utils/format.ts (no consumers), lib/queryClient.ts (unused provider
retired). Manifest totals: **4 files, 350 source lines, 9,700 bytes**. This is gross
source removed from those files, not net LOC reduction or runtime savings.
Removed @tanstack/react-query and numeral from package/lock declarations.
Existing node_modules was not pruned by the package-lock-only update.

WalletContext, LandingContext, legacy telemetry/price/notification utilities and
their types remain where archives still reference them. Generated API types and
authored lessons were retained. Historical trading/audit records were not deleted.
Append this correction to the old archive report's query-client exception:
queryClient is now retired after its root provider lost all active consumers.

Regenerate the import inventory:

```powershell
node scripts/audit_frontend.mjs --output docs/audits/UI_REFACTOR_2026-10-09_inventory.json
```

## Levels and honest scoring

| Level | Goal | Completion gate | Current state |
|---|---|---|---|
| 01: Map | Current route/state/dependency inventory | Evidence-backed purpose and candidate lists | Cleared |
| 02: Simplify shell | Navigation, focus, shared legibility and key mobile defects | Compiler, browser checks and scoped review | Cleared for the bounded changes |
| 03: Remove confirmed bloat | Orphans and unused root providers | Provenance + hashes + reference search + build/tests/review | Cleared for the four-file batch |
| 04: Focus screens | Scanner, session, journal and learning intent | Functional flows and failure states, desktop/phone/zoom verification | Planned |
| 05: Establish feature boundaries | Small components, one token owner, explicit transport | Consumer migration, retained state identity, contract checks | Planned |
| 06: Verify complete journeys | Responsive/accessibility/regression acceptance | All route states, keyboard, zoom, reduced motion, browser matrix | Planned |

Score = 10 per confirmed orphan module + 5 per unnecessary root provider retired
+ 10 per unused direct dependency removed. Current score: **70 points**.
No points for comment deletion, moving code, generated files, test weakening,
historical records, fabricated measurements or strategy changes. A level only
clears when its stated gate is met. A new phase can reopen a level if evidence fails.

Milestones: “one scanner owner retained,” “keyboard-safe navigation,” “orphan
batch verified,” “charts load with their routes.” The dashboard reads a saved
ledger; it is not a real-time CI watcher and does not auto-award completion.

## Verification

Baseline and refactored Vite builds were captured in separate ignored build folders.
Direct shell imports and provider retirement reduced the observed main JS entry
from 488,224 bytes to approximately 289,000 bytes; lightweight-charts now has its
own lazy chunk. See ledger for final exact measurements, gzip and total assets.
Entry reduction is not a claim that chart routes download that much less in total.
CSS increased because this pass adds an explicit workspace/accessibility layer;
the token consolidation level should replace legacy layers rather than keep stacking them.

TypeScript, selected local tests, native menu/route checks, and journal phone control
measurements are recorded in the ledger. The selected tests preserve scanner scores,
workflow identity, LONG/SHORT evidence, financial view models and replay mutation
retry semantics; they do not exercise native dialog behavior. Browser checks cover that.
No unrestricted backend suite/API import, new exchange operation, full Storybook
build, mobile Safari test, every dialog, zoom matrix or full WCAG sign-off is implied.

Independent review applies the current rubric to the affected diff and removal
batch. Findings and corrections are appended to the evidence ledger.

Recommended sequence: /impeccable harden (shared dialogs and truthful state labels),
/impeccable distill (screen hierarchy), /impeccable adapt (all viewport/state cases),
/impeccable extract (token/component ownership), then /impeccable polish.
