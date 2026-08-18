import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import Settings

os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres@localhost:5432/taskapi_test"

engine = create_engine(Settings().database_url)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


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
