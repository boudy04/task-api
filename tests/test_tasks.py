from datetime import datetime, timezone


def _create(client, auth, title="Task", **kwargs):
    resp = client.post("/api/tasks", json={"title": title, **kwargs}, headers=auth)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_router_requires_token(client):
    resp = client.get("/api/tasks")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Not authenticated"}


def test_create_task_returns_201_with_defaults(client, auth):
    resp = client.post("/api/tasks", json={"title": "Buy milk"}, headers=auth)
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == 1
    assert body["title"] == "Buy milk"
    assert body["description"] is None
    assert body["status"] == "todo"
    assert body["priority"] == "medium"
    assert body["due_at"] is None
    assert body["tags"] == []
    assert body["updated_at"] is not None


def test_list_returns_newest_first(client, auth):
    _create(client, auth, "first")
    _create(client, auth, "second")
    _create(client, auth, "third")
    resp = client.get("/api/tasks", headers=auth)
    assert resp.status_code == 200
    assert [t["title"] for t in resp.json()] == ["third", "second", "first"]


def test_list_status_filter(client, auth):
    _create(client, auth, "todo task")
    _create(client, auth, "done task", status="done")
    _create(client, auth, "progress task", status="in_progress")
    resp = client.get("/api/tasks", params={"status": "done"}, headers=auth)
    assert resp.status_code == 200
    assert [t["title"] for t in resp.json()] == ["done task"]


def test_list_invalid_status_422(client, auth):
    resp = client.get("/api/tasks", params={"status": "urgent"}, headers=auth)
    assert resp.status_code == 422


def test_get_task_200(client, auth):
    task = _create(client, auth, "hello")
    resp = client.get(f"/api/tasks/{task['id']}", headers=auth)
    assert resp.status_code == 200
    assert resp.json() == task


def test_get_unknown_task_404(client, auth):
    resp = client.get("/api/tasks/999", headers=auth)
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Task not found"}


def test_patch_status_only(client, auth):
    task = _create(client, auth, "t", description="keep", priority="low")
    resp = client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}, headers=auth)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == task["id"]
    assert body["status"] == "done"
    assert body["title"] == "t"
    assert body["description"] == "keep"
    assert body["priority"] == "low"
    assert body["created_at"] == task["created_at"]


def test_patch_unknown_404(client, auth):
    resp = client.patch("/api/tasks/999", json={"status": "done"}, headers=auth)
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Task not found"}


def test_patch_null_status_422(client, auth):
    task = _create(client, auth, "t")
    resp = client.patch(f"/api/tasks/{task['id']}", json={"status": None}, headers=auth)
    assert resp.status_code == 422


def test_patch_null_title_422(client, auth):
    task = _create(client, auth, "t")
    resp = client.patch(f"/api/tasks/{task['id']}", json={"title": None}, headers=auth)
    assert resp.status_code == 422


def test_out_of_range_task_id_422(client, auth):
    resp = client.get("/api/tasks/99999999999999999999", headers=auth)
    assert resp.status_code == 422


def test_delete_204_and_second_delete_404(client, auth):
    task = _create(client, auth, "t")
    resp = client.delete(f"/api/tasks/{task['id']}", headers=auth)
    assert resp.status_code == 204
    assert resp.content == b""
    resp2 = client.delete(f"/api/tasks/{task['id']}", headers=auth)
    assert resp2.status_code == 404
    assert resp2.json() == {"detail": "Task not found"}


def test_create_missing_title_422(client, auth):
    resp = client.post("/api/tasks", json={}, headers=auth)
    assert resp.status_code == 422


def test_create_empty_title_422(client, auth):
    resp = client.post("/api/tasks", json={"title": ""}, headers=auth)
    assert resp.status_code == 422


def test_create_whitespace_title_422(client, auth):
    resp = client.post("/api/tasks", json={"title": "   "}, headers=auth)
    assert resp.status_code == 422


def test_create_oversized_title_422(client, auth):
    resp = client.post("/api/tasks", json={"title": "a" * 201}, headers=auth)
    assert resp.status_code == 422


def test_patch_empty_title_422(client, auth):
    task = _create(client, auth, "t")
    resp = client.patch(f"/api/tasks/{task['id']}", json={"title": ""}, headers=auth)
    assert resp.status_code == 422


def test_create_invalid_status_422(client, auth):
    resp = client.post(
        "/api/tasks", json={"title": "x", "status": "urgent"}, headers=auth
    )
    assert resp.status_code == 422


# --- v2: per-user scoping ---


def test_cross_user_get_isolated_404(client, auth, auth_b):
    task = _create(client, auth, "alice only")
    resp = client.get(f"/api/tasks/{task['id']}", headers=auth_b)
    assert resp.status_code == 404


def test_cross_user_put_isolated_404(client, auth, auth_b):
    task = _create(client, auth, "alice only")
    resp = client.put(
        f"/api/tasks/{task['id']}",
        json={"title": "bob was here"},
        headers=auth_b,
    )
    assert resp.status_code == 404


