# Raw-candle workflow verification and root repairs

The user requested the best next verification order after clarifying that the
previous paper pass began at a supplied scanner result. This batch joins the
existing legacy policy and STEALTH/balanced paper wrapper to actual ingestion,
indicators, SMC, macro/regime analysis, gates, scores, cascade planning, risk,
paper entry/management, account values and journal publication.

The input tape is deterministic synthetic OHLCV, aggregated from one five-minute
series into five timeframes. Seed 2, 500 days, frozen clock 2025-12-03 15:00 UTC;
the LONG fixture has a 0.012 log-price impulse, the reflected SHORT fixture 0.010.
These are deliberately selected coverage scenarios, not historical observations,
strategy calibration or performance evidence. Dominance, precision, volume and
quotes are explicit input fixtures. Existing policy/gates/weights are not stubbed.
Workers pickle arguments and results but execute serially. The unused model-store
boundary remains untrained in the paper fixture; no ML artifact is loaded.

## Confirmed defects and decisions

1. `LiquidityPool.is_fresh` subtracts UTC-aware candle timestamps from naive local
   time, aborting plan metadata; HTF level scoring has the same incompatible age
   calculation. Compare in UTC and interpret legacy naive candle times as UTC.
   Existing seven-day rounding and future-time behavior are unchanged.
2. FVG formation treats the middle candle's entire range as unwanted overlap.
   A continuous displacement body therefore rejects the very first/third candle
   gap it creates. Ten raw-candle cases failed before repair; two wick-only
   rejection controls passed. Count middle-candle **wicks**, consistent with the
   existing configuration description. Keep ATR/overlap constants, grading and
   later mitigation unchanged. This increases real pattern supply and can change
   anchor admission, scores and entry geometry. Mirrored boundary/partial-retest
   tests cover the distinction between formation and subsequent mitigation.
   Updated the frontend FVG lesson and research copy to describe wick overlap
   and the configured allowance, removing the misleading universal 10% claim.
3. Worker construction reapplies mode defaults after the parent resolves settings.
   Five cases failed before repair, including stricter RR/stop overrides and the
   existing paper balanced 65/55 preset being evaluated at 70. Construct using a
   copy, then restore the resolved snapshot in place so service references agree.
   Retain the source while using its identity as a cache key; mode changes rebuild.
   Cached refresh and mode-change cases are covered. No preset values changed.

An explicit constructor for resolved configuration or a value-keyed worker cache
would be alternatives. They are broader changes than preserving the existing
dispatch contract. Ordinary process-pool tasks are separately unpickled, so the
identity cache does not promise one initialization per process lifetime.

## Verification and limits

The joined tests cover LONG/SHORT stop and profitable target settlement, missing
critical timeframes and absent structural anchors. They assert all five indicator
sets, populated macro/regimes/SMC/HTF levels, real risk validation, effective config,
position geometry and exact cash-to-journal agreement with no duplicate outcome.
Focused regressions cover 27 timestamp, 18 FVG and seven worker-config cases.
Use the guarded runner with `backend -k core_workflow` or the complete selected
manifest. Exact full-suite results and source hashes live in the system audit's
`raw_candle_workflow` evidence/coverage entries.

This does not certify process spawning/concurrency, real exchange transport,
UI/API startup, all policies/modes, automatic session restoration or strategy edge.
The existing cycle branch remains unavailable and logged; no unmeasured cycle
input was activated. The recorded CSV was used for discovery but its gaps and
zero-volume bars make it unsuitable as the healthy positive fixture.

Additional observations remain open: worker-local indicator/SMC failures are not
fully aggregated into parent feature counters; generic planner rejection and
unknown-direction reporting lose detail. Existing universe/API ownership and
causal-cycle design work remain in the prioritized system report.

Shared scanner/bot consumers receive these detection/configuration corrections;
no live executor, mode definition, threshold constant, historical store or schema
baseline is changed. Roll back the four production modules with their tests and
documentation as one bounded batch. Do not interpret clean contract inventories
as proof of unchanged signal behavior.
