"""Shared read/write for MODE_FACTOR_WEIGHTS in scorer.py.

Used by verify_weights.py, apply_weight.py, and normalize.py so they
all see the file the same way. No AI in this layer — pure code.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
SCORER_PATH = REPO_ROOT / "backend" / "strategy" / "confluence" / "scorer.py"

WEIGHT_DICTS = (
    "_OVERWATCH_WEIGHTS",
    "_STRIKE_WEIGHTS",
    "_SURGICAL_WEIGHTS",
    "_STEALTH_WEIGHTS",
)

CANONICAL_MODES = {
    "macro_surveillance": "_OVERWATCH_WEIGHTS",
    "intraday_aggressive": "_STRIKE_WEIGHTS",
    "precision":           "_SURGICAL_WEIGHTS",
    "stealth_balanced":    "_STEALTH_WEIGHTS",
}
ALIASES = {
    "overwatch": "_OVERWATCH_WEIGHTS",
    "strike":    "_STRIKE_WEIGHTS",
    "surgical":  "_SURGICAL_WEIGHTS",
    "stealth":   "_STEALTH_WEIGHTS",
}


def load_weight_dicts(source: str) -> Dict[str, Dict[str, float]]:
    """Return {'_OVERWATCH_WEIGHTS': {...}, ...} parsed from source."""
    tree = ast.parse(source)
    out: Dict[str, Dict[str, float]] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in WEIGHT_DICTS:
                out[target.id] = ast.literal_eval(node.value)
    return out


def resolve_mode(name: str) -> str:
    """Map a user-supplied mode name (canonical or alias) to its dict name."""
    key = name.strip().lower()
    if key in CANONICAL_MODES:
        return CANONICAL_MODES[key]
    if key in ALIASES:
        return ALIASES[key]
    raise ValueError(
        f"unknown mode {name!r}; expected one of "
        f"{sorted(set(CANONICAL_MODES) | set(ALIASES))}"
    )


def _dict_block_span(source: str, dict_name: str) -> Tuple[int, int]:
    """Find the [start, end) char offsets of `<dict_name> = { ... }` in source."""
    m = re.search(rf"^{re.escape(dict_name)}\s*=\s*\{{", source, re.MULTILINE)
    if not m:
        raise RuntimeError(f"{dict_name} not found in scorer.py")
    start = m.start()
    depth = 0
    i = m.end() - 1
    while i < len(source):
        c = source[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return start, i + 1
        i += 1
    raise RuntimeError(f"unterminated dict literal for {dict_name}")


def rewrite_dict_value(source: str, dict_name: str, key: str, new_value: float) -> str:
    """Replace `"<key>": <old>` inside <dict_name> with the new value.

    Preserves indentation, comments, and key order. Raises if the key is
    absent — call add_key_to_dict first if you need that.
    """
    start, end = _dict_block_span(source, dict_name)
    block = source[start:end]
    pattern = re.compile(
        rf'(^\s*"{re.escape(key)}"\s*:\s*)([-+]?\d*\.?\d+)(\s*,?)', re.MULTILINE
    )
    new_block, n = pattern.subn(rf"\g<1>{new_value:g}\g<3>", block, count=1)
    if n == 0:
        raise KeyError(f"{key!r} not found in {dict_name}")
    return source[:start] + new_block + source[end:]


def add_key_to_dict(source: str, dict_name: str, key: str, value: float) -> str:
    """Append `"<key>": <value>,` before the closing brace of <dict_name>."""
    start, end = _dict_block_span(source, dict_name)
    block = source[start:end]
    if re.search(rf'^\s*"{re.escape(key)}"\s*:', block, re.MULTILINE):
        raise KeyError(f"{key!r} already present in {dict_name}")
    # find the closing brace and back up over trailing whitespace/comma
    close_idx = block.rfind("}")
    head = block[:close_idx].rstrip()
    # match the indentation of the previous line
    last_line = head.splitlines()[-1]
    indent = re.match(r"\s*", last_line).group(0)
    # ensure trailing comma on previous entry
    if not head.endswith(","):
        head = head + ","
    new_block = head + f'\n{indent}"{key}": {value:g},\n}}'
    return source[:start] + new_block + source[end:]


def remove_key_from_dict(source: str, dict_name: str, key: str) -> str:
    """Drop the entire `"<key>": ...,` line from <dict_name>."""
    start, end = _dict_block_span(source, dict_name)
    block = source[start:end]
    pattern = re.compile(rf'^\s*"{re.escape(key)}"\s*:.*?\n', re.MULTILINE)
    new_block, n = pattern.subn("", block, count=1)
    if n == 0:
        raise KeyError(f"{key!r} not found in {dict_name}")
    return source[:start] + new_block + source[end:]


def rename_key_everywhere(source: str, old: str, new: str) -> str:
    """Rename a factor key in all 4 weight dicts."""
    for dict_name in WEIGHT_DICTS:
        start, end = _dict_block_span(source, dict_name)
        block = source[start:end]
        pattern = re.compile(rf'(^\s*"){re.escape(old)}("\s*:)', re.MULTILINE)
        new_block = pattern.sub(rf"\g<1>{new}\g<2>", block)
        source = source[:start] + new_block + source[end:]
    return source


def list_modes() -> List[str]:
    return list(CANONICAL_MODES) + list(ALIASES)
