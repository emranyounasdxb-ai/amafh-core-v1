"""Scoped retained employee-assignment and lifetime-payment report projections."""

from datetime import date

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.operations import payment_records
from app.db.organization import assignment_history, designations, employees
from app.errors import ApiError
from app.policies import Actor
from app.services.report_history import assignment_id_on, scope_value_on


async def assignment_report(
    session: AsyncSession,
    filters,
    start: date,
    end: date,
    page: int,
    size: int,
    max_rows: int | None = None,
    sort: str | None = None,
    direction: str = "asc",
) -> tuple[list[dict], int, dict]:
    source = assignment_history.join(
        employees, employees.c.id == assignment_history.c.employee_id
    ).join(designations, designations.c.id == assignment_history.c.designation_id)
    predicates = [
        assignment_history.c.assignment_start_date <= end,
        or_(
            assignment_history.c.assignment_end_date.is_(None),
            assignment_history.c.assignment_end_date > start,
        ),
    ]
    if filters.branchId is not None:
        predicates.append(assignment_history.c.branch_id == filters.branchId)
    if filters.departmentId is not None:
        predicates.append(assignment_history.c.department_id == filters.departmentId)
    if filters.designationId is not None:
        predicates.append(assignment_history.c.designation_id == filters.designationId)
    if filters.status is not None:
        if filters.status not in {"Pending Setup", "Active", "Offboarded"}:
            raise ApiError(422, "REPORT_FILTER_INVALID", "Employee status is invalid")
        predicates.append(employees.c.status == filters.status)
    query = (
        select(
            employees.c.system_employee_code,
            employees.c.full_name,
            assignment_history.c.branch_id,
            assignment_history.c.department_id,
            designations.c.name.label("designation"),
            assignment_history.c.assignment_start_date,
            assignment_history.c.assignment_end_date,
        )
        .select_from(source)
        .where(*predicates)
    )
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    if max_rows is not None and total > max_rows:
        return [], total, {}
    order = (
        {
            "systemEmployeeCode": employees.c.system_employee_code,
            "employeeName": employees.c.full_name,
            "branchId": assignment_history.c.branch_id,
            "departmentId": assignment_history.c.department_id,
            "designation": designations.c.name,
            "startDate": assignment_history.c.assignment_start_date,
            "endDate": assignment_history.c.assignment_end_date,
        }.get(sort)
        if sort is not None
        else None
    )
    rows = (
        (
            await session.execute(
                query.order_by(
                    (order.asc() if direction == "asc" else order.desc()).nulls_last()
                    if order is not None
                    else assignment_history.c.assignment_start_date.desc(),
                    assignment_history.c.id,
                )
                .offset((page - 1) * size)
                .limit(size)
            )
        )
        .mappings()
        .all()
    )
    return (
        [
            {
                "systemEmployeeCode": row["system_employee_code"],
                "employeeName": row["full_name"],
                "branchId": row["branch_id"],
                "departmentId": row["department_id"],
                "designation": row["designation"],
                "startDate": row["assignment_start_date"],
                "endDate": row["assignment_end_date"],
            }
            for row in rows
        ],
        total,
        {"assignmentCount": total},
    )


async def paid_totals(
    session: AsyncSession,
    actor: Actor,
    filters,
    start: date,
    end: date,
    page: int,
    size: int,
    max_rows: int | None = None,
    sort: str | None = None,
    direction: str = "asc",
) -> tuple[list[dict], int, dict]:
    source = payment_records.outerjoin(
        assignment_history,
        assignment_history.c.id
        == assignment_id_on(payment_records.c.employee_id, payment_records.c.payment_date),
    )
    branch = scope_value_on(
        payment_records.c.employee_id,
        payment_records.c.payment_date,
        payment_records.c.created_at,
        "branch_id",
    )
    department = scope_value_on(
        payment_records.c.employee_id,
        payment_records.c.payment_date,
        payment_records.c.created_at,
        "department_id",
    )
    scope = []
    if actor.designation == "Sales Manager":
        scope += [branch == actor.branch_id, department == actor.department_id]
    if filters.branchId is not None:
        scope.append(branch == filters.branchId)
    if filters.departmentId is not None:
        scope.append(department == filters.departmentId)
    if filters.employeeId is not None:
        scope.append(payment_records.c.employee_id == filters.employeeId)
    active_in_period = (
        select(payment_records.c.employee_id)
        .select_from(source)
        .where(payment_records.c.payment_date.between(start, end), *scope)
        .distinct()
        .subquery()
    )
    totals = (
        select(
            payment_records.c.employee_id,
            func.coalesce(
                func.sum(
                    case(
                        (payment_records.c.payment_type == "Salary", payment_records.c.amount_aed),
                        else_=0,
                    )
                ),
                0,
            ).label("salary"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            payment_records.c.payment_type == "Commission",
                            payment_records.c.amount_aed,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("commission"),
            func.coalesce(func.sum(payment_records.c.amount_aed), 0).label("total"),
        )
        .select_from(source)
        .where(*scope)
        .group_by(payment_records.c.employee_id)
        .subquery()
    )
    source = employees.join(active_in_period, employees.c.id == active_in_period.c.employee_id)
    source = source.join(totals, totals.c.employee_id == employees.c.id)
    query = select(
        employees.c.id,
        employees.c.system_employee_code,
        totals.c.salary,
        totals.c.commission,
        totals.c.total,
    ).select_from(source)
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    if max_rows is not None and total > max_rows:
        return [], total, {}
    order = (
        {
            "employeeId": employees.c.id,
            "systemEmployeeCode": employees.c.system_employee_code,
            "salaryPaidAed": totals.c.salary,
            "commissionPaidAed": totals.c.commission,
            "totalPaidAed": totals.c.total,
        }.get(sort)
        if sort is not None
        else None
    )
    rows = (
        (
            await session.execute(
                query.order_by(
                    (order.asc() if direction == "asc" else order.desc()).nulls_last()
                    if order is not None
                    else employees.c.id,
                    employees.c.id,
                )
                .offset((page - 1) * size)
                .limit(size)
            )
        )
        .mappings()
        .all()
    )
    aggregate = (
        await session.execute(
            select(
                func.coalesce(func.sum(totals.c.salary), 0),
                func.coalesce(func.sum(totals.c.commission), 0),
                func.coalesce(func.sum(totals.c.total), 0),
            ).select_from(source)
        )
    ).one()
    return (
        [
            {
                "employeeId": row["id"],
                "systemEmployeeCode": row["system_employee_code"],
                "salaryPaidAed": row["salary"],
                "commissionPaidAed": row["commission"],
                "totalPaidAed": row["total"],
            }
            for row in rows
        ],
        total,
        {
            "employees": total,
            "salaryPaidAed": aggregate[0],
            "commissionPaidAed": aggregate[1],
            "totalPaidAed": aggregate[2],
        },
    )
