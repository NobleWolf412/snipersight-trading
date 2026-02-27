"""
Telemetry Event Models

Defines all telemetry event types and data structures for tracking
scanner/bot decisions, pipeline execution, and system activity.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from enum import Enum


class EventType(str, Enum):
    """Telemetry event types."""

    # Scan lifecycle
    SCAN_STARTED = "scan_started"
    SCAN_COMPLETED = "scan_completed"

    # Signal generation
    SIGNAL_GENERATED = "signal_generated"
    SIGNAL_REJECTED = "signal_rejected"
    ALT_STOP_SUGGESTED = "alt_stop_suggested"

    # Quality gates
    QUALITY_GATE_PASSED = "quality_gate_passed"
    QUALITY_GATE_FAILED = "quality_gate_failed"

    # Bot operations
    BOT_STARTED = "bot_started"
    BOT_STOPPED = "bot_stopped"
    BOT_CYCLE_COMPLETED = "bot_cycle_completed"

    # Position management
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    PARTIAL_TAKEN = "partial_taken"
    STOP_LOSS_HIT = "stop_loss_hit"

    # Risk management
    RISK_LIMIT_HIT = "risk_limit_hit"
    DAILY_LOSS_LIMIT_HIT = "daily_loss_limit_hit"

    # System events
    ERROR_OCCURRED = "error_occurred"
    WARNING_ISSUED = "warning_issued"
    INFO_MESSAGE = "info_message"


@dataclass
class TelemetryEvent:
    """
    Base telemetry event structure.

    All events share these common fields, with event-specific data
    stored in the flexible `data` dictionary.
    """

    event_type: EventType
    timestamp: datetime
    run_id: Optional[str] = None
    symbol: Optional[str] = None
    data: Dict[str, Any] = None

    def __post_init__(self):
        """Ensure timestamp is timezone-aware and data is initialized."""
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)
        if self.data is None:
            self.data = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization."""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        result["event_type"] = self.event_type.value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TelemetryEvent":
        """Create event from dictionary."""
        data = data.copy()
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["event_type"] = EventType(data["event_type"])
        return cls(**data)


# Event factory functions for common event types


def create_scan_started_event(run_id: str, symbols: list, profile: str) -> TelemetryEvent:
    """Create scan started event."""
    return TelemetryEvent(
        event_type=EventType.SCAN_STARTED,
        timestamp=datetime.now(timezone.utc),
        run_id=run_id,
        data={"symbols": symbols, "symbol_count": len(symbols), "profile": profile},
    )


def create_scan_completed_event(
    run_id: str,
    symbols_scanned: int,
    signals_generated: int,
    signals_rejected: int,
    duration_seconds: float,
) -> TelemetryEvent:
    """Create scan completed event."""
    return TelemetryEvent(
        event_type=EventType.SCAN_COMPLETED,
        timestamp=datetime.now(timezone.utc),
        run_id=run_id,
        data={
            "symbols_scanned": symbols_scanned,
            "signals_generated": signals_generated,
            "signals_rejected": signals_rejected,
            "duration_seconds": round(duration_seconds, 2),
        },
    )


def create_signal_generated_event(
    run_id: str,
    symbol: str,
    direction: str,
    confidence_score: float,
    setup_type: str,
    entry_price: float,
    risk_reward_ratio: float,
) -> TelemetryEvent:
    """Create signal generated event."""
    return TelemetryEvent(
        event_type=EventType.SIGNAL_GENERATED,
        timestamp=datetime.now(timezone.utc),
        run_id=run_id,
        symbol=symbol,
        data={
            "direction": direction,
            "confidence_score": round(confidence_score, 2),
            "setup_type": setup_type,
            "entry_price": entry_price,
            "risk_reward_ratio": round(risk_reward_ratio, 2),
        },
    )


