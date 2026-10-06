"""Employee visa records with workflow history and linked employee documents."""

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.base import utcnow
from app.db.hr_records import (
    employee_document_types,
    employee_documents,
    visa_record_documents,
    visa_record_events,
    visa_records,
)
from app.errors import ApiError
from app.policies import Actor, require
from app.schemas.hr_records import VisaCreate, VisaDocumentAttach, VisaTransition, VisaUpdate
from app.services.hr_common import dubai_today, iso, names, scoped_employee

TRANSITIONS = {
    "Draft": ("In Progress",),
    "In Progress": ("Active",),
    "Active": ("Renewal In Progress", "Cancellation In Progress"),
    "Renewal In Progress": ("Active",),
    "Cancellation In Progress": ("Cancelled",),
    "Cancelled": (),
}
EXPIRY_TRACKED = {"Active", "Renewal In Progress", "Cancellation In Progress"}
FIELDS = {
    "visaType": "visa_type",
    "sponsor": "sponsor",
    "visaNumber": "visa_number",
    "fileNumber": "file_number",
    "issueDate": "issue_date",
    "expiryDate": "expiry_date",
    "workPermitNumber": "work_permit_number",
    "workPermitExpiryDate": "work_permit_expiry_date",
    "medicalFitnessDate": "medical_fitness_date",
    "insuranceExpiryDate": "insurance_expiry_date",
    "notes": "notes",
}


def _json(value):
    return value.isoformat() if isinstance(value, date) else value


def _validate(state: dict) -> None:
    if state["issue_date"] and state["expiry_date"] and state["expiry_date"] < state["issue_date"]:
        raise ApiError(422, "VALIDATION_ERROR", "Expiry date cannot be before the issue date")
    if state["status"] not in {"Draft", "In Progress"} and not (
        state["visa_number"] and state["issue_date"] and state["expiry_date"]
    ):
        raise ApiError(
            422,
            "VISA_DETAILS_REQUIRED",
            "An active visa requires the visa or permit number, issue date and expiry date",
        )


async def _event(
    session: AsyncSession,
    actor: Actor,
    record_id: UUID,
    event_type: str,
    *,
    from_status: str | None = None,
    to_status: str | None = None,
    changes: dict | None = None,
    note: str | None = None,
) -> None:
    await session.execute(
        visa_record_events.insert().values(
            id=uuid4(),
            visa_record_id=record_id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            changes=changes,
            note=note,
            actor_employee_id=actor.employee_id,
        )
    )


