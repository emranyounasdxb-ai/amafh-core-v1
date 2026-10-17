"""Anchored recording-name and month-folder parser.

The generated numeric field is opaque, not a timestamp. Both following fields
are exact dialled numbers (including internal extensions). Their order does not
establish call direction or employee identity. Legacy attribute names remain for
wire compatibility. Leading zeros and the original filename are preserved.
"""

import re
from dataclasses import dataclass

_FILENAME = re.compile(r"\Aauto-([0-9]+)-([0-9]{1,32})-(##)?([0-9]{1,32})\.([A-Za-z0-9]+)\Z")
_MONTH = re.compile(r"\A([0-9]{4})-(0[1-9]|1[0-2])\Z")
CONFIRMED_EXTENSION = "wav"


@dataclass(frozen=True)
class ParsedName:
    opaque: str
    extension_number: str
    marked: bool
    customer_number: str
    file_extension: str
    supported: bool


def parse_filename(name: str) -> ParsedName | None:
    """Return a parse of one direct file name, or None when the shape is unsupported."""
    if not isinstance(name, str) or name != name.strip() or any(ord(ch) < 32 for ch in name):
        return None
    match = _FILENAME.fullmatch(name)
    if match is None:
        return None
    opaque, extension_number, marker, customer_number, file_extension = match.groups()
    return ParsedName(
        opaque=opaque,
        extension_number=extension_number,
        marked=marker == "##",
        customer_number=customer_number,
        file_extension=file_extension,
        supported=file_extension.lower() == CONFIRMED_EXTENSION,
    )


def parse_month(name: str) -> str | None:
    if not isinstance(name, str):
        return None
    match = _MONTH.fullmatch(name)
    if match is None:
        return None
    return f"{match.group(1)}-{match.group(2)}"


def parse_customer_query(value: str) -> str | None:
    """Accept an exact numeric participant; never truncate or rewrite prefixes."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not 1 <= len(text) <= 32 or any(ch < "0" or ch > "9" for ch in text):
        return None
    return text
