# SniperSight — Task Router

Referenced by CLAUDE.md → "Task Router — Declare Upfront". CLAUDE.md holds the declaration
line you emit every non-trivial response; this file holds the full task-type → tooling map
and the pre-flight gates.

> ⚠️ **Verify these resolve before trusting them.** Several `/`-commands below
> (`/verify`, `/simplify`, `/security-review`, `/run`, `/loop`, `/schedule`, `/review`,
> `/update-config`, `/claude-api`, etc.) did not map to a skill in `.claude/skills/` or a
> `.claude/commands/` dir in the repo. They may live in your global `~/.claude/`. If a command
> doesn't resolve, the agent will whiff and improvise — remove it from this table or create it.
> Confirmed-present skills: `autopsy`, `confluence-trace`, `contract-check`, `impeccable`,
> `rejection-survey`, `scan-autopsy`, `trade-autopsy`, `triage`, `tune-confluence-weights`,
> `ui-ux-pro-max`. Confirmed agents: `adversarial-review`, `backend-integrity`,
> `rejection-forensics`, `repo-janitor`, `symmetry-guard`.

---

## Declaration line (emit on every non-trivial response)
```
Task type: <FEATURE|MODIFY|DEBUG|TEST|REFACTOR|UI|SCORING|DOCS|SECURITY|CONFIG|AUTOMATION|API-CODE>
Skills: <one or more, or none>
Agent: <one, or none — say so explicitly>
```
Trivial responses (typo, single-line tweak, conversational) may skip. Multiple skills allowed.
"Agent: none" is valid — say it. Operator can override; coder accepts the override.

## Task type → tooling
| Task type | Primary skills | Agents | Verification gate |
|---|---|---|---|
| **FEATURE** (add new) | `/impeccable` or `/ui-ux-pro-max` (if UI) | Plan → general-purpose → audit | audit + security review if auth/data |
| **MODIFY** (existing) | `/simplify` (post), verify | Explore (locate) → audit | verify |
| **DEBUG** (post-run) | `/autopsy` → `/scan-autopsy` / `/trade-autopsy` / `/confluence-trace` / `/rejection-survey` | rejection-forensics | diagnostic script (see CLAUDE.md "The Loop") |
| **TEST** | verify, run | general-purpose | snapshot framework for UI |
| **REFACTOR** | `/simplify`, repo-janitor | symmetry-guard (auto on scoring/regime files) | audit |
| **UI** | `/impeccable`, `/ui-ux-pro-max` | Plan (IA) → general-purpose | snapshot framework + verify |
| **SCORING/WEIGHTS** | `/tune-confluence-weights` | symmetry-guard (mandatory) | built-in skill checks + audit |
| **DOCS** | — | — | — |
| **SECURITY** | `/security-review` | — | manual sign-off |
| **CONFIG / HOOKS** | — | — | — |
| **AUTOMATION** | `/loop`, `/schedule` | — | — |
| **API-CODE** (Claude/Anthropic SDK) | `/claude-api` | — | — |

## Pre-flight gates (also in CLAUDE.md — full detail here)
- **Feature / new endpoint / new page** → Plan agent first; plan pasted verbatim; must enumerate
  affected files, new contracts (API/telemetry/DB), upstream callers, downstream consumers.
  Code does not start until the plan is on record. Operator may redirect.
- **Bug fix** → a diagnostic extension lands in the SAME diff that proves the bug gone (new file in
  `backend/diagnostics/` or extension to an existing `*_diagnostic.py`). Acceptable exception: an
  equivalent regression test in `backend/tests/` with the same loud-failure guarantees — cite it.
- **Scoring / regime / SMC edits** (`scorer.py`, `orchestrator.py`, `regime_detector.py`,
  `regime_policies.py`, `scanner_modes.py`, `backend/strategy/smc/*`) → symmetry-guard agent
  auto-invoked, output pasted alongside the audit (not in place of it). Standing-fixes check is a
  hard gate — a regression there means no commit, period.
- **Backend integrity** (any change to `engine/`, `strategy/`, `services/`, `bot/`, `analysis/`,
  `scanner_modes.py`, a FastAPI route, a telemetry event, or a DB/JSONL schema) → blast-radius map
  pasted before code lands; contract diff clean (`capture_contracts.py diff`) + `pipeline_smoke.py` passes.
