"""
conflict_density_anatomy.py — measure-first diagnostic for the conflict_density gate.

OPERATOR QUESTION (2026-06-08): when conflict_density blocks a trade, what is the
opposition actually MADE OF? The gate counts every opposing A/B order block + opposing
BOS equally (scorer.py:415-432, `conflict_count += 1`) and rejects at >=3 (non-overwatch)
/ >=5 (overwatch). This tool asks whether that flat count is hiding structure:

  - GRADE:      A vs B order blocks. The gate counts them identically. Is the opposition
                strong (A, violent displacement) or marginal (B)?
  - TYPE:       BOS (continuation threat) vs OB (zone).
  - TIMEFRAME:  in-trade-scale (e.g. 5m/15m for a scalp) vs HTF-ABOVE-scale (1h/4h). A 4H
                OB overhead that a scalp long is being magnetized TOWARD is a target/magnet,
                not a continuation threat — but the gate can't tell a target from a wall.
  - DIRECTION:  which pre-direction was being evaluated (inferred from the opposing
                structures' direction: opposition to LONG is bearish, to SHORT is bullish).

HYPOTHESIS UNDER TEST: conflict_density over-blocks by (a) counting weak zones equally
with strong ones, and (b) counting HTF-above-scale "target" zones as if they were
in-scale "threats."

READ-ONLY. Source: backend/cache/telemetry.db, event_type='signal_rejected',
gate_name='conflict_density'. Does NOT import engine code and does NOT touch the gate.
Per CLAUDE.md: measure-before-build, and scorer.py is standing-fix-protected — this only
measures, it proposes no threshold change.

KNOWN INSTRUMENTATION GAP (this tool surfaces it as a finding): the reject telemetry
serializes OB grade + timeframe but NOT the OB price level, and logs no scan-time price.
So the GEOMETRIC axis you actually want — above/below current price, in-path (target) vs
against-path (threat) — is NOT computable from telemetry. This tool quantifies grade /
type / timeframe-tier (what IS captured) and reports the gap. Closing it is a one-line
telemetry enrichment: serialize ob.top / ob.bottom + current_price into the
conflict_density GateResult.metadata (scorer.py ~459), after which this tool gains the
geometry axis. That enrichment is itself a scoring-path edit → symmetry-guard + baseline.

USAGE
    python -m backend.diagnostics.conflict_density_anatomy                 # last session (auto)
    python -m backend.diagnostics.conflict_density_anatomy --since 2026-06-06T00:24:27Z
    python -m backend.diagnostics.conflict_density_anatomy --symbol WLD/USDT:USDT
    python -m backend.diagnostics.conflict_density_anatomy --htf-min-tf 1h --top 12
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import json
from collections import Counter, defaultdict

DB_PATH = os.path.join("backend", "cache", "telemetry.db")

# Timeframe → minutes, for HTF-tier classification.
_TF_MINUTES = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "4h": 240, "6h": 360, "12h": 720,
    "1d": 1440, "3d": 4320, "1w": 10080,
}

# One opposing structure label, e.g.
#   "bearish BOS @ 0.4979 [15m]"
#   "bearish OB(A) [5m]"
#   "bullish OB(B) @ 0.0910–0.0925 [1H]"
_COND_RE = re.compile(
    r"^(?P<dir>bullish|bearish)\s+"
    r"(?P<kind>BOS|CHOCH|OB)"
    r"(?:\((?P<grade>[A-D])\))?"
    r"(?:\s+@\s+(?P<price>[0-9.]+)(?:[–\-][0-9.]+)?)?"
    r"\s*\[(?P<tf>[^\]]+)\]\s*$",
    re.IGNORECASE,
)

# "flip SHORT blocked by [conflict_density]" → primary direction was the opposite (LONG).
_FLIP_RE = re.compile(r"flip\s+(LONG|SHORT)\s+blocked", re.IGNORECASE)


def _norm_tf(tf: str) -> str:
    return (tf or "").strip().lower()


def _resolve_window(cur, since: str | None, gap_seconds: int = 600) -> tuple[str, str]:
    """Return (since_iso, until_iso). If since is given, use it → now. Otherwise resolve
    the most-recent contiguous session by walking back from the latest scan to the first
    inter-scan gap > gap_seconds (no session_id exists in telemetry)."""
    cur.execute(
        "SELECT MAX(timestamp) FROM telemetry_events WHERE event_type='signal_rejected'"
    )
    latest = cur.fetchone()[0]
    if not latest:
        return ("", "")
    if since:
        return (since, latest)

    # Walk scan_started timestamps backward, find the first gap > gap_seconds.
    cur.execute(
        "SELECT timestamp FROM telemetry_events "
        "WHERE event_type IN ('scan_started','scan_completed') ORDER BY timestamp DESC"
    )
    rows = [r[0] for r in cur.fetchall()]
    if not rows:
        return ("", latest)

    from datetime import datetime

    def _parse(ts: str) -> float:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()

    # rows are DESC (rows[0] = latest). Walk newer->older; the most-recent session runs
    # from `latest` back to the last timestamp still contiguous (no gap > gap_seconds).
    session_start = rows[0]          # iso string of the oldest contiguous scan
    prev_ts, prev_iso = _parse(rows[0]), rows[0]
    for iso in rows[1:]:
        cur_t = _parse(iso)
        if prev_ts - cur_t > gap_seconds:
            session_start = prev_iso  # newer edge of the gap = session start
            break
        prev_ts, prev_iso = cur_t, iso
        session_start = iso
    return (session_start, latest)


def _fetch_rejections(cur, since: str, until: str, symbol: str | None):
    q = (
        "SELECT symbol, timestamp, data_json FROM telemetry_events "
        "WHERE event_type='signal_rejected' "
        "AND json_extract(data_json,'$.gate_name')='conflict_density' "
        "AND timestamp >= ? AND timestamp <= ?"
    )
    params = [since, until]
    if symbol:
        q += " AND symbol = ?"
        params.append(symbol)
    q += " ORDER BY timestamp"
    cur.execute(q, params)
    return cur.fetchall()


def _infer_primary_dir(reason: str, cond_dirs: list[str]) -> str:
    """Primary direction = opposite of the opposing structures' direction.
    Cross-check against the 'flip X blocked' clause when present."""
    m = _FLIP_RE.search(reason or "")
    if m:
        flip_to = m.group(1).upper()
        return "LONG" if flip_to == "SHORT" else "SHORT"
    if cond_dirs:
        # opposition to a LONG is bearish; to a SHORT is bullish
        bearish = sum(1 for d in cond_dirs if d.lower() == "bearish")
        bullish = len(cond_dirs) - bearish
        return "LONG" if bearish >= bullish else "SHORT"
    return "UNKNOWN"


def run(since: str | None, symbol: str | None, htf_min_tf: str, top: int,
        until: str | None = None) -> int:
    if not os.path.exists(DB_PATH):
        print(f"[ERR] telemetry db not found at {DB_PATH}")
        return 2
    htf_min = _TF_MINUTES.get(_norm_tf(htf_min_tf), 60)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    win_since, win_until = _resolve_window(cur, since)
    if until:
        win_until = until
    if not win_until:
        print("[ERR] no signal_rejected events in telemetry.")
        return 2

    rows = _fetch_rejections(cur, win_since, win_until, symbol)
    if not rows:
        print("CONFLICT-DENSITY ANATOMY")
        print("=" * 60)
        print(f"Window: {win_since} -> {win_until}")
        print(f"Filters: symbol={symbol or 'all'}")
        print("\nNo conflict_density rejections in window. (Either the gate fired on "
              "nothing, or telemetry for this window is empty.)")
        return 0

    tf_counter: Counter = Counter()
    typegrade_counter: Counter = Counter()
    dir_rejections: Counter = Counter()
    dir_conflicts: defaultdict = defaultdict(int)
    sym_counter: Counter = Counter()
    htf_total = 0
    inscale_total = 0
    a_grade = 0
    b_grade = 0
    ob_total = 0
    total_structures = 0
    parse_drift = []  # (symbol, ts, reported_count, parsed_count)
    unparsed = Counter()
    samples = []
    cycles = set()

    for sym, ts, dj in rows:
        try:
            d = json.loads(dj)
        except Exception:
            continue
        meta = d.get("diagnostics") or d.get("metadata") or {}
        conds = meta.get("conflict_conditions") or []
        reported = meta.get("conflict_count")
        reason = d.get("reason", "")
        cycles.add(ts[:16])  # minute-bucket as a cheap cycle proxy
        sym_counter[sym] += 1

        cond_dirs = []
        parsed_n = 0
        for c in conds:
            m = _COND_RE.match(str(c).strip())
            if not m:
                unparsed[str(c)] += 1
                continue
            parsed_n += 1
            total_structures += 1
            g = m.group("dir")
            cond_dirs.append(g)
            kind = m.group("kind").upper()
            grade = (m.group("grade") or "").upper()
            tf = _norm_tf(m.group("tf"))

            tf_counter[tf] += 1
            mins = _TF_MINUTES.get(tf, 0)
            if mins >= htf_min:
                htf_total += 1
            else:
                inscale_total += 1

            if kind == "OB":
                ob_total += 1
                typegrade_counter[f"OB({grade or '?'})"] += 1
                if grade == "A":
                    a_grade += 1
                elif grade == "B":
                    b_grade += 1
            else:
                typegrade_counter[kind] += 1

        pdir = _infer_primary_dir(reason, cond_dirs)
        dir_rejections[pdir] += 1
        if isinstance(reported, int):
            dir_conflicts[pdir] += reported
            if parsed_n and parsed_n != reported:
                parse_drift.append((sym, ts, reported, parsed_n))
        if len(samples) < 5:
            samples.append((sym, ts, reason[:80], parsed_n,
                            cond_dirs[:1] and cond_dirs[0] or "?"))

    n_rej = len(rows)
    pct = lambda n, d: (100.0 * n / d) if d else 0.0

    # ---- headline ----
    htf_share = pct(htf_total, total_structures)
    b_share = pct(b_grade, ob_total)
    headline = (
        f"{htf_share:.0f}% of counted opposition is HTF (>= {htf_min_tf}) -- candidate "
        f"magnets/targets, not in-scale continuation threats. "
        f"{b_share:.0f}% of opposing OBs are B-grade (marginal), counted equally with A."
    )

    print("CONFLICT-DENSITY ANATOMY")
    print("=" * 60)
    print(f"Source: telemetry.db signal_rejected (gate_name=conflict_density)")
    print(f"Window: {win_since} -> {win_until}")
    print(f"Filters: symbol={symbol or 'all'}   HTF tier = >= {htf_min_tf}")
    print(f"Rejections: {n_rej}   ~cycles: {len(cycles)}   symbols: {len(sym_counter)}")
    print(f"Total opposing structures counted: {total_structures} "
          f"(mean {total_structures / n_rej:.1f}/rejection)")
    print()
    print("HEADLINE")
    print("-" * 40)
    print(headline)
    print()

    print("OPPOSITION BY TIMEFRAME")
    print("-" * 40)
    print(f"{'TF':<8}{'count':>8}{'%':>8}")
    for tf, n in sorted(tf_counter.items(), key=lambda kv: -_TF_MINUTES.get(kv[0], 0)):
        print(f"{tf:<8}{n:>8}{pct(n, total_structures):>7.1f}%")
    print(f"  -> HTF (>= {htf_min_tf}): {pct(htf_total, total_structures):.1f}%"
          f"   in-scale (< {htf_min_tf}): {pct(inscale_total, total_structures):.1f}%")
    print()

    print("OPPOSITION BY TYPE x GRADE")
    print("-" * 40)
    print(f"{'kind':<10}{'count':>8}{'%':>8}")
    for k, n in typegrade_counter.most_common():
        print(f"{k:<10}{n:>8}{pct(n, total_structures):>7.1f}%")
    print(f"  -> of OBs: A-grade {pct(a_grade, ob_total):.1f}%  "
          f"B-grade {pct(b_grade, ob_total):.1f}%   (gate counts A==B==1)")
    print()

    print("PER PRIMARY DIRECTION")
    print("-" * 40)
    print(f"{'dir':<10}{'rejections':>12}{'mean conflict':>16}")
    for dconf in ("LONG", "SHORT", "UNKNOWN"):
        r = dir_rejections.get(dconf, 0)
        if not r:
            continue
        mc = dir_conflicts.get(dconf, 0) / r if r else 0
        print(f"{dconf:<10}{r:>12}{mc:>16.1f}")
    print()

    print(f"TOP SYMBOLS (by conflict_density rejections)")
    print("-" * 40)
    for sym, n in sym_counter.most_common(top):
        print(f"{sym:<18}{n:>6}  {pct(n, n_rej):>5.1f}%")
    print()

    if parse_drift:
        print(f"[INTEGRITY] {len(parse_drift)} rejection(s) where parsed structures != "
              f"reported conflict_count (label/parse drift). Sample:")
        for sym, ts, rep, par in parse_drift[:5]:
            print(f"   {sym} {ts}  reported={rep} parsed={par}")
        print()
    if unparsed:
        print(f"[INTEGRITY] {sum(unparsed.values())} condition string(s) did not match the "
              f"parser. Top unparsed forms:")
        for s, n in unparsed.most_common(5):
            print(f"   {n:>4}x  {s!r}")
        print()

    print("INSTRUMENTATION GAP (the geometry axis you actually want)")
    print("-" * 40)
    print("The reject telemetry carries OB grade + timeframe but NOT the OB price level,")
    print("and no scan-time price. So above/below-price and in-path(target)-vs-against-")
    print("path(threat) are NOT computable here -- only grade/type/timeframe-tier are.")
    print("To unlock geometry: serialize ob.top/ob.bottom + current_price into the")
    print("conflict_density GateResult.metadata (backend/strategy/confluence/scorer.py")
    print("~line 459). That is a scoring-path edit -> symmetry-guard + baseline first.")
    print()

    print("RAW (first parsed samples)")
    print("-" * 40)
    for sym, ts, reason, pn, d0 in samples:
        print(f"   {sym} {ts}  parsed={pn} firstdir={d0}  reason={reason!r}")

    con.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Anatomy of conflict_density rejections (read-only).")
    ap.add_argument("--since", default=None,
                    help="UTC ISO start (e.g. 2026-06-06T00:24:27Z). Default: auto-resolve last session.")
    ap.add_argument("--until", default=None,
                    help="UTC ISO end. Default: latest event. Use with --since to bound one cycle/session.")
    ap.add_argument("--symbol", default=None, help="Filter to one symbol, e.g. WLD/USDT:USDT")
    ap.add_argument("--htf-min-tf", default="1h",
                    help="Timeframe at/above which a structure counts as HTF (default 1h).")
    ap.add_argument("--top", type=int, default=10, help="Top-N symbols to list (default 10).")
    args = ap.parse_args()
    return run(args.since, args.symbol, args.htf_min_tf, args.top, until=args.until)


if __name__ == "__main__":
    raise SystemExit(main())
