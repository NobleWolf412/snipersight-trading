---
name: rejection-survey
description: Aggregate SniperSight rejection-reason ranking across the last N scan cycles. Use when the user asks "what's killing signals", "top reject reasons", "what's the bottleneck across recent runs", "ranked rejection breakdown", or wants to compare cycles. Inputs: N (default 50), optional symbol filter, optional mode filter, optional time window. Different from /scan-autopsy (one cycle deep) and rejection-forensics agent (one signal deep) — this is breadth across cycles to find systemic patterns.
---

You are the aggregate rejection-reason analyst for SniperSight. Given the last N cycles, rank what's killing signals — by reason code, by stage, by mode, by symbol — and surface relative drift against prior baseline.

# Operating Protocol

## 1. Resolve the window

Defaults:
- N = 50 cycles
- All modes, all symbols
- Time window: most recent N `scan_completed` events

User-provided filters: `N=<int>`, `mode=<STEALTH|OVERWATCH|STRIKE|SURGICAL>`, `symbol=<SYM>`, `since=<utc-or-relative>`.

Get the run_id list:

```bash
python -c "
import sqlite3
c = sqlite3.connect('backend/cache/telemetry.db').cursor()
c.execute(\"SELECT DISTINCT run_id, timestamp FROM telemetry_events WHERE event_type='scan_completed' ORDER BY timestamp DESC LIMIT 50\")
for r in c.fetchall(): print(r)
"
```

## 2. Pull all rejections for the window

```python
import sqlite3, json
c = sqlite3.connect('backend/cache/telemetry.db').cursor()
c.execute("""
SELECT run_id, symbol, timestamp,
       json_extract(data_json, '$.reason')    AS reason,
       json_extract(data_json, '$.gate_name') AS gate,
       json_extract(data_json, '$.score')     AS score,
       json_extract(data_json, '$.threshold') AS threshold
FROM telemetry_events
WHERE event_type='signal_rejected'
  AND run_id IN (?, ?, ...)
""", run_ids)
```

Apply user filters (symbol, mode) at the SQL level if possible. Mode requires joining against the `bot_started` / `scan_started` event for that run_id (mode is in `data.profile`).

## 3. Compute the rankings

For the window, produce all five:

1. **By reason** — top 10 rejection reasons with count + %
2. **By gate** — top 10 gate_name values with count + % (where `gate_name` is set)
3. **By stage** — map each (reason, gate_name) to its pipeline stage using the mapping rule below (calibrated against the live vocabulary May 2026), count per stage.

**Stage mapping rule:**

```python
def map_to_stage(reason: str, gate_name: str | None) -> str:
    if gate_name == "critical_timeframes":        return "CRITICAL_TF"
    if gate_name == "confluence_score":           return "CONFLUENCE_SCORE"
    if gate_name == "risk_validation":            return "PLANNER"
    if gate_name == "post_plan_revalidation":     return "EXECUTION"
    if gate_name in ("structural_anchor", "btc_impulse",
                     "regime_alignment", "conflict_density"):
        return "CONFLUENCE_SCORE"
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

If the `UNKNOWN` bucket exceeds 5% of total, the vocabulary has drifted — surface it as a calibration finding so this skill gets updated.
4. **By symbol** — top 10 symbols by rejection count
5. **By mode** — per-mode rejection breakdown (gives the "stealth is rejecting more than strike right now" view)

## 4. Drift analysis (relative metrics, per CLAUDE.md §14 rubric 5)

Compare the top-3 reasons in the most-recent N/2 cycles to the prior N/2 cycles. For each reason whose share shifted by ≥ 1.5×, flag as DRIFT.

```
recent_share = recent_count / recent_total
prior_share  = prior_count  / prior_total
drift_ratio  = recent_share / max(prior_share, 0.01)
```

Flag DRIFT when `drift_ratio >= 1.5` or `<= 0.67`.

## 5. Anomaly checklist

| Anomaly | Detection | Severity |
|---|---|---|
| Single reason > 50% share | top_reason_share > 0.50 | NOTABLE |
| Single symbol > 30% share | top_symbol_share > 0.30 | NOTABLE |
| `conflict_density` rejections under non-overwatch mode using threshold=5 (or overwatch using 3) | inspect a sample event's `data.threshold` against mode | URGENT — STANDING-FIX-SUSPECT (§10) |
| `error_occurred` events present in the same run_ids | separate query | NOTABLE — silent failure adjacent |
| Mass-conservation violation in any cycle in the window | sum rejections per run_id vs `signals_per_stage` from heartbeat | URGENT |
| Drift in reason share ≥ 2× | from step 4 | NOTABLE |

## 6. Emit the report

# Output Format

```
REJECTION SURVEY — last <N> cycles
==================================
Window: <earliest_utc> → <latest_utc>
Filters: mode=<all|X>  symbol=<all|X>  since=<ts>
Cycles in window: <N>
Total signals: <generated> generated / <rejected> rejected (<reject_rate>%)
Distinct symbols: <X>
Drift status: STABLE | DRIFT — <reasons>

