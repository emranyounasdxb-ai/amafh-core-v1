"""Validate manager scope and close Team relationships made invalid by employee changes."""

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.organization import (
    designations,
    employees,
    team_leader_history,
    team_memberships,
    teams,
)
from app.errors import ApiError
from app.policies import Actor
from app.services.notification_events import notify


def _eligible_manager(
    manager_role: str,
    manager_branch: UUID | None,
    manager_department: UUID | None,
    employee_role: str,
    employee_branch: UUID | None,
    employee_department: UUID | None,
) -> bool:
    if manager_role in {"Owner", "Managing Director"}:
        return True
    same_scope = (
        manager_branch is not None
        and manager_department is not None
        and manager_branch == employee_branch
        and manager_department == employee_department
    )
    return same_scope and (
        manager_role == "Sales Manager"
        or (manager_role == "Team Leader" and employee_role == "Sales Executive")
    )


async def validate_manager(
    session: AsyncSession,
    employee_id: UUID,
    manager_id: UUID | None,
    branch_id: UUID | None,
    department_id: UUID | None,
    designation_id: UUID,
) -> None:
    if manager_id is None:
        return
    if manager_id == employee_id:
        raise ApiError(422, "INVALID_MANAGER", "Employee cannot report to themself")
    manager = (
        (
            await session.execute(
                select(employees, designations.c.name.label("role"))
                .join(designations, employees.c.designation_id == designations.c.id)
                .where(employees.c.id == manager_id)
                .with_for_update(of=employees)
            )
        )
        .mappings()
        .first()
    )
    role = await session.scalar(
        select(designations.c.name).where(designations.c.id == designation_id)
    )
    if not manager or manager["status"] != "Active":
        raise ApiError(422, "INVALID_MANAGER", "Reporting Manager must be active")
    if not _eligible_manager(
        manager["role"],
        manager["branch_id"],
        manager["department_id"],
        role or "",
        branch_id,
        department_id,
    ):
        raise ApiError(422, "INVALID_MANAGER", "Reporting Manager is outside the approved scope")


async def guard_direct_reports(
    session: AsyncSession,
    manager_id: UUID,
    role: str,
    branch_id: UUID | None,
    department_id: UUID | None,
    status: str,
) -> None:
    reports = (
        await session.execute(
            select(
                employees.c.branch_id, employees.c.department_id, designations.c.name.label("role")
            )
            .join(designations, employees.c.designation_id == designations.c.id)
            .where(
                employees.c.reporting_manager_id == manager_id,
                employees.c.status != "Offboarded",
            )
        )
    ).mappings()
    for report in reports:
        if status != "Active" or not _eligible_manager(
            role,
            branch_id,
            department_id,
            report["role"],
            report["branch_id"],
            report["department_id"],
        ):
            raise ApiError(409, "MANAGER_IN_USE", "Reassign direct reports before this change")


async def reconcile_teams(
    session: AsyncSession,
    actor: Actor,
    employee_id: UUID,
    branch_id: UUID | None,
    department_id: UUID | None,
    role: str,
    status: str,
) -> None:
    """Close affected relationships while retaining every historical row."""
    today = datetime.now(ZoneInfo("Asia/Dubai")).date()
    led = (
        (
            await session.execute(
                select(teams)
                .where(teams.c.leader_employee_id == employee_id, teams.c.active.is_(True))
                .with_for_update()
            )
        )
        .mappings()
        .all()
    )
    for team in led:
        if (
            status == "Active"
            and role == "Team Leader"
            and team["branch_id"] == branch_id
            and team["department_id"] == department_id
        ):
            continue
        await session.execute(update(teams).where(teams.c.id == team["id"]).values(active=False))
        await session.execute(
            update(team_leader_history)
            .where(
                team_leader_history.c.team_id == team["id"],
                team_leader_history.c.end_date.is_(None),
            )
            .values(end_date=today)
        )
        member_ids = set(
            (
                await session.scalars(
                    select(team_memberships.c.employee_id).where(
                        team_memberships.c.team_id == team["id"],
                        team_memberships.c.end_date.is_(None),
                    )
                )
            ).all()
        )
        await session.execute(
            update(team_memberships)
            .where(team_memberships.c.team_id == team["id"], team_memberships.c.end_date.is_(None))
            .values(end_date=today)
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="team.deactivated_on_assignment",
            module="teams",
            entity_type="team",
            entity_id=team["id"],
            before={"active": True},
            after={"active": False},
        )
        await notify(
            session,
            member_ids | {team["leader_employee_id"]},
            "team.membership_changed",
            "A Team membership was updated",
            team_id=team["id"],
        )
    memberships = (
        (
            await session.execute(
                select(
                    team_memberships.c.id,
                    team_memberships.c.team_id,
                    teams.c.branch_id,
                    teams.c.department_id,
                    teams.c.leader_employee_id,
                )
                .join(teams, team_memberships.c.team_id == teams.c.id)
                .where(
                    team_memberships.c.employee_id == employee_id,
                    team_memberships.c.end_date.is_(None),
                )
                .with_for_update(of=team_memberships)
            )
        )
        .mappings()
        .all()
    )
    for member in memberships:
        if (
            status == "Active"
            and role == "Sales Executive"
            and member["branch_id"] == branch_id
            and member["department_id"] == department_id
        ):
            continue
        await session.execute(
            update(team_memberships)
            .where(team_memberships.c.id == member["id"])
            .values(end_date=today)
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="team.member_ended_on_assignment",
            module="teams",
            entity_type="team",
            entity_id=member["team_id"],
            before={"employeeId": str(employee_id), "active": True},
            after={"employeeId": str(employee_id), "active": False},
        )
        await notify(
            session,
            {employee_id, member["leader_employee_id"]},
            "team.membership_changed",
            "A Team membership was updated",
            team_id=member["team_id"],
        )
