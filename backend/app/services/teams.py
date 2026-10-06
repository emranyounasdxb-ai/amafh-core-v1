"""Team creation and effective-dated membership commands."""

from uuid import UUID, uuid4

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
from app.policies import Actor, require
from app.schemas.organization import TeamCreate
from app.services.notification_events import notify
from app.services.organization import _department_in_branch, dubai_today


async def create_team(session: AsyncSession, actor: Actor, item: TeamCreate) -> UUID:
    require(actor, "team.write")
    await _department_in_branch(session, item.branchId, item.departmentId)
    leader = (
        (
            await session.execute(
                select(employees, designations.c.name.label("role"))
                .join(designations, employees.c.designation_id == designations.c.id)
                .where(employees.c.id == item.leaderEmployeeId)
                .with_for_update(of=employees)
            )
        )
        .mappings()
        .first()
    )
    if (
        not leader
        or leader["role"] != "Team Leader"
        or leader["branch_id"] != item.branchId
        or leader["department_id"] != item.departmentId
        or leader["status"] != "Active"
    ):
        raise ApiError(422, "INVALID_LEADER", "Invalid Team Leader")
    team_id = uuid4()
    await session.execute(
        teams.insert().values(
            id=team_id,
            name=item.name,
            branch_id=item.branchId,
            department_id=item.departmentId,
            leader_employee_id=item.leaderEmployeeId,
        )
    )
    await session.execute(
        team_leader_history.insert().values(
            team_id=team_id,
            leader_employee_id=item.leaderEmployeeId,
            start_date=dubai_today(),
        )
    )
    await audit.record(
        session,
        actor=actor.employee_id,
        action="team.created",
        module="teams",
        entity_type="team",
        entity_id=team_id,
        after={"name": item.name},
    )
    await session.commit()
    return team_id


async def add_team_member(
    session: AsyncSession, actor: Actor, team_id: UUID, employee_id: UUID, start_date
) -> None:
    require(actor, "team.write")
    if start_date != dubai_today():
        raise ApiError(422, "INVALID_START_DATE", "Membership changes must take effect today")
    member = (
        (
            await session.execute(
                select(employees, designations.c.name.label("role"))
                .join(designations, employees.c.designation_id == designations.c.id)
                .where(employees.c.id == employee_id)
                .with_for_update(of=employees)
            )
        )
        .mappings()
        .first()
    )
    team = (
        (
            await session.execute(
                select(teams)
                .where(teams.c.id == team_id, teams.c.active.is_(True))
                .with_for_update()
            )
        )
        .mappings()
        .first()
    )
    if (
        not team
        or not member
        or member["role"] != "Sales Executive"
        or member["branch_id"] != team["branch_id"]
        or member["department_id"] != team["department_id"]
        or member["status"] != "Active"
    ):
        raise ApiError(422, "INVALID_MEMBERSHIP", "Invalid Team membership")
    await session.execute(
        team_memberships.insert().values(
            team_id=team_id, employee_id=employee_id, start_date=start_date
        )
    )
    await audit.record(
        session,
        actor=actor.employee_id,
        action="team.member_added",
        module="teams",
        entity_type="team",
        entity_id=team_id,
        after={"employeeId": str(employee_id)},
    )
    await notify(
        session,
        {employee_id, team["leader_employee_id"]},
        "team.membership_changed",
        "A Team membership was updated",
        team_id=team_id,
    )
    await session.commit()


async def end_team_member(
    session: AsyncSession, actor: Actor, team_id: UUID, employee_id: UUID
) -> None:
    require(actor, "team.write")
    leader_id = await session.scalar(
        select(teams.c.leader_employee_id).where(teams.c.id == team_id)
    )
    result = await session.execute(
        update(team_memberships)
        .where(
            team_memberships.c.team_id == team_id,
            team_memberships.c.employee_id == employee_id,
            team_memberships.c.end_date.is_(None),
        )
        .values(end_date=dubai_today())
        .returning(team_memberships.c.id)
    )
    if not result.scalar_one_or_none():
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    await audit.record(
        session,
        actor=actor.employee_id,
        action="team.member_ended",
        module="teams",
        entity_type="team",
        entity_id=team_id,
        after={"employeeId": str(employee_id)},
    )
    await notify(
        session,
        {employee_id} | ({leader_id} if leader_id is not None else set()),
        "team.membership_changed",
        "A Team membership was updated",
        team_id=team_id,
    )
    await session.commit()
