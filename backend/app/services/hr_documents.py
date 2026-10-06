"""Prepared, approved, numbered and preserved employee letters and certificates."""

from uuid import UUID, uuid4

from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.base import utcnow
from app.db.hr_records import hr_document_issuances
from app.db.operations import stored_files
from app.errors import ApiError
from app.policies import Actor, require
from app.schemas.hr_records import HrDocumentPrepare
from app.services.employee_packages import package_on
from app.services.hr_common import dubai_today, iso, names, scoped_employee
from app.services.hr_document_content import (
    CERTIFICATES,
    LABELS,
    approved_template,
    company_profile,
    document_data,
    formal_date,
    includes_salary,
    missing_prerequisites,
    needs_owner_approval,
    preview_template,
    salary_content,
    substitute,
)
from app.services.hr_document_pdf import render_document
from app.services.idempotency import claim, complete
from app.services.media import read_stored_file
from app.services.media_storage import MAX_UPLOAD_BYTES, path_for, write_document
from app.services.notification_events import active_roles, notify

UNISSUED = {"Prepared", "Pending Approval"}


def eligible_types(employee: dict) -> list[str]:
    if employee["status"] == "Active":
        return [kind for kind in LABELS if kind not in CERTIFICATES]
    if employee["status"] == "Offboarded":
        return list(CERTIFICATES)
    return []


def approval_pending(row: dict, salary_wording: set[str]) -> bool:
    """An unissued document that only the Owner may approve and issue."""
    return row["status"] in UNISSUED and (
        row["requires_approval"] or row["document_type"] in salary_wording
    )


async def salary_wording_types(session: AsyncSession) -> set[str]:
    """Document types whose approved wording includes salary or package values."""
    return {kind for kind in LABELS if salary_content(await approved_template(session, kind))}


def item_out(
    row: dict, people: dict[UUID, str], numbers: dict[UUID, str], salary_wording: set[str]
) -> dict:
    return {
        "id": str(row["id"]),
        "documentType": row["document_type"],
        "label": LABELS[row["document_type"]],
        "status": row["status"],
        "requiresApproval": row["requires_approval"] or approval_pending(row, salary_wording),
        "addressee": row["addressee"],
        "purpose": row["purpose"],
        "nocPurpose": row["noc_purpose"],
        "documentNumber": row["document_number"],
        "preparedByName": people.get(row["prepared_by_employee_id"]),
        "preparedAt": iso(row["prepared_at"]),
        "approvedByName": people.get(row["approved_by_employee_id"]),
        "approvedAt": iso(row["approved_at"]),
        "issuedByName": people.get(row["issued_by_employee_id"]),
        "issuedAt": iso(row["issued_at"]),
        "voidedByName": people.get(row["voided_by_employee_id"]),
        "voidedAt": iso(row["voided_at"]),
        "voidReason": row["void_reason"],
        "cancelledByName": people.get(row["cancelled_by_employee_id"]),
        "cancelledAt": iso(row["cancelled_at"]),
        "cancelReason": row["cancel_reason"],
        "reissueOfNumber": numbers.get(row["reissue_of_id"]) if row["reissue_of_id"] else None,
    }


async def _blockers(session: AsyncSession, employee: dict, kind: str, profile: dict) -> list[str]:
    template = await approved_template(session, kind)
    probe = {"document_type": kind, "addressee": "-", "purpose": "-", "noc_purpose": "Travel"}
    data, package = await document_data(
        session,
        employee=employee,
        issuance=probe,
        profile=profile,
        issue_date=dubai_today(),
        document_number=None,
        template=template,
    )
    return missing_prerequisites(kind, template, profile, data, package)


async def list_documents(session: AsyncSession, actor: Actor, employee_id: UUID) -> dict:
    employee = await scoped_employee(session, actor, employee_id, "hr_letter.read")
    rows = [
        dict(row)
        for row in (
            await session.execute(
                select(hr_document_issuances)
                .where(hr_document_issuances.c.employee_id == employee_id)
                .order_by(hr_document_issuances.c.prepared_at.desc())
            )
        ).mappings()
    ]
    people = await names(
        session,
        {
            row[column]
            for row in rows
            for column in (
                "prepared_by_employee_id",
                "approved_by_employee_id",
                "issued_by_employee_id",
                "voided_by_employee_id",
                "cancelled_by_employee_id",
            )
        },
    )
    numbers = {row["id"]: row["document_number"] for row in rows if row["document_number"]}
    profile = await company_profile(session)
    eligible = eligible_types(employee)
    salary_wording = await salary_wording_types(session)
    return {
        "items": [item_out(row, people, numbers, salary_wording) for row in rows],
        "eligibleTypes": [
            {
                "documentType": kind,
                "label": LABELS[kind],
                "requiresApproval": needs_owner_approval(
                    kind, await preview_template(session, kind)
                ),
                "issuanceBlockers": await _blockers(session, employee, kind, profile),
            }
            for kind in eligible
        ],
        "canPrepare": "hr_letter.write" in actor.grants,
        "canApprove": "hr_letter.approve" in actor.grants,
        "canVoid": "hr_letter.void" in actor.grants,
    }


