import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import SessionLocal, get_db
from app.routers import tasks

TOKEN = Settings().auth_token
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def client(db_engine, clean_tables):
    app = FastAPI()

    def override_get_db():
        with SessionLocal() as session:
            yield session

    app.include_router(tasks.router)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c


def _create(client, title="Task", **kwargs):
    resp = client.post("/api/tasks", json={"title": title, **kwargs}, headers=AUTH)
    assert resp.status_code == 201
    return resp.json()


def test_router_requires_token(client, clean_tables):
    resp = client.get("/api/tasks")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid or missing token"}


def test_create_task_returns_201_with_defaults(client, clean_tables):
    resp = client.post("/api/tasks", json={"title": "Buy milk"}, headers=AUTH)
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == 1
    assert body["title"] == "Buy milk"
    assert body["description"] is None
    assert body["status"] == "todo"
    assert body["priority"] == "medium"
    assert body["created_at"] is not None
    assert body["updated_at"] is not None


def test_list_returns_newest_first(client, clean_tables):
    _create(client, "first")
    _create(client, "second")
    _create(client, "third")
    resp = client.get("/api/tasks", headers=AUTH)
    assert resp.status_code == 200
    assert [t["title"] for t in resp.json()] == ["third", "second", "first"]


def test_list_status_filter(client, clean_tables):
    _create(client, "todo task")
    _create(client, "done task", status="done")
    _create(client, "progress task", status="in_progress")
    resp = client.get("/api/tasks", params={"status": "done"}, headers=AUTH)
    assert resp.status_code == 200
    assert [t["title"] for t in resp.json()] == ["done task"]


def test_list_invalid_status_422(client, clean_tables):
    resp = client.get("/api/tasks", params={"status": "urgent"}, headers=AUTH)
    assert resp.status_code == 422


def test_get_task_200(client, clean_tables):
    task = _create(client, "hello")
    resp = client.get(f"/api/tasks/{task['id']}", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == task


def test_get_unknown_task_404(client, clean_tables):
    resp = client.get("/api/tasks/999", headers=AUTH)
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Task not found"}


def test_put_replaces_fields(client, clean_tables):
    task = _create(client, "old")
    resp = client.put(
        f"/api/tasks/{task['id']}",
        json={
            "title": "new",
            "description": "desc",
            "status": "done",
            "priority": "high",
        },
        headers=AUTH,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == task["id"]
    assert body["title"] == "new"
    assert body["description"] == "desc"
    assert body["status"] == "done"
    assert body["priority"] == "high"


def test_put_unknown_404(client, clean_tables):
    resp = client.put("/api/tasks/999", json={"title": "x"}, headers=AUTH)
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Task not found"}


def test_patch_status_only(client, clean_tables):
    task = _create(client, "t", description="keep", priority="low")
    resp = client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}, headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == task["id"]
    assert body["status"] == "done"
    assert body["title"] == "t"
    assert body["description"] == "keep"
    assert body["priority"] == "low"
    assert body["created_at"] == task["created_at"]


def test_patch_unknown_404(client, clean_tables):
    resp = client.patch("/api/tasks/999", json={"status": "done"}, headers=AUTH)
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Task not found"}


def test_patch_null_status_422(client, clean_tables):
    task = _create(client, "t")
    resp = client.patch(f"/api/tasks/{task['id']}", json={"status": None}, headers=AUTH)
    assert resp.status_code == 422


def test_delete_204_and_second_delete_404(client, clean_tables):
    task = _create(client, "t")
    resp = client.delete(f"/api/tasks/{task['id']}", headers=AUTH)
    assert resp.status_code == 204
    assert resp.content == b""
    resp2 = client.delete(f"/api/tasks/{task['id']}", headers=AUTH)
    assert resp2.status_code == 404
    assert resp2.json() == {"detail": "Task not found"}


def test_create_missing_title_422(client, clean_tables):
    resp = client.post("/api/tasks", json={}, headers=AUTH)
    assert resp.status_code == 422


def test_create_invalid_status_422(client, clean_tables):
    resp = client.post("/api/tasks", json={"title": "x", "status": "urgent"}, headers=AUTH)
    assert resp.status_code == 422


def test_put_invalid_priority_422(client, clean_tables):
    resp = client.put("/api/tasks/1", json={"priority": "critical"}, headers=AUTH)
    assert resp.status_code == 422