from app.config import Settings


def test_defaults_when_env_unset(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("AUTH_TOKEN", raising=False)
    settings = Settings()
    assert settings.database_url == "postgresql+psycopg://postgres:postgres@localhost:5432/taskapi"
    assert settings.auth_token == "dev-token"
    assert settings.auth_token != ""


def test_env_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pw@db:5432/other")
    monkeypatch.setenv("AUTH_TOKEN", "secret-token")
    settings = Settings()
    assert settings.database_url == "postgresql+psycopg://user:pw@db:5432/other"
    assert settings.auth_token == "secret-token"
