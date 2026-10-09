# Score scale, evidence budgets and admission policy

Date: 2026-10-09. Status: implemented locally; verification is recorded in
[the evidence artifact](../../../docs/audits/SCORE_POLICY_BALANCE_2026-10-09.json).
This follows the user's clarification that deduplication, weights, attainable
scores and numerical cutoffs must be evaluated together. It supersedes the
provisional unchanged-cutoff conclusion of the earlier
[deduplication checkpoint](2026-10-09__evidence-deduplication.md), whose evidence
and historical claims remain intact. Extra-high reasoning is appropriate for
this change because it crosses strategy policy, configuration and consumers.

## Problem and decision

The old weighted average did not have a consistent attainable scale. Timing
could supply only 35 raw points, destination liquidity 40, volume profile 80,
regime alignment 83.3 and a single ideal HTF FVG 85. Each was weighted as though
100 were routinely available. Optional factors also changed the denominator.
A valid OB setup was implicitly asked to collect FVG and reversal evidence too.
Removing duplicated credit alone therefore did not establish sensible admission.

Adopt `family-evidence-v2` / `family-policy-v2`. Eight fixed budgets sum to 100.
Related alternatives compete within a budget. Missing evidence retains its
unused budget rather than transferring points to the remaining factors.
Raw factor diagnostics remain available with zero contribution weight.

| Maximum contribution | OVERWATCH | STRIKE | SURGICAL | STEALTH |
|---|---:|---:|---:|---:|
| Entry anchor | 20 | 20 | 20 | 20 |
| Structural confirmation | 15 | 15 | 15 | 15 |
| Directional context | 25 | 15 | 10 | 20 |
| Momentum evidence | 10 | 20 | 15 | 15 |
| Entry location | 15 | 10 | 15 | 15 |
| Participation | 10 | 10 | 10 | 10 |
| Destination | 5 | 5 | 5 | 5 |
| Session timing | 0 | 5 | 10 | 0 |
| **Total** | **100** | **100** | **100** | **100** |

These allocations express product intent: OVERWATCH emphasizes context,
STRIKE momentum, SURGICAL timing/location, and STEALTH balanced evidence.
They are documented design choices, not statistically fitted optimal weights.

The base is `sum(family quality / 100 * family budget)`. Conflict, active MACD
opposition and selected-side counter-HTF risk remain separately explained
deductions. Positive synergy is zero: a sweep/shift sequence improves the
confirmation family instead of adding points outside the 100-point scale.
Macro adjustment is bounded inside directional context. Known negative macro
evidence survives partial missing context; positive overlays require context.

Alternatives considered: retain variable weights and lower all gates; create
separate ad hoc gates for every pattern; fit weights/cutoffs to historical
outcomes. The first two preserve scale and overlap problems. The third needs
representative frozen inputs, effective config and execution/cost provenance
that this repository's old records do not supply. No ML work was introduced.

## Evidence ownership

| Family | Actual ownership |
|---|---|
| Anchor | Best usable OB **or** FVG. Invalidated/breaker/fully consumed OBs and FVG fill >=70% cannot qualify. Only resolved structure/entry timeframes are eligible. A single ideal HTF FVG can complete this slot; stacking is unnecessary. |
| Confirmation | Best allowed-timeframe BOS/CHoCH quality, ordered confirmed sweep→shift, or observed close confirmation. Eligibility still requires a real allowed-timeframe structural shift; candles cannot invent one. |
| Context | Explicit directional status plus regime quality, averaged within one budget. Neutral/unknown is distinct from opposed. Macro is an internal bounded adjustment. |
| Momentum | Strongest Momentum/divergence/MTF/daily-StochRSI alternative. Inside Momentum, RSI/StochRSI/MACD/positive K-D compete within the 40-point oscillator allowance; negative K-D remains a deduction. ADX/DI, EMA and Bollinger features stay inside the outer momentum budget. MFI is descriptive only. |
| Location | Best OB/FVG rejection, premium/discount/VWAP, Fibonacci or volume-profile location. Proximity cautions cap location quality; permission does not earn another reward. |
| Participation | Existing deduplicated magnitude/persistence/OBV volume assessment. Default `flat` without finite volume measurements supplies no evidence. |
| Destination | Liquidity target assessment, scaled from its actual 40-point budget. An origin sweep does not earn target points. |
| Timing | Session quality scaled from its 35-point maximum, with mode-specific maximum influence. |

Centered scales above 50 preserve neutral50 and map their attainable upper
range to100; zero-based timing/destination scale directly. This does not imply
all mathematically maximal observations can occur together in a market.

