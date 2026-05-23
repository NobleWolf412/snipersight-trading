import urllib.request, json
try:
    data = json.loads(urllib.request.urlopen('http://localhost:8001/api/scanner/diagnostics').read().decode('utf-8'))
    print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Error: {e}")
