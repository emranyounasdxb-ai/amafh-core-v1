"""Team rename, deactivation and Leader tenure transitions."""

from uuid import UUID

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
from app.services.organization import dubai_today


async def _active_team(session: AsyncSession, team_id: UUID):
    row = (
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
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Active Team unavailable")
    return row


async def rename(session: AsyncSession, actor: Actor, team_id: UUID, name: str) -> None:
    require(actor, "team.write")
    team = await _active_team(session, team_id)
    try:
        await session.execute(update(teams).where(teams.c.id == team_id).values(name=name))
        await audit.record(
            session,
            actor=actor.employee_id,
            action="team.updated",
            module="teams",
            entity_type="team",
            entity_id=team_id,
            before={"name": team["name"]},
            after={"name": name},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def deactivate(session: AsyncSession, actor: Actor, team_id: UUID) -> None:
    require(actor, "team.write")
    await _active_team(session, team_id)
    today = dubai_today()
    try:
        await session.execute(update(teams).where(teams.c.id == team_id).values(active=False))
        await session.execute(
            update(team_memberships)
            .where(team_memberships.c.team_id == team_id, team_memberships.c.end_date.is_(None))
            .values(end_date=today)
        )
        await session.execute(
            update(team_leader_history)
            .where(
                team_leader_history.c.team_id == team_id, team_leader_history.c.end_date.is_(None)
            )
            .values(end_date=today)
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="team.deactivated",
            module="teams",
            entity_type="team",
            entity_id=team_id,
            before={"active": True},
            after={"active": False},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def reassign_leader(
    session: AsyncSession, actor: Actor, team_id: UUID, new_leader_id: UUID, effective_date
) -> None:
    require(actor, "team.write")
    if effective_date != dubai_today():
        raise ApiError(422, "INVALID_EFFECTIVE_DATE", "Leader reassignment takes effect today")
    team = await _active_team(session, team_id)
    if team["leader_employee_id"] == new_leader_id:
        raise ApiError(409, "CONFLICT", "Employee already leads this Team")
    leader = (
        (
            await session.execute(
                select(employees, designations.c.name.label("role"))
                .join(designations, employees.c.designation_id == designations.c.id)
                .where(employees.c.id == new_leader_id)
                .with_for_update(of=employees)
            )
        )
        .mappings()
        .first()
    )
    if (
        not leader
        or leader["status"] != "Active"
        or leader["role"] != "Team Leader"
        or leader["branch_id"] != team["branch_id"]
        or leader["department_id"] != team["department_id"]
    ):
        raise ApiError(422, "INVALID_LEADER", "Active same-scope Team Leader required")
    try:
        await session.execute(
            update(team_leader_history)
            .where(
                team_leader_history.c.team_id == team_id, team_leader_history.c.end_date.is_(None)
            )
            .values(end_date=effective_date)
        )
        await session.execute(
            team_leader_history.insert().values(
                team_id=team_id,
                leader_employee_id=new_leader_id,
                start_date=effective_date,
            )
        )
        await session.execute(
            update(teams).where(teams.c.id == team_id).values(leader_employee_id=new_leader_id)
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="team.leader_reassigned",
            module="teams",
            entity_type="team",
            entity_id=team_id,
            before={"leaderEmployeeId": str(team["leader_employee_id"])},
            after={"leaderEmployeeId": str(new_leader_id)},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
