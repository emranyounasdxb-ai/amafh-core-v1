"""Audited Owner/MD maintenance of the immutable UAE holiday calendar."""

from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.performance import uae_holiday_year_certifications, uae_public_holidays
from app.errors import ApiError
from app.policies import Actor, require
from app.schemas.performance import HolidayInput, HolidayYearInput


async def add_date(session: AsyncSession, actor: Actor, item: HolidayInput) -> dict:
    require(actor, "target.write")
    name, reference = item.name.strip(), item.sourceReference.strip()
    if not name or not reference:
        raise ApiError(
            422, "HOLIDAY_SOURCE_REQUIRED", "Holiday name and official source are required"
        )
    holiday_id = uuid4()
    values = {
        "id": holiday_id,
        "holiday_date": item.holidayDate,
        "applicable_year": item.holidayDate.year,
        "name": name,
        "source_reference": reference,
        "created_by_employee_id": actor.employee_id,
    }
    try:
        await session.execute(uae_public_holidays.insert().values(**values))
        await audit.record(
            session,
            actor=actor.employee_id,
            action="holiday.date_added",
            module="performance",
            entity_type="uae_public_holiday",
            entity_id=holiday_id,
            after={
                "date": item.holidayDate.isoformat(),
                "name": name,
                "year": item.holidayDate.year,
                "sourceReference": reference,
            },
        )
        await session.commit()
    except DBAPIError as exc:
        await session.rollback()
        raise ApiError(409, "HOLIDAY_CONFLICT", "Holiday date or certified year conflicts") from exc
    except Exception:
        await session.rollback()
        raise
    return {
        "id": str(holiday_id),
        "holidayDate": item.holidayDate.isoformat(),
        "applicableYear": item.holidayDate.year,
        "name": name,
        "sourceReference": reference,
    }


async def certify_year(session: AsyncSession, actor: Actor, item: HolidayYearInput) -> dict:
    require(actor, "target.write")
    reference = item.sourceReference.strip()
    if not reference:
        raise ApiError(422, "HOLIDAY_SOURCE_REQUIRED", "Official source is required")
    record_id = uuid4()
    try:
        count = await session.scalar(
            select(func.count())
            .select_from(uae_public_holidays)
            .where(
                uae_public_holidays.c.applicable_year == item.applicableYear,
            )
        )
        if not count:
            raise ApiError(
                422, "HOLIDAY_YEAR_EMPTY", "Holiday dates are required before certification"
            )
        await session.execute(
            uae_holiday_year_certifications.insert().values(
                id=record_id,
                applicable_year=item.applicableYear,
                source_reference=reference,
                certified_by_employee_id=actor.employee_id,
            )
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="holiday.year_certified",
            module="performance",
            entity_type="uae_holiday_year_certification",
            entity_id=record_id,
            after={
                "year": item.applicableYear,
                "sourceReference": reference,
                "holidayDateCount": count or 0,
            },
        )
        await session.commit()
    except DBAPIError as exc:
        await session.rollback()
        raise ApiError(409, "HOLIDAY_YEAR_CONFLICT", "Holiday year is already certified") from exc
    except Exception:
        await session.rollback()
        raise
    return {
        "id": str(record_id),
        "applicableYear": item.applicableYear,
        "sourceReference": reference,
        "holidayDateCount": count or 0,
    }


async def list_dates(
    session: AsyncSession,
    actor: Actor,
    *,
    page: int,
    page_size: int,
    year: int | None,
    sort: str | None = None,
    direction: str = "asc",
) -> dict:
    require(actor, "target.write")
    order = (
        {
            "holidayDate": uae_public_holidays.c.holiday_date,
            "name": uae_public_holidays.c.name,
            "sourceReference": uae_public_holidays.c.source_reference,
        }.get(sort)
        if sort is not None
        else None
    )
    if (sort is not None and order is None) or direction not in {"asc", "desc"}:
        raise ApiError(422, "SORT_INVALID", "Invalid sorting")
    conditions = [uae_public_holidays.c.applicable_year == year] if year is not None else []
    total = await session.scalar(
        select(func.count()).select_from(uae_public_holidays).where(*conditions)
    )
    rows = (
        (
            await session.execute(
                select(uae_public_holidays)
                .where(*conditions)
                .order_by(
                    (order.asc() if direction == "asc" else order.desc())
                    if order is not None
                    else uae_public_holidays.c.holiday_date,
                    uae_public_holidays.c.id,
                )
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        )
        .mappings()
        .all()
    )
    return {
        "items": [
            {
                "id": str(row["id"]),
                "holidayDate": row["holiday_date"].isoformat(),
                "applicableYear": row["applicable_year"],
                "name": row["name"],
                "sourceReference": row["source_reference"],
            }
            for row in rows
        ],
        "total": total or 0,
        "page": page,
        "pageSize": page_size,
    }


async def list_years(session: AsyncSession, actor: Actor) -> dict:
    require(actor, "target.write")
    rows = (
        (
            await session.execute(
                select(uae_holiday_year_certifications).order_by(
                    uae_holiday_year_certifications.c.applicable_year,
                )
            )
        )
        .mappings()
        .all()
    )
    return {
        "items": [
            {
                "applicableYear": row["applicable_year"],
                "sourceReference": row["source_reference"],
                "certifiedAt": row["created_at"].isoformat(),
            }
            for row in rows
        ]
    }
