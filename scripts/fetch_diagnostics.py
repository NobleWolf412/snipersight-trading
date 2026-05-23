import urllib.request
import json
import traceback

try:
    with urllib.request.urlopen("http://127.0.0.1:8001/api/scanner/diagnostics") as response:
        data = json.loads(response.read().decode())
        print(json.dumps(data, indent=2))
except Exception as e:
    traceback.print_exc()
