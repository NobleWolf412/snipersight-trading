"""
Phase 4F — score-calibration comparison (pre-fix vs post-4C/4D/4E).

Purpose
-------
Measure whether the Phase 4 scorer fixes (4C OB wick demotion, 4D freshness
recompute, 4E institutional-sequence temporal ordering) actually changed the
score distribution — i.e. whether the scorer went from rubber-stamping to
discriminating — by comparing factor-bearing signals logged BEFORE the fixes
shipped against signals logged AFTER.

Why this is non-trivial
-----------------------
1. signals.jsonl only persists the per-factor `factors` breakdown for signals
   that CLEAR the gate (confluence >= mode gate). Sub-gate scored signals carry
   a confluence number but no breakdown — so this only sees gate-clearers.
2. The bot re-scores the same setup every scan while a position/zone persists,
   so raw factor-bearing rows are massively inflated by re-scoring (e.g. one ADA
   short logged 226 times). We DEDUP per (session, symbol, direction) to one
   representative setup — the LAST row, which carries the most mature scoring.
3. Pre-fix vs post-fix is detected by CODE SIGNATURE, not filename/date: the 4E
   rewrite emits new institutional-sequence rationale strings (the arrow form
   and the "no subsequent / no preceding / temporal order" tier reasons). The
   old code emits "Sweep + Shift + OB". This is robust to a stale-code bot that
   kept running old logic after the commit landed (which is exactly what bit the
   first post-4E session — the backend was never hard-restarted).

Usage
-----
    python -m backend.diagnostics.phase4f_score_calibration

Output is paste-friendly: short summary first, per-cohort tables second.

NOT a gate-recalibration tool. It REPORTS the distribution delta; any
min_confluence_score change is a separate, baseline-gated decision (CLAUDE.md
§15 hard boundary) and must not be derived from a thin post-fix sample.
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys
from collections import Counter
from typing import Dict, List, Optional, Tuple

# Institutional-sequence tiers emitted by the 4E rewrite (scorer.py
# _score_institutional_sequence). Kept in scoring order for the report.
INST_TIERS = [100, 70, 50, 40, 20, 0]

# Substrings that ONLY the post-4E institutional-sequence reasons contain.
_POST_SIGNATURES = ("→", "no subsequent", "no preceding", "temporal order")
# Substring that ONLY the pre-fix institutional-sequence reason contains.
_PRE_SIGNATURE = "Sweep + Shift + OB"


def _classify_session(path: str) -> Optional[bool]:
    """Return True if session ran post-4E code, False if pre-fix, None if no
    factor-bearing rows exist to judge from."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if not r.get("factors"):
                continue
            for fac in r["factors"]:
                if fac["name"] == "Institutional Sequence":
                    rat = fac.get("rationale", "")
                    if any(sig in rat for sig in _POST_SIGNATURES):
                        return True
                    if _PRE_SIGNATURE in rat:
                        return False
    return None


def _collect(paths: List[str]) -> Tuple[int, Counter, List[float], int, List[float]]:
    """Dedup per (session, symbol, direction) -> last factor-bearing row, then
    aggregate institutional tiers, OB factor scores, wick-cap count, confluence."""
    setups: Dict[Tuple[str, str, str], dict] = {}
    for path in paths:
        sid = os.path.basename(os.path.dirname(path))
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                if not r.get("factors"):
                    continue
                setups[(sid, r.get("symbol"), r.get("direction"))] = r

    inst: Counter = Counter()
    ob_scores: List[float] = []
    wick_capped = 0
    conf: List[float] = []
    for r in setups.values():
        conf.append(r.get("confluence", 0.0))
        for fac in r["factors"]:
            if fac["name"] == "Institutional Sequence":
                inst[int(round(fac["score"]))] += 1
            elif fac["name"] == "Order Block":
                ob_scores.append(fac["score"])
                if fac["score"] <= 35.0:  # 4C wick-only cap signature
                    wick_capped += 1
    return len(setups), inst, ob_scores, wick_capped, conf


def _print_cohort(name: str, n: int, inst: Counter, ob: List[float],
                  wick_capped: int, conf: List[float]) -> None:
    print("=" * 60)
    print(f"{name} — {n} distinct setups")
    print("-" * 60)
    total = sum(inst.values())
    print("Institutional Sequence tiers:")
    for tier in INST_TIERS:
        c = inst.get(tier, 0)
        pct = (100 * c / total) if total else 0.0
        print(f"  {tier:>3}: {c:>5} ({pct:5.1f}%)")
    if ob:
        print(
            f"OB factor: median={statistics.median(ob):.0f} | "
            f"wick-capped(<=35)={wick_capped}/{len(ob)} "
            f"({100 * wick_capped / len(ob):.1f}%)"
        )
    if conf:
        print(
            f"Confluence: median={statistics.median(conf):.1f} "
            f"min={min(conf):.1f} max={max(conf):.1f}"
        )


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # arrow glyph in tier reasons
    root = os.path.join("logs", "paper_trading", "session_*", "signals.jsonl")
    sessions = sorted(glob.glob(root))

    pre_paths: List[str] = []
    post_paths: List[str] = []
    for p in sessions:
        sig = _classify_session(p)
        if sig is True:
            post_paths.append(p)
        elif sig is False:
            pre_paths.append(p)

    pre = _collect(pre_paths)
    post = _collect(post_paths)

    # ---- Summary first (CLAUDE.md §12 output format) ----
    pre_inst, post_inst = pre[1], post[1]
    pre_100 = (100 * pre_inst.get(100, 0) / sum(pre_inst.values())) if sum(pre_inst.values()) else 0
    post_100 = (100 * post_inst.get(100, 0) / sum(post_inst.values())) if sum(post_inst.values()) else 0
    print("PHASE 4F — SCORE CALIBRATION (pre-fix vs post-4E)")
    print(f"  sessions: pre-fix={len(pre_paths)} post-4E={len(post_paths)}")
    print(f"  distinct setups: pre-fix={pre[0]} post-4E={post[0]}")
    print(f"  Institutional=100 rate: {pre_100:.1f}%  ->  {post_100:.1f}%")
    if post[0] < 30:
        print(f"  ⚠ post-4E n={post[0]} is BELOW calibration threshold (>=30 distinct,")
        print(f"     multi-regime). Directional read only — NO gate recalibration.")
    print()

    _print_cohort("PRE-FIX (stale code)", *pre)
    _print_cohort("POST-4E", *post)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
