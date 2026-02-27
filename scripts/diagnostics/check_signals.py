"""Check if BNB generated a signal"""
import sqlite3
import json

conn = sqlite3.connect('backend/cache/telemetry.db')
c = conn.cursor()

# Get most recent scan_completed event
c.execute("""
    SELECT data_json 
    FROM telemetry_events 
    WHERE event_type='scan_completed'
    ORDER BY id DESC 
    LIMIT 1
""")

row = c.fetchone()
if row:
    data = json.loads(row[0])
    payload = data.get('payload', {})
    print("=== MOST RECENT SCAN RESULTS ===\n")
    print(f"Signals Generated: {payload.get('signals_generated', 0)}")
    print(f"Signals Rejected: {payload.get('signals_rejected', 0)}")
    print(f"Duration: {payload.get('duration_seconds', 0):.1f}s")
else:
    print("No scan_completed events found")

# Check for signal_generated events
c.execute("""
    SELECT data_json 
    FROM telemetry_events 
    WHERE event_type='signal_generated'
    ORDER BY id DESC 
    LIMIT 5
""")

rows = c.fetchall()
if rows:
    print("\n=== RECENT SIGNALS ===\n")
    for row in rows:
        data = json.loads(row[0])
        payload = data.get('payload', {})
        print(f"Symbol: {payload.get('symbol')}")
        print(f"Direction: {payload.get('direction')}")
        print(f"Confidence: {payload.get('confidence_score', 0):.1f}%")
        print(f"R:R: {payload.get('risk_reward', 0):.2f}:1")
        print("-" * 40)
else:
    print("\nNo signal_generated events found")

conn.close()
