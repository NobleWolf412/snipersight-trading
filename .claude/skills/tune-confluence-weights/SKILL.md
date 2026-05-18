---
name: tune-confluence-weights
description: |
  Edit confluence factor weights in backend/strategy/confluence/scorer.py
  (MODE_FACTOR_WEIGHTS: _OVERWATCH / _STRIKE / _SURGICAL / _STEALTH) and
  automatically verify the result before reporting done. Mechanical edits
  go through bundled scripts (no token cost, no typo risk); only judgment
  calls ("retune surgical for aggression") use AI. Catches the bugs that
  historically required running analyze_weights.py, normalize_all_weights.py,
  and test_weight_bug.py by hand.
---

# tune-confluence-weights

A self-verifying skill for editing confluence mode weights. Mechanical
operations are delegated to scripts; AI is reserved for judgment edits.
After every edit `verify_weights.py` runs and the skill only reports
success if every check passes.

## When to trigger

Trigger whenever the user asks for any of the following — these are the
edits that have historically required manual `analyze_weights.py` runs:

1. "Bump market_structure to 0.32 in strike mode" → script
2. "Add a new `vwap_reclaim` factor at 0.08 across all modes" → script
3. "Retune surgical for higher scalp aggression" → **AI**
4. "Normalize the overwatch weights so they sum to 1.0" → script
5. "Drop `fibonacci` from stealth — it's noise there" → script
6. "Make MACD weight symmetric across modes" → **AI** (which modes? which value?)
7. "Rename `htf_alignment` to `htf_composite` everywhere" → script

Do **not** trigger for:
- Reading/explaining the existing weights (no edit involved).
- Touching `MACD_MODE_CONFIGS` or `RELATIVITY_MAP` — those aren't
  factor weights and have different invariants.

## Decision: script or AI?

A request is **mechanical** (use a script) if it specifies the mode, the
key, and the value (or the operation: rename, add, drop). It is a
**judgment** call (use AI) if any of those are implicit ("rebalance",
"retune", "make it more aggressive"). When in doubt, use AI to *decide*
the values, then call the script to *apply* them — never let AI write
the Edit when the operation is a single-key change.

## What the skill does

1. **Apply the edit.**
   - **Mechanical request →** call the appropriate subcommand:
     ```
     python .claude/skills/tune-confluence-weights/apply_weight.py set    strike market_structure 0.32
     python .claude/skills/tune-confluence-weights/apply_weight.py add    vwap_reclaim 0.08
     python .claude/skills/tune-confluence-weights/apply_weight.py drop   fibonacci         # all modes
     python .claude/skills/tune-confluence-weights/apply_weight.py rename htf_alignment htf_composite
     python .claude/skills/tune-confluence-weights/normalize.py    --mode overwatch
     ```
     Scripts preserve section comments, key ordering, and indentation.
   - **Judgment request →** use the `Edit` tool to rewrite the relevant
     `_OVERWATCH_WEIGHTS` / `_STRIKE_WEIGHTS` / `_SURGICAL_WEIGHTS` /
     `_STEALTH_WEIGHTS` block. Preserve section comments.

2. **Run verification.**
   ```
   python .claude/skills/tune-confluence-weights/verify_weights.py
   ```
   Checks: mode coverage, factor-key parity across modes, no duplicates,
   sum-to-1.0 (or `--allow-unnormalized`), partial-factor renormalization
   invariant (the `test_weight_bug.py` case), and a per-factor `before
   -> after` diff vs `git HEAD`.

3. **Report.** If verification passes, summarize: one line per affected
   mode plus the effective % shift on each touched factor. If it fails,
   paste the verifier's failure block verbatim and stop — do not attempt
   a second edit without acknowledging the failure.

## Verification step (concrete)

After step 1, the skill **must** run the verifier and inspect its exit
code (non-zero on any failed check). Example successful output:

```
✓ 4 modes present (8 aliases resolved)
✓ key parity: 25 factors shared across all modes
✓ no duplicates
✓ sums: overwatch=1.000  strike=1.000  surgical=1.000  stealth=1.000
✓ partial-factor renormalization: expected 100.0, got 100.0
DIFF (this edit):
  strike.market_structure  0.28 -> 0.32  (effective 11.2% -> 12.5%)
```

Example failure output to surface unchanged:

```
✗ key parity FAILED
  strike has extra keys: {'markt_structure'}
  strike is missing keys: {'market_structure'}
  → Likely typo. Compare strike to overwatch.
```

## File layout

```
.claude/skills/tune-confluence-weights/
├── SKILL.md            ← this file
├── _weights_io.py      ← shared AST read/write (used by all 3 scripts)
├── apply_weight.py     ← deterministic edits: set/add/drop/rename
├── normalize.py        ← rewrite a mode (or all) to sum to 1.0
└── verify_weights.py   ← all post-edit checks; exit non-zero on failure
```

## Tools the skill needs

**Required:** `Read` (locate exact context for AI edits), `Edit` (judgment
edits only), `Bash` (run the three scripts and capture exit codes).

**Visibility:** no `disable-model-invocation` and no `user-invocable:
false`. The skill edits one file the user explicitly asks about — it's
not a deploy / commit / send-message risk, and the user may invoke it
directly from the menu (`/tune-confluence-weights`).

**Would help if added later:**
- A `WeightLint` MCP tool that validates a proposed dict *without writing
  to disk* — would let AI propose-then-write instead of write-then-verify.
- `mcp__github__pull_request_review_write` (already in your MCP toolkit) —
  could auto-post the verifier diff as a PR review comment for weight
  changes that land in a PR. Opt-in per-edit.

## Notes

- `_weights_io.py` is the single source of truth for parsing/rewriting
  `scorer.py` weight dicts. Any future skill (e.g., "export weights to
  JSON", "compare two modes") should import from it rather than
  reimplementing the AST walk.
- The legacy ad-hoc scripts (`analyze_weights.py`,
  `normalize_all_weights.py`, `test_weight_bug.py`) at the repo root are
  superseded by this skill — delete them once you've used the skill on a
  real edit and trust the verifier output.
