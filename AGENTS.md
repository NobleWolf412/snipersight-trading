# SniperSight contributor instructions

Reviewed 2026-10-10. These are the shared rules for every agent and contributor.
Historical thresholds, old reports and past decisions are evidence to investigate,
not proof of correctness.

## What we're doing now

Two tracks in parallel (details in [PRODUCT.md](PRODUCT.md#current-phase-reviewed-2026-10-10)):

1. **Backend:** debug and prove the trading logic. Order of priority: broken
   execution/accounting and silent failures, then strategy correctness, then
   friction and polish.
2. **UI:** reach the target look and feel. Phone and desktop are equals, and the
   operator uses the phone most. Current UI priorities: the Play Inspector chart
   modal, editing bot-planned plays with live R:R/P&L, at-a-glance rejection
   reasons, a decluttered phone layout, and modals instead of dropdown text dumps.

Deferred (design room only, no implementation): ML training/activation until the
trading logic is proven, product gamification (ranks, achievements), and any
token or wallet work.

## Read before you change

| Work | Read first |
|---|---|
| Anything | [docs/ARCHITECTURE_INDEX.md](docs/ARCHITECTURE_INDEX.md): owners, contracts, known limitations |
| UI, copy, layout, styling | [PRODUCT.md](PRODUCT.md) (intent, priorities, tone) and [DESIGN.md](DESIGN.md) (visual system). The `impeccable` skill reads both. |
| Strategy, scoring, thresholds | The index's configuration table and `backend/shared/config/` |
| Review of any change | [.claude/AUDIT_RUBRIC.md](.claude/AUDIT_RUBRIC.md) |

- The code establishes implemented behavior, not whether it is correct. Verify
  intended behavior against the operator's request and reproducible evidence.
- Treat generated graphs, saved memories, dated proposals and old reports as
  navigation and history. Confirm their claims in current source before acting.

## Work within the authorized scope

- Make bounded changes. Trace upstream inputs and downstream consumers before
  changing shared behavior; distinguish paper, testnet and live paths.
- **Strategy numbers belong to the operator.** Do not change weights,
  thresholds, mode minimums or trading behavior unless the operator explicitly
  asks, and never to make a test pass. When asked, record the baseline, the
  intended change and the verification. You may flag a number that looks wrong,
  with evidence.
- Respect the operator's existing authorization; don't repeatedly ask to
  continue. This file does not authorize orders, credential use, deployment or
  publishing; those follow the current task's authorization.
- Preserve unrelated working-tree edits and historical trading/audit records.
  For cleanup, establish that files are obsolete, check references and record
  deletions. Old age or no direct import alone is insufficient.
- Keep one owner per behavior (scan lifecycle, sessions, feeds, replay,
  financial display). Don't merge owners into a generic context, cache or
  retrying client in the name of simplification.

## Verify without contaminating runtime data

- Do not import the API or run unrestricted backend tests for an offline check.
  Imports can load the environment, create stores and start external clients.
- Use the guarded runner from the repository root. Modes: `backend`,
  `contracts`, `smoke`, `inputs`; `backend` accepts `-k <expr>`.

  Windows (local runtime, `backend/venv`):

  ```powershell
  .\backend\venv\Scripts\python.exe -B backend/diagnostics/offline_verify.py backend
  ```

  Linux / cloud sessions (no `backend/venv` in a fresh clone; install
  `requirements.txt` into a venv or the session Python first):

  ```bash
  python3 -B backend/diagnostics/offline_verify.py backend
  ```

- Check the selected manifest ([offline_checks.json](backend/diagnostics/offline_checks.json))
  before claiming a path was covered. Do not weaken isolation or overwrite
  contract baselines to obtain a pass.
- Frontend: `npx tsc --noEmit`, `npm test` (Vitest) for relevant tests,
  `npm run lint` where touched. For visual changes, check desktop **and** a
  390px phone viewport, plus reduced motion, before calling them done.
- Documentation-only changes need link/reference/config checks, not an
  unrelated application test run.
- Use independent review for substantial logic or architecture changes and
  deletion batches. Apply the checklist to the affected scope; mark unverified
  concerns explicitly.
- Report what changed, what actually ran, its result and limitations. Synthetic,
  serial-worker or static checks do not establish live or whole-system correctness.

## Keep the docs current

- Update [the architecture index](docs/ARCHITECTURE_INDEX.md) **in place** when
  ownership, a contract or a known limitation changes. Do not append dated
  checkpoint sections there; add them to the
  [architecture changelog](docs/audits/ARCHITECTURE_CHANGELOG.md) and keep
  detailed evidence in `docs/audits/` or `backend/diagnostics/decisions/`.
- Update PRODUCT.md's surface inventory in the same commit that changes a
  surface's status. Update DESIGN.md when a visual rule or signature component
  changes.
- Keep past checkpoint evidence intact; append corrections instead of rewriting
  what was known at the time.
