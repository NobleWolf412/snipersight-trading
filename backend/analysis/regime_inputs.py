"""Completed-candle evidence requirements shared by core and market advice."""
from datetime import timedelta, timezone

import numpy as np
import pandas as pd


def validate_regime_candles(frame, hours, now):
    """Return the final close time, rejecting absent, malformed or stale evidence."""
    if frame is None or len(frame) < 50 or not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError("insufficient timestamped history")
    if frame.index.tz is None or not frame.index.is_monotonic_increasing or not frame.index.is_unique:
        raise ValueError("timestamps must be ordered unique timezone-aware instants")
    values = frame[["high", "low", "close", "volume"]].to_numpy(dtype=float)
    if (not np.isfinite(values).all() or (values[:, :3] <= 0).any()
            or (values[:, 3] < 0).any() or (values[:, 0] < values[:, 1]).any()
            or (values[:, 2] > values[:, 0]).any() or (values[:, 2] < values[:, 1]).any()):
        raise ValueError("invalid market observations")
    if not (frame.index.to_series().diff().dropna() == pd.Timedelta(hours=hours)).all():
        raise ValueError("non-contiguous candle history")
    closed = frame.index[-1].to_pydatetime() + timedelta(hours=hours)
    if not closed <= now <= closed + timedelta(hours=hours, minutes=5):
        raise ValueError("forming or stale candles")
    return closed.astimezone(timezone.utc).isoformat()
