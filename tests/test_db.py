from sqlalchemy import text


def test_engine_points_at_test_database(db_engine):
    assert db_engine.url.database == "taskapi_test"


def test_select_one(db_session):
    assert db_session.execute(text("SELECT 1")).scalar() == 1


def test_round_trip(db_session):
    conn = db_session.connection()
    conn.execute(text("CREATE TEMPORARY TABLE smoke_roundtrip (value TEXT)"))
    conn.execute(text("INSERT INTO smoke_roundtrip VALUES ('hello')"))
    assert conn.execute(text("SELECT value FROM smoke_roundtrip")).scalar() == "hello"
    conn.execute(text("DROP TABLE smoke_roundtrip"))
    db_session.commit()
