"""Environment-driven settings. Secrets never belong in source."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: str = "development"
    log_level: str = "INFO"
    app_base_url: str = "http://localhost:8000"
    public_base_url: str = ""

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/patients"

    vapi_webhook_secret: str = "dev-secret-change-me"
    vapi_api_key: str = ""
    vapi_assistant_id: str = ""
    vapi_phone_number_id: str = ""

    openai_api_key: str = ""

    @property
    def sqlalchemy_url(self) -> str:
        """Render hands out `postgres://`; SQLAlchemy 2 + psycopg want `postgresql+psycopg://`."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if url.startswith("postgresql://") and "+psycopg" not in url:
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
        return url

    @property
    def is_sqlite(self) -> bool:
        return self.sqlalchemy_url.startswith("sqlite")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
