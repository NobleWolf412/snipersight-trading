"""Get detailed Strike scan results"""
import sqlite3
import json

conn = sqlite3.connect('backend/cache/telemetry.db')
c = conn.cursor()

# Get Strike scan signals
c.execute("""
    SELECT data_json
    FROM telemetry_events 
    WHERE event_type='signal_generated'
      AND id > (
          SELECT MAX(id) FROM telemetry_events 
          WHERE data_json LIKE '%"mode": "strike"%'
      )
    ORDER BY id DESC
    LIMIT 10
""")

rows = c.fetchall()

print("=== STRIKE SCAN SIGNALS ===\n")
print(f"Total Signals: {len(rows)}\n")

if rows:
    for i, row in enumerate(rows, 1):
        data = json.loads(row[0])
        p = data.get('payload', {})
        
        print(f"#{i}: {p.get('symbol', 'Unknown')}")
        print(f"  Direction: {p.get('direction', 'N/A')}")
        print(f"  Confidence: {p.get('confidence_score', 0):.2f}%")
        print(f"  Risk:Reward: {p.get('risk_reward', 0):.2f}:1")
        print(f"  Trade Type: {p.get('trade_type', 'N/A')}")
        
        # Entry/Stop/Targets if available
        entry = p.get('entry_zone', {})
        if entry:
            print(f"  Entry: ${entry.get('near_entry', 0):.2f} - ${entry.get('far_entry', 0):.2f}")
        
        stop = p.get('stop_loss', {})
        if stop and isinstance(stop, dict):
            print(f"  Stop: ${stop.get('level', 0):.2f}")
        
        targets = p.get('targets', [])
        if targets:
            print(f"  Targets: {len(targets)} levels")
            if len(targets) <= 3:
                for j, t in enumerate(targets, 1):
                    if isinstance(t, dict):
                        print(f"    TP{j}: ${t.get('level', 0):.2f}")
        
        print()

# Get confluence scores for the Strike scan
print("\n=== CONFLUENCE SCORES ===\n")
c.execute("""
    SELECT data_json
    FROM telemetry_events 
    WHERE event_type='info_message'
      AND data_json LIKE '%CONFLUENCE%'
      AND id > (
          SELECT MAX(id) FROM telemetry_events 
          WHERE data_json LIKE '%"mode": "strike"%'
      )
    ORDER BY id DESC
    LIMIT 15
""")

rows = c.fetchall()
scores = []
for row in rows:
    data = json.loads(row[0])
    p = data.get('payload', {})
    if p.get('score'):
        scores.append({
            'symbol': p.get('symbol', 'Unknown'),
            'direction': p.get('direction', 'N/A'),
            'score': p.get('score', 0)
        })

if scores:
    print(f"{'Symbol':<20} {'Direction':<10} {'Score':<10} {'vs 70%'}")
    print("-" * 55)
    for s in scores[:10]:
        passed = "PASS" if s['score'] >= 70.0 else "FAIL"
        diff = s['score'] - 70.0
        print(f"{s['symbol']:<20} {s['direction']:<10} {s['score']:>6.2f}%    {passed} ({diff:+.2f})")

conn.close()
