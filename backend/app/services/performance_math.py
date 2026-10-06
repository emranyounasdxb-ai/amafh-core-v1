"""Pure Dubai-date attribution, monthly Target proration and business-day rules."""

from calendar import monthrange
from collections.abc import Callable
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from app.whole_numbers import round_whole

DUBAI = ZoneInfo("Asia/Dubai")


def dubai_date(value: datetime) -> date:
    return value.astimezone(DUBAI).date()


def assignment_on(rows: list[dict], day: date) -> dict | None:
    matches = [
        row
        for row in rows
        if row["assignment_start_date"] <= day
        and (row["assignment_end_date"] is None or day < row["assignment_end_date"])
    ]
    return max(
        matches, key=lambda row: (row["assignment_start_date"], str(row["id"])), default=None
    )


def team_on(rows: list[dict], day: date) -> dict | None:
    matches = [
        row
        for row in rows
        if row["start_date"] <= day and (row["end_date"] is None or day < row["end_date"])
    ]
    return max(matches, key=lambda row: (row["start_date"], str(row["id"])), default=None)


def target_on(rows: list[dict], assignment: dict | None, day: date) -> dict | None:
    if assignment is None:
        return None
    matches = [
        row
        for row in rows
        if (
            row["branch_id"] == assignment["branch_id"]
            and row["department_id"] == assignment["department_id"]
            and row["designation_id"] == assignment["designation_id"]
            and row["effective_date"] <= day
            and (row["inactive_from_date"] is None or day < row["inactive_from_date"])
        )
    ]
    return max(matches, key=lambda row: (row["effective_date"], str(row["id"])), default=None)


def target_denominator(
    start: date,
    end: date,
    assignments: list[dict],
    versions: list[dict],
    product_code: str,
    department_products: dict[UUID, str],
    eligible_day: Callable[[date], bool],
) -> Decimal:
    total = Decimal(0)
    day = start
    while day <= end:
        assignment = assignment_on(assignments, day)
        target = target_on(versions, assignment, day) if eligible_day(day) else None
        if target is not None and assignment is not None:
            if department_products.get(assignment["department_id"]) != product_code:
                day += timedelta(days=1)
                continue
            value = target["target_points"] if product_code == "CC" else target["target_amount_aed"]
            if value is not None:
                total += Decimal(value) / Decimal(monthrange(day.year, day.month)[1])
        day += timedelta(days=1)
    # The calculated Target is a business result: daily proration accumulates
    # exactly and rounds once, here (DEC-051).
    return round_whole(total)


def achievement_percentage(achieved: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator <= 0:
        return None
    return round_whole((achieved * Decimal(100)) / denominator)


def working_days_elapsed(start: date, end: date, holidays: set[date]) -> int:
    elapsed = 0
    day = start + timedelta(days=1)
    while day <= end:
        if day.weekday() != 6 and day not in holidays:
            elapsed += 1
        day += timedelta(days=1)
    return elapsed
