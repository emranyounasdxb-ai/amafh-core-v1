"""Fixed Calls role eligibility plus the Owner-managed individual grant."""

import re

from app.errors import ApiError
from app.policies import Actor

CALLS_ROLES = frozenset(
    {"Owner", "Managing Director", "Sales Manager", "Coordinator", "Compliance"}
)
_PHONE = re.compile(r"\A[0-9]{1,32}\Z")
_MONTH = re.compile(r"\A[0-9]{4}-(0[1-9]|1[0-2])\Z")
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 50


def require_calls(actor: Actor) -> None:
    if not calls_access(actor.designation, actor.calls_access):
        raise ApiError(403, "FORBIDDEN", "Access denied")


def calls_access(designation: str, granted: bool) -> bool:
    """Owner access stays protected; an individual grant cannot widen role eligibility."""
    return designation == "Owner" or (designation in CALLS_ROLES and granted)


def clean_month(value: object) -> str:
    if not isinstance(value, str) or _MONTH.fullmatch(value) is None:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Choose a valid month",
            {"month": ["Choose a valid month."]},
        )
    return value


def clean_phone(value: object) -> str:
    if not isinstance(value, str):
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Enter a phone number or extension using 1–32 digits",
            {"customerNumber": ["Enter a phone number or extension using 1–32 digits."]},
        )
    text = value.strip()
    if _PHONE.fullmatch(text) is None:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Enter a phone number or extension using 1–32 digits",
            {"customerNumber": ["Enter a phone number or extension using 1–32 digits."]},
        )
    return text


def clean_page(value: object, *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Choose a valid page",
            {"page": ["Choose a valid page."]},
        )
    return value


def clean_number_prefix(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{3,32}", value.strip()) is None:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Enter at least 3 digits for suggestions",
            {"prefix": ["Enter between 3 and 32 digits."]},
        )
    return value.strip()
