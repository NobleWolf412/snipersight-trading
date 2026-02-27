"""
Diagnostic script to find ENSO rejection details in telemetry
"""
import sqlite3
import json

conn = sqlite3.connect('backend/cache/telemetry.db')
c = conn.cursor()

# Search for ENSO-related events
c.execute("""
    SELECT event_type, data_json 
    FROM telemetry_events 
    WHERE data_json LIKE '%ENSO%' 
    ORDER BY id DESC 
    LIMIT 20
""")
rows = c.fetchall()

print("=== ENSO TELEMETRY EVENTS ===\n")
for event_type, data_json in rows:
    data = json.loads(data_json)
    print(f"Event Type: {event_type}")
    print(f"Data: {json.dumps(data, indent=2)[:1000]}")
    print("-" * 50)

conn.close()
