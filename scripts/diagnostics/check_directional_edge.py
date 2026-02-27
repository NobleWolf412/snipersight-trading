"""
Diagnostic script to find "No directional edge" rejections
"""
import sqlite3
import json

conn = sqlite3.connect('backend/cache/telemetry.db')
c = conn.cursor()

# Search for directional edge events
c.execute("""
    SELECT event_type, data_json 
    FROM telemetry_events 
    WHERE data_json LIKE '%directional edge%' 
    ORDER BY id DESC 
    LIMIT 10
""")
rows = c.fetchall()

print("=== 'Directional Edge' TELEMETRY EVENTS ===\n")
for event_type, data_json in rows:
    data = json.loads(data_json)
    print(f"Event Type: {event_type}")
    print(f"Data: {json.dumps(data, indent=2)}")
    print("-" * 50)

if not rows:
    print("No directional edge events found.")
    print("\n\nSearching for confluence rejection events...")
    c.execute("""
        SELECT event_type, data_json 
        FROM telemetry_events 
        WHERE data_json LIKE '%confluence%' AND data_json LIKE '%reject%'
        ORDER BY id DESC 
        LIMIT 5
    """)
    rows2 = c.fetchall()
    for event_type, data_json in rows2:
        data = json.loads(data_json)
        print(f"\nEvent Type: {event_type}")
        print(f"Data: {json.dumps(data, indent=2)[:1500]}")

conn.close()
