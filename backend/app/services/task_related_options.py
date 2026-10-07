"""Authorized Task related-record picker options."""

from datetime import date
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.assets import assets
from app.db.attendance import attendance_records, csv_import_batches
from app.db.cases import cases, company_customers, customers, individual_customers
from app.db.finance import case_financial_results
from app.db.operations import clawbacks, payment_records
from app.db.organization import employees, team_memberships, teams
from app.errors import ApiError
from app.policies import EMPLOYEE_SCOPE, Actor
from app.repositories.case_scope import visible_case
from app.services.customer_read import _authorized_customer
from app.services.task_policy import finance_link_scope, operation_link_scope

RELATED_TYPES = {
    "case",
    "customer",
    "employee",
    "asset",
    "attendance",
    "attendance_import",
    "finance_result",
    "clawback",
    "payment",
}


def _page(items: list[dict], total: int, page: int, page_size: int) -> dict:
    return {"items": items, "total": total, "page": page, "pageSize": page_size}


def _empty(page: int, page_size: int) -> dict:
    return _page([], 0, page, page_size)


def _like(term: str, *columns):
    pattern = f"%{term}%"
    return or_(*(column.ilike(pattern) for column in columns))


def _customer_name():
    return func.coalesce(individual_customers.c.full_name, company_customers.c.company_name)


def _customer_joins(query):
    return query.outerjoin(
        individual_customers,
        and_(
            individual_customers.c.customer_id == customers.c.id,
            customers.c.customer_type == "Individual",
        ),
    ).outerjoin(
        company_customers,
        and_(
            company_customers.c.customer_id == customers.c.id,
            customers.c.customer_type == "Company",
        ),
    )


async def _team_member_ids(session: AsyncSession, actor: Actor) -> list[UUID]:
    rows = await session.scalars(
        select(team_memberships.c.employee_id)
        .select_from(team_memberships.join(teams, teams.c.id == team_memberships.c.team_id))
        .where(
            teams.c.leader_employee_id == actor.employee_id,
            teams.c.active.is_(True),
            team_memberships.c.end_date.is_(None),
        )
    )
    return list(rows)


def _format_date(value: date | None) -> str:
    if value is None:
        return ""
    return value.isoformat()


