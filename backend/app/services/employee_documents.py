"""Versioned employee documents in protected storage with onboarding requirements."""

import re
from uuid import UUID, uuid4

from fastapi import UploadFile
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.base import utcnow
from app.db.hr_records import employee_document_types, employee_documents
from app.db.operations import stored_files
from app.errors import ApiError
from app.policies import Actor, require
from app.schemas.hr_records import DocumentMetadata, DocumentRequirementUpdate
from app.services.hr_common import dubai_today, iso, names, scoped_employee
from app.services.idempotency import claim, complete
from app.services.media import read_stored_file
from app.services.media_storage import path_for, validated_document, write_document

MULTIPLE_SERIES = {"educational_certificate", "other"}
FILE_REJECTIONS = {"DOCUMENT_SIZE_LIMIT", "DOCUMENT_INVALID", "DOCUMENT_TYPE_INVALID"}
FIELD_LABELS = {
    "documentNumber": ("number_mode", "Document number"),
    "issueDate": ("issue_date_mode", "Issue date"),
    "expiryDate": ("expiry_date_mode", "Expiry date"),
    "issuingCountry": ("country_mode", "Issuing country"),
}


def _type_out(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "code": row["code"],
        "name": row["name"],
        "requiredAtOnboarding": row["required_at_onboarding"],
        "numberMode": row["number_mode"],
        "issueDateMode": row["issue_date_mode"],
        "expiryDateMode": row["expiry_date_mode"],
        "countryMode": row["country_mode"],
    }


async def _types(session: AsyncSession) -> list[dict]:
    rows = await session.execute(
        select(employee_document_types).order_by(employee_document_types.c.sort_order)
    )
    return [dict(row) for row in rows.mappings()]


def _version_out(row: dict, people: dict[UUID, str], today) -> dict:
    return {
        "id": str(row["id"]),
        "version": row["version"],
        "status": row["status"],
        "documentNumber": row["document_number"],
        "issueDate": iso(row["issue_date"]),
        "expiryDate": iso(row["expiry_date"]),
        "expired": row["expiry_date"] is not None and row["expiry_date"] < today,
        "issuingCountry": row["issuing_country"],
        "notes": row["notes"],
        "originalFilename": row["original_filename"],
        "contentType": row["content_type"],
        "byteSize": row["byte_size"],
        "uploadedByName": people.get(row["uploaded_by_employee_id"]),
        "uploadedAt": iso(row["uploaded_at"]),
        "supersededAt": iso(row["superseded_at"]),
        "withdrawnByName": people.get(row["withdrawn_by_employee_id"]),
        "withdrawnAt": iso(row["withdrawn_at"]),
        "withdrawalReason": row["withdrawal_reason"],
    }


def _document_query():
    return select(
        employee_documents,
        stored_files.c.content_type,
        stored_files.c.byte_size,
    ).join(stored_files, stored_files.c.id == employee_documents.c.file_id)


async def series_for_employee(session: AsyncSession, employee_id: UUID) -> list[dict]:
    rows = await session.execute(
        _document_query()
        .where(employee_documents.c.employee_id == employee_id)
        .order_by(employee_documents.c.uploaded_at.desc(), employee_documents.c.version.desc())
    )
    return [dict(row) for row in rows.mappings()]


async def list_documents(session: AsyncSession, actor: Actor, employee_id: UUID) -> dict:
    await scoped_employee(session, actor, employee_id, "employee_document.read")
    types = await _types(session)
    type_by_id = {row["id"]: row for row in types}
    rows = await series_for_employee(session, employee_id)
    people = await names(
        session,
        {row["uploaded_by_employee_id"] for row in rows}
        | {row["withdrawn_by_employee_id"] for row in rows},
    )
    today = dubai_today()
    grouped: dict[UUID, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["series_id"], []).append(row)
    documents = []
    for series_id, versions in grouped.items():
        versions.sort(key=lambda item: item["version"], reverse=True)
        latest = versions[0]
        kind = type_by_id[latest["document_type_id"]]
        documents.append(
            {
                "seriesId": str(series_id),
                "typeId": str(kind["id"]),
                "typeName": kind["name"],
                "status": latest["status"],
                "latest": _version_out(latest, people, today),
                "versions": [_version_out(row, people, today) for row in versions],
            }
        )
    documents.sort(
        key=lambda item: (
            item["status"] != "Current",
            type_by_id[UUID(item["typeId"])]["sort_order"],
        )
    )
    current_types = {row["document_type_id"] for row in rows if row["status"] == "Current"}
    checklist = [
        {"typeId": str(row["id"]), "typeName": row["name"], "satisfied": row["id"] in current_types}
        for row in types
        if row["required_at_onboarding"]
    ]
    return {
        "checklist": checklist,
        "missingRequired": sum(not item["satisfied"] for item in checklist),
        "documents": documents,
        "types": [_type_out(row) for row in types],
        "canUpload": "employee_document.write" in actor.grants,
        "canWithdraw": "employee_document.withdraw" in actor.grants,
    }


