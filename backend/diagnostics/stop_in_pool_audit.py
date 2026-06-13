"""
stop_in_pool_audit.py — READ-ONLY diagnostic (Phase 1, measure-first).

Question (operator thesis, UNCONFIRMED): are stops landing inside / too close to
SMC liquidity pools (PWL/PWH/PDH/PDL prior-week/day, EQL/EQH equal highs/lows) and
getting systematically swept — despite the existing 0.3-ATR liquidity buffer in
risk_engine._buffer_stop_from_liquidity?

This script measures what the trade journal can actually support and is LOUD about
what it cannot. It changes NO logic. See the companion decisions-log entry:
  backend/diagnostics/decisions/2026-06-13__stop-in-liquidity-pool-baseline.md

What is measurable from stored data (journal only):
  - Whether the liquidity buffer FIRED (stop_loss_rationale embeds the pool level).
  - Cohort sweep rates: buffered vs non-buffered (exit_reason == stop_loss).
  - Post-buffer geometry: how close the FINAL stop still sits to the logged pool.
  - Bull/bear symmetry of buffer engagement.

What is NOT measurable (flagged, not silently skipped):
  - Pools the buffer MISSED — the full PWL/PWH/PDH/PDL/EQH/EQL set at entry is
    persisted NOWHERE (not in trades.jsonl, paper signals.jsonl, nor telemetry
    signal_generated). So "stop in an *undetected* pool" cannot be counted.
  - "Swept then reversed the intended way" — needs post-exit candles; the journal's
    max_favorable/max_adverse are DURING-trade excursions only, and no durable OHLCV
    cache exists to replay post-stop price.

Secondary (static) finding this script also PROVES at runtime:
  - The buffer's static PWL/PWH/PDH/PDL branch is DEAD in production: it does
    getattr(key_levels, "pwl") on a dict (SMCSnapshot.key_levels is .to_dict()),
    which returns None, and the isinstance(lvl,(int,float)) guard also rejects a
    KeyLevel object. Only the EQH/EQL multi_tf scan can ever fire the buffer.

Usage:  python -m backend.diagnostics.stop_in_pool_audit
"""

from __future__ import annotations

import glob
import json
import re
import statistics
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────
CUTOFF = datetime(2026, 6, 1, tzinfo=timezone.utc)  # post-clamp era (avoid wide-stop confound)
BUFFER_ATR = 0.3                                     # risk_engine buffer constant
TRADES_GLOB = "logs/paper_trading/session_*/trades.jsonl"
SWEEP_REASON = "stop_loss"                            # session_stopped = open at session end, NOT a sweep
_POOL_RE = re.compile(r"liquidity pool @ ([0-9.]+)")


# ── Load ──────────────────────────────────────────────────────────────────────
def _load_trades() -> list[dict]:
    out: list[dict] = []
    for f in glob.glob(TRADES_GLOB):
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    t = json.loads(line)
                except json.JSONDecodeError:
                    continue
                et = t.get("entry_time")
                if not et:
                    continue
                try:
                    dt = datetime.fromisoformat(et)
                except ValueError:
                    continue
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt < CUTOFF:
                    continue
                out.append(t)
    return out


def _atr(t: dict) -> Optional[float]:
    """Reconstruct ATR from journal: ATR = |entry - stop| / stop_distance_atr."""
    entry = t.get("entry_price") or 0.0
    stop = t.get("stop_loss_level") or 0.0
    sda = t.get("stop_distance_atr") or 0.0
    if entry and stop and sda > 0:
        return abs(entry - stop) / sda
    return None


def _pool_from_rationale(t: dict) -> Optional[float]:
    m = _POOL_RE.search(t.get("stop_loss_rationale") or "")
    return float(m.group(1)) if m else None


