"""Audited, once-only Clawback and manual payment commands."""

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.cases import cases
from app.db.finance import case_financial_results
from app.db.operations import clawbacks, notifications, payment_records
from app.db.organization import designations, employees
from app.errors import ApiError
from app.policies import Actor, require
from app.schemas.finance import ClawbackInput, PaymentInput
from app.services.idempotency import claim, complete


async def _finance_recipients(session: AsyncSession) -> set:
    return set(
        (
            await session.execute(
                select(employees.c.id)
                .select_from(
                    employees.join(designations, employees.c.designation_id == designations.c.id)
                )
                .where(
                    employees.c.status == "Active",
                    designations.c.name.in_(["Owner", "Managing Director", "Finance"]),
                )
            )
        )
        .scalars()
        .all()
    )


async def create_clawback(
    session: AsyncSession, actor: Actor, item: ClawbackInput, key: str
) -> dict:
    require(actor, "finance.write")
    try:
        token, replay = await claim(
            session, actor, "finance.clawback", key, item.model_dump(mode="json")
        )
        if replay is not None:
            await session.rollback()
            return replay
        case = (
            (
                await session.execute(
                    select(cases)
                    .where(cases.c.internal_case_id == item.internalCaseId)
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if case is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
        prior = await session.scalar(
            select(clawbacks.c.id).where(clawbacks.c.case_id == case["id"])
        )
        if prior is not None:
            raise ApiError(409, "CLAWBACK_EXISTS", "A Clawback already exists for this Case")
        credited_owner = await session.scalar(
            select(case_financial_results.c.credited_owner_employee_id).where(
                case_financial_results.c.case_id == case["id"]
            )
        )
        owner_id = credited_owner or case["owner_employee_id"]
        record_id = uuid4()
        await session.execute(
            clawbacks.insert().values(
                id=record_id,
                case_id=case["id"],
                case_owner_employee_id=owner_id,
                amount_aed=item.amountAed,
                clawback_date=item.clawbackDate,
                reason=item.reason,
                created_by_employee_id=actor.employee_id,
            )
        )
        for recipient in (await _finance_recipients(session)) | {owner_id}:
            await session.execute(
                notifications.insert().values(
                    id=uuid4(),
                    recipient_employee_id=recipient,
                    kind="finance.clawback_recorded",
                    case_id=case["id"],
                    message=f"Clawback recorded for Case {case['internal_case_id']}",
                )
            )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="finance.clawback_created",
            module="finance",
            entity_type="clawback",
            entity_id=record_id,
            after={
                "caseId": str(case["id"]),
                "caseOwnerEmployeeId": str(owner_id),
                "amountAed": str(item.amountAed),
                "clawbackDate": item.clawbackDate.isoformat(),
                "reason": item.reason,
            },
            context={"internalCaseId": case["internal_case_id"]},
        )
        response = {
            "id": str(record_id),
            "caseId": str(case["id"]),
            "caseOwnerEmployeeId": str(owner_id),
        }
        await complete(session, token, 201, response)
        await session.commit()
        return response
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(409, "CLAWBACK_EXISTS", "A Clawback already exists for this Case") from exc
    except Exception:
        await session.rollback()
        raise


async def create_payment(session: AsyncSession, actor: Actor, item: PaymentInput, key: str) -> dict:
    require(actor, "finance.write")
    try:
        token, replay = await claim(
            session, actor, "finance.payment", key, item.model_dump(mode="json")
        )
        if replay is not None:
            await session.rollback()
            return replay
        employee = await session.scalar(
            select(employees.c.id)
            .where(employees.c.id == item.employeeId)
            .with_for_update(read=True)
        )
        if employee is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
        prior = await session.scalar(
            select(payment_records.c.id).where(
                payment_records.c.employee_id == item.employeeId,
                payment_records.c.payment_type == item.paymentType,
                payment_records.c.payment_month == item.paymentMonth,
            )
        )
        if prior is not None:
            raise ApiError(409, "PAYMENT_EXISTS", "A payment for this month and type exists")
        record_id = uuid4()
        await session.execute(
            payment_records.insert().values(
                id=record_id,
                employee_id=item.employeeId,
                payment_type=item.paymentType,
                amount_aed=item.amountAed,
                payment_month=item.paymentMonth,
                payment_date=item.paymentDate,
                created_by_employee_id=actor.employee_id,
            )
        )
        await session.execute(
            notifications.insert().values(
                id=uuid4(),
                recipient_employee_id=item.employeeId,
                kind="finance.payment_recorded",
                message=f"{item.paymentType} payment record entered",
            )
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="finance.salary_payment_created"
            if item.paymentType == "Salary"
            else "finance.commission_payment_created",
            module="finance",
            entity_type="payment_record",
            entity_id=record_id,
            after={
                "employeeId": str(item.employeeId),
                "paymentType": item.paymentType,
                "amountAed": str(item.amountAed),
                "paymentMonth": item.paymentMonth.isoformat(),
                "paymentDate": item.paymentDate.isoformat(),
            },
        )
        response = {
            "id": str(record_id),
            "employeeId": str(item.employeeId),
            "paymentType": item.paymentType,
        }
        await complete(session, token, 201, response)
        await session.commit()
        return response
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(409, "PAYMENT_EXISTS", "A payment for this month and type exists") from exc
    except Exception:
        await session.rollback()
        raise
