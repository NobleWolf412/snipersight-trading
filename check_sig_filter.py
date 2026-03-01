import urllib.request, json
data = json.loads(urllib.request.urlopen('http://localhost:8001/api/paper-trading/activity?limit=50').read().decode('utf-8'))
filtered = [a for a in data['activity'] if a['event_type'] == 'signal_filtered']
print([f"{a['data']['symbol']} {a['data']['reason']}" for a in filtered])
