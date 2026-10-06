"""Calendar-certified delayed Case evaluation at a historical Dubai date."""

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.performance import uae_holiday_year_certifications, uae_public_holidays
from app.services.performance_math import dubai_date, working_days_elapsed


async def count_delayed(
    session: AsyncSession,
    candidates: list[tuple[UUID, date, int]],
    as_of: date,
) -> tuple[int | None, str]:
    if not candidates:
        return 0, "Available"
    earliest = min(start for _, start, _ in candidates)
    years = set(range(earliest.year, as_of.year + 1))
    key = tuple(sorted(years))
    cache: dict[tuple[int, ...], tuple[set[int], set[date]]] | None = session.info.get(
        "holiday_calendar_cache"
    )
    if cache is not None and key in cache:
        certified, holidays = cache[key]
    else:
        certified = set(
            (
                await session.scalars(
                    select(uae_holiday_year_certifications.c.applicable_year).where(
                        uae_holiday_year_certifications.c.applicable_year.in_(years)
                    )
                )
            ).all()
        )
        holidays = set(
            (
                await session.scalars(
                    select(uae_public_holidays.c.holiday_date).where(
                        uae_public_holidays.c.applicable_year.in_(years)
                    )
                )
            ).all()
        )
        if cache is not None:
            cache[key] = certified, holidays
    if years - certified:
        return None, "Holiday calendar unavailable"
    return sum(
        working_days_elapsed(start, as_of, holidays) > expected for _, start, expected in candidates
    ), "Available"


def stage_start(stage_events: list[dict], as_of: date) -> tuple[str, date] | None:
    events = [row for row in stage_events if dubai_date(row["occurred_at"]) <= as_of]
    if not events:
        return None
    row = max(events, key=lambda item: (item["occurred_at"], str(item["id"])))
    return row["stage"], dubai_date(row["occurred_at"])
