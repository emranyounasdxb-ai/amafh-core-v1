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
    calls_enabled: bool = False
    calls_connector_url: str = ""
    calls_connector_token: str = ""
    calls_source_name: str = "Call recordings"
    calls_sync_interval_seconds: float = 10
    calls_sync_batch: int = 200
    calls_sync_lease_seconds: int = 60
    calls_stream_slots: int = 16
    calls_stream_per_user: int = 3
    calls_stream_chunk_bytes: int = 65536
    calls_auth_recheck_seconds: int = 15
    calls_connect_timeout_seconds: float = 5
    calls_stream_idle_seconds: float = 30

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
        self.calls_connector_url = _calls_connector_url(self.calls_connector_url)
        if any(character in self.calls_connector_token for character in "\r\n\0"):
            raise ValueError("AMAFH_CALLS_CONNECTOR_TOKEN is unusable")
        if self.calls_auth_recheck_seconds < 1 or self.calls_auth_recheck_seconds > 15:
            raise ValueError("calls_auth_recheck_seconds must be from 1 to 15")
        for name in (
            "calls_sync_batch",
            "calls_sync_lease_seconds",
            "calls_stream_slots",
            "calls_stream_per_user",
            "calls_stream_chunk_bytes",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be positive")
        if self.calls_sync_interval_seconds <= 0 or self.calls_connect_timeout_seconds <= 0:
            raise ValueError("Calls timeouts must be positive")
        if self.calls_stream_idle_seconds <= 0:
            raise ValueError("calls_stream_idle_seconds must be positive")
        return self

    def effective_message_bytes(self) -> int:
        provider = self.mail_provider_message_bytes
        if provider is None:
            return self.mail_message_bytes
        return min(self.mail_message_bytes, provider)


def _calls_connector_url(value: str) -> str:
    text = value.strip().rstrip("/")
    if not text:
        return ""
    from urllib.parse import urlsplit

    parsed = urlsplit(text)
    host = parsed.hostname
    if (
        parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or host in {None, "0.0.0.0", "::"}
        or parsed.scheme not in {"http", "https"}
    ):
        raise ValueError("AMAFH_CALLS_CONNECTOR_URL must be a bare connector origin")
    private = host in {"127.0.0.1", "localhost"} or _private_host(host)
    if parsed.scheme == "http" and not private:
        raise ValueError("Calls connector HTTP is only allowed for loopback or a private host")
    return text


def _private_host(host: str) -> bool:
    parts = host.split(".")
    if len(parts) != 4 or not all(part.isdigit() for part in parts):
        return False
    numbers = [int(part) for part in parts]
    if any(number > 255 for number in numbers):
        return False
    if numbers[0] == 10:
        return True
    if numbers[0] == 192 and numbers[1] == 168:
        return True
    return numbers[0] == 172 and 16 <= numbers[1] <= 31


@lru_cache
def settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
