"""Minimal Team identities for authorized report filters, not Team record access."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.organization import teams
from app.errors import ApiError
from app.policies import Actor, require


async def team_choices(session: AsyncSession, actor: Actor, page: int, size: int) -> dict:
    require(actor, "report.read")
    if actor.designation not in {"Owner", "Managing Director", "Finance", "Sales Manager"}:
        raise ApiError(403, "FORBIDDEN", "Access denied")
    query = select(teams.c.id, teams.c.name)
    if actor.designation == "Sales Manager":
        query = query.where(
            teams.c.branch_id == actor.branch_id,
            teams.c.department_id == actor.department_id,
        )
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = await session.execute(
        query.order_by(teams.c.name, teams.c.id).offset((page - 1) * size).limit(size)
    )
    return {
        "items": [dict(row) for row in rows.mappings()],
        "total": total,
        "page": page,
        "pageSize": size,
    }