def parse_metadata(fields: dict) -> DocumentMetadata:
    try:
        return DocumentMetadata(**fields)
    except ValidationError as exc:
        first = exc.errors()[0]
        message = str(first.get("msg", "Invalid document details")).removeprefix("Value error, ")
        raise ApiError(422, "VALIDATION_ERROR", message) from exc


def _check_modes(kind: dict, item: DocumentMetadata) -> None:
    for field, (column, label) in FIELD_LABELS.items():
        value = getattr(item, field)
        mode = kind[column]
        if mode == "required" and value is None:
            raise ApiError(422, "FIELD_REQUIRED", f"{label} is required for {kind['name']}")
        if mode == "none" and value is not None:
            raise ApiError(422, "FIELD_NOT_APPLICABLE", f"{label} does not apply to {kind['name']}")


def _filename(value: str | None) -> str:
    name = re.split(r"[\\/]", value or "")[-1]
    name = "".join(char for char in name if char.isprintable()).strip()
    return name[:255] or "document"


async def _store(
    session: AsyncSession, actor: Actor, file: UploadFile
) -> tuple[UUID, str, str, int]:
    data, mime, extension = await validated_document(file)
    key = write_document("employee_document", data, extension)
    file_id = uuid4()
    await session.execute(
        stored_files.insert().values(
            id=file_id,
            kind="employee_document",
            storage_key=key,
            content_type=mime,
            byte_size=len(data),
            uploaded_by_employee_id=actor.employee_id,
        )
    )
    return file_id, key, mime, len(data)


def _audit_after(row: dict, kind: dict, mime: str, size: int) -> dict:
    return {
        "employeeId": str(row["employee_id"]),
        "documentType": kind["name"],
        "seriesId": str(row["series_id"]),
        "version": row["version"],
        "contentType": mime,
        "byteSize": size,
        "issueDate": iso(row["issue_date"]),
        "expiryDate": iso(row["expiry_date"]),
        "issuingCountry": row["issuing_country"],
    }


async def _insert_version(
    session: AsyncSession,
    actor: Actor,
    *,
    employee_id: UUID,
    kind: dict,
    series_id: UUID,
    version: int,
    item: DocumentMetadata,
    file: UploadFile,
) -> tuple[dict, str, str, int]:
    file_id, key, mime, size = await _store(session, actor, file)
    row = {
        "id": uuid4(),
        "employee_id": employee_id,
        "document_type_id": kind["id"],
        "series_id": series_id,
        "version": version,
        "status": "Current",
        "document_number": item.documentNumber,
        "issue_date": item.issueDate,
        "expiry_date": item.expiryDate,
        "issuing_country": item.issuingCountry,
        "notes": item.notes,
        "file_id": file_id,
        "original_filename": _filename(file.filename),
        "uploaded_by_employee_id": actor.employee_id,
    }
    await session.execute(employee_documents.insert().values(**row))
    return row, key, mime, size


def _response(row: dict, kind: dict) -> dict:
    return {
        "seriesId": str(row["series_id"]),
        "id": str(row["id"]),
        "version": row["version"],
        "typeName": kind["name"],
    }


async def _reject(
    session: AsyncSession, actor: Actor, employee_id: UUID, exc: Exception, key: str | None
) -> None:
    await session.rollback()
    if key is not None:
        path_for(key).unlink(missing_ok=True)
    if isinstance(exc, ApiError) and exc.code in FILE_REJECTIONS:
        await audit.record(
            session,
            actor=actor.employee_id,
            action="employee_document.upload_rejected",
            module="hr_records",
            entity_type="employee",
            entity_id=employee_id,
            context={"reason": exc.code},
        )
        await session.commit()


