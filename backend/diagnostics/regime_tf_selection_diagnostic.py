"""
Regime timeframe-selection diagnostic.

Proves (and guards against regression of) the bug where
RegimeDetector._detect_volatility / _detect_trend select the "primary"
timeframe with `sorted(by_timeframe.keys(), reverse=True)[0]`. That naive
lexicographic sort on TF strings ('1W','1D','4H','1H','15m','5m') returns
'5m' — the LOWEST timeframe — not the intended highest ('1W'). The comment
in regime_detector.py says "Get highest timeframe indicator", so the code
does not do what it claims.

Effect: the GLOBAL volatility regime (which gates swing out of the cascade)
is computed on 5-minute ATR%, almost always < 0.8% → perma-"compressed" →
swing perma-stripped → scalp monoculture.

This script:
  1. Shows the lexicographic-sort bug (no network).
  2. Fetches live BTC candles and computes ATR-14 %-of-price per TF, mapping
     each to the regime_detector volatility label, so you can see what the
     global label WOULD be on each timeframe.

Run:  python -m backend.diagnostics.regime_tf_selection_diagnostic
"""
from __future__ import annotations

import sys

# Label thresholds — mirror regime_detector._detect_volatility (daily-calibrated
# bands as of the 2026-05-31 fix). Keep in sync with that function.
_VOL_THRESHOLDS = (
    (2.5, "compressed"),
    (5.0, "normal"),
    (7.0, "elevated"),
    (9.5, "volatile"),
    (float("inf"), "chaotic"),
)

# Minutes-per-timeframe — the correct ordering key (the proposed fix).
# Keyed lowercase; lookups normalize case (the pipeline lowercases TF keys).
_TF_MINUTES = {"5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440, "1w": 10080}


def _tf_minutes(tf: str) -> int:
    return _TF_MINUTES.get(tf.lower(), -1)

CONFIG_TFS = ("1W", "1D", "4H", "1H", "15m", "5m")


def _label_for(atr_pct: float) -> str:
    for thresh, label in _VOL_THRESHOLDS:
        if atr_pct < thresh:
            return label
    return "chaotic"


def _buggy_primary_tf(keys) -> str:
    """What the current code picks: sorted lexicographically, reverse."""
    return sorted(keys, reverse=True)[0]


def _correct_primary_tf(keys) -> str:
    """What 'highest timeframe' SHOULD pick: max by real duration."""
    return max(keys, key=_tf_minutes)


def show_sort_bug() -> bool:
    """Exercise the REAL runtime selector and assert it picks the highest-duration
    TF. Returns True if the runtime is still bugged (selects the lowest TF)."""
    buggy = _buggy_primary_tf(CONFIG_TFS)
    print("=== TF SELECTION ===")
    print(f"  configured TFs               : {CONFIG_TFS}")
    print(f"  OLD lexical sort(rev)[0]      : {buggy!r}   (the bug: lowest TF)")

    # Import the runtime helper the production path now uses. If it's missing,
    # the fix was reverted → treat as bug present.
    try:
        from backend.analysis.regime_detector import _highest_duration_tf
    except Exception as e:
        print(f"  runtime _highest_duration_tf : MISSING ({e}) → fix reverted")
        return True

    runtime_full = _highest_duration_tf(CONFIG_TFS)
    runtime_no_1w = _highest_duration_tf(("1D", "4H", "1H", "15m", "5m"))
    print(f"  runtime selects (full set)   : {runtime_full!r}  (expect '1W')")
    print(f"  runtime selects (no 1W)      : {runtime_no_1w!r}  (expect '1D' — graceful fallback)")

    ok = runtime_full == "1W" and runtime_no_1w == "1D" and buggy == "5m"
    is_bug = not ok
    print(f"  >>> BUG PRESENT              : {is_bug}  (runtime must pick highest-duration TF)")
    return is_bug


def show_live_atr_table() -> None:
    try:
        from backend.data.adapters.phemex import PhemexAdapter
        from backend.data.ingestion_pipeline import IngestionPipeline
        from backend.indicators.volatility import compute_atr
    except Exception as e:  # pragma: no cover
        print(f"\n[skip live] import failed: {e}")
        return

    print("\n=== LIVE BTC ATR-14 %-OF-PRICE PER TIMEFRAME ===")
    try:
        adapter = PhemexAdapter(testnet=False)
        pipeline = IngestionPipeline(adapter)
        fetched = pipeline.parallel_fetch(
            symbols=["BTC/USDT"], timeframes=list(CONFIG_TFS), limit=500, max_workers=4
        )
    except Exception as e:  # pragma: no cover
        print(f"[skip live] fetch failed: {e}")
        return

    mtf = fetched.get("BTC/USDT")
    tfmap = getattr(mtf, "timeframes", None) or {}
    if not tfmap:
        print("[skip live] no BTC data returned")
        return

    # Iterate the ACTUAL fetched keys (pipeline lowercases; 1w may be absent).
    present = sorted(tfmap.keys(), key=_tf_minutes)
    rows = []
    for tf in present:
        df = tfmap.get(tf)
        if df is None or len(df) < 15 or "close" not in df.columns:
            rows.append((tf, None, None, "no-data"))
            continue
        try:
            atr = compute_atr(df, period=14).iloc[-1]
            price = df["close"].iloc[-1]
            atr_pct = (atr / price) * 100 if price else None
            rows.append((tf, atr_pct, price, _label_for(atr_pct) if atr_pct is not None else "n/a"))
        except Exception as e:
            rows.append((tf, None, None, f"err:{type(e).__name__}"))

    print(f"  {'TF':>4} {'ATR%':>8}  {'price':>12}  label")
    for tf, atr_pct, price, label in rows:
        pct = f"{atr_pct:.3f}" if atr_pct is not None else "  —  "
        px = f"{price:.2f}" if price is not None else "  —  "
        print(f"  {tf:>4} {pct:>8}  {px:>12}  {label}")

    buggy_tf = _buggy_primary_tf(tfmap.keys())
    correct_tf = _correct_primary_tf(tfmap.keys())
    by_label = {tf: label for tf, _, _, label in rows}
    print(f"\n  GLOBAL label TODAY (buggy, {buggy_tf}) : {by_label.get(buggy_tf)!r}")
    print(f"  GLOBAL label if fixed ({correct_tf})    : {by_label.get(correct_tf)!r}")


def main() -> int:
    is_bug = show_sort_bug()
    show_live_atr_table()
    # Exit non-zero while the bug is present so this guards regressions.
    return 1 if is_bug else 0


if __name__ == "__main__":
    sys.exit(main())