def test_cross_user_patch_isolated_404(client, auth, auth_b):
    task = _create(client, auth, "alice only")
    resp = client.patch(
        f"/api/tasks/{task['id']}", json={"status": "done"}, headers=auth_b
    )
    assert resp.status_code == 404


def test_cross_user_delete_isolated_404(client, auth, auth_b):
    task = _create(client, auth, "alice only")
    resp = client.delete(f"/api/tasks/{task['id']}", headers=auth_b)
    assert resp.status_code == 404


def test_list_only_own_tasks(client, auth, auth_b):
    _create(client, auth, "alice task")
    _create(client, auth_b, "bob task")
    alice_titles = [t["title"] for t in client.get("/api/tasks", headers=auth).json()]
    bob_titles = [t["title"] for t in client.get("/api/tasks", headers=auth_b).json()]
    assert alice_titles == ["alice task"]
    assert bob_titles == ["bob task"]


# --- v2: due_at ---


def test_due_at_round_trip(client, auth):
    due = "2026-09-01T12:30:00Z"
    task = _create(client, auth, "with due", due_at=due)
    assert task["due_at"] == "2026-09-01T12:30:00Z"
    got = client.get(f"/api/tasks/{task['id']}", headers=auth).json()
    assert got["due_at"] == "2026-09-01T12:30:00Z"


def test_due_at_null_default_and_clearing(client, auth):
    task = _create(client, auth, "no due")
    assert task["due_at"] is None
    resp = client.patch(
        f"/api/tasks/{task['id']}",
        json={"due_at": datetime(2026, 10, 1, tzinfo=timezone.utc).isoformat()},
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["due_at"] == "2026-10-01T00:00:00Z"
    cleared = client.patch(
        f"/api/tasks/{task['id']}", json={"due_at": None}, headers=auth
    )
    assert cleared.json()["due_at"] is None


# --- v2: tags ---


def test_tag_normalize_dedupe_lowercase(client, auth):
    task = _create(client, auth, "tagged", tags=[" Work ", "WORK", "work", "home", ""])
    assert task["tags"] == ["home", "work"]


def test_patch_replaces_tags_and_cleans_orphans(client, auth, db_session):
    from app.models import Tag

    task = _create(client, auth, "t", tags=["solo"])
    resp = client.patch(
        f"/api/tasks/{task['id']}", json={"tags": ["other"]}, headers=auth
    )
    assert resp.status_code == 200
    assert resp.json()["tags"] == ["other"]
    # 'solo' lost its last reference -> row must be gone.
    db_session.commit()
    assert [t.name for t in db_session.query(Tag).all()] == ["other"]


def test_delete_task_removes_its_orphan_tags(client, auth, db_session):
    from app.models import Tag

    task = _create(client, auth, "doomed", tags=["ghost"])
    client.delete(f"/api/tasks/{task['id']}", headers=auth)
    db_session.commit()
    assert db_session.query(Tag).count() == 0


def test_tag_filter(client, auth):
    _create(client, auth, "a", tags=["work"])
    _create(client, auth, "b", tags=["home"])
    resp = client.get("/api/tasks", params=[("tag", "work")], headers=auth)
    assert [t["title"] for t in resp.json()] == ["a"]
    # Case-insensitive match against normalized names.
    resp = client.get("/api/tasks", params=[("tag", "WORK")], headers=auth)
    assert [t["title"] for t in resp.json()] == ["a"]


def test_tag_filter_and_semantics(client, auth):
    _create(client, auth, "both", tags=["work", "urgent"])
    _create(client, auth, "only-work", tags=["work"])
    resp = client.get(
        "/api/tasks", params=[("tag", "work"), ("tag", "urgent")], headers=auth
    )
    assert [t["title"] for t in resp.json()] == ["both"]


def test_tags_scoped_per_user(client, auth, auth_b, db_session):
    from app.models import Tag

    _create(client, auth, "alice task", tags=["sharedname"])
    task_b = _create(client, auth_b, "bob task", tags=["sharedname"])
    assert task_b["tags"] == ["sharedname"]
    db_session.commit()
    # Same name is fine across users: two independent rows, one per user.
    rows = db_session.query(Tag).filter_by(name="sharedname").all()
    assert len(rows) == 2
    assert len({r.user_id for r in rows}) == 2


def test_bootstrap_user_exists_and_owns_orphans(db_session, clean_tables):
    from app.main import BOOTSTRAP_USERNAME
    from app.main import init_db
    from app.models import Task, User

    # No client fixture in this test, so run the startup hook explicitly.
    init_db()
    user = db_session.query(User).filter_by(username=BOOTSTRAP_USERNAME).one()
    user_id = user.id
    task = Task(title="orphan", user_id=None)
    db_session.add(task)
    db_session.commit()
    orphan_id = task.id
    # Close this session's read transaction, else its lock on tasks blocks
    # init_db()'s ALTER TABLE below.
    db_session.close()
    init_db()
    row = db_session.get(Task, orphan_id)
    assert row.user_id == user_id
