"""Query telemetry database for BNB rejection details"""
import sqlite3
import json

conn = sqlite3.connect('backend/cache/telemetry.db')
c = conn.cursor()

# Get most recent BNB rejections
c.execute("""
    SELECT data_json 
    FROM telemetry_events 
    WHERE event_type='signal_rejected'  
      AND data_json LIKE '%BNB%'
    ORDER BY id DESC 
    LIMIT 3
""")

rows = c.fetchall()

print("=== BNB REJECTION DETAILS ===\n")
for i, row in enumerate(rows, 1):
    data = json.loads(row[0])
    print(f"Rejection #{i}:")
    print(f"  Symbol: {data.get('payload', {}).get('symbol', 'N/A')}")
    print(f"  Reason: {data.get('payload', {}).get('reason', 'N/A')}")
    print(f"  Gate: {data.get('payload', {}).get('gate_name', 'N/A')}")
    
    # Check for diagnostics
    diag = data.get('payload', {}).get('diagnostics', {})
    if diag:
        print(f"  Diagnostics:")
        for k, v in diag.items():
            print(f"    - {k}: {v}")
    print()

conn.close()
