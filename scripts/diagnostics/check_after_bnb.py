"""Check for GATE_FAIL events after BNB passing"""
import sqlite3
import json

conn = sqlite3.connect('backend/cache/telemetry.db')
c = conn.cursor()

# Get events after ID 1655 (where BNB passed risk_validation)
c.execute("""
    SELECT id, event_type, data_json
    FROM telemetry_events 
    WHERE id > 1655
    ORDER BY id ASC
    LIMIT 20
""")

rows = c.fetchall()

print("=== EVENTS AFTER BNB RISK PASS (ID 1655) ===\n")
for id, event_type, data_json in rows:
    data = json.loads(data_json)
    msg = data.get('message',  '')
    payload = data.get('payload', {})
    
    # Show all GATE_FAIL and relevant events
    if 'GATE_FAIL' in msg or 'COMPLETE' in msg or event_type == 'signal_generated':
        print(f"ID {id} | {event_type}")
        print(f"  Message: {msg}")
        if payload.get('symbol'):
            print(f"  Symbol: {payload['symbol']}")
        if payload.get('gate'):
            print(f"  Gate: {payload['gate']}")
        if payload.get('reason'):
            print(f"  Reason: {payload['reason']}")
        print()

conn.close()
