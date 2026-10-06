"""Explicit Owner corrections and reopen, separate from normal processing."""

from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.base import utcnow
from app.db.cases import case_lifecycle_history, case_ownership_history, case_stage_history, cases
from app.db.organization import designations, employees
from app.errors import ApiError
from app.normalization import identifier
from app.policies import Actor, require
from app.schemas.cases import ConfirmedAction, OwnerCorrection
from app.services.case_transitions import _locked_case
from app.services.pipelines import _valid_stage_set

FINAL = {"Completed", "Rejected"}
REOPENED = "Case Reopened by Owner"


async def correct(
    session: AsyncSession, actor: Actor, case_id: UUID, item: OwnerCorrection
) -> dict:
    require(actor, "case.correct")
    try:
        row = await _locked_case(session, case_id)
        if row["administratively_voided_at"] is not None:
            raise ApiError(409, "CASE_VOIDED", "Case is administratively voided")
        now = utcnow()
        before: dict = {}
        after: dict = {}
        values: dict = {"updated_at": now}
        if item.ownerEmployeeId is not None:
            replacement = (
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
                        .where(employees.c.id == item.ownerEmployeeId)
                        .with_for_update(read=True)
                    )
                )
                .mappings()
                .one_or_none()
            )
            if replacement is None or (
                replacement["status"] != "Active"
                or replacement["role"]
                not in {"Sales Manager", "Coordinator", "Team Leader", "Sales Executive"}
                or replacement["branch_id"] is None
                or replacement["department_id"] is None
            ):
                raise ApiError(422, "INVALID_CASE_OWNER", "Case Owner is unavailable")
            if replacement["id"] == row["owner_employee_id"]:
                raise ApiError(409, "UNCHANGED", "Case Owner is unchanged")
            scope_changed = (
                replacement["branch_id"] != row["branch_id"]
                or replacement["department_id"] != row["department_id"]
            )
            before = {
                "ownerEmployeeId": str(row["owner_employee_id"]),
                "branchId": str(row["branch_id"]),
                "departmentId": str(row["department_id"]),
                "coordinatorEmployeeId": str(row["coordinator_employee_id"])
                if row["coordinator_employee_id"]
                else None,
                "status": row["current_status"],
            }
            after = {
                "ownerEmployeeId": str(replacement["id"]),
                "branchId": str(replacement["branch_id"]),
                "departmentId": str(replacement["department_id"]),
                "coordinatorEmployeeId": None if scope_changed else before["coordinatorEmployeeId"],
                "status": "Pending for Approval" if scope_changed else row["current_status"],
            }
            values.update(
                owner_employee_id=replacement["id"],
                branch_id=replacement["branch_id"],
                department_id=replacement["department_id"],
            )
            if scope_changed:
                previous_status = row["owner_transfer_previous_status"] or row["current_status"]
                values.update(
                    coordinator_employee_id=None,
                    current_status="Pending for Approval",
                    owner_transfer_previous_status=previous_status,
                )
                await session.execute(
                    case_lifecycle_history.insert().values(
                        id=uuid4(),
                        case_id=case_id,
                        previous_status=row["current_status"],
                        status="Pending for Approval",
                        actor_employee_id=actor.employee_id,
                        occurred_at=now,
                        context={
                            "ownerTransfer": True,
                            "previousOwnerEmployeeId": str(row["owner_employee_id"]),
                            "newOwnerEmployeeId": str(replacement["id"]),
                            "previousBranchId": str(row["branch_id"]),
                            "newBranchId": str(replacement["branch_id"]),
                            "previousDepartmentId": str(row["department_id"]),
                            "newDepartmentId": str(replacement["department_id"]),
                            "previousCoordinatorEmployeeId": before["coordinatorEmployeeId"],
                            "previousWorkflowStatus": previous_status,
                            "reason": item.reason,
                        },
                    )
                )
            closed = await session.execute(
                update(case_ownership_history)
                .where(
                    case_ownership_history.c.case_id == case_id,
                    case_ownership_history.c.ended_at.is_(None),
                )
                .values(ended_at=now)
            )
            if getattr(closed, "rowcount", 0) != 1:
                raise ApiError(
                    409, "OWNERSHIP_HISTORY_INVALID", "Current owner history unavailable"
                )
            await session.execute(
                case_ownership_history.insert().values(
                    id=uuid4(),
                    case_id=case_id,
                    owner_employee_id=replacement["id"],
                    started_at=now,
                    changed_by_employee_id=actor.employee_id,
                )
            )
        elif item.bankCaseNumber is not None:
            number = identifier(item.bankCaseNumber)
            if not number:
                raise ApiError(422, "BANK_CASE_NUMBER_REQUIRED", "Bank Case Number is required")
            if row["bank_case_number"] is None:
                raise ApiError(409, "NOT_BOOKED", "Bank Case Number has not been recorded")
            if row["bank_case_number"] == number:
                raise ApiError(409, "UNCHANGED", "Bank Case Number is unchanged")
            before, after = {"bankCaseNumber": row["bank_case_number"]}, {"bankCaseNumber": number}
            values["bank_case_number"] = number
        elif item.currentStage is not None:
            if row["owner_transfer_previous_status"] is not None:
                raise ApiError(409, "CASE_PENDING_APPROVAL", "Case awaits Coordinator approval")
            if row["pipeline_configuration_id"] is None or row["bank_case_number"] is None:
                raise ApiError(409, "NOT_BOOKED", "Case is not booked")
            stages = await _valid_stage_set(session, row["pipeline_configuration_id"])
            stage = next((s for s in stages if s["name"] == item.currentStage), None)
            if stage is None:
                raise ApiError(422, "INVALID_STAGE", "Stage is not in the retained Pipeline")
            if stage["final_status"] == "Completed" and row["current_status"] != "Completed":
                raise ApiError(
                    409, "COMPLETION_REQUIRES_CSV", "Completion requires a validated bank-stage CSV"
                )
            if row["current_stage"] == stage["name"]:
                raise ApiError(409, "UNCHANGED", "Case stage is unchanged")
            if row["current_status"] in FINAL and not stage["is_final"]:
                raise ApiError(409, "FINAL_LOCK", "Reopen this final Case before a nonfinal stage")
            before = {"stage": row["current_stage"], "status": row["current_status"]}
            status = stage["final_status"] or (
                "Booked" if row["current_status"] == REOPENED else row["current_status"]
            )
            after = {"stage": stage["name"], "status": status}
            values["current_stage"] = stage["name"]
            if status != row["current_status"]:
                values.update(current_status=status, finalized_at=now if status in FINAL else None)
                await session.execute(
                    case_lifecycle_history.insert().values(
                        id=uuid4(),
                        case_id=case_id,
                        previous_status=row["current_status"],
                        status=status,
                        actor_employee_id=actor.employee_id,
                        occurred_at=now,
                        context={"ownerCorrection": True},
                    )
                )
            await session.execute(
                case_stage_history.insert().values(
                    id=uuid4(),
                    case_id=case_id,
                    stage=stage["name"],
                    status=status,
                    updated_by_employee_id=actor.employee_id,
                    occurred_at=now,
                    remark=f"Owner correction: {item.reason}",
                )
            )
        await session.execute(update(cases).where(cases.c.id == case_id).values(**values))
        await audit.record(
            session,
            actor=actor.employee_id,
            action="case.corrected",
            module="cases",
            entity_type="case",
            entity_id=case_id,
            before=before,
            after=after,
            context={"reason": item.reason},
        )
        await session.commit()
        return {"id": str(case_id), "before": before, "after": after}
    except Exception:
        await session.rollback()
        raise


