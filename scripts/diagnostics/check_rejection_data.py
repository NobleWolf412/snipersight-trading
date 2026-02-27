"""Check what rejection data is being returned for tied confluences"""
import sqlite3
import json

conn = sqlite3.connect('backend/cache/telemetry.db')
c = conn.cursor()

# Get recent scan rejections
c.execute("""
    SELECT event_type, data_json
    FROM telemetry_events 
    WHERE data_json LIKE '%directional edge%'
       OR data_json LIKE '%Conflicting signals%'
    ORDER BY id DESC 
    LIMIT 5
""")

rows = c.fetchall()

print("=== DIRECTIONAL EDGE REJECTIONS ===\n")
for event_type, data_json in rows:
    data = json.loads(data_json)
    payload = data.get('payload', {})
    
    print(f"Type: {event_type}")
    print(f"Symbol: {payload.get('symbol', 'N/A')}")
    
    # Check for factors
    if 'bullish_factors' in payload:
        print(f"✅ bullish_factors: {len(payload['bullish_factors'])} items")
    else:
        print("❌ bullish_factors: MISSING")
        
    if 'bearish_factors' in payload:
        print(f"✅ bearish_factors: {len(payload['bearish_factors'])} items")
    else:
        print("❌ bearish_factors: MISSING")
    
    if payload.get('bullish_score'):
        print(f"  Bullish Score: {payload['bullish_score']}")
    if payload.get('bearish_score'):
        print(f"  Bearish Score: {payload['bearish_score']}")
    
    print("-" * 50)

conn.close()
