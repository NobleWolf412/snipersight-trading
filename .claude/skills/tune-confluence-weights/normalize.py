#!/usr/bin/env python3
"""Rewrite each weight dict in scorer.py so its values sum to 1.0.

Pure arithmetic — no AI judgment. Replaces what normalize_all_weights.py
was doing on the command line.

Usage:
  normalize.py             # normalize all four modes
  normalize.py --mode strike  # normalize one mode only
  normalize.py --dry-run   # print the would-be values without writing
"""
from __future__ import annotations

import argparse
import sys

from _weights_io import (
    SCORER_PATH,
    WEIGHT_DICTS,
    load_weight_dicts,
    resolve_mode,
    rewrite_dict_value,
)


def normalize_one(source: str, dict_name: str, dry_run: bool) -> str:
    weights = load_weight_dicts(source)[dict_name]
    total = sum(weights.values())
    if total == 0:
        raise RuntimeError(f"{dict_name} sums to 0 — refusing to divide")
    print(f"{dict_name}: total={total:.4f}")
    for key, val in weights.items():
        new_val = round(val / total, 6)
        print(f"  {key:30s} {val:.4f} -> {new_val:.4f}")
        if not dry_run:
            source = rewrite_dict_value(source, dict_name, key, new_val)
    return source


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", help="normalize only this mode (canonical or alias)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print changes without writing scorer.py")
    args = ap.parse_args()

    src = SCORER_PATH.read_text()
    targets = [resolve_mode(args.mode)] if args.mode else list(WEIGHT_DICTS)

    for dict_name in targets:
        src = normalize_one(src, dict_name, args.dry_run)

    if not args.dry_run:
        SCORER_PATH.write_text(src)
        print("\nwrote scorer.py — now run verify_weights.py")
    else:
        print("\n(dry-run, scorer.py unchanged)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
