# Scoring evidence ownership and cutoff migration

Date: 2026-10-09. Applies to the local working tree, not a deployed release.
User scope: inspect technical-analysis duplication and double counting, implement
bounded corrections, and review acceptance/sizing thresholds with those changes.
ML implementation/training remains excluded.

## Baseline and design decision

The scorer emits 24 literal factor names plus the conditional Volume Profile
factor. These are not 25 independent technical indicators: some are composites,
some describe geometry or time, and some represent constraints. All ultimately
share market inputs. Statistical independence cannot be established from names.

Baseline: exact pre-task working-tree copies in
`%TEMP%/snipersight-evidence-base-24e02152-3a09-4a34-b01b-c54d52a3e38e`.
This follows the separate [scoring correctness batch](2026-10-09__scoring-confidence.md).
Earlier unrelated edits and historical records are preserved.

Chosen approach: remove demonstrable repeated observations, preserve distinct
time/price relationships, and make the necessary divergence scale migration
explicit. The four mode weight dictionaries and numerical admission cutoffs
are retained as provisional policy. No cutoff is lowered to restore the old
acceptance rate. That would preserve the influence of removed duplicate credit.

Alternatives considered:

1. Replace the model with fixed family budgets. This would constrain all
   correlated contributions, but family assignments, budgets and missing-data
   behavior would introduce a much larger unvalidated strategy change.
2. Remove duplicate points and apply a uniform threshold reduction. This cannot
   preserve meaning: optional denominators, saturation, penalties and different
   evidence combinations change scores by different amounts.
3. Keep divergence raw points and add a second private quality scale for its
   consumers. This preserves weighted scores but creates another eligibility
   contract. One documented 0–100 factor scale is simpler and remains auditable.

## Implemented changes

| Evidence | Previous behavior | Revised behavior |
|---|---|---|
| Relative volume | Spike flag and relative-volume ratio both reward the same current/rolling20 calculation. Ratio 2.5 gives 90; 3.5 gives 100 without other confirmation. | One magnitude contribution, the stronger existing reward: both examples give 75. |
| Volume persistence | Acceleration already requires consecutive increases, then both receive bonuses. | One positive persistence contribution. Opposing acceleration retains its penalty and cannot be cancelled by the same consecutive run. |
| HTF swing bias | Identical helper result added to Market Structure and included in HTF Composite. | HTF Composite owns swing bias. Market Structure requires BOS/CHoCH evidence. Duplicated negative bias is removed too. |
| MACD cross/sign/slope | Scalar histogram sign is described and rewarded as slope, duplicating line-minus-signal direction. | Slope credit requires two finite historical histogram values. Constant/sign-only observations receive no slope credit. |
| MACD permission | No veto, including absent MACD evidence, supplies a weighted 100 factor and counts toward coverage/penalty relief. | Non-veto state is a zero-weight diagnostic excluded from those counts. Active veto keeps its existing weighted zero and existing soft-pass policy. |
| Divergence | RSI/MACD reports of the same price-pivot pair accumulate, plus a further cross-indicator bonus. Opposed reports can also trigger that bonus. | One strongest aligned report per price-pivot pair; no cross-indicator bonus; explicit event-quality normalization described below. |
| Origin sweep | Liquidity Draw adds 15 for a sweep already scored elsewhere, even without a destination. | Draw scores destination pools and reference levels. Sweep ownership remains in Liquidity Sweep and temporal Sequence. |
| Sweep/shift relation | A further flat sweep+structure synergy rewards co-presence. | Institutional Sequence owns that relationship; its other ingredients still retain their own distinct quality scores. |
| Institutional sequence | Scored sequence checks confirmation time; conflict relief and counter-HTF confirmation only check co-presence. | Shared confirmed-sweep-before-shift predicate, retaining each consumer's confirmation, quality and timeframe requirements. Same-time/out-of-order events cannot claim complete sequence relief. OB presence remains the existing rule; OB chronology is not newly certified. |
| Regime alignment | Service adds another +2/+5 after the direction is selected. | Regime Alignment owns the reward; no repeated post-selection bonus. Counter-HTF risk adjustments remain explicit. |
| Cycle views | Reversal-cycle and direct-cycle contributions accumulate on the same phase/turn; emitted Market Structure name suffices for structural credit. | Take the larger positive cycle view, retain risk/conflict offsets, and require nonzero structural evidence. Direction guard is defensive. Dormant cycle producers/HTF-name branches are not activated. |
| Acceptance comparison | Scanner/paper use one-decimal comparison; live and service tie-breaks use raw comparison. | Shared validated one-decimal comparison, also used by classification and the model quality-gate method. Invalid scores cannot pass. |

