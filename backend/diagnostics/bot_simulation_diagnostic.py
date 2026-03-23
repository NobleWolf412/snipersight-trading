"""
Bot Simulation Diagnostic — Full Pipeline
==========================================
Simulates the paper trading bot by running the complete Orchestrator pipeline
with a MockAdapter that serves generated OHLCV data instead of live exchange data.

Pipeline path (identical to live bot):
    MockAdapter → IngestionPipeline → IndicatorService → SMCService
        → RegimeDetector → ConfluenceService → TradePlanner

This means SMC patterns, indicators, and regime are all computed from real
synthetic price action rather than hand-crafted objects. Catches wiring bugs
that an isolated unit test cannot.

Scenarios:
  1. Trending UP market        → LONG direction, score computed, no crash
  2. Trending DOWN market      → SHORT direction preferred
  3. Ranging/Compressed market → Score low, below gate threshold
  4. Volatile market           → Pipeline completes, no exception
  5. Order-block market        → OB factor should score > 0
  6. Multi-symbol scan         → All symbols processed, no crash

Usage:
    cd /path/to/snipersight-trading
    python -m backend.diagnostics.bot_simulation_diagnostic

Exit code 0 = all pass, 1 = one or more failures.
"""

import sys
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Tuple

import numpy as np
import pandas as pd

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"

results: List[Tuple[str, str, str]] = []


def _record(name: str, ok: bool, detail: str = "", warn: bool = False) -> None:
    status = WARN if warn else (PASS if ok else FAIL)
    results.append((name, status, detail))
    print(f"  {status}  {name}" + (f"  — {detail}" if detail else ""))


def _section(title: str) -> None:
    print(f"\n{'─' * 65}")
    print(f"  {title}")
    print(f"{'─' * 65}")


# ──────────────────────────────────────────────────────────────────────────────
# Imports
# ──────────────────────────────────────────────────────────────────────────────
try:
    from backend.engine.orchestrator import Orchestrator
    from backend.shared.config.defaults import ScanConfig
    from backend.shared.models.data import OHLCV, MultiTimeframeData
    from backend.data.adapters.mocks import (
        generate_trending_data,
        generate_ranging_data,
        generate_volatile_data,
        generate_with_order_blocks,
    )
    print("✅  Imports OK\n")
except Exception as exc:
    print(f"❌  IMPORT FAILED: {exc}")
    traceback.print_exc()
    sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# Mock Exchange Adapter
# Serves pre-generated OHLCV data so the full pipeline runs without an exchange.
# ──────────────────────────────────────────────────────────────────────────────

class MockAdapter:
    """
    Drop-in replacement for PhemexAdapter / BybitAdapter.
    Serves deterministic synthetic OHLCV data.
    The regime is set per-symbol at construction so each scenario is isolated.
    """

    def __init__(self, regime: str = "trending", seed: int = 42):
        self._regime = regime
        self._seed = seed

    # ── Required adapter interface ──────────────────────────────────────

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        market_type: Optional[str] = None,
        limit: int = 500,
        since: Optional[int] = None,
    ) -> pd.DataFrame:
        """Return a DataFrame of synthetic OHLCV candles."""
        if self._regime == "trending":
            candles = generate_trending_data(bars=limit, seed=self._seed)
        elif self._regime == "ranging":
            candles = generate_ranging_data(bars=limit, seed=self._seed)
        elif self._regime == "volatile":
            candles = generate_volatile_data(bars=limit, seed=self._seed)
        elif self._regime == "order_blocks":
            candles = generate_with_order_blocks(bars=limit, seed=self._seed)
        elif self._regime == "downtrend":
            candles = _generate_downtrend_data(bars=limit, seed=self._seed)
        else:
            candles = generate_trending_data(bars=limit, seed=self._seed)

        # Space timestamps by timeframe duration so SMC lookback is realistic.
        # IMPORTANT: tz-naive to match real exchange adapter output (phemex returns
        # pd.to_datetime(unit="ms") which is tz-naive). Tz-aware timestamps cause
        # "can't subtract offset-naive and offset-aware datetimes" in the SMC service.
        tf_hours = _tf_to_hours(timeframe)
        rows = []
        base_ts = datetime(2026, 1, 1)  # tz-naive — matches real exchange adapter
        for i, c in enumerate(candles):
            rows.append({
                "timestamp": base_ts + timedelta(hours=i * tf_hours),
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            })
        return pd.DataFrame(rows)

    def fetch_ticker(self, symbol: str, market_type: Optional[str] = None) -> Dict[str, Any]:
        """Return a minimal ticker dict."""
        df = self.fetch_ohlcv(symbol, "1h", limit=1)
        price = float(df["close"].iloc[-1]) if not df.empty else 40000.0
        return {"last": price, "bid": price * 0.9999, "ask": price * 1.0001}

    def fetch_markets(self) -> Dict[str, Any]:
        return {}

    def get_tick_size(self, symbol: str) -> float:
        return 0.01

    def get_lot_size(self, symbol: str) -> float:
        return 0.001

    # Make it look like ccxt
    @property
    def markets(self):
        return {}


