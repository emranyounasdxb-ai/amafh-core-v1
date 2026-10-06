"""Approval and initial booking as locked, auditable Case commands."""

from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.base import utcnow
from app.db.cases import (
    case_approvals,
    case_lifecycle_history,
    case_stage_history,
    cases,
)
from app.db.operations import notifications
from app.db.organization import designations, employees
from app.errors import ApiError
from app.normalization import identifier
from app.policies import Actor, require
from app.services.idempotency import claim, complete
from app.services.notification_events import notify
from app.services.pipelines import _valid_stage_set


async def _locked_case(session: AsyncSession, case_id: UUID):
    row = (
        (await session.execute(select(cases).where(cases.c.id == case_id).with_for_update()))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return row


async def approve(
    session: AsyncSession, actor: Actor, case_id: UUID, coordinator_id: UUID, key: str
) -> dict:
    require(actor, "case.approve")
    try:
        record_id, replay = await claim(
            session,
            actor,
            "case.approve",
            key,
            {"caseId": str(case_id), "coordinatorId": str(coordinator_id)},
        )
        if replay is not None:
            await session.rollback()
            return replay
        row = await _locked_case(session, case_id)
        if row["administratively_voided_at"] is not None:
            raise ApiError(409, "CASE_VOIDED", "Case is administratively voided")
        if actor.designation == "Sales Manager" and (
            actor.branch_id != row["branch_id"] or actor.department_id != row["department_id"]
        ):
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
        if row["current_status"] != "Pending for Approval":
            raise ApiError(409, "CASE_NOT_PENDING", "Case is not pending approval")
        coordinator = (
            (
                await session.execute(
                    select(
                        employees.c.id,
                        employees.c.status,
                        employees.c.branch_id,
                        employees.c.department_id,
                        designations.c.name.label("role"),
                    )
                    .select_from(
                        employees.join(
                            designations, employees.c.designation_id == designations.c.id
                        )
                    )
                    .where(employees.c.id == coordinator_id)
                    .with_for_update(read=True)
                )
            )
            .mappings()
            .one_or_none()
        )
        if coordinator is None or (
            coordinator["status"] != "Active"
            or coordinator["role"] != "Coordinator"
            or coordinator["branch_id"] != row["branch_id"]
            or coordinator["department_id"] != row["department_id"]
        ):
            raise ApiError(422, "INVALID_COORDINATOR", "Coordinator is unavailable")
        now = utcnow()
        prior_status = row["owner_transfer_previous_status"]
        next_status = (
            prior_status
            if prior_status is not None and prior_status != "Pending for Approval"
            else "Approved"
        )
        await session.execute(
            update(cases)
            .where(cases.c.id == case_id)
            .values(
                current_status=next_status,
                coordinator_employee_id=coordinator_id,
                owner_transfer_previous_status=None,
                updated_at=now,
            )
        )
        await session.execute(
            case_approvals.insert().values(
                id=uuid4(),
                case_id=case_id,
                approved_by_employee_id=actor.employee_id,
                coordinator_employee_id=coordinator_id,
                approved_at=now,
            )
        )
        await session.execute(
            case_lifecycle_history.insert().values(
                id=uuid4(),
                case_id=case_id,
                previous_status="Pending for Approval",
                status=next_status,
                actor_employee_id=actor.employee_id,
                occurred_at=now,
                context={
                    "coordinatorEmployeeId": str(coordinator_id),
                    "ownerTransferReapproval": prior_status is not None,
                },
            )
        )
        await session.execute(
            notifications.insert().values(
                id=uuid4(),
                recipient_employee_id=coordinator_id,
                kind="case.approved",
                case_id=case_id,
                message=f"Case {row['internal_case_id']} is assigned to you",
            )
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="case.approved",
            module="cases",
            entity_type="case",
            entity_id=case_id,
            before={"status": "Pending for Approval", "coordinatorEmployeeId": None},
            after={"status": next_status, "coordinatorEmployeeId": str(coordinator_id)},
        )
        result = {
            "id": str(case_id),
            "status": next_status,
            "coordinatorEmployeeId": str(coordinator_id),
        }
        await complete(session, record_id, 200, result)
        await session.commit()
        return result
    except Exception:
        await session.rollback()
        raise


async def book(
    session: AsyncSession, actor: Actor, case_id: UUID, bank_number: str, key: str
) -> dict:
    require(actor, "case.book")
    bank_number = identifier(bank_number)
    if not bank_number:
        raise ApiError(422, "BANK_CASE_NUMBER_REQUIRED", "Bank Case Number is required")
    try:
        record_id, replay = await claim(
            session,
            actor,
            "case.book",
            key,
            {"caseId": str(case_id), "bankCaseNumber": bank_number},
        )
        if replay is not None:
            await session.rollback()
            return replay
        row = await _locked_case(session, case_id)
        if row["administratively_voided_at"] is not None:
            raise ApiError(409, "CASE_VOIDED", "Case is administratively voided")
        if (
            actor.designation == "Coordinator"
            and row["coordinator_employee_id"] != actor.employee_id
        ):
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
        if row["current_status"] != "Approved" or row["bank_case_number"] is not None:
            raise ApiError(409, "CASE_NOT_APPROVED", "Case cannot be booked")
        if row["pipeline_configuration_id"] is None:
            raise ApiError(409, "NO_PIPELINE", "Case has no retained Pipeline Configuration")
        stages = await _valid_stage_set(session, row["pipeline_configuration_id"])
        first = stages[0]
        if first["is_final"]:
            raise ApiError(422, "INVALID_PIPELINE", "Initial stage cannot be final")
        now = utcnow()
        await session.execute(
            update(cases)
            .where(cases.c.id == case_id)
            .values(
                bank_case_number=bank_number,
                current_status="Booked",
                current_stage=first["name"],
                updated_at=now,
            )
        )
        await session.execute(
            case_stage_history.insert().values(
                id=uuid4(),
                case_id=case_id,
                stage=first["name"],
                status="Booked",
                updated_by_employee_id=actor.employee_id,
                occurred_at=now,
            )
        )
        await session.execute(
            case_lifecycle_history.insert().values(
                id=uuid4(),
                case_id=case_id,
                previous_status="Approved",
                status="Booked",
                actor_employee_id=actor.employee_id,
                occurred_at=now,
                context={"stage": first["name"]},
            )
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="case.booked",
            module="cases",
            entity_type="case",
            entity_id=case_id,
            before={"status": "Approved", "bankCaseNumber": None, "stage": None},
            after={"status": "Booked", "bankCaseNumber": bank_number, "stage": first["name"]},
        )
        await notify(
            session,
            {row["owner_employee_id"], row["created_by_employee_id"]},
            "case.booked",
            "A Case was booked",
            case_id=case_id,
        )
        result = {
            "id": str(case_id),
            "status": "Booked",
            "bankCaseNumber": bank_number,
            "currentStage": first["name"],
        }
        await complete(session, record_id, 200, result)
        await session.commit()
        return result
    except Exception:
        await session.rollback()
        raise
