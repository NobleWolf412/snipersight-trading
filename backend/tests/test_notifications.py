from fastapi.testclient import TestClient
from backend.api_server import app

client = TestClient(app)


def test_notifications_flow():
    # Initially empty list
    r = client.get("/api/notifications")
    assert r.status_code == 200
    data = r.json()
    assert "notifications" in data
    initial_count = len(data["notifications"])

    payload = {
        "type": "signal",
        "priority": "high",
        "title": "Test Trade Signal",
        "message": "High probability setup detected.",
        "data": {"symbol": "BTCUSDT", "confidence": 0.9},
    }
    r2 = client.post("/api/notifications/send", json=payload)
    assert r2.status_code == 200, r2.text
    created = r2.json()
    # Endpoint returns wrapper with 'notification' nested
    assert "notification" in created
    nested = created["notification"]
    # Title is dynamically generated; ensure it's a non-empty string containing symbol
    assert isinstance(nested.get("title"), str) and nested["title"]
    assert "BTCUSDT" in nested["title"]
    assert nested.get("priority") == payload["priority"]
    assert nested.get("type") == payload["type"]

    r3 = client.get("/api/notifications")
    assert r3.status_code == 200
    data2 = r3.json()
    assert len(data2["notifications"]) == initial_count + 1
    # Most recent should be first (assuming append order)
    titles = [n.get("title") for n in data2["notifications"]]
    assert any("BTCUSDT" in (t or "") for t in titles)
