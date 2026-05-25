# Tier 2 signal event enrichment — intentional contract drift

## Headline
`create_signal_generated_event` and `create_signal_rejected_event` factory
signatures gained 2 optional keyword args each: `pre_dir_tie_break` and
`symbol_regime_trend`. Telemetry contract baselines re-captured.

## Context
- Commit batch: Tier 2 of the analysis-quality enhancement (5 items in
  the session game plan)
- Trigger: 2026-05-24 session-skew investigation (dda4d192 vs 9558a1c8)
  — couldn't answer "why was this direction picked" or "what was the
  per-symbol regime" from telemetry alone; had to infer from
  `signals.jsonl` setup_type tallies
- Per CLAUDE.md §11 (silent-bug surfacing) + §20 (backend integrity):
  add the diagnostic fields upstream so future autopsies can answer the
  direction-attribution question in a single query

## Resolution
- `backend/bot/telemetry/events.py`:
  - `create_signal_generated_event`: added `pre_dir_tie_break: Optional[str] = None`
    + `symbol_regime_trend: Optional[str] = None`. Both keys conditionally
    added to `data` dict only when non-None (backward-compat).
  - `create_signal_rejected_event`: same two optional kwargs.
- `backend/engine/orchestrator.py`:
  - Signal-generated emission at L2338 now passes both fields from
    `context.metadata`.
  - Gate-rejection path at L1690-1709 now adds both to `_rejection_info`
    dict, surfacing in per-cycle rejection_stats.
- `backend/diagnostics/contracts/telemetry_contracts.json`: re-baselined
  via `python -m backend.diagnostics.capture_contracts capture`.

## Why it matters next time
- Future autopsy session-skew investigations can answer "why was this
  direction picked" from a SQL query on telemetry events alone
- Older signal events (pre-Tier-2) won't have these keys; consumers
  should `.get(key)` with a None default
- Schema is backward-compatible: factories accept kwargs by name,
  defaults ensure existing callers don't break
