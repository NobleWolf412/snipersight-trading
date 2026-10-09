# Workflow integration pass

Baseline: `44cf732`. User authorization: review and implement workflow dead ends
so scanner, bot, market context, journal and training flows work together. ML
implementation/training, paid accounts, multi-user authentication and real orders
remain outside scope. Preserve deliberate admission/recovery safeguards.

## Execution plan

1. Restore verified market context, including source/age/error provenance, without
   substituting stale dominance or a default recommended mode.
2. Give scan jobs one durable browser-session owner across navigation/reload;
   reconnect polling, finish/persist results, and acknowledge cancellation/errors.
3. Trace fixed/paper/live setup, risk configuration, active-session discovery,
   monitoring, stop/recovery and completed journal handoffs. Repair concrete gaps.
4. Replace Settings mock connections and disconnected controls with working
   preferences and links/actions backed by the real configuration owners.
5. Make replay/training entry, progress and completion reachable. Avoid presenting
   unsupported historical macro or ML behavior as available.
6. Audit route fallbacks, exports, empty/loading/error recovery and fake live data.
   Implement bounded missing actions, label unavailable integrations honestly.
7. Run guarded backend checks, meaningful frontend tests, TypeScript, independent
   reviews and browser walkthroughs. Record verified versus unverified paths and
   update the current architecture map/evidence ledger.

## Initial confirmed findings

- CryptoCompare dominance now returns 401; expired cache cannot support advice.
  CoinGecko's documented public `/global` responds with current source timestamps.
- Scanner component owns polling and run id locally; unmount loses the workflow
  while the backend continues the scan. Cancellation ignores API errors.
- Settings presents fake linked keys, 2FA and subscription state. Notification,
  appearance and risk controls are local-only; several buttons have no handlers.
- Additional bot/journal and scanner/replay findings are undergoing independent
  source review before implementation.

## Data-source decision under review

Use a named CoinGecko global snapshot for BTC, explicitly tracked USDT+USDC, and
the remaining market. This changes the previous top-100 basket denominator;
record the source/composition version and keep its cache/history separate. Require
finite, bounded percentages, valid total capitalization and a fresh provider
`updated_at`. Do not silently switch denominators or use cached errors as data.
Existing numeric strategy thresholds are unchanged and remain uncalibrated.

