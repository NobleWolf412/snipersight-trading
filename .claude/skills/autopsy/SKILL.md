---
name: autopsy
description: Post-run triage for SniperSight. Use after a paper-trader or autonomous-bot session to find where signals died, which trades misbehaved, and what's worth investigating. Default entry point when the user says "what happened", "review the last run", "anything weird?", "autopsy the session", or runs the bot/paper trader and asks for a debrief. Walks live data sources (telemetry.db, trade_journal.jsonl, /api/cycles/last) and surfaces the 3 most interesting threads, then delegates to /scan-autopsy, /trade-autopsy, /rejection-survey, or the rejection-forensics agent for drilldown.
---

You are the triage entry point for post-run SniperSight debugging. The user just stopped the paper trader or autonomous bot and wants to know what happened. Your job is to find the threads worth pulling — not to do every drilldown yourself.

# Operating Protocol

## 1. Establish the session window

**Calibration note:** `bot_started`/`bot_stopped`/`bot_cycle_completed` events are NEVER emitted in current telemetry (verified May 2026). Do not rely on them. Resolve sessions in this order:

1. **Primary:** latest `session_id` in `backend/cache/trade_journal.jsonl` (if any trades were taken). Each journal row carries `session_id` + `entry_time` + `exit_time`. Take all rows with the latest session_id and bound the window by `min(entry_time)` → `max(exit_time)`.
2. **Fallback (scanner-only):** latest contiguous cluster of `scan_started` events in telemetry (gap ≥ 30 minutes ends a cluster). Use that cluster's `[min,max]` timestamp range.
3. **User-specified:** if the user named a window ("last hour", "today", "since 2pm"), override and use that.

```bash
# Primary: last session_id from journal
python -c "
import json
rows = [json.loads(l) for l in open('backend/cache/trade_journal.jsonl')]
if rows:
    sid = rows[-1]['session_id']
    in_session = [r for r in rows if r['session_id'] == sid]
    print('session_id:', sid)
    print('first_entry:', in_session[0]['entry_time'])
    print('last_exit:', in_session[-1]['exit_time'])
    print('trade_count:', len(in_session))
else:
    print('no trades in journal')
"

# Fallback: latest scan_started cluster
python -c "
import sqlite3
c = sqlite3.connect('backend/cache/telemetry.db').cursor()
c.execute(\"SELECT timestamp FROM telemetry_events WHERE event_type='scan_started' ORDER BY timestamp DESC LIMIT 200\")
ts = [r[0] for r in c.fetchall()]
# cluster: walk backwards, end on a >30min gap
from datetime import datetime, timedelta
cluster = [ts[0]]
for t in ts[1:]:
    if datetime.fromisoformat(cluster[-1]) - datetime.fromisoformat(t) > timedelta(minutes=30):
        break
    cluster.append(t)
print('cluster:', cluster[-1], '->', cluster[0], f'({len(cluster)} scans)')
"
```

## 2. Pull session-level vitals

For the session window, gather:

- **Scans:** `scan_started` / `scan_completed` counts, average wall_ms, any with `failed=true`
- **Signals:** `signal_generated` count, `signal_rejected` count by `reason`
- **Bot decisions:** `position_opened`, `position_closed` (with `exit_reason`), `stop_loss_hit`, `partial_taken`
- **Risk:** `risk_limit_hit`, `daily_loss_limit_hit`
- **Errors:** `error_occurred` (with `error_type`) and `warning_issued`
- **Symmetry:** count of LONG vs SHORT signals — gross asymmetry (>3:1) is a §10 standing-fix red flag

Trade PnL comes from `backend/cache/trade_journal.jsonl` filtered by `session_id` (each row has it). Required fields per row: `trade_id`, `symbol`, `direction`, `entry_price`, `exit_price`, `pnl`, `pnl_pct`, `exit_reason`, `confidence_score`, `regime`.

## 3. Run the anomaly checklist

Flag any of the following as a thread worth pulling:

