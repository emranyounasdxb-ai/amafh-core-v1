"""One filtered audit population for Owner/MD pages and exports."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.operations import audit_events
from app.errors import ApiError


def filtered_query(
    *,
    actor_id: UUID | None = None,
    action: str | None = None,
    module: str | None = None,
    entity_id: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> Select:
    if from_time is not None and to_time is not None and from_time > to_time:
        raise ApiError(422, "DATE_RANGE_INVALID", "Start Time must not follow End Time")
    query = select(audit_events)
    for condition in (
        audit_events.c.actor_employee_id == actor_id if actor_id else None,
        audit_events.c.action == action if action else None,
        audit_events.c.module == module if module else None,
        audit_events.c.entity_id == entity_id if entity_id else None,
        audit_events.c.occurred_at >= from_time if from_time else None,
        audit_events.c.occurred_at <= to_time if to_time else None,
    ):
        if condition is not None:
            query = query.where(condition)
    return query


async def count(session: AsyncSession, query: Select) -> int:
    return await session.scalar(select(func.count()).select_from(query.subquery())) or 0


async def rows(
    session: AsyncSession,
    query: Select,
    offset: int,
    limit: int,
    *,
    sort: str = "occurredAt",
    direction: str = "desc",
) -> list[dict]:
    order = {
        "occurredAt": audit_events.c.occurred_at,
        "action": audit_events.c.action,
        "module": audit_events.c.module,
        "entityType": audit_events.c.entity_type,
        "actorEmployeeId": audit_events.c.actor_employee_id,
    }.get(sort)
    if order is None or direction not in {"asc", "desc"}:
        raise ApiError(422, "SORT_INVALID", "Invalid sorting")
    result = await session.execute(
        query.order_by(order.asc() if direction == "asc" else order.desc(), audit_events.c.id)
        .offset(offset)
        .limit(limit)
    )
    return [dict(row) for row in result.mappings()]
