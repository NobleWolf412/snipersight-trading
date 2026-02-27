"""Analyze most recent Strike scan for errors and red flags"""
import sqlite3
import json

conn = sqlite3.connect('backend/cache/telemetry.db')
c = conn.cursor()

# Get most recent scan START event
c.execute("""
    SELECT id, data_json
    FROM telemetry_events 
    WHERE event_type='info_message' 
      AND data_json LIKE '%"stage": "START"%'
    ORDER BY id DESC 
    LIMIT 1
""")

row = c.fetchone()
if not row:
    print("No recent scan found")
    exit()

start_id, start_data = row
start_payload = json.loads(start_data).get('payload', {})

print("=== STRIKE SCAN ANALYSIS ===\n")
print(f"Scan ID: {start_payload.get('run_id', 'Unknown')}")
print(f"Mode: {start_payload.get('mode', 'Unknown')}")
print(f"Symbols: {len(start_payload.get('symbols', []))}")
print(f"Gates:")
print(f"  - Min Confluence: {start_payload.get('gates', {}).get('confluence_min', 'N/A')}%")
print(f"  - Min R:R: {start_payload.get('gates', {}).get('min_rr_ratio', 'N/A')}:1")
print()

# Get all events from this scan
c.execute("""
    SELECT event_type, data_json
    FROM telemetry_events 
    WHERE id >= ?
    ORDER BY id ASC
""", (start_id,))

rows = c.fetchall()

# Analyze scan
errors = []
warnings = []
gate_fails = {}
signals_generated = []
completed = False

for event_type, data_json in rows:
    data = json.loads(data_json)
    msg = data.get('message', '')
    payload = data.get('payload', {})
    
    # Check for errors
    if event_type == 'error':
        errors.append({
            'symbol': payload.get('symbol', 'System'),
            'error': payload.get('error_message', 'Unknown error'),
            'type': payload.get('error_type', 'Unknown')
        })
    
    # Check for GATE_FAIL events
    if 'GATE_FAIL' in msg:
        gate = payload.get('gate', 'unknown')
        symbol = payload.get('symbol', 'Unknown')
        if gate not in gate_fails:
            gate_fails[gate] = []
        gate_fails[gate].append(symbol)
    
    # Check for signals generated
    if event_type == 'signal_generated':
        signals_generated.append({
            'symbol': payload.get('symbol'),
            'direction': payload.get('direction'),
            'confidence': payload.get('confidence_score', 0),
            'rr': payload.get('risk_reward', 0)
        })
    
    # Check for completion
    if msg == 'Pipeline progress: COMPLETE':
        completed = True

print("=" * 60)
print("HEALTH CHECK")
print("=" * 60)

# Report errors
if errors:
    print(f"\n🚨 ERRORS FOUND: {len(errors)}")
    for err in errors:
        print(f"  - {err['symbol']}: {err['type']} - {err['error']}")
else:
    print("\n✅ No errors detected")

# Report gate failures
if gate_fails:
    print(f"\n📊 Gate Failure Breakdown:")
    for gate, symbols in gate_fails.items():
        print(f"  - {gate}: {len(symbols)} symbols")
        if len(symbols) <= 3:
            print(f"    ({', '.join(symbols)})")
else:
    print("\n✅ No gate failures (all symbols passed)")

# Report signals
if signals_generated:
    print(f"\n✅ SIGNALS GENERATED: {len(signals_generated)}")
    for sig in signals_generated:
        print(f"  - {sig['symbol']} {sig['direction']}: {sig['confidence']:.1f}% confidence, {sig['rr']:.2f}R")
else:
    print("\n⚠️  No signals generated")

# Check completion
if completed:
    print(f"\n✅ Scan completed successfully")
else:
    print(f"\n⚠️  Scan may not have completed (no COMPLETE event found)")

print("\n" + "=" * 60)
print("VERDICT")
print("=" * 60)

if errors:
    print("🔴 RED FLAG: Errors detected during scan")
elif not completed:
    print("🟡 YELLOW FLAG: Scan completion unclear")
elif not signals_generated and not gate_fails:
    print("🟡 YELLOW FLAG: No signals and no rejections - possible issue")
else:
    print("🟢 GREEN: Scan completed without errors")

conn.close()
