"""Immutable effective-dated office hours for the Dubai and Abu Dhabi operating Branches.

Eligibility comes from the Branch's explicit operating city, never its display name.
"""

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.attendance import office_timings
from app.db.organization import branches
from app.errors import ApiError
from app.policies import Actor, require
from app.schemas.attendance import OfficeTimingInput


def public(row) -> dict:
    return {
        "id": row["id"],
        "branchId": row["branch_id"],
        "effectiveDate": row["effective_date"],
        "startTime": row["start_time"],
        "endTime": row["end_time"],
        "createdByEmployeeId": row["created_by_employee_id"],
    }


async def effective(session: AsyncSession, branch_id: UUID, on_date: date) -> dict | None:
    row = (
        (
            await session.execute(
                select(office_timings)
                .where(
                    office_timings.c.branch_id == branch_id,
                    office_timings.c.effective_date <= on_date,
                )
                .order_by(office_timings.c.effective_date.desc())
                .limit(1)
            )
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row else None


async def create(session: AsyncSession, actor: Actor, item: OfficeTimingInput) -> dict:
    require(actor, "office_timing.write")
    try:
        city = await session.scalar(
            select(branches.c.operating_city).where(
                branches.c.id == item.branchId, branches.c.active
            )
        )
        if city is None:
            raise ApiError(422, "BRANCH_UNAVAILABLE", "Office Timing Branch unavailable")
        previous = (
            (
                await session.execute(
                    select(office_timings)
                    .where(office_timings.c.branch_id == item.branchId)
                    .order_by(office_timings.c.effective_date.desc())
                    .limit(1)
                )
            )
            .mappings()
            .one_or_none()
        )
        if previous and item.effectiveDate <= previous["effective_date"]:
            raise ApiError(
                409, "OFFICE_TIMING_CONFLICT", "Effective Date conflicts with retained version"
            )
        timing_id = uuid4()
        values = {
            "id": timing_id,
            "branch_id": item.branchId,
            "effective_date": item.effectiveDate,
            "start_time": item.startTime,
            "end_time": item.endTime,
            "created_by_employee_id": actor.employee_id,
        }
        await session.execute(office_timings.insert().values(**values))
        await audit.record(
            session,
            actor=actor.employee_id,
            action="office_timing.created" if previous is None else "office_timing.replaced",
            module="attendance",
            entity_type="office_timing",
            entity_id=timing_id,
            before={
                "versionId": str(previous["id"]),
                "startTime": str(previous["start_time"]),
                "endTime": str(previous["end_time"]),
            }
            if previous
            else None,
            after={
                "branchId": str(item.branchId),
                "effectiveDate": item.effectiveDate.isoformat(),
                "startTime": item.startTime.isoformat(),
                "endTime": item.endTime.isoformat(),
            },
        )
        await session.commit()
        return public(values)
    except DBAPIError as exc:
        await session.rollback()
        raise ApiError(409, "OFFICE_TIMING_CONFLICT", "Office Timing version conflicts") from exc
    except Exception:
        await session.rollback()
        raise


async def list_versions(
    session: AsyncSession,
    actor: Actor,
    *,
    branch_id: UUID | None,
    page: int,
    page_size: int,
    sort: str | None = None,
    direction: str = "asc",
) -> dict:
    require(actor, "office_timing.write")
    order = (
        {
            "effectiveDate": office_timings.c.effective_date,
            "branchId": office_timings.c.branch_id,
            "startTime": office_timings.c.start_time,
            "endTime": office_timings.c.end_time,
        }.get(sort)
        if sort is not None
        else None
    )
    if (sort is not None and order is None) or direction not in {"asc", "desc"}:
        raise ApiError(422, "SORT_INVALID", "Invalid sorting")
    query = select(office_timings)
    if branch_id is not None:
        query = query.where(office_timings.c.branch_id == branch_id)
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = (
        (
            await session.execute(
                query.order_by(
                    (order.asc() if direction == "asc" else order.desc())
                    if order is not None
                    else office_timings.c.effective_date.desc(),
                    office_timings.c.id,
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .mappings()
        .all()
    )
    return {
        "items": [public(row) for row in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


async def detail(session: AsyncSession, actor: Actor, timing_id: UUID) -> dict:
    require(actor, "office_timing.write")
    row = (
        (await session.execute(select(office_timings).where(office_timings.c.id == timing_id)))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return public(row)
