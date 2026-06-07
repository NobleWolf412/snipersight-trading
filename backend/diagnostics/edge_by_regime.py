"""
Edge-by-regime (and regime x trade_type) — READ-ONLY, with a built-in confound guard.

"Does the bot handle certain regimes better?" The journal already carries `regime` +
`trade_type` per trade, so this slices expectancy/win by them. The CATCH this tool exists to
prevent: regime is often entangled with the wide-stop-era clamp date (2026-05-31). Recent market
flipped up_compressed (pre-clamp, wide-stop era) -> down (post-clamp, clean), so a naive
edge-by-regime reads "up_compressed bleeds / down is fine" when the real cause is the (fixed)
wide stops, NOT the regime. This is the 6th confound of the session.

So EVERY regime row here shows its pre/post-clamp split, and a regime that is entirely pre-clamp
is tagged CONFOUNDED (wide-stop-era artifact, not a regime effect). The CLEAN section reports only
post-clamp trades. A regime comparison is only trustworthy ACROSS regimes that BOTH have clean
(post-clamp) data — which today we do NOT have (post-clamp is single-regime down_*). The tool
makes that limitation impossible to miss.

Usage:  python -m backend.diagnostics.edge_by_regime
        python -m backend.diagnostics.edge_by_regime --since 2026-05-31   # clean window only
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
JOURNAL = REPO / "backend" / "cache" / "trade_journal.jsonl"
CLAMP_DATE = "2026-05-31"  # reachability-clamp ship date = the wide-stop-era confound boundary


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _stat(rows):
    n = len(rows)
    if not n:
        return None
    w = sum(1 for r in rows if (_f(r.get("pnl")) or 0) > 0)
    tot = sum(_f(r.get("pnl")) or 0 for r in rows)
    return {"n": n, "win": 100 * w / n, "exp": tot / n, "tot": tot}


def _fmt(s):
    return f"n={s['n']:3} win={s['win']:3.0f}% exp={s['exp']:+6.2f} tot={s['tot']:+8.1f}" if s else "n=0"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    since = None
    if "--since" in sys.argv:
        since = sys.argv[sys.argv.index("--since") + 1]

    if not JOURNAL.exists():
        print("No trade_journal.jsonl.")
        return 1
    rows = []
    for line in JOURNAL.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            t = json.loads(line)
        except json.JSONDecodeError:
            continue
        if since and (t.get("entry_time", "") or "") < since:
            continue
        rows.append(t)
    if not rows:
        print("No trades in window.")
        return 1

    def is_post(t):
        return (t.get("entry_time", "") or "") >= CLAMP_DATE

    by_reg = defaultdict(list)
    for t in rows:
        by_reg[t.get("regime") or "?"].append(t)

    print("=== EDGE BY REGIME (confound-guarded) ===")
    print(f"window: {'ALL' if not since else '>= ' + since}  | clamp boundary: {CLAMP_DATE}")
    print(f"\n  {'regime':16}{'overall':32}{'pre/post':>10}  confound?")
    confounded, clean_regimes = [], []
    for reg in sorted(by_reg, key=lambda r: -len(by_reg[r])):
        ts = by_reg[reg]
        pre = sum(1 for t in ts if not is_post(t))
        post = len(ts) - pre
        flag = ""
        if post == 0:
            flag = "CONFOUNDED (all pre-clamp = wide-stop era, NOT a regime effect)"
            confounded.append(reg)
        elif pre == 0:
            flag = "clean (all post-clamp)"
            clean_regimes.append(reg)
        else:
            flag = "MIXED (split below)"
            clean_regimes.append(reg)
        print(f"  {reg:16}{_fmt(_stat(ts)):32}{f'{pre}/{post}':>10}  {flag}")

    # CLEAN view: post-clamp only, by regime x trade_type
    post_rows = [t for t in rows if is_post(t)]
    print(f"\n--- CLEAN (post-clamp) regime x trade_type — the only trustworthy slice ---")
    if not post_rows:
        print("  (no post-clamp trades in window)")
    else:
        by_rt = defaultdict(list)
        for t in post_rows:
            by_rt[(t.get("regime") or "?", t.get("trade_type") or "?")].append(t)
        for k in sorted(by_rt, key=lambda k: -len(by_rt[k])):
            print(f"  {k[0]:16} {k[1]:9} {_fmt(_stat(by_rt[k]))}")
        cleanset = sorted({t.get('regime') or '?' for t in post_rows})
        print(f"\n  post-clamp regimes present: {cleanset}")

    print("\n=== READ ===")
    if confounded:
        print(f"  CONFOUNDED regimes (ignore for regime inference — they are the wide-stop era): {confounded}")
    cleanset = sorted({t.get('regime') or '?' for t in post_rows}) if post_rows else []
    if len(cleanset) <= 1:
        print(f"  Post-clamp data spans only {len(cleanset)} regime(s): {cleanset}. A cross-regime")
        print("  comparison is IMPOSSIBLE until clean data exists in >=2 regimes. Run clean sessions")
        print("  when the market is in a non-down regime, then re-run this. Do NOT read the overall")
        print("  table as a regime effect — it is dominated by the era split.")
    else:
        print(f"  Post-clamp spans regimes {cleanset} — compare their clean exp/win ABOVE. Still")
        print("  treat small-n cells as noise (bootstrap via edge_significance before acting).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
