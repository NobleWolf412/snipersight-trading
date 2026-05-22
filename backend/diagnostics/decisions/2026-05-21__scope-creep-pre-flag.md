# 2026-05-21 — Rubric 9 (scope creep) must fire BEFORE the expansion lands

## Headline
When an expansion is needed mid-sub-step (e.g., adding a second endpoint not in the stated ask), halt and raise for confirmation FIRST. Retroactive "flag → rationalize → authorize" degrades the rubric into ceremonial.

## Context
Calibrated on Phase 3a TickerRail sub-step. Coder added a second API endpoint that wasn't in the original stated ask, then flagged it under Rubric 9 in the audit output AFTER the code was already written. The flag was meant to catch the *moment of expansion*, not to justify it after the fact.

Outcome: 486fdf7 (TickerRail wiring), f7c1bbb (audit fixes #1), 20d6839 (rubric 7 fix + scope-9 authorization). Three audit rounds, all rubrics resolved to ✅, no rule-3 iteration-cap halt triggered — but the procedural lesson stuck.

## Resolution
Rule codified in MEMORY.md "§16 invocation discipline" rule 3:
> Rubric 9 (scope creep) flags must fire BEFORE the expansion lands. When an expansion is needed mid-sub-step, halt and raise for confirmation FIRST.

Also reinforced by §18 Pre-flight Discipline (added 2026-05-21): feature / new-endpoint work requires Plan agent invocation up front, which surfaces would-be expansions before code starts.

## Why it matters next time
Audit rubrics are gates, not commentary. If Rubric 9 only ever fires retroactively, it's documentation, not enforcement. The pattern to break: "I noticed I needed to add X; I added X; here's the Rubric 9 flag justifying it." The replacement: "Stated ask is Y; I need X to deliver Y; raising before code lands."

Cross-ref: CLAUDE.md §16 Rubric 9, §18 Pre-flight Discipline; MEMORY.md §16 invocation discipline rule 3.
