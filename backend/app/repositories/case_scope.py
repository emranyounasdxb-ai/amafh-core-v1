"""Server-side Case visibility predicates shared by Cases and Customers."""

from sqlalchemy import and_, exists, false, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.db.cases import cases
from app.db.organization import designations, employees, team_memberships, teams
from app.policies import Actor


def visible_case(actor: Actor) -> ColumnElement[bool]:
    role = actor.designation
    if role in {"Owner", "Managing Director", "Finance"}:
        return true()
    if role == "Sales Manager":
        return and_(
            cases.c.branch_id == actor.branch_id, cases.c.department_id == actor.department_id
        )
    if role == "Coordinator":
        return or_(
            cases.c.coordinator_employee_id == actor.employee_id,
            and_(
                cases.c.bank_case_number.is_not(None),
                cases.c.owner_transfer_previous_status.is_(None),
                cases.c.branch_id == actor.branch_id,
                cases.c.department_id == actor.department_id,
            ),
        )
    if role == "Team Leader":
        own_team = exists(
            select(team_memberships.c.id)
            .select_from(team_memberships.join(teams, team_memberships.c.team_id == teams.c.id))
            .where(
                team_memberships.c.employee_id == cases.c.owner_employee_id,
                team_memberships.c.end_date.is_(None),
                teams.c.active.is_(True),
                teams.c.leader_employee_id == actor.employee_id,
                teams.c.branch_id == actor.branch_id,
                teams.c.department_id == actor.department_id,
            )
        )
        return or_(cases.c.owner_employee_id == actor.employee_id, own_team)
    if role == "Sales Executive":
        return cases.c.owner_employee_id == actor.employee_id
    return false()


def own_case(actor: Actor) -> ColumnElement[bool]:
    """Own Cases: the actor's Cases, plus their Team's Sales Executives' Cases for a Team Leader."""
    mine = cases.c.owner_employee_id == actor.employee_id
    if actor.designation != "Team Leader":
        return mine
    team_sales_executive = exists(
        select(team_memberships.c.id)
        .select_from(
            team_memberships.join(teams, team_memberships.c.team_id == teams.c.id)
            .join(employees, employees.c.id == team_memberships.c.employee_id)
            .join(designations, designations.c.id == employees.c.designation_id)
        )
        .where(
            team_memberships.c.employee_id == cases.c.owner_employee_id,
            team_memberships.c.end_date.is_(None),
            teams.c.active.is_(True),
            teams.c.leader_employee_id == actor.employee_id,
            teams.c.branch_id == actor.branch_id,
            teams.c.department_id == actor.department_id,
            designations.c.name == "Sales Executive",
        )
    )
    return or_(mine, team_sales_executive)


def case_access(actor: Actor) -> ColumnElement[bool]:
    """Cases the actor may open: their Case viewing scope plus their Own Cases."""
    own = own_case(actor)
    return or_(visible_case(actor), own) if "case.read" in actor.grants else own


async def can_own_for_creator(session: AsyncSession, actor: Actor, owner_id) -> bool:
    if owner_id == actor.employee_id:
        return True
    if actor.designation != "Team Leader":
        return False
    row = await session.scalar(
        select(team_memberships.c.id)
        .select_from(team_memberships.join(teams, team_memberships.c.team_id == teams.c.id))
        .where(
            team_memberships.c.employee_id == owner_id,
            team_memberships.c.end_date.is_(None),
            teams.c.active.is_(True),
            teams.c.leader_employee_id == actor.employee_id,
            teams.c.branch_id == actor.branch_id,
            teams.c.department_id == actor.department_id,
        )
    )
    return row is not None
