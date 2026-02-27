# -*- coding: utf-8 -*-
import sqlite3
import json
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('backend/cache/telemetry.db')
cursor = conn.cursor()

# Find WIF signal from the most recent scan
query = """
SELECT event_type, timestamp, symbol, data_json 
FROM telemetry_events 
WHERE symbol LIKE '%WIF%' OR data_json LIKE '%WIF%'
ORDER BY timestamp DESC 
LIMIT 20
"""

results = cursor.execute(query).fetchall()

print("=" * 80)
print("WIF/USDT SIGNAL DETAILS")
print("=" * 80)

for event_type, ts, symbol, data_json_str in results:
    if data_json_str:
        data = json.loads(data_json_str)
        
        # Look for signal generated event
        if event_type == 'signal_generated' and 'WIF' in (symbol or ''):
            print(f"\n[SIGNAL] WIF/USDT")
            print(f"Timestamp: {ts}")
            print(f"\nTrade Details:")
            for key, value in data.items():
                if key not in ['metadata', 'targets', 'entry_zone']:
                    print(f"  {key}: {value}")
            
            # Entry zone
            if 'entry_zone' in data:
                print(f"\nEntry Zone:")
                for key, value in data['entry_zone'].items():
                    print(f"  {key}: {value}")
            
            # Stop Loss
            if 'stop_loss' in data:
                print(f"\nStop Loss:")
                if isinstance(data['stop_loss'], dict):
                    for key, value in data['stop_loss'].items():
                        print(f"  {key}: {value}")
                else:
                    print(f"  level: {data['stop_loss']}")
            
            # Targets
            if 'targets' in data:
                print(f"\nTargets:")
                for i, target in enumerate(data['targets'], 1):
                    if isinstance(target, dict):
                        print(f"  TP{i}: {target.get('level', 'N/A')} ({target.get('percentage', 0)}%) - {target.get('rationale', '')}")
                    else:
                        print(f"  TP{i}: {target}")
            
            # Metadata
            if 'metadata' in data:
                print(f"\nMetadata:")
                meta = data['metadata']
                if isinstance(meta, dict):
                    for key, value in meta.items():
                        if key not in ['entry_structure', 'structure_tfs_used']:
                            print(f"  {key}: {value}")
            
            break

conn.close()
print("\n" + "=" * 80)
