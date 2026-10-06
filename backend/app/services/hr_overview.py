"""Cross-employee HR & PRO list reads inside the actor's employee scope."""

from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.hr_records import (
    employee_document_types,
    employee_documents,
    employee_packages,
    hr_document_issuances,
    visa_records,
)
from app.db.organization import branches, departments, employees
from app.policies import Actor, require
from app.repositories.employee_scope import employee_query
from app.services.employee_packages import applicable
from app.services.hr_common import dubai_today, iso, names
from app.services.hr_document_content import CERTIFICATES, LABELS
from app.services.hr_documents import item_out, salary_wording_types
from app.services.visa_records import EXPIRY_TRACKED
from app.whole_numbers import whole_text


async def _people(session: AsyncSession, actor: Actor, permission: str) -> list[dict]:
    require(actor, permission)
    query = (
        employee_query(actor)
        .add_columns(
            branches.c.name.label("branch_name"), departments.c.name.label("department_name")
        )
        .outerjoin(branches, branches.c.id == employees.c.branch_id)
        .outerjoin(departments, departments.c.id == employees.c.department_id)
        .order_by(employees.c.full_name, employees.c.id)
    )
    return [dict(row) for row in (await session.execute(query)).mappings()]


def _person(row: dict) -> dict:
    return {
        "employeeId": str(row["id"]),
        "fullName": row["full_name"],
        "employeeCode": row["company_employee_code"],
        "designation": row["designation"],
        "branchName": row["branch_name"],
        "departmentName": row["department_name"],
        "employeeStatus": row["status"],
    }


def _grouped(rows, key: str) -> dict[UUID, list[dict]]:
    grouped: dict[UUID, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row[key], []).append(dict(row))
    return grouped


async def packages_overview(session: AsyncSession, actor: Actor) -> dict:
    people = await _people(session, actor, "package.read")
    ids = [row["id"] for row in people]
    versions = _grouped(
        (
            await session.execute(
                select(employee_packages)
                .where(employee_packages.c.employee_id.in_(ids))
                .order_by(employee_packages.c.effective_date.desc())
            )
        ).mappings(),
        "employee_id",
    )
    today = dubai_today()
    items = []
    for person in people:
        rows = versions.get(person["id"], [])
        current = applicable(rows, today)
        upcoming = next((row for row in reversed(rows) if row["effective_date"] > today), None)
        items.append(
            {
                **_person(person),
                "currentTotalAed": whole_text(current["total_monthly_aed"]) if current else None,
                "currentEffectiveDate": iso(current["effective_date"]) if current else None,
                "upcomingTotalAed": whole_text(upcoming["total_monthly_aed"]) if upcoming else None,
                "upcomingEffectiveDate": iso(upcoming["effective_date"]) if upcoming else None,
                "versionCount": len(rows),
            }
        )
    return {"items": items, "canManage": "package.write" in actor.grants}


async def documents_overview(session: AsyncSession, actor: Actor) -> dict:
    people = await _people(session, actor, "employee_document.read")
    ids = [row["id"] for row in people]
    required = set(
        (
            await session.execute(
                select(employee_document_types.c.id).where(
                    employee_document_types.c.required_at_onboarding.is_(True)
                )
            )
        ).scalars()
    )
    current = _grouped(
        (
            await session.execute(
                select(
                    employee_documents.c.employee_id,
                    employee_documents.c.document_type_id,
                    employee_documents.c.expiry_date,
                ).where(
                    employee_documents.c.employee_id.in_(ids),
                    employee_documents.c.status == "Current",
                )
            )
        ).mappings(),
        "employee_id",
    )
    today = dubai_today()
    items = []
    for person in people:
        rows = current.get(person["id"], [])
        expiries = [row["expiry_date"] for row in rows if row["expiry_date"] is not None]
        upcoming = [value for value in expiries if value >= today]
        items.append(
            {
                **_person(person),
                "currentCount": len(rows),
                "missingRequired": len(required - {row["document_type_id"] for row in rows}),
                "expiredCount": sum(value < today for value in expiries),
                "nextExpiryDate": iso(min(upcoming)) if upcoming else None,
            }
        )
    return {"items": items, "canUpload": "employee_document.write" in actor.grants}


async def visa_overview(session: AsyncSession, actor: Actor) -> dict:
    people = await _people(session, actor, "visa.read")
    ids = [row["id"] for row in people]
    records = _grouped(
        (
            await session.execute(
                select(visa_records)
                .where(visa_records.c.employee_id.in_(ids))
                .order_by(visa_records.c.created_at.desc())
            )
        ).mappings(),
        "employee_id",
    )
    today = dubai_today()
    items = []
    for person in people:
        rows = records.get(person["id"], [])
        current = next((row for row in rows if row["status"] != "Cancelled"), None)
        expiry_date = current["expiry_date"] if current else None
        tracked = current is not None and current["status"] in EXPIRY_TRACKED
        items.append(
            {
                **_person(person),
                "visaStatus": current["status"] if current else None,
                "visaType": current["visa_type"] if current else None,
                "expiryDate": iso(current["expiry_date"]) if current else None,
                "expired": tracked and expiry_date is not None and expiry_date < today,
                "workPermitExpiryDate": iso(current["work_permit_expiry_date"])
                if current
                else None,
                "recordCount": len(rows),
            }
        )
    return {"items": items, "canManage": "visa.write" in actor.grants}


async def hr_documents_overview(
    session: AsyncSession, actor: Actor, category: Literal["letter", "certificate"]
) -> dict:
    people = {row["id"]: row for row in await _people(session, actor, "hr_letter.read")}
    kinds = CERTIFICATES if category == "certificate" else set(LABELS) - CERTIFICATES
    rows = [
        dict(row)
        for row in (
            await session.execute(
                select(hr_document_issuances)
                .where(
                    hr_document_issuances.c.employee_id.in_(list(people)),
                    hr_document_issuances.c.document_type.in_(sorted(kinds)),
                )
                .order_by(hr_document_issuances.c.prepared_at.desc())
            )
        ).mappings()
    ]
    actors = await names(
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
    reissued = {
        row["id"]: row["document_number"]
        for row in (
            await session.execute(
                select(hr_document_issuances.c.id, hr_document_issuances.c.document_number).where(
                    hr_document_issuances.c.id.in_(
                        [row["reissue_of_id"] for row in rows if row["reissue_of_id"]]
                    )
                )
            )
        ).mappings()
    }
    salary_wording = await salary_wording_types(session)
    return {
        "items": [
            {
                **item_out(row, actors, reissued, salary_wording),
                **_person(people[row["employee_id"]]),
            }
            for row in rows
        ],
        "canPrepare": "hr_letter.write" in actor.grants,
        "canApprove": "hr_letter.approve" in actor.grants,
        "canVoid": "hr_letter.void" in actor.grants,
    }
