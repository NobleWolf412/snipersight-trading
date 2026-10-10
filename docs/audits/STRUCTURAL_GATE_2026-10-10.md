# Structural rejection follow-up — 2026-10-10

The pasted STEALTH scan shows thirteen evidence rejections, eleven numerically
above its 65-point gate. The session activity record at 14:25:13UTC confirms thirteen
evidence failures and one conflict-density failure among fourteen scanned pairs.
The persisted ETH 69 and BTC 77.2 records both award 15 confirmation points from
Multi-Candle Confirmation while failing the separate structural-shift condition.
This is possible under the existing family policy: supporting candles can score,
but cannot replace a qualifying BOS/CHoCH. The pasted rows do not establish that
all thirteen candidates should have been admitted.

## Reproduced defects and correction

1. The four-swing detector checked only the most recent high when the sequence
   ended with a high, and only the most recent low when it ended with a low.
   A normal intervening pullback could therefore hide the opposite boundary's
   break. Both boundaries now use the latest two highs and two lows, retaining
   the existing continuation/reversal geometry and strict close crossing.
2. A separate, older initial-trend state could suppress the four-swing result.
   Four-swing geometry now owns its classification. The simple detector retains
   its own state machine and initial ranging-establishment behavior.
3. Repeated closes beyond a four-swing pivot previously reissued the same break,
   including after a first break failed volume. Each direction/pivot timestamp
   is now consumed before volume admission. A new pivot at the same price remains
   a different event. A later candle cannot upgrade the first break's grade.
4. Structural grading passed already-normalized distance and two thresholds to
   positional arguments meaning `value, atr, a_threshold`. Explicit keywords now
   supply raw price distance, actual ATR, and the existing A/B thresholds. This
   can raise or lower grades depending on timeframe; it is not a blanket easing.
   Existing volume promotion remains. Nonpositive/unknown ATR retains the prior
   C base grade. The existing `break_distance_atr` field now contains its value.
5. Rejection text now identifies either no detected aligned BOS/CHoCH on the
   allowed timeframes, or the latest event's timeframe, timestamp and weak grade.
   The existing `evidence_missing` and reason channels carry this detail through
   scanner, paper, live and UI consumers; no new rejection field is required.

Weights, score cutoffs, mode timeframes, volume requirements, opposing-wall
checks and latest-event selection were not changed. An older A-grade event does
not replace a newer weak event just to gain admission. The shared detector feeds
scoring, BOS-linked order blocks and planning; changed event inventory and grades
can therefore change plans for scanner, paper, testnet and live consumers.

## Evidence and alternatives

Four read-only Phemex BTC candle captures are stored beside this report. Each was
truncated to completed bars at 14:25UTC. The old detector emitted zero events in
all four captures; the correction emits 2/3/4/4 events on 15m/1h/4h/1d respectively.
These are 500-row chart/feed captures taken later, not the original full engine
snapshot (some engine lookbacks are 750 rows). They establish detector behavior,
not that a particular rejected trade was valid or would have profited.

Alternatives considered: lower the 65-point gate; switch STEALTH to the simple detector;
search older swing windows until a pattern passes. None addresses the actual
omission while preserving mode intent. The correction keeps the four-swing
requirement and evaluates both boundaries of the latest geometry.

The [verification record](STRUCTURAL_GATE_2026-10-10.json) contains failure/pass
counts, source hashes, capture summaries, independent review and runtime limits.
All 561 selected guarded backend regressions passed, including detector, scoring,
rejection consumers and the synthetic serial-worker scanner-to-paper workflow.
Contract inventories retain six pre-existing writer differences; smoke retains
five pre-existing mode-policy differences. Neither baseline was overwritten.
The running paper session was not restarted. Its fresh per-scan worker processes
loaded the corrected source: at 14:40UTC a TAO rejection included the latest 15m
CHoCH grade C detail, BTC reached the separate pullback check, and BNB had a pending
simulated limit. These later observations do not reconstruct the pasted scan.

## Remaining limits

The precomputed swing detector still has documented confirmation-time/look-ahead
limitations; this change does not certify causal historical availability. Structural
freshness/invalidation and selecting the latest event across different timeframes
also require separate policy work. Scores remain uncalibrated and candle-based
confirmation points remain distinct from the mandatory structural eligibility
test. Existing contract/smoke baseline drift is recorded without replacing the
baselines. No live session or real exchange order was initiated by this work.