Price and volume necessarily occur in several useful relationships. Volume at
price/VWAP locate an entry; relative volume measures participation. They are
different questions, not independent statistical votes. MFI explicitly mixes
price and volume ([Fidelity definition](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/mfi));
it no longer supplies another admission reward. Oscillator extremes also do
not independently confirm a reversal; see [Schwab's technical-analysis examples](https://workplace.schwab.com/story/technical-indicators-3-trading-traps-to-avoid).
Neither source validates this project's numerical policy.

## Gates and downstream behavior

| Policy | Previous | Current |
|---|---:|---:|
| OVERWATCH scanner | 72 | 75 |
| STRIKE scanner | 68 | 65 |
| SURGICAL scanner | 70 | 70 |
| STEALTH scanner | 70 | 65 |
| Conservative bot gate/floor | 72/62 | 75/65 |
| Balanced bot gate/floor | 65/55 | 65/55 |
| Aggressive bot gate/floor | 58/48 | 60/50 |

The standard band is65, strong75, exceptional85; SURGICAL uses an intermediate
70 admission cutoff. Scanner tiers and planner A/B confidence thresholds use
the same one-decimal comparisons, including rounding boundaries. Planner ATR
fallback uses60. RR, critical-data checks, cash-risk limits and stop/target
rules remain separately enforced. A custom gate does not relabel score quality.

Explicit custom values win. Generic ScanConfig and API startup no longer impose
an implicit70 over STEALTH65. Paper drawdown tightening uses the current
conservative preset; entry snapping and countertrend strong-score checks use75.
The RangeBot numeric default is65. Both bot setup pages submit explicit custom
values; selecting a displayed mode does not silently replace those values.

Both bot engines still execute the existing STEALTH/fusion path. Fusion's
actual scoring mode is recorded, which can differ from the displayed/session
mode. This batch does not activate autonomous execution of all four modes.
Paper's dynamic floor/thesis behavior and live's hard cutoff are not claimed
identical. A scanner gate may already have filtered ordinary below-gate plans.
New v2 evidence eligibility is enforced at both paper and live entry, even if
the user chooses a zero numeric cutoff or the thesis policy bypasses a score.

Legacy direction selection prefers the sole eligible side before numeric
tie-breaking. Thesis keeps its selected direction and rejects it if ineligible;
it does not flip to the opposite trade. Counter-HTF confirmation accepts usable
OB or FVG anchors and a correctly ordered sequence on allowed timeframes.

An immediate opposing zone/level within0.5ATR fails eligibility. Crossed levels
behind the trade and consumed zones cannot masquerade as walls. A P/D caution
cannot mask an actual immediate wall. Farther proximity cautions reduce the
location family's ceiling, preserving a separate visible reason.

## Findings from integration and independent review

The exact price-reflection test exposed a pre-existing seed asymmetry in
`bos_choch._determine_initial_trend`: falling highs took priority over rising
lows, so both a contracting tape and its reflection seeded downtrend. One tape
emitted six SHORT breaks while its reflection emitted no LONG breaks. Seed
evidence now treats conflicting slopes as ranging and agreed slopes as a trend.
This is a bounded prerequisite for symmetric admission, not a redesign of SMC.
Existing swing-confirmation timing/look-ahead limitations remain open.

Independent review also identified and corrected discarded proximity safety,
consumed anchors, missing-context macro inflation, OB-only/unscoped sequence
relief, default-volume credit, tier rounding, stale default cutoffs and missing
rejection provenance. Scored rejection logs now retain actual scoring mode,
model/policy version, numeric result, eligibility and family contributions.
The UI distinguishes an evidence failure from a numeric cutoff failure.
Contribution charts exclude zero-weight diagnostics and disclose mixed policy
cohorts. `htf_aligned` now describes inferred directional context, affecting
planner pullback treatment and newly recorded journal booleans; historical rows
are not relabeled.

## Reproducible evidence and limits

Before changing policy, 64 controlled setup cases covered eight shapes, four
modes and both directions. Valid OB/FVG continuation examples scored roughly
46–60 and missed every original scanner gate; adding reversal evidence still
left those examples below their gates. The new same-input reference cases score
roughly87–90. Weak cases remain roughly33–40. Missing-anchor/shift examples may
clear the *numeric* cutoff but must fail admission. Permanent assertions check
these outcomes, symmetric directions, budget conservation, duplicate readings,
invalid anchors, crossed/active walls, unknown data, macro bounds and rounding.
These are controlled detector outputs, not a profitability backtest.

The artifact records final raw-candle outcomes separately from controlled
accepted-plan settlement, exact verification counts, review findings, hashes
and protected records. Tests run through the guarded manifest; no unrestricted
API imports, credentials, exchange transport or actual trading stores are used.

Final selected backend run: **2,374 passed**, 387 warnings, 320.18 seconds;
all seven guard-denial checks passed. The runner recorded denied subprocess and
outside-fixture directory operations. Focused policy checks passed149 cases;
consumer units235; integration31; the final reflection check1. Frontend40 and
`tsc --noEmit` passed. These selections overlap the full backend manifest and
must not be added together as a unique-test count.

Contracts exit1 with exactly the intended paper/live signal-writer fingerprints;
API, telemetry and pipeline inventories are clean. Smoke exits1 for the intended
OVERWATCH72→75, STRIKE68→65 and STEALTH70→65 deltas; seven other groups are clean.
Neither baseline was overwritten. The independent reviewer found no remaining
implementation blocker in the scoped changes; root also inspected UI diffs.

The unchanged original raw tapes produce LONG76.5475 and SHORT77.2475 at both
balanced and aggressive presets, and exercise real paper stop/target settlement.
The reflected tape proves mirrored detector events; it is not claimed as a
complete reflected-plan success. No candle seeds or admission cutoffs were tuned
to rescue these fixtures.

Protected-record exception: actual telemetry.db changed during this task. Its
writer was not established. The existing API/UI processes were already running
from the previous evening, and guarded verification denied real-store access;
neither fact by itself attributes the write. The artifact retains exact observed
hashes/times. Journal and contract/capture baselines matched at review time.

Serial worker and controlled executor fixtures do not certify real process
concurrency, exchange fills, slippage or win rates. Frontend checks are static
render/classification/type checks, not a browser visual review.

The next calibration evidence should be version-separated historical replay
or paper observations using frozen inputs and costs, including rejected setups
and per-mode/side/regime coverage. The score measures policy evidence coverage;
85/100 does **not** mean85% win probability. No live acceptance frequency or
optimal profitability threshold has been established here.

Changes are local. No app restart, external order, history migration, deployment,
commit or push was performed. Roll back the scoped policy, consumer, detector
and test hunks together using the recorded pre-batch backups; do not reset the
whole dirty tree to HEAD or overwrite prior checkpoint evidence.
