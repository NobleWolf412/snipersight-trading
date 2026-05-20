# SniperSight post-run debug skill set

Six skills + one agent + one headless diagnostic make up the post-run debug loop
for SniperSight. This doc is the map: when to use which, in what order, and
what each one assumes about its data sources.

If you're reading this in a fresh Claude conversation, this is the entire
mental model — every other detail lives in the individual `SKILL.md` files
or in [CLAUDE.md](../../CLAUDE.md).

---

## The loop (canonical chain)

```
[1] Run paper trader / autonomous bot
        |
        v
[2] Stop bot (clean stop, not crash)
        |
        v
[3] /autopsy                                  triage. names top 3 threads.
        |
        v
[4] Drill on a named thread (one of):
      /scan-autopsy <run_id>                  one cycle's pipeline funnel
      /trade-autopsy <trade_id>               one closed trade's lifecycle
      /rejection-survey [N=50]                pattern across N cycles
      /confluence-trace <SYMBOL>              per-symbol scoring anatomy
      forensics on <SYM> <MODE>               single-signal kill chain (agent)
      run symmetry-guard                      §10 standing-fix audit (agent)
        |
        v
[5] Paste the drilldown report into chat
        |
        v
[6] Claude proposes a targeted fix (§13 surgical edit, not a rewrite)
        |
        v
[7] You approve → Claude applies edit
        |
        v
[8] Per §12: extend / add a diagnostic that proves the bug is gone
   (lives in backend/diagnostics/; would catch the bug returning)
        |
        v
[9] You restart paper trader / bot, let it run a cycle or two
        |
        v
[10] /autopsy again — confirm the thread is gone, no new threads
        |
        v
[11] Commit (or repeat from [4] if there's another thread)
```

**Loop closes** when `/autopsy` returns CLEAN on two consecutive sessions.

---

## Skill index

| Skill | Scope | Input | Reads | Writes state? |
|---|---|---|---|---|
| `/autopsy` | session triage — "what just happened?" | optional `session_id` / window | `trade_journal.jsonl`, `telemetry.db`, optional `/api/cycles/last` | reads only (annotates threads) |
| `/scan-autopsy` | one cycle — "where did signals die?" | `run_id` or `last` | `telemetry.db`, optional `/api/cycles/...` | writes drift + mass-conservation gaps |
| `/trade-autopsy` | one trade — "why did this lose?" | `trade_id` / `last` / `last-loss` / `last-win` / `<symbol>` | `trade_journal.jsonl`, `telemetry.db` | writes verdict per `trade-<id>` |
| `/rejection-survey` | N cycles aggregate — "what's killing signals systemically?" | `N` (default 50), optional `mode` / `symbol` | `telemetry.db` | writes drift only |
| `/confluence-trace` | per-symbol scoring anatomy | `SYMBOL` + optional `MODE`/`compare` | `logs/paper_trading/session_*/signals.jsonl`, `scorer.py` weights, `scanner_modes.py` cascade | writes verdict + gaps per `confluence-<sym>` |
| `rejection-forensics` agent | one signal kill-chain at timestamp | `SYMBOL` + `MODE` + optional timestamp | `telemetry.db`, signal_log, source code | n/a (not a skill — Agent tool delegate) |
| `symmetry-guard` agent | §10 standing-fix audit | (none) | scoring, regime, orchestration, SMC code | n/a (Agent tool delegate) |

**Headless equivalent of `/autopsy`:** `python -m backend.diagnostics.autopsy_report` — same logic, runs in ~5s, writes paste-friendly report to `.claude/autopsy-reports/<utc>__pid<pid>.md` + stdout, exit code 0=CLEAN / 1=NOTABLE / 2=INVESTIGATE / 3=DATA-UNAVAILABLE / 4=INTERNAL-ERROR. Wire into your bot stop / wrapper script for auto-triage.

---

## Decision tree — "which skill?"

```
You just stopped the bot/paper trader.                       → /autopsy
You have a specific run_id you want walked stage-by-stage.   → /scan-autopsy <run_id>
You have a specific trade_id you want post-mortem'd.         → /trade-autopsy <id>
You want broad pattern across many cycles.                   → /rejection-survey [N]
You want to know WHY this symbol scores like it does.        → /confluence-trace <SYM>
You have a specific signal that didn't fire as expected.     → "forensics on <SYM> <MODE>" (agent)
You suspect a bull/bear symmetry leak or §10 regression.     → "run symmetry-guard" (agent)
```

**If you're unsure**, start with `/autopsy`. It triages and tells you which
drilldown to run next. Don't pick a drilldown skill cold without triage first
unless you already know the specific thread you want pulled.

---

## Cross-skill state file

`.claude/.skill-state/session-<sid>.json` — a tiny per-session JSON written by
some skills and read by others so verdicts don't get re-investigated.

**Sections:**
- `resolved_findings[]` — skill verdicts per `thread_key` (e.g. a `/trade-autopsy`
  call writes `trade-<trade_id>` → `EXPECTED-LOSS-NO-BUG`)
- `observability_gaps[]` — known telemetry/log gaps with status (open/patched/wontfix)
- `vocabulary_drift[]` — new (reason, gate_name) combos with counter

Skills read this on entry and **annotate** their output with prior verdicts
(e.g. `/autopsy` marks a prior-cleared thread as `[PRIOR: trade-autopsy → CLEARED]`).
**State is annotation, not control** — every skill still runs its analysis
fresh per CLAUDE.md §11. A skill that hides resolved threads from triage
would mask regressions.

Manage state from a shell when needed:
```
python .claude/skills/_state_helper.py read <session_id>
python .claude/skills/_state_helper.py list-findings <session_id>
python .claude/skills/_state_helper.py list-gaps <session_id>
python .claude/skills/_state_helper.py list-drift <session_id>
```

