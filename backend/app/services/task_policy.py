"""Task assignment, management, and linked-record access policy."""

from uuid import UUID

from sqlalchemy import and_, exists, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.assets import assets
from app.db.attendance import attendance_records, csv_import_batches
from app.db.cases import cases, customers
from app.db.finance import case_financial_results
from app.db.operations import clawbacks, payment_records
from app.db.organization import designations, employees, team_memberships, teams
from app.db.tasks import tasks
from app.errors import ApiError
from app.policies import Actor, employee_visible
from app.repositories import permissions as permission_rows
from app.repositories.case_scope import visible_case
from app.services.customer_read import _authorized_customer

LEADERS = {"Owner", "Managing Director"}
ACTIVE = {"Open", "In Progress"}


async def employee_actor(session: AsyncSession, employee_id: UUID) -> Actor:
    row = (
        (
            await session.execute(
                select(employees, designations.c.name.label("designation"))
                .join(designations, designations.c.id == employees.c.designation_id)
                .where(employees.c.id == employee_id, employees.c.status == "Active")
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None or row["branch_id"] is None or row["department_id"] is None:
        raise ApiError(422, "ASSIGNEE_UNAVAILABLE", "Assignee unavailable")
    return Actor(
        account_id=UUID(int=0),
        employee_id=employee_id,
        designation=row["designation"],
        display_name=row["full_name"],
        branch_id=row["branch_id"],
        department_id=row["department_id"],
        session_id=UUID(int=0),
        csrf_hash="",
        grants=await permission_rows.actor_grants(session, row["designation"]),
    )


async def current_team(session: AsyncSession, actor: Actor, employee_id: UUID) -> UUID | None:
    return await session.scalar(
        select(teams.c.id)
        .select_from(teams.join(team_memberships, team_memberships.c.team_id == teams.c.id))
        .where(
            teams.c.leader_employee_id == actor.employee_id,
            teams.c.active.is_(True),
            teams.c.branch_id == actor.branch_id,
            teams.c.department_id == actor.department_id,
            team_memberships.c.employee_id == employee_id,
            team_memberships.c.end_date.is_(None),
        )
        .limit(1)
    )


async def assignee_team(session: AsyncSession, employee_id: UUID) -> UUID | None:
    return await session.scalar(
        select(teams.c.id)
        .select_from(teams.join(team_memberships, team_memberships.c.team_id == teams.c.id))
        .where(
            teams.c.active.is_(True),
            team_memberships.c.employee_id == employee_id,
            team_memberships.c.end_date.is_(None),
        )
        .limit(1)
    )


async def assignment_scope(session: AsyncSession, actor: Actor, assignee_id: UUID) -> dict:
    assignee = await employee_actor(session, assignee_id)
    if assignee_id != actor.employee_id and actor.designation not in LEADERS:
        if actor.designation == "Sales Manager":
            allowed = (
                actor.branch_id == assignee.branch_id
                and actor.department_id == assignee.department_id
            )
        elif actor.designation == "Team Leader":
            allowed = assignee.designation == "Sales Executive" and bool(
                await current_team(session, actor, assignee_id)
            )
        else:
            allowed = False
        if not allowed:
            raise ApiError(403, "FORBIDDEN", "Assignee unavailable")
    return {
        "assignee": assignee,
        "branch_id": assignee.branch_id,
        "department_id": assignee.department_id,
        "team_id": await assignee_team(session, assignee_id),
    }


def visible_task(actor: Actor):
    if actor.designation in LEADERS:
        return true()
    own = or_(
        tasks.c.creator_employee_id == actor.employee_id,
        tasks.c.assignee_employee_id == actor.employee_id,
    )
    if actor.designation == "Sales Manager":
        current = exists(
            select(employees.c.id).where(
                employees.c.id == tasks.c.assignee_employee_id,
                employees.c.branch_id == actor.branch_id,
                employees.c.department_id == actor.department_id,
            )
        )
        scope = or_(
            and_(tasks.c.status.in_(ACTIVE), current),
            and_(
                tasks.c.status.not_in(ACTIVE),
                tasks.c.branch_id == actor.branch_id,
                tasks.c.department_id == actor.department_id,
            ),
        )
        return scope
    if actor.designation == "Team Leader":
        current_member = exists(
            select(team_memberships.c.id)
            .select_from(team_memberships.join(teams, teams.c.id == team_memberships.c.team_id))
            .where(
                team_memberships.c.employee_id == tasks.c.assignee_employee_id,
                team_memberships.c.end_date.is_(None),
                teams.c.active.is_(True),
                teams.c.leader_employee_id == actor.employee_id,
                teams.c.branch_id == actor.branch_id,
                teams.c.department_id == actor.department_id,
            )
        )
        historical_team = exists(
            select(teams.c.id).where(
                teams.c.id == tasks.c.team_id,
                teams.c.leader_employee_id == actor.employee_id,
                teams.c.active.is_(True),
            )
        )
        own_current = and_(
            own,
            tasks.c.branch_id == actor.branch_id,
            tasks.c.department_id == actor.department_id,
        )
        return or_(
            own_current,
            and_(tasks.c.status.in_(ACTIVE), current_member),
            and_(tasks.c.status.not_in(ACTIVE), historical_team),
        )
    return own


async def may_manage(session: AsyncSession, actor: Actor, task: dict) -> bool:
    if actor.employee_id == task["creator_employee_id"] or actor.designation in LEADERS:
        return True
    assignee_id = task["assignee_employee_id"]
    if actor.designation == "Sales Manager":
        assignee = await session.execute(
            select(employees.c.branch_id, employees.c.department_id).where(
                employees.c.id == assignee_id
            )
        )
        row = assignee.one_or_none()
        return bool(
            row and row.branch_id == actor.branch_id and row.department_id == actor.department_id
        )
    if actor.designation == "Team Leader":
        return bool(await current_team(session, actor, assignee_id))
    return False


async def may_link(session: AsyncSession, actor: Actor, kind: str, record_id: UUID) -> bool:
    if kind == "case":
        if "case.read" not in actor.grants:
            return False
        return (
            await session.scalar(
                select(cases.c.id).where(cases.c.id == record_id, visible_case(actor))
            )
            is not None
        )
    if kind == "customer":
        if "case.read" not in actor.grants:
            return False
        return (
            await session.scalar(
                select(customers.c.id).where(
                    customers.c.id == record_id, _authorized_customer(actor)
                )
            )
            is not None
        )
    if kind == "employee":
        if "employee.read" not in actor.grants:
            return False
        row = (
            (await session.execute(select(employees).where(employees.c.id == record_id)))
            .mappings()
            .one_or_none()
        )
        if row is None:
            return False
        team_ids = set()
        if actor.designation == "Team Leader":
            team_ids = set(
                (
                    await session.execute(
                        select(team_memberships.c.employee_id)
                        .select_from(
                            team_memberships.join(teams, teams.c.id == team_memberships.c.team_id)
                        )
                        .where(
                            teams.c.leader_employee_id == actor.employee_id,
                            teams.c.active.is_(True),
                            team_memberships.c.end_date.is_(None),
                        )
                    )
                ).scalars()
            )
        return employee_visible(actor, dict(row), team_ids)
    if kind in {"asset", "attendance", "attendance_import"}:
        if actor.designation not in LEADERS | {"Admin Staff"}:
            return False
        table = {
            "asset": assets,
            "attendance": attendance_records,
            "attendance_import": csv_import_batches,
        }[kind]
        query = select(table.c.id).where(table.c.id == record_id)
        if kind == "attendance_import":
            query = query.where(csv_import_batches.c.kind == "attendance")
        if actor.designation == "Admin Staff":
            query = query.where(table.c.branch_id == actor.branch_id)
        return await session.scalar(query) is not None
    if kind in {"finance_result", "clawback", "payment"}:
        if actor.designation not in LEADERS | {"Finance", "Sales Manager"}:
            return False
        if kind == "payment":
            source = payment_records.join(
                employees, employees.c.id == payment_records.c.employee_id
            )
            query = (
                select(payment_records.c.id)
                .select_from(source)
                .where(payment_records.c.id == record_id)
            )
            if actor.designation == "Sales Manager":
                query = query.where(
                    employees.c.branch_id == actor.branch_id,
                    employees.c.department_id == actor.department_id,
                )
        else:
            table = case_financial_results if kind == "finance_result" else clawbacks
            source = table.join(cases, cases.c.id == table.c.case_id)
            query = select(table.c.id).select_from(source).where(table.c.id == record_id)
            if actor.designation == "Sales Manager":
                query = query.where(
                    cases.c.branch_id == actor.branch_id,
                    cases.c.department_id == actor.department_id,
                )
        return await session.scalar(query) is not None
    return False
