"""Atomic Customer reuse and Case creation from confirmed interest."""

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.base import utcnow
from app.db.cases import (
    bank_product_mappings,
    banks,
    case_lifecycle_history,
    case_ownership_history,
    cases,
    product_types,
    product_variants,
)
from app.db.operations import notifications
from app.db.organization import branches, departments, designations, employees, user_accounts
from app.errors import ApiError
from app.identifiers import DUBAI, new_case_id
from app.policies import Actor, require
from app.repositories.case_scope import can_own_for_creator
from app.schemas.cases import CaseCreate
from app.services.customer_identity import match_or_create
from app.services.idempotency import claim, complete
from app.services.pipelines import effective_pipeline
from app.services.variant_eligibility import validate_salary_criteria


async def _configuration(session: AsyncSession, item: CaseCreate, on) -> tuple[str, object]:
    if item.customer.type == "Individual" and item.customer.salaryAed is None:
        raise ApiError(
            422,
            "SALARY_REQUIRED",
            "Enter the Customer salary",
            {"customer.salaryAed": ["Customer salary is required"]},
        )
    bank = await session.scalar(
        select(banks.c.id)
        .where(banks.c.id == item.bankId, banks.c.active.is_(True))
        .with_for_update(read=True)
    )
    product = (
        (
            await session.execute(
                select(product_types)
                .where(product_types.c.id == item.productTypeId, product_types.c.active.is_(True))
                .with_for_update(read=True)
            )
        )
        .mappings()
        .one_or_none()
    )
    mapping = await session.scalar(
        select(bank_product_mappings.c.id)
        .where(
            bank_product_mappings.c.bank_id == item.bankId,
            bank_product_mappings.c.product_type_id == item.productTypeId,
            bank_product_mappings.c.active.is_(True),
        )
        .with_for_update(read=True)
    )
    if not bank or not product or not mapping:
        raise ApiError(422, "INACTIVE_CONFIGURATION", "Bank and Product are unavailable")
    if product["code"] == "CC":
        if item.productVariantId is None or item.requestedPfAmount is not None:
            raise ApiError(
                422,
                "INVALID_PRODUCT_CONTEXT",
                "Credit Card requires a Variant and no PF amount",
                {
                    "productVariantId" if item.productVariantId is None else "requestedPfAmount": [
                        "Select a Variant"
                        if item.productVariantId is None
                        else "CC does not use a PF amount"
                    ]
                },
            )
        variant = (
            (
                await session.execute(
                    select(product_variants)
                    .where(
                        product_variants.c.id == item.productVariantId,
                        product_variants.c.bank_id == item.bankId,
                        product_variants.c.product_type_id == item.productTypeId,
                        product_variants.c.active.is_(True),
                    )
                    .with_for_update(read=True)
                )
            )
            .mappings()
            .one_or_none()
        )
        if variant is None:
            raise ApiError(
                422,
                "INVALID_VARIANT",
                "Product Variant is unavailable",
                {
                    "productVariantId": [
                        "Choose an active Variant for the selected Bank and Product"
                    ]
                },
            )
        if item.customer.type == "Individual":
            validate_salary_criteria(variant, item.customer.salaryAed)
    elif product["code"] == "PF":
        if item.productVariantId is not None or item.requestedPfAmount is None:
            raise ApiError(
                422,
                "INVALID_PRODUCT_CONTEXT",
                "Personal Finance requires a PF amount and no Variant",
            )
    else:
        raise ApiError(422, "UNSUPPORTED_PRODUCT", "Product has no approved Case path")
    pipeline_id, _ = await effective_pipeline(session, item.bankId, item.productTypeId, on)
    return product["code"], pipeline_id


