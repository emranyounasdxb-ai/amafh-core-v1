"""Coordinator handling counts and non-identifying peer comparison."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.cases import case_approvals, case_stage_history, cases, product_types
from app.db.organization import assignment_history, designations, employees
from app.errors import ApiError
from app.policies import Actor
from app.schemas.performance import PerformanceFilters
from app.services.performance_math import DUBAI, assignment_on, dubai_date
from app.services.performance_scope import MANAGEMENT_ROLES, resolve
from app.services.public_row_sort import sort_rows
from app.whole_numbers import whole_text


async def _coordinator_id(session: AsyncSession) -> UUID:
    role_id = await session.scalar(
        select(designations.c.id).where(designations.c.name == "Coordinator")
    )
    assert role_id is not None
    return role_id


async def _assignments(session: AsyncSession, employee: dict) -> list[dict]:
    rows = [
        dict(row)
        for row in (
            await session.execute(
                select(assignment_history).where(assignment_history.c.employee_id == employee["id"])
            )
        ).mappings()
    ]
    return rows or [
        {
            "id": employee["id"],
            "branch_id": employee["branch_id"],
            "department_id": employee["department_id"],
            "designation_id": employee["designation_id"],
            "assignment_start_date": employee["date_of_joining"],
            "assignment_end_date": None,
        }
    ]


def _eligible_assignment(
    assignment: dict,
    actor: Actor,
    filters: PerformanceFilters,
    coordinator_id: UUID,
    *,
    own_coordinator: bool,
) -> bool:
    if assignment["designation_id"] != coordinator_id:
        return False
    if filters.designationId is not None and filters.designationId != coordinator_id:
        return False
    if filters.branchId is not None and assignment["branch_id"] != filters.branchId:
        return False
    if filters.departmentId is not None and assignment["department_id"] != filters.departmentId:
        return False
    if actor.designation == "Sales Manager" or (
        actor.designation == "Coordinator" and not own_coordinator
    ):
        return (
            assignment["branch_id"] == actor.branch_id
            and assignment["department_id"] == actor.department_id
        )
    return True


async def _candidate(
    session: AsyncSession,
    actor: Actor,
    employee: dict,
    filters: PerformanceFilters,
    coordinator_id: UUID,
) -> bool:
    start = filters.startDate or employee["date_of_joining"]
    end = filters.endDate or datetime.now(DUBAI).date()
    if start > end or filters.teamId is not None:
        return False
    for row in await _assignments(session, employee):
        if not _eligible_assignment(
            row,
            actor,
            filters,
            coordinator_id,
            own_coordinator=(
                actor.designation == "Coordinator" and employee["id"] == actor.employee_id
            ),
        ):
            continue
        if row["assignment_start_date"] <= end and (
            row["assignment_end_date"] is None or row["assignment_end_date"] > start
        ):
            return True
    return False


async def _metric(
    session: AsyncSession,
    actor: Actor,
    employee: dict,
    filters: PerformanceFilters,
    *,
    finance_report: bool = False,
) -> dict:
    scope = await resolve(session, actor, filters, finance_report=finance_report)
    start = filters.startDate or employee["date_of_joining"]
    end = filters.endDate or datetime.now(DUBAI).date()
    if start > end or end > datetime.now(DUBAI).date():
        raise ApiError(422, "PERFORMANCE_DATE_INVALID", "Date range is unavailable")
    assignments = await _assignments(session, employee)
    coordinator_id = await _coordinator_id(session)

    def allowed(day: date) -> bool:
        if not start <= day <= end:
            return False
        assignment = assignment_on(assignments, day)
        if assignment is None or assignment["designation_id"] != coordinator_id:
            return False
        if filters.teamId is not None or (
            filters.designationId is not None and filters.designationId != coordinator_id
        ):
            return False
        if actor.designation == "Coordinator" and employee["id"] != actor.employee_id:
            return (
                assignment["branch_id"] == actor.branch_id
                and (assignment["department_id"] == actor.department_id)
                and (filters.branchId is None or assignment["branch_id"] == filters.branchId)
                and (
                    filters.departmentId is None
                    or assignment["department_id"] == filters.departmentId
                )
            )
        return scope.activity_allowed(employee["id"], day, assignments, [], [], filters)

    approvals = (
        (
            await session.execute(
                select(case_approvals).where(
                    case_approvals.c.coordinator_employee_id == employee["id"]
                )
            )
        )
        .mappings()
        .all()
    )
    stage_events = (
        (
            await session.execute(
                select(case_stage_history).where(
                    case_stage_history.c.updated_by_employee_id == employee["id"]
                )
            )
        )
        .mappings()
        .all()
    )
    handled = {row["case_id"] for row in approvals if allowed(dubai_date(row["approved_at"]))}
    booked = {
        row["case_id"]
        for row in stage_events
        if row["status"] == "Booked" and (allowed(dubai_date(row["occurred_at"])))
    }
    updated = {
        row["case_id"]
        for row in stage_events
        if row["csv_import_batch_id"] is not None and allowed(dubai_date(row["occurred_at"]))
    }
    if filters.productCode is not None or filters.bankId is not None:
        product_rows = await session.execute(
            select(cases.c.id, product_types.c.code, cases.c.bank_id)
            .select_from(cases.join(product_types, cases.c.product_type_id == product_types.c.id))
            .where(cases.c.id.in_(handled | booked | updated))
        )
        context = {case_id: (code, bank_id) for case_id, code, bank_id in product_rows.all()}

        def included(case_id: UUID) -> bool:
            product, bank = context.get(case_id, (None, None))
            return (filters.productCode is None or product == filters.productCode) and (
                filters.bankId is None or bank == filters.bankId
            )

        handled = {case_id for case_id in handled if included(case_id)}
        booked = {case_id for case_id in booked if included(case_id)}
        updated = {case_id for case_id in updated if included(case_id)}
    return {
        "handledCases": len(handled),
        "submittedBookedCases": len(booked),
        "stageUpdatedCases": len(updated),
    }


async def workload(
    session: AsyncSession,
    actor: Actor,
    employee_id: UUID | None,
    filters: PerformanceFilters,
    *,
    finance_report: bool = False,
) -> dict:
    if actor.designation not in MANAGEMENT_ROLES | {"Sales Manager", "Coordinator"} and not (
        finance_report and actor.designation == "Finance"
    ):
        raise ApiError(403, "FORBIDDEN", "Access denied")
    target_id = employee_id or actor.employee_id
    if actor.designation == "Coordinator" and target_id != actor.employee_id:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    employee = (
        (
            await session.execute(
                select(employees).where(
                    employees.c.id == target_id,
                )
            )
        )
        .mappings()
        .one_or_none()
    )
    if employee is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    coordinator_id = await _coordinator_id(session)
    if not await _candidate(session, actor, dict(employee), filters, coordinator_id):
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    own = await _metric(session, actor, dict(employee), filters, finance_report=finance_report)
    if actor.designation != "Coordinator":
        return {"employeeId": str(target_id), **own}
    peers = (
        (
            await session.execute(
                select(employees).where(
                    employees.c.id != target_id,
                    or_(
                        employees.c.designation_id == coordinator_id,
                        employees.c.id.in_(
                            select(assignment_history.c.employee_id).where(
                                assignment_history.c.designation_id == coordinator_id
                            )
                        ),
                    ),
                )
            )
        )
        .mappings()
        .all()
    )
    peer_counts = [
        await _metric(session, actor, dict(peer), filters)
        for peer in peers
        if await _candidate(session, actor, dict(peer), filters, coordinator_id)
    ]
    averages = {}
    for key in ("handledCases", "submittedBookedCases", "stageUpdatedCases"):
        average = (
            Decimal(sum(row[key] for row in peer_counts)) / len(peer_counts)
            if peer_counts
            else None
        )
        averages[key] = whole_text(average)
    return {
        "employeeId": str(target_id),
        **own,
        "peerAggregate": {"peerCount": len(peer_counts), "average": averages},
    }


async def own_monthly_metric(
    session: AsyncSession, actor: Actor, filters: PerformanceFilters
) -> dict:
    """Own monthly activity includes zeroes before a Coordinator's first assignment."""
    if actor.designation != "Coordinator":
        raise ApiError(403, "FORBIDDEN", "Access denied")
    employee = (
        (await session.execute(select(employees).where(employees.c.id == actor.employee_id)))
        .mappings()
        .one()
    )
    return await _metric(session, actor, dict(employee), filters)


