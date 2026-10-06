"""Self-service My Wallet views over the signed-in employee's own Finance records."""

from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import String, case, cast, func, literal, null, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.cases import banks, cases, product_types, product_variants
from app.db.finance import case_financial_results
from app.db.operations import clawbacks, payment_records
from app.errors import ApiError
from app.policies import Actor
from app.repositories.case_scope import case_access
from app.services.hr_common import dubai_today

KINDS = ("salary_payment", "commission_payment", "commission_earned", "clawback")
PAYMENT_KINDS = {"salary_payment": "Salary", "commission_payment": "Commission"}


def _completed_day():
    return func.date(func.timezone("Asia/Dubai", case_financial_results.c.completed_at))


def period(start: date | None, end: date | None) -> tuple[date, date]:
    if start is None and end is None:
        today = dubai_today()
        return today.replace(day=1), today.replace(day=monthrange(today.year, today.month)[1])
    if start is None or end is None or start > end:
        raise ApiError(422, "PERIOD_INVALID", "Choose a valid period")
    return start, end


def _text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


async def _accessible_cases(session: AsyncSession, actor: Actor, case_ids) -> set[UUID]:
    ids = {value for value in case_ids if value is not None}
    if not ids:
        return set()
    rows = await session.scalars(select(cases.c.id).where(cases.c.id.in_(ids), case_access(actor)))
    return set(rows)


async def summary(
    session: AsyncSession, actor: Actor, *, start: date | None, end: date | None
) -> dict:
    start, end = period(start, end)
    paid = (
        await session.execute(
            select(
                payment_records.c.payment_type,
                func.coalesce(func.sum(payment_records.c.amount_aed), 0),
            )
            .where(
                payment_records.c.employee_id == actor.employee_id,
                payment_records.c.payment_date.between(start, end),
            )
            .group_by(payment_records.c.payment_type)
        )
    ).all()
    paid_by_type = {payment_type: total for payment_type, total in paid}
    earned = await session.scalar(
        select(func.coalesce(func.sum(case_financial_results.c.commission_aed), 0)).where(
            case_financial_results.c.credited_owner_employee_id == actor.employee_id,
            case_financial_results.c.commission_aed.is_not(None),
            _completed_day().between(start, end),
        )
    )
    clawed = await session.scalar(
        select(func.coalesce(func.sum(clawbacks.c.amount_aed), 0)).where(
            clawbacks.c.case_owner_employee_id == actor.employee_id,
            clawbacks.c.clawback_date.between(start, end),
        )
    )
    return {
        "periodFrom": start.isoformat(),
        "periodTo": end.isoformat(),
        "salaryPaidAed": str(paid_by_type.get("Salary", 0)),
        "commissionEarnedAed": str(earned or 0),
        "commissionPaidAed": str(paid_by_type.get("Commission", 0)),
        "clawbacksAed": str(clawed or 0),
    }


def _ledger(actor: Actor, start: date, end: date):
    payments = select(
        case(
            (payment_records.c.payment_type == "Salary", literal("salary_payment")),
            else_=literal("commission_payment"),
        ).label("kind"),
        payment_records.c.id.label("id"),
        payment_records.c.payment_date.label("occurred_on"),
        payment_records.c.amount_aed.label("amount_aed"),
        payment_records.c.payment_month.label("payment_month"),
        cast(null(), cases.c.id.type).label("case_id"),
        cast(null(), String).label("case_reference"),
        cast(null(), String).label("product_name"),
        cast(null(), String).label("bank_name"),
        cast(null(), String).label("reason"),
        payment_records.c.created_at.label("recorded_at"),
    ).where(
        payment_records.c.employee_id == actor.employee_id,
        payment_records.c.payment_date.between(start, end),
    )
    earned = (
        select(
            literal("commission_earned").label("kind"),
            case_financial_results.c.id.label("id"),
            _completed_day().label("occurred_on"),
            case_financial_results.c.commission_aed.label("amount_aed"),
            cast(null(), payment_records.c.payment_month.type).label("payment_month"),
            cases.c.id.label("case_id"),
            cases.c.internal_case_id.label("case_reference"),
            product_types.c.name.label("product_name"),
            banks.c.name.label("bank_name"),
            cast(null(), String).label("reason"),
            case_financial_results.c.completed_at.label("recorded_at"),
        )
        .select_from(
            case_financial_results.join(cases, cases.c.id == case_financial_results.c.case_id)
            .join(product_types, product_types.c.id == cases.c.product_type_id)
            .join(banks, banks.c.id == cases.c.bank_id)
        )
        .where(
            case_financial_results.c.credited_owner_employee_id == actor.employee_id,
            case_financial_results.c.commission_aed.is_not(None),
            _completed_day().between(start, end),
        )
    )
    clawed = (
        select(
            literal("clawback").label("kind"),
            clawbacks.c.id.label("id"),
            clawbacks.c.clawback_date.label("occurred_on"),
            clawbacks.c.amount_aed.label("amount_aed"),
            cast(null(), payment_records.c.payment_month.type).label("payment_month"),
            cases.c.id.label("case_id"),
            cases.c.internal_case_id.label("case_reference"),
            cast(null(), String).label("product_name"),
            cast(null(), String).label("bank_name"),
            clawbacks.c.reason.label("reason"),
            clawbacks.c.created_at.label("recorded_at"),
        )
        .select_from(clawbacks.join(cases, cases.c.id == clawbacks.c.case_id))
        .where(
            clawbacks.c.case_owner_employee_id == actor.employee_id,
            clawbacks.c.clawback_date.between(start, end),
        )
    )
    return union_all(payments, earned, clawed).subquery("wallet_ledger")


