"""Static bearer-token auth (accounts deferred; see tag api-v2-auth-deferred)."""


def test_missing_token_401(client):
    resp = client.get("/api/tasks")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Not authenticated"}


def test_wrong_token_401(client):
    resp = client.get(
        "/api/tasks", headers={"Authorization": "Bearer not-the-admin-token"}
    )
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid or missing token"}


def test_garbage_token_401(client):
    resp = client.get("/api/tasks", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401


def test_admin_token_accesses_tasks(client, auth):
    resp = client.get("/api/tasks", headers=auth)
    assert resp.status_code == 200
