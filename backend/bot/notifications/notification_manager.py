"""
Notification Event System for SniperSight Backend

Handles generation of notification events that can be consumed
by the frontend notification system via WebSocket or polling.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
import json

class NotificationType(str, Enum):
    """Types of notifications that can be sent."""
    SIGNAL = "signal"
    RISK_ALERT = "risk_alert"
    EXECUTION = "execution" 
    SYSTEM = "system"


class NotificationPriority(str, Enum):
    """Priority levels for notifications."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class NotificationEvent:
    """A notification event to be sent to the frontend."""
    id: str
    type: NotificationType
    priority: NotificationPriority
    timestamp: datetime
    title: str
    body: str
    data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result


class NotificationManager:
    """Manages notification events for the backend."""
    
    def __init__(self):
        self.events: List[NotificationEvent] = []
        self.max_events = 100  # Keep last 100 events
    
    def send_signal_notification(self, signal_data: Dict[str, Any]) -> str:
        """Send high-confidence signal notification."""
        event_id = f"signal-{signal_data['symbol']}-{int(datetime.now().timestamp())}"
        
        event = NotificationEvent(
            id=event_id,
            type=NotificationType.SIGNAL,
            priority=NotificationPriority.HIGH if signal_data['confidence'] >= 80 else NotificationPriority.NORMAL,
            timestamp=datetime.now(timezone.utc),
            title=f"🎯 High-Confidence Setup: {signal_data['symbol']}",
            body=f"{signal_data['direction']} • {signal_data['confidence']:.1f}% confidence • {signal_data.get('risk_reward', 0):.1f}:1 R:R",
            data=signal_data
        )
        
        self._add_event(event)
        return event_id
    
    def send_risk_alert(self, alert_type: str, message: str, severity: str = "warning", data: Optional[Dict] = None) -> str:
        """Send risk management alert."""
        event_id = f"risk-{alert_type}-{int(datetime.now().timestamp())}"
        
        priority = NotificationPriority.CRITICAL if severity == "critical" else NotificationPriority.HIGH
        
        event = NotificationEvent(
            id=event_id,
            type=NotificationType.RISK_ALERT,
            priority=priority,
            timestamp=datetime.now(timezone.utc),
            title=f"⚠️ Risk Alert: {alert_type.replace('_', ' ').upper()}",
            body=message,
            data={"alert_type": alert_type, "severity": severity, **(data or {})}
        )
        
        self._add_event(event)
        return event_id
    
    def send_execution_notification(self, execution_data: Dict[str, Any]) -> str:
        """Send order execution notification."""
        event_id = f"execution-{execution_data['symbol']}-{int(datetime.now().timestamp())}"
        
        status_emoji = {
            "filled": "✅",
            "partial": "🟡",
            "cancelled": "❌", 
            "rejected": "🚫"
        }
        
        status = execution_data.get('status', 'unknown')
        emoji = status_emoji.get(status, "📈")
        
        event = NotificationEvent(
            id=event_id,
            type=NotificationType.EXECUTION,
            priority=NotificationPriority.HIGH if status == "rejected" else NotificationPriority.NORMAL,
            timestamp=datetime.now(timezone.utc),
            title=f"{emoji} Order {status.upper()}: {execution_data['symbol']}",
            body=f"{execution_data.get('side', 'BUY')} {execution_data.get('quantity', 0)} @ ${execution_data.get('price', 0):.2f}",
            data=execution_data
        )
        
        self._add_event(event)
        return event_id
    
    def send_system_notification(self, title: str, body: str, priority: str = "normal", action: Optional[str] = None) -> str:
        """Send system notification."""
        event_id = f"system-{int(datetime.now().timestamp())}"
        
        event = NotificationEvent(
            id=event_id,
            type=NotificationType.SYSTEM,
            priority=NotificationPriority(priority),
            timestamp=datetime.now(timezone.utc),
            title=title,
            body=body,
            data={"action": action} if action else None
        )
        
        self._add_event(event)
        return event_id
    
    def _add_event(self, event: NotificationEvent):
        """Add event to the queue, maintaining max size."""
        self.events.append(event)
        
        # Trim to max size
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
    
    def get_recent_events(self, limit: int = 20, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get recent notification events."""
        events = self.events
        
        # Filter by timestamp if provided
        if since:
            events = [e for e in events if e.timestamp > since]
        
        # Sort by timestamp (newest first) and limit
        events = sorted(events, key=lambda x: x.timestamp, reverse=True)
        
        return [event.to_dict() for event in events[:limit]]
    
    def get_event_by_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific event by ID."""
        for event in self.events:
            if event.id == event_id:
                return event.to_dict()
        return None
    
    def clear_events(self):
        """Clear all events."""
        self.events.clear()


# Global notification manager instance
notification_manager = NotificationManager()