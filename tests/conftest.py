import os
import warnings

import pytest
from sqlalchemy import text

os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres@localhost:5432/taskapi_test"

from app.db import Base, SessionLocal, engine


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