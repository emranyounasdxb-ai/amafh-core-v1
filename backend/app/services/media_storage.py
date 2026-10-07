"""Bounded image validation and protected server-generated file storage."""

import io
import os
import stat
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.config import settings
from app.errors import ApiError
from app.media_keys import valid_media_key
from app.services.pdf_validation import validate_pdf

MAX_UPLOAD_BYTES = 5_000_000
MAX_PIXELS = 16_000_000
FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}


async def validated_image(file: UploadFile) -> tuple[bytes, str, str]:
    content = bytearray()
    while chunk := await file.read(64 * 1024):
        content.extend(chunk)
        if len(content) > MAX_UPLOAD_BYTES:
            raise ApiError(422, "IMAGE_SIZE_LIMIT", "Image exceeds 5,000,000 bytes")
    if not content:
        raise ApiError(422, "IMAGE_INVALID", "Image file is empty")
    try:
        with Image.open(io.BytesIO(content)) as source:
            original_format = source.format
            if original_format not in FORMATS or file.content_type != FORMATS[original_format][0]:
                raise ApiError(
                    422, "IMAGE_TYPE_INVALID", "Only JPG, PNG, and WebP images are allowed"
                )
            if source.width * source.height > MAX_PIXELS or source.width < 1 or source.height < 1:
                raise ApiError(
                    422, "IMAGE_DIMENSIONS_LIMIT", "Image dimensions exceed the safe limit"
                )
            source.load()
            image = source.convert("RGB" if original_format == "JPEG" else "RGBA")
            output = io.BytesIO()
            image.save(output, format=original_format)
            data = output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ApiError(422, "IMAGE_INVALID", "Image content is invalid") from exc
    if len(data) > MAX_UPLOAD_BYTES:
        raise ApiError(422, "IMAGE_SIZE_LIMIT", "Processed image exceeds 5,000,000 bytes")
    mime, extension = FORMATS[original_format]
    return data, mime, extension


def _root() -> Path:
    configured = settings().media_storage_root
    if not configured.is_absolute():
        raise RuntimeError("Media storage root must be absolute")
    root = configured.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != "nt" and stat.S_IMODE(root.stat().st_mode) & 0o077:
        raise RuntimeError("Media storage root must not be group- or world-accessible")
    return root


DOCUMENT_FORMATS = {
    "PDF": ("application/pdf", ".pdf"),
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
}


async def validated_document(file: UploadFile) -> tuple[bytes, str, str]:
    """A PDF, JPEG or PNG retained byte-for-byte after content and size validation."""
    content = bytearray()
    while chunk := await file.read(64 * 1024):
        content.extend(chunk)
        if len(content) > MAX_UPLOAD_BYTES:
            raise ApiError(422, "DOCUMENT_SIZE_LIMIT", "File exceeds 5,000,000 bytes")
    if not content:
        raise ApiError(422, "DOCUMENT_INVALID", "File is empty")
    data = bytes(content)
    if data.startswith(b"%PDF-"):
        detected = "PDF"
        await validate_pdf(data)
    elif data.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n")):
        try:
            with Image.open(io.BytesIO(data)) as source:
                detected = source.format or ""
                if detected not in {"JPEG", "PNG"}:
                    raise ApiError(422, "DOCUMENT_INVALID", "Image content is invalid")
                if source.width * source.height > MAX_PIXELS:
                    raise ApiError(
                        422, "DOCUMENT_INVALID", "Image dimensions exceed the safe limit"
                    )
                source.verify()
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
            raise ApiError(422, "DOCUMENT_INVALID", "Image content is invalid") from exc
    else:
        raise ApiError(422, "DOCUMENT_TYPE_INVALID", "Only PDF, JPEG and PNG files are allowed")
    mime, extension = DOCUMENT_FORMATS[detected]
    if file.content_type != mime:
        raise ApiError(422, "DOCUMENT_TYPE_INVALID", "Only PDF, JPEG and PNG files are allowed")
    return data, mime, extension


def path_for(key: str) -> Path:
    if not valid_media_key(key):
        raise RuntimeError("Invalid retained media storage key")
    root = _root()
    path = (root / Path(*key.split("/"))).resolve()
    if root not in path.parents:
        raise RuntimeError("Invalid retained media path")
    return path


def write_image(kind: str, data: bytes, extension: str) -> str:
    return _write(f"{kind}/img-{uuid4().hex}{extension}", data)


def write_document(kind: str, data: bytes, extension: str) -> str:
    return _write(f"{kind}/doc-{uuid4().hex}{extension}", data)


def _write(key: str, data: bytes) -> str:
    path = path_for(key)
    path.parent.mkdir(mode=0o700, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return key
