---
name: trade-autopsy
description: Post-mortem a single closed paper trade in SniperSight. Use when the user names a trade_id or asks "why did this trade lose", "post-mortem trade X", "this winner is suspicious", "what made this fire and exit", or "what went wrong on <symbol>". Inputs: trade_id (or "last", "last-loss", "last-win"). Pulls trade_journal.jsonl + matching telemetry signal_generated event + confluence breakdown, classifies the exit, and flags anomalies (high-confidence loss, orphan/stagnation exits, regime mismatch at entry, missing kill-zone alignment).
---

You are the per-trade post-mortem for SniperSight paper trading. Given one closed trade, reconstruct: what made it fire, what happened during it, why it closed, and whether anything looks wrong.

# Operating Protocol

## 1. Resolve the trade

Inputs accepted:
- Full `trade_id` (e.g. `DOT/USDT_1778670315.388812`)
- `"last"` — most recent closed trade
- `"last-loss"` — most recent trade with `pnl < 0`
- `"last-win"` — most recent trade with `pnl > 0`
- `<symbol>` — most recent closed trade for that symbol

Trade source: `backend/cache/trade_journal.jsonl` (one JSON row per trade).

```bash
# Last closed trade
tail -1 backend/cache/trade_journal.jsonl
# Last losing trade
python -c "
import json
rows = [json.loads(l) for l in open('backend/cache/trade_journal.jsonl')]
losses = [r for r in rows if r.get('pnl', 0) < 0]
print(json.dumps(losses[-1], indent=2) if losses else 'none')
"
```

## 2. Extract the trade vitals

From the journal row, capture:

- `trade_id`, `symbol`, `direction`, `entry_price`, `exit_price`, `quantity`
- `entry_time`, `exit_time`, duration
- `pnl`, `pnl_pct`, `max_favorable`, `max_adverse`
- `exit_reason` — one of: `target`, `stop_loss`, `max_hours_open`, `stagnation`, `orphan_price_feed_failure`, `session_stopped`, or `EMERGENCY: <reason>`
- `targets_hit` (list of target indices)
- `trade_type` (`scalp` | `intraday` | `swing`)
- `confidence_score` (0–100)
- `conviction_class` (e.g. A/B/C)
- `plan_type` (e.g. `SMC`)
- `risk_reward_ratio`
- `stop_distance_atr`
- `timeframe`, `regime`, `pullback_probability`
- `kill_zone`, `session_id`

## 3. Match to the originating signal

The journal row doesn't carry a signal_id. Match via `(symbol, entry_time)`:

```python
import sqlite3, json
from datetime import datetime, timedelta, timezone
c = sqlite3.connect('backend/cache/telemetry.db').cursor()
# Window: ±2 minutes around entry_time
entry_dt = datetime.fromisoformat(trade['entry_time'])
lo = (entry_dt - timedelta(minutes=2)).isoformat()
hi = (entry_dt + timedelta(minutes=2)).isoformat()
c.execute("""
SELECT timestamp, run_id, data_json
FROM telemetry_events
WHERE event_type='signal_generated' AND symbol=?
  AND timestamp BETWEEN ? AND ?
ORDER BY timestamp DESC
""", (trade['symbol'], lo, hi))
candidate = c.fetchone()
```

If a match is found, pull the confluence breakdown via `/api/signals/{id}/confluence` if a signal_id is recoverable, or via the `confluence_breakdown` field cached in `live_trading_service.signal_log` (if accessible).

If no match within ±2min, expand to ±10min and try again. If still nothing, mark the signal lineage as MISSING and proceed — that's itself an anomaly worth surfacing.

## 4. Classify the exit

| exit_reason | Classification | Expected? |
|---|---|---|
| `target` | EXPECTED-WIN | Yes — the plan worked |
| `stop_loss` | EXPECTED-LOSS | Yes — the plan was wrong but the geometry caught it |
| `max_hours_open` | TIMEOUT | Suspect — review TF vs plan_type |
| `stagnation` | STAGNATION-STRIKE | Suspect — stagnation strikes counter fired |
| `orphan_price_feed_failure` | INFRA-FAILURE | Suspect — price feed lost the symbol, not a market decision |
| `session_stopped` | OPERATOR-EXIT | Out of scope — user stopped the bot |
| `EMERGENCY: <reason>` | EMERGENCY-EXIT | Highest priority — surface as urgent |

## 5. Anomaly checklist

Flag any of:

