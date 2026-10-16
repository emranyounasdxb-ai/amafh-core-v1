"""Reject malformed recipients and header-injection attempts before any mail command."""

from email.utils import getaddresses

from app.errors import ApiError
from app.services.login_email import EMAIL_SHAPE

MAX_RECIPIENTS = 50


def recipients(values: list[str], field: str) -> list[str]:
    if len(values) > MAX_RECIPIENTS:
        raise ApiError(
            422, "VALIDATION_ERROR", "Too many recipients", {field: ["Use fewer addresses."]}
        )
    cleaned: list[str] = []
    for value in values:
        if any(mark in value for mark in ("\r", "\n", "\0")):
            raise ApiError(
                422,
                "VALIDATION_ERROR",
                "Invalid recipient",
                {field: ["Enter a normal email address."]},
            )
        parsed = getaddresses([value])
        if len(parsed) != 1:
            raise ApiError(
                422, "VALIDATION_ERROR", "Invalid recipient", {field: ["Enter one email address."]}
            )
        _name, address = parsed[0]
        if (
            not address
            or not EMAIL_SHAPE.fullmatch(address)
            or any(mark in address for mark in ("\r", "\n", "\0", " "))
        ):
            raise ApiError(
                422,
                "VALIDATION_ERROR",
                "Invalid recipient",
                {field: ["Enter a valid email address."]},
            )
        cleaned.append(address)
    return cleaned


def subject(value: str) -> str:
    if any(mark in value for mark in ("\r", "\n", "\0")) or len(value) > 998:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Invalid subject",
            {"subject": ["Enter a subject without line breaks."]},
        )
    return value.strip()
