"""Validated environment configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import HttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AMAFH_", env_file=".env", extra="ignore")

    database_url: str
    public_origin: HttpUrl
    environment: Literal["production", "development", "test"] = "production"
    session_idle_seconds: int = 3600
    media_storage_root: Path = Path(__file__).resolve().parent.parent / "private_media"
    owner_recovery_secret_file: Path | None = None

    @field_validator("database_url")
    @classmethod
    def postgres_only(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("AMAFH_DATABASE_URL must use postgresql+psycopg")
        return value

    @field_validator("session_idle_seconds")
    @classmethod
    def confirmed_idle_lifetime(cls, value: int) -> int:
        if value != 3600:
            raise ValueError("Session inactivity lifetime is fixed at one hour")
        return value

    @model_validator(mode="after")
    def secure_public_origin(self):
        if (
            self.public_origin.username
            or self.public_origin.password
            or self.public_origin.path not in {None, "/"}
            or self.public_origin.query
            or self.public_origin.fragment
        ):
            raise ValueError("Public origin must be a bare origin without credentials or path")
        if self.public_origin.scheme != "https" and not (
            self.environment in {"development", "test"}
            and self.public_origin.host in {"localhost", "127.0.0.1"}
        ):
            raise ValueError("Public origin requires HTTPS outside local development/test")
        return self


@lru_cache
def settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
