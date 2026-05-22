# 2026-05-21 — §16 audit subagent output must be pasted verbatim

## Headline
The §16 audit subagent's full Section 1/Section 2/Section 3 block (status table + open items + routing line) must appear in the response message body verbatim. Coder-authored summaries do NOT satisfy the rule, regardless of audit outcome.

## Context
Three slip incidents calibrated this rule:

1. **3a' / 3a'' Phase-3 follow-up round** — three consecutive turns shipped with the coder describing the subagent's findings instead of pasting them. Each round's gaps got addressed, but the gate's actual output was invisible to the operator. Operator's third demand finally landed verbatim.

2. **3z.h clean-pass slip — commit 54d0923** — shipped with the literal phrase "All 12 rubrics ✅, no open items" replacing the auditor's actual table. Operator caught it and halted, treating the change as unaudited.

3. **3a TickerRail sub-step** — earlier procedural drift round; coder summarized the auditor's table into bullet points.

## Resolution
- CLAUDE.md §16 "Verbatim-paste enforcement" subsection (lines 139–144 at time of writing) codifies the rule and both calibration incidents.
- The fix shape is identical for clean passes and flagged passes: paste the Section 1/2/3 block before any commit framing. Phrases like "All 12 rubrics ✅, no open items" or "auditor flagged…" without the literal block above them = unaudited.

## Why it matters next time
The audit step is the gate-not-checkpoint principle from §16; pasting the gate's actual output is non-negotiable. Coders cannot operate the gate AND report the gate's verdict — that's the same hand. The operator's ability to trust the audit depends on the raw output being inspectable. Clean passes are the highest-risk slip case because there's no flagged item forcing structural engagement with the subagent's output.

Cross-ref: CLAUDE.md §16 (Verbatim-paste enforcement); MEMORY.md §16 invocation discipline rule 1.
