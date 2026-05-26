# Two stuck-value Tier 2 telemetry bugs surfaced by taken_trade_forensics

## Headline
[scorer.py:3220](backend/strategy/confluence/scorer.py#L3220) `htf_aligned`
was checking factor names ("HTF Alignment", "HTF Structure Bias") that
the scorer no longer emits — making the field permanently False. At
[orchestrator.py:3089](backend/engine/orchestrator.py#L3089), `macro_state`
was serialized via `.value` (auto() int) instead of `.name` (label),
making the journal store "6" instead of "STABLE_SCARE". Both surfaced
together via the 2026-05-26 taken_trade_forensics partitioning, which
showed 17/17 Tier 2 trades had identical values for both fields.

## Context
- 2026-05-26 ran `backend/diagnostics/taken_trade_forensics.py` after the
  adversarial-review challenge (task a62c1e9) flagged that the
  conflict_density investigation answered the wrong question. The
  forensics partitioned the trade journal by entry-context features
  to find which combinations correlated with PnL.
- Output showed `htf_aligned_at_entry=False` for 17/17 Tier 2 trades
  and `macro_state_at_entry="6"` for the same 17. Stuck values, not
  variance.
- Bug #1 root cause: [scorer.py:3243-3247](backend/strategy/confluence/scorer.py#L3243)
  documents that "HTF Structure Bias" / "HTF Structural Proximity" /
  "HTF Momentum Gate" were consolidated into a single "HTF Composite"
  factor in CRITICAL_FACTORS. The htf_aligned predicate was not updated
  in lockstep.
- Bug #2 root cause: `MacroState` is `enum.Enum` with `auto()` members,
  so `.value` returns the auto-generated integer (STABLE_SCARE=6). The
  serializer chose `.value` for "safety" but `.name` was actually needed.

## Resolution
- [scorer.py:3220](backend/strategy/confluence/scorer.py#L3220) predicate
  changed from
  `any(f.name in ("HTF Alignment", "HTF Structure Bias") and f.score > 55 for f in factors)`
  to
  `any(f.name == "HTF Composite" and f.score > 60 for f in factors)`.
  Threshold 60 chosen as critical-threshold-minus-5 (CRITICAL_FACTORS
  has "HTF Composite": 65). Multi-line comment block cites the
  forensics calibration date for future readers.
- [orchestrator.py:3089](backend/engine/orchestrator.py#L3089) predicate
  changed from `.value if hasattr(_macro_state, "value")` to `.name if
  hasattr(_macro_state, "name")`. Comment cites calibration.
- New `backend/tests/unit/test_breakdown_field_regression.py` with 7
  tests: positive + negative + static source-grep for each bug. The
  static-grep tests catch re-introduction of the wrong factor names
  or .value serialization respectively (same pattern as commit ed452b9's
  process-isolation regression test).
- `backend/diagnostics/contracts/api_contracts.json` re-baselined from
  97 to 98 routes — the added route is `/api/market/tradfi` introduced
  by the parallel session in commit a482a63. The baseline was out of
  sync with main; re-baselining is housekeeping and is decoupled from
  the two stuck-value fixes.

## Git-index race incident (procedural learning)
Mid-fix, a parallel session committed `1412e24 Add Replay engine` which
swept up the macro_state.name working-tree change into that commit's
diff via the shared `.git/index`. As a result, the macro_state fix is
in main but landed inside the parallel session's replay-engine commit,
not in the htf_aligned commit. The §16 auditor flagged the unrelated
replay code as scope creep before the un-tangling was noticed.

Per the [git-index-race memory entry](../../../../C:/Users/macca/.claude/projects/c--Users-macca-snipersight-trading/memory/feedback_git_index_race.md):
the appropriate guard is `git diff --cached --stat` immediately before
every commit. That would have caught the bleed but the timing window
between the parallel-session commit and the audit subagent's grep was
narrow enough that the issue surfaced via the auditor instead.

## Why it matters next time
- The htf_aligned fix has a downstream behavioral effect at
  [confluence_service.py:547](backend/services/confluence_service.py#L547):
  that path applies a counter-HTF setup_qualifier penalty (−5 to −20
  total_score) when `chosen.htf_aligned == False`. Pre-fix, every
  scored signal got the penalty applied (because htf_aligned was always
  False). Post-fix, HTF-aligned setups (HTF Composite > 60) no longer
  eat the penalty — their total_score will increase by 5-20 pts and
  some may now cross min_confluence_score that previously failed.
  This is the *intended* consequence of fixing the bug, but it's a
  de facto signal-pass-rate relaxation for the aligned subset.
- Per §16 audit Rubric 11 follow-up: run `taken_trade_forensics.py`
  after the next 50 Tier 2 trades and compare to the pre-fix 17-trade
  baseline. If signal pass-rate shifts >15% or win-rate degrades,
  write a follow-up decisions entry. The fix is correct; the
  monitoring is the discipline.
- The setup_qualifier semantic is now clearer (also surfaced by the
  forensics): "Strong" / "Moderate" / "Soft" / "Weak" qualifiers ONLY
  apply to counter-HTF setups (per [confluence_service.py:656-668](backend/services/confluence_service.py#L656)).
  All 17 Tier 2 trades had setup_qualifier set → all 17 were
  counter-HTF entries. Even with the htf_aligned fix landed, those
  17 trades would still show htf_aligned=False because they genuinely
  ARE counter-HTF. The fix doesn't retroactively change historical
  data; it makes the field carry truthful values on future
  aligned-setup trades when they happen.
- Open audit item (Rubric 5): threshold 60 was chosen as critical-5
  buffer, not against an HTF Composite score distribution. If Rubric
  11 monitoring shows over- or under-firing of htf_aligned, the
  threshold should be re-tuned against the observed distribution.

## Bugs not addressed in this commit
- `conviction_class = "B"` for 67/67 trades — the planner's Literal
  default. Grep across `backend/` finds NO production code assigning
  "A" or "C"; the classifier is either never written or was removed.
  Separate commit required after deciding whether to restore the
  classifier or remove the field.
- Setup qualifier "Strong" vs "Soft" win-rate reversal (Strong loses
  more, n=12 vs 5) — sample too small to act on. Track via future
  forensics runs.
