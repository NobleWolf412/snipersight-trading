# 2026-05-22 — capture_contracts JSONL scan: skip `logs/` directory

## Headline
`capture_contracts.py` was incorrectly counting runtime-emitted paper-trader `signals.jsonl` files under `logs/paper_trading/session_*/` as part of the DB/JSONL contract baseline. Fixed: scan now skips any path with `logs` in its parts, matching the canonical contract scope (which lives under `backend/cache/`).

## Context
Discovered during the 2026-05-22 docs-rewrite round. After committing Tier 4b (`56435d7`), the operator ran a paper-trading session that emitted a new file at `logs/paper_trading/session_e61102fa/signals.jsonl`. The next `python -m backend.diagnostics.capture_contracts diff` invocation reported:

```
db_contracts.jsonl_count: 17 -> 18
db_contracts.jsonl_files: added item (path='logs/paper_trading/session_e61102fa/signals.jsonl')
```

This is a false drift signal: the schema didn't change (the new file uses the same canonical signal-event key set as existing JSONLs), and the `logs/` directory is gitignored — these files are runtime data, not committed contract surface. Every paper-trader session would generate this kind of false drift on the next `capture_contracts diff`, which would slowly poison §16 Rubric 14's signal-to-noise ratio.

## Resolution
Single-line addition to `backend/diagnostics/capture_contracts.py` JSONL scan loop:

```python
for path in REPO_ROOT.rglob(jsonl_glob):
    if "venv" in path.parts or "__pycache__" in path.parts:
        continue
    if "logs" in path.parts:   # NEW: skip runtime per-session JSONLs
        continue
```

Comment block above the loop documents why (runtime-emitted, gitignored, would drift baseline without representing real schema change). Canonical JSONLs live under `backend/cache/`, and that path is unaffected by the new exclusion.

After fix, re-captured `backend/diagnostics/contracts/db_contracts.json` baseline.

Actual counts (corrected from a prior draft of this entry that miscounted):
- Pre-fix polluted baseline: `jsonl_count = 17` — 1 canonical (`backend/cache/trade_journal.jsonl`) + 16 runtime-emitted `logs/**/session_*/signals.jsonl` entries that had accumulated across earlier paper-trader sessions.
- Post-fix baseline: `jsonl_count = 1` — only the canonical `backend/cache/trade_journal.jsonl`. All 16 `logs/**` entries correctly dropped.

`python -m backend.diagnostics.capture_contracts diff` returns CLEAN against the new baseline.

(Secondary note: `backend/cache/signals.jsonl` is referenced in the codebase as the canonical signal journal path but is not present locally in this environment — likely cleared during prior repo-janitor work or never emitted in this session. The script will pick it up automatically the next time it appears, since the `**/signals.jsonl` glob is unchanged.)

The `logs/` check is now anchored to `path.relative_to(REPO_ROOT).parts[0] == "logs"` (rather than substring `"logs" in path.parts`) to avoid false positives on incidental "logs" segments in absolute paths.

## Why it matters next time
The capture-contracts script is itself the §16 Rubric 14 enforcement mechanism — silent false drift from runtime-emitted files would force operators to either re-baseline (accepting noise into the contract) or ignore drift signals (defeating the rubric). Either failure mode is corrosive. Best to fix the scan precisely once.

This is also a small example of a general pattern: any script that scans the repo for "contract-surface files" must distinguish source-controlled schema artifacts from runtime-emitted data files. The `logs/` exclusion is the start; if a similar issue surfaces in another scan (e.g. a future addition of `**/events.jsonl`), the same pattern applies.

## Affected files (same commit as docs rewrite — 2026-05-22__docs-rewrite-blueprint-to-built.md)

MOD:
- `backend/diagnostics/capture_contracts.py` — comment block + relative-path-anchored skip (`rel_parts[0] == "logs"`)
- `backend/diagnostics/contracts/db_contracts.json` — re-baselined (jsonl_count 17→1, removed 16 `logs/**/session_*/signals.jsonl` entries that had accumulated from prior paper-trader sessions)

Cross-ref: commits 72f64fe (Tier 1 introduces capture_contracts), 712f494 (Tier 4a adds the verbatim-paste enforcer on commits that follow); CLAUDE.md §16 Rubric 14 + §20.
