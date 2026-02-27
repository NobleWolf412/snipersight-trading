# -*- coding: utf-8 -*-
import sqlite3
import json
import sys
from datetime import datetime

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('backend/cache/telemetry.db')
cursor = conn.cursor()

# Get the most recent scan run_id
print("=" * 80)
print("SCAN DETAILS - Latest Scan Results")
print("=" * 80)

# Find the most recent completed scan
scan_query = """
SELECT run_id, timestamp, data_json 
FROM telemetry_events 
WHERE event_type = 'scan_completed' 
ORDER BY timestamp DESC 
LIMIT 1
"""

scan_result = cursor.execute(scan_query).fetchone()
if not scan_result:
    print("No scan results found.")
    conn.close()
    exit()

run_id, timestamp,data_json = scan_result
scan_data = json.loads(data_json)

print(f"\n[SCAN] ID: {run_id}")
print(f"[TIME] Completed: {timestamp}")
print(f"[STATS] Symbols Scanned: {scan_data.get('symbols_scanned', 'N/A')}")
print(f"[STATS] Signals Generated: {scan_data.get('signals_generated', 'N/A')}")
print(f"[STATS] Signals Rejected: {scan_data.get('signals_rejected', 'N/A')}")
print(f"[STATS] Duration: {scan_data.get('duration_seconds', 0):.2f} seconds")

# Get all events for this scan run
print("\n" + "=" * 80)
print("DETAILED SCAN PROGRESSION")
print("=" * 80)

events_query = """
SELECT event_type, timestamp, symbol, data_json 
FROM telemetry_events 
WHERE run_id = ? OR data_json LIKE ?
ORDER BY timestamp ASC
"""

events = cursor.execute(events_query, (run_id, f'%{run_id}%')).fetchall()

signals_passed = []
signals_rejected = []

for event_type, ts, symbol, data_json_str in events:
    data = json.loads(data_json_str) if data_json_str else {}
    
    if event_type == 'info_message':
        stage = data.get('stage', '')
        message = data.get('message', '')
        payload = data.get('payload', {})
        
        if stage == 'PASS':
            symbol_name = payload.get('symbol', symbol)
            stage_name = payload.get('stage', 'unknown')
            if symbol_name:
                print(f"[PASS] {symbol_name} - PASSED {stage_name}")
                if symbol_name not in [s['symbol'] for s in signals_passed]:
                    signals_passed.append({'symbol': symbol_name, 'stage': stage_name})
        
        elif stage == 'REJECT':
            symbol_name = payload.get('symbol', symbol)
            reason = payload.get('reason', 'unknown')
            stage_name = payload.get('stage', 'unknown')
            if symbol_name:
                print(f"[REJECT] {symbol_name} - REJECTED at {stage_name}: {reason}")
                signals_rejected.append({
                    'symbol': symbol_name, 
                    'stage': stage_name,
                    'reason': reason
                })
    
    elif event_type == 'signal_generated' and symbol:
        print(f"\n[SIGNAL] GENERATED: {symbol}")
        if 'entry_price' in data:
            print(f"   Entry: ${data['entry_price']}")
        if 'direction' in data:
            print(f"   Direction: {data['direction'].upper()}")
        if 'confluence_score' in data:
            print(f"   Confluence Score: {data['confluence_score']:.1f}")

# Summary of unique symbols
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"\n[PASSED] Signals Passed ({len(signals_passed)}):")
for sig in signals_passed:
    print(f"   - {sig['symbol']}")

if signals_rejected:
    print(f"\n[REJECTED] Signals Rejected ({len(signals_rejected)}):")
    rejection_reasons = {}
    for sig in signals_rejected:
        reason = sig['reason']
        if reason not in rejection_reasons:
            rejection_reasons[reason] = []
        rejection_reasons[reason].append(sig['symbol'])
    
    for reason, symbols in rejection_reasons.items():
        print(f"\n   {reason} ({len(symbols)} symbols):")
        for sym in symbols[:5]:  # Show first 5
            print(f"      - {sym}")
        if len(symbols) > 5:
            print(f"      ... and {len(symbols) - 5} more")

conn.close()
print("\n" + "=" * 80)
