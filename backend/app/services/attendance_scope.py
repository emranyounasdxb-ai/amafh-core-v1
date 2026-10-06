"""Eligible Active employees by retained Branch assignment on a Dubai date."""

from datetime import date
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.organization import assignment_history, employees


async def eligible_employees(session: AsyncSession, branch_id: UUID, on_date: date) -> list[dict]:
    all_with_history = set(
        (await session.execute(select(assignment_history.c.employee_id).distinct())).scalars()
    )
    effective_rows = (
        await session.execute(
            select(assignment_history.c.employee_id, assignment_history.c.branch_id)
            .where(
                assignment_history.c.assignment_start_date <= on_date,
                or_(
                    assignment_history.c.assignment_end_date.is_(None),
                    assignment_history.c.assignment_end_date > on_date,
                ),
            )
            .order_by(
                assignment_history.c.assignment_start_date.desc(),
                assignment_history.c.created_at.desc(),
            )
        )
    ).all()
    historical_branch: dict[UUID, UUID | None] = {}
    for row in effective_rows:
        historical_branch.setdefault(row.employee_id, row.branch_id)
    active = (
        (
            await session.execute(
                select(
                    employees.c.id,
                    employees.c.system_employee_code,
                    employees.c.full_name,
                    employees.c.branch_id,
                )
                .where(employees.c.status == "Active", employees.c.date_of_joining <= on_date)
                .order_by(employees.c.system_employee_code)
            )
        )
        .mappings()
        .all()
    )
    return [
        dict(row)
        for row in active
        if (historical_branch.get(row["id"]) if row["id"] in all_with_history else row["branch_id"])
        == branch_id
    ]
