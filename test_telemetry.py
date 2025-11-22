#!/usr/bin/env python3
"""
Test script to verify telemetry system is working.

Emits sample telemetry events and queries them back.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.bot.telemetry.logger import get_telemetry_logger
from backend.bot.telemetry.events import (
    create_scan_started_event,
    create_scan_completed_event,
    create_signal_generated_event,
    create_signal_rejected_event,
    EventType
)

def test_telemetry():
    """Test telemetry system end-to-end."""
    print("=" * 80)
    print("TELEMETRY SYSTEM TEST")
    print("=" * 80)
    print()
    
    # Get telemetry logger
    telemetry = get_telemetry_logger()
    print("✓ Telemetry logger initialized")
    print()
    
    # Emit test events
    print("Emitting test events...")
    
    # Scan started
    scan_event = create_scan_started_event(
        run_id="test123",
        symbols=["BTC/USDT", "ETH/USDT", "SOL/USDT"],
        profile="balanced"
    )
    telemetry.log_event(scan_event)
    print("  ✓ Scan started event")
    
    # Signal generated
    signal_event = create_signal_generated_event(
        run_id="test123",
        symbol="BTC/USDT",
        direction="LONG",
        confidence_score=85.5,
        setup_type="OB_FVG_Confluence",
        entry_price=42150.0,
        risk_reward_ratio=3.2
    )
    telemetry.log_event(signal_event)
    print("  ✓ Signal generated event")
    
    # Signal rejected
    reject_event = create_signal_rejected_event(
        run_id="test123",
        symbol="ETH/USDT",
        reason="Below minimum confluence threshold",
        gate_name="confluence_score",
        score=62.5,
        threshold=70.0
    )
    telemetry.log_event(reject_event)
    print("  ✓ Signal rejected event")
    
    # Scan completed
    complete_event = create_scan_completed_event(
        run_id="test123",
        symbols_scanned=3,
        signals_generated=1,
        signals_rejected=2,
        duration_seconds=2.45
    )
    telemetry.log_event(complete_event)
    print("  ✓ Scan completed event")
    print()
    
    # Query events back
    print("Querying events from storage...")
    recent_events = telemetry.get_cached_events(limit=10)
    print(f"  ✓ Retrieved {len(recent_events)} events from cache")
    print()
    
    # Display events
    print("Recent events:")
    print("-" * 80)
    for event in recent_events[:5]:  # Show last 5
        print(f"[{event['timestamp']}] {event['event_type']}")
        if event.get('symbol'):
            print(f"  Symbol: {event['symbol']}")
        if event.get('data'):
            print(f"  Data: {event['data']}")
        print()
    
    # Get analytics
    print("Analytics metrics:")
    print("-" * 80)
    total_scans = telemetry.get_event_count(event_type=EventType.SCAN_COMPLETED)
    total_signals = telemetry.get_event_count(event_type=EventType.SIGNAL_GENERATED)
    total_rejected = telemetry.get_event_count(event_type=EventType.SIGNAL_REJECTED)
    
    print(f"  Total scans: {total_scans}")
    print(f"  Signals generated: {total_signals}")
    print(f"  Signals rejected: {total_rejected}")
    
    if total_signals + total_rejected > 0:
        success_rate = (total_signals / (total_signals + total_rejected)) * 100
        print(f"  Success rate: {success_rate:.1f}%")
    print()
    
    print("=" * 80)
    print("✅ TELEMETRY SYSTEM TEST COMPLETE")
    print("=" * 80)
    print()
    print("Next steps:")
    print("  1. Start API server: python -m backend.api_server")
    print("  2. Run a scan to see telemetry in action")
    print("  3. View telemetry at http://localhost:5173/bot/status")

if __name__ == "__main__":
    test_telemetry()
