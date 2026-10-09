# Scoring and confidence correctness — 2026-10-09

The user requested a deep review and implementation of scoring/confidence fixes.
The baseline is the existing working tree on `ace4bc3`, including earlier repairs,
not a clean checkout. ML work, order submission and runtime restarts are excluded.
This batch repairs reproducible software defects; it does not establish predictive
value or a probability of profit. Weights, point constants and preset values stay
unchanged. Some outputs and admission/sizing decisions deliberately change below.

## Defects and decisions

| Defect / before | Implemented behavior |
|---|---|
| Neutral MACD gave SHORT +8 across three TFs; equal DI gave SHORT +20 while LONG got zero | Explicit rising/falling and greater/less comparisons; equality is neutral |
| Strict MACD gave strengthening LONG 43, mirrored SHORT 35, weakening SHORT 43 | Negative expansion strengthens SHORT; mirrored scores are 43/43 and 35/35 |
| Three closes were counted oldest first: `[99,101,102]` at support 100 scored zero, `[101,102,99]` could score 70 | Count the consecutive streak backward from the latest closed candle; mirrored tests cover both sides |
| A NaN regime score could clamp to maximum strength | Nonfinite/out-of-range regime scores raise, including through the full scorer; absent regime remains distinct |
| Compressed sideways aliases STRIKE/OVERWATCH scored 60, canonical profiles 50 | Aliases use canonical baseline (50); existing fusion using `strike` therefore also loses that inconsistent extra factor bonus |
| Published fields omitted coverage, clamps and compression; raw +15 StochRSI became +49.95 in the descriptive field | Additive `metadata.score_components` records every actual delta; daily StochRSI raw adjustment remains descriptive, already included through its weighted factor |
| HTF modifiers could change 69→71 while state/tier still described 69; penalties had the reverse problem | Reclassify after service adjustments; record requested and capped actual deltas. READY/B use existing one-decimal scanner/paper gate comparison; explicit zero stays zero |
| Thesis could choose SHORT but retain LONG's 80-point breakdown over SHORT's 40 | Thesis chooses before gates; forced selection retains the correct complete breakdown, side-specific HTF and reversal evidence. FLAT abstains before scoring. Legacy selection stays in place |
| Counter-HTF rejection discarded the chosen side and fell through to UNKNOWN/errors | Typed rejection carries selected side, its score and `counter_htf` cause; existing `low_confluence` category remains compatible |
| Conflict recovery could undo structural direction | Thesis forbids opposite retries; the existing BTC-confirmed same-direction allowance below six conflicts remains unchanged |
| Paper startup, scan and entry resolved presets/floors differently; live constructor could raise balanced 65 to mode 70 | One resolver at all bot stages: explicit gate/floor, named preset, custom mode fallback. Explicit gate without floor uses a ten-point band. Resolved values survive `apply_mode` |
| Drawdown “tightening” could reduce custom 80/75 to 72/62; kill zones could undo tightening | Component-wise maximum with the risk threshold; no kill-zone relaxation during drawdown tightening. A zero floor stays zero |
| Scanner cards read wrong history fields and seeded HIGH/MED/LOW from symbol characters | Read canonical score, direction, pair and price fields. Unknown score displays unavailable; unknown direction is not invented. Card/notification scores say /100, and radar/console use the recorded gate decision on 0–100 scale; missing scores stay absent through conversion/storage |

## Ownership and alternatives

The scorer owns raw directional arithmetic. Its JSONL now explicitly labels
`stage=directional_scorer` and records the raw components. ConfluenceService owns
direction selection and post-score adjustments. Its chosen breakdown and final
metadata reach the planner; `TradePlan.confidence_score` uses this total. The API's
dataclass serialization retains the metadata for scan history and UI consumers.
The process-local confluence cache is populated by live signal logging only and stores the attached final breakdown; scanner/paper/replay do not populate it. Neither this cache nor raw scorer JSONL reconstructs complete final decision history.

`raw_directional_scores` is separate from the selected, adjusted alternative-score
diagnostics. The unselected side remains preliminary, not a counterfactual final
trade score. No historical logs are rewritten.

An immutable resolved session configuration would be stronger than restoring
caller thresholds after mode defaults, but entails broader lifecycle/worker
changes. A typed pair of fully adjusted directional scores would better separate
policy from scoring, but entails broader service and rejection contracts. The
bounded resolver and optional thesis direction repair preserve current consumers.

