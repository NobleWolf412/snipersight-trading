import sqlite3
import json

conn = sqlite3.connect('backend/cache/telemetry.db')
c = conn.cursor()

# Get gate failures
c.execute("""
    SELECT data_json 
    FROM telemetry_events 
    WHERE event_type='info_message' 
    ORDER BY id DESC 
    LIMIT 100
""")
rows = c.fetchall()

print("=== GATE FAILURES ===\n")
count = 0
for r in rows:
    data = json.loads(r[0])
    msg = data.get('message', '')
    if 'GATE_FAIL' in msg:
        payload = data.get('payload', {})
        symbol = payload.get('symbol', 'Unknown')
        reason = payload.get('reason', 'No reason')
        gate = payload.get('gate', 'unknown')
        
        print(f"{symbol}:")
        print(f"  Gate: {gate}")
        print(f"  Reason: {reason}")
        count += 1
        
        if count >= 10:
            break

print(f"\nTotal gate failures found: {count}")
conn.close()
