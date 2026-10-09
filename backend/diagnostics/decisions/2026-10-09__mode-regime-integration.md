# Mode, regime and recommendation integration

Status: offline implementation and verification complete. User authorized research, a plan, fixed-mode
consistency and adaptive selection validated in paper trading on 2026-10-09.

## Evidence and intent

Baseline is the working tree preserved at
`%TEMP%/snipersight-mode-regime-base-fxapvm7k` (source hashes included), after the
family-evidence-v2 scoring work. It is not the older Git HEAD or a deployed release.

The scanner card derives recommendations locally from labels the backend does
not emit. The backend recommendation includes weekly data and applies daily ATR
bands to the highest available timeframe; display and advice can disagree.
Failures return STEALTH. Both bot engines force STEALTH and partially swap scoring
profiles after computing indicators. Paper additionally supplies different planner
defaults. Auto planning and cascade profiles can diverge from the scored mode.
Mode gates can be replaced by weaker session values or bypassed by thesis policy.

Independent read-only reviews by `regime_design_review` and
`mode_consistency_review` informed this design. Their findings must be checked
again against the finished diff.

## Plan and acceptance criteria

1. **Regime measurement.** Reuse a corrected shared ADX calculation; distinguish
   missing evidence from sideways/healthy. Global market measurement explicitly
   uses daily BTC candles. Weekly and 4h remain named context. Display and advice
   share a snapshot, source times and expiry. Repeated reads of one candle do not
   count as new confirmation. Fix critical numeric/label errors, with symmetric
   up/down fixtures. Daily ATR bands are retained as an uncalibrated policy;
   intraday planner volatility calibration is a separate limitation, not silently
   replaced by invented scaling.
2. **Authoritative advice.** A pure, versioned backend rule returns a suggested
   mode with reason, or explicit stand-aside/unavailable. It consumes dimensions,
   not marketing labels or an overall score masquerading as confidence. The card
   refreshes, expires stale evidence and changes the scanner only on user choice.
   Dominance levels are described as basket context, not demonstrated flows.
3. **Fixed playbooks.** Scanner, paper and live honor the same complete mode
   settings before indicator/structure computation. Apply declared MACD settings.
   Remove profile-only fusion and hidden planner mode switching. Resolve gates
   from the selected mode; bot restrictions can tighten them. Eligibility and
   score gates apply under both decision policies. Capture the effective policy
   on each plan so subsequent scans cannot reinterpret an existing candidate.
4. **Paper adaptive selection.** Opt-in adaptive selection uses the same advice
   policy and allowed modes. Resolve one complete mode for a scan before feature
   computation, abstain on unavailable/unsuitable inputs, and preserve existing
   pending/open trade identity. Live and exchange-testnet adaptive execution stay
   unsupported during paper validation. Scanner choice and bot choice remain
   separate UI state. Fixed STEALTH remains the default.
5. **Verification and evidence.** Guarded mode/worker/indicator/regime/recommendation
   tests, synthetic paper workflow, frontend integration and TypeScript checks;
   then relevant full guarded backend, contract and smoke checks. Inspect actual
   manifest/guard results. Preserve baselines, record intentional deltas and obtain
   independent review before completion. Update architecture and append evidence.

## Initial routing policy (hypothesis, not calibrated advantage)

Unavailable or stale required observations yield no recommendation. Chaotic
daily volatility yields stand-aside. Clear up/down trends are treated equally;
STRIKE searches trend setups, SURGICAL searches normal-volatility ranges, and
STEALTH searches mixed/compressed conditions without assuming a breakout.
OVERWATCH requires compatible daily/weekly structure and an allowed swing mode.
Allowed modes are constraints, never silently bypassed. Recommendation cutoffs
come from the selected mode. None of this estimates a win probability.

## Boundaries and alternatives

One shared snapshot plus mode playbooks was chosen over separately tuned regime
engines for every horizon. The latter adds state and calibration complexity and
makes a single recommendation ambiguous. Global BTC context remains an advisory
filter; individual symbols still require their own qualified setup.

Paper fixtures establish software behavior, not profitability or future adaptive
outperformance. No ML, actual orders, service restart, deployment, history rewrite
or contract-baseline replacement is part of this implementation.

## Research and review corrections

