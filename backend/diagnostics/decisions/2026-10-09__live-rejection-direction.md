# Preserve absent direction in live rejection evidence

The live scan wrapper manufactured LONG when a rejection omitted direction.
The live log writer independently repeated that fallback and retained null or
empty values. Paper's scan wrapper was already corrected in the earlier worker
evidence batch. This repair changes diagnostic values only.

Both live boundaries now map absent, null or empty direction to `UNKNOWN`.
Explicit `LONG`, `SHORT` and `UNKNOWN` remain unchanged. The signal ID uses the
same lowercased direction as the recorded entry, so unknown evidence has an
`_unknown` suffix and the trace returns `side: "unknown"`. Existing TypeScript
types accept the string; Gauntlet and PipelineTracer already render it neutrally.
No trading direction is assigned and no order, score, risk or strategy setting
changes. Historical JSONL records are not rewritten or reinterpreted.

## Verification and contracts

Twelve new guarded cases cover the real live scan wrapper and direct log calls,
each with missing, null, empty, UNKNOWN, LONG and SHORT direction. They verify
the ring buffer, ID lookup, fixture JSONL and trace response together. Six cases
failed before the fix; the explicit-side cases already passed. All **175 focused
tests passed** afterward, including related lifecycle, entry-risk, universe and
rejection-consumer cases. Every invocation passed the seven isolation checks.

The API, telemetry and pipeline inventories are clean, as are all eight smoke
groups. The storage inventory deliberately reports one implementation hash
change for `LiveTradingService._log_signal`:

- Before: `5bf01611b95df8de4c1b405e0d1a1c21ab9ee3ff1dcc372dab36299e504d2f09`
- After: `37498c3ac2a7ec8000d30603f8d5c7f66437a5540d85433dbb1b947258227745`

This captures the intended value change; literal writer keys remain unchanged.
The contract command exits 1 for that drift. Its baseline is preserved, and this
is not described as an all-clean contract check. The complete selected suite was
not rerun for this two-site reporting change.

## Boundaries and rollback

The exact pre-batch source copies and protected-file hashes are under
`%TEMP%/snipersight-live-evidence-base-b7d24d8e-3677-4267-8b20-8b72ff6e6e4b`.
Revert these two defaults together with their new fixture cases if needed;
restoring whole files would discard earlier unrelated repairs. No runtime store
migration, exchange call, bot startup or service restart is part of this repair.
Paper/live trace ownership, process-global universe evidence and immutable
effective configuration remain distinct follow-ups. These tests use supplied
rejection inputs and do not establish live-exchange or whole-system correctness.