### Divergence scale and downstream boundaries

The current detector inspects the latest price-pivot pair per direction. Simply
keeping the strongest legacy event would cap RSI at 55 and MACD at 42, silently
making existing 60-point counter-HTF/STRIKE checks unreachable.

The revised factor is `min(100, retained_event_points * 100 / 55)`, where 55 is
the existing strongest RSI regular event (`15 + .4 * 100`). MACD keeps its lower
relative maximum, `42 / 55 * 100 = 76.36`. Regular/hidden relative rewards remain.
Rationale includes raw points and the normalization. This is a real factor-scale
change, not a claim that every candidate's score must decrease.

For example, RSI regular strength 50 gives 63.64. A second RSI copy or same-pivot
MACD report adds no score. The old RSI+MACD pair at strength 50 scored 77; the old
RSI-only report scored 35. A 60-point factor cutoff now corresponds to regular
RSI strength 45 or regular MACD strength 70. Counter-HTF uses `>=60`; STRIKE's
existing stricter `>60` condition is retained. Generic coverage/strong-factor
counts at 50/70 also consume the normalized factor. These mappings are explicit
heuristic policy, not estimated probabilities or statistically optimal cutoffs.

### Test admission migration

The unchanged raw-candle LONG fixture now scores 62.545 and fails balanced 65;
the original SHORT still passes. The permanent matrix checks both directions
under balanced 65/55 and aggressive 58/48 through the actual bot scan wrapper.
The LONG balanced rejection must produce no order and retain score provenance.
Settlement and downstream planner/risk fault injection use the existing named
aggressive preset with unchanged candles and risk/settlement assertions. No
production gate or score is overridden to rescue the old success expectation.

Independent review accepted this migration because the lost balanced admission
remains explicit. Exploratory seed/time/impulse variants did not establish another
balanced LONG success; searching for a convenient synthetic success was stopped.
These fixtures establish mechanics, not representative default trade frequency,
market-data coverage of balanced LONG acceptance, or optimal cutoffs.

## Full factor inventory and retained distinctions

| Factors | Evidence and assessment |
|---|---|
| Order Block, Fair Value Gap | Formation geometry, grade, displacement/size, freshness and mitigation. Shared detector grading inputs remain correlated; neither multiple names nor grade components establish independent votes. |
| Market Structure, Liquidity Sweep, Institutional Sequence | Break quality, sweep quality and their confirmed temporal relationship. The sequence is an interaction, not independent raw data. |
| OB Precision | Current entry location, rejection candle and nesting; different from historical OB formation quality. |
| Momentum | RSI/StochRSI/MFI/MACD and K/D share a 40-point cap; ADX/DI, EMA stacking and Bollinger position add context. Corrected the misleading “weighted average/prevents multicollinearity” comment. This is a bounded sum, not an independence model. |
| Price-Indicator Divergence | Relationship between price and oscillator pivots, distinct from current oscillator level. Deduplicated by price event. |
| MTF Indicator Alignment | Cross-timeframe agreement in RSI/MACD/ADX, with real histogram change. Overlapping candles are not independent observations. Normal snapshots do not populate the optional volume-trend branch. |
| Weekly StochRSI Bonus | Despite the historical name, evaluates daily StochRSI. Timeframe/context distinction is retained, not presented as an independent oscillator. |
| Volume, Volume Profile | Recent activity/flow versus volume distribution across price levels. Sharing volume input alone does not make them equivalent. |
| Close Momentum, Multi-Candle Confirmation | Latest candle-close position versus consecutive closes beyond a structural level. |
| HTF Composite | Bounded sub-average of swing bias, structural proximity, momentum permission and OB inflection. Proximity subcomponents still share structure; no global independence claim. |
| Premium/Discount Zone, Fibonacci Proximity | Dealing-range/VWAP location versus distance to swing-derived levels. Related geometry, distinct predicates. |
| Regime Alignment, Volatility | Directional market context versus current volatility suitability; detector inputs overlap. |
| Liquidity Draw, Opposing Structure | Destination opportunities/reference levels versus nearby opposing OB threats. |
| Kill Zone Timing | Session timing; meaningful context, not market direction by itself. |
| MACD Veto, BTC Impulse Gate, Structural Minimum | Permission, benchmark context and an anchor constraint. MACD pass now has no weighted reward. BTC and structural-minimum policy remain explicit legacy assumptions. |

