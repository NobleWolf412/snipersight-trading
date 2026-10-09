# SniperSight contributor instructions

Reviewed 2026-10-08 for the current system review. These instructions replace the
older project rulebook; historical thresholds and past design decisions are
evidence to investigate, not proof of correctness.

## Start from current evidence

- Start with [docs/ARCHITECTURE_INDEX.md](docs/ARCHITECTURE_INDEX.md), then inspect
  the relevant implementation, configuration precedence, callers and consumers.
- The code establishes implemented behavior, not whether that behavior is correct.
  Verify intended behavior against the user's request and reproducible evidence.
- Treat generated graphs, saved memories, dated proposals and old reports as
  navigation/history. Confirm their claims in current source before acting.
- Preserve scanner and autonomous-bot product intent. ML implementation/training
  is outside the current review scope.

## Work within the authorized scope

- Prioritize broken execution/accounting and silent failures before strategy
  correctness, friction and polish.
- Make bounded changes. Trace upstream inputs and downstream consumers before
  changing shared behavior; distinguish paper, testnet and live paths.
- Do not change strategy weights, thresholds or trading behavior merely to make
  a test pass. Record the baseline, intended behavior change and verification.
- Respect the user's existing authorization; do not repeatedly ask to continue.
  This file does not independently authorize orders, credential use, deployment
  or publishing. Use the current task's authorization for those actions.
- Preserve unrelated working-tree edits and historical trading/audit records.
  For cleanup, establish that files are obsolete, check references, and record
  deletions. Old age or no direct import alone is insufficient.

## Verify without contaminating runtime data

- Do not import the API or run unrestricted backend tests for an offline check:
  imports can load environment, create stores and start external clients.
- Use the repository venv and guarded runner from the repository root:

  ```powershell
  .\backend\venv\Scripts\python.exe -B backend/diagnostics/offline_verify.py backend
  .\backend\venv\Scripts\python.exe -B backend/diagnostics/offline_verify.py contracts
  .\backend\venv\Scripts\python.exe -B backend/diagnostics/offline_verify.py smoke
  ```

- Select meaningful tests for the change; the backend runner accepts `-k`.
  Check the selected manifest before claiming a path was covered. Do not weaken
  isolation or overwrite contract baselines to obtain a pass.
- For TypeScript changes use the installed compiler, `tsc --noEmit`, and relevant
  local tests. Documentation-only changes need link/reference/config checks,
  not an unrelated application test run.
- Use independent review for substantial logic or architecture changes and
  deletion batches. Apply the [current checklist](.claude/AUDIT_RUBRIC.md) to the
  affected scope; mark unverified concerns explicitly.
- Report what changed, what actually ran, its result and limitations. Synthetic,
  serial-worker or static checks do not establish live or whole-system correctness.
- Update the current map and evidence ledger when behavior/ownership changes.
  Keep past checkpoint evidence intact; append corrections instead of rewriting
  what was known at the time.
