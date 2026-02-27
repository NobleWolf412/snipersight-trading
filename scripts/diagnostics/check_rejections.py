import sqlite3
import json

conn = sqlite3.connect('backend/cache/telemetry.db')
c = conn.cursor()

# Get all events for this run
c.execute("SELECT event_type, symbol, data_json FROM telemetry_events WHERE run_id='4cb0d791' OR (run_id IS NULL AND timestamp > '2026-01-21T01:50:00') ORDER BY id ASC")
rows = c.fetchall()

print(f"Total events found: {len(rows)}\n")

for event_type, symbol, data_json in rows:
    data = json.loads(data_json)
    
    if event_type == 'signal_rejected':
        print(f"\n[REJECTED] {symbol}:")
        print(f"  Reason: {data.get('reason')}")
        diag = data.get('diagnostics', {})
        if diag:
            for k, v in diag.items():
                print(f"    {k}: {v}")
    
    elif event_type == 'info_message':
        msg = data.get('message', '')
        if 'GATE_FAIL' in msg or 'error' in msg.lower() or 'exception' in msg.lower():
            print(f"\n[ERROR/GATE_FAIL]")
            print(f"  Message: {msg}")
            payload = data.get('payload', {})
            if payload:
                print(f"  Payload:")
                for k, v in payload.items():
                    print(f"    {k}: {v}")

conn.close()