def create_signal_rejected_event(
    run_id: str,
    symbol: str,
    reason: str,
    gate_name: Optional[str] = None,
    score: Optional[float] = None,
    threshold: Optional[float] = None,
    diagnostics: Optional[Dict[str, Any]] = None,
) -> TelemetryEvent:
    """Create signal rejected event."""
    data = {"reason": reason}
    if gate_name:
        data["gate_name"] = gate_name
    if score is not None:
        data["score"] = round(score, 2)
    if threshold is not None:
        data["threshold"] = round(threshold, 2)
    if diagnostics:
        # Attach structured diagnostics for UI/console visibility
        data["diagnostics"] = diagnostics

    return TelemetryEvent(
        event_type=EventType.SIGNAL_REJECTED,
        timestamp=datetime.now(timezone.utc),
        run_id=run_id,
        symbol=symbol,
        data=data,
    )


def create_alt_stop_suggested_event(
    run_id: str,
    symbol: str,
    direction: str,
    cushion_pct: float,
    risk_band: str,
    suggested_level: float,
    current_stop: float,
    leverage: int,
    regime_label: str,
    recommended_buffer_atr: float,
) -> TelemetryEvent:
    """Create alternative stop suggestion event for high liquidation risk scenarios."""
    return TelemetryEvent(
        event_type=EventType.ALT_STOP_SUGGESTED,
        timestamp=datetime.now(timezone.utc),
        run_id=run_id,
        symbol=symbol,
        data={
            "direction": direction,
            "cushion_pct": round(cushion_pct, 4),
            "risk_band": risk_band,
            "suggested_level": suggested_level,
            "current_stop": current_stop,
            "leverage": leverage,
            "regime_label": regime_label,
            "recommended_buffer_atr": recommended_buffer_atr,
        },
    )


def create_quality_gate_event(
    run_id: str, symbol: str, gate_name: str, passed: bool, details: Dict[str, Any]
) -> TelemetryEvent:
    """Create quality gate event."""
    return TelemetryEvent(
        event_type=EventType.QUALITY_GATE_PASSED if passed else EventType.QUALITY_GATE_FAILED,
        timestamp=datetime.now(timezone.utc),
        run_id=run_id,
        symbol=symbol,
        data={"gate_name": gate_name, **details},
    )


def create_error_event(
    error_message: str,
    error_type: str,
    symbol: Optional[str] = None,
    run_id: Optional[str] = None,
    traceback: Optional[str] = None,
) -> TelemetryEvent:
    """Create error event."""
    data = {"error_message": error_message, "error_type": error_type}
    if traceback:
        data["traceback"] = traceback

    return TelemetryEvent(
        event_type=EventType.ERROR_OCCURRED,
        timestamp=datetime.now(timezone.utc),
        run_id=run_id,
        symbol=symbol,
        data=data,
    )


def create_bot_started_event(mode: str, profile: str, config: Dict[str, Any]) -> TelemetryEvent:
    """Create bot started event."""
    return TelemetryEvent(
        event_type=EventType.BOT_STARTED,
        timestamp=datetime.now(timezone.utc),
        data={"mode": mode, "profile": profile, "config": config},
    )


def create_bot_stopped_event(reason: str = "user_requested") -> TelemetryEvent:
    """Create bot stopped event."""
    return TelemetryEvent(
        event_type=EventType.BOT_STOPPED,
        timestamp=datetime.now(timezone.utc),
        data={"reason": reason},
    )


def create_info_event(
    message: str,
    stage: Optional[str] = None,
    symbol: Optional[str] = None,
    run_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> TelemetryEvent:
    """Create info message event for pipeline progress."""
    data = {"message": message}
    if stage:
        data["stage"] = stage
    if payload:
        data["payload"] = payload

    return TelemetryEvent(
        event_type=EventType.INFO_MESSAGE,
        timestamp=datetime.now(timezone.utc),
        run_id=run_id,
        symbol=symbol,
        data=data,
    )
