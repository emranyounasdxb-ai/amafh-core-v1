"""PF commission uses the final funded amount, never requested amounts or points."""

from decimal import Decimal, localcontext

from app.errors import ApiError
from app.whole_numbers import round_whole

MAX_AMOUNT = Decimal("999999999999999999")


def calculate_commission(amount: Decimal, rate: Decimal) -> Decimal:
    # Two 18-digit operands must not be multiplied at Decimal's default precision.
    with localcontext() as context:
        context.prec = 50
        result = round_whole(amount * rate / Decimal(1000))
    if result < 0 or result > MAX_AMOUNT:
        raise ApiError(422, "PF_COMMISSION_LIMIT", "Calculated PF commission exceeds the AED limit")
    return result
