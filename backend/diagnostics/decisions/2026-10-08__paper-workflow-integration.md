# Paper workflow integration

The user approved verifying the existing scanner/bot lifecycle and explicitly
excluded ML work. Project-era strategy assumptions are not authority for this
follow-up. No thresholds or strategy inputs were recalibrated.

Joined fixtures reproduced 14 failures in the original code: wrong stop-fill
prices, partial exits treated as complete, admission after fills, entry remainders
reopening closed positions, unstable journal retry P&L, and paper shutdown without
execution. Two additional cases exposed equity double-counting while reductions
were pending. Both LONG and SHORT are exercised.

Decision: reuse the manager's existing cumulative-receipt lifecycle for paper.
A partial market reduction retains its order and logical slice; it commits at the
cumulative execution price when complete. Account values and status views use
actual filled holdings meanwhile. Per-fill manager settlement would require a
different target-allocation/retry contract; disabling simulated partial fills would
remove the case instead of repairing ownership.

Entry plans are retained before immediate execution and through adoption errors.
The simulator checks the position cap before filling, cancels entry remainders
before reducing, and refuses fills on cancelled/rejected orders. Market remainders
below 1% now complete like existing limit remainders, preventing an endless partial
fill tail; fee rates and configured fill probabilities are unchanged. Shutdown performs
bounded execution retries, retains failed work, and blocks reset/start from erasing
unresolved exposure or publication. Final cash P&L is frozen per position so a
journal retry or a new same-symbol trade cannot consume a different accumulator.

Affected flow: scanner-result handoff, signal admission, PaperExecutor fills,
PositionManager callbacks, direction flips, stop, journal publication, account
status, sizing/drawdown and session checkpoints/reports. Production source changes
are limited to paper_trading_service.py and paper_executor.py. Existing testnet
execution dispatch remains; live executor, manager implementation, scanner scoring,
thresholds, frontend and ML files are untouched.

Verification: 50 new integration cases, 1,741 selected backend tests, four clean
contract inventories and eight clean smoke categories. The guarded runner provides
`backend -k paper_workflow` for focused reproduction. The full run is recorded in
the system audit ledgers. Contract capture does not inventory every dynamic JSON
field: the optional `state.json.paper_execution` forensic object is explicitly
documented and tested here, not implied by the clean contract comparison.

Limits: scanner results and quotes are supplied fixtures; no exchange was used.
Cold restart reopens the journal and preserves an inspectable checkpoint but does
not automatically resume paper trading. No actual data-store repair, deployment,
ML operation or historical performance claim is included.

Rollback boundary: revert the two paper source files together with the integration
test, verification manifest/filter, and accompanying docs/ledger entry. The new
checkpoint field is additive; existing journals and contract baselines were not
migrated or rewritten.