async def reopen(session: AsyncSession, actor: Actor, case_id: UUID, item: ConfirmedAction) -> dict:
    require(actor, "case.correct")
    try:
        row = await _locked_case(session, case_id)
        if row["administratively_voided_at"] is not None:
            raise ApiError(409, "CASE_VOIDED", "Case is administratively voided")
        if row["current_status"] not in FINAL:
            raise ApiError(409, "NOT_FINAL", "Only a final Case may be reopened")
        now = utcnow()
        await session.execute(
            update(cases)
            .where(cases.c.id == case_id)
            .values(
                current_status=REOPENED,
                current_stage=REOPENED,
                finalized_at=None,
                updated_at=now,
            )
        )
        await session.execute(
            case_lifecycle_history.insert().values(
                id=uuid4(),
                case_id=case_id,
                previous_status=row["current_status"],
                status=REOPENED,
                actor_employee_id=actor.employee_id,
                occurred_at=now,
                context={"reason": item.reason, "ownerReopen": True},
            )
        )
        await session.execute(
            case_stage_history.insert().values(
                id=uuid4(),
                case_id=case_id,
                stage=REOPENED,
                status=REOPENED,
                updated_by_employee_id=actor.employee_id,
                occurred_at=now,
                remark=f"Owner reopen: {item.reason}",
            )
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="case.reopened",
            module="cases",
            entity_type="case",
            entity_id=case_id,
            before={
                "status": row["current_status"],
                "stage": row["current_stage"],
                "finalizedAt": row["finalized_at"].isoformat() if row["finalized_at"] else None,
            },
            after={"status": REOPENED, "stage": REOPENED, "finalizedAt": None},
            context={"reason": item.reason},
        )
        await session.commit()
        return {"id": str(case_id), "status": REOPENED, "currentStage": REOPENED}
    except Exception:
        await session.rollback()
        raise
