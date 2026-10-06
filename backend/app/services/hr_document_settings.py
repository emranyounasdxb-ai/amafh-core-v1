"""Owner-managed company details and Draft-first letter and certificate wording."""

from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db.base import utcnow
from app.db.hr_records import hr_company_profile, hr_document_templates
from app.errors import ApiError
from app.policies import Actor, require
from app.schemas.hr_records import CompanyProfileUpdate, TemplateDraft
from app.services.hr_common import iso, names
from app.services.hr_document_content import (
    COMPANY_FIELDS,
    LABELS,
    PLACEHOLDERS,
    company_profile,
    needs_owner_approval,
    validate_template,
)

API_FIELDS = {
    "company_legal_name": "companyLegalName",
    "company_address": "companyAddress",
    "trade_license_number": "tradeLicenseNumber",
    "signatory_name": "signatoryName",
    "signatory_designation": "signatoryDesignation",
}


def _template_out(row: dict, people: dict[UUID, str]) -> dict:
    return {
        "id": str(row["id"]),
        "version": row["version"],
        "title": row["title"],
        "body": row["body"],
        "status": row["status"],
        "createdByName": people.get(row["created_by_employee_id"]),
        "createdAt": iso(row["created_at"]),
        "approvedByName": people.get(row["approved_by_employee_id"]),
        "approvedAt": iso(row["approved_at"]),
        "retiredAt": iso(row["retired_at"]),
    }


async def read_settings(session: AsyncSession, actor: Actor) -> dict:
    if not ({"hr_letter.read", "hr_settings.write"} & actor.grants):
        raise ApiError(403, "FORBIDDEN", "Access denied")
    profile = await company_profile(session)
    rows = [
        dict(row)
        for row in (
            await session.execute(
                select(hr_document_templates).order_by(
                    hr_document_templates.c.document_type, hr_document_templates.c.version.desc()
                )
            )
        ).mappings()
    ]
    people = await names(
        session,
        {row["created_by_employee_id"] for row in rows}
        | {row["approved_by_employee_id"] for row in rows}
        | {profile.get("updated_by_employee_id")},
    )
    updated_by = profile.get("updated_by_employee_id")
    templates = []
    for kind, label in LABELS.items():
        versions = [row for row in rows if row["document_type"] == kind]
        approved = next((row for row in versions if row["status"] == "Approved"), None)
        latest = versions[0] if versions else None
        templates.append(
            {
                "documentType": kind,
                "label": label,
                "requiresApproval": needs_owner_approval(kind, approved or latest),
                "approved": _template_out(approved, people) if approved else None,
                "latest": _template_out(latest, people) if latest else None,
                "versions": [_template_out(row, people) for row in versions],
            }
        )
    return {
        "company": {
            **{api: profile.get(column) for column, api in API_FIELDS.items()},
            "updatedByName": people.get(updated_by) if updated_by is not None else None,
            "updatedAt": iso(profile.get("updated_at")),
        },
        "missingCompanyDetails": [
            label for key, label in COMPANY_FIELDS.items() if not profile.get(key)
        ],
        "templates": templates,
        "placeholders": [
            {"key": key, "description": description, "salary": salary}
            for key, (description, salary) in PLACEHOLDERS.items()
        ],
        "canManage": "hr_settings.write" in actor.grants,
    }


async def update_company(session: AsyncSession, actor: Actor, item: CompanyProfileUpdate) -> dict:
    require(actor, "hr_settings.write")
    try:
        profile = (
            (
                await session.execute(
                    select(hr_company_profile).where(hr_company_profile.c.id == 1).with_for_update()
                )
            )
            .mappings()
            .one()
        )
        values = {column: getattr(item, api) for column, api in API_FIELDS.items()}
        changed = {key: value for key, value in values.items() if profile[key] != value}
        if changed:
            await session.execute(
                update(hr_company_profile)
                .where(hr_company_profile.c.id == 1)
                .values(**changed, updated_at=utcnow(), updated_by_employee_id=actor.employee_id)
            )
            await audit.record(
                session,
                actor=actor.employee_id,
                action="hr_company_profile.updated",
                module="hr_records",
                entity_type="hr_company_profile",
                entity_id="1",
                before={API_FIELDS[key]: profile[key] for key in changed},
                after={API_FIELDS[key]: value for key, value in changed.items()},
            )
        await session.commit()
        return {"changed": bool(changed)}
    except Exception:
        await session.rollback()
        raise


async def draft_template(
    session: AsyncSession, actor: Actor, document_type: str, item: TemplateDraft
) -> dict:
    require(actor, "hr_settings.write")
    if document_type not in LABELS:
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    validate_template(document_type, item.title, item.body)
    try:
        await session.execute(
            select(
                func.pg_advisory_xact_lock(func.hashtextextended(f"hr_template:{document_type}", 0))
            )
        )
        version = (
            await session.scalar(
                select(func.max(hr_document_templates.c.version)).where(
                    hr_document_templates.c.document_type == document_type
                )
            )
            or 0
        ) + 1
        template_id = uuid4()
        await session.execute(
            hr_document_templates.insert().values(
                id=template_id,
                document_type=document_type,
                version=version,
                title=item.title,
                body=item.body,
                status="Draft",
                created_by_employee_id=actor.employee_id,
            )
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="hr_template.drafted",
            module="hr_records",
            entity_type="hr_document_template",
            entity_id=template_id,
            after={"documentType": document_type, "version": version, "title": item.title},
        )
        await session.commit()
        return {"id": str(template_id), "version": version, "status": "Draft"}
    except Exception:
        await session.rollback()
        raise


async def approve_template(session: AsyncSession, actor: Actor, template_id: UUID) -> dict:
    require(actor, "hr_settings.write")
    try:
        row = (
            (
                await session.execute(
                    select(hr_document_templates)
                    .where(hr_document_templates.c.id == template_id)
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ApiError(404, "NOT_FOUND", "Record unavailable")
        if row["status"] != "Draft":
            raise ApiError(409, "TEMPLATE_NOT_DRAFT", "Only Draft wording can be approved")
        latest = await session.scalar(
            select(func.max(hr_document_templates.c.version)).where(
                hr_document_templates.c.document_type == row["document_type"]
            )
        )
        if row["version"] != latest:
            raise ApiError(
                409, "TEMPLATE_NOT_LATEST", "Only the newest wording version can be approved"
            )
        validate_template(row["document_type"], row["title"], row["body"])
        now = utcnow()
        await session.execute(
            update(hr_document_templates)
            .where(
                hr_document_templates.c.document_type == row["document_type"],
                hr_document_templates.c.status == "Approved",
            )
            .values(status="Retired", retired_at=now)
        )
        await session.execute(
            update(hr_document_templates)
            .where(hr_document_templates.c.id == template_id)
            .values(status="Approved", approved_by_employee_id=actor.employee_id, approved_at=now)
        )
        await audit.record(
            session,
            actor=actor.employee_id,
            action="hr_template.approved",
            module="hr_records",
            entity_type="hr_document_template",
            entity_id=template_id,
            before={"status": "Draft"},
            after={
                "status": "Approved",
                "documentType": row["document_type"],
                "version": row["version"],
            },
        )
        await session.commit()
        return {"id": str(template_id), "status": "Approved"}
    except Exception:
        await session.rollback()
        raise
