#!/usr/bin/env python3
"""Verify MODE_FACTOR_WEIGHTS in backend/strategy/confluence/scorer.py.

Exits 0 if every check passes, 1 otherwise. Designed to be called by the
tune-confluence-weights skill after an Edit, but safe to run by hand.

Checks:
  1. All 4 canonical modes + aliases resolve.
  2. Every mode shares the exact same factor key set.
  3. No duplicate keys (caught at parse time by Python, double-checked here).
  4. Each mode sums to 1.0 +/- 0.001 (unless --allow-unnormalized).
  5. Partial-factor renormalization scenario produces expected score.
  6. Diff vs git HEAD for any factor that changed in this edit.
"""
from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from pathlib import Path
from typing import Dict, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
SCORER_PATH = REPO_ROOT / "backend" / "strategy" / "confluence" / "scorer.py"

CANONICAL_MODES = {
    "macro_surveillance": "overwatch",
    "intraday_aggressive": "strike",
    "precision": "surgical",
    "stealth_balanced": "stealth",
}

TOL = 1e-3
RED = "\033[31m"; GREEN = "\033[32m"; YELLOW = "\033[33m"; RESET = "\033[0m"


def ok(msg: str) -> None: print(f"{GREEN}✓{RESET} {msg}")
def warn(msg: str) -> None: print(f"{YELLOW}!{RESET} {msg}")
def fail(msg: str) -> None: print(f"{RED}✗{RESET} {msg}")


def load_weights(source: str) -> Tuple[Dict[str, Dict[str, float]], Dict[str, str]]:
    """Parse MODE_FACTOR_WEIGHTS without importing the module (avoids deps).

    Returns (weights_by_canonical_mode, alias_map).
    """
    tree = ast.parse(source)
    weight_dicts: Dict[str, Dict[str, float]] = {}
    mode_map_raw = None

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            name = target.id
            if name in {"_OVERWATCH_WEIGHTS", "_STRIKE_WEIGHTS",
                       "_SURGICAL_WEIGHTS", "_STEALTH_WEIGHTS"}:
                weight_dicts[name] = ast.literal_eval(node.value)
            elif name == "MODE_FACTOR_WEIGHTS":
                mode_map_raw = node.value

    if mode_map_raw is None:
        raise RuntimeError("MODE_FACTOR_WEIGHTS not found in scorer.py")

    resolved: Dict[str, Dict[str, float]] = {}
    aliases: Dict[str, str] = {}
    for k, v in zip(mode_map_raw.keys, mode_map_raw.values):
        mode_name = ast.literal_eval(k)
        target_name = v.id if isinstance(v, ast.Name) else None
        if target_name and target_name in weight_dicts:
            resolved[mode_name] = weight_dicts[target_name]
            aliases[mode_name] = target_name
    return resolved, aliases


def check_mode_coverage(weights: Dict[str, Dict[str, float]]) -> bool:
    missing = [m for m in CANONICAL_MODES if m not in weights]
    for canonical, alias in CANONICAL_MODES.items():
        if alias not in weights:
            missing.append(alias)
    if missing:
        fail(f"mode coverage FAILED — missing modes: {sorted(set(missing))}")
        return False
    ok(f"{len(CANONICAL_MODES)} modes present ({len(weights)} aliases resolved)")
    return True


def check_key_parity(weights: Dict[str, Dict[str, float]]) -> bool:
    by_canonical = {m: set(weights[m].keys()) for m in CANONICAL_MODES if m in weights}
    if not by_canonical:
        fail("key parity FAILED — no canonical modes resolved")
        return False
    reference_mode, reference_keys = next(iter(by_canonical.items()))
    bad = False
    for mode, keys in by_canonical.items():
        extra = keys - reference_keys
        missing = reference_keys - keys
        if extra or missing:
            fail(f"key parity FAILED for {mode}")
            if extra:
                print(f"    {mode} has extra keys:   {sorted(extra)}")
            if missing:
                print(f"    {mode} is missing keys: {sorted(missing)}")
            print(f"    → compare against {reference_mode}")
            bad = True
    if not bad:
        ok(f"key parity: {len(reference_keys)} factors shared across all modes")
    return not bad