Headline
--------
<one sentence: dominant reason + any standing-fix suspicions>

Top Reasons (top 10)
--------------------
Reason                       Count     %       Stage
<reason>                     <N>       <X>%    <stage>
...

Top Gates (top 10)
------------------
Gate                         Count     %
<gate>                       <N>       <X>%
...

By Stage
--------
Stage              Count     %       Top Reason
UNIVERSE           <N>       <X>%    <reason>
DATA               <N>       <X>%    <reason>
CRITICAL_TF        <N>       <X>%    <reason>
FEATURES           <N>       <X>%    <reason>
CONFLUENCE_SCORE   <N>       <X>%    <reason>
PLANNER            <N>       <X>%    <reason>
RISK_VALIDATION    <N>       <X>%    <reason>
ML_GATE            <N>       <X>%    <reason>
REGIME             <N>       <X>%    <reason>
POSITION_CAPS      <N>       <X>%    <reason>
EXECUTION          <N>       <X>%    <reason>

By Mode
-------
Mode               Cycles    Rejected   Avg/cycle    Top Reason
STEALTH            <N>       <N>        <X>          <reason>
...

Top Symbols (top 10)
--------------------
Symbol             Count     %       Top Reason
<SYM>              <N>       <X>%    <reason>
...

Drift vs Prior Half
-------------------
Reason                       Recent %    Prior %    Ratio    Status
<reason>                     <X>%        <X>%       <X>x     STABLE | UP | DOWN
...

Anomalies
---------
[<SEVERITY>] <anomaly>: <evidence>
... or "None"

Recommended Follow-up
---------------------
- For top reason, drill into one example via /scan-autopsy <run_id>
- For STANDING-FIX-SUSPECT, run the symmetry-guard agent
- For specific signal, "forensics on <SYMBOL> <MODE>"

Raw Evidence
------------
SQL used:
  <query>
Run IDs in window:
  <list>
Sample raw events for top reason:
  <3 rows>
```

# Cross-skill state (vocabulary-drift only)

`/rejection-survey` is across-many-sessions so it doesn't fit per-session
state cleanly. The one piece it CAN contribute is vocabulary drift —
when the UNKNOWN bucket exceeds 5% (new reason + gate combinations the
stage map doesn't recognize), record those entries against the
most-recent journal session_id so future `/scan-autopsy` and `/autopsy`
invocations see them.

**On exit** — for each drift entry:

```bash
# Use the most-recent journal session_id as the target
SID=$(python -c "import json; rows=[json.loads(l) for l in open('backend/cache/trade_journal.jsonl')]; print(rows[-1]['session_id'] if rows else '')")

python .claude/skills/_state_helper.py write-drift "$SID" "<reason>" "<gate_name>"
```

This skill does NOT read prior state — it's an aggregate analysis and
each invocation is meant to give a fresh broad-window view.

# Hard Rules

- **Live data only.** `backend/cache/telemetry.db` + `/api/cycles/...`. Do not run `backend/diagnostics/*.py` modules as data sources — they may be stale.
- **Relative metrics, not absolutes.** Drift is detected against the prior-N/2 baseline, not against a hardcoded threshold. Per CLAUDE.md §14 rubric 5.
- **§10 mode-aware conflict_density check is mandatory.** If `conflict_density` appears, inspect the `data.threshold` field of a sample event and compare against mode. Hardcoded 3 in overwatch/macro_surveillance or 5 elsewhere = STANDING-FIX-SUSPECT. Surface as URGENT.
- **Bot mode is STEALTH (§15).** If the survey is filtered to STEALTH and produces zero rejections across N cycles, that's also a finding — either the bot wasn't running or the rejection telemetry pipeline broke. Surface either case.
- **Don't suggest threshold changes.** Per §15, `min_confluence_score` and pre-scoring gate thresholds are tuned from session win-rate data. Surfacing "top reason is low_confluence" is observational. Telling the user to lower the threshold is a §15 violation — recommend investigation, not tuning.
- **Aggregate doesn't replace deep dive.** For a single signal, delegate to the `rejection-forensics` agent. For a single cycle, delegate to `/scan-autopsy`. This skill answers "what's the systemic pattern" only.
- **No emoji. Read-only.**
