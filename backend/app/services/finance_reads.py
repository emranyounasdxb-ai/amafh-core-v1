"""Scope-filtered Finance views and transaction-derived Points balances."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.cases import cases
from app.db.finance import case_financial_results
from app.db.operations import clawbacks, payment_records, points_wallet_transactions, points_wallets
from app.db.organization import assignment_history, employees
from app.errors import ApiError
from app.policies import Actor, require
from app.services.report_history import assignment_id_on, scope_value_on


def _visible_scope(actor: Actor, branch, department):
    if actor.designation == "Sales Manager":
        return (branch == actor.branch_id) & (department == actor.department_id)
    return True


def _historical_scope(source, employee_id, activity_day, occurred_at):
    source = source.outerjoin(
        assignment_history,
        assignment_history.c.id == assignment_id_on(employee_id, activity_day),
    )
    branch = scope_value_on(employee_id, activity_day, occurred_at, "branch_id")
    department = scope_value_on(employee_id, activity_day, occurred_at, "department_id")
    return source, branch, department


def _completed_scope():
    result = case_financial_results
    day = func.date(func.timezone("Asia/Dubai", result.c.completed_at))
    return _historical_scope(
        result.join(cases, result.c.case_id == cases.c.id),
        result.c.credited_owner_employee_id,
        day,
        result.c.completed_at,
    )


def _clawback_scope():
    return _historical_scope(
        clawbacks.join(cases, clawbacks.c.case_id == cases.c.id),
        clawbacks.c.case_owner_employee_id,
        clawbacks.c.clawback_date,
        clawbacks.c.created_at,
    )


def _payment_scope():
    return _historical_scope(
        payment_records,
        payment_records.c.employee_id,
        payment_records.c.payment_date,
        payment_records.c.created_at,
    )


def _finance_access(actor: Actor) -> None:
    require(actor, "finance.read")


def _wallet_access(actor: Actor) -> None:
    if actor.designation not in {"Owner", "Managing Director", "Finance"}:
        raise ApiError(403, "FORBIDDEN", "Access denied")


def _public(row) -> dict:
    result = {}
    for key, value in dict(row).items():
        if isinstance(value, (UUID, Decimal)):
            value = str(value)
        elif isinstance(value, (date, datetime)):
            value = value.isoformat()
        result[key] = value
    return result


def _page(items, total: int | None, page: int, page_size: int) -> dict:
    return {
        "items": [_public(row) for row in items],
        "total": total or 0,
        "page": page,
        "pageSize": page_size,
    }


def _ordered(sort: str | None, direction: str, fields: dict, default):
    if sort not in {None, *fields} or direction not in {"asc", "desc"}:
        raise ApiError(422, "SORT_INVALID", "Invalid sorting")
    if sort is None:
        return default.desc()
    column = fields[sort]
    return (column.asc() if direction == "asc" else column.desc()).nulls_last()


async def completed_cases(
    session: AsyncSession,
    actor: Actor,
    *,
    page: int,
    page_size: int,
    branch_id: UUID | None,
    product_code: str | None,
    completed_from: date | None,
    completed_to: date | None,
    sort: str | None = None,
    direction: str = "asc",
) -> dict:
    _finance_access(actor)
    source, branch, department = _completed_scope()
    predicates = [_visible_scope(actor, branch, department)]
    if branch_id is not None:
        predicates.append(branch == branch_id)
    if product_code is not None:
        predicates.append(case_financial_results.c.product_code == product_code)
    if completed_from is not None:
        predicates.append(
            func.date(func.timezone("Asia/Dubai", case_financial_results.c.completed_at))
            >= completed_from
        )
    if completed_to is not None:
        predicates.append(
            func.date(func.timezone("Asia/Dubai", case_financial_results.c.completed_at))
            <= completed_to
        )
    total = await session.scalar(select(func.count()).select_from(source).where(*predicates))
    rows = (
        await session.execute(
            select(
                *case_financial_results.c,
                cases.c.internal_case_id,
                branch.label("branch_id"),
                department.label("department_id"),
                cases.c.owner_employee_id.label("current_owner_employee_id"),
            )
            .select_from(source)
            .where(*predicates)
            .order_by(
                _ordered(
                    sort,
                    direction,
                    {
                        "internalCaseId": cases.c.internal_case_id,
                        "productCode": case_financial_results.c.product_code,
                        "completedAt": case_financial_results.c.completed_at,
                        "ccPoints": case_financial_results.c.cc_points,
                        "commissionAed": case_financial_results.c.commission_aed,
                    },
                    case_financial_results.c.completed_at,
                ),
                case_financial_results.c.id,
            )
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).mappings()
    return _page(rows, total, page, page_size)


async def completed_case_detail(session: AsyncSession, actor: Actor, case_id: UUID) -> dict:
    _finance_access(actor)
    source, branch, department = _completed_scope()
    row = (
        (
            await session.execute(
                select(
                    *case_financial_results.c,
                    cases.c.internal_case_id,
                    branch.label("branch_id"),
                    department.label("department_id"),
                    cases.c.owner_employee_id.label("current_owner_employee_id"),
                )
                .select_from(source)
                .where(
                    case_financial_results.c.case_id == case_id,
                    _visible_scope(actor, branch, department),
                )
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    result = _public(row)
    clawback_source, clawback_branch, clawback_department = _clawback_scope()
    clawback = (
        (
            await session.execute(
                select(clawbacks)
                .select_from(clawback_source)
                .where(
                    clawbacks.c.case_id == case_id,
                    _visible_scope(actor, clawback_branch, clawback_department),
                )
            )
        )
        .mappings()
        .one_or_none()
    )
    result["clawback"] = _public(clawback) if clawback else None
    return result


async def list_wallets(
    session: AsyncSession,
    actor: Actor,
    *,
    page: int,
    page_size: int,
    employee_id: UUID | None,
    sort: str | None = None,
    direction: str = "asc",
) -> dict:
    _wallet_access(actor)
    predicates = []
    if employee_id is not None:
        predicates.append(points_wallets.c.employee_id == employee_id)
    total = await session.scalar(
        select(func.count()).select_from(points_wallets).where(*predicates)
    )
    balance = (
        select(func.coalesce(func.sum(points_wallet_transactions.c.points_credited), 0))
        .where(points_wallet_transactions.c.wallet_id == points_wallets.c.id)
        .correlate(points_wallets)
        .scalar_subquery()
    )
    rows = (
        await session.execute(
            select(
                points_wallets.c.id,
                points_wallets.c.employee_id,
                points_wallets.c.created_at,
                balance.label("balance_points"),
            )
            .select_from(
                points_wallets.join(employees, employees.c.id == points_wallets.c.employee_id)
            )
            .where(*predicates)
            .order_by(
                _ordered(
                    sort,
                    direction,
                    {"employeeName": employees.c.full_name, "balancePoints": balance},
                    points_wallets.c.created_at,
                ),
                points_wallets.c.id,
            )
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).mappings()
    return _page(rows, total, page, page_size)


async def wallet_detail(
    session: AsyncSession,
    actor: Actor,
    employee_id: UUID,
    *,
    page: int,
    page_size: int,
) -> dict:
    _wallet_access(actor)
    wallet = (
        (
            await session.execute(
                select(points_wallets).where(points_wallets.c.employee_id == employee_id)
            )
        )
        .mappings()
        .one_or_none()
    )
    if wallet is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    total = await session.scalar(
        select(func.count())
        .select_from(points_wallet_transactions)
        .where(points_wallet_transactions.c.wallet_id == wallet["id"])
    )
    balance = await session.scalar(
        select(func.coalesce(func.sum(points_wallet_transactions.c.points_credited), 0)).where(
            points_wallet_transactions.c.wallet_id == wallet["id"]
        )
    )
    rows = (
        await session.execute(
            select(points_wallet_transactions)
            .where(points_wallet_transactions.c.wallet_id == wallet["id"])
            .order_by(
                points_wallet_transactions.c.occurred_at.desc(), points_wallet_transactions.c.id
            )
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).mappings()
    return {
        "walletId": str(wallet["id"]),
        "employeeId": str(employee_id),
        "balancePoints": balance or 0,
        "transactions": _page(rows, total, page, page_size),
    }


async def list_clawbacks(
    session: AsyncSession,
    actor: Actor,
    *,
    page: int,
    page_size: int,
    branch_id: UUID | None,
    case_id: UUID | None,
    sort: str | None = None,
    direction: str = "asc",
) -> dict:
    _finance_access(actor)
    source, branch, department = _clawback_scope()
    predicates = [_visible_scope(actor, branch, department)]
    if branch_id is not None:
        predicates.append(branch == branch_id)
    if case_id is not None:
        predicates.append(cases.c.id == case_id)
    total = await session.scalar(select(func.count()).select_from(source).where(*predicates))
    rows = (
        await session.execute(
            select(
                *clawbacks.c,
                cases.c.internal_case_id,
                branch.label("branch_id"),
                department.label("department_id"),
            )
            .select_from(source)
            .where(*predicates)
            .order_by(
                _ordered(
                    sort,
                    direction,
                    {
                        "internalCaseId": cases.c.internal_case_id,
                        "amountAed": clawbacks.c.amount_aed,
                        "clawbackDate": clawbacks.c.clawback_date,
                        "reason": clawbacks.c.reason,
                    },
                    clawbacks.c.clawback_date,
                ),
                clawbacks.c.id,
            )
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).mappings()
    return _page(rows, total, page, page_size)


async def clawback_detail(session: AsyncSession, actor: Actor, record_id: UUID) -> dict:
    _finance_access(actor)
    source, branch, department = _clawback_scope()
    row = (
        (
            await session.execute(
                select(
                    *clawbacks.c,
                    cases.c.internal_case_id,
                    branch.label("branch_id"),
                    department.label("department_id"),
                )
                .select_from(source)
                .where(clawbacks.c.id == record_id, _visible_scope(actor, branch, department))
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return _public(row)


async def list_payments(
    session: AsyncSession,
    actor: Actor,
    *,
    page: int,
    page_size: int,
    employee_id: UUID | None,
    payment_type: str | None,
    payment_from: date | None,
    payment_to: date | None,
    sort: str | None = None,
    direction: str = "asc",
) -> dict:
    _finance_access(actor)
    source, branch, department = _payment_scope()
    source = source.join(employees, employees.c.id == payment_records.c.employee_id)
    predicates = [_visible_scope(actor, branch, department)]
    if employee_id is not None:
        predicates.append(payment_records.c.employee_id == employee_id)
    if payment_type is not None:
        predicates.append(payment_records.c.payment_type == payment_type)
    if payment_from is not None:
        predicates.append(payment_records.c.payment_date >= payment_from)
    if payment_to is not None:
        predicates.append(payment_records.c.payment_date <= payment_to)
    total = await session.scalar(select(func.count()).select_from(source).where(*predicates))
    rows = (
        await session.execute(
            select(
                *payment_records.c,
                branch.label("branch_id"),
                department.label("department_id"),
            )
            .select_from(source)
            .where(*predicates)
            .order_by(
                _ordered(
                    sort,
                    direction,
                    {
                        "employeeName": employees.c.full_name,
                        "paymentType": payment_records.c.payment_type,
                        "amountAed": payment_records.c.amount_aed,
                        "paymentMonth": payment_records.c.payment_month,
                        "paymentDate": payment_records.c.payment_date,
                    },
                    payment_records.c.payment_date,
                ),
                payment_records.c.id,
            )
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).mappings()
    return _page(rows, total, page, page_size)


async def payment_detail(session: AsyncSession, actor: Actor, record_id: UUID) -> dict:
    _finance_access(actor)
    source, branch, department = _payment_scope()
    row = (
        (
            await session.execute(
                select(
                    *payment_records.c,
                    branch.label("branch_id"),
                    department.label("department_id"),
                )
                .select_from(source)
                .where(
                    payment_records.c.id == record_id,
                    _visible_scope(actor, branch, department),
                )
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return _public(row)


async def employee_payment_history(
    session: AsyncSession,
    actor: Actor,
    employee_id: UUID,
    *,
    page: int,
    page_size: int,
    payment_type: str | None,
    payment_from: date | None,
    payment_to: date | None,
) -> dict:
    _finance_access(actor)
    payment_source, branch, department = _payment_scope()
    historical_scope = _visible_scope(actor, branch, department)
    employee = await session.scalar(select(employees.c.id).where(employees.c.id == employee_id))
    if employee is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    if actor.designation == "Sales Manager":
        current_scope = await session.scalar(
            select(employees.c.id).where(
                employees.c.id == employee_id,
                employees.c.branch_id == actor.branch_id,
                employees.c.department_id == actor.department_id,
            )
        )
        historical_access = await session.scalar(
            select(payment_records.c.id)
            .select_from(payment_source)
            .where(payment_records.c.employee_id == employee_id, historical_scope)
            .limit(1)
        )
        if current_scope is None and historical_access is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
    result = await list_payments(
        session,
        actor,
        page=page,
        page_size=page_size,
        employee_id=employee_id,
        payment_type=payment_type,
        payment_from=payment_from,
        payment_to=payment_to,
    )
    total = await session.scalar(
        select(func.coalesce(func.sum(payment_records.c.amount_aed), 0))
        .select_from(payment_source)
        .where(payment_records.c.employee_id == employee_id, historical_scope)
    )
    return {"employeeId": str(employee_id), "lifetimePaidAed": str(total), **result}


async def own_clawback_mentions(
    session: AsyncSession, actor: Actor, *, page: int, page_size: int
) -> dict:
    predicates = [clawbacks.c.case_owner_employee_id == actor.employee_id]
    total = await session.scalar(select(func.count()).select_from(clawbacks).where(*predicates))
    rows = (
        await session.execute(
            select(
                clawbacks.c.id,
                clawbacks.c.case_id,
                clawbacks.c.amount_aed,
                clawbacks.c.clawback_date,
                clawbacks.c.reason,
            )
            .where(*predicates)
            .order_by(
                clawbacks.c.clawback_date.desc(),
                clawbacks.c.id,
            )
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).mappings()
    return _page(rows, total, page, page_size)
