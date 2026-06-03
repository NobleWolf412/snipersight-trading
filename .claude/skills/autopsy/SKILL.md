---
name: autopsy
description: Post-run triage for SniperSight. Use after a paper-trader or autonomous-bot session to find where signals died, which trades misbehaved, and what's worth investigating. Default entry point when the user says "what happened", "review the last run", "anything weird?", "autopsy the session", or runs the bot/paper trader and asks for a debrief. Walks live data sources (telemetry.db, trade_journal.jsonl, /api/cycles/last) and surfaces the 3 most interesting threads, then delegates to /scan-autopsy, /trade-autopsy, /rejection-survey, or the rejection-forensics agent for drilldown.
---

You are the triage entry point for post-run SniperSight debugging. The user just stopped the paper trader or autonomous bot and wants to know what happened. Your job is to find the threads worth pulling — not to do every drilldown yourself.

# Operating Protocol

## 0. LEAD WITH THE ONE-SHOT SCORECARD (run this first, always)

Before anything else, run the consolidated debrief and paste its output verbatim — it IS the big-picture rollup, so you don't hand-compute it or make the operator choose a drilldown:

```bash
python -m backend.diagnostics.session_debrief          # latest session (+ recent-window context if thin)
# or:  python -m backend.diagnostics.session_debrief <session_id> | --all
```

It produces, in one pass: expectancy + win-rate (overall and by **direction × regime cohort** — the with/counter-trend split), **trade-type mix** (flags scalp monoculture), **stop-branch** (structural / max-stop-cap / atr-fallback, from `stop_loss_rationale`) + median stop ATR + `tp1_clamped` reachability rate, the latest scan's **rejection-reason** ranking + direction-vs-regime mismatch, a flag list, and a **THREADS/DRILL-DOWNS** section that names the exact follow-up command per flag.

