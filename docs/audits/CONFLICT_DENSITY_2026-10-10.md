# Conflict-density correction — 2026-10-10

This follow-up addresses the user's SOL, ETH, XRP, SPCX and ONDO rejections.
It builds on the separate [structural detector correction](STRUCTURAL_GATE_2026-10-10.md).
The recorded [scan 400 rejection summaries](conflict_density_2026-10-10/rejections_scan_400.json)
contain the actual conflict lists. They do not contain complete SMC snapshots,
so they cannot reproduce every original admission decision.

## Findings and bounded changes

The old conflict gate counted every opposing BOS in the snapshot. ONDO's four
reported conditions were one 1h and three 4h bearish BOS records. Four historical
records do not establish four simultaneous conditions. The corrected projection
selects the latest structural timestamp on each allowed timeframe across **both
BOS and CHoCH**, then counts at most one opposing BOS state. A newer aligned BOS
or CHoCH replaces earlier opposition. An opposing CHoCH remains excluded from
this count, preserving the previous distinction between reversal and continuation.
Conflicting equal-time events conservatively retain one opposing BOS condition
and are labeled explicitly. No arbitrary age expiry was introduced.

Initial and flip calls previously counted all loaded timeframes, while cascade
calls supplied a scope. The shared gate now resolves explicit scope first,
then effective config.structure_timeframes, then the selected mode's defaults.
Case is normalized; an explicitly empty scope remains empty. Gates 1–3 retain
their existing timeframe behavior; this repair scopes the conflict projection.

Opposing A/B order blocks now exclude invalidated, breaker and fully mitigated
zones. Duplicate/nested zones across detector families and timeframes share one
condition when their overlap exceeds 50% of the smaller range. This reuses the
existing overlap boundary symmetrically. Every member must overlap every other
member; a bridging zone cannot merge disjoint obstacles. Source snapshots are
not changed. Mode freshness remains owned by SMC detection. Zone positions
relative to a ticker or a future limit entry were not given a new admission rule.

Labels now show OrderBlock.low/high, rather than nonexistent bottom/top fields,
and structural event times. Rejection reasons distinguish the number of opposing
timeframe states and distinct zones and show the applicable base limit.

The legacy score winner can differ from the direction that passed pre-scoring
gates, including after a preliminary flip. The orchestrator now validates the
actual winner once before planning, comparing it with the admitted direction.
There is no second flip/scoring loop. Final rejection carries the actual side
and score; initial rejection carries the known preliminary side instead of
UNKNOWN. Thesis direction ownership remains unchanged.

## Threshold and strategy boundary

The base blocking limits remain 3 for STEALTH/STRIKE/SURGICAL and 5 for OVERWATCH.
The existing BTC-aligned exception still allows fewer than 6 conflicts only when
the quality-override guard permits it. The same exception applies at final-side
revalidation; other failed gates cannot use that exception. Score weights,
score cutoffs, risk limits and execution permissions are unchanged.

Changing count units changes the effective selectivity despite retaining the
numbers. These limits are design policies, not statistically calibrated optima.
Tests prove that 3/5/6 boundaries remain reachable and enforced; they do not prove
trade profitability. One BOS state plus its associated order block can still
contribute two different evidence types. Their causal link is not retained by
the snapshot, and they must not be described as independent statistical votes.

ETH's three original labels span three different timeframes, so duplication alone
does not establish that its rejection was wrong. Its latest full structural state
would be needed. XRP's opposite-side regime rejection and DOGE's immediate FVG
entry obstruction are separate gates; this work does not remove them.

## Callers, consumers and verification

Producers are SMCDetectionService and the BOS/OB detectors. The conflict projection
is shared by initial, opposite-side retry, cascade and changed-final-direction
checks. ScannerService retains rejections; paper/live scan wrappers and telemetry
already preserve conflict_count, conflict_conditions, direction, score and reason.
The new policy/scope/state/zone metadata is internal to GateResult; no new public
schema or claim of externally persisted structured fields is made. UI stage
classification uses reason_type and remains compatible with the new wording.

Synthetic baseline tests reproduced history inflation and the direction bypass.
The saved public BTC candles used by the prior audit also exercise the actual
detector plus corrected projection: historical opposing BOS counts 2/2 (LONG/SHORT)
become one current state on each side. This is a later capture truncated to a
completed-bar cutoff, not a replay of the user's original full scan.

Exact commands, test totals, source hashes, contract drift and review evidence are
recorded in [the verification record](CONFLICT_DENSITY_2026-10-10.json).
The current checklist was applied to scope, configuration, chronology, ownership,
direction symmetry, diagnostic propagation and guarded verification. Independent
source review found no blocking defect. No frontend change requires a TS build.

No session was restarted, no order was requested and no history/baseline was
rewritten. Existing worker processes can load changed source on later scans;
offline checks do not certify the active process's complete module version.
Remaining risks include detector pivot-confirmation causality, structural-state
expiry, broader score-direction heuristics and paper calibration of corrected
counts. These remain distinct from the reproduced counting/wiring defects.