async def _owner_assignment(session: AsyncSession, actor: Actor, owner_id):
    if not await can_own_for_creator(session, actor, owner_id):
        raise ApiError(403, "OWNER_OUT_OF_SCOPE", "Case Owner is unavailable")
    row = (
        (
            await session.execute(
                select(employees, designations.c.name.label("role"))
                .join(designations, employees.c.designation_id == designations.c.id)
                .where(employees.c.id == owner_id)
                .with_for_update()
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None or row["status"] != "Active":
        raise ApiError(422, "INVALID_CASE_OWNER", "Case Owner is unavailable")
    missing = [
        label
        for label, column in (("Branch", "branch_id"), ("Department", "department_id"))
        if row[column] is None
    ]
    if missing:
        subject = "Your employee record" if owner_id == actor.employee_id else "The Case Owner"
        raise ApiError(
            422,
            "INVALID_CASE_OWNER",
            f"{subject} has no {' or '.join(missing)} assignment. Ask HR to assign the Branch "
            "and Department before creating a Case.",
        )
    if (
        actor.designation == "Team Leader"
        and owner_id != actor.employee_id
        and row["role"] != "Sales Executive"
    ):
        raise ApiError(403, "OWNER_OUT_OF_SCOPE", "Case Owner is unavailable")
    await _require_sales_manager(session, row["branch_id"], row["department_id"])
    return row


def _active_sales_managers(branch_id, department_id):
    return (
        select(employees.c.id)
        .select_from(
            employees.join(designations, employees.c.designation_id == designations.c.id).join(
                user_accounts, user_accounts.c.employee_id == employees.c.id
            )
        )
        .where(
            designations.c.name == "Sales Manager",
            employees.c.status == "Active",
            employees.c.branch_id == branch_id,
            employees.c.department_id == department_id,
            user_accounts.c.access_status == "Active",
        )
    )


async def _require_sales_manager(session: AsyncSession, branch_id, department_id) -> None:
    """Every new Case is approved by a Sales Manager of the owner's Branch and Department."""
    if await session.scalar(_active_sales_managers(branch_id, department_id).limit(1)):
        return
    branch = await session.scalar(select(branches.c.name).where(branches.c.id == branch_id))
    department = await session.scalar(
        select(departments.c.name).where(departments.c.id == department_id)
    )
    raise ApiError(
        422,
        "SALES_MANAGER_UNAVAILABLE",
        f"No active Sales Manager is assigned to {branch} / {department}, so the Case cannot "
        "enter approval. Ask HR to assign a Sales Manager before creating a Case.",
    )


async def _notify_sales_managers(session: AsyncSession, case_id, branch_id, department_id) -> None:
    recipients = (
        (await session.execute(_active_sales_managers(branch_id, department_id))).scalars().all()
    )
    for recipient in recipients:
        await session.execute(
            notifications.insert().values(
                id=uuid4(),
                recipient_employee_id=recipient,
                kind="case.pending_approval",
                case_id=case_id,
                message=f"Case {case_id} is pending approval",
            )
        )


async def create_case(
    session: AsyncSession, actor: Actor, item: CaseCreate, key: str, *, personal: bool = False
) -> dict:
    require(actor, "case.create")
    if personal and item.ownerEmployeeId not in (None, actor.employee_id):
        raise ApiError(403, "OWNER_OUT_OF_SCOPE", "Own Cases can only be created for yourself")
    owner_id = actor.employee_id if personal else item.ownerEmployeeId or actor.employee_id
    try:
        payload = item.model_dump(mode="json")
        # Preserve fingerprints of successful pre-feature requests and Company requests.
        # A genuinely new Individual request still fails the salary check below.
        if item.customer.salaryAed is None:
            payload["customer"].pop("salaryAed", None)
        record_id, replay = await claim(session, actor, "case.create", key, payload)
        if replay is not None:
            await session.rollback()
            return replay
        owner = await _owner_assignment(session, actor, owner_id)
        now = utcnow()
        product_code, pipeline_id = await _configuration(
            session, item, now.astimezone(DUBAI).date()
        )
        customer_id, reused = await match_or_create(session, item.customer, actor)
        case_id, internal_id = uuid4(), await new_case_id(session, now)
        await session.execute(
            cases.insert().values(
                id=case_id,
                internal_case_id=internal_id,
                customer_id=customer_id,
                bank_id=item.bankId,
                product_type_id=item.productTypeId,
                product_variant_id=item.productVariantId,
                requested_pf_amount=item.requestedPfAmount,
                salary_aed=item.customer.salaryAed,
                pipeline_configuration_id=pipeline_id,
                created_by_employee_id=actor.employee_id,
                owner_employee_id=owner_id,
                branch_id=owner["branch_id"],
                department_id=owner["department_id"],
                current_status="Pending for Approval",
                created_at=now,
            )
        )
        await session.execute(
            case_ownership_history.insert().values(
                id=uuid4(),
                case_id=case_id,
                owner_employee_id=owner_id,
                started_at=now,
                changed_by_employee_id=actor.employee_id,
            )
        )
        await session.execute(
            case_lifecycle_history.insert().values(
                id=uuid4(),
                case_id=case_id,
                previous_status=None,
                status="Pending for Approval",
                actor_employee_id=actor.employee_id,
                occurred_at=now,
                context={"customerReused": reused},
            )
        )
        await _notify_sales_managers(session, case_id, owner["branch_id"], owner["department_id"])
        await audit.record(
            session,
            actor=actor.employee_id,
            action="case.created",
            module="cases",
            entity_type="case",
            entity_id=case_id,
            after={
                "internalCaseId": internal_id,
                "customerId": str(customer_id),
                "customerType": item.customer.type,
                "customerReused": reused,
                "product": product_code,
                "bankId": str(item.bankId),
                "productVariantId": str(item.productVariantId) if item.productVariantId else None,
                "salaryAed": str(item.customer.salaryAed)
                if item.customer.salaryAed is not None
                else None,
                "requestedPfAmount": str(item.requestedPfAmount)
                if item.requestedPfAmount
                else None,
                "pipelineConfigurationId": str(pipeline_id),
                "createdByEmployeeId": str(actor.employee_id),
                "ownerEmployeeId": str(owner_id),
                "branchId": str(owner["branch_id"]),
                "departmentId": str(owner["department_id"]),
                "status": "Pending for Approval",
            },
        )
        result = {
            "id": str(case_id),
            "internalCaseId": internal_id,
            "customerId": str(customer_id),
            "customerReused": reused,
            "salaryAed": str(item.customer.salaryAed)
            if item.customer.salaryAed is not None
            else None,
            "createdByEmployeeId": str(actor.employee_id),
            "ownerEmployeeId": str(owner_id),
            "branchId": str(owner["branch_id"]),
            "departmentId": str(owner["department_id"]),
            "pipelineConfigurationId": str(pipeline_id),
            "status": "Pending for Approval",
        }
        await complete(session, record_id, 201, result)
        await session.commit()
        return result
    except Exception:
        await session.rollback()
        raise
