"""Display-only view of a pending entry's trade plan, shared by paper and live status.

Missing or invalid prices publish as None, never 0.0, so the UI can show
unknown instead of a fabricated level. This never recomputes the plan.
"""
from copy import deepcopy
import math
from typing import Any, Dict, Optional


def _price(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def pending_plan_view(plan: Any) -> Dict[str, Any]:
    zone = getattr(plan, "entry_zone", None)
    stop = getattr(plan, "stop_loss", None)
    score = getattr(plan, "confidence_score", None)
    metadata = getattr(plan, "metadata", None) or {}
    return {
        "entry_near": _price(getattr(zone, "near_entry", None)),
        "entry_far": _price(getattr(zone, "far_entry", None)),
        "stop_loss": _price(getattr(stop, "level", None)),
        "targets": [level for level in (_price(getattr(t, "level", None)) for t in getattr(plan, "targets", None) or []) if level],
        "timeframe": getattr(plan, "timeframe", None),
        "trade_type": getattr(plan, "trade_type", None),
        "confluence": float(score) if isinstance(score, (int, float)) and math.isfinite(score) else None,
        "rationale": getattr(plan, "rationale", None) or None,
        "strategy": deepcopy(metadata.get("strategy", {})),
    }
