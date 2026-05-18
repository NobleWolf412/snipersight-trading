---
name: tune-confluence-weights
description: |
  Edit confluence factor weights in backend/strategy/confluence/scorer.py
  (MODE_FACTOR_WEIGHTS: _OVERWATCH / _STRIKE / _SURGICAL / _STEALTH) and
  automatically verify the result before reporting done. Catches the bugs
  that historically required running analyze_weights.py, normalize_all_weights.py,
  and test_weight_bug.py by hand: weights that don't sum to 1.0, factor
  keys that drift between modes (typos, orphans), duplicate keys, and the
  partial-factor renormalization bug where a missing factor silently
  redistributes weight.
---

# tune-confluence-weights

A self-verifying skill for editing confluence mode weights. After every
edit the skill runs `verify_weights.py` and only reports success if every
check passes. On failure it prints the diff and the exact offending mode/
factor so the next edit is targeted, not guesswork.

## When to trigger

Trigger whenever the user asks for any of the following — these are the
edits that have historically required manual `analyze_weights.py` runs:

1. "Bump market_structure to 0.32 in strike mode"
2. "Add a new `vwap_reclaim` factor at 0.08 across all modes"
3. "Retune surgical for higher scalp aggression"
4. "Normalize the overwatch weights so they sum to 1.0"
5. "Drop `fibonacci` from stealth — it's noise there"
6. "Make MACD weight symmetric across modes"
7. "Rename `htf_alignment` to `htf_composite` everywhere"

Do **not** trigger for:
- Reading/explaining the existing weights (no edit involved).
- Touching `MACD_MODE_CONFIGS` or `RELATIVITY_MAP` — those aren't
  factor weights and have different invariants.

## What the skill does

1. **Generate the edit.** Apply the requested change to
   `_OVERWATCH_WEIGHTS`, `_STRIKE_WEIGHTS`, `_SURGICAL_WEIGHTS`, and/or
   `_STEALTH_WEIGHTS` in `backend/strategy/confluence/scorer.py` using
   the `Edit` tool. Preserve the section comments
   (`# --- SMC Core ---`, etc.) and the existing key ordering.

2. **Run verification.** Execute the bundled verifier:
   ```
   python .claude/skills/tune-confluence-weights/verify_weights.py
   ```
   The verifier loads `MODE_FACTOR_WEIGHTS` directly from `scorer.py`
   (no need to start the API) and checks:

   - **Mode coverage:** all 4 canonical modes + their aliases are
     defined (`macro_surveillance`/`overwatch`, `intraday_aggressive`/
     `strike`, `precision`/`surgical`, `stealth_balanced`/`stealth`).
   - **Key parity:** every mode has exactly the same set of factor
     keys. Drift here is the #1 cause of silent renormalization bugs.
   - **No duplicates:** every key appears once per mode.
   - **Sum-to-1.0 (or documented otherwise):** each mode's weights sum
     to 1.0 ± 0.001, OR the verifier prints the normalized percentages
     so the operator can confirm the intended pre-normalization shape.
   - **Partial-factor scenario:** runs the scoring math from
     `calculate_confluence_score` against a synthetic factor set where
     one weighted factor scores 0 and verifies the renormalization
     produces the expected score (the `test_weight_bug.py` case).
   - **Diff summary:** prints per-mode, per-factor `before -> after`
     for everything changed in this commit, with new effective %.

3. **Report.** If verification passes, summarize the changes (one line
   per affected mode + the effective % shift on each touched factor).
   If it fails, paste the verifier's failure block verbatim and stop
   — do not attempt a second edit without acknowledging the failure.

## Verification step (concrete)

After the `Edit` tool call(s), the skill **must** run the verifier and
inspect its exit code. The verifier exits non-zero on any failed check.
Example successful output:

```
✓ 4 modes present (8 aliases resolved)
✓ key parity: 26 factors shared across all modes
✓ no duplicates
✓ sums: overwatch=1.000  strike=1.000  surgical=1.000  stealth=1.000
✓ partial-factor renormalization: expected 100.0, got 100.0
DIFF (this edit):
  strike.market_structure  0.28 -> 0.32  (effective 11.2% -> 12.5%)
```

Example failure output the skill must surface unchanged:

```
✗ key parity FAILED
  strike has extra keys: {'markt_structure'}
  strike is missing keys: {'market_structure'}
  → Likely typo. Compare strike to overwatch.
```

## Tools the skill needs

The skill is intentionally cheap — it relies on tools you already have:

- **`Edit`** — to apply the weight changes in `scorer.py`. Required.
- **`Bash`** — to run `verify_weights.py` and capture its exit code
  and output. Required.
- **`Read`** — to load the current `MODE_FACTOR_WEIGHTS` block before
  proposing the edit, so `old_string` for `Edit` is exact. Required.

What would make this skill **better** if added:

- **`git diff` access via Bash** — already available; the verifier
  uses `git show HEAD:backend/strategy/confluence/scorer.py` to
  compute the before/after diff. No new tool needed but worth noting
  the dependency.
- **A `WeightLint` MCP tool** (hypothetical) that runs the same checks
  on a JSON payload without writing to disk. Would let the skill
  validate a proposed edit *before* writing it, turning a fix-after-the-
  fact verifier into a propose-then-write loop. Not built today.
- **`mcp__github__pull_request_review_write`** — when these edits land
  in a PR, the skill could post the diff summary as a review comment
  automatically. Already in your MCP toolkit; opt-in per-edit.

## Notes

- The verifier is **read-only against scorer.py**. It never rewrites
  weights — that's the skill's job via `Edit`. This split keeps the
  source of truth in one place.
- If the user explicitly says "leave the sums alone, I'll normalize
  later," the verifier still runs but the sum check downgrades from
  hard-fail to warning. Pass `--allow-unnormalized` to opt in.
- The synthetic partial-factor test mirrors `test_weight_bug.py` —
  delete that script once you trust this skill.
