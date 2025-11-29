from fastapi.testclient import TestClient
from backend.api_server import app


client = TestClient(app)


def test_scanner_pairs_endpoint_basic():
    resp = client.get(
        "/api/scanner/pairs",
        params={
            "limit": 10,
            "majors": True,
            "altcoins": True,
            "meme_mode": False,
            "exchange": "phemex",
            "leverage": 10,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["exchange"] == "phemex"
    assert isinstance(data["symbols"], list)
    assert len(data["symbols"]) <= 10


def test_scanner_pairs_unsupported_exchange():
    resp = client.get(
        "/api/scanner/pairs",
        params={"exchange": "unsupported", "limit": 5},
    )
    assert resp.status_code == 400