# ── Cohort metrics ────────────────────────────────────────────────────────────
def _cohort_stats(trades: list[dict]) -> dict:
    n = len(trades)
    er = Counter(t.get("exit_reason") for t in trades)
    swept = er.get(SWEEP_REASON, 0)
    dirs = Counter(t.get("direction") for t in trades)
    stopped = [t for t in trades if t.get("exit_reason") == SWEEP_REASON]
    mfe = [t.get("max_favorable", 0.0) for t in stopped]
    mae = [t.get("max_adverse", 0.0) for t in stopped]
    return {
        "n": n,
        "swept": swept,
        "sweep_rate": (100 * swept / n) if n else 0.0,
        "exit_reasons": dict(er),
        "dir": dict(dirs),
        "stopped_mfe_median": statistics.median(mfe) if mfe else None,
        "stopped_mae_median": statistics.median(mae) if mae else None,
    }


# ── Buffer reachability probe (runtime proof the static branch is dead) ────────
def _static_branch_reachability() -> dict:
    """
    Call the real buffer with a production-shaped key_levels dict whose PWL sits
    0.1 ATR from the stop (well inside the 0.3-ATR window). If the static branch
    were live, the stop would move. We pass multi_tf_data=None to isolate the
    static branch from the EQH/EQL scan.
    """
    try:
        from backend.strategy.planner.risk_engine import _buffer_stop_from_liquidity
        from backend.analysis.key_levels import KeyLevels, KeyLevel
    except Exception as e:  # pragma: no cover - import guard
        return {"ok": False, "error": f"import failed: {e}"}

    atr = 1.0
    entry_ref = 110.0
    stop = 100.0           # LONG stop below entry
    pool_price = 99.9      # 0.1 ATR below the stop -> inside 0.3-ATR window
    kl = KeyLevels(
        symbol="X",
        pwl=KeyLevel(price=pool_price, level_type="PWL",
                     timestamp=datetime(2026, 6, 1, tzinfo=timezone.utc), timeframe="1d"),
    )

    # (a) production path: SMCSnapshot.key_levels is a dict (.to_dict())
    dict_stop, dict_rat = _buffer_stop_from_liquidity(
        stop_level=stop, entry_ref=entry_ref, is_bullish=True, atr=atr,
        multi_tf_data=None, key_levels=kl.to_dict(),
    )
    # (b) hypothetical: even a KeyLevels dataclass fails (pwl is a KeyLevel obj)
    obj_stop, obj_rat = _buffer_stop_from_liquidity(
        stop_level=stop, entry_ref=entry_ref, is_bullish=True, atr=atr,
        multi_tf_data=None, key_levels=kl,
    )
    return {
        "ok": True,
        "pool_inside_window_at": pool_price,
        "dict_path_moved_stop": dict_stop != stop,
        "obj_path_moved_stop": obj_stop != stop,
        "dict_rationale": dict_rat,
        "obj_rationale": obj_rat,
    }


