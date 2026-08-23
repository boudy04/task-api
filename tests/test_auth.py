from datetime import datetime, timedelta, timezone

import jwt


def test_register_201_returns_token(client):
    resp = client.post(
        "/api/auth/register", json={"username": "newuser", "password": "password123"}
    )
    assert resp.status_code == 201
    assert resp.json()["token"]


def test_register_duplicate_409(client):
    body = {"username": "dupuser", "password": "password123"}
    assert client.post("/api/auth/register", json=body).status_code == 201
    resp = client.post("/api/auth/register", json=body)
    assert resp.status_code == 409
    assert resp.json() == {"detail": "Username already taken"}


def test_register_short_username_422(client):
    resp = client.post(
        "/api/auth/register", json={"username": "ab", "password": "password123"}
    )
    assert resp.status_code == 422


def test_register_short_password_422(client):
    resp = client.post(
        "/api/auth/register", json={"username": "okname", "password": "short"}
    )
    assert resp.status_code == 422


def test_login_ok_200(client):
    client.post(
        "/api/auth/register",
        json={"username": "loginuser", "password": "password123"},
    )
    resp = client.post(
        "/api/auth/login", json={"username": "loginuser", "password": "password123"}
    )
    assert resp.status_code == 200
    assert resp.json()["token"]


def test_login_wrong_password_401(client):
    client.post(
        "/api/auth/register",
        json={"username": "loginuser2", "password": "password123"},
    )
    resp = client.post(
        "/api/auth/login", json={"username": "loginuser2", "password": "wrongpass99"}
    )
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid credentials"}


def test_login_unknown_user_401(client):
    resp = client.post(
        "/api/auth/login", json={"username": "ghostuser", "password": "password123"}
    )
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid credentials"}


def test_no_token_401(client):
    resp = client.get("/api/tasks")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Not authenticated"}


def test_garbage_token_401(client):
    resp = client.get("/api/tasks", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid or missing token"}


def test_expired_token_401(client):
    from app.auth import _SECRET

    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        _SECRET,
        algorithm="HS256",
    )
    resp = client.get("/api/tasks", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid or missing token"}


def test_valid_token_accesses_tasks(client, auth):
    resp = client.get("/api/tasks", headers=auth)
    assert resp.status_code == 200