async def _detail(session: AsyncSession, actor: Actor, rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    ids = [row["id"] for row in rows]
    events = [
        dict(row)
        for row in (
            await session.execute(
                select(visa_record_events)
                .where(visa_record_events.c.visa_record_id.in_(ids))
                .order_by(visa_record_events.c.occurred_at.desc())
            )
        ).mappings()
    ]
    links = [
        dict(row)
        for row in (
            await session.execute(
                select(
                    visa_record_documents,
                    employee_documents.c.series_id,
                    employee_documents.c.version,
                    employee_documents.c.status.label("document_status"),
                    employee_documents.c.original_filename,
                    employee_document_types.c.name.label("type_name"),
                )
                .join(
                    employee_documents,
                    employee_documents.c.id == visa_record_documents.c.document_id,
                )
                .join(
                    employee_document_types,
                    employee_document_types.c.id == employee_documents.c.document_type_id,
                )
                .where(
                    visa_record_documents.c.visa_record_id.in_(ids),
                    visa_record_documents.c.detached_at.is_(None),
                )
                .order_by(visa_record_documents.c.attached_at)
            )
        ).mappings()
    ]
    people = await names(
        session,
        {row["created_by_employee_id"] for row in rows}
        | {row["updated_by_employee_id"] for row in rows}
        | {row["actor_employee_id"] for row in events}
        | {row["attached_by_employee_id"] for row in links},
    )
    today = dubai_today()
    manage = "visa.write" in actor.grants
    output = []
    for row in rows:
        output.append(
            {
                "id": str(row["id"]),
                **{key: _json(row[column]) for key, column in FIELDS.items()},
                "status": row["status"],
                "expired": row["status"] in EXPIRY_TRACKED
                and row["expiry_date"] is not None
                and row["expiry_date"] < today,
                "workPermitExpired": row["status"] in EXPIRY_TRACKED
                and row["work_permit_expiry_date"] is not None
                and row["work_permit_expiry_date"] < today,
                "allowedTransitions": list(TRANSITIONS[row["status"]]) if manage else [],
                "createdByName": people.get(row["created_by_employee_id"]),
                "createdAt": iso(row["created_at"]),
                "updatedByName": people.get(row["updated_by_employee_id"]),
                "updatedAt": iso(row["updated_at"]),
                "documents": [
                    {
                        "linkId": str(link["id"]),
                        "documentId": str(link["document_id"]),
                        "seriesId": str(link["series_id"]),
                        "typeName": link["type_name"],
                        "version": link["version"],
                        "documentStatus": link["document_status"],
                        "originalFilename": link["original_filename"],
                        "attachedByName": people.get(link["attached_by_employee_id"]),
                        "attachedAt": iso(link["attached_at"]),
                    }
                    for link in links
                    if link["visa_record_id"] == row["id"]
                ],
                "events": [
                    {
                        "id": str(event["id"]),
                        "eventType": event["event_type"],
                        "fromStatus": event["from_status"],
                        "toStatus": event["to_status"],
                        "changes": event["changes"],
                        "note": event["note"],
                        "actorName": people.get(event["actor_employee_id"]),
                        "occurredAt": iso(event["occurred_at"]),
                    }
                    for event in events
                    if event["visa_record_id"] == row["id"]
                ],
            }
        )
    return output


async def list_visa_records(session: AsyncSession, actor: Actor, employee_id: UUID) -> dict:
    await scoped_employee(session, actor, employee_id, "visa.read")
    rows = [
        dict(row)
        for row in (
            await session.execute(
                select(visa_records)
                .where(visa_records.c.employee_id == employee_id)
                .order_by(visa_records.c.created_at.desc())
            )
        ).mappings()
    ]
    detailed = await _detail(session, actor, rows)
    current = next((item for item in detailed if item["status"] != "Cancelled"), None)
    return {
        "current": current,
        "history": [item for item in detailed if item is not current],
        "canManage": "visa.write" in actor.grants,
    }


async def _locked_record(session: AsyncSession, actor: Actor, record_id: UUID) -> dict:
    require(actor, "visa.write")
    employee_id = await session.scalar(
        select(visa_records.c.employee_id).where(visa_records.c.id == record_id)
    )
    if employee_id is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    await scoped_employee(session, actor, employee_id, "visa.write")
    row = (
        (
            await session.execute(
                select(visa_records).where(visa_records.c.id == record_id).with_for_update()
            )
        )
        .mappings()
        .one()
    )
    return dict(row)


async def create_visa_record(
    session: AsyncSession, actor: Actor, employee_id: UUID, item: VisaCreate
) -> dict:
    try:
        employee = await scoped_employee(session, actor, employee_id, "visa.write", lock=True)
        if employee["status"] == "Offboarded":
            raise ApiError(
                409,
                "EMPLOYEE_OFFBOARDED",
                "Visa records cannot be added for an Offboarded employee",
            )
        if await session.scalar(
            select(visa_records.c.id).where(
                visa_records.c.employee_id == employee_id, visa_records.c.status != "Cancelled"
            )
        ):
            raise ApiError(
                409, "VISA_CURRENT_EXISTS", "This employee already has a current visa record"
            )
        values = {column: getattr(item, key) for key, column in FIELDS.items()}
        _validate({**values, "status": "Draft"})
        record_id = uuid4()
        await session.execute(
            visa_records.insert().values(
                id=record_id,
                employee_id=employee_id,
                status="Draft",
                created_by_employee_id=actor.employee_id,
                **values,
            )
        )
        await _event(session, actor, record_id, "created", to_status="Draft")
        await audit.record(
            session,
            actor=actor.employee_id,
            action="visa.created",
            module="hr_records",
            entity_type="visa_record",
            entity_id=record_id,
            after={
                "employeeId": str(employee_id),
                "status": "Draft",
                **{key: _json(value) for key, value in item.model_dump().items()},
            },
        )
        await session.commit()
        return {"id": str(record_id), "status": "Draft"}
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(
            409, "VISA_CURRENT_EXISTS", "This employee already has a current visa record"
        ) from exc
    except Exception:
        await session.rollback()
        raise


async def update_visa_record(
    session: AsyncSession, actor: Actor, record_id: UUID, item: VisaUpdate
) -> dict:
    try:
        row = await _locked_record(session, actor, record_id)
        if row["status"] == "Cancelled":
            raise ApiError(409, "VISA_CANCELLED", "A cancelled visa record is read-only")
        provided = item.model_dump(exclude_unset=True)
        for required in ("visaType", "sponsor"):
            if required in provided and provided[required] is None:
                raise ApiError(422, "VALIDATION_ERROR", "Visa type and sponsor are required")
        changes = {
            key: {"before": _json(row[FIELDS[key]]), "after": _json(value)}
            for key, value in provided.items()
            if row[FIELDS[key]] != value
        }
        if not changes:
            await session.rollback()
            return {"id": str(record_id), "status": row["status"], "changed": False}
        state = {**row, **{FIELDS[key]: provided[key] for key in changes}}
        _validate(state)
        await session.execute(
            update(visa_records)
            .where(visa_records.c.id == record_id)
            .values(
                **{FIELDS[key]: provided[key] for key in changes},
                updated_at=utcnow(),
                updated_by_employee_id=actor.employee_id,
            )
        )
        await _event(session, actor, record_id, "updated", changes=changes)
        await audit.record(
            session,
            actor=actor.employee_id,
            action="visa.updated",
            module="hr_records",
            entity_type="visa_record",
            entity_id=record_id,
            before={key: change["before"] for key, change in changes.items()},
            after={key: change["after"] for key, change in changes.items()},
        )
        await session.commit()
        return {"id": str(record_id), "status": row["status"], "changed": True}
    except Exception:
        await session.rollback()
        raise


async def transition_visa_record(
    session: AsyncSession, actor: Actor, record_id: UUID, item: VisaTransition
) -> dict:
    try:
        row = await _locked_record(session, actor, record_id)
        if row["status"] != item.fromStatus:
            raise ApiError(
                409, "VISA_STATUS_CHANGED", "The visa status changed; reload and try again"
            )
        if item.toStatus not in TRANSITIONS[row["status"]]:
            raise ApiError(
                422,
                "VISA_TRANSITION_INVALID",
                f"A visa cannot move from {row['status']} to {item.toStatus}",
            )
        _validate({**row, "status": item.toStatus})
        await session.execute(
            update(visa_records)
            .where(visa_records.c.id == record_id)
            .values(
                status=item.toStatus,
                updated_at=utcnow(),
                updated_by_employee_id=actor.employee_id,
            )
        )
        await _event(
            session,
            actor,
            record_id,
            "status_changed",
            from_status=row["status"],
            to_status=item.toStatus,
            note=item.note,
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="visa.status_changed",
            module="hr_records",
            entity_type="visa_record",
            entity_id=record_id,
            before={"status": row["status"]},
            after={"status": item.toStatus, "note": item.note},
        )
        await session.commit()
        return {"id": str(record_id), "status": item.toStatus}
    except Exception:
        await session.rollback()
        raise


async def attach_document(
    session: AsyncSession, actor: Actor, record_id: UUID, item: VisaDocumentAttach
) -> dict:
    try:
        require(actor, "employee_document.read")
        row = await _locked_record(session, actor, record_id)
        if row["status"] == "Cancelled":
            raise ApiError(409, "VISA_CANCELLED", "A cancelled visa record is read-only")
        try:
            document_id = UUID(item.documentId)
        except ValueError as exc:
            raise ApiError(422, "VALIDATION_ERROR", "Document unavailable") from exc
        document = (
            (
                await session.execute(
                    select(employee_documents).where(employee_documents.c.id == document_id)
                )
            )
            .mappings()
            .one_or_none()
        )
        if document is None or document["employee_id"] != row["employee_id"]:
            raise ApiError(422, "VALIDATION_ERROR", "Document unavailable")
        if document["status"] != "Current":
            raise ApiError(
                422, "DOCUMENT_NOT_CURRENT", "Only a current document version can be attached"
            )
        if await session.scalar(
            select(visa_record_documents.c.id).where(
                visa_record_documents.c.visa_record_id == record_id,
                visa_record_documents.c.document_id == document_id,
                visa_record_documents.c.detached_at.is_(None),
            )
        ):
            raise ApiError(409, "VISA_DOCUMENT_ATTACHED", "This document is already attached")
        link_id = uuid4()
        await session.execute(
            visa_record_documents.insert().values(
                id=link_id,
                visa_record_id=record_id,
                document_id=document_id,
                attached_by_employee_id=actor.employee_id,
            )
        )
        await _event(
            session,
            actor,
            record_id,
            "document_attached",
            changes={"documentId": str(document_id), "version": document["version"]},
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="visa.document_attached",
            module="hr_records",
            entity_type="visa_record",
            entity_id=record_id,
            after={"documentId": str(document_id), "version": document["version"]},
        )
        await session.commit()
        return {"linkId": str(link_id)}
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(409, "VISA_DOCUMENT_ATTACHED", "This document is already attached") from exc
    except Exception:
        await session.rollback()
        raise


async def detach_document(
    session: AsyncSession, actor: Actor, record_id: UUID, link_id: UUID
) -> None:
    try:
        row = await _locked_record(session, actor, record_id)
        if row["status"] == "Cancelled":
            raise ApiError(409, "VISA_CANCELLED", "A cancelled visa record is read-only")
        link = (
            (
                await session.execute(
                    select(visa_record_documents)
                    .where(
                        visa_record_documents.c.id == link_id,
                        visa_record_documents.c.visa_record_id == record_id,
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if link is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
        if link["detached_at"] is not None:
            raise ApiError(409, "VISA_DOCUMENT_DETACHED", "This document is already detached")
        await session.execute(
            update(visa_record_documents)
            .where(visa_record_documents.c.id == link_id)
            .values(detached_at=utcnow(), detached_by_employee_id=actor.employee_id)
        )
        await _event(
            session,
            actor,
            record_id,
            "document_detached",
            changes={"documentId": str(link["document_id"])},
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="visa.document_detached",
            module="hr_records",
            entity_type="visa_record",
            entity_id=record_id,
            before={"documentId": str(link["document_id"])},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
