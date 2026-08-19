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


def test_health_503_when_db_down(db_engine, monkeypatch):
    import app.db as db_module

    class _BrokenEngine:
        def connect(self):
            raise ConnectionError("db down")

    monkeypatch.setattr(db_module, "engine", _BrokenEngine())
    monkeypatch.setattr("app.main.engine", _BrokenEngine())
    resp = client.get("/health")
    assert resp.status_code == 503
