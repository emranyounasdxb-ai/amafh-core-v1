"""Complete backup and restore workflows; no API request invokes these commands."""

import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from app.backup.bundle import build_manifest, create_bundle, inspect_bundle
from app.backup.config import BackupConfig, BackupError
from app.backup.crypto import file_digests
from app.backup.drive import DriveStore
from app.backup.postgres import (
    DatabaseSpec,
    dump_snapshot,
    inspect_dump,
    require_pg18_tool,
    restore_to_empty_target,
    source_snapshot,
)


@dataclass(frozen=True)
class BackupResult:
    set_id: str
    verified: bool
    retained_media_files: int
    expired_sets_removed: int


@dataclass(frozen=True)
class RestoreResult:
    set_id: str
    verified: bool
    applied: bool
    retained_media_files: int


def _workdir(root: Path) -> tempfile.TemporaryDirectory[str]:
    return tempfile.TemporaryDirectory(prefix="amafh-backup-", dir=root)


def perform_backup(config: BackupConfig) -> BackupResult:
    if config.source_database_url is None or config.media_root is None or config.pg_dump is None:
        raise BackupError("Backup source configuration is incomplete")
    key = config.encryption_key()
    require_pg18_tool(config.pg_dump, "pg_dump")
    require_pg18_tool(config.pg_restore, "pg_restore")
    source = DatabaseSpec.from_url(config.source_database_url)
    drive = DriveStore(config)
    set_id = str(uuid4())
    created_at = datetime.now(UTC).isoformat()
    with _workdir(config.temp_root) as temporary:
        workdir = Path(temporary)
        dump = workdir / "database.dump"
        with source_snapshot(source) as (snapshot, media_records):
            dump_snapshot(source, config.pg_dump, snapshot, dump)
            manifest = build_manifest(
                set_id=set_id,
                created_at=created_at,
                key_id=config.key_id,
                source_database=source.name,
                snapshot=snapshot,
                dump_path=dump,
                media_root=config.media_root,
                media_records=media_records,
            )
        inspect_dump(config.pg_restore, dump)
        encrypted = workdir / "backup.amafhbk"
        create_bundle(
            encrypted, manifest=manifest, dump_path=dump, media_root=config.media_root, key=key
        )
        local_check = workdir / "local-check"
        local_check.mkdir(mode=0o700)
        verified_local = inspect_bundle(
            encrypted, key=key, key_id=config.key_id, set_id=set_id, workdir=local_check
        )
        if verified_local.manifest != manifest:
            raise BackupError("Local backup set verification failed")
        inspect_dump(config.pg_restore, verified_local.dump_path)
        size, sha256, _ = file_digests(encrypted)
        if not size:
            raise BackupError("Encrypted backup is empty")
        file_id = drive.upload_pending(
            encrypted, set_id=set_id, created_at=created_at, sha256=sha256
        )
        remote = workdir / "downloaded.amafhbk"
        _, properties = drive.downloaded_file(file_id, set_id, remote, state="pending")
        if properties["sha256"] != sha256:
            raise BackupError("Uploaded backup hash differs from local backup")
        remote_check = workdir / "remote-check"
        remote_check.mkdir(mode=0o700)
        verified_remote = inspect_bundle(
            remote, key=key, key_id=config.key_id, set_id=set_id, workdir=remote_check
        )
        if verified_remote.manifest != manifest:
            raise BackupError("Downloaded backup set differs from exported set")
        inspect_dump(config.pg_restore, verified_remote.dump_path)
        drive.mark_verified(file_id, set_id, created_at, sha256)
        removed = drive.retain_recent_verified(new_set_id=set_id, now=datetime.now(UTC))
        return BackupResult(set_id, True, len(manifest["media"]), removed)


