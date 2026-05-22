# 2026-05-21 — Workflow enhancement Tier 1: §17/§18/§19/§20 added, Rubrics 13/14 added

## Headline
Tier 1 workflow enhancement landed: task router (§17), pre-flight discipline (§18), decisions log (§19), and backend integrity discipline (§20) added to CLAUDE.md. §16 audit rubric extended from 12 to 14 items (blast-radius + contract-diff). Initial contract baselines captured.

## Context
User asked: "what could we do to enhance this workflow either to modify claude.md, or whatever files you refer to, and further automate for increased quality? where are our pain points and gaps?"

Identified pain points from MEMORY.md calibration history:
1. Verbatim-paste discipline slipping (3a'/3a''/3z.h)
2. Scope-creep flags firing retroactively (3a TickerRail)
3. Audit subagent's explicit gap on adversarial-review issues (CLAUDE.md §16 "What the audit cannot catch")
4. No automatic skill/agent dispatch — ad-hoc per turn
5. Diagnostic discipline (§12) as principle, not enforced
6. No design-first gate even for new endpoints
7. Calibration learnings died with memory resets
8. Backend interface contracts (API, telemetry, DB, SniperContext) had no snapshot enforcement — silent drift could break downstream consumers without the §16 rubric noticing

User accepted Tier 1 ("yeah") including the backend-integrity addendum ("make sure the backend stays intact up and downstream").

## Resolution
1. **CLAUDE.md §17 Task Router** — every work-doing response now starts with a one-line declaration `Task type: X. Skills: Y. Agent: Z.` Task-type → skills/agents table embedded inline.

2. **CLAUDE.md §18 Pre-flight Discipline** — three gates: (a) feature/new-endpoint work requires Plan agent first, (b) bug-fix work ships diagnostic script in same diff, (c) scoring/regime/SMC file edits auto-invoke symmetry-guard agent.

3. **CLAUDE.md §19 Decisions Log** — new dir `backend/diagnostics/decisions/`, calibration learnings migrate out of MEMORY.md into per-decision files. Memory becomes one-line pointer index.

4. **CLAUDE.md §20 Backend Integrity Discipline** — trigger list (engine/strategy/services/bot/analysis + API routes + telemetry + DB/JSONL schemas), required blast-radius map pre-flight, contract snapshots in `backend/diagnostics/contracts/`, pipeline smoke test plan.

5. **§16 Rubric 13** — blast-radius enumeration required for backend-touching changes.

6. **§16 Rubric 14** — contract-diff clean (or documented deltas) required; `python -m backend.diagnostics.capture_contracts diff` exits clean.

7. **`backend/diagnostics/capture_contracts.py`** — driver script with `capture` and `diff` modes. Introspects FastAPI routes, telemetry EventType + factory signatures, SniperContext dataclass fields, and CREATE TABLE statements + JSONL canonical keys.

8. **Initial baselines captured 2026-05-21** (actual counts from captured JSONs):
   - `api_contracts.json` — 97 routes
   - `telemetry_contracts.json` — 19 EventType members + 10 factory functions
   - `pipeline_contracts.json` — 12 SniperContext fields
   - `db_contracts.json` — SQLite tables from `telemetry/storage.py` and other persistence modules, plus JSONL key sets where files exist

## Why it matters next time
The §16 rubric was previously blind to interface-stability drift. A function rename in `confluence_breakdown` could silently break `ConfluenceBreakdown.tsx` and the auditor wouldn't flag it. With Rubrics 13/14 + the contract snapshots, any backend-touching change has to either match baseline or document the delta — which forces the coder to think about downstream consumers explicitly, not by chance.

The decisions log is the durable replacement for memory-as-calibration-store. When memory resets, the rules survive in `backend/diagnostics/decisions/`. MEMORY.md becomes a 5-line index.

Future Tier 2 items queued (not landed this round):
- adversarial-review subagent (addresses §16 "what the audit cannot catch")
- `/triage` skill (front-of-house for §17 router)
- symmetry-guard PostToolUse hook (auto-invoke on scoring/regime file edits)
- `pipeline_smoke.py` + `golden_scan.json` (referenced by §20 but not yet implemented; placeholder in rubric 14 is conditional "for pipeline changes")
- frontend↔backend TS-type sync

Cross-ref: CLAUDE.md §16/§17/§18/§19/§20; `backend/diagnostics/capture_contracts.py`; `backend/diagnostics/contracts/*.json`.
