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


def test_member_login_unknown_username_404(client):
    resp = client.post("/api/members/login", json={"username": "ghost"})
    assert resp.status_code == 404


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