def _restore_target(
    config: BackupConfig,
    set_id: str,
    confirmation: str | None,
    source_database_name: str,
) -> tuple[DatabaseSpec, Path]:
    if confirmation != set_id:
        raise BackupError("Restore application requires the exact set ID confirmation")
    raw_url = os.environ.get("AMAFH_BACKUP_RESTORE_DATABASE_URL", "")
    raw_root = os.environ.get("AMAFH_BACKUP_RESTORE_MEDIA_ROOT", "")
    if not raw_url or not raw_root:
        raise BackupError("Restore target database and media directory must be configured")
    target = DatabaseSpec.from_url(raw_url)
    if target.name == source_database_name:
        raise BackupError("Restore database must have a distinct name")
    media = Path(raw_root)
    if not media.is_absolute() or media.exists() or media.is_symlink():
        raise BackupError("Restore media directory must be an unused absolute path")
    media = media.resolve()
    if config.media_root is not None and (
        media == config.media_root or media.is_relative_to(config.media_root)
    ):
        raise BackupError("Restore media directory must be separate from active media")
    if (config.media_root is not None and config.media_root.is_relative_to(media)) or (
        media.is_relative_to(config.temp_root)
    ):
        raise BackupError(
            "Restore media directory must be separate from active and temporary paths"
        )
    parent = media.parent
    if parent.is_symlink() or not parent.is_dir():
        raise BackupError("Restore media parent must be an existing private directory")
    if os.name != "nt":
        details = parent.stat()
        owner_uid = os.getuid()  # type: ignore[attr-defined]
        if details.st_uid != owner_uid or stat.S_IMODE(details.st_mode) & 0o077:
            raise BackupError("Restore media parent must be owned by this process and mode 0700")
    return target, media


def _copy_media_to_stage(source: Path, stage: Path) -> None:
    stage.mkdir(mode=0o700)
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        destination = stage / relative
        if item.is_symlink():
            raise BackupError("Verified media staging contains an unsafe link")
        if item.is_dir():
            destination.mkdir(mode=0o700, parents=True, exist_ok=True)
            continue
        if not item.is_file():
            raise BackupError("Verified media staging contains an unsafe file")
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with item.open("rb") as input_file, os.fdopen(descriptor, "wb") as output:
            shutil.copyfileobj(input_file, output, length=1024 * 1024)


def perform_restore(
    config: BackupConfig, *, set_id: str, apply: bool = False, confirmation: str | None = None
) -> RestoreResult:
    try:
        set_id = str(UUID(set_id))
    except ValueError as exc:
        raise BackupError("Restore set ID must be a UUID") from exc
    if apply and confirmation != set_id:
        raise BackupError("Restore application requires the exact set ID confirmation")
    key = config.encryption_key()
    drive = DriveStore(config)
    item = drive.find_verified(set_id)
    with _workdir(config.temp_root) as temporary:
        workdir = Path(temporary)
        encrypted = workdir / "downloaded.amafhbk"
        _, properties = drive.downloaded_file(item["id"], set_id, encrypted, state="verified")
        verified_dir = workdir / "verified"
        verified_dir.mkdir(mode=0o700)
        bundle = inspect_bundle(
            encrypted, key=key, key_id=config.key_id, set_id=set_id, workdir=verified_dir
        )
        if bundle.manifest["created_at"] != properties["createdAt"]:
            raise BackupError("Backup set timestamp differs from Drive metadata")
        require_pg18_tool(config.pg_restore, "pg_restore")
        inspect_dump(config.pg_restore, bundle.dump_path)
        if not apply:
            return RestoreResult(set_id, True, False, len(bundle.manifest["media"]))
        target, media_target = _restore_target(
            config, set_id, confirmation, bundle.manifest["source_database"]
        )
        parent = media_target.parent
        stage_root = Path(tempfile.mkdtemp(prefix=".amafh-restore-", dir=parent))
        try:
            stage_media = stage_root / "media"
            _copy_media_to_stage(bundle.media_dir, stage_media)
            restore_to_empty_target(
                bundle.manifest["source_database"],
                target,
                config.pg_restore,
                bundle.dump_path,
            )
            if media_target.exists():
                raise BackupError("Restore media destination was occupied during restore")
            os.replace(stage_media, media_target)
        except Exception as exc:
            raise BackupError(
                "Restore failed; keep the target inactive and discard any partial target state"
            ) from exc
        finally:
            shutil.rmtree(stage_root)
        return RestoreResult(set_id, True, True, len(bundle.manifest["media"]))