Primary sources:
- [Global market data](https://docs.coingecko.com/reference/crypto-global)
- [Keyless access and rate limits](https://docs.coingecko.com/docs/errors-and-rate-limits)

Status: implementation in progress. This file is a current work ledger, not a
claim that every repository feature or exchange workflow is certified.


## Implemented workflow ownership

- Manual scans now belong to `ScanRunService` above page routes. The browser
  persists request identity, creation acknowledgment and stop intent. Unknown
  starts retry the same identity; server reuse is atomic under the job lock.
  Acknowledged missing jobs release with an explicit restart/expiry message.
  Disconnects retain ownership, failed stops stay visible, and auto-repeat is
  cancelled on stop/off and never restored automatically after browser reload.
- Completion saves one receipt with the job's actual completion time and complete
  results. Storage failure retains results in memory. Inputs show exchange,
  categories, pair limit, target override, market type, leverage and macro toggle.
  History selection, setup details and JSON export are reachable. Planner timeframe,
  actual score/eligibility, price levels and unknown provenance reach result cards.
- Bot navigation retains paper recovery/completed sessions, captures the service
  owner before reset, and fences older responses. Paper status exposes recovery,
  lifecycle work and safe-reset state. Testnet shutdown retry retains unresolved
  ownership and closes it only after the existing flatness/checkpoint barriers.
  Setup drafts contain configuration, never credentials or live-risk acknowledgment.
- Journal filtering uses UTC day boundaries, reports filtered counts and paginates
  through all matching records. CSV includes every record and heterogeneous columns.
  The chart is cumulative realized P/L, without an invented starting account balance.
- Replay serializes navigation, reconciles the actual cursor before absolute seeks,
  does not blindly retry mutations, and cleans up replaced/late sessions. Rewind from
  the end works. Missing historical macro/configuration remains explicitly unavailable;
  absent score/gate data is no longer displayed as zero/failed confirmation.
- Settings now controls the two implemented appearance preferences and links to
  actual scanner/paper/live configuration owners. Mock linked credentials, paid
  subscriptions, authentication, notification controls and disconnected risk settings
  were removed. Full journal export and status refresh are wired.
- Intel displays independently expiring regime, dominance, funding, TradFi and
  sentiment observations with sources, dates and retry. Invalid Fear & Greed values
  no longer become neutral50. Old seeded news/liquidation/AI panels were removed.
  Training uses actual paper status; ML implementation/training remains excluded.
- Legacy routes redirect to supported flows; unknown routes offer navigation.
  Footer demo connections/latencies, fake scanner setup counts/timestamps and
  synthetic bot backtest performance were removed. The latter now explains the
  historical-input limitation and links to replay inspection and forward paper testing.

## Provider decision and strategy boundary

CoinGecko global capitalization shares replace the unavailable CryptoCompare top100
basket. `coingecko-global-usdt-usdc-v1` has separate cache/history files; historical
files remain untouched. Stable share explicitly means USDT+USDC, and the remainder
includes other stablecoins. The provider observation must pass numeric, partition,
capitalization-consistency and one-hour freshness checks. Market-regime expiration
cannot outlive that observation. Concurrent reads serialize and failures back off.

This changes strategy inputs and their denominator. It does not establish that the
existing dominance/risk thresholds are calibrated for this composition. No numeric
strategy weights/cutoffs or risk limits were adjusted in this workflow pass. Global
market-cap BTC dominance is now named accurately, but forward paper evaluation of
routing and signal frequency remains necessary. A keyless request worked in the
observed runtime; official Demo documentation expects a key. Rate limits/access can
still make the feed unavailable; an optional backend `COINGECKO_DEMO_API_KEY` can be
configured by the operator. No account or key was created during this work.

## Independent review and corrections

Reviews by `mode_consistency_review`, `regime_design_review`,
`api_ownership_design` and `api_backend_integrity` were read-only/source-based.
Their findings led to fixes for lost scan-create responses, delayed creation racing
GET404, persisted acknowledgment and cancellation intent, cancellation leakage to
new runs, late response ownership, stale feed retry, first-frame replay failure,
server cursor drift and paper/testnet recovery handoffs. They did not validate
profitability or place orders. Final integrity review traced the serialization
producer/consumers and found the bounded conversion compatible.

The integrity pass also found a stale diagnostic consumer of removed dominance
helpers. Its fixture now constructs the initialized service under the guarded
runner and asserts expired cache stays unavailable. A pre-existing AST probe for
the removed free HTF bonus is explicitly retired with a pointer to the current
score-policy tests; old saved evidence is preserved.

## Browser-discovered corrections

The first actual20-pair scan completed, but its GET result returned HTTP500 because
nested rejection metadata contained a NumPy boolean. `ScanJob.to_response` now
sanitizes the whole response, including metadata/rejections. The shared converter
preserves native/NumPy booleans before integer handling, converts tuples to arrays,
and represents nonfinite numeric evidence as JSON null. The regression uses the
actual FastAPI encoder and strict JSON; original in-memory evidence is not mutated.

The cooldown display had a doubled `/api/api` prefix and stayed loading. The same
incorrect prefix was found in signal trace, confluence distribution and kill-zone
client methods. All four now use the existing API base exactly once; frontend tests
assert their actual fetch URLs. Cooldown empty responses now show an error.

## Verification checkpoints

- Guarded focused backend:175 passed before the broad run.
- Guarded full backend manifest:2477 passed,415 warnings,427.60s. This checkpoint
  preceded the browser-discovered JSON correction and diagnostic fixture changes.
- After JSON correction:357 relevant backend tests passed,2121 deselected,
  275 warnings,196.90s; scanner isolation/workflows, score policy and serialization.
- Guarded `inputs`: completed after diagnostic corrections. Its pre-existing ML
  chronology fixture is descriptive only; no training or model changes performed.
- Guarded contracts: API, telemetry and pipeline inventories clean; six existing
  JSONL drift items unchanged. Guarded smoke: five already documented mode-policy
  differences. Baselines were not replaced and these two checks did not exit clean.
- Every guarded invocation exercised seven denial probes. Network/child-process
  attempts were denied; offline writes stayed in fixtures. Runtime browser checks
  below are separate from this isolation claim.
- TypeScript and selected frontend results, final runtime checks, source hashes
  and manifest scope are recorded in the adjacent JSON evidence file.

Contract inventories omit query validation, HTTP error semantics, additive fields,
filtered counts, CSV columns, provider composition and browser state ownership.
The selected fixtures and source tracing cover those changes explicitly; green
inventory sections alone are insufficient.

## Checklist disposition and remaining limits

1. Scope: implemented bounded workflow repairs; no ML build/training or real orders.
2. Fundamentals: request/response, source time, UTC filters and actual mode DTO traced.
3. Ownership/contracts: browser scan/replay owners, separate paper/live owners,
   service publication and versioned feed caches documented above. Roll back backend
   and frontend together; old history remains readable, new source files are separate.
4. Behavior: offline success/failure/retry/concurrency tests plus bounded real browser
   walkthrough. LONG/SHORT paper-recovery and scoring fixtures passed.
5. Accounting: no historical rewrite; unknown geometry/score/fees are not invented.
   Journal remains a display of recorded historical outcomes, not a recertification
   of those old rows or their labels.
6. Verification: guarded runs and live read-only market inspection are separated.
7. Trading assumptions: provider-dependent routing/threshold calibration is unproven.
8. Completion: independent findings and fixes recorded; final evidence below. This
   is not certification of every exchange, mobile device or unexercised feature.

Scan identities survive browser navigation/reload but backend jobs remain in memory
with retention limits, not a durable exactly-once ledger across server restarts.
Replay signal backtesting remains unavailable without historical macro/configuration.
Paid/account/messaging integrations and quizzes remain unsupported. ML tools are
pre-existing experimental surfaces and remain outside this review. No automatic bot
restart or adaptive live routing was enabled. Real execution and testnet shutdown
were verified with isolated fixtures, not exchange orders.

## Final replay browser correction

The final browser pass reproduced a second defect: a ten-bar replay advance
exceeded the 30-second client timeout, although the backend later committed it.
The UI now requests and publishes successive single-bar advances, displays the
requested destination, and offers Stop moving. Backward seeks first return to
zero, then reconstruct incrementally, retaining the backend causal-prefix rules.
A newer navigation supersedes queued/ongoing display ownership. Server cursor
reconciliation still precedes every navigation; mutating POSTs are not retried.

Independent source review by `mode_consistency_review` found and verified the fix
for an ended-replay restart continuation overriding Stop. The continuation now
checks session/navigation generation and a confirmed first frame. Three added
regressions cover intermediate progress, cancellation/reconciliation, and this
ended-replay race.

Stop moving prevents subsequent requests; an in-flight server calculation may
finish and the next action reconciles its cursor. A cached rewind can recompute
bars 0–1 together; recovery after a backend computation exception can still
rebuild a longer prefix. This correction does not guarantee constant request
latency or add historical signal evaluation. The visible chart retains its last
accepted frame when a request is cancelled/superseded.

## Completed browser and build checkpoint

The repaired scan completed through the private Tailscale address after navigation
away, reload and return: 20 pairs processed, zero qualifying setups and 20 recorded
rejections (14 evidence requirements, four regime alignment, one conflict density,
one structural anchor). The result appeared in browser history with its completion
time. This observed sample is evidence of workflow completion, not strategy quality.

Final replay session `ae98aa` loaded 167 BTC/USDT one-hour bars in STEALTH. The
+10 control visibly progressed through BAR6/167 to BAR11/167 without an error;
RESET returned BAR1/167 and Escape returned READY TO LOAD. This is candle/structure
inspection only; score and confirmation gates were explicitly unavailable.

Final frontend suite: 114 passed across eight files,1.19s. Installed TypeScript
compiler exited0; production build exited0 in7.64s. The repeat contract check
retained exactly the six prior JSONL differences; API/telemetry/pipeline were clean.
Source hashes, document links, preserved historical ledger entries and git diff
whitespace checks passed. Earlier verification checkpoints above remain intact.

This bounded workflow pass is complete. Backend/UI are running locally on the
recorded ports and the Tailscale URL; both trading services were idle with zero
positions during final status checks. No bot was started or order placed for this
verification. These changes are not committed or pushed. Remaining calibration,
historical analysis, external integration and exceptional replay latency limits
are recorded above and in the adjacent machine-readable evidence.
