from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/taskapi"
    # Retired v1 static token; parsed for backwards compat but ignored (logged once).
    auth_token: str = "dev-token"
    jwt_secret: str = ""
    bootstrap_password: str = "change-me-now"

    @field_validator("database_url")
    @classmethod
    def force_psycopg_driver(cls, v: str) -> str:
        if v.startswith("postgresql://") or v.startswith("postgres://"):
            return v.replace("://", "+psycopg://", 1)
        return v
