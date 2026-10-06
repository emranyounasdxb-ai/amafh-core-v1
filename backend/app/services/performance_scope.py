"""Server-owned Performance visibility and historical activity boundaries."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.organization import (
    assignment_history,
    employees,
    team_leader_history,
    team_memberships,
    teams,
)
from app.errors import ApiError
from app.policies import Actor
from app.schemas.performance import PerformanceFilters
from app.services.performance_math import DUBAI, assignment_on, team_on

PERFORMANCE_ROLES = {"Sales Manager", "Coordinator", "Team Leader", "Sales Executive"}
MANAGEMENT_ROLES = {"Owner", "Managing Director"}


@dataclass(frozen=True)
class PerformanceScope:
    actor: Actor
    team_id: UUID | None
    finance_report: bool = False

    def activity_allowed(
        self,
        employee_id: UUID,
        day: date,
        assignment_rows: list[dict],
        membership_rows: list[dict],
        leader_rows: list[dict],
        filters: PerformanceFilters,
    ) -> bool:
        assignment = assignment_on(assignment_rows, day)
        if assignment is None:
            return False
        if filters.branchId is not None and assignment["branch_id"] != filters.branchId:
            return False
        if filters.departmentId is not None and assignment["department_id"] != filters.departmentId:
            return False
        if (
            filters.designationId is not None
            and assignment["designation_id"] != filters.designationId
        ):
            return False
        membership = team_on(membership_rows, day)
        leadership = team_on(leader_rows, day)
        if filters.teamId is not None and not (
            (membership is not None and membership["team_id"] == filters.teamId)
            or (leadership is not None and leadership["team_id"] == filters.teamId)
        ):
            return False
        if self.actor.designation in MANAGEMENT_ROLES or self.finance_report:
            return True
        if self.actor.designation == "Sales Manager":
            return assignment["branch_id"] == self.actor.branch_id and (
                assignment["department_id"] == self.actor.department_id
            )
        if self.actor.designation == "Team Leader":
            if employee_id == self.actor.employee_id:
                return True
            return (
                self.team_id is not None
                and membership is not None
                and (membership["team_id"] == self.team_id)
            )
        return employee_id == self.actor.employee_id


async def resolve(
    session: AsyncSession,
    actor: Actor,
    filters: PerformanceFilters,
    *,
    finance_report: bool = False,
) -> PerformanceScope:
    if actor.designation not in MANAGEMENT_ROLES | PERFORMANCE_ROLES and not (
        finance_report and actor.designation == "Finance"
    ):
        raise ApiError(403, "FORBIDDEN", "Access denied")
    if actor.designation == "Sales Manager" and (
        (filters.branchId is not None and filters.branchId != actor.branch_id)
        or (filters.departmentId is not None and filters.departmentId != actor.department_id)
    ):
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    team_id = None
    if actor.designation == "Team Leader":
        team_id = await session.scalar(
            select(teams.c.id).where(
                teams.c.leader_employee_id == actor.employee_id,
                teams.c.active,
            )
        )
        if filters.teamId is not None and filters.teamId != team_id:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
    if actor.designation in {"Sales Executive", "Coordinator"} and filters.teamId is not None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return PerformanceScope(actor, team_id, finance_report and actor.designation == "Finance")


async def visible_employee_ids(session: AsyncSession, scope: PerformanceScope) -> list[UUID]:
    actor = scope.actor
    if actor.designation in MANAGEMENT_ROLES or scope.finance_report:
        statement = select(employees.c.id)
    elif actor.designation == "Sales Manager":
        formerly_scoped = select(assignment_history.c.employee_id).where(
            assignment_history.c.branch_id == actor.branch_id,
            assignment_history.c.department_id == actor.department_id,
        )
        statement = select(employees.c.id).where(
            (
                (employees.c.branch_id == actor.branch_id)
                & (employees.c.department_id == actor.department_id)
            )
            | employees.c.id.in_(formerly_scoped)
        )
    elif actor.designation == "Team Leader":
        members = select(team_memberships.c.employee_id).where(
            team_memberships.c.team_id == scope.team_id,
            team_memberships.c.end_date.is_(None),
        )
        statement = select(employees.c.id).where(
            (employees.c.id == actor.employee_id)
            | (employees.c.id.in_(members) & (employees.c.status == "Active"))
        )
    else:
        statement = select(employees.c.id).where(employees.c.id == actor.employee_id)
    return list((await session.scalars(statement.order_by(employees.c.id))).all())


def _overlaps(start: date, end: date, row_start: date, row_end: date | None) -> bool:
    return row_start <= end and (row_end is None or row_end > start)


def _population_relevant(
    scope: PerformanceScope,
    employee: dict,
    filters: PerformanceFilters,
    assignments: list[dict],
    memberships: list[dict],
    leaderships: list[dict],
) -> bool:
    start = filters.startDate or employee["date_of_joining"]
    end = filters.endDate or datetime.now(DUBAI).date()
    if start > end:
        return False
    for assignment in assignments:
        if not _overlaps(
            start, end, assignment["assignment_start_date"], assignment["assignment_end_date"]
        ):
            continue
        if filters.branchId is not None and assignment["branch_id"] != filters.branchId:
            continue
        if filters.departmentId is not None and assignment["department_id"] != filters.departmentId:
            continue
        if (
            filters.designationId is not None
            and assignment["designation_id"] != filters.designationId
        ):
            continue
        if scope.actor.designation == "Sales Manager" and (
            assignment["branch_id"] != scope.actor.branch_id
            or assignment["department_id"] != scope.actor.department_id
        ):
            continue
        overlap_start = max(start, assignment["assignment_start_date"])
        overlap_end = min(
            end,
            assignment["assignment_end_date"] - timedelta(days=1)
            if assignment["assignment_end_date"] is not None
            else end,
        )
        if overlap_start > overlap_end:
            continue
        team_id = filters.teamId
        if scope.actor.designation == "Team Leader" and employee["id"] != scope.actor.employee_id:
            team_id = scope.team_id
            relationships = memberships
        else:
            relationships = memberships + leaderships
        if team_id is None or any(
            row["team_id"] == team_id
            and _overlaps(overlap_start, overlap_end, row["start_date"], row["end_date"])
            for row in relationships
        ):
            return True
    return False


async def filtered_employee_ids(
    session: AsyncSession, scope: PerformanceScope, filters: PerformanceFilters
) -> list[UUID]:
    visible = await visible_employee_ids(session, scope)
    if not visible:
        return []
    if (
        not any(
            (
                filters.startDate,
                filters.branchId,
                filters.departmentId,
                filters.teamId,
                filters.designationId,
            )
        )
        and scope.actor.designation != "Team Leader"
    ):
        return visible
    rows = {
        row["id"]: dict(row)
        for row in (
            await session.execute(select(employees).where(employees.c.id.in_(visible)))
        ).mappings()
    }
    assignments: dict[UUID, list[dict]] = {employee_id: [] for employee_id in visible}
    for row in (
        await session.execute(
            select(assignment_history).where(assignment_history.c.employee_id.in_(visible))
        )
    ).mappings():
        assignments[row["employee_id"]].append(dict(row))
    memberships: dict[UUID, list[dict]] = {employee_id: [] for employee_id in visible}
    for row in (
        await session.execute(
            select(team_memberships).where(team_memberships.c.employee_id.in_(visible))
        )
    ).mappings():
        memberships[row["employee_id"]].append(dict(row))
    leaderships: dict[UUID, list[dict]] = {employee_id: [] for employee_id in visible}
    for row in (
        await session.execute(
            select(team_leader_history).where(team_leader_history.c.leader_employee_id.in_(visible))
        )
    ).mappings():
        leaderships[row["leader_employee_id"]].append(dict(row))
    result = []
    for employee_id in visible:
        employee = rows[employee_id]
        history = assignments[employee_id] or [
            {
                "branch_id": employee["branch_id"],
                "department_id": employee["department_id"],
                "designation_id": employee["designation_id"],
                "assignment_start_date": employee["date_of_joining"],
                "assignment_end_date": None,
            }
        ]
        if _population_relevant(
            scope, employee, filters, history, memberships[employee_id], leaderships[employee_id]
        ):
            result.append(employee_id)
    return result


async def require_employee(
    session: AsyncSession, scope: PerformanceScope, employee_id: UUID
) -> dict:
    if employee_id not in await visible_employee_ids(session, scope):
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    row = (
        (await session.execute(select(employees).where(employees.c.id == employee_id)))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return dict(row)