OB+FVG+Structure synergy is retained because it includes the FVG/formation
interaction absent from Sequence. HTF sweep context synergy remains a correlated
cross-timeframe interaction. This review does not claim complete decorrelation,
that more factors imply more independent evidence, or that retained interactions
improve returns. SURGICAL's three-bar acceleration window cannot meet the current
three-increase flag requirement; that pre-existing producer limitation is recorded,
not silently activated as part of the deduplication.

## Acceptance and downstream impact

| Consumer | Retained numerical policy / effect |
|---|---|
| Scanner | OVERWATCH 72, STRIKE 68, SURGICAL 70, STEALTH 70; caller overrides still apply. |
| Bot presets | Conservative 72/62, balanced 65/55, aggressive 58/48 (gate/floor). Explicit values win; custom falls back to mode. |
| Legacy direction | Five-point margin, threshold tie-break and absolute-70 rules. Revised evidence can change the winning direction. |
| Tiers / state | Gate-relative B/A/APEX and existing anchor conditions; recomputed from final score. Counts are heuristic conditions, not independent evidence counts. |
| Planner conviction | Existing 80/65/60 scores plus geometry/data conditions. |
| Paper entry | Gate/full size, floor/half size; existing drawdown tightening and limited timing relaxation. Legacy upstream gate normally prevents ordinary below-gate entries; drawdown tightening can still create a half-size case after admission. |
| Live/testnet | Existing hard score gate, now same one-decimal comparison. Quantity, risk budgets, stops and exposure checks unchanged. Live does not use the paper soft floor. |
| Paper countertrend / entry snapping | Existing absolute70 checks retained. Changed scores can affect eligibility and distance-to-market limits. |
| Ranking / cascade | Existing score-first ordering and trade-type preference bonuses. They remain uncalibrated; limited slots may select different candidates. |
| Thesis policy | Scanner/paper demote the admission score; live keeps its gate. Existing environment/config ownership differences are not resolved by score arithmetic. |

No blanket gate reduction was justified. Existing archives lack the original
revision, frozen inputs, effective config and execution provenance needed for a
paired calibration. The reviewed 384-row journal inventory and small historical
post-fix cohorts cannot establish a new cutoff. Threshold optimization requires
version-separated, representative accepted **and rejected** candidates, costs,
realistic fills and independent validation across market conditions.

## Provenance and verification boundaries

New scorer results carry `score_model_version=evidence-dedup-v1` and
`score_calibration=heuristic_uncalibrated`. Raw breakdown JSONL, scored rejection
payloads and paper/live signal JSONL preserve the source version; unknown and
unscored evidence is not stamped as current. Completed-trade accounting schemas
remain unchanged. A version is not a frozen input/config package, and old
diagnostic aggregators do not automatically split versions.

The machine-readable [comparison and verification record](../../../docs/audits/SCORING_EVIDENCE_2026-10-09.json)
records paired inputs, actual commands/results, source hashes and review findings.
Final selected backend run: **2,180 passed**, 208 warnings, 296.91 seconds; the
preceding focused core/rejection/score-contract run passed 75 cases. All seven
guard-denial checks passed. Independent guarded contracts report clean API,
telemetry and pipeline inventories, plus exactly two intentional paper/live
signal-writer fingerprints (exit 1; baselines preserved). All eight structural
smoke groups are clean. Actual journal and telemetry hashes match the baseline.
All backend execution uses the guarded runner. Synthetic candle fixtures prove
mechanics and boundaries, not profitability, representative admission rates,
parallel worker isolation or live exchange behavior. No app restart, deployment,
orders, commit or push was performed for this batch.

## Technical-analysis references

Definitions were checked against primary platform documentation. StochRSI is
derived from RSI, so it is related evidence rather than an independent price
observation ([TradingView](https://www.tradingview.com/support/solutions/43000502333-stochastic-rsi-stoch-rsi/)).
MFI weights typical-price flow with volume; OBV cumulatively signs volume using
close direction ([Fidelity indicator reference](https://www.fidelity.com/webcontent/ap130058-research-experience-content/23.01/chartGuide/indicators.pdf),
[Fidelity OBV](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/obv)).
Volume-at-price describes distribution over price levels
([Fidelity glossary](https://www.fidelity.com/webcontent/ap002390-mlo-content/19.09/help/help_definition_v.shtml)).
These definitions support the dependency distinctions; they do not validate
SniperSight's weights, numeric cutoffs or predictive performance.
