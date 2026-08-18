from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_public_200():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_app_boots_with_routes():
    assert client.get("/health").status_code == 200
    assert client.get("/api/tasks").status_code == 401


def test_api_tasks_requires_auth():
    resp = client.get("/api/tasks")
    assert resp.status_code == 401
