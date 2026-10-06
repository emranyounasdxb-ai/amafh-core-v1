"""Bounded report projections from retained Case, Customer, Finance and HR facts."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.cases import case_stage_history, cases, customers, pipeline_stages, product_types
from app.db.organization import designations, employees, user_accounts
from app.errors import ApiError
from app.policies import Actor
from app.repositories.case_scope import visible_case
from app.services.performance_delay import count_delayed
from app.services.performance_math import DUBAI, dubai_date


def report_day(column):
    return func.timezone("Asia/Dubai", column).cast(Date)


def _case_filters(actor: Actor, filters, start: date, end: date, *, time_column):
    predicates = [visible_case(actor), report_day(time_column).between(start, end)]
    if filters.branchId is not None:
        predicates.append(cases.c.branch_id == filters.branchId)
    if filters.departmentId is not None:
        predicates.append(cases.c.department_id == filters.departmentId)
    if filters.bankId is not None:
        predicates.append(cases.c.bank_id == filters.bankId)
    if filters.productCode is not None:
        predicates.append(product_types.c.code == filters.productCode)
    if filters.employeeId is not None:
        predicates.append(cases.c.owner_employee_id == filters.employeeId)
    return predicates


async def case_pipeline(
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
    source = cases.join(product_types, product_types.c.id == cases.c.product_type_id)
    predicates = _case_filters(actor, filters, start, end, time_column=cases.c.created_at)
    predicates.append(cases.c.administratively_voided_at.is_(None))
    if filters.status is not None:
        predicates.append(cases.c.current_status == filters.status)
    base = (
        select(
            cases.c.id,
            cases.c.internal_case_id,
            cases.c.current_status,
            cases.c.current_stage,
            cases.c.branch_id,
            cases.c.department_id,
            cases.c.bank_id,
            cases.c.owner_employee_id,
            cases.c.created_at,
            cases.c.pipeline_configuration_id,
            product_types.c.code.label("product_code"),
        )
        .select_from(source)
        .where(*predicates)
    )
    total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
    if max_rows is not None and total > max_rows:
        return [], total, {}
    order = (
        {
            "internalCaseId": cases.c.internal_case_id,
            "status": cases.c.current_status,
            "currentStage": cases.c.current_stage,
            "branchId": cases.c.branch_id,
            "departmentId": cases.c.department_id,
            "bankId": cases.c.bank_id,
            "productCode": product_types.c.code,
            "ownerEmployeeId": cases.c.owner_employee_id,
            "createdAt": cases.c.created_at,
        }.get(sort)
        if sort is not None
        else None
    )
    rows = (
        (
            await session.execute(
                base.order_by(
                    (order.asc() if direction == "asc" else order.desc()).nulls_last()
                    if order is not None
                    else cases.c.created_at.desc(),
                    cases.c.id,
                )
                .offset((page - 1) * size)
                .limit(size)
            )
        )
        .mappings()
        .all()
    )
    counts: dict[str, int] = {
        row[0]: row[1]
        for row in (
            await session.execute(
                select(cases.c.current_status, func.count())
                .select_from(source)
                .where(*predicates)
                .group_by(cases.c.current_status)
            )
        ).all()
    }
    candidates = (
        await session.execute(
            select(cases.c.id, cases.c.current_stage, cases.c.pipeline_configuration_id)
            .select_from(source)
            .where(
                *predicates,
                cases.c.current_status.not_in(["Completed", "Rejected"]),
                cases.c.current_stage.is_not(None),
            )
        )
    ).all()
    delayed = []
    if candidates:
        ids = [row.id for row in candidates]
        latest = (
            (
                await session.execute(
                    select(case_stage_history)
                    .where(case_stage_history.c.case_id.in_(ids))
                    .order_by(
                        case_stage_history.c.case_id,
                        case_stage_history.c.occurred_at.desc(),
                        case_stage_history.c.id.desc(),
                    )
                )
            )
            .mappings()
            .all()
        )
        by_case: dict[UUID, dict] = {}
        for stage_record in latest:
            by_case.setdefault(stage_record["case_id"], dict(stage_record))
        stage_keys = {(row.pipeline_configuration_id, row.current_stage) for row in candidates}
        stage_rows = (
            await session.execute(
                select(
                    pipeline_stages.c.pipeline_configuration_id,
                    pipeline_stages.c.name,
                    pipeline_stages.c.expected_business_days,
                ).where(
                    pipeline_stages.c.pipeline_configuration_id.in_(
                        [key[0] for key in stage_keys if key[0] is not None]
                    )
                )
            )
        ).all()
        expected = {
            (row.pipeline_configuration_id, row.name): row.expected_business_days
            for row in stage_rows
        }
        for row in candidates:
            stage = by_case.get(row.id)
            days = expected.get((row.pipeline_configuration_id, row.current_stage))
            if stage is not None and stage["stage"] == row.current_stage and days is not None:
                delayed.append((row.id, dubai_date(stage["occurred_at"]), days))
    delayed_count, delayed_state = await count_delayed(session, delayed, datetime.now(DUBAI).date())
    items = [
        {
            "internalCaseId": row["internal_case_id"],
            "status": row["current_status"],
            "currentStage": row["current_stage"],
            "branchId": row["branch_id"],
            "departmentId": row["department_id"],
            "bankId": row["bank_id"],
            "productCode": row["product_code"],
            "ownerEmployeeId": row["owner_employee_id"],
            "createdAt": row["created_at"],
        }
        for row in rows
    ]
    return (
        items,
        total,
        {
            "totalCases": total,
            "pendingApproval": counts.get("Pending for Approval", 0),
            "bookedCases": counts.get("Booked", 0),
            "completedCases": counts.get("Completed", 0),
            "rejectedCases": counts.get("Rejected", 0),
            "delayedCases": delayed_count,
            "delayedMetricState": delayed_state,
        },
    )


async def customer_report(
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
    source = customers.join(cases, cases.c.customer_id == customers.c.id).join(
        product_types, product_types.c.id == cases.c.product_type_id
    )
    predicates = _case_filters(actor, filters, start, end, time_column=cases.c.created_at)
    if filters.customerType is not None:
        predicates.append(customers.c.customer_type == filters.customerType)
    grouped = (
        select(
            customers.c.id,
            customers.c.customer_id,
            customers.c.customer_type,
            customers.c.created_at,
            func.count(cases.c.id).label("case_count"),
        )
        .select_from(source)
        .where(*predicates)
        .group_by(customers.c.id)
    )
    total = await session.scalar(select(func.count()).select_from(grouped.subquery())) or 0
    if max_rows is not None and total > max_rows:
        return [], total, {}
    order = (
        {
            "customerId": customers.c.customer_id,
            "type": customers.c.customer_type,
            "caseCount": func.count(cases.c.id),
            "createdAt": customers.c.created_at,
        }.get(sort)
        if sort is not None
        else None
    )
    rows = (
        (
            await session.execute(
                grouped.order_by(
                    (order.asc() if direction == "asc" else order.desc()).nulls_last()
                    if order is not None
                    else customers.c.created_at.desc(),
                    customers.c.id,
                )
                .offset((page - 1) * size)
                .limit(size)
            )
        )
        .mappings()
        .all()
    )
    counts: dict[str, int] = {
        row[0]: row[1]
        for row in (
            await session.execute(
                select(customers.c.customer_type, func.count(func.distinct(customers.c.id)))
                .select_from(source)
                .where(*predicates)
                .group_by(customers.c.customer_type)
            )
        ).all()
    }
    grouped_rows = grouped.subquery()
    new_count = (
        await session.scalar(
            select(func.count())
            .select_from(grouped_rows)
            .where(report_day(grouped_rows.c.created_at).between(start, end))
        )
        or 0
    )
    return (
        [
            {
                "customerId": row["customer_id"],
                "type": row["customer_type"],
                "caseCount": row["case_count"],
                "createdAt": row["created_at"],
            }
            for row in rows
        ],
        total,
        {
            "totalCustomers": total,
            "newCustomers": new_count,
            "existingWithNewCases": total - new_count,
            "individualCustomers": counts.get("Individual", 0),
            "companyCustomers": counts.get("Company", 0),
        },
    )


async def employee_report(
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
    source = employees.join(designations, designations.c.id == employees.c.designation_id)
    source = source.outerjoin(user_accounts, user_accounts.c.employee_id == employees.c.id)
    predicates = [employees.c.date_of_joining.between(start, end)]
    if filters.branchId is not None:
        predicates.append(employees.c.branch_id == filters.branchId)
    if filters.departmentId is not None:
        predicates.append(employees.c.department_id == filters.departmentId)
    if filters.designationId is not None:
        predicates.append(employees.c.designation_id == filters.designationId)
    if filters.status is not None:
        if filters.status not in {"Pending Setup", "Active", "Offboarded"}:
            raise ApiError(422, "REPORT_FILTER_INVALID", "Employee status is invalid")
        predicates.append(employees.c.status == filters.status)
    if filters.accessStatus is not None:
        predicates.append(
            func.coalesce(user_accounts.c.access_status, "Not Provisioned") == filters.accessStatus
        )
    query = (
        select(
            employees.c.id,
            employees.c.system_employee_code,
            employees.c.full_name,
            employees.c.status,
            employees.c.branch_id,
            employees.c.department_id,
            employees.c.date_of_joining,
            designations.c.name.label("designation"),
            user_accounts.c.access_status,
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
            "status": employees.c.status,
            "accessStatus": func.coalesce(user_accounts.c.access_status, "Not Provisioned"),
            "branchId": employees.c.branch_id,
            "departmentId": employees.c.department_id,
            "designation": designations.c.name,
            "joiningDate": employees.c.date_of_joining,
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
                    else employees.c.date_of_joining.desc(),
                    employees.c.id,
                )
                .offset((page - 1) * size)
                .limit(size)
            )
        )
        .mappings()
        .all()
    )
    status_counts: dict[str, int] = {
        row[0]: row[1]
        for row in (
            await session.execute(
                select(employees.c.status, func.count())
                .select_from(source)
                .where(*predicates)
                .group_by(employees.c.status)
            )
        ).all()
    }
    return (
        [
            {
                "systemEmployeeCode": row["system_employee_code"],
                "employeeName": row["full_name"],
                "status": row["status"],
                "accessStatus": row["access_status"] or "Not Provisioned",
                "branchId": row["branch_id"],
                "departmentId": row["department_id"],
                "designation": row["designation"],
                "joiningDate": row["date_of_joining"],
            }
            for row in rows
        ],
        total,
        {
            "totalEmployees": total,
            "activeEmployees": status_counts.get("Active", 0),
            "offboardedEmployees": status_counts.get("Offboarded", 0),
        },
    )
