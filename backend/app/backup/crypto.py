"""Versioned streaming AES-256-GCM backup envelope."""

import hashlib
import json
import os
import struct
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from app.backup.config import BackupError

MAGIC = b"AMAFHBK1"
CHUNK = 1024 * 1024
TAG_BYTES = 16
# NIST SP 800-38D's per-invocation GCM plaintext ceiling (2^39 - 256 bits).
MAX_GCM_PLAINTEXT_BYTES = (1 << 36) - 32


def file_digests(path: Path) -> tuple[int, str, str]:
    sha256 = hashlib.sha256()
    md5 = hashlib.md5(usedforsecurity=False)
    size = 0
    with path.open("rb") as source:
        while data := source.read(CHUNK):
            size += len(data)
            sha256.update(data)
            md5.update(data)
    return size, sha256.hexdigest(), md5.hexdigest()


class _EncryptingWriter:
    def __init__(self, output: BinaryIO, encryptor: object):
        self.output = output
        self.encryptor = encryptor
        self.total = 0

    def write(self, data: bytes) -> int:
        self.total += len(data)
        if self.total > MAX_GCM_PLAINTEXT_BYTES:
            raise BackupError("Backup set exceeds the authenticated encryption size limit")
        self.output.write(self.encryptor.update(data))  # type: ignore[attr-defined]
        return len(data)

    def flush(self) -> None:
        self.output.flush()


def encrypt_tar(
    output_path: Path,
    *,
    key: bytes,
    set_id: str,
    key_id: str,
    created_at: str,
    write_archive: Callable[[object], None],
) -> None:
    if len(key) != 32:
        raise BackupError("Backup encryption key is invalid")
    nonce = os.urandom(12)
    header = json.dumps(
        {
            "version": 1,
            "set_id": set_id,
            "key_id": key_id,
            "created_at": created_at,
            "nonce": nonce.hex(),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    prefix = MAGIC + struct.pack(">I", len(header)) + header
    descriptor = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(prefix)
            encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
            encryptor.authenticate_additional_data(prefix)
            write_archive(_EncryptingWriter(output, encryptor))
            output.write(encryptor.finalize())
            output.write(encryptor.tag)
            output.flush()
            os.fsync(output.fileno())
    except Exception:
        output_path.unlink(missing_ok=True)
        raise


def _header(source: BinaryIO) -> tuple[dict, bytes, int]:
    magic = source.read(len(MAGIC))
    length_bytes = source.read(4)
    if magic != MAGIC or len(length_bytes) != 4:
        raise BackupError("Backup envelope is invalid")
    length = struct.unpack(">I", length_bytes)[0]
    if length < 20 or length > 4096:
        raise BackupError("Backup envelope is invalid")
    data = source.read(length)
    if len(data) != length:
        raise BackupError("Backup envelope is incomplete")
    try:
        header = json.loads(data)
        UUID(header["set_id"])
        nonce = bytes.fromhex(header["nonce"])
        if header["version"] != 1 or len(nonce) != 12:
            raise ValueError
        if not isinstance(header["key_id"], str) or not isinstance(header["created_at"], str):
            raise ValueError
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise BackupError("Backup envelope is invalid") from exc
    return header, MAGIC + length_bytes + data, len(MAGIC) + 4 + length


def decrypt_to_tar(
    encrypted_path: Path,
    output_path: Path,
    *,
    key: bytes,
    expected_set_id: str,
    expected_key_id: str,
) -> dict:
    if len(key) != 32:
        raise BackupError("Backup encryption key is invalid")
    authenticated = False
    try:
        with encrypted_path.open("rb") as source:
            descriptor = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as output:
                header, prefix, offset = _header(source)
                if header["set_id"] != expected_set_id or header["key_id"] != expected_key_id:
                    raise BackupError("Backup set or encryption key ID does not match")
                size = encrypted_path.stat().st_size
                ciphertext_size = size - offset - TAG_BYTES
                if ciphertext_size <= 0:
                    raise BackupError("Backup envelope is incomplete")
                source.seek(size - TAG_BYTES)
                tag = source.read(TAG_BYTES)
                source.seek(offset)
                decryptor = Cipher(
                    algorithms.AES(key), modes.GCM(bytes.fromhex(header["nonce"]), tag)
                ).decryptor()
                decryptor.authenticate_additional_data(prefix)
                remaining = ciphertext_size
                while remaining:
                    block = source.read(min(CHUNK, remaining))
                    if not block:
                        raise BackupError("Backup envelope is incomplete")
                    remaining -= len(block)
                    output.write(decryptor.update(block))
                output.write(decryptor.finalize())
                output.flush()
                os.fsync(output.fileno())
                authenticated = True
                return header
    except InvalidTag as exc:
        raise BackupError("Backup authentication failed") from exc
    finally:
        # Never retain plaintext if the GCM tag has not authenticated it.
        if not authenticated:
            output_path.unlink(missing_ok=True)
