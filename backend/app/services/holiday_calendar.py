"""Audited Owner/MD maintenance and atomic correction of the UAE holiday calendar."""

from datetime import date, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.performance import uae_holiday_year_certifications, uae_public_holidays
from app.errors import ApiError
from app.policies import Actor, require
from app.schemas.performance import HolidayBatchInput, HolidayInput, HolidayYearInput


async def _lock_years(session: AsyncSession, years: set[int]) -> None:
    for year in sorted(years):
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"uae_holidays:{year}"},
        )


def _holiday_values(day: date, name: str, reference: str) -> dict:
    return {"date": day.isoformat(), "year": day.year, "name": name, "sourceReference": reference}


async def add_batch(session: AsyncSession, actor: Actor, item: HolidayBatchInput) -> list[dict]:
    require(actor, "target.write")
    expanded: list[tuple[int, date, str, str]] = []
    dates: dict[date, int] = {}
    errors: dict[str, list[str]] = {}
    for index, row in enumerate(item.rows):
        for offset in range((row.endDate - row.startDate).days + 1):
            day = row.startDate + timedelta(days=offset)
            if day in dates:
                previous = dates[day]
                errors.setdefault(f"rows.{index}.startDate", []).append(
                    f"{day} also occurs in row {previous + 1}"
                )
                errors.setdefault(f"rows.{previous}.startDate", []).append(
                    f"{day} also occurs in row {index + 1}"
                )
            dates[day] = index
            expanded.append((index, day, row.name, row.sourceReference))
    if len(expanded) > 3660:
        errors["rows"] = ["A batch may contain at most 3660 expanded dates"]
    if errors:
        raise ApiError(422, "HOLIDAY_BATCH_INVALID", "Review the affected holiday rows", errors)
    try:
        await _lock_years(session, {day.year for day in dates})
        existing = set(
            (
                await session.scalars(
                    select(uae_public_holidays.c.holiday_date).where(
                        uae_public_holidays.c.holiday_date.in_(dates)
                    )
                )
            ).all()
        )
        certified = set(
            (
                await session.scalars(
                    select(uae_holiday_year_certifications.c.applicable_year).where(
                        uae_holiday_year_certifications.c.applicable_year.in_(
                            {day.year for day in dates}
                        )
                    )
                )
            ).all()
        )
        for index, day, _name, _reference in expanded:
            if day in existing:
                errors.setdefault(f"rows.{index}.startDate", []).append(
                    f"A holiday already exists on {day}"
                )
            if day.year in certified:
                message = f"Year {day.year} is certified; edit its existing holiday records"
                if message not in errors.setdefault(f"rows.{index}.startDate", []):
                    errors[f"rows.{index}.startDate"].append(message)
        if errors:
            raise ApiError(
                409, "HOLIDAY_CONFLICT", "No holidays saved. Review the affected rows", errors
            )
        result = []
        for index, day, name, reference in expanded:
            holiday_id = uuid4()
            await session.execute(
                uae_public_holidays.insert().values(
                    id=holiday_id,
                    holiday_date=day,
                    applicable_year=day.year,
                    name=name,
                    source_reference=reference,
                    created_by_employee_id=actor.employee_id,
                )
            )
            await audit.record(
                session,
                actor=actor.employee_id,
                action="holiday.date_added",
                module="performance",
                entity_type="uae_public_holiday",
                entity_id=holiday_id,
                after=_holiday_values(day, name, reference),
                context={"batchRow": index + 1},
            )
            result.append(
                {
                    "id": str(holiday_id),
                    "holidayDate": day.isoformat(),
                    "applicableYear": day.year,
                    "name": name,
                    "sourceReference": reference,
                }
            )
        await session.commit()
        return result
    except DBAPIError as exc:
        await session.rollback()
        raise ApiError(
            409, "HOLIDAY_CONFLICT", "No holidays saved. Reload and review the batch"
        ) from exc
    except Exception:
        await session.rollback()
        raise


async def edit_date(
    session: AsyncSession, actor: Actor, holiday_id: UUID, item: HolidayInput
) -> dict:
    require(actor, "target.write")
    name, reference = item.name.strip(), item.sourceReference.strip()
    if not name or not reference:
        raise ApiError(
            422,
            "HOLIDAY_SOURCE_REQUIRED",
            "Holiday name and official source are required",
            {
                key: ["This field is required"]
                for key, value in (("name", name), ("sourceReference", reference))
                if not value
            },
        )
    try:
        query = select(uae_public_holidays).where(uae_public_holidays.c.id == holiday_id)
        original = (await session.execute(query)).mappings().one_or_none()
        if original is None:
            raise ApiError(404, "HOLIDAY_NOT_FOUND", "Holiday not found")
        await _lock_years(session, {original["applicable_year"], item.holidayDate.year})
        current = (await session.execute(query.with_for_update())).mappings().one()
        if current["applicable_year"] != original["applicable_year"]:
            raise ApiError(
                409, "HOLIDAY_CHANGED", "Holiday changed; reopen it and review the current values"
            )
        conflict = await session.scalar(
            select(uae_public_holidays.c.id).where(
                uae_public_holidays.c.holiday_date == item.holidayDate,
                uae_public_holidays.c.id != holiday_id,
            )
        )
        if conflict:
            raise ApiError(
                409,
                "HOLIDAY_CONFLICT",
                "Holiday date already exists",
                {"holidayDate": [f"A holiday already exists on {item.holidayDate}"]},
            )
        await session.execute(
            uae_public_holidays.update()
            .where(uae_public_holidays.c.id == holiday_id)
            .values(
                holiday_date=item.holidayDate,
                applicable_year=item.holidayDate.year,
                name=name,
                source_reference=reference,
            )
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="holiday.date_updated",
            module="performance",
            entity_type="uae_public_holiday",
            entity_id=holiday_id,
            before=_holiday_values(
                current["holiday_date"], current["name"], current["source_reference"]
            ),
            after=_holiday_values(item.holidayDate, name, reference),
        )
        await session.commit()
    except DBAPIError as exc:
        await session.rollback()
        raise ApiError(
            409,
            "HOLIDAY_CONFLICT",
            "Holiday update conflicts with existing data",
            {"holidayDate": ["Reload and review the holiday date"]},
        ) from exc
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