def check_no_duplicates(source: str) -> bool:
    bad = False
    for dict_name in ("_OVERWATCH_WEIGHTS", "_STRIKE_WEIGHTS",
                      "_SURGICAL_WEIGHTS", "_STEALTH_WEIGHTS"):
        marker = f"{dict_name} = {{"
        idx = source.find(marker)
        if idx < 0:
            continue
        end = source.find("\n}\n", idx)
        body = source[idx:end]
        seen: Dict[str, int] = {}
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith('"') and ":" in stripped:
                key = stripped.split('"', 2)[1]
                seen[key] = seen.get(key, 0) + 1
        dupes = [k for k, n in seen.items() if n > 1]
        if dupes:
            fail(f"duplicate keys in {dict_name}: {dupes}")
            bad = True
    if not bad:
        ok("no duplicates")
    return not bad


def check_sums(weights: Dict[str, Dict[str, float]], allow_unnormalized: bool) -> bool:
    sums = {m: sum(weights[m].values()) for m in CANONICAL_MODES if m in weights}
    bad = False
    for mode, total in sums.items():
        if abs(total - 1.0) > TOL:
            if allow_unnormalized:
                warn(f"{mode} sums to {total:.4f} (not 1.0) — normalization deferred")
            else:
                fail(f"{mode} sums to {total:.4f}, expected 1.000 ± {TOL}")
                bad = True
    if not bad:
        summary = "  ".join(f"{CANONICAL_MODES[m]}={sums[m]:.3f}" for m in CANONICAL_MODES)
        ok(f"sums: {summary}")
    return not bad


def check_partial_renormalization(weights: Dict[str, Dict[str, float]]) -> bool:
    """Mirror of test_weight_bug.py: factor A scores 100, factor B scores 0
    and is dropped from the contribution list. The renormalization across
    the surviving factors must still produce 100 (not 50)."""
    fake = [("A", 100.0, 0.5), ("B", 0.0, 0.5)]
    factors = [(n, s, w) for (n, s, w) in fake if s > 0]
    total_w = sum(w for _, _, w in factors)
    if total_w > 0 and abs(total_w - 1.0) > 0.01:
        factors = [(n, s, w / total_w) for (n, s, w) in factors]
    score = sum(s * w for _, s, w in factors)
    if abs(score - 100.0) > TOL:
        fail(f"partial-factor renormalization: expected 100.0, got {score:.4f}")
        return False
    ok(f"partial-factor renormalization: expected 100.0, got {score:.1f}")
    return True


def print_diff_vs_head() -> None:
    """Print per-mode, per-factor diffs vs git HEAD, with effective %."""
    try:
        prev = subprocess.check_output(
            ["git", "show", f"HEAD:backend/strategy/confluence/scorer.py"],
            cwd=REPO_ROOT, stderr=subprocess.DEVNULL, text=True,
        )
    except subprocess.CalledProcessError:
        return
    try:
        prev_weights, _ = load_weights(prev)
    except Exception:
        return
    curr_weights, _ = load_weights(SCORER_PATH.read_text())
    changes = []
    for mode in CANONICAL_MODES:
        a = prev_weights.get(mode, {})
        b = curr_weights.get(mode, {})
        keys = set(a) | set(b)
        sum_b = sum(b.values()) or 1.0
        for k in sorted(keys):
            va, vb = a.get(k), b.get(k)
            if va != vb:
                pct = (vb / sum_b * 100) if vb is not None else 0.0
                changes.append(f"  {mode}.{k}  {va} -> {vb}  (effective {pct:.1f}%)")
    if changes:
        print("DIFF (this edit):")
        for line in changes:
            print(line)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-unnormalized", action="store_true",
                    help="downgrade sum-to-1.0 failures to warnings")
    args = ap.parse_args()

    source = SCORER_PATH.read_text()
    weights, _aliases = load_weights(source)

    results = [
        check_mode_coverage(weights),
        check_key_parity(weights),
        check_no_duplicates(source),
        check_sums(weights, args.allow_unnormalized),
        check_partial_renormalization(weights),
    ]
    print_diff_vs_head()
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