- [Fidelity on ADX](https://www.fidelity.com/viewpoints/active-investor/average-directional-index-ADX)
  distinguishes trend strength from the directional DI lines; both bullish and
  bearish strength need symmetric treatment. The shared implementation now uses
  simultaneous directional-move comparisons and arithmetic-seeded Wilder averages.
- [Fidelity on ATR](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/atr)
  describes volatility rather than direction. Percentage-of-price units do not
  make different candle durations interchangeable. Global daily measurement is
  explicit; pre-existing intraday planner bands remain an uncalibrated limitation.
- The global detector confirms **structural trend** using distinct daily bars.
  Engine views retain that confirmed trend but always include newly measured
  volatility, participation and risk. Display/advice uses the current observation.
  This avoids hiding current risk behind a days-old confirmed composite.
- Adaptive paper mode changes require two strictly increasing completed 4h source
  observations. The initial valid mode can be selected immediately. Pending mode
  changes pause new candidates; position monitoring continues. This is a declared
  policy choice whose responsiveness requires forward paper evidence.
- Paper passes the mode-qualified sizing floor to the core and retains the higher
  full-size gate for entry sizing. Example: STRIKE conservative75/65 can admit a
  score70 at reduced size. OVERWATCH cannot admit below its75 baseline. Live uses
  its full admission gate. Explicit zero cannot waive production qualification.
- Independent review identified a SURGICAL planner alias omission, stale React
  callback dependencies, source expiry crossing the candle deadline, and reversed
  source-time confirmation. Corrections require regression evidence before final
  completion. Strategy provenance is retained prospectively; old histories remain
  as recorded.


## Final policy decisions and review disposition

- Global/advice candle validity now shares `regime_inputs.validate_regime_candles`:
  timezone-aware, ordered, unique, contiguous completed OHLCV; valid price geometry,
  at least50 observations, source-age bounds. Core validates before cache reuse.
  Both global and adaptive confirmations reject regressed source times.
- Fixed VAP horizons are OVERWATCH4h/240h, STRIKE15m/72h, SURGICAL5m/24h and
  STEALTH15m/72h. These adopt the existing swing/intraday/scalp horizons explicitly
  per mode, rather than switching evidence with an unrecorded auto-regime hint.
- Mode zone/trigger roles reach the planner and ingestion; declared planner entry
  offsets and allowed HTF swing overrides reach their actual consumers. The tuple
  override does not replace the planner's profile dictionary. OVERWATCH/STEALTH
  execute nested-entry logic; SURGICAL's role helper is consistent but that does
  not imply its every setup requires nested entry confirmation.
- Removing STEALTH's cross-profile cascade retains its previous exclusion of
  swing trades. The unused old recommendation function was removed after checking
  backend/src consumers; its sole old test was replaced with fixed-mode isolation.
- The original raw SHORT fixture now qualifies numerically but is rejected by the
  existing bot target-distance/RR cap after the fixed VAP horizon changes geometry.
  The candle tape and cap are preserved. LONG raw-paper settlement and LONG/SHORT
  accepted-plan settlement remain separate evidence boundaries.
- The strategy payload is provenance (version, mode, gates, timeframe roles,
  MACD/VAP, overrides and recommendation), not every input/management parameter
  needed for historical reproduction. Existing global position-management rules
  are unchanged; adaptive changes cannot replace a different-mode open/pending plan.
- Two independent read-only reviewers found no remaining blockers after fixes.
  Their source reviews are separate from guarded runtime verification.

## Forward paper acceptance before any live adaptive proposal

Keep fixed STEALTH as the default and adaptive simulated-paper opt-in. Collect
versioned recommendations, abstentions, source timestamps, chosen modes, qualified
candidate counts, rejection reasons and actual simulated costs/outcomes. Compare
with the same-universe fixed-mode baseline across trend, range and volatility
conditions, including mode-change delays and pending/open-trade retention. Do not
choose thresholds from a few winners or imply a minimum sample proves advantage.
Review net results, drawdown, fill assumptions and rejection frequency before a
separate proposal to enable live adaptive selection. No such enablement, real
orders, deployment or forward-performance claim is included in this batch.

Known calibration limits remain: global daily ATR cutoffs, intraday planner
volatility bands, mode routing preferences, fixed profile-dependent pullback/backing
heuristics and representative market frequency. Some unrelated Intel display
fallbacks remain outside this recommendation-card change.

The legacy aggregate regime score still includes its neutral derivatives term;
there is no verified derivatives feed. The UI marks it unavailable, and the new
mode rule uses measured dimensions instead of the aggregate score. Recalibrating
that aggregate and its consumers requires separate evidence.

Verification: the full selected2439-test manifest passed across the final main
run and targeted repairs;45 frontend tests and TypeScript passed. Contracts and
structural smoke retain documented intentional drift without baseline updates.
Detailed log hashes, review findings and limitations are in
[the integration evidence](../../../docs/audits/MODE_REGIME_INTEGRATION_2026-10-09.json).