async def transactions(
    session: AsyncSession,
    actor: Actor,
    *,
    start: date | None,
    end: date | None,
    kind: str | None,
    page: int,
    page_size: int,
) -> dict:
    start, end = period(start, end)
    ledger = _ledger(actor, start, end)
    predicates = [] if kind is None else [ledger.c.kind == kind]
    total = await session.scalar(select(func.count()).select_from(ledger).where(*predicates))
    rows = (
        (
            await session.execute(
                select(ledger)
                .where(*predicates)
                .order_by(ledger.c.occurred_on.desc(), ledger.c.recorded_at.desc(), ledger.c.id)
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        )
        .mappings()
        .all()
    )
    accessible = await _accessible_cases(session, actor, [row["case_id"] for row in rows])
    return {
        "periodFrom": start.isoformat(),
        "periodTo": end.isoformat(),
        "items": [
            {
                "kind": row["kind"],
                "id": str(row["id"]),
                "date": row["occurred_on"].isoformat(),
                "amountAed": _text(row["amount_aed"]),
                "paymentMonth": _text(row["payment_month"]),
                "caseReference": row["case_reference"],
                "caseId": str(row["case_id"]) if row["case_id"] in accessible else None,
                "productName": row["product_name"],
                "bankName": row["bank_name"],
                "reason": row["reason"],
                "recordedAt": _text(row["recorded_at"]),
            }
            for row in rows
        ],
        "total": total or 0,
        "page": page,
        "pageSize": page_size,
    }


async def transaction_detail(
    session: AsyncSession, actor: Actor, kind: str, record_id: UUID
) -> dict:
    if kind in PAYMENT_KINDS:
        row = (
            (
                await session.execute(
                    select(payment_records).where(
                        payment_records.c.id == record_id,
                        payment_records.c.employee_id == actor.employee_id,
                        payment_records.c.payment_type == PAYMENT_KINDS[kind],
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
        return {
            "kind": kind,
            "id": str(row["id"]),
            "paymentType": row["payment_type"],
            "amountAed": _text(row["amount_aed"]),
            "paymentMonth": _text(row["payment_month"]),
            "paymentDate": _text(row["payment_date"]),
            "recordedAt": _text(row["created_at"]),
        }
    if kind == "commission_earned":
        row = (
            (
                await session.execute(
                    select(
                        case_financial_results,
                        _completed_day().label("completed_on"),
                        cases.c.internal_case_id,
                        product_types.c.name.label("product_name"),
                        product_variants.c.name.label("product_variant_name"),
                        banks.c.name.label("bank_name"),
                    )
                    .select_from(
                        case_financial_results.join(
                            cases, cases.c.id == case_financial_results.c.case_id
                        )
                        .join(product_types, product_types.c.id == cases.c.product_type_id)
                        .join(banks, banks.c.id == cases.c.bank_id)
                        .outerjoin(
                            product_variants, product_variants.c.id == cases.c.product_variant_id
                        )
                    )
                    .where(
                        case_financial_results.c.id == record_id,
                        case_financial_results.c.credited_owner_employee_id == actor.employee_id,
                        case_financial_results.c.commission_aed.is_not(None),
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
        accessible = await _accessible_cases(session, actor, [row["case_id"]])
        return {
            "kind": kind,
            "id": str(row["id"]),
            "caseReference": row["internal_case_id"],
            "caseId": str(row["case_id"]) if row["case_id"] in accessible else None,
            "productCode": row["product_code"],
            "productName": row["product_name"],
            "productVariantName": row["product_variant_name"],
            "bankName": row["bank_name"],
            "completedOn": _text(row["completed_on"]),
            "completedAt": _text(row["completed_at"]),
            "commissionAed": _text(row["commission_aed"]),
            "ccPoints": row["cc_points"],
            "pfAmountAed": _text(row["pf_amount_aed"]),
            "ruleEffectiveDate": _text(row["rule_effective_date"]),
        }
    if kind == "clawback":
        row = (
            (
                await session.execute(
                    select(clawbacks, cases.c.internal_case_id)
                    .select_from(clawbacks.join(cases, cases.c.id == clawbacks.c.case_id))
                    .where(
                        clawbacks.c.id == record_id,
                        clawbacks.c.case_owner_employee_id == actor.employee_id,
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
        accessible = await _accessible_cases(session, actor, [row["case_id"]])
        return {
            "kind": kind,
            "id": str(row["id"]),
            "caseReference": row["internal_case_id"],
            "caseId": str(row["case_id"]) if row["case_id"] in accessible else None,
            "amountAed": _text(row["amount_aed"]),
            "clawbackDate": _text(row["clawback_date"]),
            "reason": row["reason"],
            "recordedAt": _text(row["created_at"]),
        }
    raise ApiError(404, "NOT_FOUND", "Record unavailable")