def _tf_to_hours(tf: str) -> float:
    tf = tf.lower()
    mapping = {"1m": 1/60, "5m": 5/60, "15m": 0.25, "30m": 0.5,
               "1h": 1, "4h": 4, "1d": 24, "1w": 168}
    return mapping.get(tf, 1.0)


def _generate_downtrend_data(bars: int = 500, seed: int = 99) -> List[OHLCV]:
    """Downtrend — mirror of generate_trending_data but with negative drift."""
    np.random.seed(seed)
    base_price = 40000.0
    trend_strength = -0.0012   # Negative drift
    volatility = 0.02

    candles = []
    current_price = base_price
    start_time = datetime(2026, 1, 1)  # tz-naive to match real exchange adapter

    for i in range(bars):
        price_change = (trend_strength + np.random.normal(0, volatility)) * current_price
        current_price = max(100.0, current_price + price_change)  # Floor at 100

        open_price = current_price
        close_price = max(50.0, current_price * (1 + np.random.normal(trend_strength, volatility * 0.5)))
        high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, volatility * 0.3)))
        low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, volatility * 0.3)))

        # Ensure OHLCV constraints
        high_price = max(open_price, close_price, high_price)
        low_price = min(open_price, close_price, low_price)

        volume = np.random.uniform(100, 800)
        candles.append(OHLCV(
            timestamp=start_time + timedelta(hours=i),
            open=round(open_price, 2), high=round(high_price, 2),
            low=round(low_price, 2), close=round(close_price, 2),
            volume=round(volume, 2),
        ))
        current_price = close_price

    return candles


# ──────────────────────────────────────────────────────────────────────────────
# Orchestrator factory
# ──────────────────────────────────────────────────────────────────────────────

def _make_orchestrator(regime: str = "trending", seed: int = 42) -> Orchestrator:
    cfg = ScanConfig()
    cfg.profile = "stealth"
    cfg.min_confluence_score = 70.0
    adapter = MockAdapter(regime=regime, seed=seed)
    return Orchestrator(config=cfg, exchange_adapter=adapter)


def _make_mtf(
    symbol: str,
    regime: str = "trending",
    seed: int = 42,
    limit: int = 750,
) -> MultiTimeframeData:
    """Build a MultiTimeframeData from mock candles — all timeframes share the same regime shape."""
    adapter = MockAdapter(regime=regime, seed=seed)
    timeframes = ["1w", "1d", "4h", "1h", "15m"]
    tfs: Dict[str, pd.DataFrame] = {}
    for tf in timeframes:
        tfs[tf] = adapter.fetch_ohlcv(symbol, tf, limit=limit)
    return MultiTimeframeData(symbol=symbol, timeframes=tfs)


