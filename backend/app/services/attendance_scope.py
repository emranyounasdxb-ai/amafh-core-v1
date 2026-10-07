"""Date-effective employment and retained Branch assignment for attendance."""

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.organization import assignment_history, employees
from app.errors import ApiError


async def eligible_employees(session: AsyncSession, branch_id: UUID, on_date: date) -> list[dict]:
    history = (
        (
            await session.execute(
                select(assignment_history).order_by(
                    assignment_history.c.assignment_start_date.desc(),
                    assignment_history.c.created_at.desc(),
                )
            )
        )
        .mappings()
        .all()
    )
    by_employee: dict[UUID, list] = {}
    for item in history:
        by_employee.setdefault(item["employee_id"], []).append(item)
    candidates = (
        (
            await session.execute(
                select(
                    employees.c.id,
                    employees.c.system_employee_code,
                    employees.c.full_name,
                    employees.c.branch_id,
                    employees.c.status,
                    employees.c.last_working_date,
                )
                .where(
                    employees.c.date_of_joining <= on_date,
                    employees.c.status.in_(("Active", "Offboarded")),
                )
                .order_by(employees.c.system_employee_code)
            )
        )
        .mappings()
        .all()
    )
    result = []
    for row in candidates:
        retained = by_employee.get(row["id"], [])
        possible_branches = {row["branch_id"], *(item["branch_id"] for item in retained)}
        if branch_id not in possible_branches:
            continue
        last_day = row["last_working_date"]
        if row["status"] == "Offboarded":
            if last_day is None:
                raise ApiError(
                    422,
                    "ATTENDANCE_HISTORY_REQUIRED",
                    "Last working date evidence is required for this Branch",
                )
            if on_date > last_day:
                continue
        effective = [
            item
            for item in retained
            if item["assignment_start_date"] <= on_date
            and (item["assignment_end_date"] is None or item["assignment_end_date"] > on_date)
        ]
        # Transfers remain end-exclusive. Only the terminal offboarding assignment
        # may include its last working date; never include an old transfer row.
        if not effective and row["status"] == "Offboarded" and on_date == last_day and retained:
            terminal = retained[0]
            terminal_rows = [
                item
                for item in retained
                if item["assignment_start_date"] == terminal["assignment_start_date"]
                and item["created_at"] == terminal["created_at"]
            ]
            if (
                len(terminal_rows) == 1
                and terminal["assignment_start_date"] <= on_date
                and terminal["assignment_end_date"] == last_day
            ):
                effective = [terminal]
        if len(effective) != 1:
            raise ApiError(
                422,
                "ATTENDANCE_HISTORY_REQUIRED",
                "Unambiguous retained assignment evidence is required for this Branch and date",
            )
        if effective[0]["branch_id"] == branch_id:
            result.append(dict(row))
    return result
