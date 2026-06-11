# Fix 2: Stop Liquidity Buffer — Calibration Baseline

**Date:** 2026-06-11
**Change:** `_buffer_stop_from_liquidity()` added to `risk_engine.py`. When a computed
stop is within 0.3 ATR of an EQL/EQH/PWL/PDH pool, it is pushed 0.3 ATR beyond the
pool (away from entry) before the percentage-stop gate and leverage adjustment run.

---

## Why stop-hunt proximity is the root problem

From `project_stop_placement_pwl_proximity.md` (memory, flagged for investigation):
> Stops landing inside SMC liquidity pools (PWL/PDH/EQL) get systematically swept.

The -54.73 rest_maker session autopsy (`2026-06-07__t16-reversal-gap-and-session-1993dcd5-capstone.md`)
confirmed 6/7 losers never went green (MAE 2.33% vs MFE 0.16%) — consistent with stops being
swept before the trade had time to develop, not with a failed direction thesis.

The pattern: a structurally valid stop placed at or inside an EQL/EQH cluster provides a
precise sweep target. Market makers hunt the cluster; the stop triggers; price reverses. The fix
is to push the stop THROUGH the cluster — making it harder to sweep without a genuine breakout.

---

## Why 0.3 ATR was chosen for the buffer

**Design frame:** The buffer is a clearance distance, not a scoring weight. The question is:
"How far beyond the pool must the stop be to avoid the standard sweep depth?"

A sweep typically extends 0.1–0.3 ATR below an EQL cluster before reversing — this is the
"liquidity hunt wick" range. Three reference points:

1. **OB body width**: Order blocks are typically 0.3–0.8 ATR wide. Placing a stop 0.3 ATR
   beyond a pool gives the same clearance as placing it beyond a shallow OB — an already-
   accepted SMC stop placement convention.

2. **ATR noise floor**: Crypto intraday noise (wick size) is empirically ≈0.1–0.2 ATR.
   0.3 ATR clears the noise floor with a 50% margin but does not approach 0.5 ATR (where
   the stop would be too wide for scalp/intraday geometry).

3. **Percentage-stop gate**: The existing gate rejects stops wider than 3% (scalp) / 5%
   (intraday) / 10% (swing). At BTC $100k with ATR=$1000: 0.3 ATR = $300 = 0.3% — well
   inside the 3% scalp cap. For alts at 5% ATR/price: 0.3 ATR = 1.5% of price — still
   within the intraday gate. The buffer cannot itself cause a gate rejection on normal assets.

**Why not 0.2 ATR?** Insufficient to clear the standard hunt wick (0.1–0.2 ATR noise).
**Why not 0.5 ATR?** Over-widens stops for scalp geometry; starts approaching entry-to-stop
distance for tight scalps. The existing OB freshness / structure-stop logic provides 0.5+ ATR
stops when structure genuinely requires it — the buffer should not add that magnitude.

---

## Proximity trigger (within 0.3 ATR → push)

The trigger threshold and the buffer distance are intentionally the same (0.3 ATR). This means:
- Stop already beyond 0.3 ATR of every pool: no adjustment (stop is already clear)
- Stop exactly at 0.3 ATR from pool: no adjustment (candidate = pool - buffer = current stop)
- Stop within 0.3 ATR of pool: candidate < current stop → pushed to 0.3 ATR clearance

Setting trigger = buffer is the clean design: "the stop is safe when it's at least buffer-
distance from any pool; if it's not, push it there."

---

## Forward measurement plan

After the first overnight session (2026-06-12 or later):

```python
import pathlib, json, re
lines = pathlib.Path("logs/bot_journal.jsonl").read_text().splitlines()
plans = [json.loads(l) for l in lines if '"stop_loss"' in l and "BUFFERED" in l]
print(f"Buffer fired: {len(plans)} plans")
# Examine whether buffered stops held or were still hit
```

Also check `logger.info("STOP BUFFERED:")` lines in the application log.

**Trigger thresholds:**
- Buffer fires on < 5% of plans: pool detection may be too restrictive (check key_levels populate)
- Buffer fires on > 40% of plans: 0.3 ATR proximity circle is too wide, reduce to 0.2 ATR
- Post-buffer stops still hit: extend buffer to 0.4 ATR or investigate `_find_eqh_eql_zones` tolerance

---

## Conservative properties

| Property | Value |
|----------|-------|
| ATR=0/None | Returns original stop — no inflation |
| No pools found | No change |
| Buffer widens stop past pct gate | Gate correctly rejects (by design — runs after buffer) |
| distance_atr after buffer | Recomputed; guarded against ≤0 (planner_service raises ValueError) |
| Only widens stops | Never tightens (candidate < adjusted for LONG, candidate > adjusted for SHORT) |