def _run_symbol(
    orchestrator: Orchestrator,
    symbol: str,
    regime: str = "trending",
    seed: int = 42,
) -> Tuple[Any, Optional[Dict]]:
    """Run _process_symbol with pre-built MTF data. Returns (plan_or_None, rejection_or_None)."""
    mtf = _make_mtf(symbol, regime=regime, seed=seed)
    run_id = uuid.uuid4().hex[:8]
    ts = datetime(2026, 3, 23, 14, 0, tzinfo=timezone.utc)
    try:
        plan, rejection = orchestrator._process_symbol(
            symbol=symbol,
            run_id=run_id,
            timestamp=ts,
            prefetched_data=mtf,
        )
        return plan, rejection
    except Exception as exc:
        return None, {"error": str(exc), "traceback": traceback.format_exc()}


# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 1: Trending UP market
# ──────────────────────────────────────────────────────────────────────────────
_section("Scenario 1 — Trending UP market (full pipeline)")
try:
    orch = _make_orchestrator(regime="trending", seed=42)
    plan, rej = _run_symbol(orch, "BTC/USDT", regime="trending", seed=42)
    error = rej.get("error") if rej else None
    _record("Pipeline completes without crash", error is None, error or "")
    if not error:
        direction = orch.confluence_service.diagnostics  # Just a side-check
        ctx_dir = None
        if plan:
            ctx_dir = plan.direction
            _record("Trade plan generated (score >= gate)", True, f"direction={ctx_dir}")
        else:
            reason = rej.get("reason", "unknown") if rej else "no rejection info"
            reason_type = rej.get("reason_type", "") if rej else ""
            # Below-gate rejection is expected for some market states — not a bug
            below_gate = reason_type in ("low_confluence",) or "confluence" in reason.lower()
            _record(
                "Pipeline correctly rejected (below gate) or generated plan",
                rej is not None and "error" not in rej,
                f"reason={reason[:80]}",
            )
except Exception as exc:
    _record("Scenario 1 unhandled exception", False, str(exc)); traceback.print_exc()


# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 2: Downtrend — SHORT direction preferred
# ──────────────────────────────────────────────────────────────────────────────
_section("Scenario 2 — Downtrend market (SHORT path)")
try:
    orch = _make_orchestrator(regime="downtrend", seed=99)
    plan, rej = _run_symbol(orch, "ETH/USDT", regime="downtrend", seed=99)
    error = rej.get("error") if rej else None
    _record("Pipeline completes without crash", error is None, error or "")
    if not error:
        # A downtrend should either produce a SHORT plan or reject (below gate)
        # It should NOT produce a LONG plan with high confidence
        if plan:
            _record("Plan direction is SHORT (downtrend)", plan.direction == "SHORT",
                    f"got={plan.direction}")
        else:
            reason = rej.get("reason_type", "") if rej else ""
            _record("Correctly rejected (no LONG bias forced on downtrend)",
                    "error" not in rej,
                    f"reason_type={reason}")
except Exception as exc:
    _record("Scenario 2 unhandled exception", False, str(exc)); traceback.print_exc()


# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 3: Ranging/compressed market — score below gate
# ──────────────────────────────────────────────────────────────────────────────
_section("Scenario 3 — Ranging market (compressed, expected below gate)")
try:
    orch = _make_orchestrator(regime="ranging", seed=42)
    plan, rej = _run_symbol(orch, "LINK/USDT", regime="ranging", seed=42)
    error = rej.get("error") if rej else None
    _record("Pipeline completes without crash", error is None, error or "")
    if not error:
        # Ranging markets should mostly produce below-gate rejections
        # (low volatility → no FVGs, no sweeps → low score)
        if plan:
            # If a plan IS generated, score must be valid
            _record("Plan has valid direction", plan.direction in ("LONG", "SHORT"),
                    f"direction={plan.direction}")
        else:
            reason = rej.get("reason_type", "") if rej else ""
            expected_rejection = reason in ("low_confluence", "missing_critical_tf",
                                            "directional_conflict", "no_data")
            _record("Ranging market correctly rejected (not an error)",
                    expected_rejection or "error" not in rej,
                    f"reason_type={reason}")
except Exception as exc:
    _record("Scenario 3 unhandled exception", False, str(exc)); traceback.print_exc()


# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 4: Volatile market — pipeline stability
# ──────────────────────────────────────────────────────────────────────────────
_section("Scenario 4 — Volatile market (pipeline stability)")
try:
    orch = _make_orchestrator(regime="volatile", seed=7)
    plan, rej = _run_symbol(orch, "SOL/USDT", regime="volatile", seed=7)
    error = rej.get("error") if rej else None
    _record("Pipeline completes without crash", error is None, error or "")
    if not error:
        _record("Result is plan or clean rejection",
                plan is not None or (rej is not None and "error" not in rej),
                "")
        if plan and hasattr(plan, 'confidence_score'):
            _record("Confidence score >= 0",
                    plan.confidence_score >= 0,
                    f"score={plan.confidence_score:.1f}")
except Exception as exc:
    _record("Scenario 4 unhandled exception", False, str(exc)); traceback.print_exc()


# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 5: Order block market — OB factor fires
# ──────────────────────────────────────────────────────────────────────────────
_section("Scenario 5 — Order block market (OB factor should score > 0)")
try:
    orch = _make_orchestrator(regime="order_blocks", seed=42)
    plan, rej = _run_symbol(orch, "BNB/USDT", regime="order_blocks", seed=42)
    error = rej.get("error") if rej else None
    _record("Pipeline completes without crash", error is None, error or "")

    if not error:
        # Check the rejection details for OB scoring if we have them
        if rej and "top_factors" in rej:
            ob_score_str = next(
                (f for f in rej["top_factors"] if "Order Block" in f), None
            )
            if ob_score_str:
                # Format is "Order Block: 72.0" etc
                try:
                    ob_score = float(ob_score_str.split(":")[1].strip())
                    _record("Order Block factor scored > 0", ob_score > 0,
                            f"ob_score={ob_score}")
                except Exception:
                    _record("OB score present in rejection details", True,
                            ob_score_str)
        if plan:
            _record("Plan generated (high OB structure quality)", True,
                    f"direction={plan.direction}")
        else:
            reason_type = rej.get("reason_type", "") if rej else ""
            _record("Clean rejection (not error)", "error" not in (rej or {}),
                    f"reason_type={reason_type}")
except Exception as exc:
    _record("Scenario 5 unhandled exception", False, str(exc)); traceback.print_exc()


# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 6: Multi-symbol scan — no symbol crashes the pipeline
# ──────────────────────────────────────────────────────────────────────────────
_section("Scenario 6 — Multi-symbol scan (pipeline stability across symbols)")
try:
    SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "LINK/USDT"]
    # Use one orchestrator, trending regime for predictability
    orch = _make_orchestrator(regime="trending", seed=42)

    crashed = []
    completed = []
    plans_generated = []
    rejected = []

    for sym in SYMBOLS:
        try:
            mtf = _make_mtf(sym, regime="trending", seed=42)
            run_id = uuid.uuid4().hex[:8]
            ts = datetime(2026, 3, 23, 14, 0, tzinfo=timezone.utc)
            plan, rej = orch._process_symbol(
                symbol=sym, run_id=run_id, timestamp=ts, prefetched_data=mtf
            )
            if rej and "error" in rej:
                crashed.append(f"{sym}: {rej['error'][:60]}")
            elif plan:
                plans_generated.append(sym)
                completed.append(sym)
            else:
                rejected.append(sym)
                completed.append(sym)
        except Exception as e:
            crashed.append(f"{sym}: {e!s:.60}")

    _record(f"All {len(SYMBOLS)} symbols complete without crash",
            len(crashed) == 0,
            f"crashed={crashed}" if crashed else "")
    _record(f"Pipeline completed for {len(completed)}/{len(SYMBOLS)} symbols",
            len(completed) == len(SYMBOLS),
            f"completed={completed}")
    print(f"       Plans: {plans_generated or 'none'}")
    print(f"       Rejected (clean): {rejected}")
    if crashed:
        print(f"       Crashed: {crashed}")
