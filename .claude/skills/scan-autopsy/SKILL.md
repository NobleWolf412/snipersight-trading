---
name: scan-autopsy
description: Walk a single SniperSight scan cycle stage-by-stage and report where signals died. Use when the user names a run_id or asks "what happened in that cycle", "trace this scan", "why did scan X return nothing". Inputs: a run_id (or "last" for most recent). Walks UNIVERSE → DATA → CRITICAL_TF → FEATURES → CONFLUENCE → PLANNER → RISK → ML_GATE → REGIME → POSITION_CAPS → EXECUTION with per-stage entered/passed/rejected counts, mass-conservation check, and rejection reason breakdown. Different from /rejection-survey (aggregate across cycles) and rejection-forensics agent (single signal deep-dive).
---

You are the per-cycle pipeline tracer for SniperSight. Given a single scan cycle, walk every pipeline stage and show what entered, what survived, what got killed, and why.

# Operating Protocol

## 1. Resolve the run_id

User provides a `run_id` (e.g. `e4099705`) or `"last"`.

For `"last"`:
```bash
python -c "
import sqlite3
c = sqlite3.connect('backend/cache/telemetry.db').cursor()
c.execute(\"SELECT run_id FROM telemetry_events WHERE event_type='scan_completed' ORDER BY timestamp DESC LIMIT 1\")
print(c.fetchone()[0])
"
```

If the run_id doesn't exist in telemetry, halt and ask the user to confirm — do not guess.

## 2. Pull the cycle heartbeat (preferred path)

The orchestrator emits a per-cycle heartbeat with stage counts. Get it via:

```bash
curl -s 'http://localhost:8000/api/cycles/last?include_audit=true'   # if last
# or query backend.engine.cycle_heartbeat for a specific run_id
```

The heartbeat returns:
- `symbols_scanned` (universe size)
- `signals_per_stage` (dict: stage → count rejected)
- `plans_emitted` (final count)
- `wall_ms`, `bottleneck_stage`
- `failed`, `exception_class` (if cycle failed)
- Drift status (if include_audit) — OK or DEGRADED

If backend isn't reachable, fall back to building the same view from telemetry events for that run_id.

## 3. Walk the 11 stages

For each stage in this canonical order (mirrors `backend/routers/observability.py:164-180`):

| # | Stage | Owner | Observed gate_name / reason |
|---|---|---|---|
| 1 | UNIVERSE | `backend/analysis/pair_selection.py` | (universe drops are pre-telemetry — get from `/api/universe`) |
| 2 | DATA | `backend/data/...` ingestion | reason contains `no_data` / `stale` |
| 3 | CRITICAL_TF | `orchestrator._check_critical_timeframes` | gate_name=`critical_timeframes`, reason="Missing critical timeframes: ..." |
| 4 | FEATURES | indicator / SMC services | reason contains `indicator_` / `smc_` |
| 5 | CONFLUENCE_SCORE | `strategy/confluence/scorer.py` | gate_name=`confluence_score`, reason="Below minimum confluence threshold"; also `structural_anchor`, `btc_impulse`, `regime_alignment`, `conflict_density` |
| 6 | PLANNER | `strategy/planning/` | gate_name=`risk_validation` with reason="No trade plan generated"; reason=`trade_type_mismatch` |
| 7 | RISK_VALIDATION | `strategy/risk/` | reason=`insufficient_rr`, geometry failures |
| 8 | ML_GATE | edge model | (model-specific — observe `ml_` prefix in reason) |
| 9 | REGIME | `analysis/regime_policies.py` | reason contains `regime` |
| 10 | POSITION_CAPS | `bot/executor/position_manager.py` | reason in {max_positions, has_position, pending_order} |
| 11 | EXECUTION | `bot/executor/paper_executor.py` | gate_name=`post_plan_revalidation` (reason=`revalidation_price_drift`); also `stale_entry`, `position_size`, `price_fetch`, `pending_fill`, `errors` |

**Stage mapping rule (calibrated against live vocabulary May 2026):**

```python
def map_to_stage(reason: str, gate_name: str | None) -> str:
    # gate_name is the canonical key when set
    if gate_name == "critical_timeframes":        return "CRITICAL_TF"
    if gate_name == "confluence_score":           return "CONFLUENCE_SCORE"
    if gate_name == "risk_validation":            return "PLANNER"  # "No trade plan generated"
    if gate_name == "post_plan_revalidation":     return "EXECUTION"
    if gate_name in ("structural_anchor", "btc_impulse",
                     "regime_alignment", "conflict_density"):
        return "CONFLUENCE_SCORE"  # pre-scoring gates count as confluence-stage kills
    # Fallback: pattern-match reason text
    r = (reason or "").lower()
    if "trade_type_mismatch" in r:     return "PLANNER"
    if "insufficient_rr" in r:         return "RISK_VALIDATION"
    if "no trade plan" in r:           return "PLANNER"
    if "no_data" in r or "stale" in r: return "DATA"
    if r.startswith("indicator_") or r.startswith("smc_"): return "FEATURES"
    if r.startswith("ml_"):            return "ML_GATE"
    if "regime" in r:                  return "REGIME"
    if r in ("max_positions","has_position","pending_order"): return "POSITION_CAPS"
    if r in ("stale_entry","position_size","price_fetch","pending_fill","errors"): return "EXECUTION"
    return "UNKNOWN"
```

If the `UNKNOWN` bucket grows > 5% of total rejections, flag it as a calibration miss — the vocab has drifted and this skill needs an update.

Telemetry query:

```sql
SELECT json_extract(data_json, '$.reason')    AS reason,
       json_extract(data_json, '$.gate_name') AS gate,
       COUNT(*) AS n
FROM telemetry_events
WHERE event_type='signal_rejected' AND run_id=?
GROUP BY reason, gate
ORDER BY n DESC;
```

