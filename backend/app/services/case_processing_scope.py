"""Hold the live Coordinator assignment stable throughout a Case command."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.organization import designations, employees
from app.errors import ApiError
from app.policies import Actor


async def lock_assignment(session: AsyncSession, actor: Actor) -> None:
    if actor.designation != "Coordinator":
        return
    row = (
        (
            await session.execute(
                select(
                    employees.c.status,
                    employees.c.branch_id,
                    employees.c.department_id,
                    designations.c.name.label("role"),
                )
                .join(designations, employees.c.designation_id == designations.c.id)
                .where(employees.c.id == actor.employee_id)
                .with_for_update(read=True, of=employees)
            )
        )
        .mappings()
        .one_or_none()
    )
    if (
        row is None
        or row["status"] != "Active"
        or row["role"] != "Coordinator"
        or (row["branch_id"] != actor.branch_id or row["department_id"] != actor.department_id)
    ):
        raise ApiError(404, "NOT_FOUND", "Record unavailable")


def current_scope(actor: Actor, case) -> bool:
    return case["branch_id"] == actor.branch_id and case["department_id"] == actor.department_id
