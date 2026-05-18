#!/usr/bin/env python3
"""End-to-end orchestrator for tune-confluence-weights.

The skill calls this once per user request instead of running edit/verify
manually and bouncing back to chat. It encodes the deterministic
follow-ups so they happen without a second round trip:

  edit  →  verify  →  (deterministic fix?)  →  re-verify  →  report

Exit codes:
  0  everything green, report printed
  2  needs human judgment (key drift, duplicate, partial-renorm) — chat
     should surface the verifier failure to the user
  1  internal error

Usage:
  run.py set    MODE KEY VALUE        # mechanical
  run.py add    KEY VALUE
  run.py drop   KEY
  run.py rename OLD NEW
  run.py normalize [--mode MODE]
  run.py verify-only                  # AI just made an Edit, now confirm

Auto-fix policy (extend this list, never the chat):
  - sums ≠ 1.0           → run normalize.py, re-verify
  - allow-unnormalized-flagged-by-caller → skip auto-fix
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sh(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr)


def run_verify(allow_unnormalized: bool = False) -> tuple[int, str]:
    cmd = ["python", str(HERE / "verify_weights.py")]
    if allow_unnormalized:
        cmd.append("--allow-unnormalized")
    return sh(cmd)


def classify_failure(output: str) -> str:
    """Return a tag for the auto-fix dispatcher."""
    if "sums to" in output and "expected 1.000" in output:
        return "unnormalized"
    if "key parity FAILED" in output:
        return "key_drift"          # human judgment
    if "duplicate keys" in output:
        return "duplicates"         # human judgment
    if "partial-factor renormalization" in output and "FAILED" in output:
        return "scoring_invariant"  # code regression, not a weight issue
    return "unknown"


def auto_fix(tag: str) -> tuple[bool, str]:
    """Returns (handled, log_line). Only deterministic fixes belong here."""
    if tag == "unnormalized":
        rc, out = sh(["python", str(HERE / "normalize.py")])
        return rc == 0, f"auto-fix: normalized all modes\n{out}"
    return False, ""


def apply_edit(args: argparse.Namespace) -> tuple[int, str]:
    if args.cmd == "verify-only":
        return 0, ""
    if args.cmd == "normalize":
        cmd = ["python", str(HERE / "normalize.py")]
        if args.mode:
            cmd += ["--mode", args.mode]
        return sh(cmd)
    # apply_weight.py subcommands
    cmd = ["python", str(HERE / "apply_weight.py"), args.cmd]
    if args.cmd == "set":
        cmd += [args.mode, args.key, str(args.value)]
    elif args.cmd == "add":
        cmd += [args.key, str(args.value)]
    elif args.cmd == "drop":
        cmd += [args.key]
    elif args.cmd == "rename":
        cmd += [args.old, args.new]
    return sh(cmd)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--allow-unnormalized", action="store_true",
                    help="skip the auto-normalize follow-up")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("set"); s.add_argument("mode"); s.add_argument("key"); s.add_argument("value", type=float)
    a = sub.add_parser("add"); a.add_argument("key"); a.add_argument("value", type=float)
    d = sub.add_parser("drop"); d.add_argument("key")
    r = sub.add_parser("rename"); r.add_argument("old"); r.add_argument("new")
    n = sub.add_parser("normalize"); n.add_argument("--mode")
    sub.add_parser("verify-only")
    args = ap.parse_args()

    rc, edit_out = apply_edit(args)
    if rc != 0:
        print(edit_out)
        return 1
    if edit_out:
        print(edit_out)

    rc, verify_out = run_verify(allow_unnormalized=args.allow_unnormalized)
    if rc == 0:
        print(verify_out)
        return 0

    tag = classify_failure(verify_out)
    handled, log = auto_fix(tag)
    if not handled:
        print(verify_out)
        print(f"\nneeds human judgment (classified as: {tag})")
        return 2

    print(log)
    rc, verify_out = run_verify()
    print(verify_out)
    return 0 if rc == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
