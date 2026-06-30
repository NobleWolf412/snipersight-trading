"""Retroactive CVD edge test via Binance historical dumps (decisions/2026-06-30__cvd-experiment).

Phemex keeps no trade history, so CVD couldn't be tested retroactively — EXCEPT Binance publishes free
historical klines (with taker-buy volume) at data.binance.vision (reachable; the API is geo-blocked).
We compute Binance CVD at each of our journaled trades' entry times (a CROSS-VENUE PROXY — order flow on
the same asset is highly correlated across major venues) and run the SAME noise-floor + anti-overfit
test we planned for Phase C — in ~a day instead of a 2-4 week forward capture.

Honest caveats: (1) cross-venue proxy, not Phemex's own tape; (2) 15m-candle CVD, coarser than tick.
A PASS here is a strong lead to confirm forward on Phemex (Phase A is capturing live); a FAIL kills it
cheap. Direction-signed (flow agreeing with the trade is +). Run:
    python -m backend.diagnostics.cvd_historical_edge
"""
from __future__ import annotations

import csv
import io
import json
import math
import os
import statistics as st
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone

_CACHE = "backend/cache/binance_dumps"
_BASE = "https://data.binance.vision/data/futures/um/daily/klines/{sym}/15m/{sym}-15m-{date}.zip"
_HOUR_MS = 3600 * 1000
_15M_MS = 15 * 60 * 1000


def _binance_symbol(journal_sym: str) -> str:
    base = journal_sym.split(":")[0].split("/")[0]
    return f"{base}USDT"


def _download_day(sym: str, date: str):
    """Return [(open_ts, cvd, vol, close)] for one UTC day, cached. None if unavailable (404/missing)."""
    os.makedirs(_CACHE, exist_ok=True)
    cache = os.path.join(_CACHE, f"{sym}-{date}.json")
    if os.path.exists(cache):
        try:
            return json.load(open(cache))
        except Exception:
            pass
    url = _BASE.format(sym=sym, date=date)
    try:
        data = urllib.request.urlopen(url, timeout=30).read()
        z = zipfile.ZipFile(io.BytesIO(data))
        rows = list(csv.reader(io.TextIOWrapper(z.open(z.namelist()[0]))))
        if rows and not rows[0][0].replace(".", "").isdigit():
            rows = rows[1:]
        out = []
        for k in rows:
            ts = int(float(k[0])); vol = float(k[5]); tbb = float(k[9]); close = float(k[4])
            out.append([ts, 2 * tbb - vol, vol, close])  # cvd = 2*takerBuyBase - volume
        json.dump(out, open(cache, "w"))
        return out
    except Exception:
        json.dump(None, open(cache, "w"))  # cache the miss
        return None


def _features_at(series, entry_ts: int, direction: str):
    """Direction-signed CVD features at entry_ts from a symbol's sorted 15m candle series."""
    dir_sign = 1.0 if direction == "LONG" else -1.0
    win = [c for c in series if entry_ts - _HOUR_MS <= c[0] < entry_ts]          # last 1h
    if len(win) < 3:
        return None  # insufficient coverage
    net = sum(c[1] for c in win); tot = sum(c[2] for c in win)
    imbalance = (net / tot) if tot > 0 else 0.0
    price_ret = (win[-1][3] - win[0][3]) / win[0][3] if win[0][3] > 0 else 0.0
    cvd_dir = (net > 0) - (net < 0); px_dir = (price_ret > 0) - (price_ret < 0)
    divergence = float(cvd_dir) * dir_sign if (cvd_dir and px_dir and cvd_dir != px_dir) else 0.0
    # z vs a trailing ~1-day baseline of 1h-net-flow samples (rolling over the prior candles)
    base = [c for c in series if entry_ts - 24 * _HOUR_MS <= c[0] < entry_ts]
    nets = []
    for i in range(4, len(base)):
        nets.append(sum(base[j][1] for j in range(i - 4, i)))  # rolling 1h (4x15m) net flow
    z = 0.0
    if len(nets) >= 10:
        mu = st.mean(nets); sd = st.pstdev(nets)
        z = ((net - mu) / sd) if sd > 0 else 0.0
    return {"cvd_slope_1h": imbalance * dir_sign, "cvd_divergence": divergence, "cvd_z": z * dir_sign}


def _pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return 0.0
    mx = st.mean(xs); my = st.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return (num / den) if den else 0.0


