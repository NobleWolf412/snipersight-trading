"""CvdTracker — per-symbol rolling Cumulative Volume Delta + entry-snapshot features.

decisions/2026-06-30__cvd-experiment (Phase A, OBSERVATIONAL ONLY — nothing here is read by the
planner/scorer/executor; it only feeds journal columns for the noise-floor test).

CVD = signed aggressive taker volume: a market BUY that lifts the ask is +amount (aggressive demand),
a market SELL that hits the bid is -amount (aggressive supply). The net over a window is the
"force behind the move" — the runners-vs-faders signal the candle autopsy found missing.

Design constraints (all measured, not assumed):
- Phemex via ccxt does NOT populate trade `id` -> de-dup + gap-detect by TIMESTAMP.
- fetchTrades is recent-only -> a poll gap silently drops trades; we DETECT it and expose a coverage
  fraction so gap-corrupted entries can be excluded from the clean test set (loud-failure, not silent).
- Features are DIRECTION-SIGNED relative to the trade (flow agreeing with the trade's side is +) so the
  LONG and SHORT cohorts don't self-cancel in the pooled correlation (bull/bear symmetry, CLAUDE.md §10).

This module performs NO network I/O — the poller feeds it trades via ingest(); pure + unit-testable.
"""
from __future__ import annotations

import statistics as _stats
from collections import defaultdict, deque
from typing import Deque, Dict, List, Tuple

_MIN = 60 * 1000  # one minute in ms


class CvdTracker:
    def __init__(
        self,
        long_window_ms: int = 60 * _MIN,   # 1h — matches STEALTH planning TF
        short_window_ms: int = 15 * _MIN,  # 15m
        z_history: int = 120,              # rolling samples of windowed net-flow for the z-score baseline
    ) -> None:
        self.long_window_ms = long_window_ms
        self.short_window_ms = short_window_ms
        self._trades: Dict[str, Deque[Tuple[int, float, float]]] = defaultdict(deque)  # (ts, signed_vol, price)
        self._last_ts: Dict[str, int] = {}
        self._last_gap_ts: Dict[str, int] = {}  # ts of the most recent detected coverage gap
        self._z_hist: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=z_history))

    # ── ingest ────────────────────────────────────────────────────────────────
    def ingest(self, symbol: str, trades: List[Tuple[int, float, float]]) -> None:
        """Add new (ts, signed_vol, price) trades (ASC by ts). De-dups by ts, detects coverage gaps,
        evicts trades older than the long window, and samples the windowed net-flow for the z baseline."""
        if not trades:
            return
        dq = self._trades[symbol]
        last = self._last_ts.get(symbol)
        oldest_in = trades[0][0]
        # Gap detection: on a non-first poll, if the oldest returned trade is newer than what we last
        # saw, trades fell off the recent-N window between polls and are lost -> mark a gap.
        if last is not None and oldest_in > last:
            self._last_gap_ts[symbol] = trades[-1][0]
        for ts, sv, px in trades:
            if last is not None and ts <= last:
                continue  # already seen (de-dup by timestamp — id is None on Phemex)
            dq.append((ts, sv, px))
        self._last_ts[symbol] = max(self._last_ts.get(symbol, 0), trades[-1][0])
        now = self._last_ts[symbol]
        # Evict beyond the long window.
        cutoff = now - self.long_window_ms
        while dq and dq[0][0] < cutoff:
            dq.popleft()
        # Sample the current 1h net-flow for the z baseline.
        net_1h = sum(sv for ts, sv, _ in dq if ts >= now - self.long_window_ms)
        self._z_hist[symbol].append(net_1h)

    # ── snapshot ──────────────────────────────────────────────────────────────
    def snapshot_features(self, symbol: str, direction: str, now_ms: int) -> Dict[str, float]:
        """Direction-signed CVD features at `now_ms` for a trade in `direction` ('LONG'/'SHORT').

        Returns a dict of journal-ready features. dir_sign = +1 LONG / -1 SHORT, so a value > 0 means
        the aggressive order flow AGREES with the trade's intended direction. Empty/cold symbol -> zeros
        with coverage 0 (excluded from the clean test set downstream)."""
        dir_sign = 1.0 if direction == "LONG" else -1.0
        dq = self._trades.get(symbol)
        zeros = {
            "cvd_slope_1h": 0.0, "cvd_divergence": 0.0, "cvd_z": 0.0,
            "cvd_coverage": 0.0, "cvd_n_trades": 0.0,
        }
        if not dq:
            return zeros

        long_cut = now_ms - self.long_window_ms
        win = [(ts, sv, px) for ts, sv, px in dq if ts >= long_cut]
        if not win:
            return zeros
        net = sum(sv for _, sv, _ in win)
        tot = sum(abs(sv) for _, sv, _ in win)
        imbalance = (net / tot) if tot > 0 else 0.0  # -1..+1 order-flow imbalance over 1h

        # price return over the window (oldest->newest in-window price)
        price_old = win[0][2]
        price_new = win[-1][2]
        price_ret = ((price_new - price_old) / price_old) if price_old > 0 else 0.0

        # divergence: flow disagrees with price IN THE TRADE'S FAVOR (the fade/exhaustion confirmation).
        cvd_dir = (net > 0) - (net < 0)
        px_dir = (price_ret > 0) - (price_ret < 0)
        if cvd_dir != 0 and px_dir != 0 and cvd_dir != px_dir:
            divergence = float(cvd_dir) * dir_sign  # +1 if flow supports the trade against price
        else:
            divergence = 0.0

        # z-score of the current 1h net-flow vs the per-symbol rolling baseline (normalized level).
        hist = self._z_hist.get(symbol)
        if hist and len(hist) >= 10:
            mu = _stats.mean(hist)
            sd = _stats.pstdev(hist)
            z = ((net - mu) / sd) if sd > 0 else 0.0
        else:
            z = 0.0  # warming up — not enough baseline yet

        # coverage: span actually covered (0..1) zeroed if a gap landed inside the window.
        span = (now_ms - win[0][0]) / self.long_window_ms
        coverage = max(0.0, min(1.0, span))
        last_gap = self._last_gap_ts.get(symbol)
        if last_gap is not None and last_gap >= long_cut:
            coverage = 0.0  # a gap corrupted this window -> exclude downstream

        return {
            "cvd_slope_1h": imbalance * dir_sign,   # the "force": flow imbalance in the trade's direction
            "cvd_divergence": divergence,           # -1/0/+1, signed for the trade
            "cvd_z": z * dir_sign,                  # normalized 1h net-flow, signed
            "cvd_coverage": coverage,               # 0..1 data-quality flag
            "cvd_n_trades": float(len(win)),        # sample size in the window (quality co-indicator)
        }