Use that THREADS section as your routing spine. Steps 1–N below are how you EXECUTE a drilldown the scorecard points you to (a specific cycle → `/scan-autopsy`, a trade → `/trade-autopsy`, a symbol's scoring → `/confluence-trace`, aggregate rejections → `/rejection-survey`, a single kill-chain → `rejection-forensics` agent). Don't re-derive the window/metrics by hand if the script already printed them — only fall through to the manual steps for data the script doesn't cover or when it errors.

Notes: read-only; tolerant of older trades missing the 2026-06-02 calc-geometry keys (they show `unrecorded` — if the whole window is unrecorded, the bot needs a restart to journal stop-branch/clamp). The live `WIDE STOP` branch log lands in `logs/backend.err.log` (or `dev_servers.log` under the concurrently launcher).

## 1. Establish the session window

**Calibration note:** `bot_started`/`bot_stopped`/`bot_cycle_completed` events are NEVER emitted in current telemetry (verified May 2026). Do not rely on them. Resolve sessions in this order:

1. **Primary:** latest `session_id` in `backend/cache/trade_journal.jsonl` (if any trades were taken). Each journal row carries `session_id` + `entry_time` + `exit_time`. Take all rows with the latest session_id and bound the window by `min(entry_time)` → `max(exit_time)`.
2. **Fallback (scanner-only):** latest contiguous cluster of `scan_started` events in telemetry (gap ≥ 30 minutes ends a cluster). Use that cluster's `[min,max]` timestamp range.
3. **User-specified:** if the user named a window ("last hour", "today", "since 2pm"), override and use that.

**Stale-journal-but-fresh-scans (calibration 2026-05-24):** if the journal's latest `last_exit` is OLDER than the latest `scan_started` timestamp by ≥30 minutes, the journal is stale (e.g. the most recent session ran the scanner but produced no trades — happens at high min_confluence_score). In that case, PREFER the scan cluster over the journal session and report both: emit `"session_id: <journal-sid> (STALE — scans newer)"` in the window line. This was the dda4d192-vs-9558a1c8 case where 8h of scanning with threshold=95 left an empty journal.

```bash
# Resolve session window — handles the stale-journal case
python -X utf8 -c "
import json, sqlite3
from datetime import datetime, timedelta

journal_sid = None
journal_last_exit = None
try:
    rows = [json.loads(l) for l in open('backend/cache/trade_journal.jsonl')]
    if rows:
        journal_sid = rows[-1]['session_id']
        in_session = [r for r in rows if r['session_id'] == journal_sid]
        journal_first = in_session[0]['entry_time']
        journal_last_exit = in_session[-1]['exit_time']
except Exception:
    pass

# Scan cluster (always compute)
c = sqlite3.connect('backend/cache/telemetry.db').cursor()
c.execute(\"SELECT timestamp FROM telemetry_events WHERE event_type='scan_started' ORDER BY timestamp DESC LIMIT 500\")
ts = [r[0] for r in c.fetchall()]
cluster_start, cluster_end = None, None
if ts:
    cluster = [ts[0]]
    for t in ts[1:]:
        if datetime.fromisoformat(cluster[-1]) - datetime.fromisoformat(t) > timedelta(minutes=30):
            break
        cluster.append(t)
    cluster_end = cluster[0]
    cluster_start = cluster[-1]

# Decide which to prefer
stale = False
if journal_sid and journal_last_exit and cluster_end:
    if datetime.fromisoformat(cluster_end) - datetime.fromisoformat(journal_last_exit) > timedelta(minutes=30):
        stale = True

print(f'journal_sid: {journal_sid}')
print(f'journal_first_entry: {journal_first if journal_sid else None}')
print(f'journal_last_exit: {journal_last_exit}')
print(f'cluster_start: {cluster_start}')
print(f'cluster_end: {cluster_end}')
print(f'stale_journal: {stale}')
print(f'PREFER: {\"scan cluster\" if stale or not journal_sid else \"journal session\"}')
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

**Tier 2 journal fields (post-Tier-2 sessions only)** — surface when present:
- `btc_velocity_1h_at_entry`, `alt_velocity_1h_at_entry`, `macro_state_at_entry`, `regime_trend_at_entry` — macro context at OPEN (not exit). Lets autopsy show "was the trade counter-macro at entry?".
- `htf_aligned_at_entry`, `setup_qualifier` (Soft/Strong/Unknown) — joins outcomes against HTF alignment + qualifier cohort.
- `targets_stripped_count`, `final_targets_remaining` — already in journal pre-Tier-2.

These fields are ADDITIVE — old journal rows (pre-Tier-2) won't have them. Treat missing fields as `None` / skip the corresponding breakdown rather than failing.

## 2a. Auto-computed analysis breakdowns (always include in output)

Compute these from `signals.jsonl` (per-session file at `logs/paper_trading/session_<sid>/signals.jsonl`) + journal rows. These three breakdowns answered questions that required manual SQL in prior autopsies (calibrated 2026-05-24 dda4d192 vs 9558a1c8 session-skew investigation):

**(a) Per-symbol direction tally** — for the session's `signals.jsonl`, tally LONG vs SHORT evaluations per symbol. Output top 15 by total volume with LONG% column. Reveals which symbols flipped direction between sessions and whether the global skew is regime-explained (same direction across most symbols) or a leak (mixed per-symbol with global skew).

**(b) Setup-type ↑/↓ breakdown** — count occurrences of `'↑'` vs `'↓'` in `setup_type` strings across all signal rows. The bot's structure detector tags HTF Bounce setups with direction arrows; this count reflects the market's structural direction-bias for the session.

**(c) Per-regime acceptance rate** — for each value of `regime` in signals.jsonl, compute `count(result==passed) / count(result in {filtered,passed})`. Reveals which regimes the bot's gates favor.

```bash
# Auto-compute breakdowns from signals.jsonl
python -X utf8 -c "
import json
from collections import Counter, defaultdict
SID = '<RESOLVED-SID>'  # filled by step 1 output
path = f'logs/paper_trading/session_{SID}/signals.jsonl'
try:
    rows = [json.loads(l) for l in open(path)]
except FileNotFoundError:
    rows = []
    print(f'NO signals.jsonl at {path}')

by_symbol = defaultdict(Counter)
for r in rows:
    by_symbol[r.get('symbol','?')][r.get('direction','?')] += 1
print('=== Per-symbol direction tally (top 15) ===')
syms = sorted(by_symbol.keys(), key=lambda s: -sum(by_symbol[s].values()))
print(f'{\"symbol\":14}{\"LONG\":>6}{\"SHORT\":>7}{\"LONG_pct\":>10}')
for s in syms[:15]:
    c = by_symbol[s]
    L, S = c.get('LONG',0), c.get('SHORT',0)
    pct = 100*L/(L+S) if (L+S) else 0
    print(f'  {s:12}{L:>6}{S:>7}{pct:>9.0f}%')

up_count = sum(1 for r in rows if '↑' in str(r.get('setup_type','')))
down_count = sum(1 for r in rows if '↓' in str(r.get('setup_type','')))
print(f'\\nSetup-type ↑/↓: ↑={up_count}  ↓={down_count}  ratio={up_count/down_count if down_count else \"inf\":.2f}')

by_regime = defaultdict(Counter)
for r in rows:
    by_regime[r.get('regime','?')][r.get('result','?')] += 1
print('\\n=== Per-regime pass-rate ===')
for regime, c in sorted(by_regime.items(), key=lambda x: -sum(x[1].values())):
    p, f = c.get('passed',0)+c.get('executed',0), c.get('filtered',0)
    total = p + f
    rate = 100*p/total if total else 0
    print(f'  {regime:18s} passed={p:5d}  filtered={f:5d}  pass_rate={rate:.1f}%')
"
```

Surface ALL THREE breakdowns in the report's `Auto Breakdowns` section (added below). If the data is missing (pre-Tier-2 session, no signals.jsonl), note it explicitly rather than omitting.

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

Auto Breakdowns
---------------
Per-symbol direction tally (top 15):
  <symbol>    <LONG>  <SHORT>   <LONG_pct%>
  ...
Setup-type ↑/↓ ratio: ↑=<n>  ↓=<n>  (=<ratio>)
Per-regime pass-rate:
  <regime>: passed=<n> filtered=<n> rate=<%>
  ...

Tier 2 Cohort Splits  (only if journal rows have Tier 2 fields)
---------------------------------------------------------------
By setup_qualifier:
  Strong  trades=<n>  win_rate=<%>  total_pnl=<usd>
  Soft    trades=<n>  win_rate=<%>  total_pnl=<usd>
  Unknown trades=<n>  win_rate=<%>  total_pnl=<usd>
By htf_aligned:
  aligned     trades=<n>  win_rate=<%>  total_pnl=<usd>
  counter-HTF trades=<n>  win_rate=<%>  total_pnl=<usd>
By macro_state_at_entry:
  <state>     trades=<n>  win_rate=<%>  total_pnl=<usd>
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