---

## Live data sources (verified May 2026)

| Source | Path | Used by | Notes |
|---|---|---|---|
| Telemetry SQLite | `backend/cache/telemetry.db` | autopsy, scan-autopsy, rejection-survey, trade-autopsy | `telemetry_events(event_type, timestamp, run_id, symbol, data_json)`. Schema in `backend/bot/telemetry/storage.py:50`. |
| Trade journal | `backend/cache/trade_journal.jsonl` | autopsy, trade-autopsy | One JSON row per closed paper trade. Carries `session_id` so journal is also the canonical session boundary source. |
| Signal log | `logs/paper_trading/session_*/signals.jsonl` | confluence-trace | One JSON row per signal scored (passed or filtered). Has `convergence_missing`, `regime`, `gate_name`, `reason_type`. |
| Cycle heartbeat API | `/api/cycles/last`, `/api/cycles/history` | scan-autopsy | Only available when backend on :8000 is up. Optional. |
| Signal trace API | `/api/signals/{id}/trace`, `/api/signals/{id}/confluence` | trade-autopsy, confluence-trace | In-process only — backend must be running. |
| Scorer weights | `backend/strategy/confluence/scorer.py:639-686` | confluence-trace | `MODE_FACTOR_WEIGHTS` — per-mode factor weight maps |
| Cascade config | `backend/shared/config/scanner_modes.py:20-42`, `:364` | confluence-trace | `RELATIVITY_MAP` (scalp/intraday/swing tier definitions) + `cascade_trade_types` per mode |

---

## Known observability gaps (cross-reference for skills)

These were surfaced by skills running in prior sessions. Each is a candidate
fix that would make future forensic calls richer. None of the listed gaps
prevent the skills from working — they just degrade the depth of analysis.

| Gap | Where | Status | Impact |
|---|---|---|---|
| `bot_started` / `bot_stopped` events never emitted | `backend/bot/telemetry/events.py` | open | `/autopsy` resolves session via journal session_id instead of bot lifecycle event |
| `direction=null` on signal_rejected telemetry | `backend/bot/telemetry/events.py` create_signal_rejected_event | open | Skills can't compute LONG/SHORT rejection asymmetry from telemetry alone |
| `logs/confluence_breakdown.log` 0 bytes (no emit wired) | `backend/strategy/confluence/scorer.py:74` (rotating logger declared, no emit call) | open | `/confluence-trace` falls back to `convergence_missing` names only — no per-factor scores/weights on disk |
| `ml_gate` rejections not in telemetry signal_rejected | `backend/bot/paper_trading_service.py:1958` `_log_signal` w/o telemetry pair | open | Stage 8 (ML_GATE) is invisible to `/scan-autopsy` and `/rejection-survey` |
| `conflict_density` events emit `threshold=None` | `backend/engine/orchestrator.py:1685-1688` `_FORWARD_KEYS` set doesn't include `_conflict_threshold` | open | §10 mode-aware threshold check can't be done from telemetry alone (scorer.py still applies it correctly) |
| Pre-scoring gate emit-asymmetry → silent rejections | `backend/engine/orchestrator.py:1663` and siblings | **PATCHED** (commit 00d21db) | NEAR/INJ silent-drops resolved; parent-loop emit-of-last-resort catches all future silent paths |

Open-gap status is tracked in `.claude/.skill-state/` per session via the
state helper's `observability_gaps[]` section. When you patch one, write
`status=patched` so future skill invocations see it as resolved:
```
python .claude/skills/_state_helper.py write-gap <sid> <gap-id> patched "fixed in commit <sha>"
```

---

## What the skills DON'T do

Intentional non-goals, per CLAUDE.md §15:

- **Lower `min_confluence_score`.** Per-mode thresholds were tuned from session
  win-rate data. Skills surface "this is rejecting a lot" as observation, never
  as a tuning recommendation.
- **Auto-fix.** Skills are read-only. The fix step is operator-driven and
  audit-gated per §16.
- **Auto-chain end-to-end.** Each skill is invoked individually so domain
  judgment applies at each step (e.g. "is this NEAR/INJ pattern worth pulling
  on, or is it noise?"). Auto-chaining would burn signal.
- **Self-modify.** Skills detect vocabulary drift and queue it to state, but
  never patch their own SKILL.md mapping rules. The cost of a misclassified
  stage map is silent forensic errors — that's a human-judgment edit.

---

## Self-test (skill data plumbing healthy?)

If any skill returns surprising "DATA-UNAVAILABLE" or "no data found" results,
run these checks:

```
# Telemetry DB has recent rows
python -c "import sqlite3; c=sqlite3.connect('backend/cache/telemetry.db'); print(c.execute('SELECT COUNT(*), MAX(timestamp) FROM telemetry_events').fetchone())"

# Trade journal has rows
python -c "import json; print(sum(1 for _ in open('backend/cache/trade_journal.jsonl')))"

# State helper works
python .claude/skills/_state_helper.py read 'smoke-test-session'   # should print {}

# Headless autopsy
python -m backend.diagnostics.autopsy_report --quiet
```

If any of those fail, the skill chain itself is fine — the data sources are
the problem (bot not running, paper trader hasn't traded, etc.).

---

## Conventions

- All commits include trailer: `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`
- Skills are committed to `.claude/skills/<name>/SKILL.md` (project scope, not user-global)
- Diagnostics that mirror skill logic live in `backend/diagnostics/<name>.py`
- New diagnostic scripts follow the existing pattern: paste-friendly stdout,
  CI-friendly exit codes, read-only against live data sources
- Per §16 every code change to scoring/regime/execution/pre-scoring gate logic
  goes through the audit subagent's 12-point rubric before commit
