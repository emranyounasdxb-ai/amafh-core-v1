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
    mail_imap_host: str = "ded6959.inmotionhosting.com"
    mail_imap_port: int = 993
    mail_smtp_host: str = "ded6959.inmotionhosting.com"
    mail_smtp_port: int = 465
    mail_attachment_bytes: int = 10_000_000
    mail_attachments_bytes: int = 10_000_000
    mail_message_bytes: int = 15_000_000
    mail_provider_message_bytes: int | None = None
    mail_read_bytes: int = 15_000_000
    mailbox_key_file: Path | None = None
    mail_timeout_seconds: float = 20
    mail_attachment_ttl_seconds: int = 86_400
    mail_refresh_seconds: int = 60
    mail_sync_headers: int = 1000
    mail_sync_bodies: int = 40
    mail_sync_body_bytes: int = 200_000
    mail_sync_batch: int = 50
    mail_sync_lease_seconds: int = 60
    mail_sync_attempts: int = 5

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
        for name in ("mail_imap_host", "mail_smtp_host"):
            host = getattr(self, name).strip()
            if not host or any(character in host for character in " \t\r\n/@:\\"):
                raise ValueError(f"{name} must be a bare mail hostname")
            setattr(self, name, host)
        for name in ("mail_imap_port", "mail_smtp_port"):
            if not 1 <= getattr(self, name) <= 65535:
                raise ValueError(f"{name} is not a valid port")
        for name in (
            "mail_attachment_bytes",
            "mail_attachments_bytes",
            "mail_message_bytes",
            "mail_read_bytes",
            "mail_attachment_ttl_seconds",
            "mail_refresh_seconds",
            "mail_sync_headers",
            "mail_sync_bodies",
            "mail_sync_body_bytes",
            "mail_sync_batch",
            "mail_sync_lease_seconds",
            "mail_sync_attempts",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be positive")
        if self.mail_timeout_seconds <= 0:
            raise ValueError("mail_timeout_seconds must be positive")
        if self.mail_provider_message_bytes is not None and self.mail_provider_message_bytes < 1:
            raise ValueError("mail_provider_message_bytes must be positive when set")
        if self.mailbox_key_file is not None and not self.mailbox_key_file.is_absolute():
            raise ValueError("AMAFH_MAILBOX_KEY_FILE must be an absolute path")
        return self

    def effective_message_bytes(self) -> int:
        provider = self.mail_provider_message_bytes
        if provider is None:
            return self.mail_message_bytes
        return min(self.mail_message_bytes, provider)


@lru_cache
def settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