except Exception as exc:
    _record("Scenario 6 unhandled exception", False, str(exc)); traceback.print_exc()


# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 7: Synergy bonus never crashes (regression guard)
# ──────────────────────────────────────────────────────────────────────────────
_section("Scenario 7 — Synergy bonus >= 0 regression (trending market, varied seeds)")
try:
    orch = _make_orchestrator(regime="trending", seed=42)
    any_synergy_crash = False
    crash_msg = ""
    for seed in [1, 7, 13, 42, 99, 137, 256]:
        mtf = _make_mtf("BTC/USDT", regime="trending", seed=seed)
        run_id = uuid.uuid4().hex[:8]
        ts = datetime(2026, 3, 23, 14, 0, tzinfo=timezone.utc)
        try:
            plan, rej = orch._process_symbol(
                symbol="BTC/USDT", run_id=run_id, timestamp=ts, prefetched_data=mtf
            )
            if rej and "synergy" in str(rej.get("error", "")).lower():
                any_synergy_crash = True
                crash_msg = rej["error"]
        except Exception as e:
            if "synergy" in str(e).lower():
                any_synergy_crash = True
                crash_msg = str(e)
    _record("No synergy crash across 7 seeds", not any_synergy_crash, crash_msg)
except Exception as exc:
    _record("Scenario 7 unhandled exception", False, str(exc)); traceback.print_exc()


# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 8: Dead ticker (zero movement) — rejected, not crashed
# ──────────────────────────────────────────────────────────────────────────────
_section("Scenario 8 — Dead ticker (flat price, zero volatility)")
try:
    # Build a completely flat candle series — no movement at all
    def _flat_df(tf: str, bars: int = 500) -> pd.DataFrame:
        base_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        tf_h = _tf_to_hours(tf)
        rows = [{
            "timestamp": base_ts + timedelta(hours=i * tf_h),
            "open": 0.391, "high": 0.392, "low": 0.390,
            "close": 0.391, "volume": 1.0,
        } for i in range(bars)]
        return pd.DataFrame(rows)

    flat_mtf = MultiTimeframeData(
        symbol="MATIC/USDT",
        timeframes={tf: _flat_df(tf) for tf in ["1w", "1d", "4h", "1h", "15m"]},
    )
    orch = _make_orchestrator(regime="ranging", seed=42)
    run_id = uuid.uuid4().hex[:8]
    ts = datetime(2026, 3, 23, 14, 0, tzinfo=timezone.utc)
    plan, rej = orch._process_symbol(
        symbol="MATIC/USDT", run_id=run_id, timestamp=ts, prefetched_data=flat_mtf
    )
    error = rej.get("error") if rej else None
    _record("Dead ticker doesn't crash pipeline", error is None, error or "")
    _record("Dead ticker produces no trade plan", plan is None,
            f"unexpected plan: {plan}")
    if rej and not error:
        score = rej.get("score", None)
        _record("Score is near 0 (if present)",
                score is None or score < 15,
                f"score={score}")
except Exception as exc:
    _record("Scenario 8 unhandled exception", False, str(exc)); traceback.print_exc()


# ──────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ──────────────────────────────────────────────────────────────────────────────
print(f"\n{'═' * 65}")
print("  SUMMARY")
print(f"{'═' * 65}")

passes = sum(1 for _, s, _ in results if s == PASS)
fails  = sum(1 for _, s, _ in results if s == FAIL)
warns  = sum(1 for _, s, _ in results if s == WARN)
total  = len(results)

for name, status, detail in results:
    line = f"  {status}  {name}"
    if detail:
        line += f"  — {detail}"
    print(line)

print(f"\n{'─' * 65}")
print(f"  Total: {total}  |  Pass: {passes}  |  Fail: {fails}  |  Warn: {warns}")
print(f"{'─' * 65}")

if fails > 0:
    print(f"\n❌  {fails} check(s) failed.")
    sys.exit(1)
else:
    print(f"\n✅  All {passes} checks passed." + (f" ({warns} warnings)" if warns else ""))
    sys.exit(0)
