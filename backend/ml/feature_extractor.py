"""
ML Feature Extractor

Converts raw journal records into a numeric feature matrix for model training
and inference. Only uses records that were captured with the Phase-2A enrichment
(identified by the presence of a non-zero confidence_score).

Triple-barrier labeling
-----------------------
Instead of a flat win/loss label, each trade is assigned a label and a sample
weight based on which barrier was hit first:

  Barrier          Label   Weight  Rationale
  ---------------  ------  ------  -----------------------------------------------
  target           1       1.0     High-confidence win — price reached TP cleanly
  stop_loss        0       1.0     High-confidence loss — price hit SL cleanly
  stagnation /     sign    0.3     Ambiguous — time ran out; outcome uncertain
  max_hours        (pnl)
  manual           sign    0.5     Partially ambiguous — human intervened
                   (pnl)

Trades that hit the time barrier still contribute to training but with reduced
weight so the model is not misled by uncertain outcomes.

Feature vector (37 total):
  [0-3]   confidence_score, risk_reward_ratio, stop_distance_atr, pullback_probability
  [4-7]   hour_sin, hour_cos, dow_sin, dow_cos
  [8-11]  conviction_ordinal, plan_type_ordinal, trade_type_ordinal, direction_long
  [12-18] kz_* one-hot (7)
  [19-24] regime_* one-hot (6)
  [25-29] synergy_bonus, conflict_penalty, htf_aligned, htf_proximity_atr, macro_score
  [30-36] rsi, adx, bb_percent_b, volume_ratio, macd_histogram_sign, atr_percent,
          volume_acceleration
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

# Sample weights per exit reason (triple-barrier confidence)
_BARRIER_WEIGHTS = {
    "target":     1.0,
    "stop_loss":  1.0,
    "manual":     0.5,
    "stagnation": 0.3,
    "max_hours":  0.3,
}


def is_enriched(record: Dict[str, Any]) -> bool:
    """Return True if this journal record has Phase-2A ML features."""
    return float(record.get("confidence_score") or 0) > 0


def extract_features(record: Dict[str, Any]) -> Optional[np.ndarray]:
    """
    Convert one journal record into a 1-D feature vector (37 features).

    Returns None if the record is not enriched (pre-Phase-2A trade).
    Feature ordering must stay stable — any change requires a model retrain.
    """
    if not is_enriched(record):
        return None

    feats: List[float] = []

    # ── [0-3] Core numeric ────────────────────────────────────────────────────
    feats.append(float(record.get("confidence_score") or 0))
    feats.append(float(record.get("risk_reward_ratio") or 0))
    feats.append(float(record.get("stop_distance_atr") or 0))
    feats.append(float(record.get("pullback_probability") or 0))

    # ── [4-7] Cyclical time encoding ──────────────────────────────────────────
    entry_time = record.get("entry_time") or record.get("timestamp") or ""
    hour, dow = _parse_time(entry_time)
    feats.append(math.sin(2 * math.pi * hour / 24))
    feats.append(math.cos(2 * math.pi * hour / 24))
    feats.append(math.sin(2 * math.pi * dow / 7))
    feats.append(math.cos(2 * math.pi * dow / 7))

    # ── [8-11] Ordinal categoricals ───────────────────────────────────────────
    feats.append(float(_CONVICTION_MAP.get(str(record.get("conviction_class") or "B"), 1)))
    feats.append(float(_PLAN_TYPE_MAP.get(str(record.get("plan_type") or "SMC"), 0)))
    feats.append(float(_TRADE_TYPE_MAP.get(str(record.get("trade_type") or "intraday"), 1)))
    feats.append(1.0 if record.get("direction") == "LONG" else 0.0)

    # ── [12-18] One-hot: kill zone ────────────────────────────────────────────
    kz = str(record.get("kill_zone") or "no_session").lower()
    for zone in _KILL_ZONES:
        feats.append(1.0 if kz == zone else 0.0)

    # ── [19-24] One-hot: regime ───────────────────────────────────────────────
    reg = str(record.get("regime") or "unknown").lower()
    for r in _REGIMES:
        feats.append(1.0 if reg == r else 0.0)

    # ── [25-29] Confluence breakdown features ─────────────────────────────────
    # synergy_bonus: 0-10, normalize to 0-1
    feats.append(min(1.0, float(record.get("synergy_bonus") or 0) / 10.0))
    # conflict_penalty: 0-20, normalize to 0-1
    feats.append(min(1.0, float(record.get("conflict_penalty") or 0) / 20.0))
    # htf_aligned: already 0/1
    feats.append(float(record.get("htf_aligned") or 0))
    # htf_proximity_atr: distance to HTF level in ATR units; clip at 5, normalize
    feats.append(min(1.0, float(record.get("htf_proximity_atr") or 0) / 5.0))
    # macro_score: -20 to +20, shift to 0-1
    feats.append((float(record.get("macro_score") or 0) + 20.0) / 40.0)

    # ── [30-36] Indicator snapshot features ───────────────────────────────────
    # rsi: 0-100, normalize to 0-1
    feats.append(float(record.get("rsi") or 50) / 100.0)
    # adx: 0-100, normalize to 0-1
    feats.append(float(record.get("adx") or 0) / 100.0)
    # bb_percent_b: already 0-1 (0=at lower band, 1=at upper band)
    feats.append(float(record.get("bb_percent_b") or 0.5))
    # volume_ratio (RVOL): current/average, clip at 5, normalize
    feats.append(min(1.0, float(record.get("volume_ratio") or 1.0) / 5.0))
    # macd_histogram sign: -1 / 0 / +1 (direction of momentum)
    _mh = float(record.get("macd_histogram") or 0)
    feats.append(1.0 if _mh > 0 else (-1.0 if _mh < 0 else 0.0))
    # atr_percent: ATR as % of price, clip at 5%, normalize
    feats.append(min(1.0, float(record.get("atr_percent") or 0) / 5.0))
    # volume_acceleration: normalized slope -1 to +1
    feats.append(max(-1.0, min(1.0, float(record.get("volume_acceleration") or 0))))

    return np.array(feats, dtype=np.float32)


def build_dataset(
    records: List[Dict[str, Any]],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[str]]:
    """
    Build X (features), y (labels), and sample_weights from journal records.

    Triple-barrier labeling:
      - target          → label 1, weight 1.0
      - stop_loss       → label 0, weight 1.0
      - stagnation /
        max_hours       → label from sign(pnl), weight 0.3
      - manual          → label from sign(pnl), weight 0.5

    Returns:
        X:              shape (n_samples, n_features)
        y:              shape (n_samples,)  binary int32
        sample_weights: shape (n_samples,)  float32
        trade_ids:      list of trade_id strings in the same order
    """
    X_rows, y_rows, w_rows, ids = [], [], [], []

    for rec in records:
        vec = extract_features(rec)
        if vec is None:
            continue

        exit_reason = str(rec.get("exit_reason") or "").lower()
        pnl = float(rec.get("pnl") or 0)

        label, weight = _barrier_label(exit_reason, pnl)

        X_rows.append(vec)
        y_rows.append(label)
        w_rows.append(weight)
        ids.append(rec.get("trade_id", ""))

    if not X_rows:
        return np.empty((0, 0)), np.empty((0,)), np.empty((0,)), []

    return (
        np.stack(X_rows),
        np.array(y_rows, dtype=np.int32),
        np.array(w_rows, dtype=np.float32),
        ids,
    )


def feature_names() -> List[str]:
    """Return the ordered list of feature names (for importance display)."""
    names = [
        # [0-3] core
        "confidence_score",
        "risk_reward_ratio",
        "stop_distance_atr",
        "pullback_probability",
        # [4-7] time
        "hour_sin",
        "hour_cos",
        "dow_sin",
        "dow_cos",
        # [8-11] ordinal
        "conviction_ordinal",
        "plan_type_ordinal",
        "trade_type_ordinal",
        "direction_long",
    ]
    # [12-18] kill zone one-hot
    names += [f"kz_{z}" for z in _KILL_ZONES]
    # [19-24] regime one-hot
    names += [f"regime_{r}" for r in _REGIMES]
    # [25-29] confluence breakdown
    names += [
        "synergy_bonus",
        "conflict_penalty",
        "htf_aligned",
        "htf_proximity_atr",
        "macro_score",
    ]
    # [30-36] indicator snapshot
    names += [
        "rsi",
        "adx",
        "bb_percent_b",
        "volume_ratio",
        "macd_histogram_sign",
        "atr_percent",
        "volume_acceleration",
    ]
    return names


# ── helpers ───────────────────────────────────────────────────────────────────

def _barrier_label(exit_reason: str, pnl: float) -> Tuple[int, float]:
    """
    Return (label, sample_weight) for a trade.

    Clear barriers (target / stop_loss) get full weight.
    Time/ambiguous barriers get reduced weight and are labeled by pnl sign.
    """
    if exit_reason == "target":
        return 1, 1.0
    if exit_reason == "stop_loss":
        return 0, 1.0
    label = 1 if pnl > 0 else 0
    weight = _BARRIER_WEIGHTS.get(exit_reason, 0.3)
    return label, weight


def _parse_time(iso: str) -> Tuple[int, int]:
    """Extract (hour_of_day, day_of_week) from an ISO timestamp string."""
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.hour, dt.weekday()
    except Exception:
        return 0, 0
