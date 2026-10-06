"""Readable identity for Performance rows the actor is already authorized to read."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.organization import (
    branches,
    departments,
    designations,
    employees,
    team_memberships,
    teams,
)
from app.policies import Actor, employee_visible


async def _team_member_ids(session: AsyncSession, actor: Actor) -> set[UUID]:
    if actor.designation != "Team Leader":
        return set()
    return set(
        (
            await session.scalars(
                select(team_memberships.c.employee_id)
                .join(teams, teams.c.id == team_memberships.c.team_id)
                .where(
                    teams.c.leader_employee_id == actor.employee_id,
                    teams.c.active.is_(True),
                    team_memberships.c.end_date.is_(None),
                )
            )
        ).all()
    )


async def identities(
    session: AsyncSession, actor: Actor, employee_ids: list[UUID]
) -> dict[UUID, dict]:
    if not employee_ids:
        return {}
    rows = (
        (
            await session.execute(
                select(
                    employees.c.id,
                    employees.c.full_name,
                    employees.c.system_employee_code,
                    employees.c.company_employee_code,
                    employees.c.branch_id,
                    employees.c.department_id,
                    employees.c.avatar_file_id,
                    designations.c.name.label("designation"),
                    branches.c.name.label("branch_name"),
                    departments.c.name.label("department_name"),
                )
                .outerjoin(designations, designations.c.id == employees.c.designation_id)
                .outerjoin(branches, branches.c.id == employees.c.branch_id)
                .outerjoin(departments, departments.c.id == employees.c.department_id)
                .where(employees.c.id.in_(set(employee_ids)))
            )
        )
        .mappings()
        .all()
    )
    members = await _team_member_ids(session, actor)
    return {
        row["id"]: {
            "employeeName": row["full_name"],
            "systemEmployeeCode": row["system_employee_code"],
            "companyEmployeeCode": row["company_employee_code"],
            "designation": row["designation"],
            "branchName": row["branch_name"],
            "departmentName": row["department_name"],
            "avatarFileId": (
                row["avatar_file_id"] if employee_visible(actor, dict(row), members) else None
            ),
        }
        for row in rows
    }


async def attach(session: AsyncSession, actor: Actor, items: list[dict]) -> list[dict]:
    labels = await identities(session, actor, [UUID(str(item["employeeId"])) for item in items])
    return [{**item, **labels.get(UUID(str(item["employeeId"])), {})} for item in items]
