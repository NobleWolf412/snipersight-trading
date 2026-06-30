# Order-flow (CVD) forward-capture experiment — 2026-06-30

## Why this exists
The strategy has NO measured edge. Four signal classes were rigorously tested against a noise floor and
ALL came back noise: (1) 26 SMC/confluence factors (0 predict, best |r| 0.12 < floor 0.13, n=355);
(2) direction-vs-regime cohort (flips sign recent-24 vs full-332 — variance); (3) trailing/exit tuning
(improves losing, not winning); (4) funding rate (retroactive, n=347, corr at/below floor 0.107). Every
lead looked real small and evaporated at scale — the signature of no edge. **CVD (cumulative volume
delta = aggressive taker buy/sell FORCE) is the ONLY signal that is (a) genuinely different in kind
(order-flow force, not price geometry or positioning) and (b) untestable retroactively (Phemex via ccxt
fetchTrades is recent-only — no history).** So it requires FORWARD capture. The candle autopsy found the
missing thing is "runners vs faders" — at entry we can't tell a trade that will keep running from one
that fizzles. CVD is the hypothesis for that missing force signal.

## Hard mandate: MEASURE BEFORE BUILD (the discipline the 4 priors lacked)
CVD must beat the noise floor on REAL forward-captured data, OUT-OF-SAMPLE, above a multiple-comparison-
corrected bar, across symbols and regimes, at a pre-committed n — BEFORE any of it touches a decision.
The kill criterion is written NOW so we cannot move goalposts after seeing data.

## Phases + kill criterion
- **Phase A — build capture (SHIPPED 2026-06-30, this commit).** Observational only; journal columns,
  zero decision-path reads (grep-proven). Gates: symmetry-guard PASS (direction-sign mathematically
  exact — LONG/SHORT won't self-cancel), backend-integrity CLEAN (async-safe, pipeline_smoke clean,
  live untouched §15). Live capture proven (slope(L) = -slope(S) exact; OI populated).
- **Phase B — accumulate.** Run paper (STEALTH, use_testnet=false, $1k) to n ≥ 150 clean/coverage-passing
  trades. HONEST cost: ~2–4 weeks wall-clock at ~1 fill/2–3h. NO peeking (peeking-and-stopping is a leak).
- **Phase C — the GO/NO-GO test** (`cvd_edge.py`, reuses factor_contribution noise-floor methodology).
- **Phase D — wire a flag-gated PAPER gate ONLY if C passes** (default off, byte-identical, live untouched).

**KILL CRITERION at C (pre-committed, non-negotiable):** abandon CVD unless a feature clears the
**Bonferroni-corrected floor** (N=3 features → ≈0.195 at n=150) on the **held-out test fold**, AND
survives **leave-one-symbol-out**, AND **holds sign across both regime cohorts**, AND isn't REDUNDANT
(≥0.70) with an existing factor. Train-only pass / one-symbol-dependent / regime-sign-flip = the exact
prior mirage → NOISE, close it, write the verdict, do NOT build.

## Operator-approved config (2026-06-30)
- Features (N=3): `cvd_slope_1h` (force/imbalance), `cvd_divergence` (price-vs-flow), `cvd_z` (normalized).
  Direction-signed (flow agreeing with the trade = +). `cvd_accel` deferred (keeps the Bonferroni bar tight).
- Windows 15m + 1h (1h = STEALTH planning TF). Min n = 150 (detects |r|≳0.2; weaker is net-negative on
  fees regardless). Split: BOTH chronological 60/40 + walk-forward. Coverage threshold 0.9 for the clean set.
- **Parallel OI capture: YES** — fetchOpenInterest works live (history doesn't); `open_interest_at_entry`
  snapshotted in the same poller for ~zero marginal cost, tested separately under the same harness.

## Architecture (Phase A)
- `phemex.fetch_recent_trades` (signed taker flow; de-dup by TIMESTAMP — Phemex trade id is None) +
  `phemex.get_open_interest`.
- `backend/bot/cvd/cvd_tracker.py` — pure rolling-CVD; gap detection → `cvd_coverage` flag (loud, not
  silent; gap-corrupted entries excluded from the clean test set).
- `paper_trading_service`: 60s observational poller (bounded ≤25 symbols/tick) feeding the tracker the
  candidate universe; snapshot+OI injected into `plan.metadata["cvd"]` at BOTH open_position sites;
  journaled via the existing `*_at_entry` pattern (PositionState → CompletedTrade → to_dict). 6 new
  journal columns. `_inject_cvd_snapshot` + the poller are fully try/except wrapped — can't affect trading.
- `backend/diagnostics/cvd_capture_health.py` — read-only coverage/gap/distribution + live sanity.

## HONEST base-rate risk
Four priors were noise; the unconditional prior that CVD is also noise is **~80%+**. CVD being "different
in kind" is a reason to look, NOT evidence of edge. Expected outcome: **NOISE, abandoned at Phase C after
2–4 weeks.** The asymmetry that justifies the spend: Phase A is cheap, reusable infra (the CVD/OI columns
enrich autopsy regardless), the test is rigorous enough that a PASS would be believable (unlike the prior
four weak bars), and the kill criterion stops us fast. One more shot, taken rigorously.

## Follow-ups
- db_contracts re-baseline (additive CVD keys) via `/contract-check` with this decisions entry AFTER the
  first trade journals on this code (NOT from the audit path; the current 45→25 delta is pre-existing
  first-line-sample drift, unrelated).
- Phase C diagnostic `cvd_edge.py` to be written when n approaches 150.
