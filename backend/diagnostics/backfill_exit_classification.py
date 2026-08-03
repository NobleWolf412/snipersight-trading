"""Stamp the honest outcome fields onto journal history.

The classifier runs at write time from now on, but 1,045 trades were recorded
before it existed, and every analysis over them — including the ones that
produced the 2026-05-29 and 05-30 decision docs — read a win rate built from a
label that was wrong for 306 rows. This rewrites those rows with `outcome`,
`exit_path`, `realized_r` and `label_conflict` so the history becomes analysable
instead of discarded.

NEVER writes in place. The source file is left byte-identical and a `.classified`
sibling is produced; a backfill that destroys the only copy of the evidence is a
worse bug than the one it fixes.

    python -m diagnostics.backfill_exit_classification            # report only
    python -m diagnostics.backfill_exit_classification --write    # emit files
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bot.exit_classification import classify  # noqa: E402

CACHE = Path(__file__).resolve().parents[1] / "cache"
SOURCES = ["trade_journal.pre-patchB-2026-05-20.jsonl", "trade_journal.jsonl"]


def load(path: Path):
    rows = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def report(name: str, rows: list) -> dict:
    cls = [classify(r) for r in rows]
    oc = collections.Counter(c["outcome"] for c in cls)
    conf = [c for c in cls if c["label_conflict"]]
    decided = oc["WIN"] + oc["LOSS"]
    naive = sum(1 for r in rows if (r.get("pnl") or 0) > 0)

    print(f"\n{name}   n={len(rows)}")
    print(f"  WIN {oc['WIN']}   LOSS {oc['LOSS']}   SCRATCH {oc['SCRATCH']}   UNKNOWN {oc['UNKNOWN']}")
    print(f"  win rate, counted as before (pnl > 0) : {naive / len(rows) * 100:5.1f}%")
    print(f"  win rate, scratches removed           : "
          f"{oc['WIN'] / decided * 100 if decided else 0:5.1f}%   (of {decided} decided)")
    print(f"  label conflicts                       : {len(conf)}"
          + (f"   {dict(collections.Counter(c['exit_path'] for c in conf))}" if conf else ""))
    return {"n": len(rows), "conflicts": len(conf), "outcomes": dict(oc)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="emit <name>.classified.jsonl beside each source")
    args = ap.parse_args()

    total_conf = 0
    for name in SOURCES:
        src = CACHE / name
        if not src.exists():
            print(f"missing: {src}")
            continue
        rows = load(src)
        stats = report(name, rows)
        total_conf += stats["conflicts"]

        if args.write:
            out = src.with_suffix(".classified.jsonl")
            with out.open("w", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps({**r, **classify(r)}, default=str) + "\n")
            print(f"  -> wrote {out.name} ({len(rows)} rows); {src.name} untouched")

    print(f"\n{total_conf} rows across the book carry a label their P&L contradicts.")
    if not args.write:
        print("re-run with --write to emit the classified copies.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