| Anomaly | How to detect | Delegate to |
|---|---|---|
| Symmetry leak (LONG/SHORT count grossly skewed) | LONG count / SHORT count ratio > 3 or < 0.33, with N ≥ 20 signals | `symmetry-guard` agent |
| Single rejection reason dominates (>50%) | Top reason / total rejections > 0.5 | `/rejection-survey` |
| Specific signal user expected | User named it OR signal flagged manually | `rejection-forensics` agent |
| A trade lost with high confidence_score (≥80) | trade_journal row, pnl<0, confidence_score≥80 | `/trade-autopsy <trade_id>` |
| Exit reason `orphan_price_feed_failure` or `stagnation` strikes | Either appears in trade_journal | `/trade-autopsy <trade_id>` |
| A scan cycle's heartbeat is DEGRADED | `/api/cycles/last?include_audit=true` returns DEGRADED envelope | `/scan-autopsy <run_id>` |
| Mass-conservation violation in a cycle | `plans_emitted + sum(signals_per_stage) != symbols_scanned` from heartbeat | `/scan-autopsy <run_id>` |
| `error_occurred` events present | Telemetry query | Report inline (don't delegate) |
| Bot mode mismatch (per §15: bot is always STEALTH) | `bot_started.data.mode != 'STEALTH'` | Halt + warn the user |

You are NOT exhaustively re-running each drilldown. You are picking the **top 3 threads** and naming the skill/agent that owns each.

## 4. Emit the report

Use the Output Format below verbatim. §12 paste-friendly: short summary first, structured detail second, raw data last.

# Output Format

```
SESSION AUTOPSY — <session_id or window>
========================================
Window: <start_utc> → <end_utc> (<duration>)
Mode: <STEALTH|OVERWATCH|STRIKE|SURGICAL>  Profile: <profile>
Verdict: CLEAN | NOTABLE | INVESTIGATE

Headline
--------
<one sentence: what happened, where attention is needed>

Vitals
------
Scans: <total> (<failed_count> failed, avg <wall_ms>ms)
Signals: <generated> generated / <rejected> rejected (<accept_rate>%)
Symmetry: LONG <count>  SHORT <count>  (ratio <X:Y>) [OK | SKEWED]
Trades: <opened> opened / <closed> closed
PnL: <total_usd> (<win_count>W / <loss_count>L, <win_rate>%)
Errors: <count> error_occurred, <count> warning_issued
Drift: cycle audit <OK | DEGRADED — reason>

Top 3 Threads
-------------
1. <thread title> — <one-line evidence>
   → run /<skill or agent> <args>
2. <thread title> — <one-line evidence>
   → run /<skill or agent> <args>
3. <thread title> — <one-line evidence>
   → run /<skill or agent> <args>

Exit-Reason Distribution
------------------------
<reason>: <count>  (<pct>%)
...

Top Rejection Reasons (top 5)
-----------------------------
<reason>: <count>  (<pct>%)
...

Raw Evidence
------------
<query snippets, telemetry row IDs, trade_ids — only what backs the headline + threads>
```

# Cross-skill state (read-on-entry, no write)

Before composing the report, read this session's prior cross-skill findings:

```bash
python .claude/skills/_state_helper.py read <session_id> 2>/dev/null
# or just the findings list:
python .claude/skills/_state_helper.py list-findings <session_id>
```

For each thread you would surface in "Top 3 Threads", check if a prior
finding exists with a matching `thread_key`. If so, ANNOTATE the thread
with the prior verdict — DO NOT silently prune it:

```
1. [PRIOR: trade-autopsy → EXPECTED-LOSS-NO-BUG] High-confidence loss — DOT/USDT conf=90.1
   evidence: pnl=-27.31 exit=stop_loss
   verdict: cleared by /trade-autopsy <ts>; re-listing for completeness, no follow-up needed
```

The user sees both fresh triage and prior resolutions — annotation is a
MEMORY layer, not a CONTROL layer (CLAUDE.md §11 prefer-loud-failures).
A skill that hides resolved threads from triage masks regressions.

`/autopsy` itself does NOT write findings — it triages, drilldowns
resolve. So no write step for this skill.

Thread-key conventions for matching:
  trade-autopsy  → `trade-<trade_id>`
  scan-autopsy   → `cycle-<run_id>`
  confluence-trace → `confluence-<symbol>`

# Hard Rules

- **Don't drill down inside /autopsy.** When you find a thread, NAME the skill or agent that owns it. The user wants triage breadth, not depth — depth is what the focused skills are for.
- **Live data only.** `backend/diagnostics/` modules and root-level `*_diagnostic.py` scripts are **potentially stale**. Read from `backend/cache/telemetry.db`, `backend/cache/trade_journal.jsonl`, and the `/api/...` endpoints. Treat any diagnostic script's output as suspect unless you've sanity-checked it against the live sources.
- **Relative metrics over absolutes.** Per CLAUDE.md §14 rubric 5: compare against prior-N median, not arbitrary thresholds. The N=5 cycle median is available via `/api/cycles/history?n=5`.
- **§10 standing-fix watch.** If you see hardcoded conflict_density=3 in any code path tied to overwatch/macro_surveillance, or absolute-ATR in regime classification, raise STANDING-FIX-SUSPECT inline.
- **Bot mode is STEALTH (CLAUDE.md §15).** If `bot_started.data.mode` is anything else, treat as urgent.
- **No emoji.** Greppable plain text only.
- **Read-only.** Don't write code, don't mutate config, don't run any non-read-only script.
- **Cite file:line.** When you reference a code path (regime detector, scorer gate, position manager exit), include a clickable ref so the user can jump.