The named gate presets remain conservative 72/62, balanced 65/55 and aggressive
58/48. Custom without an explicit gate uses the mode gate for both bots (STEALTH
70); live previously used an inconsistent 65 fallback. Invalid settings reject
before bot initialization. Explicit floor wins even under a named preset.

## Evidence and limitations

The initial 33 math regressions produced **21 failures and 12 existing passes**.
After correction, joined service tests cover both directions, ties, clipped
positive adjustments, counter-HTF penalties, explicit zero, rounded boundaries,
full-scorer arithmetic and invalid regime evidence. Pipeline tests run the actual
symbol controller, pre-score gates and service with supplied indicator/SMC scores,
observe the planner input, and cover FLAT, opposite retries, BTC allowances and
legacy selection. Paper-entry fixtures verify full/half/rejected sizing for both
sides. Startup tests execute the real configuration blocks/Orchestrator while
excluding credentials, executors and background tasks. They do not certify a
real session startup or exchange execution.

Independent review compared 12,600 classification cases and 2,430 arithmetic
fixtures, confirmed nine unchanged weight/cap/multiplier groups, and found issues fixed before completion: swallowed regime validation, rounded label
boundaries, accidentally removed same-direction BTC recovery, and rejected-side evidence loss. Two additional mirrored rejection regressions reproduced UNKNOWN/errors before that repair. Original
floating arithmetic ordering was retained to avoid incidental threshold drift.

The first full selected-suite run passed 2,082 tests and failed four AST-only live-reconciliation cases because their injected namespace lacked the new pure resolver dependency. Updating that fixture to use the actual resolver and mode lookup made all four pass; no application rule was relaxed.

Frontend review additionally caught converter-to-zero coercion and a raw-versus-rounded UI gate mismatch. Missing/nonfinite scores now remain optional through JSON history, without a derived conviction label. `metadata.score_gate_passed` carries the backend comparison; older records use a one-decimal fallback, including exact half-even quarter ties. This additive boolean was verified in the final focused run after the full-suite checkpoint.

Final check results and source hashes are appended under `scoring_confidence` in
both system-discovery ledgers. Prior checkpoint results remain historical.

Unresolved policy/calibration questions are explicit:

- Scores are heuristic rankings. No held-out outcome calibration or profit claim.
- Normalization uses emitted factors; optional absence changes the denominator.
  Changing this requires an availability and calibration policy.
- The existing MACD veto factor can score 100 when data are unavailable. No veto
  and confirmed directional alignment differ; missing-data scoring needs a
  deliberate baseline, rather than an arbitrary replacement score.
- The global HTF bonus still reads a different shape than MarketRegime provides;
  this batch does not activate an extra correlated +5 bonus.
- Paper's near-miss band generally cannot admit new legacy candidates because
  upstream orchestration already applies the full gate. Tests supplying near-miss
  plans establish consumer behavior only. Live retains its hard score gate even
  in thesis mode, and its raw comparison differs from scanner/paper rounding.
- Some policy consumers reread the process flag, optional structures depend on
  ordering, and directional BTC penalties differ. These need explicit policy and
  measured evidence; they were not silently homogenized.
- Synthetic charts/setup/regime visuals remain disclosed prototype elements.
  Old stored rows that previously lost evidence cannot recover it from scores.

## Rollback

Exact pre-batch copies and protected-file hashes are under
`%TEMP%/snipersight-scoring-base-96c9ba86-e2b1-4eee-b89b-d75c118d97d9`.
Revert this batch's scoped changes together; restoring files from Git HEAD would
discard earlier unrelated repairs. Restore service/controller direction handling
together, and all sensitivity call sites with the resolver. The additive metadata
requires no runtime-store migration. Contract baselines stay unchanged. Backend
changes have not been loaded into the running API by a restart in this batch.

## Final verification checkpoint

- Full selected backend manifest: **2,088 passed**, 169 deprecation warnings,
  269.38 seconds. Final additive gate-result metadata: **96 focused tests
  passed**, eight warnings, 9.57 seconds.
- Related rejection follow-up: **75 passed**. Frontend: **33 passed** (25 new
  score tests plus eight existing rejection tests). `tsc --noEmit`: exit 0.
- Smoke: eight groups clean. API/telemetry/pipeline inventories clean. Storage
  has only the prior `LiveTradingService._log_signal` implementation fingerprint
  change; contract command exits 1, no new inventory drift, baseline unchanged.
- Independent math/UI, architecture and backend-integrity reviewers report no
  remaining blocker in this scope. Journal/telemetry/baseline/capture-script
  hashes match the pre-batch snapshots. These are isolated fixture checks; no
  live or whole-system correctness claim follows from their counts.
