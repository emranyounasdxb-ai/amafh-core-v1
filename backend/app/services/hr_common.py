"""Shared employee scope and presentation helpers for Phase 12C HR records."""

from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.organization import employees
from app.errors import ApiError
from app.policies import Actor, require
from app.repositories.employee_scope import employee_query

DUBAI = ZoneInfo("Asia/Dubai")


def dubai_today() -> date:
    return datetime.now(DUBAI).date()


async def scoped_employee(
    session: AsyncSession,
    actor: Actor,
    employee_id: UUID,
    permission: str,
    *,
    lock: bool = False,
) -> dict:
    """The employee inside the actor's record scope, or a 404 that reveals nothing."""
    require(actor, permission)
    query = employee_query(actor).where(employees.c.id == employee_id)
    if lock:
        query = query.with_for_update(of=employees)
    row = (await session.execute(query)).mappings().first()
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return dict(row)


async def names(session: AsyncSession, ids: set[UUID | None]) -> dict[UUID, str]:
    """Readable names of the HR and Owner actors recorded on HR records."""
    wanted = {value for value in ids if value is not None}
    if not wanted:
        return {}
    rows = await session.execute(
        select(employees.c.id, employees.c.full_name).where(employees.c.id.in_(wanted))
    )
    return {row.id: row.full_name for row in rows}


def iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
