"""Finance report projections scoped to retained employee assignments."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.db.cases import cases, product_types
from app.db.finance import case_financial_results
from app.db.operations import clawbacks, payment_records
from app.db.organization import assignment_history
from app.policies import Actor
from app.services.report_history import assignment_id_on, scope_value_on
from app.services.report_queries import report_day


async def finance_report(
    session: AsyncSession,
    actor: Actor,
    kind: str,
    filters,
    start: date,
    end: date,
    page: int,
    size: int,
    max_rows: int | None = None,
    sort: str | None = None,
    direction: str = "asc",
) -> tuple[list[dict], int, dict]:
    if kind == "finance-payments":
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
        predicates: list[ColumnElement[bool]] = [payment_records.c.payment_date.between(start, end)]
        if actor.designation == "Sales Manager":
            predicates += [branch == actor.branch_id, department == actor.department_id]
        if filters.branchId is not None:
            predicates.append(branch == filters.branchId)
        if filters.departmentId is not None:
            predicates.append(department == filters.departmentId)
        if filters.employeeId is not None:
            predicates.append(payment_records.c.employee_id == filters.employeeId)
        query = (
            select(payment_records, branch.label("branch_id"), department.label("department_id"))
            .select_from(source)
            .where(*predicates)
        )
        order = (payment_records.c.payment_date.desc(), payment_records.c.id)
        sortable = {
            "employeeId": payment_records.c.employee_id,
            "paymentType": payment_records.c.payment_type,
            "amountAed": payment_records.c.amount_aed,
            "paymentDate": payment_records.c.payment_date,
            "branchId": branch,
            "departmentId": department,
        }
        amount = payment_records.c.amount_aed
    else:
        record = case_financial_results if kind == "finance-completed" else clawbacks
        source = record.join(cases, cases.c.id == record.c.case_id).join(
            product_types, product_types.c.id == cases.c.product_type_id
        )
        when = record.c.completed_at if kind == "finance-completed" else record.c.clawback_date
        owner = (
            record.c.credited_owner_employee_id
            if kind == "finance-completed"
            else record.c.case_owner_employee_id
        )
        activity_day = report_day(when) if kind == "finance-completed" else when
        source = source.outerjoin(
            assignment_history,
            assignment_history.c.id == assignment_id_on(owner, activity_day),
        )
        recorded_at = record.c.completed_at if kind == "finance-completed" else record.c.created_at
        branch = scope_value_on(owner, activity_day, recorded_at, "branch_id")
        department = scope_value_on(owner, activity_day, recorded_at, "department_id")
        predicates = [
            report_day(when).between(start, end)
            if kind == "finance-completed"
            else when.between(start, end),
        ]
        if actor.designation == "Sales Manager":
            predicates += [branch == actor.branch_id, department == actor.department_id]
        if filters.branchId is not None:
            predicates.append(branch == filters.branchId)
        if filters.departmentId is not None:
            predicates.append(department == filters.departmentId)
        if filters.bankId is not None:
            predicates.append(cases.c.bank_id == filters.bankId)
        if filters.productCode is not None:
            predicates.append(product_types.c.code == filters.productCode)
        if filters.employeeId is not None:
            predicates.append(owner == filters.employeeId)
        query = select(
            record,
            cases.c.internal_case_id,
            branch.label("branch_id"),
            department.label("department_id"),
            product_types.c.code.label("case_product_code"),
        )
        query = query.select_from(source).where(*predicates)
        order = (when.desc(), record.c.id)
        sortable = (
            {
                "internalCaseId": cases.c.internal_case_id,
                "productCode": product_types.c.code,
                "ccPoints": case_financial_results.c.cc_points,
                "pfAmountAed": case_financial_results.c.pf_amount_aed,
                "commissionAmountAed": case_financial_results.c.commission_aed,
                "caseOwnerEmployeeId": owner,
                "branchId": branch,
                "departmentId": department,
                "completedAt": case_financial_results.c.completed_at,
            }
            if kind == "finance-completed"
            else {
                "internalCaseId": cases.c.internal_case_id,
                "amountAed": clawbacks.c.amount_aed,
                "clawbackDate": clawbacks.c.clawback_date,
                "caseOwnerEmployeeId": owner,
                "branchId": branch,
                "departmentId": department,
            }
        )
        amount = record.c.commission_aed if kind == "finance-completed" else record.c.amount_aed
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    if max_rows is not None and total > max_rows:
        return [], total, {}
    if sort is not None:
        column = sortable[sort]
        order = ((column.asc() if direction == "asc" else column.desc()).nulls_last(), order[-1])
    rows = (
        (await session.execute(query.order_by(*order).offset((page - 1) * size).limit(size)))
        .mappings()
        .all()
    )
    amount_total = (
        await session.scalar(
            select(func.coalesce(func.sum(amount), 0)).select_from(source).where(*predicates)
        )
        or 0
    )
    items = []
    for row in rows:
        if kind == "finance-payments":
            items.append(
                {
                    "employeeId": row["employee_id"],
                    "paymentType": row["payment_type"],
                    "amountAed": row["amount_aed"],
                    "paymentDate": row["payment_date"],
                    "branchId": row["branch_id"],
                    "departmentId": row["department_id"],
                }
            )
        elif kind == "finance-completed":
            items.append(
                {
                    "internalCaseId": row["internal_case_id"],
                    "productCode": row["case_product_code"],
                    "ccPoints": row["cc_points"],
                    "pfAmountAed": row["pf_amount_aed"],
                    "commissionAmountAed": row["commission_aed"],
                    "caseOwnerEmployeeId": row["credited_owner_employee_id"],
                    "branchId": row["branch_id"],
                    "departmentId": row["department_id"],
                    "completedAt": row["completed_at"],
                }
            )
        else:
            items.append(
                {
                    "internalCaseId": row["internal_case_id"],
                    "amountAed": row["amount_aed"],
                    "clawbackDate": row["clawback_date"],
                    "caseOwnerEmployeeId": row["case_owner_employee_id"],
                    "branchId": row["branch_id"],
                    "departmentId": row["department_id"],
                }
            )
    summary = {
        "recordCount": total,
        "totalCommissionAed" if kind == "finance-completed" else "totalAmountAed": amount_total,
    }
    if kind == "finance-completed":
        cc_points, pf_amount = (
            await session.execute(
                select(
                    func.coalesce(func.sum(case_financial_results.c.cc_points), 0),
                    func.coalesce(func.sum(case_financial_results.c.pf_amount_aed), 0),
                )
                .select_from(source)
                .where(*predicates)
            )
        ).one()
        summary.update(totalCCPoints=cc_points, totalPFAed=pf_amount)
    return items, total, summary
