"""Backup-only configuration; secrets are never part of application settings."""

import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from app.config import settings


class BackupError(Exception):
    """A safe operational failure whose message contains no secret or backup data."""


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise BackupError(f"Missing required configuration: {name}")
    return value


def _absolute(name: str) -> Path:
    path = Path(_required(name))
    if not path.is_absolute():
        raise BackupError(f"{name} must be an absolute path")
    return path


def _private_file(path: Path, name: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise BackupError(f"{name} must identify a regular private file")
    if os.name != "nt":
        details = path.stat()
        owner_uid = os.getuid()  # type: ignore[attr-defined]
        if details.st_uid != owner_uid or stat.S_IMODE(details.st_mode) & 0o077:
            raise BackupError(f"{name} must be owned by this process and mode 0600")


def _private_dir(path: Path, name: str, *, create: bool = False) -> Path:
    if path.is_symlink():
        raise BackupError(f"{name} must not be a symbolic link")
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.is_dir():
        raise BackupError(f"{name} must identify a directory")
    resolved = path.resolve()
    if os.name != "nt":
        details = resolved.stat()
        owner_uid = os.getuid()  # type: ignore[attr-defined]
        if details.st_uid != owner_uid or stat.S_IMODE(details.st_mode) & 0o077:
            raise BackupError(f"{name} must be owned by this process and mode 0700")
    return resolved


@dataclass(frozen=True)
class BackupConfig:
    source_database_url: str | None
    media_root: Path | None
    temp_root: Path
    key_file: Path
    key_id: str
    oauth_file: Path
    owner_email: str
    drive_folder_id: str
    pg_dump: Path | None
    pg_restore: Path

    @classmethod
    def from_environment(cls, *, restore: bool = False) -> BackupConfig:
        # A disaster restore must work even when the source media directory or
        # database is gone. Backup still requires an explicit live media path.
        if restore:
            media_value = os.environ.get("AMAFH_MEDIA_STORAGE_ROOT", "")
            media_root = Path(media_value).resolve() if media_value else None
            if media_root is not None and not Path(media_value).is_absolute():
                raise BackupError("AMAFH_MEDIA_STORAGE_ROOT must be absolute when configured")
        else:
            media_root = _private_dir(
                _absolute("AMAFH_MEDIA_STORAGE_ROOT"), "AMAFH_MEDIA_STORAGE_ROOT"
            )
        backend_root = Path(__file__).resolve().parents[3]
        temp_path = _absolute("AMAFH_BACKUP_TEMP_ROOT")
        if temp_path.resolve().is_relative_to(backend_root) or (
            media_root is not None and temp_path.resolve().is_relative_to(media_root)
        ):
            raise BackupError("Backup temporary storage must be outside source and media")
        temp_root = _private_dir(temp_path, "AMAFH_BACKUP_TEMP_ROOT", create=True)
        key_file = _absolute("AMAFH_BACKUP_KEY_FILE")
        oauth_file = _absolute("AMAFH_BACKUP_DRIVE_OAUTH_FILE")
        _private_file(key_file, "AMAFH_BACKUP_KEY_FILE")
        _private_file(oauth_file, "AMAFH_BACKUP_DRIVE_OAUTH_FILE")
        for path in (key_file.resolve(), oauth_file.resolve(), temp_root):
            if path.is_relative_to(backend_root) or (
                media_root is not None and path.is_relative_to(media_root)
            ):
                raise BackupError(
                    "Backup secrets and temporary files must be outside source and media"
                )
        if media_root is not None and (
            media_root.is_relative_to(temp_root) or temp_root.is_relative_to(media_root)
        ):
            raise BackupError("Backup temporary storage must be separate from media storage")
        key_id = _required("AMAFH_BACKUP_KEY_ID")
        folder_id = _required("AMAFH_BACKUP_DRIVE_FOLDER_ID")
        owner_email = _required("AMAFH_BACKUP_OWNER_EMAIL").casefold()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", key_id):
            raise BackupError("AMAFH_BACKUP_KEY_ID is invalid")
        if not re.fullmatch(r"[A-Za-z0-9_-]{10,200}", folder_id):
            raise BackupError("AMAFH_BACKUP_DRIVE_FOLDER_ID is invalid")
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", owner_email):
            raise BackupError("AMAFH_BACKUP_OWNER_EMAIL is invalid")
        pg_dump = None if restore else _absolute("AMAFH_BACKUP_PG_DUMP")
        pg_restore = _absolute("AMAFH_BACKUP_PG_RESTORE")
        if (pg_dump is not None and not pg_dump.is_file()) or not pg_restore.is_file():
            raise BackupError("Required PostgreSQL 18 utility is unavailable")
        return cls(
            source_database_url=None if restore else settings().database_url,
            media_root=media_root,
            temp_root=temp_root,
            key_file=key_file.resolve(),
            key_id=key_id,
            oauth_file=oauth_file.resolve(),
            owner_email=owner_email,
            drive_folder_id=folder_id,
            pg_dump=pg_dump.resolve() if pg_dump is not None else None,
            pg_restore=pg_restore.resolve(),
        )

    def encryption_key(self) -> bytes:
        _private_file(self.key_file, "AMAFH_BACKUP_KEY_FILE")
        key = self.key_file.read_bytes()
        if len(key) != 32:
            raise BackupError("Backup encryption key must contain exactly 32 raw bytes")
        return key
