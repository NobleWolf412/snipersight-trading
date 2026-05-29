# 2026-05-29 — Calibration: verify the data path before asserting a mechanism

**Type:** calibration near-miss (wrong premise shipped, caught + corrected same session)
**Related:** `2026-05-29__longbook-degradation-rootcause.md`, commit f159766

## What happened

While fixing the 2026-05-24 trading degradation, I asserted a second root-cause mechanism:
that `_calculate_targets` (risk_engine.py) received the composite scan regime label
(`up_compressed`/`down_compressed`) and that `_effective_regime = "calm" if regime_label ==
"compressed"` let those labels fall through to a 1.0× ladder multiplier, disabling the
intended TP1-reachability compression. I shipped a substring-match "fix" (f159766) on that
premise, with symmetry-guard PASS and backend-integrity CLEAN.

The premise was false. The sole caller `planner_service.py:403` passes
`regime_label = get_atr_regime(...)`, and `get_atr_regime` (regime_engine.py:19) returns the
VOLATILITY regime ALREADY MAPPED to PlannerConfig keys (`compressed→calm`,
`volatile/chaotic→explosive`). So `regime_label` is always {calm,normal,elevated,explosive} —
the `== "compressed"` branch never needed to fire because the value was already `"calm"`.
The substring change is a functional no-op. Caught while tracing a sibling thread
(entry_engine.py), which forced me to read `get_atr_regime`'s return contract.

## Why the gates didn't catch it

- **symmetry-guard** verified the change was direction-symmetric (it was) — that is orthogonal
  to whether the premise was true.
- **backend-integrity** verified blast radius + contracts (clean) — also orthogonal. It even
  flagged entry_engine.py as "may carry the same bug" without tracing `get_atr_regime`, which
  is the same class of un-traced-premise miss.
- This is exactly CLAUDE.md §16 "what the audit cannot catch": same-model audits verify
  structure and rubric compliance, not the truth of a domain premise.

## Lesson (how to apply)

Before asserting "factor X behaves wrong because parameter P carries value V here": **trace P
back to its call site and confirm V is actually what flows.** A claim about *which value a
parameter carries* is a caller-trace check (find_symbol the caller, read the argument
expression, read any adapter/mapper in between). It must precede the fix. The decisive
evidence here was one read of `get_atr_regime`'s body — cheaper than a commit + correction.

Pattern trigger: any time a fix rationale contains "this label/value falls through / isn't
matched / is wrong here", stop and grep the producer of that value first.
