# Preserve UTC timestamps across ingestion and regime validation

The authorized restart after `eb2b420` exposed a missed integration boundary:
`/api/market/regime` returned 503 because Phemex converts millisecond epochs to
timezone-naive UTC datetimes, while the new regime validator requires aware
timestamps. Ingestion already treated naive values as UTC for candle closure,
but discarded that conversion before publishing the dataframe.

Normalize the copied timestamp column to UTC before deduplication and gap
filling. This retains the established exchange interpretation, preserves the
instants in aware feeds, and prevents daylight-saving changes from shifting the
daily or weekly grid. Both the published index and timestamp column now retain
UTC; raw adapter input remains untouched. Do not relax regime freshness,
continuity, history-depth or completed-candle requirements.

The affected path is adapter -> ingestion -> cache -> indicator/SMC/regime and
scanner/paper/live/replay consumers. Cache expiry already interprets naive values
as UTC. SMC freshness and replay normalize event instants; sessions explicitly
convert to Eastern. VWAP daily grouping becomes consistently UTC-based. JSON
timestamps may gain an explicit `+00:00`, which the inspected UI consumers accept.
Restart discards old in-memory cached frames.

Nine regression cases exercise actual fetching/normalization followed by regime
validation across 4h, daily and weekly candles, using naive UTC, aware UTC and
America/New_York input. Before the fix, six cases failed and three passed. After
the fix, all nine pass within 87 focused guarded checks. Independent source review
found no blocker; broader selected verification is recorded in the audit ledger.

The subsequent runtime check reached the external dominance dependency. Its
CryptoCompare market-cap endpoint now returns HTTP 401 with "API key required";
the retained local cache is expired. Regime advice therefore remains unavailable
until a working authenticated source is configured. No expired dominance value,
fabricated regime or automatic default mode was substituted. Provider migration
and credential configuration are not part of this timestamp correction.
