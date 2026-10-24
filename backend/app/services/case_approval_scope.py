"""Keep the live manager/reporting relationship stable through approval commit."""

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.cases import cases
from app.db.organization import designations, employees, team_memberships, teams
from app.errors import ApiError
from app.policies import Actor
from app.repositories.case_scope import visible_case


async def lock_manager(session: AsyncSession, actor: Actor) -> None:
    if actor.designation != "Sales Manager":
        return
    row = (
        (
            await session.execute(
                select(employees, designations.c.name.label("role"))
                .join(designations, designations.c.id == employees.c.designation_id)
                .where(employees.c.id == actor.employee_id)
                .with_for_update(read=True, key_share=True, of=employees)
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None or (
        row["status"] != "Active"
        or row["role"] != actor.designation
        or row["branch_id"] != actor.branch_id
        or row["department_id"] != actor.department_id
    ):
        raise ApiError(404, "NOT_FOUND", "Record unavailable")


async def require_case(session: AsyncSession, actor: Actor, row) -> None:
    if actor.designation != "Sales Manager":
        return
    if row["branch_id"] != actor.branch_id:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    if row["department_id"] != actor.department_id:
        owner = (
            (
                await session.execute(
                    select(employees)
                    .where(employees.c.id == row["owner_employee_id"])
                    .with_for_update(read=True, key_share=True, of=employees)
                )
            )
            .mappings()
            .one_or_none()
        )
        if owner is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
        if owner["reporting_manager_id"] != actor.employee_id:
            # Freeze the explicit active Team path too. Team commands lock Team
            # before membership; assignment commands first lock the employee.
            link = (
                (
                    await session.execute(
                        select(
                            team_memberships.c.id,
                            teams.c.id.label("team_id"),
                            teams.c.leader_employee_id,
                        )
                        .join(teams, teams.c.id == team_memberships.c.team_id)
                        .where(
                            team_memberships.c.employee_id == owner["id"],
                            team_memberships.c.end_date.is_(None),
                            teams.c.active.is_(True),
                        )
                    )
                )
                .mappings()
                .one_or_none()
            )
            if link is None:
                raise ApiError(404, "NOT_FOUND", "Record unavailable")
            await session.execute(
                select(employees.c.id)
                .where(employees.c.id == link["leader_employee_id"])
                .with_for_update(read=True, key_share=True, of=employees)
            )
            try:
                team = (
                    (
                        await session.execute(
                            select(teams)
                            .where(teams.c.id == link["team_id"])
                            # Team reassignment locks the Team before the new
                            # leader. Do not wait while holding employee locks.
                            .with_for_update(read=True, of=teams, nowait=True)
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
            except DBAPIError as error:
                if getattr(error.orig, "sqlstate", None) != "55P03":
                    raise
                raise ApiError(
                    409, "ASSIGNMENT_CHANGING", "Reporting assignment is changing. Retry approval."
                ) from None
            if team is None or team["leader_employee_id"] != link["leader_employee_id"]:
                raise ApiError(404, "NOT_FOUND", "Record unavailable")
            member = (
                (
                    await session.execute(
                        select(team_memberships)
                        .where(team_memberships.c.id == link["id"])
                        .with_for_update(read=True, of=team_memberships)
                    )
                )
                .mappings()
                .one_or_none()
            )
            if member is None or member["end_date"] is not None:
                raise ApiError(404, "NOT_FOUND", "Record unavailable")
    if (
        await session.scalar(select(cases.c.id).where(cases.c.id == row["id"], visible_case(actor)))
        is None
    ):
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
