"""Check ENSO rejection details in telemetry"""
import sqlite3
import json

conn = sqlite3.connect('backend/cache/telemetry.db')
c = conn.cursor()

# Get any ENSO-related events
c.execute("""
    SELECT id, event_type, data_json
    FROM telemetry_events 
    WHERE data_json LIKE '%ENSO%'
    ORDER BY id DESC 
    LIMIT 10
""")

rows = c.fetchall()

print("=== ENSO TELEMETRY EVENTS ===\n")
for id, event_type, data_json in rows:
    data = json.loads(data_json)
    payload = data.get('payload', {})
    msg = data.get('message', '')
    
    print(f"ID {id} | {event_type}")
    if msg:
        print(f"  Message: {msg}")
    
    # Check for factors
    if 'bullish_factors' in payload:
        print(f"  BULLISH FACTORS: {len(payload['bullish_factors'])} items")
        if payload['bullish_factors']:
            for f in payload['bullish_factors'][:3]:
                print(f"    - {f.get('name', 'N/A')}: {f.get('score', 0)}")
    
    if 'bearish_factors' in payload:
        print(f"  BEARISH FACTORS: {len(payload['bearish_factors'])} items")
        if payload['bearish_factors']:
            for f in payload['bearish_factors'][:3]:
                print(f"    - {f.get('name', 'N/A')}: {f.get('score', 0)}")
    
    if payload.get('bullish_score') is not None:
        print(f"  Bullish Score: {payload['bullish_score']}")
    if payload.get('bearish_score') is not None:
        print(f"  Bearish Score: {payload['bearish_score']}")
    if payload.get('gap') is not None:
        print(f"  Gap: {payload['gap']}")
    
    print("-" * 60)

conn.close()
