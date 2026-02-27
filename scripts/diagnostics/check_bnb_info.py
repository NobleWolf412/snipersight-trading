"""
Check BNB info_message events for GATE_FAIL details
"""
import sqlite3
import json

conn = sqlite3.connect('backend/cache/telemetry.db')
c = conn.cursor()

# Get most recent BNB info_message events
c.execute("""
    SELECT id, data_json
    FROM telemetry_events 
    WHERE event_type = 'info_message'
      AND data_json LIKE '%BNB%'
    ORDER BY id DESC 
    LIMIT 10
""")

rows = c.fetchall()

print("=== BNB INFO MESSAGES ===\n")
for id, data_json in rows:
    data = json.loads(data_json)
    msg = data.get('message', '')
    payload = data.get('payload', {})
    
    print(f"ID {id}:")
    print(f"  Message: {msg}")
    if payload:
        print(f"  Payload:")
        for k, v in payload.items():
            if isinstance(v, (dict, list)):
                print(f"    {k}: {json.dumps(v, indent=6)}")
            else:
                print(f"    {k}: {v}")
    print("-" * 70)

conn.close()
