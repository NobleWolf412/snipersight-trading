# Worker diagnostics and terminal rejection ownership

The next priority after raw-candle verification is preserving evidence across the
worker/parent and planning-attempt boundaries. This changes reporting, not entry,
score, risk, threshold or candidate-selection rules. ML remains outside scope.

## Reproduction and design

Fifteen initial regressions failed: the worker returned only plan/rejection, so
parent feature diagnostics stayed empty; cached workers retained previous records;
position-sizing errors reused a previous risk reason; cascade attempts shared stale
failure metadata; planner/risk terminal records omitted the already chosen side.

The internal worker return is now `(plan, rejection, diagnostics)`. Both successful
and failed calls export a detached per-symbol snapshot. The parent merges it once.
Public `scan` and `_process_symbol` returns remain pairs. Diagnostic occurrences
can coexist with a generated signal and do not increase rejected-symbol totals.
The existing legacy FEATURES rollup remains an occurrence count, not a disjoint
rejection bucket. Service-level crashes retain both partial timeframe evidence
and the fatal service error.

The planner keeps its plan-or-None return and gains an optional caller-owned
`rejection_details` output. Clean entry-depth and unreachable-TP1 declines, plus
existing error rejection sites, preserve their cause. Standalone callers retain
their existing telemetry behavior. Orchestrated scans own the terminal rejection:
failed candidates remain in cascade attempt evidence and warning/error logs;
a later successful candidate must not leave a rejected-symbol event behind.
Post-plan price revalidation follows the same ownership rule.

Each cascade scale clears previous failure metadata before running, records its
own cause, and retains the chosen LONG/SHORT direction. When all scales fail,
the terminal event includes the attempts. Risk validation clears its last failure
before every call and records sizing failures explicitly. Failures before side
selection remain UNKNOWN; the paper rejection wrapper now preserves that value
instead of manufacturing LONG. The separate live-service fallback is unchanged.

## Alternatives and blast radius

A typed worker result could replace the triple but would broaden the change.
A shared diagnostics queue adds ordering, lifecycle and duplicate-delivery risk.
A typed planner outcome or decline exception would require more caller changes
than an optional evidence output and would alter the established None-return API.

Scanner API/service, paper/live scanning and backtests use the worker path.
Replay and direct diagnostic callers retain `_process_symbol`'s pair. Parent
diagnostics, persisted scan summaries, the HUD rejection panel and telemetry
forensics receive the repaired evidence. No live executor or actual order is
required. This is a shared scanner change, not a live execution certification.

## Downstream corrections found during independent review

The first symmetry review found four additional planner error-event sites that
still bypassed caller ownership. They now return evidence to orchestrated callers
while standalone callers retain their events. Both-direction tests cover all
sites, counting all rejection events rather than filtering away mismatched run IDs.

The integrity review found that the HUD's OTHER bucket and compact scan summary
counted legacy `features` occurrences again as rejected signals. Both now reserve
that key for diagnostic occurrences. Feature samples render timeframe/stage and
safe error strings. Post-plan revalidation is classified as planning in the trace
route and HUD; unknown directions have neutral colors in the gauntlet and tracer.
No new endpoint, decision gate or strategy threshold was added.

A final consumer trace found a runtime blocker: the heartbeat copied diagnostic
occurrences into `signals_per_stage`, violating terminal outcome conservation and
raising after an otherwise completed scan. Two focused before-tests reproduced
both accepted and rejected cases. Heartbeat construction now excludes the reserved
`features` rollup before computing counts and bottleneck; its conservation assertion
remains active. All 12 fault-injection integration cases now use the real
`scan_with_heartbeat` wrapper and verify the stored snapshot, not just `scan`.

The guarded full run also caught a replay test double missing the existing SMC
service diagnostics property. The fixture now supplies it; the as-of assertion
remains unchanged.

## Verification and limitations

Focused regressions cover cached worker reuse across symbols/runs, serialization,
partial/startup failures, real parent aggregation, LONG/SHORT terminal failures,
cascade rejection then success, clean planner declines and persistence retry.
The existing guarded core workflow checks remain part of the selected suite.
Exact final counts, artifacts and source hashes are in the system audit's
`worker_rejection_evidence` ledger entry. Contract inventories and smoke checks
must pass without replacing their baselines.

The serial pickling pool verifies payload delivery, not operating-system process
isolation, transport or concurrent execution. Synthetic scenarios are not market
calibration. The referenced full audit rubric is absent, so focused independent
reviews cannot certify that unavailable rubric. No real history is rewritten.
The existing live-service missing-direction fallback remains outside this paper
reporting change. The trace endpoint still reads the live service buffer; shared
API ownership remains a separate priority. A failed telemetry write can leave a
fallback cache observation before a retry; retry eligibility is tested, not global
exactly-once telemetry under storage failure.

Rollback the orchestrator and planner-service changes together with their worker
contract tests; reverting only one side would break result unpacking. The paper
wrapper, trace mapping and HUD corrections accompany this same evidence change.
