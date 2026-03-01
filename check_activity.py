import json, urllib.request; data = json.loads(urllib.request.urlopen('http://localhost:8001/api/paper-trading/activity?limit=20').read().decode('utf-8')); print(json.dumps(data, indent=2))