## 4. Mass-conservation check (REQUIRED)

Per CLAUDE.md §14 rubric 3, every cycle must satisfy:

```
universe_size == plans_emitted + sum(rejections_per_stage)
```

If this fails, flag MASS-CONSERVATION-VIOLATION with the delta. This is one of the highest-priority signal-loss bugs to surface (it means a symbol disappeared without a reason code).

## 5. Bottleneck identification

The stage with the largest rejection count is the bottleneck. Also flag:
- **Stage with 100% rejection rate** (everything that reached it died there)
- **Stage where rejections > prior-5-cycle median by 2×** (relative metric per rubric 5; pull prior 5 via `/api/cycles/history?n=5`)

## 6. Sample rejected signals (top 3 per dominant stage)

For the bottleneck stage, pull 3 example rejected signals with their reason + symbol so the user has concrete cases. Include the signal_id when available (lets them follow up with rejection-forensics or /api/signals/{id}/trace).

# Output Format

```
SCAN AUTOPSY — run_id <id>
==========================
Mode: <mode>  Profile: <profile>  Wall: <ms>ms
Cycle started: <utc>   Cycle status: OK | FAILED:<exception_class>
Drift audit: OK | DEGRADED — <reason>
Mass conservation: OK | VIOLATED (delta=<n>)

Headline
--------
<one sentence: bottleneck stage + dominant reason>

Stage Funnel
------------
Stage              Entered  Passed  Rejected  TopReason
UNIVERSE           <N>      <N>     <N>       <reason>
DATA               <N>      <N>     <N>       <reason>
CRITICAL_TF        <N>      <N>     <N>       <reason>
FEATURES           <N>      <N>     <N>       <reason>
CONFLUENCE_SCORE   <N>      <N>     <N>       <reason>
PLANNER            <N>      <N>     <N>       <reason>
RISK_VALIDATION    <N>      <N>     <N>       <reason>
ML_GATE            <N>      <N>     <N>       <reason>
REGIME             <N>      <N>     <N>       <reason>
POSITION_CAPS      <N>      <N>     <N>       <reason>
EXECUTION          <N>      <N>     <N>       <reason>
                                              ─────────
Plans emitted: <N>

Bottleneck
----------
Stage: <stage>
Rejection rate: <pct>% (vs prior-5 median <pct>%)
Dominant reason: <reason> (<count>, <pct>% of stage)

Rejection Breakdown (top 10)
----------------------------
<reason>           <count>   <pct>%   <stage>
...

Sample Killed Signals (top 3 at bottleneck)
-------------------------------------------
<symbol>  direction=<long|short>  reason=<reason>  metric=<value>
<symbol>  direction=<long|short>  reason=<reason>  metric=<value>
<symbol>  direction=<long|short>  reason=<reason>  metric=<value>

Recommended Follow-up
---------------------
- <action>: e.g. "run rejection-forensics on <symbol> <mode>"
- <action>: e.g. "check `scorer.py:104` if conflict_density dominates"

Raw Evidence
------------
SQL queries used:
  <query 1>
  <query 2>
Cycle heartbeat:
  <pasted JSON>
```

# Cross-skill state (read gaps + write drift / mass-conservation)

**On entry** — surface known observability gaps for this cycle's session
(if a session_id can be resolved via timestamp). Resolve session via the
most recent journal session_id as fallback when timestamp matching is
ambiguous:

```bash
SID=$(python -c "import json; rows=[json.loads(l) for l in open('backend/cache/trade_journal.jsonl')]; print(rows[-1]['session_id'] if rows else '')")

python .claude/skills/_state_helper.py list-gaps "$SID"
```

If gaps mention paths relevant to this cycle (e.g.
`ml-rejections-not-in-telemetry`, `breakdown-log-zero-bytes`), surface
them in the Calibration findings section so the operator sees the
known-gap context, not just this cycle's findings in isolation.

**On exit** — record any drift or gap you observed:

```bash
# Vocabulary drift — if UNKNOWN bucket > 5% or new gate_name appeared
python .claude/skills/_state_helper.py write-drift "$SID" "<reason>" "<gate_name>"

# Mass-conservation violation — record as a gap so the next /autopsy sees it
python .claude/skills/_state_helper.py write-gap "$SID" \
    "mass-conservation-cycle-<run_id>" \
    open \
    "scan_completed.signals_rejected=<X> but signal_rejected events=<Y>; delta=<Z>"
```

State is a memory layer (CLAUDE.md §11) — your analysis still runs
fresh every invocation; state only adds cross-skill context.

# Hard Rules

- **One cycle, one run_id.** This skill is per-cycle. For cross-cycle aggregation, use `/rejection-survey`. For a single signal, use the `rejection-forensics` agent.
- **Live data only.** Telemetry DB + `/api/cycles/...`. Do NOT use `backend/diagnostics/cycle_heartbeat_audit.py` as the data source — it may be out of date. Treat it as a reference pattern at most.
- **Mass-conservation violation is the highest-priority finding.** If one fires, surface it in the headline regardless of bottleneck size — a missing symbol without a reason code is the §11 silent-bug class.
- **Mode-aware conflict_density.** If CONFLUENCE_SCORE shows conflict_density rejections, verify the threshold used matches mode (5 for overwatch/macro_surveillance, 3 elsewhere — CLAUDE.md §10). Mismatch = STANDING-FIX-SUSPECT.
- **Relative metrics, not absolutes.** Compare rejection rates to prior-5 median via `/api/cycles/history?n=5`. Don't invent absolute thresholds.
- **Cite file:line.** When pointing at a code path (gate, planner, executor), use [filename.py:line](path) so the user can jump.
- **No emoji. Read-only.**
