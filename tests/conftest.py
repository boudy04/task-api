import os
import warnings

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres@localhost:5432/taskapi_test"

from app.db import Base, SessionLocal, engine, get_db
from app.main import app


def pytest_configure(config):
    warnings.filterwarnings(
        "ignore",
        message=r"Using `httpx` with `starlette.testclient` is deprecated",
    )


@pytest.fixture(scope="session")
def db_engine():
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def db_session(db_engine):
    with SessionLocal() as session:
        yield session


@pytest.fixture(scope="function")
def clean_tables(db_session):
    yield
    for table in reversed(Base.metadata.sorted_tables):
        db_session.execute(text(f"TRUNCATE TABLE {table.name} RESTART IDENTITY CASCADE"))
    db_session.commit()


@pytest.fixture(scope="function")
def client(db_engine, clean_tables):
    def override_get_db():
        with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def register_and_login(client, username, password="password123"):
    """Register (or log in) and return bearer-token headers for the user."""
    resp = client.post(
        "/api/auth/register", json={"username": username, "password": password}
    )
    if resp.status_code == 409:
        resp = client.post(
            "/api/auth/login", json={"username": username, "password": password}
        )
    assert resp.status_code in (200, 201), resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


@pytest.fixture(scope="function")
def auth(client):
    return register_and_login(client, "alice")


@pytest.fixture(scope="function")
def auth_b(client):
    return register_and_login(client, "bob")
