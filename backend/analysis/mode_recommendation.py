"""Shared, deterministic mode advice. Suitability is a policy, not win probability."""
from datetime import datetime, timedelta, timezone

from backend.shared.config.scanner_modes import get_mode

RECOMMENDATION_VERSION = "mode-routing-v1"
MODES = ("overwatch", "strike", "surgical", "stealth")


def unavailable_recommendation(reason="Market analysis is unavailable."):
    return {"status": "unavailable", "mode": None, "reason": reason,
            "reason_code": "INPUT_UNAVAILABLE", "warning": reason,
            "confidence": "unavailable", "policy_version": RECOMMENDATION_VERSION,
            "calibration": "uncalibrated", "recommended_confluence": None}


def recommend_mode(snapshot, allowed_modes=MODES, *, now=None):
    """Select one allowed playbook from a fresh daily/4h market snapshot.

    Weekly alignment permits a swing suggestion only when OVERWATCH is allowed.
    Dominance risk labels remain context: absolute basket shares do not prove flows.
    """
    allowed = tuple(dict.fromkeys(allowed_modes))
    if not allowed or any(mode not in MODES for mode in allowed):
        raise ValueError("At least one valid allowed mode is required")
    now = now or datetime.now(timezone.utc)
    try:
        expires = datetime.fromisoformat(snapshot["expires_at"].replace("Z", "+00:00"))
        observed = datetime.fromisoformat(snapshot["timestamp"].replace("Z", "+00:00"))
        if expires.tzinfo is None or observed.tzinfo is None or not observed <= now < expires:
            return unavailable_recommendation("Market analysis has expired; waiting for fresh data.")
        for tf, hours in (("1d", 24), ("4h", 4)):
            source = datetime.fromisoformat(snapshot["source_times"][tf].replace("Z", "+00:00"))
            if source.tzinfo is None or not source <= now <= source + timedelta(hours=hours, minutes=5):
                return unavailable_recommendation("Required market candles are stale or invalid.")
        dimensions = snapshot["dimensions"]
        daily = dimensions["trend"]
        volatility = dimensions["volatility"]
        matrix = snapshot["matrix"]
        intermediate = matrix["4h"]["trend"]
        if dimensions.get("liquidity") not in ("thin", "healthy", "heavy"):
            raise ValueError("Unknown participation")
        if snapshot["reference_timeframe"] != "1d":
            raise ValueError("Daily reference required")
        trends = {"up", "strong_up", "down", "strong_down", "sideways"}
        if daily not in trends or intermediate not in trends:
            raise ValueError("Unknown trend")
        if volatility not in {"compressed", "normal", "elevated", "volatile", "chaotic"}:
            raise ValueError("Unknown volatility")
    except (KeyError, TypeError, ValueError, AttributeError):
        return unavailable_recommendation("Required daily and 4h market evidence is incomplete.")

    result = {"status": "available", "mode": None, "reason": "", "warning": None,
              "confidence": "rule_based", "policy_version": RECOMMENDATION_VERSION,
              "calibration": "uncalibrated", "reference_timeframe": "1d",
              "timestamp": snapshot["timestamp"], "expires_at": snapshot["expires_at"],
              "source_times": dict(snapshot.get("source_times", {})),
              "regime": {**dimensions, "composite": snapshot.get("composite"),
                         "score": snapshot.get("score")},
              "matrix": matrix, "recommended_confluence": None}
    if volatility in {"volatile", "chaotic"} or dimensions.get("liquidity") == "thin":
        result.update(status="stand_aside", reason_code="UNSUITABLE_CONDITIONS",
                      reason="High daily volatility or thin participation: wait for clearer conditions.")
        return result

    def direction(trend):
        return "up" if trend in ("up", "strong_up") else "down" if trend in ("down", "strong_down") else None

    weekly = matrix.get("1w", {}).get("trend")
    try:
        weekly_source = datetime.fromisoformat(snapshot["source_times"]["1w"].replace("Z", "+00:00"))
        if weekly_source.tzinfo is None or not weekly_source <= now <= weekly_source + timedelta(days=7, minutes=5):
            weekly = None
    except (KeyError, TypeError, ValueError, AttributeError):
        weekly = None
    if ("overwatch" in allowed and direction(daily) is not None
            and direction(weekly) == direction(daily) == direction(intermediate)):
        mode, code = "overwatch", "ALIGNED_SWING_CONTEXT"
        reason = "Weekly, daily and 4h trends agree. OVERWATCH can search for swing setups."
    elif direction(intermediate) is not None and volatility in ("normal", "elevated"):
        if direction(daily) is not None and direction(daily) != direction(intermediate):
            mode, code = "stealth", "MIXED_TIMEFRAME_CONTEXT"
            reason = "Daily and 4h directions disagree. STEALTH can evaluate balanced setups with that conflict visible."
        else:
            mode, code = "strike", "INTERMEDIATE_TREND"
            reason = "The 4h trend is clear with manageable daily volatility. STRIKE can search for trend setups."
    elif daily == intermediate == "sideways" and volatility == "normal":
        mode, code = "surgical", "RANGE_CONTEXT"
        reason = "Daily and 4h structure are ranging. SURGICAL can search for confirmed entries at range locations."
    else:
        mode, code = "stealth", "BALANCED_CONTEXT"
        reason = "Mixed or compressed conditions favour a balanced search. A confirmed setup is still required."
    if mode not in allowed:
        result.update(status="stand_aside", reason_code="MODE_NOT_ALLOWED",
                      reason=f"These conditions suggest {mode.upper()}, which is outside the allowed modes.")
        return result
    result.update(mode=mode, reason_code=code, reason=reason,
                  recommended_confluence=get_mode(mode).min_confluence_score)
    return result


class AdaptiveModeSelector:
    """Paper routing state: a changed mode needs two distinct 4h observations."""
    def __init__(self):
        self.active_mode = None
        self.pending_mode = None
        self.pending_source = None

    def select(self, snapshot, allowed_modes):
        result = recommend_mode(snapshot, allowed_modes)
        if result["status"] != "available":
            self.pending_mode = self.pending_source = None
            return result
        mode = result["mode"]
        if self.active_mode is None or mode == self.active_mode:
            self.active_mode = mode
            self.pending_mode = self.pending_source = None
            return result
        source = result.get("source_times", {}).get("4h")
        if (source and self.pending_mode == mode and self.pending_source is not None
                and datetime.fromisoformat(source) > datetime.fromisoformat(self.pending_source)):
            self.active_mode = mode
            self.pending_mode = self.pending_source = None
            return result
        if self.pending_mode != mode:
            self.pending_mode, self.pending_source = mode, source
        return {**result, "status": "stand_aside", "mode": None,
                "reason_code": "MODE_CHANGE_PENDING",
                "reason": "Waiting for another completed 4h observation to confirm the mode change."}
