"""Demo workspace members: seeded trio + /api/members management."""

from app.db import SessionLocal
from app.models import Task


def _names(client, auth):
    resp = client.get("/api/members", headers=auth)
    assert resp.status_code == 200
    return [m["username"] for m in resp.json()]


def test_fresh_db_seeds_demo_trio(client, auth):
    names = _names(client, auth)

    assert names == sorted(names)  # alphabetical
    assert {"boudy04", "alice", "bob", "carol"} <= set(names)


def test_list_public_for_identity_picker(client):
    # The app's login picker lists usernames before any login exists; writes
    # below still demand the caller and admin role.
    resp = client.get("/api/members")
    assert resp.status_code == 200
    assert client.post("/api/members", json={"username": "sneak"}).status_code == 401


def test_create_member_201_and_normalizes_case(client, auth):
    resp = client.post("/api/members", headers=auth, json={"username": " Dave_Dev "})

    assert resp.status_code == 201
    assert resp.json()["username"] == "dave_dev"
    assert "dave_dev" in _names(client, auth)


def test_create_duplicate_case_insensitive_409(client, auth):
    resp = client.post("/api/members", headers=auth, json={"username": "Alice"})

    assert resp.status_code == 409
    assert resp.json() == {"detail": "Username already taken"}


def test_create_invalid_username_422(client, auth):
    for bad in ("ab", "has space", "no/exclam!", "x" * 25):
        resp = client.post("/api/members", headers=auth, json={"username": bad})
        assert resp.status_code == 422


def test_delete_member_204_then_gone(client, auth):
    member_id = next(
        m["id"] for m in client.get("/api/members", headers=auth).json()
        if m["username"] == "carol"
    )

    assert client.delete(f"/api/members/{member_id}", headers=auth).status_code == 204
    assert "carol" not in _names(client, auth)
    # Unknown ids stay a clean 404.
    assert client.delete("/api/members/99999", headers=auth).status_code == 404


def test_delete_owner_400(client, auth):
    owner_id = next(
        m["id"] for m in client.get("/api/members", headers=auth).json()
        if m["username"] == "boudy04"
    )

    resp = client.delete(f"/api/members/{owner_id}", headers=auth)

    assert resp.status_code == 400
    assert "boudy04" in _names(client, auth)


def test_delete_member_with_task_409_row_survives(client, auth):
    resp = client.post("/api/members", headers=auth, json={"username": "dave"})
    member_id = resp.json()["id"]
    # Legacy-style data owned by the member (FK would make a bare delete a 500).
    with SessionLocal() as db:
        db.add(Task(title="legacy", user_id=member_id))
        db.commit()

    resp = client.delete(f"/api/members/{member_id}", headers=auth)

    assert resp.status_code == 409
    assert resp.json() == {"detail": "Member still has tasks or tags"}
    assert "dave" in _names(client, auth)
