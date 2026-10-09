# Strict universe selection

Scope: local working tree based on `ace4bc3d9923d31f252ef9710b5f425ee26ba79d`.
No exchange session, live order or deployment is part of verification.

## Baseline and decision

The selector marked disabled-category symbols `bucket_excluded`, then backfilled
them into `selected`. An empty perp filter substituted a second default pool,
potentially bypassing stale, stablecoin, market and category exclusions. Majors
were inferred from a ranked prefix, sometimes promoting arbitrary symbols.
Initial reproduction: 24 failures / 4 passes in 28 new guarded contract cases.
Both bot callers also substituted five majors on a selection exception; all ten
new caller cases failed before their repair. Independent review then caught the
paper caller passing unsupported market type `perp` to Phemex. A real-adapter
fixture reproduced an empty paper universe while live succeeded. Paper now uses
the adapter-owned market type (`swap` for its default Phemex adapter). Four added
consumer cases cover real Phemex ranking/selection reaching both bot engines and
scanner job success/empty handling, without exchange transport.

Category switches now mean strict inclusion. Universe size is a maximum, and an
underfilled or empty result is valid. All switches off retains the existing
meaning of all categories, now explained in setup. Each candidate is classified
once by the existing shared classifier; MAJOR, MEME and remaining categories
form disjoint buckets. Bucket priority stays majors, memes, alts, with adapter
ordering inside each bucket. Identical symbol strings count once; aliases are
not normalized or merged here.

Initial empty/failed adapter ranking still uses the default pool, logs that
provenance and passes every candidate through the same filters. There is no
second fallback after exclusion. Explicit `is_perp=False` is authoritative;
absent/failing metadata retains the existing notation heuristic, with a warning
on failure. Snapshot writes/reads detach nested data. The audit checks overlap,
duplicates and count conservation, and reports an empty result as a note.

## Callers and impact

- ScannerService and scanner/API debug routes consume the shared selector.
  ScannerService already fails an empty scan job before invoking the engine.
- Paper (including its testnet configuration) and live scan cycles consume the
  same selection contract. Selection exceptions now end the cycle with
  `scan_error`; an empty set after selection/stale/admission/exclusion filters
  ends with `scan_completed`, zero scanned/signals and `universe_empty`.
  Paper clears the observational CVD candidate list on these early exits.
- No execution, sizing or scoring threshold is retuned. The chosen basket and
  therefore basket-derived macro breadth can change. This is a trading-input
  behavior correction, including the shared live service path.
- The universe endpoint and audit consume detached selection snapshots; these
  remain process-global selection evidence, not final bot-admission history.
- BotSetup explains strict categories, maximum size and all-off behavior.

## Alternatives and limits

Keeping preference-style backfill and only correcting the report would preserve
the basket but contradict category-filter intent. A typed result with per-owner
history would address broader ownership, but is a separate API change.

The classifier's existing cached/heuristic taxonomy is not recalibrated here.
Perp filtering still uses the existing leverage > 1 / non-spot activation rule;
explicit swap selection at 1x remains a separate market-identity question.
Phemex's internal ranking fallback may return plain pair names; strict metadata
filtering may correctly leave it empty. No real-exchange recovery is certified.
Existing fail-open bot liquidity/stale-filter exception policies are unchanged.
Global universe ownership is the next review boundary.

## Verification

Guarded targeted selection/audit/consumer checks: 82 passed. The caller cases
construct only the scan boundary and replace the decision engine; they do not
instantiate a live executor. Full selected regressions, contract inventory,
pipeline smoke and independent review are recorded in the current audit ledger.

Final selected guarded suite: **1,951 passed**, 161 existing warnings, 260.29 s.
All four contract inventories and eight structural smoke categories are clean;
TypeScript and whitespace checks pass. Independent review initially required the
Phemex caller repair and positive consumer coverage; both were reproduced and
resolved, with follow-up approval. Actual journal/telemetry hashes are unchanged.