async def _check_eligible(session: AsyncSession, employee: dict, kind: str) -> None:
    if kind not in eligible_types(employee):
        if kind in CERTIFICATES:
            raise ApiError(
                422,
                "NOT_ELIGIBLE",
                "Experience certificates are available only for Offboarded employees",
            )
        raise ApiError(422, "NOT_ELIGIBLE", "Letters are available only for Active employees")
    if kind in CERTIFICATES and employee["last_working_date"] is None:
        raise ApiError(
            422,
            "LAST_WORKING_DATE_REQUIRED",
            "The last working date was not recorded for this employee",
        )
    if (
        includes_salary(kind, await preview_template(session, kind))
        and await package_on(session, employee["id"], dubai_today()) is None
    ):
        raise ApiError(
            422,
            "PACKAGE_REQUIRED",
            "A letter with salary details requires an effective employee package",
        )


async def _create(
    session: AsyncSession,
    actor: Actor,
    employee: dict,
    values: dict,
    reissue_of: dict | None,
) -> dict:
    kind = values["document_type"]
    await _check_eligible(session, employee, kind)
    record_id = uuid4()
    requires_approval = needs_owner_approval(kind, await preview_template(session, kind))
    status = "Pending Approval" if requires_approval else "Prepared"
    await session.execute(
        hr_document_issuances.insert().values(
            id=record_id,
            employee_id=employee["id"],
            status=status,
            requires_approval=requires_approval,
            reissue_of_id=reissue_of["id"] if reissue_of else None,
            prepared_by_employee_id=actor.employee_id,
            **values,
        )
    )
    await audit.record(
        session,
        actor=actor.employee_id,
        action="hr_document.reissue_prepared" if reissue_of else "hr_document.prepared",
        module="hr_records",
        entity_type="hr_document",
        entity_id=record_id,
        after={
            "employeeId": str(employee["id"]),
            "documentType": kind,
            "status": status,
            "reissueOf": reissue_of["document_number"] if reissue_of else None,
        },
    )
    if status == "Pending Approval":
        await notify(
            session,
            await active_roles(session, {"Owner"}),
            "hr_document.approval_requested",
            f"{LABELS[kind]} awaiting approval",
            employee_id=employee["id"],
        )
    return {"id": str(record_id), "status": status}


async def prepare(
    session: AsyncSession, actor: Actor, employee_id: UUID, item: HrDocumentPrepare, key: str
) -> dict:
    try:
        employee = await scoped_employee(session, actor, employee_id, "hr_letter.write", lock=True)
        token, replay = await claim(
            session,
            actor,
            "hr_document.prepare",
            key,
            {"employeeId": str(employee_id), **item.model_dump(mode="json")},
        )
        if replay is not None:
            await session.rollback()
            return replay
        response = await _create(
            session,
            actor,
            employee,
            {
                "document_type": item.documentType,
                "addressee": item.addressee,
                "purpose": item.purpose,
                "noc_purpose": item.nocPurpose,
            },
            None,
        )
        await complete(session, token, 201, response)
        await session.commit()
        return response
    except Exception:
        await session.rollback()
        raise


async def _locked(session: AsyncSession, actor: Actor, record_id: UUID, permission: str) -> tuple:
    require(actor, permission)
    employee_id = await session.scalar(
        select(hr_document_issuances.c.employee_id).where(hr_document_issuances.c.id == record_id)
    )
    if employee_id is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    employee = await scoped_employee(session, actor, employee_id, permission, lock=True)
    row = (
        (
            await session.execute(
                select(hr_document_issuances)
                .where(hr_document_issuances.c.id == record_id)
                .with_for_update()
            )
        )
        .mappings()
        .one()
    )
    return dict(row), employee


async def _allocate(session: AsyncSession, prefix: str, year: int) -> str:
    value = await session.scalar(
        text(
            "INSERT INTO hr_document_sequences (id, prefix, year, last_value) "
            "VALUES (gen_random_uuid(), :prefix, :year, 1) "
            "ON CONFLICT (prefix, year) DO UPDATE "
            "SET last_value = hr_document_sequences.last_value + 1 RETURNING last_value"
        ).bindparams(prefix=prefix, year=year)
    )
    return f"{prefix}-{year}-{value:06d}"