async def upload_document(
    session: AsyncSession,
    actor: Actor,
    employee_id: UUID,
    document_type_id: UUID,
    item: DocumentMetadata,
    file: UploadFile,
    idempotency_key: str,
) -> dict:
    key = None
    try:
        employee = await scoped_employee(
            session, actor, employee_id, "employee_document.write", lock=True
        )
        token, replay = await claim(
            session,
            actor,
            "employee_document.upload",
            idempotency_key,
            {
                "employeeId": str(employee_id),
                "documentTypeId": str(document_type_id),
                "filename": file.filename,
                "size": file.size,
                **item.model_dump(mode="json"),
            },
        )
        if replay is not None:
            await session.rollback()
            return replay
        if employee["status"] == "Offboarded":
            raise ApiError(
                409, "EMPLOYEE_OFFBOARDED", "Documents cannot be added for an Offboarded employee"
            )
        kind_row = (
            (
                await session.execute(
                    select(employee_document_types).where(
                        employee_document_types.c.id == document_type_id
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        if kind_row is None:
            raise ApiError(422, "VALIDATION_ERROR", "Document type unavailable")
        kind = dict(kind_row)
        _check_modes(kind, item)
        if kind["code"] not in MULTIPLE_SERIES and await session.scalar(
            select(employee_documents.c.id).where(
                employee_documents.c.employee_id == employee_id,
                employee_documents.c.document_type_id == document_type_id,
                employee_documents.c.status == "Current",
            )
        ):
            raise ApiError(
                409,
                "DOCUMENT_EXISTS",
                f"A current {kind['name']} exists. Replace it to add a new version.",
            )
        series_id = uuid4()
        row, key, mime, size = await _insert_version(
            session,
            actor,
            employee_id=employee_id,
            kind=kind,
            series_id=series_id,
            version=1,
            item=item,
            file=file,
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="employee_document.uploaded",
            module="hr_records",
            entity_type="employee_document",
            entity_id=row["id"],
            after=_audit_after(row, kind, mime, size),
        )
        response = _response(row, kind)
        await complete(session, token, 201, response)
        await session.commit()
        return response
    except IntegrityError as exc:
        await _reject(session, actor, employee_id, exc, key)
        raise ApiError(409, "CONFLICT", "The document changed; reload and try again") from exc
    except Exception as exc:
        await _reject(session, actor, employee_id, exc, key)
        raise


async def _current_version(session: AsyncSession, series_id: UUID) -> dict:
    row = (
        (
            await session.execute(
                select(employee_documents)
                .where(employee_documents.c.series_id == series_id)
                .order_by(employee_documents.c.version.desc())
                .limit(1)
                .with_for_update()
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    return dict(row)


async def replace_document(
    session: AsyncSession,
    actor: Actor,
    series_id: UUID,
    replaces_version: int,
    item: DocumentMetadata,
    file: UploadFile,
    idempotency_key: str,
) -> dict:
    key = None
    employee_id = None
    try:
        require(actor, "employee_document.write")
        owner_id = await session.scalar(
            select(employee_documents.c.employee_id)
            .where(employee_documents.c.series_id == series_id)
            .limit(1)
        )
        if owner_id is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
        employee_id = owner_id
        employee = await scoped_employee(
            session, actor, employee_id, "employee_document.write", lock=True
        )
        token, replay = await claim(
            session,
            actor,
            "employee_document.replace",
            idempotency_key,
            {
                "seriesId": str(series_id),
                "replacesVersion": replaces_version,
                "filename": file.filename,
                "size": file.size,
                **item.model_dump(mode="json"),
            },
        )
        if replay is not None:
            await session.rollback()
            return replay
        if employee["status"] == "Offboarded":
            raise ApiError(
                409, "EMPLOYEE_OFFBOARDED", "Documents cannot be added for an Offboarded employee"
            )
        current = await _current_version(session, series_id)
        if current["status"] != "Current":
            raise ApiError(409, "DOCUMENT_NOT_CURRENT", "A withdrawn document cannot be replaced")
        if current["version"] != replaces_version:
            raise ApiError(
                409, "DOCUMENT_VERSION_CHANGED", "The document changed; reload and try again"
            )
        kind = dict(
            (
                await session.execute(
                    select(employee_document_types).where(
                        employee_document_types.c.id == current["document_type_id"]
                    )
                )
            )
            .mappings()
            .one()
        )
        _check_modes(kind, item)
        await session.execute(
            update(employee_documents)
            .where(employee_documents.c.id == current["id"])
            .values(status="Superseded", superseded_at=utcnow())
        )
        row, key, mime, size = await _insert_version(
            session,
            actor,
            employee_id=employee_id,
            kind=kind,
            series_id=series_id,
            version=current["version"] + 1,
            item=item,
            file=file,
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="employee_document.replaced",
            module="hr_records",
            entity_type="employee_document",
            entity_id=row["id"],
            before={"id": str(current["id"]), "version": current["version"]},
            after=_audit_after(row, kind, mime, size),
        )
        response = _response(row, kind)
        await complete(session, token, 201, response)
        await session.commit()
        return response
    except IntegrityError as exc:
        if employee_id is None:
            await session.rollback()
            raise
        await _reject(session, actor, employee_id, exc, key)
        raise ApiError(409, "CONFLICT", "The document changed; reload and try again") from exc
    except Exception as exc:
        if employee_id is None:
            await session.rollback()
            raise
        await _reject(session, actor, employee_id, exc, key)
        raise


async def withdraw_document(
    session: AsyncSession, actor: Actor, series_id: UUID, reason: str
) -> None:
    try:
        require(actor, "employee_document.withdraw")
        employee_id = await session.scalar(
            select(employee_documents.c.employee_id)
            .where(employee_documents.c.series_id == series_id)
            .limit(1)
        )
        if employee_id is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
        await scoped_employee(session, actor, employee_id, "employee_document.withdraw", lock=True)
        current = await _current_version(session, series_id)
        if current["status"] != "Current":
            raise ApiError(409, "DOCUMENT_NOT_CURRENT", "The document is already withdrawn")
        await session.execute(
            update(employee_documents)
            .where(employee_documents.c.id == current["id"])
            .values(
                status="Withdrawn",
                withdrawn_by_employee_id=actor.employee_id,
                withdrawn_at=utcnow(),
                withdrawal_reason=reason,
            )
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="employee_document.withdrawn",
            module="hr_records",
            entity_type="employee_document",
            entity_id=current["id"],
            before={"status": "Current"},
            after={"status": "Withdrawn", "reason": reason, "version": current["version"]},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def download_version(
    session: AsyncSession, actor: Actor, version_id: UUID
) -> tuple[bytes, str, str]:
    require(actor, "employee_document.read")
    row = (
        (
            await session.execute(
                select(employee_documents, employee_document_types.c.code)
                .join(
                    employee_document_types,
                    employee_document_types.c.id == employee_documents.c.document_type_id,
                )
                .where(employee_documents.c.id == version_id)
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    await scoped_employee(session, actor, row["employee_id"], "employee_document.read")
    data, mime = await read_stored_file(session, row["file_id"], "employee_document")
    await audit.record(
        session,
        actor=actor.employee_id,
        action="employee_document.downloaded",
        module="hr_records",
        entity_type="employee_document",
        entity_id=version_id,
        context={"version": row["version"]},
    )
    await session.commit()
    extension = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png"}[mime]
    return data, mime, f"{row['code'].replace('_', '-')}-v{row['version']}.{extension}"


async def list_types(session: AsyncSession, actor: Actor) -> list[dict]:
    if not ({"employee_document.read", "hr_settings.write"} & actor.grants):
        raise ApiError(403, "FORBIDDEN", "Access denied")
    return [_type_out(row) for row in await _types(session)]


async def update_requirement(
    session: AsyncSession, actor: Actor, type_id: UUID, item: DocumentRequirementUpdate
) -> dict:
    require(actor, "hr_settings.write")
    try:
        row = (
            (
                await session.execute(
                    select(employee_document_types)
                    .where(employee_document_types.c.id == type_id)
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
        if row["required_at_onboarding"] != item.requiredAtOnboarding:
            await session.execute(
                update(employee_document_types)
                .where(employee_document_types.c.id == type_id)
                .values(
                    required_at_onboarding=item.requiredAtOnboarding,
                    updated_at=utcnow(),
                    updated_by_employee_id=actor.employee_id,
                )
            )
            await audit.record(
                session,
                actor=actor.employee_id,
                action="employee_document_type.requirement_updated",
                module="hr_records",
                entity_type="employee_document_type",
                entity_id=type_id,
                before={"requiredAtOnboarding": row["required_at_onboarding"]},
                after={"requiredAtOnboarding": item.requiredAtOnboarding},
            )
        await session.commit()
        return {**_type_out(dict(row)), "requiredAtOnboarding": item.requiredAtOnboarding}
    except Exception:
        await session.rollback()
        raise
