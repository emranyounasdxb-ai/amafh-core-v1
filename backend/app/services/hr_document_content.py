"""Authoritative letter and certificate data, placeholders and issuance prerequisites."""

import re
from datetime import date
from uuid import UUID

import pycountry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.hr_records import hr_company_profile, hr_document_templates
from app.db.organization import assignment_history, branches, departments, designations
from app.errors import ApiError
from app.services.employee_packages import package_on
from app.whole_numbers import round_whole

LABELS = {
    "salary_letter": "Salary letter",
    "employment_verification": "Employment verification letter",
    "noc": "No Objection Certificate",
    "salary_transfer_letter": "Salary transfer letter",
    "experience_certificate": "Experience certificate",
}
REQUIRES_APPROVAL = {"salary_letter", "salary_transfer_letter", "experience_certificate"}
SALARY_TYPES = {"salary_letter", "salary_transfer_letter"}
SALARY_PERMITTED = SALARY_TYPES | {"employment_verification", "noc"}
CERTIFICATES = {"experience_certificate"}

PLACEHOLDERS: dict[str, tuple[str, bool]] = {
    "employee_name": ("Employee full name", False),
    "company_employee_code": ("Company Employee Code", False),
    "designation": ("Current designation", False),
    "branch": ("Current Branch", False),
    "department": ("Current Department", False),
    "date_of_joining": ("Date of joining", False),
    "nationality": ("Nationality", False),
    "passport_number": ("Passport number", False),
    "emirates_id_number": ("Emirates ID number", False),
    "last_working_date": ("Last working date (former employees)", False),
    "designation_history": ("Positions held, from assignment history", False),
    "addressee": ("Addressee", False),
    "purpose": ("Purpose", False),
    "noc_purpose": ("NOC purpose category (travel, bank or visa)", False),
    "issue_date": ("Dubai issue date", False),
    "document_number": ("Document number", False),
    "company_legal_name": ("Company legal name", False),
    "company_address": ("Company address", False),
    "trade_license_number": ("Trade licence number", False),
    "signatory_name": ("Signatory name", False),
    "signatory_designation": ("Signatory designation", False),
    "salary_breakdown": ("Monthly package breakdown in whole AED", True),
    "basic_salary": ("Basic salary in whole AED", True),
    "housing_allowance": ("Housing allowance in whole AED", True),
    "transport_allowance": ("Transport allowance in whole AED", True),
    "other_allowance_label": ("Other allowance label", True),
    "other_allowance": ("Other allowance in whole AED", True),
    "total_monthly_package": ("Total monthly package in whole AED", True),
}
TOKEN = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")
COMPANY_FIELDS = {
    "company_legal_name": "Company legal name",
    "company_address": "Company address",
    "trade_license_number": "Trade licence number",
    "signatory_name": "Signatory name",
    "signatory_designation": "Signatory designation",
}
NOT_RECORDED = "[not recorded]"


def placeholders_in(body: str) -> set[str]:
    return set(TOKEN.findall(body))


def salary_content(template: dict | None) -> bool:
    """Whether stored wording renders salary or package values."""
    if template is None:
        return False
    used = placeholders_in(template["body"]) | placeholders_in(template["title"])
    return any(PLACEHOLDERS.get(key, ("", False))[1] for key in used)


def includes_salary(document_type: str, template: dict | None) -> bool:
    return document_type in SALARY_TYPES or salary_content(template)


def needs_owner_approval(document_type: str, template: dict | None) -> bool:
    return document_type in REQUIRES_APPROVAL or salary_content(template)


def validate_template(document_type: str, title: str, body: str) -> None:
    used = placeholders_in(body) | placeholders_in(title)
    unknown = sorted(used - PLACEHOLDERS.keys())
    if unknown:
        raise ApiError(
            422, "TEMPLATE_PLACEHOLDER_UNKNOWN", f"Unknown placeholders: {', '.join(unknown)}"
        )
    salary = sorted(key for key in used if PLACEHOLDERS[key][1])
    if salary and document_type not in SALARY_PERMITTED:
        raise ApiError(
            422,
            "TEMPLATE_SALARY_NOT_ALLOWED",
            "Salary details are not allowed in experience certificates",
        )


def formal_date(value: date | None) -> str | None:
    return value.strftime("%d %B %Y") if value else None


def aed(value) -> str | None:
    return None if value is None else f"AED {int(round_whole(value)):,}"


async def company_profile(session: AsyncSession) -> dict:
    row = (
        (await session.execute(select(hr_company_profile).where(hr_company_profile.c.id == 1)))
        .mappings()
        .one_or_none()
    )
    return dict(row) if row else {key: None for key in COMPANY_FIELDS}