| Anomaly | Detection | Severity |
|---|---|---|
| High-confidence loss | `pnl < 0 AND confidence_score >= 80` | NOTABLE |
| Conviction A loss | `pnl < 0 AND conviction_class == 'A'` | NOTABLE |
| Low-confidence win | `pnl > 0 AND confidence_score < 60` | INFO (luck or undervalued setup) |
| Orphan / stagnation / emergency exit | exit_reason in {orphan_price_feed_failure, stagnation, EMERGENCY:*} | URGENT |
| Risk-off regime at entry | `regime` ∈ risk-off labels (check `regime_policies.py`) | NOTABLE |
| No kill-zone alignment | `kill_zone == "no_session"` for a STEALTH/STRIKE scalp | INFO |
| Stop distance was outside mode's typical | `stop_distance_atr` < 0.3 or > 2.0 | NOTABLE |
| Max adverse > stop distance (slippage) | `max_adverse > stop_distance_atr` | NOTABLE |
| Signal lineage MISSING | No signal_generated telemetry match | URGENT (silent-bug class) |
| Direction asymmetry pattern (this and prior 5 trades all same direction) | Check last 5 closed trades — if 5/5 same direction with mixed regimes, possible §10 symmetry leak | NOTABLE |

## 6. Emit the report

# Output Format

```
TRADE AUTOPSY — <trade_id>
==========================
Symbol: <SYMBOL>  Direction: <LONG|SHORT>  Type: <scalp|intraday|swing>
Entry: <price> @ <utc>  Exit: <price> @ <utc>  Duration: <hms>
PnL: <usd> (<pct>%)  Mode: <regime at entry>  Session: <session_id>
Exit classification: EXPECTED-WIN | EXPECTED-LOSS | TIMEOUT | STAGNATION-STRIKE | INFRA-FAILURE | OPERATOR-EXIT | EMERGENCY-EXIT

Headline
--------
<one sentence: what happened, severity>

Signal Lineage
--------------
signal_generated event: <FOUND at <ts>, run_id=<run>> | MISSING
confidence_score: <X.X>  conviction: <A|B|C>  plan_type: <SMC|...>
risk_reward_ratio: <X.X>  stop_distance_atr: <X.XX>
regime at entry: <label>  kill_zone: <zone>  pullback_probability: <X.XX>

Trade Lifecycle
---------------
max_favorable: <X.XX>%  max_adverse: <X.XX>%
targets_hit: [<indices>]
exit_reason: <reason>

Anomalies
---------
[<SEVERITY>] <anomaly>: <evidence>
[<SEVERITY>] <anomaly>: <evidence>
... or "None"

Verdict
-------
<one paragraph: was this trade defensible? did the system behave as designed?
 if INFRA-FAILURE or signal MISSING, what subsystem to investigate>

Recommended Follow-up
---------------------
- <action>: e.g. "run rejection-forensics on <SYMBOL> <MODE> with timestamp <entry_ts> to verify the gate path"
- <action>: e.g. "run /scan-autopsy <run_id> to see the cycle that produced this signal"

Raw Evidence
------------
Journal row:
  <pasted JSON>
Matched telemetry signal_generated:
  <pasted JSON> | "no match within ±10min"
Confluence breakdown:
  <pasted from /api/signals/{id}/confluence or signal_log> | "not recoverable"
```

# Cross-skill state (read prior verdict + write your own)

**On entry** — check whether this trade was already autopsied:

```bash
python .claude/skills/_state_helper.py read <session_id> 2>/dev/null | grep -A2 "trade-<trade_id>"
```

If a prior finding exists with `thread_key = trade-<trade_id>`, surface
the prior verdict in your Headline section. Then RE-RUN the analysis
fresh — state annotates, doesn't replace (CLAUDE.md §11). If your fresh
analysis disagrees with the prior verdict, flag it explicitly: "Prior
call returned X; fresh analysis returns Y — investigate divergence."

**On exit** — record your verdict so future `/autopsy` invocations
surface this trade as resolved:

```bash
python .claude/skills/_state_helper.py write-finding \
    <session_id> \
    trade-<trade_id> \
    trade-autopsy \
    <classification> \
    "<one-line summary>"
```

Where `<classification>` is your Exit-classification result:
EXPECTED-WIN, EXPECTED-LOSS, TIMEOUT, STAGNATION-STRIKE, INFRA-FAILURE,
OPERATOR-EXIT, EMERGENCY-EXIT (use the EXPECTED-LOSS-NO-BUG variant
when the geometry was correct and the trade was simply a market miss).

# Hard Rules

- **Live data only.** `backend/cache/trade_journal.jsonl` and `backend/cache/telemetry.db`. The legacy `paper_trading.db` is gone — do not look for it.
- **Don't grade the strategy.** Your job is to verify the *system* worked as designed, not to opine on whether the trade idea was good. "Score 85, lost to stop_loss" is not necessarily a system bug — it's the geometry working. The bug is if score 85 lost to `orphan_price_feed_failure`.
- **Signal MISSING is the most important anomaly.** A trade fired without a telemetry trail = silent bug per CLAUDE.md §11. Always surface it.
- **Symmetry suspicion threshold = 5/5 same direction with mixed regimes.** Don't fire on a single asymmetric trade; that's noise.
- **For deep "why did this fire" forensics, delegate.** The `rejection-forensics` agent owns single-signal deep dives. You own the trade lifecycle view.
- **Bot is STEALTH (§15).** If the matched signal was generated in any other mode and went live, that's a §15 hard-boundary violation — escalate.
- **No emoji. Read-only.**
