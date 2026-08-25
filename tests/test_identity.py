"""Member identity tokens and role enforcement (decision R28)."""

import pytest


@pytest.fixture
def member(client, auth):
    """Create 'dave' via the admin API and log him in; returns his headers."""
    client.post(
        "/api/members",
        json={"username": "dave"},
        headers=auth,
    )
    resp = client.post("/api/members/login", json={"username": "dave"})
    assert resp.status_code == 200
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_member_login_returns_token_and_role(client, auth):
    client.post("/api/members", json={"username": "erin"}, headers=auth)
    resp = client.post("/api/members/login", json={"username": "Erin"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "member"
    assert body["username"] == "erin"
    assert body["token"]


def test_member_login_unknown_username_autoprovisions(client):
    resp = client.post("/api/members/login", json={"username": "ghost"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "ghost"
    assert resp.json()["role"] == "member"


def test_member_login_bootstrap_username_400(client):
    resp = client.post("/api/members/login", json={"username": "boudy04"})
    assert resp.status_code == 400


def test_member_token_reads_tasks(client, auth, member):
    resp = client.get("/api/tasks", headers=member)
    assert resp.status_code == 200


def test_relogin_replaces_old_token(client, auth):
    client.post("/api/members", json={"username": "frank"}, headers=auth)
    first = client.post("/api/members/login", json={"username": "frank"}).json()["token"]
    second = client.post("/api/members/login", json={"username": "frank"}).json()["token"]
    old = client.get("/api/tasks", headers={"Authorization": f"Bearer {first}"})
    assert old.status_code == 401
    new = client.get("/api/tasks", headers={"Authorization": f"Bearer {second}"})
    assert new.status_code == 200


def test_member_cannot_create_task(client, auth, member):
    resp = client.post(
        "/api/tasks",
        json={"title": "nope", "description": "d"},
        headers=member,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Members have view-only access"


def test_member_cannot_update_task(client, auth, member):
    created = client.post(
        "/api/tasks", json={"title": "t", "description": "d"}, headers=auth
    ).json()
    for method in ("put", "patch"):
        resp = getattr(client, method)(
            f"/api/tasks/{created['id']}",
            json={"title": "hijack"},
            headers=member,
        )
        assert resp.status_code == 403


def test_member_cannot_delete_task(client, auth, member):
    created = client.post(
        "/api/tasks", json={"title": "t", "description": "d"}, headers=auth
    ).json()
    resp = client.delete(f"/api/tasks/{created['id']}", headers=member)
    assert resp.status_code == 403


def test_member_cannot_assign(client, auth, member):
    created = client.post(
        "/api/tasks", json={"title": "t", "description": "d"}, headers=auth
    ).json()
    resp = client.put(
        f"/api/tasks/{created['id']}",
        json={"assignee_ids": [2]},
        headers=member,
    )
    assert resp.status_code == 403


def test_member_cannot_manage_members(client, auth, member):
    resp = client.post("/api/members", json={"username": "sneak"}, headers=member)
    assert resp.status_code == 403
    resp = client.delete("/api/members/2", headers=member)
    assert resp.status_code == 403


def test_members_me_shapes(client, auth, member):
    member_me = client.get("/api/members/me", headers=member)
    assert member_me.status_code == 200
    body = member_me.json()
    assert body["role"] == "member"
    assert body["username"] == "dave"

    admin_me = client.get("/api/members/me", headers=auth)
    assert admin_me.json()["role"] == "admin"
    assert admin_me.json()["username"] == "boudy04"


def test_admin_verify(client, auth):
    ok = client.post("/api/admin/verify", json={"token": "dev-token"})
    assert ok.status_code == 200
    assert ok.json()["role"] == "admin"

    bad = client.post("/api/admin/verify", json={"token": "wrong"})
    assert bad.status_code == 401


def test_garbage_token_401(client):
    resp = client.get("/api/tasks", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401
def test_member_list_includes_admin_tasks(client, auth, member):
    client.post("/api/tasks", json={"title": "admin owned", "description": "d"}, headers=auth)
    resp = client.get("/api/tasks", headers=member)
    titles = [t["title"] for t in resp.json()]
    assert "admin owned" in titles


def test_member_get_single_admin_task_200(client, auth, member):
    created = client.post(
        "/api/tasks", json={"title": "solo", "description": "d"}, headers=auth
    ).json()
    resp = client.get(f"/api/tasks/{created['id']}", headers=member)
    assert resp.status_code == 200


def test_admin_adds_note_201(client, auth):
    created = client.post(
        "/api/tasks", json={"title": "t", "description": "d"}, headers=auth
    ).json()
    resp = client.post(
        f"/api/tasks/{created['id']}/notes",
        json={"body": "awaiting review"},
        headers=auth,
    )
    assert resp.status_code == 201
    assert resp.json()["author"] == "boudy04"
    detail = client.get(f"/api/tasks/{created['id']}", headers=auth).json()
    assert detail["notes"][0]["body"] == "awaiting review"


def test_assignee_adds_note_201_non_assignee_403(client, auth):
    client.post("/api/members", json={"username": "dave"}, headers=auth)
    dave = client.post("/api/members/login", json={"username": "dave"}).json()["token"]
    dave_id = client.get("/api/members/me", headers={"Authorization": f"Bearer {dave}"}).json()["id"]
    created = client.post(
        "/api/tasks",
        json={"title": "t", "description": "d", "assignee_ids": [dave_id]},
        headers=auth,
    ).json()

    ok = client.post(
        f"/api/tasks/{created['id']}/notes",
        json={"body": "blocked, done for now, awaiting review"},
        headers={"Authorization": f"Bearer {dave}"},
    )
    assert ok.status_code == 201
    assert ok.json()["author"] == "dave"

    client.post("/api/members", json={"username": "eve"}, headers=auth)
    eve = client.post("/api/members/login", json={"username": "eve"}).json()["token"]
    denied = client.post(
        f"/api/tasks/{created['id']}/notes",
        json={"body": "I am not assigned"},
        headers={"Authorization": f"Bearer {eve}"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Only assignees can add notes"


def test_note_body_validation_422(client, auth):
    created = client.post(
        "/api/tasks", json={"title": "t", "description": "d"}, headers=auth
    ).json()
    resp = client.post(
        f"/api/tasks/{created['id']}/notes", json={"body": ""}, headers=auth
    )
    assert resp.status_code == 422


def test_assignee_status_only_patch_200_other_keys_403(client, auth):
    client.post("/api/members", json={"username": "dave"}, headers=auth)
    dave = client.post("/api/members/login", json={"username": "dave"}).json()["token"]
    dave_id = client.get("/api/members/me", headers={"Authorization": f"Bearer {dave}"}).json()["id"]
    created = client.post(
        "/api/tasks",
        json={"title": "t", "description": "d", "assignee_ids": [dave_id]},
        headers=auth,
    ).json()

    ok = client.patch(
        f"/api/tasks/{created['id']}",
        json={"status": "done"},
        headers={"Authorization": f"Bearer {dave}"},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "done"

    denied = client.patch(
        f"/api/tasks/{created['id']}",
        json={"status": "todo", "title": "hijack"},
        headers={"Authorization": f"Bearer {dave}"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Assignees may only update status"


def test_member_login_autoprovisions(client):
    resp = client.post("/api/members/login", json={"username": "newbie"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "member"
    me = client.get(
        "/api/members/me", headers={"Authorization": f"Bearer {resp.json()['token']}"}
    )
    assert me.json()["username"] == "newbie"


def test_member_login_bad_charset_422(client):
    resp = client.post("/api/members/login", json={"username": "ab"})
    assert resp.status_code == 422

