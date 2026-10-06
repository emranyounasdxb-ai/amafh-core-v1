"""One authenticated database-and-media backup set with per-member hashes."""

import hashlib
import json
import os
import re
import stat
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, BinaryIO, cast

from app.backup.config import BackupError
from app.backup.crypto import CHUNK, decrypt_to_tar, encrypt_tar, file_digests
from app.media_keys import valid_media_key

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MAX_MANIFEST_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class VerifiedBundle:
    manifest: dict
    dump_path: Path
    media_dir: Path


def _media_file(root: Path, key: str) -> Path:
    if not valid_media_key(key):
        raise BackupError("Database contains an invalid media storage key")
    path = root.joinpath(*key.split("/"))
    if path.is_symlink() or not path.is_file() or root not in path.resolve().parents:
        raise BackupError("A registered media file is missing or unsafe")
    if not stat.S_ISREG(path.stat().st_mode):
        raise BackupError("A registered media file is not regular")
    return path


def build_manifest(
    *,
    set_id: str,
    created_at: str,
    key_id: str,
    source_database: str,
    snapshot: str,
    dump_path: Path,
    media_root: Path,
    media_records: list[tuple[str, str, int]],
) -> dict:
    dump_size, dump_hash, _ = file_digests(dump_path)
    if not dump_size:
        raise BackupError("PostgreSQL dump is empty")
    media = []
    seen: set[str] = set()
    for kind, key, registered_size in media_records:
        if key in seen:
            raise BackupError("Database contains duplicate media keys")
        seen.add(key)
        if not valid_media_key(key) or key.split("/", 1)[0] != kind:
            raise BackupError("Database media category and storage key disagree")
        path = _media_file(media_root, key)
        size, digest, _ = file_digests(path)
        if size != registered_size:
            raise BackupError("Registered media size differs from stored content")
        media.append({"kind": kind, "key": key, "size": size, "sha256": digest})
    return {
        "format": 1,
        "set_id": set_id,
        "created_at": created_at,
        "key_id": key_id,
        "source_postgres_major": 18,
        "source_database": source_database,
        "snapshot": snapshot,
        "database": {"name": "database.dump", "size": dump_size, "sha256": dump_hash},
        "media": media,
    }


def _tar_file(archive: tarfile.TarFile, name: str, path: Path, size: int) -> None:
    info = tarfile.TarInfo(name)
    info.size = size
    info.mode = 0o600
    info.uid = info.gid = 0
    info.mtime = 0
    with path.open("rb") as source:
        archive.addfile(info, source)


def create_bundle(
    output_path: Path, *, manifest: dict, dump_path: Path, media_root: Path, key: bytes
) -> None:
    manifest_data = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(manifest_data) > _MAX_MANIFEST_BYTES:
        raise BackupError("Backup manifest is too large")

    def write_archive(encrypted_output: object) -> None:
        with tarfile.open(
            fileobj=cast(BinaryIO, encrypted_output), mode="w|", format=tarfile.USTAR_FORMAT
        ) as tar:
            info = tarfile.TarInfo("manifest.json")
            info.size = len(manifest_data)
            info.mode = 0o600
            info.mtime = 0
            import io

            tar.addfile(info, io.BytesIO(manifest_data))
            _tar_file(tar, "database.dump", dump_path, manifest["database"]["size"])
            for item in manifest["media"]:
                _tar_file(
                    tar,
                    "media/" + item["key"],
                    _media_file(media_root, item["key"]),
                    item["size"],
                )

    encrypt_tar(
        output_path,
        key=key,
        set_id=manifest["set_id"],
        key_id=manifest["key_id"],
        created_at=manifest["created_at"],
        write_archive=write_archive,
    )