async def _issue(
    session: AsyncSession, actor: Actor, row: dict, employee: dict, *, approving: bool
) -> dict:
    kind = row["document_type"]
    await _check_eligible(session, employee, kind)
    profile = await company_profile(session)
    template = await approved_template(session, kind)
    if not approving and (row["requires_approval"] or needs_owner_approval(kind, template)):
        raise ApiError(403, "APPROVAL_REQUIRED", "This document must be approved by the Owner")
    today = dubai_today()
    data, package = await document_data(
        session,
        employee=employee,
        issuance=row,
        profile=profile,
        issue_date=today,
        document_number=None,
        template=template,
    )
    missing = missing_prerequisites(kind, template, profile, data, package)
    if missing or template is None:
        raise ApiError(422, "ISSUANCE_BLOCKED", "Issuance requires: " + "; ".join(missing))
    number = await _allocate(session, "HR-CRT" if kind in CERTIFICATES else "HR-LTR", today.year)
    data["document_number"] = number
    title = substitute(template["title"], data)
    pdf = render_document(
        title=title,
        body=substitute(template["body"], data),
        company=profile,
        document_number=number,
        issue_date=formal_date(today) or "",
        addressee=row["addressee"],
        certificate=kind in CERTIFICATES,
        draft=False,
    )
    if len(pdf) > MAX_UPLOAD_BYTES:
        raise ApiError(422, "DOCUMENT_SIZE_LIMIT", "The generated document is too large")
    key = write_document("hr_issued_document", pdf, ".pdf")
    try:
        file_id = uuid4()
        await session.execute(
            stored_files.insert().values(
                id=file_id,
                kind="hr_issued_document",
                storage_key=key,
                content_type="application/pdf",
                byte_size=len(pdf),
                uploaded_by_employee_id=actor.employee_id,
            )
        )
        now = utcnow()
        snapshot = {
            "values": data,
            "title": title,
            "template": {
                "id": str(template["id"]),
                "version": template["version"],
                "title": template["title"],
            },
            "issueDate": today.isoformat(),
            "packageId": str(package["id"]) if package else None,
        }
        await session.execute(
            update(hr_document_issuances)
            .where(hr_document_issuances.c.id == row["id"])
            .values(
                status="Issued",
                document_number=number,
                template_id=template["id"],
                snapshot=snapshot,
                file_id=file_id,
                issued_by_employee_id=actor.employee_id,
                issued_at=now,
                **(
                    {"approved_by_employee_id": actor.employee_id, "approved_at": now}
                    if approving
                    else {}
                ),
            )
        )
        if approving:
            await audit.record(
                session,
                actor=actor.employee_id,
                action="hr_document.approved",
                module="hr_records",
                entity_type="hr_document",
                entity_id=row["id"],
                before={"status": row["status"]},
                after={"status": "Approved"},
            )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="hr_document.issued",
            module="hr_records",
            entity_type="hr_document",
            entity_id=row["id"],
            before={"status": row["status"]},
            after={
                "status": "Issued",
                "documentNumber": number,
                "documentType": kind,
                "templateVersion": template["version"],
                "issueDate": today.isoformat(),
            },
        )
        await session.commit()
    except Exception:
        path_for(key).unlink(missing_ok=True)
        raise
    return {"id": str(row["id"]), "status": "Issued", "documentNumber": number}


async def issue(session: AsyncSession, actor: Actor, record_id: UUID) -> dict:
    try:
        row, employee = await _locked(session, actor, record_id, "hr_letter.write")
        if row["requires_approval"]:
            raise ApiError(403, "APPROVAL_REQUIRED", "This document must be approved by the Owner")
        if row["status"] != "Prepared":
            raise ApiError(409, "HR_DOCUMENT_STATE", "This document is not awaiting issue")
        return await _issue(session, actor, row, employee, approving=False)
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(409, "CONFLICT", "The document changed; reload and try again") from exc
    except Exception:
        await session.rollback()
        raise


async def approve(session: AsyncSession, actor: Actor, record_id: UUID) -> dict:
    try:
        row, employee = await _locked(session, actor, record_id, "hr_letter.approve")
        if not approval_pending(row, await salary_wording_types(session)):
            raise ApiError(409, "HR_DOCUMENT_STATE", "This document is not awaiting approval")
        return await _issue(session, actor, row, employee, approving=True)
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(409, "CONFLICT", "The document changed; reload and try again") from exc
    except Exception:
        await session.rollback()
        raise


