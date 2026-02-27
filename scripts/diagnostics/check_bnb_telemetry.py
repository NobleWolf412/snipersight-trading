"""
Query telemetry for detailed BNB rejection with new logging
"""
import sqlite3
import json

conn = sqlite3.connect('backend/cache/telemetry.db')
c = conn.cursor()

# Get most recent events (last 30)
c.execute("""
    SELECT id, event_type, data_json
    FROM telemetry_events 
    ORDER BY id DESC 
    LIMIT 30
""")

rows = c.fetchall()

print("=== RECENT TELEMETRY EVENTS ===\n")
bnb_found = False
for id, event_type, data_json in rows:
    data = json.loads(data_json)
    payload = data.get('payload', {})
    
    # Check if BNB-related
    if 'BNB' in str(payload.get('symbol', '')):
        bnb_found = True
        print(f"ID: {id} | Type: {event_type}")
        print(f"Symbol: {payload.get('symbol')}")
        print(f"Reason: {payload.get('reason', 'N/A')}")
        print(f"Gate: {payload.get('gate_name', 'N/A')}")
        
        diag = payload.get('diagnostics', {})
        if diag:
            print("Diagnostics:")
            for k, v in diag.items():
                print(f"  {k}: {v}")
        print("-" * 60)

if not bnb_found:
    print("No BNB rejections found in last 30 events")
    print("\nShowing all rejection events:")
    for id, event_type, data_json in rows:
        if event_type == 'signal_rejected':
            data = json.loads(data_json)
            payload = data.get('payload', {})
            print(f"  {payload.get('symbol', 'Unknown')}: {payload.get('reason', 'No reason')}")

conn.close()
