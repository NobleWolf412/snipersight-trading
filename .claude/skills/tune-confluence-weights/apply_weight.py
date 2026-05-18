#!/usr/bin/env python3
"""Apply a mechanical weight edit to scorer.py — no AI required.

Subcommands:
  set    MODE KEY VALUE        # bump or replace one weight
  add    KEY VALUE             # add a factor to every mode
  drop   KEY                   # remove a factor from every mode
  rename OLD NEW               # rename a factor key in every mode

MODE accepts canonical names (macro_surveillance, intraday_aggressive,
precision, stealth_balanced) or aliases (overwatch, strike, surgical,
stealth). Edits are written back to scorer.py; run verify_weights.py
afterwards (the skill does this automatically).
"""
from __future__ import annotations

import argparse
import sys

from _weights_io import (
    SCORER_PATH,
    WEIGHT_DICTS,
    add_key_to_dict,
    list_modes,
    remove_key_from_dict,
    rename_key_everywhere,
    resolve_mode,
    rewrite_dict_value,
)


def cmd_set(args: argparse.Namespace) -> int:
    dict_name = resolve_mode(args.mode)
    src = SCORER_PATH.read_text()
    new = rewrite_dict_value(src, dict_name, args.key, args.value)
    SCORER_PATH.write_text(new)
    print(f"set {args.mode}.{args.key} = {args.value}")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    src = SCORER_PATH.read_text()
    for dict_name in WEIGHT_DICTS:
        src = add_key_to_dict(src, dict_name, args.key, args.value)
    SCORER_PATH.write_text(src)
    print(f"added {args.key}={args.value} to all 4 modes")
    return 0


def cmd_drop(args: argparse.Namespace) -> int:
    src = SCORER_PATH.read_text()
    for dict_name in WEIGHT_DICTS:
        src = remove_key_from_dict(src, dict_name, args.key)
    SCORER_PATH.write_text(src)
    print(f"dropped {args.key} from all 4 modes")
    return 0


def cmd_rename(args: argparse.Namespace) -> int:
    src = SCORER_PATH.read_text()
    src = rename_key_everywhere(src, args.old, args.new)
    SCORER_PATH.write_text(src)
    print(f"renamed {args.old} -> {args.new} in all 4 modes")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_set = sub.add_parser("set", help="set MODE.KEY = VALUE")
    p_set.add_argument("mode", choices=list_modes(), metavar="MODE")
    p_set.add_argument("key")
    p_set.add_argument("value", type=float)
    p_set.set_defaults(func=cmd_set)

    p_add = sub.add_parser("add", help="add KEY=VALUE to every mode")
    p_add.add_argument("key")
    p_add.add_argument("value", type=float)
    p_add.set_defaults(func=cmd_add)

    p_drop = sub.add_parser("drop", help="remove KEY from every mode")
    p_drop.add_argument("key")
    p_drop.set_defaults(func=cmd_drop)

    p_ren = sub.add_parser("rename", help="rename OLD -> NEW in every mode")
    p_ren.add_argument("old")
    p_ren.add_argument("new")
    p_ren.set_defaults(func=cmd_rename)

    args = ap.parse_args()
    try:
        return args.func(args)
    except (KeyError, ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
