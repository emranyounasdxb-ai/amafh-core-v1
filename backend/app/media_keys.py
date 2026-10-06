"""Canonical retained-media key grammar shared by storage and backup validation."""

import re

IMAGE_KINDS = frozenset(
    {
        "employee_avatar",
        "employee_cover",
        "bank_logo",
        "product_image",
        "product_variant_image",
        "global_profile_banner",
    }
)
DOCUMENT_KINDS = frozenset({"employee_document", "hr_issued_document"})

_IMAGE_NAME = re.compile(r"img-[0-9a-f]{32}\.(?:jpg|png|webp)")
_DOCUMENT_NAME = re.compile(r"doc-[0-9a-f]{32}\.(?:pdf|jpg|png)")


def valid_media_key(key: str) -> bool:
    parts = key.split("/")
    if len(parts) != 2:
        return False
    kind, name = parts
    return (kind in IMAGE_KINDS and _IMAGE_NAME.fullmatch(name) is not None) or (
        kind in DOCUMENT_KINDS and _DOCUMENT_NAME.fullmatch(name) is not None
    )