def _validate_manifest(manifest: object, header: dict, expected_set_id: str) -> dict:
    if not isinstance(manifest, dict):
        raise BackupError("Backup manifest is invalid")
    try:
        if (
            manifest["format"] != 1
            or manifest["set_id"] != expected_set_id
            or manifest["set_id"] != header["set_id"]
            or manifest["key_id"] != header["key_id"]
            or manifest["created_at"] != header["created_at"]
            or manifest["source_postgres_major"] != 18
            or not isinstance(manifest["source_database"], str)
            or not 1 <= len(manifest["source_database"]) <= 63
        ):
            raise ValueError
        date = datetime.fromisoformat(manifest["created_at"])
        if date.tzinfo is None or date.utcoffset() != UTC.utcoffset(date):
            raise ValueError
        database = manifest["database"]
        if database["name"] != "database.dump" or not isinstance(database["size"], int):
            raise ValueError
        if database["size"] <= 0 or not _SHA256.fullmatch(database["sha256"]):
            raise ValueError
        media = manifest["media"]
        if not isinstance(media, list):
            raise ValueError
        keys = set()
        for item in media:
            if (
                not isinstance(item, dict)
                or not isinstance(item["key"], str)
                or not valid_media_key(item["key"])
                or item["kind"] != item["key"].split("/", 1)[0]
                or item["key"] in keys
                or not isinstance(item["size"], int)
                or item["size"] < 0
                or not isinstance(item["sha256"], str)
                or not _SHA256.fullmatch(item["sha256"])
            ):
                raise ValueError
            keys.add(item["key"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise BackupError("Backup manifest is invalid") from exc
    return manifest


def _copy_verified(source: IO[bytes], output: Path, expected: dict) -> None:
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    digest = hashlib.sha256()
    size = 0
    with os.fdopen(descriptor, "wb") as target:
        while data := source.read(CHUNK):
            target.write(data)
            digest.update(data)
            size += len(data)
    if size != expected["size"] or digest.hexdigest() != expected["sha256"]:
        raise BackupError("Backup member hash or size mismatch")


def inspect_bundle(
    encrypted_path: Path,
    *,
    key: bytes,
    key_id: str,
    set_id: str,
    workdir: Path,
) -> VerifiedBundle:
    archive_path = workdir / "authenticated.tar"
    header = decrypt_to_tar(
        encrypted_path,
        archive_path,
        key=key,
        expected_set_id=set_id,
        expected_key_id=key_id,
    )
    dump_path = workdir / "database.dump"
    media_dir = workdir / "media"
    media_dir.mkdir(mode=0o700)
    try:
        with tarfile.open(archive_path, mode="r|") as tar:
            members = iter(tar)
            first = next(members, None)
            if first is None or first.name != "manifest.json" or not first.isfile():
                raise BackupError("Backup manifest is missing")
            if first.size > _MAX_MANIFEST_BYTES:
                raise BackupError("Backup manifest is too large")
            manifest_stream = tar.extractfile(first)
            if manifest_stream is None:
                raise BackupError("Backup manifest is missing")
            try:
                manifest = _validate_manifest(
                    json.loads(manifest_stream.read(_MAX_MANIFEST_BYTES + 1)), header, set_id
                )
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise BackupError("Backup manifest is invalid") from exc
            expected = {"database.dump": manifest["database"]}
            expected.update({"media/" + item["key"]: item for item in manifest["media"]})
            seen = set()
            for member in members:
                if not member.isfile() or member.name not in expected or member.name in seen:
                    raise BackupError("Backup archive contains an unexpected member")
                seen.add(member.name)
                source = tar.extractfile(member)
                if source is None:
                    raise BackupError("Backup archive member is unreadable")
                destination = (
                    dump_path
                    if member.name == "database.dump"
                    else media_dir.joinpath(*member.name.removeprefix("media/").split("/"))
                )
                if member.size != expected[member.name]["size"]:
                    raise BackupError("Backup archive member size mismatch")
                _copy_verified(source, destination, expected[member.name])
            if seen != set(expected):
                raise BackupError("Backup archive is incomplete")
        return VerifiedBundle(manifest, dump_path, media_dir)
    except (tarfile.TarError, OSError) as exc:
        raise BackupError("Backup archive is invalid") from exc
    finally:
        archive_path.unlink(missing_ok=True)
