"""
Signal Dataset Builder

Builds ML training datasets from scan signals (signals.jsonl) instead of
only completed trades. This provides 10-100x more training data by including
both executed and filtered signals.

Labeling strategy:
  - Executed signals matched to a completed trade → actual outcome (weight 1.0)
  - Executed signals with no matched trade → excluded (outcome unknown)
  - Filtered signals → label 0 with low weight (0.15) — the gauntlet rejected
    them for a reason, so they're weak negatives
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from backend.ml.feature_extractor import (
    extract_features,
    _KILL_ZONES,
)

logger = logging.getLogger(__name__)

_SESSION_LOGS_DIR = Path("logs/paper_trading")
_TRADE_JOURNAL_PATH = Path("backend/cache/trade_journal.jsonl")

FILTERED_SIGNAL_WEIGHT = 0.15


def _derive_kill_zone(timestamp_iso: str) -> str:
    """Derive kill zone from ISO timestamp."""
    try:
        dt = datetime.fromisoformat(timestamp_iso.replace("Z", "+00:00"))
        hour = dt.hour
        if 0 <= hour < 8:
            return "asian_session"
        elif 8 <= hour < 9:
            return "london_open"
        elif 9 <= hour < 12:
            return "london_session"
        elif 12 <= hour < 14:
            return "new_york_open"
        elif 14 <= hour < 17:
            return "new_york_session"
        elif 17 <= hour < 18:
            return "london_close"
        else:
            return "no_session"
    except Exception:
        return "no_session"


def _signal_to_record(signal: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a signal log entry into a format compatible with extract_features()."""
    return {
        "confidence_score": signal.get("confluence", 0),
        "risk_reward_ratio": signal.get("rr", 0) or 0,
        "stop_distance_atr": signal.get("stop_distance_atr", 0) or 0,
        "pullback_probability": signal.get("pullback_probability", 0) or 0,
        "entry_time": signal.get("timestamp", ""),
        "conviction_class": signal.get("conviction_class", "B"),
        "plan_type": signal.get("plan_type", "SMC"),
        "trade_type": signal.get("trade_type", "intraday"),
        "direction": signal.get("direction", "LONG"),
        "kill_zone": signal.get("kill_zone") or _derive_kill_zone(signal.get("timestamp", "")),
        "regime": signal.get("regime", "unknown"),
    }


def collect_signals() -> List[Dict[str, Any]]:
    """Read all signals from all session log directories."""
    signals = []

    if not _SESSION_LOGS_DIR.exists():
        return signals

    for session_dir in sorted(_SESSION_LOGS_DIR.iterdir()):
        signals_file = session_dir / "signals.jsonl"
        if not signals_file.exists():
            continue
        try:
            with open(signals_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            signals.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.warning("Failed to read %s: %s", signals_file, e)

    logger.info("Collected %d signals from %s", len(signals), _SESSION_LOGS_DIR)
    return signals


def load_trade_journal() -> List[Dict[str, Any]]:
    """Load completed trades from the trade journal."""
    trades = []
    if not _TRADE_JOURNAL_PATH.exists():
        return trades
    try:
        with open(_TRADE_JOURNAL_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        trades.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        logger.warning("Failed to read trade journal: %s", e)
    return trades


def _match_signal_to_trade(
    signal: Dict[str, Any],
    trades_by_symbol: Dict[str, List[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    """Find the trade that was opened from this executed signal."""
    symbol = signal.get("symbol", "")
    direction = signal.get("direction", "")
    signal_time = signal.get("timestamp", "")

    candidates = trades_by_symbol.get(symbol, [])
    if not candidates:
        return None

    try:
        sig_dt = datetime.fromisoformat(signal_time.replace("Z", "+00:00"))
    except Exception:
        return None

    best_match = None
    best_delta = float("inf")

    for trade in candidates:
        if trade.get("direction") != direction:
            continue
        trade_time = trade.get("entry_time", "")
        try:
            trade_dt = datetime.fromisoformat(trade_time.replace("Z", "+00:00"))
        except Exception:
            continue
        delta = abs((trade_dt - sig_dt).total_seconds())
        if delta < 300 and delta < best_delta:
            best_delta = delta
            best_match = trade

    return best_match


def build_signal_dataset(
    signals: Optional[List[Dict[str, Any]]] = None,
    trades: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[str]]:
    """
    Build training dataset from scan signals + trade outcomes.

    Returns same format as feature_extractor.build_dataset():
        X:              shape (n, 25) feature matrix
        y:              shape (n,)    binary labels
        sample_weights: shape (n,)    confidence weights
        ids:            list of signal identifiers
    """
    if signals is None:
        signals = collect_signals()
    if trades is None:
        trades = load_trade_journal()

    trades_by_symbol: Dict[str, List[Dict[str, Any]]] = {}
    for t in trades:
        sym = t.get("symbol", "")
        trades_by_symbol.setdefault(sym, []).append(t)

    X_rows, y_rows, w_rows, ids = [], [], [], []
    matched_trade_ids = set()

    for i, signal in enumerate(signals):
        record = _signal_to_record(signal)
        vec = extract_features(record)

        if vec is None:
            continue

        result = signal.get("result", "")
        sig_id = f"sig_{i}_{signal.get('symbol', '')}_{signal.get('timestamp', '')}"

        if result == "executed":
            matched_trade = _match_signal_to_trade(signal, trades_by_symbol)
            if matched_trade is None:
                continue

            trade_id = matched_trade.get("trade_id", "")
            if trade_id in matched_trade_ids:
                continue
            matched_trade_ids.add(trade_id)

            exit_reason = str(matched_trade.get("exit_reason", "")).lower()
            pnl = float(matched_trade.get("pnl", 0))

            if exit_reason == "target":
                label, weight = 1, 1.0
            elif exit_reason == "stop_loss":
                label, weight = 0, 1.0
            elif exit_reason in ("stagnation", "max_hours"):
                label, weight = (1 if pnl > 0 else 0), 0.3
            elif exit_reason == "manual":
                label, weight = (1 if pnl > 0 else 0), 0.5
            else:
                continue

            X_rows.append(vec)
            y_rows.append(label)
            w_rows.append(weight)
            ids.append(sig_id)

        elif result == "filtered":
            X_rows.append(vec)
            y_rows.append(0)
            w_rows.append(FILTERED_SIGNAL_WEIGHT)
            ids.append(sig_id)

    if not X_rows:
        return np.empty((0, 0)), np.empty((0,)), np.empty((0,)), []

    logger.info(
        "Signal dataset: %d samples (%d executed+matched, %d filtered)",
        len(X_rows),
        sum(1 for w in w_rows if w > FILTERED_SIGNAL_WEIGHT),
        sum(1 for w in w_rows if w == FILTERED_SIGNAL_WEIGHT),
    )

    return (
        np.stack(X_rows),
        np.array(y_rows, dtype=np.int32),
        np.array(w_rows, dtype=np.float32),
        ids,
    )
