"""
Direction-Selection Audit — verifies the quality-aware override changes direction
on symbols where DIRECTION-SHORT-CIRCUIT was diagnosed (INJ/SOL etc.).

Per CLAUDE.md §18 bug-fix discipline: every fix must land with a diagnostic
that exercises the reproduction case AND proves the bug is gone. This script
is paired with the orchestrator override change shipped 2026-05-27.

What it does:
  1. For each requested symbol (default: today's known-failed set), fetch live
     SMC structure from PhemexAdapter.
  2. Run the OLD count-based selector (_derive_pre_direction) → record direction.
  3. Run the NEW quality-aware override (_apply_quality_override on the SAME
     structure) → record direction.
  4. Report flips: symbols where OLD picks one side, NEW picks the other.
  5. Print the aggregate-quality scores per direction for visibility.

Validation assertion: INJ/USDT MUST flip from LONG→SHORT under the new logic
in current market conditions. This is the calibration fixture from session
2f35590b run_id 1fde069e (INJ #27 lost -$124). If the assertion fails, either
the fix isn't deployed or the structural pattern has changed since calibration
(re-run on a different sample).

Usage:
    python -X utf8 -m backend.diagnostics.direction_selection_audit
    python -X utf8 -m backend.diagnostics.direction_selection_audit INJ/USDT SOL/USDT
    python -X utf8 -m backend.diagnostics.direction_selection_audit --strict   # fails non-zero if INJ doesn't flip
"""

from __future__ import annotations

import sys
from typing import List, Tuple

import pandas as pd

# Default audit set — symbols where DIRECTION-SHORT-CIRCUIT was diagnosed
DEFAULT_SYMBOLS = (
    "INJ/USDT",   # primary regression fixture — must flip LONG→SHORT
    "SOL/USDT",   # diagnosed 2026-05-26 confluence-trace
    "OP/USDT",    # 0/3 intraday LONG losses today
    "ARB/USDT",   # bidirectional pattern
    "APT/USDT",   # session 2f35590b consistent LONG-only target
    "BTC/USDT",   # control — should defer (count_dir = quality_dir)
)


def _fetch_smc_snapshot(symbol: str):
    """Pull live OHLCV from Phemex + run SMC detector. Returns SMCSnapshot."""
    from backend.data.adapters.phemex import PhemexAdapter
    from backend.services.smc_service import SMCDetectionService
    from backend.shared.models.data import MultiTimeframeData

    adapter = PhemexAdapter()
    tf_data = {}
    for tf in ("1d", "4h", "1h", "15m", "5m"):
        df = adapter.fetch_ohlcv(symbol, tf, limit=400)
        if df is not None and not df.empty:
            tf_data[tf] = df

    if not tf_data:
        return None, 0.0

    current_price = float(tf_data["5m"]["close"].iloc[-1])
    mtf = MultiTimeframeData(symbol=symbol, timeframes=tf_data)
    smc = SMCDetectionService(mode="stealth")
    snapshot = smc.detect(mtf, current_price)
    return snapshot, current_price


def _audit_one(symbol: str) -> Tuple[str, dict]:
    """Return (status, info_dict) for one symbol.

    status ∈ {"flipped", "no_change", "no_data", "error"}."""
    from backend.engine.orchestrator import Orchestrator
    from types import SimpleNamespace

    try:
        snap, price = _fetch_smc_snapshot(symbol)
    except Exception as exc:
        return "error", {"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"}

    if snap is None:
        return "no_data", {"symbol": symbol}

    # OLD selector — count-based tally only
    regime_stub = SimpleNamespace(trend="up", score=50.0)
    old_dir, old_tb = Orchestrator._derive_pre_direction(
        snap.order_blocks, snap.structural_breaks, regime_stub
    )

    # NEW — quality-aware override on top
    new_dir, new_tb, override_meta = Orchestrator._apply_quality_override(
        snap, old_dir, old_tb
    )

    # Compute aggregate quality per direction for visibility
    q_long = Orchestrator._aggregate_direction_quality(snap, "LONG")
    q_short = Orchestrator._aggregate_direction_quality(snap, "SHORT")

    info = {
        "symbol": symbol,
        "price": price,
        "ob_total": len(snap.order_blocks),
        "ob_bull": sum(1 for o in snap.order_blocks if getattr(o, "direction", None) == "bullish"),
        "ob_bear": sum(1 for o in snap.order_blocks if getattr(o, "direction", None) == "bearish"),
        "bos_bull": sum(1 for b in snap.structural_breaks if getattr(b, "direction", None) == "bullish"),
        "bos_bear": sum(1 for b in snap.structural_breaks if getattr(b, "direction", None) == "bearish"),
        "old_direction": old_dir,
        "old_tie_break": old_tb,
        "new_direction": new_dir,
        "new_tie_break": new_tb,
        "quality_long": round(q_long, 2),
        "quality_short": round(q_short, 2),
        "delta": round(q_short - q_long, 2),
        "override_meta": override_meta,
    }

    status = "flipped" if old_dir != new_dir else "no_change"
    return status, info


