"""Seal mailbox passwords with the deployment key. Missing or invalid keys fail closed."""

import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

KEY_BYTES = 32
NONCE_BYTES = 12
VERSION = b"\x01"


class MailboxKeyError(Exception):
    """The encryption key cannot be used. Callers must not store plaintext."""


def load_key() -> bytes:
    path: Path | None = settings().mailbox_key_file
    if path is None:
        raise MailboxKeyError
    try:
        key = path.read_bytes()
    except OSError as exc:
        raise MailboxKeyError from exc
    if len(key) != KEY_BYTES:
        raise MailboxKeyError
    return key


def seal(password: str) -> bytes:
    key = load_key()
    nonce = os.urandom(NONCE_BYTES)
    try:
        ciphertext = AESGCM(key).encrypt(nonce, password.encode("utf-8"), None)
    except Exception as exc:
        raise MailboxKeyError from exc
    return VERSION + nonce + ciphertext


def open_secret(blob: bytes) -> str:
    if len(blob) <= 1 + NONCE_BYTES or not blob.startswith(VERSION):
        raise MailboxKeyError
    key = load_key()
    nonce = blob[1 : 1 + NONCE_BYTES]
    try:
        plain = AESGCM(key).decrypt(nonce, blob[1 + NONCE_BYTES :], None)
    except Exception as exc:
        raise MailboxKeyError from exc
    return plain.decode("utf-8")
