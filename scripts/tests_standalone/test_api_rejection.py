"""Test API response to verify rejection factors are included"""
import requests
import json
import time

# Start a scan
print("Starting scan...")
r = requests.post('http://localhost:8001/api/scanner/runs', params={
    'limit': 3,
    'min_score': 70,
    'sniper_mode': 'strike',
    'majors': True,
    'altcoins': True,
    'exchange': 'phemex',
    'leverage': 8,
})
data = r.json()
run_id = data.get('run_id')
print(f"Scan started: {run_id}")

# Poll for completion
for i in range(60):
    time.sleep(5)
    r = requests.get(f'http://localhost:8001/api/scanner/runs/{run_id}')
    result = r.json()
    status = result.get('status')
    print(f"  [{i*5}s] Status: {status}")
    if status in ['completed', 'failed']:
        break

# Check the rejections
print("\n=== REJECTION ANALYSIS ===")
rejections = result.get('rejections', {})
details = rejections.get('details', {})
low_confluence = details.get('low_confluence', [])

print(f"Total low_confluence rejections: {len(low_confluence)}")

for rej in low_confluence[:3]:
    symbol = rej.get('symbol')
    keys = list(rej.keys())
    bull_factors = rej.get('bullish_factors', [])
    bear_factors = rej.get('bearish_factors', [])
    print(f"\n{symbol}:")
    print(f"  Keys: {keys}")
    print(f"  Bullish factors: {len(bull_factors)}")
    print(f"  Bearish factors: {len(bear_factors)}")
    if bull_factors:
        print(f"    First: {bull_factors[0].get('name')} = {bull_factors[0].get('score')}")