async def list_workload(
    session: AsyncSession,
    actor: Actor,
    filters: PerformanceFilters,
    *,
    page: int,
    page_size: int,
    finance_report: bool = False,
    max_rows: int | None = None,
    sort: str | None = None,
    direction: str = "asc",
) -> dict:
    workload_sorts = {"handledCases", "submittedBookedCases", "stageUpdatedCases"}
    if sort not in {None, "employeeName", "employeeId", *workload_sorts} or direction not in {
        "asc",
        "desc",
    }:
        raise ApiError(422, "SORT_INVALID", "Invalid sorting")
    if actor.designation not in MANAGEMENT_ROLES | {"Sales Manager"} and not (
        finance_report and actor.designation == "Finance"
    ):
        raise ApiError(403, "FORBIDDEN", "Access denied")
    if filters.endDate is not None and filters.endDate > datetime.now(DUBAI).date():
        raise ApiError(422, "PERFORMANCE_DATE_INVALID", "Date range is unavailable")
    await resolve(session, actor, filters, finance_report=finance_report)
    coordinator_id = await _coordinator_id(session)
    historical_ids = select(assignment_history.c.employee_id).where(
        assignment_history.c.designation_id == coordinator_id
    )
    query = select(employees).where(
        or_(employees.c.designation_id == coordinator_id, employees.c.id.in_(historical_ids))
    )
    order = employees.c.full_name if sort == "employeeName" else employees.c.id
    rows = (
        (
            await session.execute(
                query.order_by(order.asc() if direction == "asc" else order.desc(), employees.c.id)
            )
        )
        .mappings()
        .all()
    )
    eligible = [
        row for row in rows if await _candidate(session, actor, dict(row), filters, coordinator_id)
    ]
    if max_rows is not None and len(eligible) > max_rows:
        return {"items": [], "total": len(eligible), "page": page, "pageSize": page_size}
    selected = (
        eligible if sort in workload_sorts else eligible[(page - 1) * page_size : page * page_size]
    )
    items = [
        await workload(session, actor, row["id"], filters, finance_report=finance_report)
        for row in selected
    ]
    if sort in workload_sorts:
        items = sort_rows(items, sort, direction)[(page - 1) * page_size : page * page_size]
    return {"items": items, "total": len(eligible), "page": page, "pageSize": page_size}
