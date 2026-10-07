"""Opaque secrets, adaptive password hashing and input policy."""

import hashlib
import secrets
import string

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.errors import ApiError

hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128

# An unavailable account still incurs the same Argon2 verification cost as an
# eligible account. This is a valid precomputed hash, never a user credential.
DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$syjPWWt8L0x9cAWJQTA14Q$"
    "x96EmOjl1HVjl5s0bI4PXaZFyquT3ufcOjTC35pVJnw"
)


def new_token() -> str:
    return secrets.token_urlsafe(48)


def token_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_password(value: str) -> None:
    if not MIN_PASSWORD_LENGTH <= len(value) <= MAX_PASSWORD_LENGTH:
        raise ApiError(422, "PASSWORD_POLICY", "Password must contain 12 to 128 characters")
    if not all(
        (
            any(c.isupper() for c in value),
            any(c.islower() for c in value),
            any(c.isdigit() for c in value),
            any(c in string.punctuation for c in value),
        )
    ):
        raise ApiError(
            422,
            "PASSWORD_POLICY",
            "Password must contain uppercase, lowercase, number and special character",
        )


def hash_password(value: str) -> str:
    validate_password(value)
    return hasher.hash(value)


def verify_password(encoded: str | None, value: str) -> bool:
    if encoded is None:
        return False
    try:
        return hasher.verify(encoded, value)
    except VerifyMismatchError, ValueError:
        return False
