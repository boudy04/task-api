from app.config import Settings


def test_defaults_when_env_unset(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("AUTH_TOKEN", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("BOOTSTRAP_PASSWORD", raising=False)
    settings = Settings()
    assert settings.database_url == "postgresql+psycopg://postgres:postgres@localhost:5432/taskapi"
    assert settings.auth_token == "dev-token"
    assert settings.auth_token != ""
    # Empty JWT_SECRET is valid: auth falls back to a random per-boot secret.
    assert settings.jwt_secret == ""
    assert settings.bootstrap_password == "change-me-now"


def test_env_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pw@db:5432/other")
    monkeypatch.setenv("AUTH_TOKEN", "secret-token")
    monkeypatch.setenv("JWT_SECRET", "real-secret")
    monkeypatch.setenv("BOOTSTRAP_PASSWORD", "s3cret-pass")
    settings = Settings()
    assert settings.database_url == "postgresql+psycopg://user:pw@db:5432/other"
    assert settings.auth_token == "secret-token"
    assert settings.jwt_secret == "real-secret"
    assert settings.bootstrap_password == "s3cret-pass"
