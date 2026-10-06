"""Owner-only, non-destructive Administrative Void/Archive of a Case."""

from uuid import UUID, uuid4

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.base import utcnow
from app.db.cases import case_lifecycle_history, cases
from app.errors import ApiError
from app.policies import Actor, require
from app.schemas.cases import ConfirmedAction
from app.services.case_transitions import _locked_case


async def administratively_void(
    session: AsyncSession, actor: Actor, case_id: UUID, item: ConfirmedAction
) -> dict:
    require(actor, "case.void")
    try:
        row = await _locked_case(session, case_id)
        if row["administratively_voided_at"] is not None:
            raise ApiError(409, "CASE_VOIDED", "Case is administratively voided")
        now = utcnow()
        await session.execute(
            update(cases)
            .where(cases.c.id == case_id)
            .values(
                administratively_voided_at=now,
                administratively_voided_by_employee_id=actor.employee_id,
                administrative_void_reason=item.reason,
                updated_at=now,
            )
        )
        await session.execute(
            case_lifecycle_history.insert().values(
                id=uuid4(),
                case_id=case_id,
                previous_status=row["current_status"],
                status=row["current_status"],
                actor_employee_id=actor.employee_id,
                occurred_at=now,
                context={"administrativeVoid": True, "reason": item.reason},
            )
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="case.administratively_voided",
            module="cases",
            entity_type="case",
            entity_id=case_id,
            before={
                "administrativelyVoidedAt": None,
                "administrativelyVoidedByEmployeeId": None,
                "status": row["current_status"],
                "currentStage": row["current_stage"],
            },
            after={
                "administrativelyVoidedAt": now.isoformat(),
                "administrativelyVoidedByEmployeeId": str(actor.employee_id),
                "status": row["current_status"],
                "currentStage": row["current_stage"],
            },
            context={
                "reason": item.reason,
                "internalCaseId": row["internal_case_id"],
                "customerId": str(row["customer_id"]),
                "pipelineConfigurationId": str(row["pipeline_configuration_id"])
                if row["pipeline_configuration_id"]
                else None,
            },
        )
        await session.commit()
        return {
            "id": str(case_id),
            "administrativelyVoidedAt": now.isoformat(),
            "administrativelyVoidedByEmployeeId": str(actor.employee_id),
            "administrativeVoidReason": item.reason,
        }
    except Exception:
        await session.rollback()
        raise