# ── Report ────────────────────────────────────────────────────────────────────
def main() -> None:
    trades = _load_trades()
    total = len(trades)

    buffered = [t for t in trades if "liquidity pool" in (t.get("stop_loss_rationale") or "").lower()]
    non_buffered = [t for t in trades if t not in buffered]

    # Mass conservation (runtime assert in the body, per §16 Rubric 3) ──────────
    assert len(buffered) + len(non_buffered) == total, (
        f"MASS LEAK: buffered({len(buffered)}) + non({len(non_buffered)}) != total({total})"
    )
    er_all = Counter(t.get("exit_reason") for t in trades)
    assert sum(er_all.values()) == total, "MASS LEAK: exit_reason counts != total"

    buf = _cohort_stats(buffered)
    non = _cohort_stats(non_buffered)
    probe = _static_branch_reachability()

    # ── SUMMARY (short first) ──────────────────────────────────────────────────
    print("=" * 78)
    print("STOP-IN-LIQUIDITY-POOL AUDIT -- Phase 1 baseline (READ-ONLY)")
    print(f"cutoff entry_time >= {CUTOFF.date()} | closed trades: {total}")
    print("=" * 78)
    print(f"\nBuffer fired on {len(buffered)}/{total} trades "
          f"({100*len(buffered)/total:.1f}%)  --  n={len(buffered)} is BELOW the n>=30 "
          f"power floor; sweep-rate comparison below is INDICATIVE, not conclusive.")
    print(f"  buffered direction mix : {buf['dir']}")
    print(f"  all-trade direction mix: {Counter(t.get('direction') for t in trades)}")

    # ── COHORT TABLE (structured detail) ───────────────────────────────────────
    print("\n--- COHORT: sweep (stop_loss) rate ---")
    hdr = f"{'cohort':<14}{'n':>4}{'swept':>7}{'sweep%':>9}   exit_reasons"
    print(hdr)
    print(f"{'BUFFERED':<14}{buf['n']:>4}{buf['swept']:>7}{buf['sweep_rate']:>8.1f}%   {buf['exit_reasons']}")
    print(f"{'NON-BUFFERED':<14}{non['n']:>4}{non['swept']:>7}{non['sweep_rate']:>8.1f}%   {non['exit_reasons']}")
    print("\n--- stopped-trade excursion (DURING-trade proxy; not post-stop) ---")
    print(f"  BUFFERED stopped  : MFE_med={buf['stopped_mfe_median']}  MAE_med={buf['stopped_mae_median']}")
    print(f"  NON-BUF  stopped  : MFE_med={non['stopped_mfe_median']}  MAE_med={non['stopped_mae_median']}")

    # ── BUFFER REACHABILITY (the live finding) ─────────────────────────────────
    print("\n--- BUFFER STATIC-BRANCH REACHABILITY PROBE ---")
    if not probe.get("ok"):
        print(f"  PROBE SKIPPED: {probe.get('error')}")
    else:
        print(f"  pool placed 0.1 ATR inside the 0.3-ATR window @ {probe['pool_inside_window_at']}")
        print(f"  production dict path moved the stop? {probe['dict_path_moved_stop']}  "
              f"(rationale={probe['dict_rationale']!r})")
        print(f"  KeyLevels-obj  path moved the stop? {probe['obj_path_moved_stop']}  "
              f"(rationale={probe['obj_rationale']!r})")
        if not probe["dict_path_moved_stop"] and not probe["obj_path_moved_stop"]:
            print("  >>> CONFIRMED DEAD: static PWL/PWH/PDH/PDL branch never buffers in "
                  "production. Only the EQH/EQL multi_tf scan can fire the buffer.")
        else:
            print("  >>> static branch now LIVE — the dead-branch defect appears FIXED; "
                  "re-baseline this diagnostic.")

    # ── RAW (last): per-buffered-trade geometry ────────────────────────────────
    print("\n--- RAW: buffered trades, final-stop vs logged pool (ATR units) ---")
    for t in buffered:
        atr = _atr(t)
        pool = _pool_from_rationale(t)
        stop = t.get("stop_loss_level")
        dist_atr = (abs(stop - pool) / atr) if (atr and pool and stop) else None
        dstr = f"{dist_atr:.2f}" if dist_atr is not None else "n/a"
        print(f"  {t.get('symbol'):<14} {t.get('direction'):<5} exit={t.get('exit_reason'):<14} "
              f"stop={stop} pool={pool} dist={dstr}ATR")

    # ── LIMITATIONS (loud) ─────────────────────────────────────────────────────
    print("\n--- LIMITATIONS (data not stored; thesis NOT fully testable here) ---")
    print("  1. Full pool set at entry is persisted nowhere -> cannot count stops sitting")
    print("     in pools the buffer never detected (incl. the dead PWL/PDH branch).")
    print("  2. Post-stop reversal is unmeasurable -> no durable OHLCV cache; MFE/MAE are")
    print("     during-trade only. 'Swept then reversed' needs candle replay.")
    print("  3. n(buffered)=%d << 30 -> no statistically valid sweep-rate verdict." % len(buffered))
    print("  UNBLOCK: persist key_levels + nearest-pool distance into the journal at entry")
    print("  (read-additive instrumentation, owned by the journal thread), then re-run after")
    print("  >=30 setups across >=2 regimes. See the decisions entry.")


if __name__ == "__main__":
    main()
