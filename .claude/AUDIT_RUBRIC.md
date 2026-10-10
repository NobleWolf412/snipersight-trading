# Change verification checklist

Reviewed 2026-10-10. Replaces the May 2026 rubric and its tool-specific protocol.
Apply this checklist to the actual change; use "not applicable" with a reason.
A clean review establishes only the evidence and scope it names.

1. **Scope and intent.** State the concrete problem, authorized behavior change,
   affected files, relevant prior requests and material assumptions.
2. **Fundamentals.** Confirm real call paths, effective configuration, units,
   candle/confirmation time, freshness and input provenance where relevant.
   Implemented behavior and historical calibration claims can both be wrong.
3. **Contracts and ownership.** Trace producers, callers, consumers and state
   owners across backend and UI. Check public and private shape changes.
   Explain intentional deltas and coordinated rollback; snapshot tools do not
   capture every private contract.
4. **Behavioral evidence.** Reproduce the defect and exercise meaningful success,
   failure and boundary cases. Test LONG/SHORT where behavior is directional.
   Cover partial results, retry/restart and concurrency when the change touches
   them. Do not infer process isolation from a serial fake pool.
5. **Accounting and diagnosability.** Preserve unknown outcomes and error causes.
   Check conservation only for disjoint counts with the same denominator;
   diagnostic occurrences and candidate attempts can overlap terminal outcomes.
   Use cleanup/finalization where needed, not blanket try/finally requirements.
6. **Safe verification.** Use the guarded backend runner described in
   [AGENTS.md](../AGENTS.md). Keep credentials, external services and actual
   histories outside offline fixtures. Inspect guard results. Run relevant
   contracts/smoke/type checks; document their scope and any deliberate drift.
7. **Trading assumptions.** Do not equate scores with win probabilities or treat
   old thresholds as proven optimal. Separate software defects, strategy
   hypotheses and calibration evidence. Test effective overrides as well as
   defaults; preserve user risk boundaries through the affected path.
8. **UI and product fit** (UI changes only). Check against PRODUCT.md and
   DESIGN.md: desktop and 390px phone both deliberate, reduced motion honored,
   ambient effects never posing as state signals, unknowns shown as unknown,
   paper/live distinguishable, extra detail in modals rather than dropdown text.
9. **Reviewable completion.** Inspect the actual diff; preserve unrelated edits,
   verify remaining references after deletion, update navigation/evidence and
   record open risks. State which checks ran versus source-only inspection.

For substantial changes or deletion batches, have an independent reviewer inspect
the scoped diff and evidence. Report concrete findings with paths, severity,
verification and unresolved items. Preserve the report in the task or evidence
record; a particular heading or verbatim-paste token is not proof of review.

If a check fails, investigate the cause and rerun the affected verification.
Escalate unresolved material uncertainty with evidence; neither a fixed retry
count nor a green checklist substitutes for judgment.

This checklist does not authorize commits, pushes, deployments, live orders or
baseline replacement. Those follow the current user's authorization and scope.