async def cancel(session: AsyncSession, actor: Actor, record_id: UUID, reason: str) -> None:
    try:
        permission = "hr_letter.write" if "hr_letter.write" in actor.grants else "hr_letter.approve"
        row, _ = await _locked(session, actor, record_id, permission)
        if row["status"] not in UNISSUED:
            raise ApiError(409, "HR_DOCUMENT_STATE", "Only an unissued document can be cancelled")
        await session.execute(
            update(hr_document_issuances)
            .where(hr_document_issuances.c.id == record_id)
            .values(
                status="Cancelled",
                cancelled_by_employee_id=actor.employee_id,
                cancelled_at=utcnow(),
                cancel_reason=reason,
            )
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="hr_document.cancelled",
            module="hr_records",
            entity_type="hr_document",
            entity_id=record_id,
            before={"status": row["status"]},
            after={"status": "Cancelled", "reason": reason},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def void(session: AsyncSession, actor: Actor, record_id: UUID, reason: str) -> None:
    try:
        row, _ = await _locked(session, actor, record_id, "hr_letter.void")
        if row["status"] != "Issued":
            raise ApiError(409, "HR_DOCUMENT_STATE", "Only an issued document can be voided")
        await session.execute(
            update(hr_document_issuances)
            .where(hr_document_issuances.c.id == record_id)
            .values(
                status="Voided",
                voided_by_employee_id=actor.employee_id,
                voided_at=utcnow(),
                void_reason=reason,
            )
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="hr_document.voided",
            module="hr_records",
            entity_type="hr_document",
            entity_id=record_id,
            before={"status": "Issued", "documentNumber": row["document_number"]},
            after={"status": "Voided", "reason": reason},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def reissue(session: AsyncSession, actor: Actor, record_id: UUID, key: str) -> dict:
    try:
        row, employee = await _locked(session, actor, record_id, "hr_letter.write")
        token, replay = await claim(
            session, actor, "hr_document.reissue", key, {"sourceId": str(record_id)}
        )
        if replay is not None:
            await session.rollback()
            return replay
        if row["status"] not in {"Issued", "Voided"}:
            raise ApiError(
                409, "HR_DOCUMENT_STATE", "Only an issued or voided document can be reissued"
            )
        response = await _create(
            session,
            actor,
            employee,
            {
                "document_type": row["document_type"],
                "addressee": row["addressee"],
                "purpose": row["purpose"],
                "noc_purpose": row["noc_purpose"],
            },
            row,
        )
        await complete(session, token, 201, response)
        await session.commit()
        return response
    except Exception:
        await session.rollback()
        raise


async def preview(session: AsyncSession, actor: Actor, record_id: UUID) -> bytes:
    require(actor, "hr_letter.read")
    row = (
        (
            await session.execute(
                select(hr_document_issuances).where(hr_document_issuances.c.id == record_id)
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    employee = await scoped_employee(session, actor, row["employee_id"], "hr_letter.read")
    if row["status"] not in UNISSUED:
        raise ApiError(409, "HR_DOCUMENT_STATE", "Open the issued document instead")
    profile = await company_profile(session)
    template = await preview_template(session, row["document_type"])
    today = dubai_today()
    data, _ = await document_data(
        session,
        employee=employee,
        issuance=dict(row),
        profile=profile,
        issue_date=today,
        document_number=None,
        template=template,
    )
    return render_document(
        title=substitute(template["title"], data),
        body=substitute(template["body"], data),
        company=profile,
        document_number=None,
        issue_date=formal_date(today) or "",
        addressee=row["addressee"],
        certificate=row["document_type"] in CERTIFICATES,
        draft=True,
    )


async def download(session: AsyncSession, actor: Actor, record_id: UUID) -> tuple[bytes, str]:
    require(actor, "hr_letter.read")
    row = (
        (
            await session.execute(
                select(hr_document_issuances).where(hr_document_issuances.c.id == record_id)
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None or row["file_id"] is None:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    await scoped_employee(session, actor, row["employee_id"], "hr_letter.read")
    data, _ = await read_stored_file(session, row["file_id"], "hr_issued_document")
    await audit.record(
        session,
        actor=actor.employee_id,
        action="hr_document.downloaded",
        module="hr_records",
        entity_type="hr_document",
        entity_id=record_id,
        context={"documentNumber": row["document_number"]},
    )
    await session.commit()
    suffix = "-VOIDED" if row["status"] == "Voided" else ""
    return data, f"{row['document_number']}{suffix}.pdf"
