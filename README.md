# SniperSight

SniperSight combines a React trading dashboard with a Python/FastAPI scanner,
Smart Money Concepts analysis, trade planning, paper trading and live execution
components. Their presence does not establish production readiness or profitability.

## Working on the code

Start with [the architecture index](docs/ARCHITECTURE_INDEX.md), its current
findings and coverage ledger, then inspect the implementation. Scanner requests,
paper sessions and live sessions have separate configuration and state owners.

[AGENTS.md](AGENTS.md) contains contributor instructions.
[The verification checklist](.claude/AUDIT_RUBRIC.md) describes evidence expected
for a change. [PRODUCT.md](PRODUCT.md) and [DESIGN.md](DESIGN.md) describe product
and visual intent; current behavior is established by code and verification.

The October 2026 review is an offline assessment with bounded repairs. Its
[checkpoints](docs/audits/SYSTEM_DISCOVERY_2026-10-07.md) state what was tested and
what remains unverified. ML implementation and training are outside that work.

## Development startup

Use the dependency declarations in [package.json](package.json),
[requirements.txt](requirements.txt) and [pyproject.toml](pyproject.toml).
The existing local Python environment is `backend/venv`; inspect those declarations
when recreating an environment rather than assuming the local install is portable.

With dependencies installed and the intended Python environment active:

```powershell
npm run dev:all
```

The package scripts start the API at **8001** and frontend at **5000**.
[Vite](vite.config.ts) proxies API requests to the configured backend; alternate
launchers and environment overrides can change this. API startup loads environment
and initializes services, so it is not an offline verification command.

For the Windows desktop launcher, run `scripts/start_windows.ps1` or the installed
**SniperSight** desktop shortcut. It starts the repository Python environment and
installed Vite in the background, opens the dashboard, and reuses healthy running
services. Logs are under `%LOCALAPPDATA%\SniperSight\logs`. This launcher binds
both services to localhost and does not enable automatic code reload. Phone access
uses the separately configured private Tailscale Serve HTTPS address; the PC must
remain awake. Starting the dashboard does not start a trading bot. See the
[local access verification](docs/audits/LOCAL_ACCESS_2026-10-08.json) for this host.

## Decision system

Modes are configurations of the shared engine. Read
[scanner_modes.py](backend/shared/config/scanner_modes.py) for defaults and the
[index's configuration table](docs/ARCHITECTURE_INDEX.md#decision-contracts-and-configuration-precedence)
for request/session overrides. A mode default is not necessarily the effective
score or risk threshold.

The main path joins market selection, candle ingestion, features and market
context, gates and directional scoring, decision policy, planning and risk.
Paper/live services add admission, execution and position management. The index
links the actual owners, contracts and known differences; no duplicate static
module tree is maintained here.

## Offline verification

From this Windows checkout:

```powershell
.\backend\venv\Scripts\python.exe -B backend/diagnostics/offline_verify.py backend
.\backend\venv\Scripts\python.exe -B backend/diagnostics/offline_verify.py contracts
.\backend\venv\Scripts\python.exe -B backend/diagnostics/offline_verify.py smoke
.\node_modules\.bin\tsc.cmd --noEmit
```

The guarded backend suite is selected, not the whole repository. It isolates
test stores and denies external transport and child processes. Use `-k` for a
focused backend selection and inspect the runner/manifest when adding coverage.
Frontend test configuration and coverage limits are documented in the index.

Contract snapshots supplement caller/consumer inspection. Do not regenerate them
simply to hide drift. Successful offline tests do not certify exchange connectivity,
all modes/policies, operating-system worker isolation or live settlement.

## Records and security

Preserve real journals, telemetry, audit checkpoints and dated decisions.
Dated proposals and archives are historical evidence, not current implementation
instructions. The current index records unresolved ownership and data issues.

Do not assume local endpoints or a connected wallet provide authentication.
The removed security templates did not demonstrate JWT/RBAC/encryption in the
current app; wallet account selection alone is not proof of identity.
