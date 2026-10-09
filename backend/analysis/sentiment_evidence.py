"""Validate source observations without importing the API or initiating clients."""
from datetime import datetime, timezone
import math


def parse_sentiment_observation(row, *, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(row, dict):
        raise ValueError("Sentiment observation is missing")
    value, timestamp = row.get("value"), row.get("timestamp")
    if isinstance(value, bool) or isinstance(timestamp, bool):
        raise ValueError("Sentiment observation contains a boolean")
    try:
        numeric, observed = float(value), float(timestamp)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("Sentiment value and provider time are required") from exc
    if not math.isfinite(numeric) or not numeric.is_integer() or not 0 <= numeric <= 100:
        raise ValueError("Sentiment value must be an integer from 0 to 100")
    if not math.isfinite(observed) or not 0 <= now.timestamp() - observed < 36 * 3600:
        raise ValueError("Sentiment observation is stale, future or invalid")
    classification = row.get("value_classification")
    if not isinstance(classification, str) or not classification.strip():
        raise ValueError("Sentiment classification is missing")
    return int(numeric), classification, datetime.fromtimestamp(observed, timezone.utc).isoformat()
