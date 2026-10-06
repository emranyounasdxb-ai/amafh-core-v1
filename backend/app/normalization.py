"""Canonical forms for business identifiers and display names."""

import pycountry


def display_name(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Expected a text value")
    return " ".join(value.split())


def identifier(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Expected a text identifier")
    return " ".join(value.split()).upper()


def nationality(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Expected an ISO 3166-1 alpha-2 code")
    code = value.strip().upper()
    if pycountry.countries.get(alpha_2=code) is None:
        raise ValueError("Nationality must be an ISO 3166-1 alpha-2 country or territory")
    return code
