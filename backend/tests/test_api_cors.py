from fastapi.testclient import TestClient

from app.api.main import app


def test_cors_allows_configured_frontend_origin():
    client = TestClient(app)
    response = client.get(
        "/api/route-restaurants",
        params={"origin": "not-a-coordinate", "destination": "37.6,127.1"},
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_rejects_unconfigured_origin():
    client = TestClient(app)
    response = client.get(
        "/api/route-restaurants",
        params={"origin": "not-a-coordinate", "destination": "37.6,127.1"},
        headers={"Origin": "http://evil.example.com"},
    )
    assert "access-control-allow-origin" not in response.headers