def main(argv: List[str]) -> int:
    strict_mode = "--strict" in argv
    args = [a for a in argv[1:] if not a.startswith("--")]
    symbols = tuple(args) if args else DEFAULT_SYMBOLS

    print("=" * 80)
    print("  DIRECTION-SELECTION AUDIT — quality-aware override vs count-based")
    print("=" * 80)
    print(f"  Audit set: {len(symbols)} symbols")
    print(f"  Strict mode: {strict_mode}  (fails non-zero if INJ doesn't flip)")
    print()

    flips = []
    unchanged = []
    failed = []
    inj_info = None

    for sym in symbols:
        print(f"  Auditing {sym}...")
        status, info = _audit_one(sym)
        if status == "flipped":
            flips.append(info)
        elif status == "no_change":
            unchanged.append(info)
        else:
            failed.append(info)
        if sym == "INJ/USDT":
            inj_info = info

    # ── Summary table ────────────────────────────────────────────────
    print()
    print("=" * 80)
    print("  RESULTS")
    print("=" * 80)
    print(
        f"  {'symbol':14s} {'OB(B/b)':9s} {'BOS(B/b)':10s} {'qL':>7s} {'qS':>7s} {'Δ':>7s}  "
        f"{'OLD':>10s} -> {'NEW':<10s}  {'verdict':10s}"
    )
    print("  " + "─" * 96)

    for info in flips + unchanged + failed:
        if info.get("error"):
            print(f"  {info['symbol']:14s} ERROR: {info['error']}")
            continue
        ob = f"{info['ob_bull']}/{info['ob_bear']}"
        bs = f"{info['bos_bull']}/{info['bos_bear']}"
        verdict = "FLIPPED" if info["old_direction"] != info["new_direction"] else "no_change"
        print(
            f"  {info['symbol']:14s} {ob:9s} {bs:10s} "
            f"{info['quality_long']:>7.1f} {info['quality_short']:>7.1f} {info['delta']:>+7.1f}  "
            f"{info['old_direction']:>10s} -> {info['new_direction']:<10s}  {verdict:10s}"
        )

    # ── Aggregate ───────────────────────────────────────────────────
    print()
    print(f"  Flipped: {len(flips)}   No-change: {len(unchanged)}   Failed: {len(failed)}")

    if flips:
        print()
        print("  FLIPPED detail:")
        for info in flips:
            meta = info["override_meta"]
            print(
                f"    {info['symbol']}: {meta['from']} -> {meta['to']} "
                f"(Δ={meta['delta']:+.1f} > threshold {meta['threshold']})"
            )

    # ── INJ regression validation ───────────────────────────────────
    print()
    print("  REGRESSION VALIDATION")
    print("  " + "─" * 78)

    exit_code = 0

    if inj_info is None or inj_info.get("error"):
        msg = "INJ/USDT not in audit set or fetch failed — cannot validate regression"
        print(f"  WARN: {msg}")
        if strict_mode:
            exit_code = 2
    else:
        inj_flipped = inj_info["old_direction"] != inj_info["new_direction"]
        old_was_long = inj_info["old_direction"] == "LONG"
        new_is_short = inj_info["new_direction"] == "SHORT"

        if inj_flipped and old_was_long and new_is_short:
            print(
                f"  PASS: INJ/USDT correctly flipped LONG -> SHORT "
                f"(Δ={inj_info['delta']:+.1f}, calibration fixture)"
            )
        elif not inj_flipped:
            msg = (
                f"WARN: INJ/USDT did NOT flip "
                f"(old={inj_info['old_direction']}, new={inj_info['new_direction']}). "
                f"Either fix not deployed OR structure changed since 2026-05-27 calibration."
            )
            print(f"  {msg}")
            if strict_mode:
                exit_code = 1
        else:
            print(
                f"  WARN: INJ/USDT flipped but not LONG->SHORT "
                f"(was {inj_info['old_direction']} -> {inj_info['new_direction']})"
            )

    # ── Recommended follow-up ───────────────────────────────────────
    print()
    if flips:
        print(
            f"  Next step: re-run on a fresh session after armed and confirm the "
            f"flipped symbols ({', '.join(i['symbol'] for i in flips)}) now produce "
            f"SHORT signals where they previously produced LONG."
        )

    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
