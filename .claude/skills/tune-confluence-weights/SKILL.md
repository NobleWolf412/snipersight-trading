---
name: tune-confluence-weights
description: Inspect and verify an explicitly requested confluence weight change against current source and a documented baseline.
---

# Confluence weight changes

Follow [AGENTS.md](../../../AGENTS.md). Read the effective configuration and actual
factor calculations before editing. Weights are not win probabilities and
normalization alone does not establish strategy quality.

For an authorized change, record the baseline, intended behavior, affected modes
and consumers. Reproduce the relevant scenario and exercise both directions.
Do not lower gates, activate dormant factors or normalize values merely to make
an assertion pass.

The bundled `verify_weights.py` is a source-inspection utility. Read it before
running it: its hardcoded mode/key expectations and synthetic arithmetic are
limited checks, not evidence that the full current scoring engine ran. Use the
installed venv and the exact skill-relative script path; the mirrored copy lives
under `.agents/skills/`, not `.Codex/skills/`.

Backend behavioral tests must use the guarded runner from AGENTS.md. Compare
the actual diff and report structural versus behavioral results separately.
Do not delete other tests simply because this utility passes, and do not post
external review comments or publish changes without task authorization.
