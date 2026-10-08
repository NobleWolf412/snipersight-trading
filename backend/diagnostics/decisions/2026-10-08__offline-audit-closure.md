# Offline audit closure: explicit inputs, risk bounds and evidence limits

The user authorized continuing bounded sessions without further check-ins. Work
remains local under the original no-orders/credentials/deployment/destructive
operations boundary. No additional commit or push was made during this pass.

## Volatility and final paper/testnet sizing

D19 requires finite ATR and positive price in common percentage units. Missing
price must not activate absolute-ATR thresholds or manufacture normal volatility.
Preserve existing percentage bands; reference-TF calibration is separate work.
The planner bridge passes its current price. Eighteen focused cases pass.

D20 treats configured risk as a ceiling. Streak/sensitivity/regime inputs may
reduce it; a favorable regime cannot raise it. A synthetic $1,000 account at 1%
risk and 1.2 multiplier previously produced $12 planned loss. Re-evaluate after
snapping/precision using the farther planned/native stop, current equity/free
margin, and downward quantity precision. Sixty focused cases cover both sides,
actual order-block wiring and invalid inputs. Existing accounting fixture now
includes the real required risk field; its margin expectation is unchanged.

Upstream: session risk settings, account observation, plan geometry and public
market precision. Downstream: paper/testnet order quantity, native stop request,
manager adoption and recorded risk activity. No execution protocol is replaced.
The bound excludes fees, gaps and slippage. Alternative of merely clamping the
regime helper leaves later geometry/precision unverified. Revert initial/final
sizing and their tests together if the contract changes.

Fusion state initializes before the scoring try-body so early failures retain
their original rejection instead of throwing a second exception in finally.
This changes failure reporting, not selection weights or dormant cycle logic.

## Verification isolation incident and correction

The earlier temporary broad pytest guard covered Python open writes but omitted
sqlite3.connect. Default TelemetryStorage uses the actual source-relative DB;
some tests appended there. Read-only investigation identified 130 test-time rows
(IDs 2992099–2992228): 128 info messages and two TEST/USDT alt-stop events.
The exact ID/payload-hash manifest is
`docs/audits/SYSTEM_DISCOVERY_2026-10-07_test_telemetry.json`.
No pre-run full DB hash exists, so do not claim every historical byte unchanged.
Earlier blanket untouched-store claims are explicitly superseded in the audit.
No rows were deleted or historical data repaired. The protected trade-journal
hash remains unchanged. Exclude the exact manifest IDs for historical analysis.

The portable offline wrapper now clears configuration, redirects default
telemetry before consumer imports, rejects SQLite paths/URIs outside fixtures,
and denies external writes, credentials, transport and subprocesses. It checks
seven denial events without performing those operations. Integer descriptor
wrapping of already opened fixture files and temporary/in-memory SQLite are
supported. It is an accidental-side-effect guard for trusted Python checks,
not a sandbox for hostile native extensions.

The first stricter wrapper exposed descriptor/SQLite URI handling errors, then
18 test/setup failures from the real default telemetry path. Fixing the wrapper
and redirecting storage restored 1,691 passes without weakening the external DB
guard. Four contract groups and eight smoke categories are clean. Frontend's
last relevant verification is 36 tests and clean TypeScript. CI now propagates
smoke/lint/Vitest failure; no GitHub run or full lint pass is claimed.

## Disposition, not speculative strategy changes

Controlled probes reproduce global-trend bonus field mismatch, strong-down
substring precedence, mixed cached/dynamic policy flags, universe
selected/excluded overlap, and reverse-time ML folds. Current code traces also
show conditional ML weak labels, synchronous/shared API context work, dormant
cycles, observational CVD/OI, proxy macro fields and repeated trend evidence.

These require different decisions: do not activate extra score weight, change
universe semantics against existing backfill tests, retrain saved models, or
retune regime bands merely to clear the list. The current audit contains concrete
next batches, verification and rollback for each, and distinguishes confirmed
defects from architecture risks, calibration hypotheses and missing evidence.
No bulk deletion was justified by the inventory. The architecture index is a
navigation aid with explicit coverage limits; the original product is preserved.