def run():
    rows = [json.loads(l) for l in open("backend/cache/trade_journal.jsonl")]

    def R(r):
        q = r.get("quantity") or 0; e = r.get("entry_price") or 0; sl = r.get("stop_loss_level") or 0
        risk = q * abs(e - sl)
        return r.get("pnl", 0) / risk if risk > 0 else None

    trades = [r for r in rows if r.get("entry_time") and R(r) is not None and r.get("direction") in ("LONG", "SHORT")]
    print(f"journal trades usable: {len(trades)}")

    # gather (binance_symbol -> set of UTC dates) needed: entry day + prior 1 day (window + baseline)
    need = defaultdict(set)
    for r in trades:
        bs = _binance_symbol(r["symbol"])
        d = datetime.fromisoformat(r["entry_time"]).astimezone(timezone.utc)
        for off in range(0, 2):
            need[bs].add((d - timedelta(days=off)).strftime("%Y-%m-%d"))

    series = {}
    missing_syms = []
    print(f"downloading Binance 15m dumps for {len(need)} symbols (cached)...")
    for bs, dates in need.items():
        candles = []
        got_any = False
        for date in sorted(dates):
            day = _download_day(bs, date)
            if day:
                got_any = True
                candles.extend(day)
        if got_any:
            series[bs] = sorted(candles, key=lambda c: c[0])
        else:
            missing_syms.append(bs)
    if missing_syms:
        print(f"  no Binance futures data for: {missing_syms} (those trades excluded)")

    # compute features + outcome per trade
    data = []  # (R, slope, divergence, z, symbol, regime, entry_ts)
    for r in trades:
        bs = _binance_symbol(r["symbol"])
        s = series.get(bs)
        if not s:
            continue
        ets = int(datetime.fromisoformat(r["entry_time"]).timestamp() * 1000)
        f = _features_at(s, ets, r["direction"])
        if f is None:
            continue
        data.append((R(r), f["cvd_slope_1h"], f["cvd_divergence"], f["cvd_z"],
                     r["symbol"], r.get("regime_trend_at_entry") or r.get("regime") or "?", ets))
    n = len(data)
    print(f"matched Binance CVD for {n} trades\n")
    if n < 30:
        print("INSUFFICIENT matched trades for a verdict.")
        return

    Rs = [d[0] for d in data]
    feats = {"cvd_slope_1h": 1, "cvd_divergence": 2, "cvd_z": 3}
    floor = 1.96 / math.sqrt(n)
    # Bonferroni for N=3 two-sided: z ~ invnorm(1 - 0.05/(2*3)) ~ 2.39
    bonf = 2.394 / math.sqrt(n)
    print(f"=== RETROACTIVE CVD EDGE (n={n}) ===")
    print(f"  noise floor (raw) +-{floor:.3f} | Bonferroni floor (N=3) +-{bonf:.3f}\n")
    print(f"  {'feature':16}{'r_all':>8}{'r_train':>9}{'r_test':>8}{'sign_ok':>8}{'verdict':>10}")
    surviving = []
    # chronological 60/40 split
    order = sorted(range(n), key=lambda i: data[i][6])
    cut = int(n * 0.6)
    tr_idx, te_idx = set(order[:cut]), set(order[cut:])
    for fname, fi in feats.items():
        xs = [d[fi] for d in data]
        r_all = _pearson(xs, Rs)
        xtr = [data[i][fi] for i in order[:cut]]; ytr = [data[i][0] for i in order[:cut]]
        xte = [data[i][fi] for i in order[cut:]]; yte = [data[i][0] for i in order[cut:]]
        r_tr = _pearson(xtr, ytr); r_te = _pearson(xte, yte)
        sign_ok = (r_tr * r_te) > 0 and abs(r_tr) > 1e-9
        passes = abs(r_te) >= bonf and sign_ok
        verdict = "SURVIVE" if passes else ("noise" if abs(r_all) < floor else "fragile")
        if passes:
            surviving.append(fname)
        print(f"  {fname:16}{r_all:>8.3f}{r_tr:>9.3f}{r_te:>8.3f}{str(sign_ok):>8}{verdict:>10}")

    # per-symbol leave-one-out + per-regime sign, only for survivors
    print()
    for fname in (surviving or []):
        fi = feats[fname]
        syms = sorted({d[4] for d in data})
        loo_ok = True
        for drop in syms:
            sub = [d for d in data if d[4] != drop]
            if abs(_pearson([d[fi] for d in sub], [d[0] for d in sub])) < bonf:
                loo_ok = False
                break
        byreg = defaultdict(list)
        for d in data:
            byreg[d[5]].append(d)
        regs = sorted(byreg, key=lambda k: -len(byreg[k]))[:2]
        reg_signs = [(_pearson([d[fi] for d in byreg[g]], [d[0] for d in byreg[g]])) for g in regs if len(byreg[g]) >= 10]
        reg_ok = len(reg_signs) >= 2 and (reg_signs[0] * reg_signs[1] > 0)
        print(f"  [{fname}] leave-one-symbol-out clears Bonferroni: {loo_ok} | sign holds across top-2 regimes: {reg_ok}")

    print("\n=== VERDICT ===")
    if not surviving:
        print("  NOISE — no CVD feature clears the Bonferroni floor on the held-out fold with consistent sign.")
        print("  Kill criterion met: do NOT build a CVD gate. (Same outcome as the prior 4 leads, found in a day.)")
    else:
        print(f"  CANDIDATE SURVIVORS: {surviving} — clear held-out Bonferroni + sign. CHECK the leave-one-out")
        print("  + regime lines above; if those hold, this is the first real lead -> confirm FORWARD on Phemus")
        print("  (Phase A capture) before any gate. If LOO/regime fail, it's a one-symbol/one-regime artifact.")


if __name__ == "__main__":
    run()
