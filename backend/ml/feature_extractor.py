"""
ML Feature Extractor

Converts raw journal records into a numeric feature matrix for model training
and inference. Only uses records that were captured with the Phase-2A enrichment
(identified by the presence of a non-zero confidence_score).
"""

import math
import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Minimum enriched trades needed before we attempt training.
MIN_SAMPLES = 30

# Categorical cardinalities used for one-hot encoding.
_CONVICTION_MAP = {"A": 2, "B": 1, "C": 0}
_PLAN_TYPE_MAP = {"SMC": 0, "ATR_FALLBACK": 1, "HYBRID": 2}
_TRADE_TYPE_MAP = {"scalp": 0, "intraday": 1, "swing": 2}

_KILL_ZONES = [
    "no_session",
    "asian_session",
    "london_open",
    "london_session",
    "new_york_open",
    "new_york_session",
    "london_close",
]

_REGIMES = [
    "unknown",
    "bullish",
    "bearish",
    "ranging",
    "compressed",
    "volatile",
]


def is_enriched(record: Dict[str, Any]) -> bool:
    """Return True if this journal record has Phase-2A ML features."""
    return float(record.get("confidence_score") or 0) > 0


def extract_features(record: Dict[str, Any]) -> Optional[np.ndarray]:
    """
    Convert one journal record into a 1-D feature vector.

    Returns None if the record is not enriched (pre-Phase-2A trade).
    Feature ordering must stay stable — any change requires a model retrain.
    """
    if not is_enriched(record):
        return None

    feats: List[float] = []

    # ── Numeric ───────────────────────────────────────────────────────────────
    feats.append(float(record.get("confidence_score") or 0))
    feats.append(float(record.get("risk_reward_ratio") or 0))
    feats.append(float(record.get("stop_distance_atr") or 0))
    feats.append(float(record.get("pullback_probability") or 0))

    # ── Cyclical time encoding ────────────────────────────────────────────────
    entry_time = record.get("entry_time") or ""
    hour, dow = _parse_time(entry_time)
    feats.append(math.sin(2 * math.pi * hour / 24))
    feats.append(math.cos(2 * math.pi * hour / 24))
    feats.append(math.sin(2 * math.pi * dow / 7))
    feats.append(math.cos(2 * math.pi * dow / 7))

    # ── Ordinal ───────────────────────────────────────────────────────────────
    feats.append(float(_CONVICTION_MAP.get(str(record.get("conviction_class") or "B"), 1)))
    feats.append(float(_PLAN_TYPE_MAP.get(str(record.get("plan_type") or "SMC"), 0)))
    feats.append(float(_TRADE_TYPE_MAP.get(str(record.get("trade_type") or "intraday"), 1)))
    feats.append(1.0 if record.get("direction") == "LONG" else 0.0)

    # ── One-hot: kill zone ────────────────────────────────────────────────────
    kz = str(record.get("kill_zone") or "no_session").lower()
    for zone in _KILL_ZONES:
        feats.append(1.0 if kz == zone else 0.0)

    # ── One-hot: regime ───────────────────────────────────────────────────────
    reg = str(record.get("regime") or "unknown").lower()
    for r in _REGIMES:
        feats.append(1.0 if reg == r else 0.0)

    return np.array(feats, dtype=np.float32)


def build_dataset(
    records: List[Dict[str, Any]],
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    Build X (features) and y (labels) from a list of journal records.

    Label: 1 = win (pnl > 0), 0 = loss.

    Returns:
        X: shape (n_samples, n_features)
        y: shape (n_samples,)  binary
        trade_ids: list of trade_id strings in the same order
    """
    X_rows, y_rows, ids = [], [], []

    for rec in records:
        vec = extract_features(rec)
        if vec is None:
            continue
        label = 1 if float(rec.get("pnl") or 0) > 0 else 0
        X_rows.append(vec)
        y_rows.append(label)
        ids.append(rec.get("trade_id", ""))

    if not X_rows:
        return np.empty((0, 0)), np.empty((0,)), []

    return np.stack(X_rows), np.array(y_rows, dtype=np.int32), ids


def feature_names() -> List[str]:
    """Return the ordered list of feature names (for importance display)."""
    names = [
        "confidence_score",
        "risk_reward_ratio",
        "stop_distance_atr",
        "pullback_probability",
        "hour_sin",
        "hour_cos",
        "dow_sin",
        "dow_cos",
        "conviction_ordinal",
        "plan_type_ordinal",
        "trade_type_ordinal",
        "direction_long",
    ]
    names += [f"kz_{z}" for z in _KILL_ZONES]
    names += [f"regime_{r}" for r in _REGIMES]
    return names


# ── helpers ───────────────────────────────────────────────────────────────────

def _parse_time(iso: str) -> Tuple[int, int]:
    """Extract (hour_of_day, day_of_week) from an ISO timestamp string."""
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.hour, dt.weekday()
    except Exception:
        return 0, 0
