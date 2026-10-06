"""Application-wide whole-number rule for business numbers (DEC-051).

Business amounts, points, targets, percentages and other calculated business
results are whole numbers. Fractions round to the nearest whole number and an
exact half rounds away from zero (750.50 -> 751, -750.50 -> -751). Arithmetic
uses Decimal so the rule never depends on binary floating point.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Annotated, Any

from pydantic import BeforeValidator, Field

WHOLE = Decimal(1)


def round_whole(value: Any) -> Decimal:
    """Round a business number to the nearest whole Decimal, half away from zero."""
    number = value if isinstance(value, Decimal) else Decimal(str(value))
    return number.quantize(WHOLE, rounding=ROUND_HALF_UP)


def whole_text(value: Any) -> str | None:
    """Authoritative whole-number string used by API responses and exports."""
    if value is None:
        return None
    return str(round_whole(value))


def _normalize(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return value
        candidate: Any = text
    elif isinstance(value, (int, float, Decimal)):
        candidate = value
    else:
        return value
    try:
        number = Decimal(str(candidate))
    except InvalidOperation:
        return value
    if not number.is_finite():
        return value
    return round_whole(number)


def _normalize_int(value: Any) -> Any:
    rounded = _normalize(value)
    return int(rounded) if isinstance(rounded, Decimal) else rounded


WholeAmount = Annotated[
    Decimal, BeforeValidator(_normalize), Field(max_digits=18, decimal_places=0)
]
"""Whole AED amount input: fractional input is rounded before validation."""

WholeCount = Annotated[int, BeforeValidator(_normalize_int)]
"""Whole points or quantity input: fractional input is rounded before validation."""
