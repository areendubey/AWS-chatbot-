"""
Tests for /health/live and /health/ready endpoints.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_live_endpoint():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_health_ready_endpoint():
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "details" in data
    assert data["details"]["database"] == "reachable"