async def approved_template(session: AsyncSession, document_type: str) -> dict | None:
    row = (
        (
            await session.execute(
                select(hr_document_templates).where(
                    hr_document_templates.c.document_type == document_type,
                    hr_document_templates.c.status == "Approved",
                )
            )
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row else None


async def preview_template(session: AsyncSession, document_type: str) -> dict:
    """The approved wording, or the newest Draft when none is approved yet."""
    approved = await approved_template(session, document_type)
    if approved:
        return approved
    row = (
        (
            await session.execute(
                select(hr_document_templates)
                .where(hr_document_templates.c.document_type == document_type)
                .order_by(hr_document_templates.c.version.desc())
                .limit(1)
            )
        )
        .mappings()
        .one()
    )
    return dict(row)


async def _names(session: AsyncSession, table, ident: UUID | None) -> str | None:
    if ident is None:
        return None
    return await session.scalar(select(table.c.name).where(table.c.id == ident))


async def _history(session: AsyncSession, employee: dict) -> str | None:
    rows = (
        await session.execute(
            select(
                designations.c.name,
                assignment_history.c.assignment_start_date,
                assignment_history.c.assignment_end_date,
            )
            .join(designations, designations.c.id == assignment_history.c.designation_id)
            .where(assignment_history.c.employee_id == employee["id"])
            .order_by(assignment_history.c.assignment_start_date, assignment_history.c.created_at)
        )
    ).all()
    merged: list[list] = []
    for name, start, end in rows:
        if merged and merged[-1][0] == name:
            merged[-1][2] = end
        else:
            merged.append([name, start, end])
    if not merged:
        return None
    lines = []
    for index, (name, start, end) in enumerate(merged):
        final = index == len(merged) - 1
        until = employee["last_working_date"] if final else end
        period = f"from {formal_date(start)}"
        if until:
            period += f" to {formal_date(until)}"
        lines.append(f"• {name}, {period}")
    return "\n".join(lines)


def _salary_breakdown(package: dict | None) -> str | None:
    if package is None:
        return None
    lines = [f"Basic salary: {aed(package['basic_salary_aed'])} per month"]
    if package["housing_allowance_aed"] is not None:
        lines.append(f"Housing allowance: {aed(package['housing_allowance_aed'])} per month")
    if package["transport_allowance_aed"] is not None:
        lines.append(f"Transport allowance: {aed(package['transport_allowance_aed'])} per month")
    if package["other_allowance_aed"] is not None:
        lines.append(
            f"{package['other_allowance_label']}: {aed(package['other_allowance_aed'])} per month"
        )
    lines.append(f"Total monthly package: {aed(package['total_monthly_aed'])}")
    return "\n".join(lines)


async def document_data(
    session: AsyncSession,
    *,
    employee: dict,
    issuance: dict,
    profile: dict,
    issue_date: date,
    document_number: str | None,
    template: dict | None,
) -> tuple[dict[str, str | None], dict | None]:
    package = (
        await package_on(session, employee["id"], issue_date)
        if includes_salary(issuance["document_type"], template)
        else None
    )
    country = (
        pycountry.countries.get(alpha_2=employee["nationality"])
        if employee["nationality"]
        else None
    )
    data: dict[str, str | None] = {
        "employee_name": employee["full_name"],
        "company_employee_code": employee["company_employee_code"],
        "designation": employee.get("designation")
        or await _names(session, designations, employee["designation_id"]),
        "branch": await _names(session, branches, employee["branch_id"]),
        "department": await _names(session, departments, employee["department_id"]),
        "date_of_joining": formal_date(employee["date_of_joining"]),
        "nationality": getattr(country, "common_name", None) or getattr(country, "name", None),
        "passport_number": employee["passport_number"],
        "emirates_id_number": employee["emirates_id_number"],
        "last_working_date": formal_date(employee["last_working_date"]),
        "designation_history": await _history(session, employee),
        "addressee": issuance["addressee"],
        "purpose": issuance["purpose"].strip().rstrip(".") if issuance["purpose"] else None,
        "noc_purpose": issuance["noc_purpose"].lower() if issuance["noc_purpose"] else None,
        "issue_date": formal_date(issue_date),
        "document_number": document_number,
        **{key: profile.get(key) for key in COMPANY_FIELDS},
        "salary_breakdown": _salary_breakdown(package),
        "basic_salary": aed(package["basic_salary_aed"]) if package else None,
        "housing_allowance": aed(package["housing_allowance_aed"]) if package else None,
        "transport_allowance": aed(package["transport_allowance_aed"]) if package else None,
        "other_allowance_label": package["other_allowance_label"] if package else None,
        "other_allowance": aed(package["other_allowance_aed"]) if package else None,
        "total_monthly_package": aed(package["total_monthly_aed"]) if package else None,
    }
    return data, package


def substitute(text: str, data: dict[str, str | None]) -> str:
    return TOKEN.sub(lambda match: data.get(match.group(1)) or NOT_RECORDED, text)


def missing_prerequisites(
    document_type: str,
    template: dict | None,
    profile: dict,
    data: dict[str, str | None],
    package: dict | None,
) -> list[str]:
    missing = []
    if template is None or template["status"] != "Approved":
        missing.append(f"Approved {LABELS[document_type].lower()} wording")
    missing.extend(label for key, label in COMPANY_FIELDS.items() if not profile.get(key))
    if includes_salary(document_type, template) and package is None:
        missing.append("An employee package effective on the issue date")
    if template is not None:
        used = placeholders_in(template["body"]) | placeholders_in(template["title"])
        for key in sorted(used - COMPANY_FIELDS.keys() - {"document_number"}):
            if not data.get(key) and not (PLACEHOLDERS[key][1] and package is None):
                missing.append(f"{PLACEHOLDERS[key][0]} (not recorded)")
    return missing