async def related_options(
    session: AsyncSession,
    actor: Actor,
    *,
    related_type: str,
    q: str = "",
    page: int = 1,
    page_size: int = 25,
) -> dict:
    if related_type not in RELATED_TYPES:
        raise ApiError(422, "TASK_RELATED_TYPE_INVALID", "Unsupported related record type")
    term = q.strip()
    offset = (page - 1) * page_size
    kind = related_type

    if kind == "customer":
        if "case.read" not in actor.grants:
            return _empty(page, page_size)
        name = _customer_name()
        query = _customer_joins(
            select(customers.c.id, name.label("label"), customers.c.customer_id)
        )
        predicates = [_authorized_customer(actor)]
        if term:
            predicates.append(_like(term, name, customers.c.customer_id))
        query = query.where(*predicates)
        return await _fetch(
            session,
            query.order_by(name, customers.c.customer_id),
            page=page,
            page_size=page_size,
            offset=offset,
            subtitle_key="customer_id",
        )

    if kind == "case":
        if "case.read" not in actor.grants:
            return _empty(page, page_size)
        name = _customer_name()
        query = (
            select(cases.c.id, cases.c.internal_case_id.label("label"), name.label("subtitle"))
            .select_from(cases)
            .join(customers, customers.c.id == cases.c.customer_id)
        )
        query = _customer_joins(query).where(visible_case(actor))
        if term:
            query = query.where(_like(term, cases.c.internal_case_id, name))
        return await _fetch(
            session,
            query.order_by(cases.c.internal_case_id),
            page=page,
            page_size=page_size,
            offset=offset,
        )

    if kind == "employee":
        if "employee.read" not in actor.grants:
            return _empty(page, page_size)
        predicates = []
        scope = EMPLOYEE_SCOPE.get(actor.designation, "none")
        if scope == "branch":
            predicates.append(employees.c.branch_id == actor.branch_id)
        elif scope == "department":
            predicates.extend(
                [
                    employees.c.branch_id == actor.branch_id,
                    employees.c.department_id == actor.department_id,
                ]
            )
        elif scope == "team":
            member_ids = await _team_member_ids(session, actor)
            predicates.append(employees.c.id.in_([actor.employee_id, *member_ids]))
        elif scope != "all":
            predicates.append(employees.c.id == actor.employee_id)
        query = select(
            employees.c.id,
            employees.c.full_name.label("label"),
            employees.c.company_employee_code.label("subtitle"),
        )
        if predicates:
            query = query.where(*predicates)
        if term:
            query = query.where(
                _like(term, employees.c.full_name, employees.c.company_employee_code)
            )
        return await _fetch(
            session,
            query.order_by(employees.c.full_name),
            page=page,
            page_size=page_size,
            offset=offset,
        )

    if kind in {"asset", "attendance", "attendance_import"}:
        table = {
            "asset": assets,
            "attendance": attendance_records,
            "attendance_import": csv_import_batches,
        }[kind]
        predicate = operation_link_scope(actor, kind, table)
        if predicate is None:
            return _empty(page, page_size)
        if kind == "asset":
            query = select(
                assets.c.id,
                func.concat(assets.c.brand, " ", assets.c.model).label("label"),
                assets.c.asset_code.label("subtitle"),
            )
            query = query.where(predicate)
            if term:
                query = query.where(
                    _like(term, assets.c.brand, assets.c.model, assets.c.asset_code)
                )
            return await _fetch(
                session,
                query.order_by(assets.c.asset_code),
                page=page,
                page_size=page_size,
                offset=offset,
            )
        if kind == "attendance":
            query = select(
                attendance_records.c.id,
                employees.c.full_name.label("label"),
                attendance_records.c.attendance_date,
                attendance_records.c.status,
            ).join(employees, employees.c.id == attendance_records.c.employee_id)
            query = query.where(predicate)
            if term:
                query = query.where(_like(term, employees.c.full_name, attendance_records.c.status))
            total = await session.scalar(query.with_only_columns(func.count()).order_by(None)) or 0
            rows = (
                (
                    await session.execute(
                        query.order_by(attendance_records.c.attendance_date.desc())
                        .offset(offset)
                        .limit(page_size)
                    )
                )
                .mappings()
                .all()
            )
            items = [
                {
                    "id": row["id"],
                    "label": f"{row['label']} · {_format_date(row['attendance_date'])}",
                    "subtitle": row["status"],
                }
                for row in rows
            ]
            return _page(items, total, page, page_size)
        query = select(
            csv_import_batches.c.id,
            csv_import_batches.c.attendance_date,
            csv_import_batches.c.status,
            csv_import_batches.c.created_at,
        ).where(csv_import_batches.c.kind == "attendance")
        query = query.where(predicate)
        if term:
            query = query.where(_like(term, csv_import_batches.c.status))
        total = await session.scalar(query.with_only_columns(func.count()).order_by(None)) or 0
        rows = (
            (
                await session.execute(
                    query.order_by(csv_import_batches.c.created_at.desc())
                    .offset(offset)
                    .limit(page_size)
                )
            )
            .mappings()
            .all()
        )
        items = [
            {
                "id": row["id"],
                "label": "Attendance import · "
                + (_format_date(row["attendance_date"]) or row["created_at"].date().isoformat()),
                "subtitle": row["status"],
            }
            for row in rows
        ]
        return _page(items, total, page, page_size)

    if kind in {"finance_result", "clawback", "payment"}:
        scope = finance_link_scope(actor, kind)
        if scope is None:
            return _empty(page, page_size)
        source, predicate = scope
        if kind == "payment":
            query = (
                select(
                    payment_records.c.id,
                    employees.c.full_name.label("label"),
                    payment_records.c.payment_type,
                    payment_records.c.payment_month,
                )
                .select_from(source)
                .join(employees, employees.c.id == payment_records.c.employee_id)
            )
            query = query.where(predicate)
            if term:
                query = query.where(
                    _like(term, employees.c.full_name, payment_records.c.payment_type)
                )
            total = await session.scalar(query.with_only_columns(func.count()).order_by(None)) or 0
            rows = (
                (
                    await session.execute(
                        query.order_by(payment_records.c.payment_month.desc())
                        .offset(offset)
                        .limit(page_size)
                    )
                )
                .mappings()
                .all()
            )
            items = [
                {
                    "id": row["id"],
                    "label": row["label"],
                    "subtitle": f"{row['payment_type']} · {_format_date(row['payment_month'])[:7]}",
                }
                for row in rows
            ]
            return _page(items, total, page, page_size)
        if kind == "clawback":
            query = select(
                clawbacks.c.id,
                cases.c.internal_case_id.label("label"),
                clawbacks.c.clawback_date,
            ).select_from(source)
            query = query.where(predicate)
            if term:
                query = query.where(_like(term, cases.c.internal_case_id))
            total = await session.scalar(query.with_only_columns(func.count()).order_by(None)) or 0
            rows = (
                (
                    await session.execute(
                        query.order_by(clawbacks.c.clawback_date.desc())
                        .offset(offset)
                        .limit(page_size)
                    )
                )
                .mappings()
                .all()
            )
            items = [
                {
                    "id": row["id"],
                    "label": row["label"],
                    "subtitle": _format_date(row["clawback_date"]),
                }
                for row in rows
            ]
            return _page(items, total, page, page_size)
        query = select(
            case_financial_results.c.id,
            cases.c.internal_case_id.label("label"),
            case_financial_results.c.product_code.label("subtitle"),
        ).select_from(source)
        query = query.where(predicate)
        if term:
            query = query.where(
                _like(term, cases.c.internal_case_id, case_financial_results.c.product_code)
            )
        return await _fetch(
            session,
            query.order_by(cases.c.internal_case_id),
            page=page,
            page_size=page_size,
            offset=offset,
        )

    return _empty(page, page_size)


async def _fetch(
    session: AsyncSession,
    ordered,
    *,
    page: int,
    page_size: int,
    offset: int,
    subtitle_key: str | None = None,
) -> dict:
    total = (
        await session.scalar(select(func.count()).select_from(ordered.order_by(None).subquery()))
        or 0
    )
    rows = (await session.execute(ordered.offset(offset).limit(page_size))).mappings().all()
    items = []
    for row in rows:
        subtitle = row.get("subtitle")
        if subtitle_key:
            subtitle = row.get(subtitle_key)
        items.append(
            {
                "id": row["id"],
                "label": str(row["label"] or "Related record"),
                "subtitle": str(subtitle) if subtitle else None,
            }
        )
    return _page(items, total, page, page_size)
