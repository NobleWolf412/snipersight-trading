"""
P/D direction efficacy — is the Premium/Discount factor's directional lean a useful
predictor, or is it inverted (especially against with-trend BOS continuation)?

FINDING (2026-06-13, post-clamp era, n=123 matched trades): the P/D factor's
endorsement is INVERTED as a predictor in the current trending regime —
  - P/D FAVORED the direction        -> WORST cohort (38% WR, -4.42/trade)
  - P/D OPPOSED + aligned BOS         -> BEST cohort  (54% WR, +1.71/trade)
i.e. the trades that overrode P/D to follow a confirmed continuation BOS won; the
trades P/D endorsed lost. See decisions/2026-06-13__pd-factor-inverted-in-trends-finding.md.

Method (clean cut — addresses the confounds in the first exploratory pass):
  1. Per-trade matching: each closed trade is tied to its OWN originating signal
     (same session, same symbol+direction, nearest timestamp), not symbol-level.
  2. Era filter: only trades with entry_time >= ERA_START (post the 2026-05-31
     wide-stop clamp), to remove the known wide-stop-era loss confound.
  3. Three buckets by the trade's own signal P/D-vs-BOS status: P/D-favored /
     P/D-opposed-with-aligned-BOS / P/D-opposed-no-BOS.

LIMITATIONS (do not over-read): single regime (post-Jun-1 is down_normal-dominated,
so the finding is "P/D inverted IN TRENDS" — may flip in ranging markets); modest n
(~40/bucket); PnL is MODELED (paper), so relative-better != net-profitable after fees.

READ-ONLY. No engine files modified. No thresholds proposed.

USAGE
    python -X utf8 -m backend.diagnostics.pd_direction_efficacy
    python -X utf8 -m backend.diagnostics.pd_direction_efficacy --era 2026-06-01
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import defaultdict
from typing import Dict, List, Optional

import pandas as pd


def _ts(v) -> pd.Timestamp:
    t = pd.Timestamp(v)
    return t.tz_localize("UTC") if t.tz is None else t.tz_convert("UTC")


def pd_stance(rationale: str, direction: str) -> Optional[str]:
    """'favors' / 'opposes' / None — P/D factor vs the chosen direction."""
    is_long = direction == "LONG"
    if "Discount zone" in rationale:
        zone = "discount"
    elif "Premium zone" in rationale:
        zone = "premium"
    else:
        return None
    favors = (is_long and zone == "discount") or (not is_long and zone == "premium")
    return "favors" if favors else "opposes"


def ms_continuation(rationale: str, score: float) -> bool:
    """Aligned BOS continuation in the trade direction (MS factor is direction-scored)."""
    return ("BOS" in rationale) and score >= 50.0


_BUCKETS = [
    "P/D FAVORED direction",
    "P/D OPPOSED + aligned BOS (conflict)",
    "P/D OPPOSED, no BOS",
    "P/D neutral/no-data",
]


def measure(era_start: pd.Timestamp) -> Dict:
    results: List[tuple] = []
    matched = unmatched = era_skipped = 0

    for sess_dir in glob.glob(os.path.join("logs", "paper_trading", "session_*")):
        sig_path = os.path.join(sess_dir, "signals.jsonl")
        trd_path = os.path.join(sess_dir, "trades.jsonl")
        if not (os.path.exists(sig_path) and os.path.exists(trd_path)):
            continue
        sigs: Dict[tuple, list] = defaultdict(list)
        with open(sig_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                if not r.get("factors"):
                    continue
                pd_r = ms_r = ""
                ms_sc = 0.0
                for fac in r["factors"]:
                    if fac["name"] == "Premium/Discount Zone":
                        pd_r = fac.get("rationale", "")
                    elif fac["name"] == "Market Structure":
                        ms_r, ms_sc = fac.get("rationale", ""), fac.get("score", 0)
                sigs[(r["symbol"], r["direction"])].append((_ts(r["timestamp"]), pd_r, ms_r, ms_sc))

        with open(trd_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                t = json.loads(line)
                et = _ts(t.get("entry_time"))
                if et < era_start:
                    era_skipped += 1
                    continue
                cands = sigs.get((t.get("symbol"), t.get("direction")), [])
                best = bestdt = None
                for (ts, pd_r, ms_r, ms_sc) in cands:
                    dt = abs((et - ts).total_seconds())
                    if bestdt is None or dt < bestdt:
                        bestdt, best = dt, (pd_r, ms_r, ms_sc)
                if best is None:
                    unmatched += 1
                    continue
                matched += 1
                pd_r, ms_r, ms_sc = best
                stance = pd_stance(pd_r, t["direction"])
                if stance == "favors":
                    bucket = _BUCKETS[0]
                elif stance == "opposes" and ms_continuation(ms_r, ms_sc):
                    bucket = _BUCKETS[1]
                elif stance == "opposes":
                    bucket = _BUCKETS[2]
                else:
                    bucket = _BUCKETS[3]
                results.append((bucket, float(t.get("pnl", 0))))

    return {"results": results, "matched": matched, "unmatched": unmatched,
            "era_skipped": era_skipped}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="P/D direction efficacy (read-only).")
    ap.add_argument("--era", default="2026-06-01", help="entry_time floor (post wide-stop clamp)")
    args = ap.parse_args()
    era = pd.Timestamp(args.era, tz="UTC")

    m = measure(era)
    by_bucket: Dict[str, list] = defaultdict(list)
    for b, p in m["results"]:
        by_bucket[b].append(p)
    # mass conservation (§16 rubric 3)
    assert sum(len(v) for v in by_bucket.values()) == m["matched"], "bucket conservation"

    print("PD DIRECTION EFFICACY (per-trade, era-filtered)")
    print(f"  era >= {args.era} | matched {m['matched']} | unmatched {m['unmatched']} | "
          f"pre-era skipped {m['era_skipped']}")
    print()
    for b in _BUCKETS:
        ps = by_bucket.get(b, [])
        if not ps:
            print(f"  {b}: n=0")
            continue
        wins = sum(1 for p in ps if p > 0)
        print(f"  {b}:")
        print(f"      n={len(ps)} | win-rate {100*wins/len(ps):.0f}% | "
              f"avg {sum(ps)/len(ps):+.2f} | total {sum(ps):+.2f}")
    print()
    print("LIMITATIONS: single regime (post-Jun-1 trending) · modest n · modeled PnL.")
    print("Finding = 'P/D inverted IN TRENDS'; may flip in ranging markets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
