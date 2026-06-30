"""CVD capture health — read-only (decisions/2026-06-30__cvd-experiment, Phase A).

FUNDAMENTALS-FIRST: before trusting CVD as a signal, verify the CAPTURE is real — coverage, gap rate,
per-symbol distributions, and (live) that the poll->ingest->snapshot path actually produces non-zero
direction-signed features. Run:
    python -m backend.diagnostics.cvd_capture_health            # journal + live sanity
    python -m backend.diagnostics.cvd_capture_health --live-only
"""
from __future__ import annotations

import argparse
import json
import statistics as st
from collections import defaultdict


def journal_health(path: str = "backend/cache/trade_journal.jsonl") -> None:
    try:
        rows = [json.loads(l) for l in open(path)]
    except FileNotFoundError:
        print(f"(no journal at {path})")
        return
    with_field = [r for r in rows if "cvd_coverage_at_entry" in r]
    print("=== JOURNAL CVD CAPTURE ===")
    print(f"  rows total: {len(rows)} | rows carrying CVD fields: {len(with_field)}")
    if not with_field:
        print("  (no trades journaled on CVD-capture code yet — run a session, then re-check)")
        return
    cov = [r.get("cvd_coverage_at_entry", 0.0) for r in with_field]
    clean = [r for r in with_field if r.get("cvd_coverage_at_entry", 0.0) >= 0.9]
    nonzero = [r for r in with_field if abs(r.get("cvd_slope_1h_at_entry", 0.0)) > 1e-9]
    print(f"  coverage>=0.9 (clean): {len(clean)}/{len(with_field)} | nonzero slope: {len(nonzero)}/{len(with_field)}")
    print(f"  coverage: min {min(cov):.2f} med {st.median(cov):.2f} max {max(cov):.2f}")
    print(f"  {'symbol':10}{'n':>4}{'med_slope':>10}{'med_z':>8}{'med_cov':>8}{'med_OI':>14}")
    bys = defaultdict(list)
    for r in with_field:
        bys[r.get("symbol", "?")].append(r)
    for s, rs in sorted(bys.items(), key=lambda x: -len(x[1]))[:15]:
        sl = st.median([r.get("cvd_slope_1h_at_entry", 0.0) for r in rs])
        z = st.median([r.get("cvd_z_at_entry", 0.0) for r in rs])
        c = st.median([r.get("cvd_coverage_at_entry", 0.0) for r in rs])
        oi = st.median([r.get("open_interest_at_entry", 0.0) for r in rs])
        print(f"  {s[:8]:10}{len(rs):>4}{sl:>10.3f}{z:>8.2f}{c:>8.2f}{oi:>14,.0f}")


def live_sanity(symbols=None) -> None:
    from backend.data.adapters.phemex import PhemexAdapter
    from backend.bot.cvd.cvd_tracker import CvdTracker
    from datetime import datetime, timezone
    import time
    symbols = symbols or ["BTC/USDT", "ETH/USDT", "ADA/USDT", "SOL/USDT"]
    a = PhemexAdapter(testnet=False, default_type="swap")
    t = CvdTracker()
    print("\n=== LIVE CAPTURE SANITY (2 polls, ~5s apart) ===")
    for _ in range(2):
        for s in symbols:
            tr = a.fetch_recent_trades(s + ":USDT", limit=200)
            t.ingest(s, tr)
        time.sleep(5)
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    print(f"  {'symbol':10}{'slope(L)':>10}{'slope(S)':>10}{'z':>7}{'cov':>6}{'n':>6}{'OI':>14}")
    for s in symbols:
        fl = t.snapshot_features(s, "LONG", now_ms)
        fs = t.snapshot_features(s, "SHORT", now_ms)
        oi = a.get_open_interest(s + ":USDT")
        print(f"  {s[:8]:10}{fl['cvd_slope_1h']:>10.3f}{fs['cvd_slope_1h']:>10.3f}{fl['cvd_z']:>7.2f}"
              f"{fl['cvd_coverage']:>6.2f}{fl['cvd_n_trades']:>6.0f}{(oi or 0):>14,.0f}")
    print("  (slope(L) should be the exact negation of slope(S) — direction-sign symmetry check)")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--live-only", action="store_true")
    args = p.parse_args()
    if not args.live_only:
        journal_health()
    live_sanity()


if __name__ == "__main__":
    main()
