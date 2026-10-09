---
name: contract-check
description: Compare current API, telemetry, pipeline and storage inventories with recorded baselines using isolated verification.
---

# Contract checks

Start with [the contributor instructions](../../../AGENTS.md) and
[current architecture index](../../../docs/ARCHITECTURE_INDEX.md).

For an offline comparison, run from the repository root:

```powershell
.\backend\venv\Scripts\python.exe -B backend/diagnostics/offline_verify.py contracts
```

Inspect exit status, guard results and each inventory delta. A clean inventory
does not establish private return-shape compatibility or complete behavior.
Trace affected callers and consumers and explain intentional changes.

For status only, read the baseline JSON files under
`backend/diagnostics/contracts/` without importing the API.

Baseline replacement is a separate mutation: require task authorization, record
the intended deltas and affected consumers, and inspect the capture implementation
and storage inputs before running it. Do not use actual historical rows to make
a snapshot pass, or repeat capture merely to hide drift.

Report scope, result, evidence and unresolved deltas. Do not claim the inventory
is clean if the tool failed or isolation blocked the intended check.
