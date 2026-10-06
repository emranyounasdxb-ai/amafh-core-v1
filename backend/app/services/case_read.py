"""Scope-filtered Case lists, details, queues and retained history."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, String, case, cast, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.cases import (
    banks,
    case_approvals,
    case_lifecycle_history,
    case_ownership_history,
    case_stage_history,
    cases,
    company_customers,
    customers,
    individual_customers,
    product_types,
    product_variants,
)
from app.db.organization import branches
from app.errors import ApiError
from app.policies import Actor, require
from app.repositories.case_scope import case_access, own_case, visible_case
from app.repositories.employee_scope import employee_query


def _value(value):
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _case(row) -> dict:
    fields = {
        "id": "id",
        "internal_case_id": "internalCaseId",
        "customer_id": "customerId",
        "bank_id": "bankId",
        "product_type_id": "productTypeId",
        "product_variant_id": "productVariantId",
        "pipeline_configuration_id": "pipelineConfigurationId",
        "requested_pf_amount": "requestedPfAmount",
        "created_by_employee_id": "createdByEmployeeId",
        "owner_employee_id": "ownerEmployeeId",
        "coordinator_employee_id": "coordinatorEmployeeId",
        "branch_id": "branchId",
        "department_id": "departmentId",
        "current_status": "status",
        "current_stage": "currentStage",
        "bank_case_number": "bankCaseNumber",
        "finalized_at": "finalizedAt",
        "administratively_voided_at": "administrativelyVoidedAt",
        "administratively_voided_by_employee_id": "administrativelyVoidedByEmployeeId",
        "administrative_void_reason": "administrativeVoidReason",
        "created_at": "createdAt",
        "updated_at": "updatedAt",
    }
    return {alias: _value(row[key]) for key, alias in fields.items()}


async def list_cases(
    session: AsyncSession,
    actor: Actor,
    *,
    page: int,
    page_size: int,
    q: str = "",
    status: str | None = None,
    bank_id: UUID | None = None,
    product_id: UUID | None = None,
    owner_id: UUID | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    sort: str = "createdAt",
    direction: str = "desc",
    approval_queue: bool = False,
    view: str = "active",
    own: bool = False,
) -> dict:
    if not own:
        require(actor, "case.read")
    if approval_queue and actor.designation not in {"Owner", "Managing Director", "Sales Manager"}:
        raise ApiError(403, "FORBIDDEN", "Access denied")
    if created_from and created_to and created_from > created_to:
        raise ApiError(422, "INVALID_DATE_RANGE", "Invalid date range")
    predicates = [own_case(actor) if own else visible_case(actor)]
    if view not in {"active", "archived", "all"}:
        raise ApiError(422, "INVALID_CASE_VIEW", "Unsupported Case view")
    if approval_queue or view == "active":
        predicates.append(cases.c.administratively_voided_at.is_(None))
    elif view == "archived":
        predicates.append(cases.c.administratively_voided_at.is_not(None))
    if approval_queue:
        predicates.append(cases.c.current_status == "Pending for Approval")
    elif status:
        predicates.append(cases.c.current_status == status)
    if bank_id:
        predicates.append(cases.c.bank_id == bank_id)
    if product_id:
        predicates.append(cases.c.product_type_id == product_id)
    if owner_id:
        predicates.append(cases.c.owner_employee_id == owner_id)
    if created_from:
        predicates.append(
            func.timezone("Asia/Dubai", cases.c.created_at).cast(Date) >= created_from
        )
    if created_to:
        predicates.append(func.timezone("Asia/Dubai", cases.c.created_at).cast(Date) <= created_to)
    visible_employees = employee_query(actor).subquery()

    def employee_name(employee_id):
        visible_name = (
            select(visible_employees.c.full_name)
            .where(visible_employees.c.id == employee_id)
            .scalar_subquery()
        )
        return func.coalesce(visible_name, literal("Unavailable"))

    customer_name = (
        select(
            func.coalesce(
                individual_customers.c.full_name,
                company_customers.c.company_name,
                customers.c.customer_id,
            )
        )
        .select_from(
            customers.outerjoin(
                individual_customers, individual_customers.c.customer_id == customers.c.id
            ).outerjoin(company_customers, company_customers.c.customer_id == customers.c.id)
        )
        .where(customers.c.id == cases.c.customer_id)
        .scalar_subquery()
    )
    term = q.strip()
    if term:
        pattern = "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        predicates.append(
            or_(
                cases.c.internal_case_id.ilike(pattern, escape="\\"),
                customer_name.ilike(pattern, escape="\\"),
                cases.c.bank_case_number.ilike(pattern, escape="\\"),
                cases.c.current_stage.ilike(pattern, escape="\\"),
                cases.c.current_status.ilike(pattern, escape="\\"),
                employee_name(cases.c.owner_employee_id).ilike(pattern, escape="\\"),
                employee_name(cases.c.created_by_employee_id).ilike(pattern, escape="\\"),
                select(banks.c.name)
                .where(banks.c.id == cases.c.bank_id)
                .scalar_subquery()
                .ilike(pattern, escape="\\"),
            )
        )
    scoped_branch_name = (
        select(branches.c.name).where(branches.c.id == cases.c.branch_id).scalar_subquery()
    )
    branch_name = (
        scoped_branch_name
        if actor.designation in {"Owner", "Managing Director", "HR", "Finance"}
        else case(
            (cases.c.branch_id == actor.branch_id, scoped_branch_name),
            else_=literal("Unavailable"),
        )
    )
    variant_name = (
        select(product_variants.c.name)
        .where(product_variants.c.id == cases.c.product_variant_id)
        .scalar_subquery()
    )
    order = {
        "createdAt": cases.c.created_at,
        "updatedAt": cases.c.updated_at,
        "internalCaseId": cases.c.internal_case_id,
        "customerName": customer_name,
        "productName": select(product_types.c.name)
        .where(product_types.c.id == cases.c.product_type_id)
        .scalar_subquery(),
        "bankName": select(banks.c.name).where(banks.c.id == cases.c.bank_id).scalar_subquery(),
        "variantOrPfAmount": case(
            (cases.c.requested_pf_amount.is_not(None), cast(cases.c.requested_pf_amount, String)),
            else_=variant_name,
        ),
        "createdByName": employee_name(cases.c.created_by_employee_id),
        "ownerName": employee_name(cases.c.owner_employee_id),
        "branchName": branch_name,
        "status": cases.c.current_status,
        "bankCaseNumber": cases.c.bank_case_number,
        "currentStage": cases.c.current_stage,
    }.get(sort)
    if order is None or direction not in {"asc", "desc"}:
        raise ApiError(422, "INVALID_SORT", "Unsupported Case sort")
    total = await session.scalar(select(func.count()).select_from(cases).where(*predicates))
    ordering = (
        [
            (
                cases.c.requested_pf_amount.is_not(None).asc()
                if direction == "asc"
                else cases.c.requested_pf_amount.is_not(None).desc()
            ),
            (
                cases.c.requested_pf_amount.asc()
                if direction == "asc"
                else cases.c.requested_pf_amount.desc()
            ).nulls_last(),
            (variant_name.asc() if direction == "asc" else variant_name.desc()).nulls_last(),
        ]
        if sort == "variantOrPfAmount"
        else [(order.asc() if direction == "asc" else order.desc()).nulls_last()]
    )
    rows = (
        await session.execute(
            select(cases)
            .where(*predicates)
            .order_by(*ordering, cases.c.id)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).mappings()
    return {
        "items": [_case(row) for row in rows],
        "page": page,
        "pageSize": page_size,
        "total": total or 0,
    }


async def get_case(session: AsyncSession, actor: Actor, case_id: UUID) -> dict:
    row = (
        (await session.execute(select(cases).where(cases.c.id == case_id, case_access(actor))))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return _case(row)


async def get_history(session: AsyncSession, actor: Actor, case_id: UUID) -> dict:
    await get_case(session, actor, case_id)
    result = {}
    for key, table, order in (
        ("lifecycle", case_lifecycle_history, case_lifecycle_history.c.occurred_at),
        ("ownership", case_ownership_history, case_ownership_history.c.started_at),
        ("stages", case_stage_history, case_stage_history.c.occurred_at),
        ("approvals", case_approvals, case_approvals.c.approved_at),
    ):
        rows = (
            await session.execute(
                select(table).where(table.c.case_id == case_id).order_by(order, table.c.id)
            )
        ).mappings()
        result[key] = [{column: _value(value) for column, value in row.items()} for row in rows]
    return result
