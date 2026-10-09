# API read ownership

Independent source review identified three related ownership boundaries:
market regime reads borrow a mutable scanner engine; recommendation performs
blocking work on the event loop and borrows a global detector; replay endpoints
perform synchronous work and deletion/GC do not coordinate with active navigation.

Decision: a private market reader owns a fixed Phemex swap source, pipeline,
indicators, detectors and display cache. Display retains startup STEALTH
timeframes/profile; recommendation retains its existing weekly/daily/4h/1h/15m
context with a separate detector. Whole reads run in admitted worker threads.
The optional market endpoint symbol continues to return global context; no
symbol-specific analysis is introduced. Returned dominance must pass the existing
freshness/validity check; it is still a separate observation from cached regime.

A shared small worker gate admits one operation before submission and retains
admission until the physical worker finishes, including when its caller cancels.
Queued cancellation submits nothing. Replay uses a separate gate; cancellation
may finish a step but cannot release ownership early. Cancelled creation cleans
up its registered session after load finishes. Replay engine session locks also
coordinate navigation, status, delete and GC for direct non-route callers.

Alternatives: locking the scanner preserves dependence on its last configuration
and delays display behind scans; constructing a new orchestrator per read loses
hysteresis and adds unrelated dependencies. One shared detector would mix the
daily display and weekly recommendation inputs. Per-session async dispatchers
offer more replay concurrency but require broader lifecycle and adapter policy.
One admitted replay operation is the bounded initial choice.

Affected files: new shared worker helper and private market service; api_server,
ScannerService, replay router/engine; focused guarded tests/manifest and current
navigation/evidence. Callers are market/regime and scanner/recommendation display
routes plus replay create/status/step/jump/delete. Consumers are dashboard/mode
hints/BotSetup and training Replay. Endpoint payload shapes remain unchanged;
no score/threshold/execution logic is retuned. Roll back these ownership boundaries
together, not just the route offload.

Verification uses actual route bodies isolated from API bootstrap, fixture data
and controlled thread barriers. No exchange transport, session trading, credential
use or historical rewrites. Evidence/results are recorded after implementation.

## Reproductions and review corrections

Six original route checks failed: market display borrowed the scanner, and all
five replay operations blocked the event loop. Lifecycle checks reproduced
deletion/GC during navigation and use of a deleted captured reference; the fourth
check established the new owned status boundary. The initial repaired focused
set passed 149 cases and the first full selected run passed 1,977 cases.

Independent review then found a drain task cancelled before its first coroutine
step could strand admission and cancelled-create cleanup. A controlled injection
reproduced the timeout. Abandoned executor futures now retain completion callbacks
instead of drain tasks; cleanup completion owns release. Tests cover queued
cancellation, bounded executor submissions, late failure, cleanup execution and
submission failures. The original dominance failure cause is logged before the
handled unavailable response. Follow-up review clears both findings.

## Limits

The private reader changes a display dependency: scanner requests no longer
choose its source or timeframes. Recommendation now requires validated dominance;
missing Phemex configuration returns unavailable analysis rather than selecting
an arbitrary exchange. No detector thresholds or classification algorithms change.
Both reader contexts serialize through one admitted worker, and replay serializes
across all sessions. Future parallelism requires an explicit adapter/lifecycle
policy. API response shapes and captured contract inventories remain unchanged.

Cancellation tests cancel Python route tasks. Browser disconnect/AbortController
does not itself prove that ASGI cancels the corresponding task; lost HTTP
responses and existing non-idempotent replay POST retries remain outside this
repair. Real server shutdown, exchange recovery, multi-process routing and live
execution are unverified. Session/cache ownership is in memory, not durable
restart recovery. Dominance and cached regime may have different observation times.

## Final verification

Final selected guarded suite: **1,980 passed**, 161 existing warnings, 249.03 s.
This includes 29 new ownership/lifecycle cases beyond the 1,951-case universe
checkpoint. Four contract inventories and eight structural smoke groups are
clean after the final correction. Source syntax and diff checks pass. Independent
architecture re-review cleared both findings; backend-integrity review traced
the actual UI/diagnostic consumers and found no blocking compatibility defect.
Protected journal, telemetry, contract tool and DB baseline hashes are unchanged.
Local uncommitted work; no publication, deployment or live-readiness claim.
