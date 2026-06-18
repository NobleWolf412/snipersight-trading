# 2026-06-17 — Bug #4: restore global regime to scan_completed telemetry (+ telemetry contract re-baseline)

**Trigger:** §11.6 bug-fix backlog (decisions/2026-06-16__regime-strategy-router-design.md). The
global market regime (`orchestrator.self.current_regime`, computed at orchestrator.py:443) was never
passed to `create_scan_completed_event` — the factory had no `regime_label` field at all, so the
scan-level regime was **never emitted** to telemetry (absent, never a present-then-nulled value).
That left no independent stream to validate the journal's entry-regime stamp
(bug #1, fixed in commit 7c9a7ad) against — i.e. after fixing how the journal labels regime, we had
no second source to confirm the labels are now correct. This closes that gap.

## Change
- `backend/bot/telemetry/events.py` — `create_scan_completed_event` gains optional
  `regime_label: Optional[str]=None` and `regime_score: Optional[float]=None`, conditionally added
  to the event `data` (mirrors the existing `symbol_regime_trend` optional-field pattern). Keys are
  OMITTED when None — absence is meaningful (regime detection failed).
- `backend/engine/orchestrator.py:717` — the sole production caller passes
  `regime_label=self.current_regime.composite if self.current_regime else None` and
  `regime_score=self.current_regime.score if self.current_regime else None`. None-safe; matches the
  existing `.composite`/`.score` access at :447-454.
- `backend/tests/unit/test_scan_completed_regime.py` — present-when-supplied + omitted-when-failed
  + score-rounding + independent-key-gating.

No trading-behavior change — purely additive observability.

## Backend-integrity gate (§18/§20) — verdict: contained
- Blast radius: 1 production caller (orchestrator.py:717); `MarketRegime.composite:str`/`.score:float`
  confirmed (regime.py:33-34). All scan_completed consumers read `data` via `.get()` / as a JSON blob
  (storage.py:56 `data_json TEXT`, no per-key columns) — additive keys break nothing; no frontend
  asserts the data shape. pipeline_smoke CLEAN (telemetry_events checks event-type presence, not key
  sets). 3/3 regression tests pass.

## Contract re-baseline (this entry authorizes it, per CLAUDE.md §20 human-driven baseline)
`capture_contracts diff` showed ONE change-introduced drift:
`telemetry_contracts.factories.create_scan_completed_event: list 5 → 7` (added regime_label,
regime_score). This is legitimate additive schema growth → re-baseline `telemetry_contracts.json`.

**Scope guard:** only `backend/diagnostics/contracts/telemetry_contracts.json` is re-baselined in this
commit. The pre-existing api_contracts drift (count 103→67, stale route baseline) and db_contracts
drift (`trade_journal.jsonl` absent from this clone) are UNRELATED to this change and are deliberately
left as-is — re-baselining them here would launder unrelated drift under this commit. They remain a
separate operator action. (`capture` re-writes all four baseline files; the api/db/pipeline files were
reverted via `git checkout` so this commit touches telemetry_contracts.json only.)

## Backlog status
§11.6: #1 entry-regime snapshot ✅ (7c9a7ad) · **#4 regime telemetry ✅ (this)** · #2 P/D inversion,
#3 FVG grade-after-TF-ATR, #5 factor re-rank after sign-fix, #6 regime ATR%-TF verify — open.
Next-natural: with #4 in, the live regime-label distribution is observable again — accumulate
post-fix scans and confirm the entry-regime stamp (bug #1) is producing sane labels before #7
(re-bucket + re-measure).
