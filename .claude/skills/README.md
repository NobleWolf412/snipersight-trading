# Project tooling

Reviewed 2026-10-08. Contributor guidance is in [AGENTS.md](../../AGENTS.md);
current architecture and verification scope are in
[the index](../../docs/ARCHITECTURE_INDEX.md).

Retained tools:

- `contract-check`: guarded inventory comparison, not full behavioral coverage.
- `tune-confluence-weights`: source-weight inspection plus scoped regression
  verification for an explicitly requested change; not strategy calibration.
- Generic UI/design and graph orientation skills: use when relevant; confirm
  generated relationships and product-specific assumptions against source.
- `_state_helper.py`: retained annotation utility, with
  [tests](../../backend/tests/skills/test_state_helper.py). It does not establish
  current findings or mutate the decision engine.

The retired triage and forensic playbooks encoded obsolete stage mappings,
configuration assumptions and copied helper paths. Use current diagnostic code,
record schemas and the architecture index for investigations. Do not infer absent
telemetry, trading intent or a failure reason from those former playbooks.
